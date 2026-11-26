import ipaddress
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

# ============================================================
#  НАСТРОЙКИ — то, что чаще всего хочется поменять
# ============================================================

LIST_NAME = "vpn-targets"          # имя общего address-list на роутере
COMBINED_FILE = "vpn-targets.rsc"  # общий файл (домены + все источники + автоочистка)

SOURCES_LIST = "vpn-target"       # address-list с доменами источников обновлений
SOURCES_FILE = "vpn-sources.rsc"   # лежит в extras/, импортируется первым

TIMEOUT = 30     # таймаут одного HTTP-запроса, секунд
RETRIES = 3      # попыток на один URL
RETRY_DELAY = 5  # пауза между попытками растёт линейно: 5с, 10с, ...

# --- Пути считаем относительно самого скрипта, а не cwd ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output_rsc")
EXTRAS_DIR = os.path.join(BASE_DIR, "extras")
DOMAINS_FILE = os.path.join(BASE_DIR, "domains.txt")

# ============================================================
#  ИСТОЧНИКИ — кого качаем
# ============================================================

# --- Источники JSON ---
GOOGLE_SOURCES = {
    "https://www.gstatic.com/ipranges/goog.json": "google",
    "https://www.gstatic.com/ipranges/cloud.json": "google",
}

SOURCES = {
    "https://openai.com/gptbot.json": "gptbot",
    "https://openai.com/chatgpt-user.json": "chatgpt",
}

# AWS — скачивается один раз, из него режем и общий список, и CloudFront
AWS_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"

# --- Источники текстовых CIDR ---
TEXT_CIDR_SOURCES = {
    "https://core.telegram.org/resources/cidr.txt": "telegram",
}

# ipverse/as-ip-blocks — ежедневно обновляемые агрегированные BGP-префиксы по ASN:
#   AS714   Apple Inc.
#   AS2906  Netflix Streaming Services Inc. (основной стриминг)
#   AS40027 Netflix Streaming Services Inc.
#   AS55095 Netflix Inc (корпоративный)
#   AS33353 Sony Interactive Entertainment LLC (PlayStation Network)
#   AS32934 Facebook Inc. (Meta: Facebook/Instagram/WhatsApp, включая relay звонков)
#   AS63293 Facebook Inc. (Meta Offnet)
IPVERSE_ASN_SOURCES = {
    714: "apple",
    2906: "netflix",
    40027: "netflix",
    55095: "netflix",
    33353: "playstation",
    32934: "meta",
    63293: "meta",
}

# Зеркала ipverse перебираются по очереди:
#   - raw.githubusercontent.com в некоторых сетях недоступен/задушен;
#   - jsDelivr НЕ подходит: отказывается обслуживать этот репозиторий
#     ("Package size exceeded the configured limit of 50 MB");
#   - githack и statically отдают те же файлы через свои CDN.
_IPVERSE_MIRRORS = (
    "https://raw.githack.com/ipverse/as-ip-blocks/master/as/{asn}/ipv4-aggregated.txt",
    "https://cdn.statically.io/gh/ipverse/as-ip-blocks/master/as/{asn}/ipv4-aggregated.txt",
    "https://raw.githubusercontent.com/ipverse/as-ip-blocks/master/as/{asn}/ipv4-aggregated.txt",
)

SOURCE_ORDER = ("google", "telegram", "amazon", "cloudfront", "gptbot", "chatgpt",
                "netflix", "playstation", "apple", "meta")

# Эти источники — подмножества других и в общий файл отдельно не пишутся
# (cloudfront целиком входит в amazon), но получают свой раздельный .rsc
COMBINED_SKIP = ("cloudfront",)


# ---------- Загрузка ----------

def _get(url):
    """GET с ретраями и растущей паузой между попытками."""
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT,
                             headers={"User-Agent": "MikroTik-IP-Lists/1.0"})
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_err = e
            if attempt < RETRIES:
                delay = RETRY_DELAY * attempt
                print(f"    [!] попытка {attempt}/{RETRIES} не удалась: {e}")
                print(f"        повтор через {delay} с...")
                time.sleep(delay)
    raise last_err


def download_json(url):
    data = _get(url).json()
    if not isinstance(data, dict):
        raise ValueError("Некорректный формат JSON")
    return data


def download_text(url):
    return _get(url).text


def download_ipverse(asn):
    """Качает префиксы ASN с ipverse, перебирая зеркала."""
    last_err = None
    for template in _IPVERSE_MIRRORS:
        url = template.format(asn=asn)
        try:
            return download_text(url), url
        except requests.RequestException as e:
            last_err = e
            print(f"    [!] зеркало недоступно, пробую следующее")
    raise last_err


# ---------- Парсинг ----------

def extract_ipv4_prefixes_json(data, source, service=None):
    prefixes = set()
    items = data.get("prefixes") or data.get("ipv4Prefixes") or []
    if not isinstance(items, list):
        raise ValueError("Некорректное поле prefixes")

    for item in items:
        if not isinstance(item, dict):
            continue
        if service and item.get("service") != service:
            continue
        address = item.get("ip_prefix") if source == "amazon" else item.get("ipv4Prefix")
        if not address:
            continue
        try:
            net = ipaddress.ip_network(address, strict=False)
        except ValueError:
            print(f"    [!] Некорректный CIDR: {address}")
            continue
        if net.version == 4:
            prefixes.add(str(net))
    return prefixes


def extract_ipv4_prefixes_text(text):
    prefixes = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
        except ValueError:
            print(f"    [!] Некорректный CIDR: {line}")
            continue
        if net.version == 4:
            prefixes.add(str(net))
    return prefixes


def load_domains():
    """Читает domains.txt. Возвращает список (domain, comment)."""
    if not os.path.exists(DOMAINS_FILE):
        print(f"[!] domains.txt не найден: {DOMAINS_FILE}")
        print(f"    Создай файл рядом с parser.py — в общий файл попадут домены.")
        return []

    domains = []
    with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                domain, comment = line.split("|", 1)
            else:
                domain, comment = line, "domain"
            domains.append((domain.strip(), comment.strip()))
    print(f"[*] domains.txt: загружено {len(domains)} доменов")
    return domains


# ---------- Сбор ----------

def collect_all():
    """Собирает префиксы. Ошибка одного источника не роняет сборку:
    сообщаем, пропускаем и идём дальше. Возвращает (result, failures)."""
    result = {}
    failures = []

    def report_failure(source, err):
        print(f"    [X] ОШИБКА ({source}): {err}")
        print(f"        источник пропущен, сборка продолжается")
        failures.append((source, str(err)))

    for url in GOOGLE_SOURCES:
        print(f"[*] Загружаю Google: {url}")
        try:
            data = download_json(url)
            cur = extract_ipv4_prefixes_json(data, "google")
            if not cur:
                raise ValueError("пустой ответ")
            result.setdefault("google", set()).update(cur)
            print(f"    Получено: {len(cur)}")
        except Exception as e:
            report_failure("google", e)

    for url, source in SOURCES.items():
        print(f"[*] Загружаю {source}: {url}")
        try:
            data = download_json(url)
            cur = extract_ipv4_prefixes_json(data, source)
            if not cur:
                raise ValueError("пустой ответ")
            result.setdefault(source, set()).update(cur)
            print(f"    Получено: {len(cur)}")
        except Exception as e:
            report_failure(source, e)

    # AWS: один файл — два списка (весь AWS + отдельно CloudFront edge)
    print(f"[*] Загружаю amazon: {AWS_URL}")
    try:
        aws_data = download_json(AWS_URL)

        cur = extract_ipv4_prefixes_json(aws_data, "amazon")
        if not cur:
            raise ValueError("пустой ответ")
        result.setdefault("amazon", set()).update(cur)
        print(f"    Получено: {len(cur)}")

        cur = extract_ipv4_prefixes_json(aws_data, "amazon", service="CLOUDFRONT")
        if not cur:
            raise ValueError("cloudfront: пустой ответ")
        result.setdefault("cloudfront", set()).update(cur)
        print(f"    cloudfront: {len(cur)}")
    except Exception as e:
        report_failure("amazon/cloudfront", e)

    for url, source in TEXT_CIDR_SOURCES.items():
        print(f"[*] Загружаю {source}: {url}")
        try:
            text = download_text(url)
            cur = extract_ipv4_prefixes_text(text)
            if not cur:
                raise ValueError("пустой ответ")
            result.setdefault(source, set()).update(cur)
            print(f"    Получено: {len(cur)}")
        except Exception as e:
            report_failure(source, e)

    # Префиксы по ASN через ipverse (с перебором зеркал)
    for asn, source in IPVERSE_ASN_SOURCES.items():
        print(f"[*] Загружаю {source} (AS{asn})")
        try:
            text, used_url = download_ipverse(asn)
            cur = extract_ipv4_prefixes_text(text)
            if not cur:
                raise ValueError("пустой ответ")
            result.setdefault(source, set()).update(cur)
            print(f"    Получено: {len(cur)} ({used_url.split('/as/')[0]}...)")
        except Exception as e:
            report_failure(f"{source} (AS{asn})", e)

    return result, failures


# ---------- Генерация RSC ----------

def collect_source_hosts():
    """Домены всех источников, откуда качаются списки (для vpn-sources)."""
    urls = list(GOOGLE_SOURCES) + list(SOURCES) + [AWS_URL] + list(TEXT_CIDR_SOURCES)
    urls += [t.split("/as/")[0] for t in _IPVERSE_MIRRORS]

    hosts = set()
    for url in urls:
        host = urlparse(url).netloc
        if host:
            hosts.add(host)
    return sorted(hosts)


def write_sources():
    """Отдельный список vpn-sources с доменами источников обновлений.
    Импортируется ПЕРВЫМ, чтобы роутер мог скачивать списки.
    vpn-targets.rsc его НЕ затирает. Кладётся в extras/."""
    filename = os.path.join(EXTRAS_DIR, SOURCES_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    hosts = collect_source_hosts()

    lines = []
    lines.append(f"# MikroTik address-list: {SOURCES_LIST}")
    lines.append("# Домены источников обновлений списков")
    lines.append(f"# Generated at {now}")
    lines.append("#")
    lines.append("# Импортируй ЭТОТ ФАЙЛ ПЕРВЫМ, до vpn-targets.rsc.")
    lines.append("# Через эти хосты скачиваются списки — они должны быть доступны")
    lines.append("# роутеру (и его DNS) всегда, иначе обновление списков отвалится.")
    lines.append(f"# Список {SOURCES_LIST} не очищается файлом {COMBINED_FILE}.")
    lines.append("# Требуется рабочий DNS на роутере (см. extras/doh-google.rsc).")
    lines.append("#")
    lines.append("/ip firewall address-list")
    for host in hosts:
        lines.append(f'add list={SOURCES_LIST} address={host} comment="source"')

    _write_file(filename, lines)
    print(f"[+] {filename}: {len(hosts)} доменов источников")




def sort_key(net_str):
    net = ipaddress.ip_network(net_str)
    return (int(net.network_address), net.prefixlen)


def _write_file(filename, lines):
    tmp = filename + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, filename)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_combined(prefixes_by_source, domains, failures=()):
    """Общий файл: домены + все источники + автоочистка."""
    filename = os.path.join(OUTPUT_DIR, COMBINED_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total = sum(len(v) for v in prefixes_by_source.values())

    lines = []
    lines.append(f"# MikroTik address-list: {LIST_NAME}")
    lines.append(f"# Combined list (domains + all sources)")
    lines.append(f"# Generated at {now}")
    lines.append(f"# Sources: domains, {', '.join(SOURCE_ORDER)}")
    if failures:
        failed = ", ".join(source for source, _ in failures)
        lines.append(f"# WARNING: не удалось загрузить: {failed}")
        lines.append("# WARNING: этих префиксов в файле нет — обнови позже!")
    lines.append("#")
    lines.append("# This file removes old entries from the list before import.")
    lines.append("#")
    lines.append("/ip firewall address-list")
    lines.append(f":if ([:len [/ip firewall address-list find list={LIST_NAME}]] > 0) do={{")
    lines.append(f"    /ip firewall address-list remove [find list={LIST_NAME}]")
    lines.append("}")
    lines.append("")

    # --- Домены (всегда, даже если пусто — чтобы было видно) ---
    lines.append("# --- Domains ---")
    if domains:
        for domain, comment in domains:
            lines.append(f'add list={LIST_NAME} address={domain} comment="{comment}"')
    else:
        lines.append("# (нет доменов — проверь domains.txt)")
    lines.append("")

    # --- IP-источники ---
    for source in SOURCE_ORDER:
        if source in COMBINED_SKIP:
            continue
        nets = prefixes_by_source.get(source)
        if not nets:
            continue
        lines.append(f"# --- {source} ---")
        for net in sorted(nets, key=sort_key):
            lines.append(f'add list={LIST_NAME} address={net} comment="{source}"')
        lines.append("")

    # --- Источники-подмножества (включены выше, отдельно не пишем) ---
    for source in COMBINED_SKIP:
        nets = prefixes_by_source.get(source)
        if nets:
            lines.append(f"# ({source}: {len(nets)} префиксов уже входят в секцию amazon,")
            lines.append(f"#  отдельный файл — output_rsc/{source}.rsc)")
            lines.append("")

    _write_file(filename, lines)
    print(f"[+] {filename}: {total} IPv4, {len(domains)} доменов")


def write_split(prefixes_by_source, domains):
    """Раздельные файлы по источникам и отдельный domains.rsc. Без автоочистки."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- domains.rsc ---
    filename = os.path.join(OUTPUT_DIR, "domains.rsc")
    by_comment = {}
    for domain, comment in domains:
        by_comment.setdefault(comment, []).append(domain)

    lines = []
    lines.append(f"# MikroTik address-list: {LIST_NAME}")
    lines.append("# Domains only")
    lines.append(f"# Generated at {now}")
    lines.append("#")
    lines.append("# This file does NOT remove old entries.")
    lines.append(f"# To clean up: /ip firewall address-list remove [find list={LIST_NAME}]")
    lines.append("#")
    lines.append("/ip firewall address-list")
    if by_comment:
        for comment in sorted(by_comment):
            lines.append(f"# --- {comment} ---")
            for domain in sorted(by_comment[comment]):
                lines.append(f'add list={LIST_NAME} address={domain} comment="{comment}"')
            lines.append("")
    else:
        lines.append("# (нет доменов — проверь domains.txt)")
    _write_file(filename, lines)
    print(f"[+] {filename}: {len(domains)} доменов")

    # --- <source>.rsc ---
    for source in SOURCE_ORDER:
        nets = prefixes_by_source.get(source)
        if not nets:
            continue
        filename = os.path.join(OUTPUT_DIR, f"{source}.rsc")
        lines = []
        lines.append(f"# MikroTik address-list: {LIST_NAME}")
        lines.append(f"# Source: {source}")
        lines.append(f"# Generated at {now}")
        lines.append("#")
        lines.append("# This file does NOT remove old entries.")
        lines.append(f"# To clean up: /ip firewall address-list remove [find list={LIST_NAME}]")
        lines.append("#")
        lines.append("/ip firewall address-list")
        for net in sorted(nets, key=sort_key):
            lines.append(f'add list={LIST_NAME} address={net} comment="{source}"')
        _write_file(filename, lines)
        print(f"[+] {filename}: {len(nets)} IPv4")


# ---------- Main ----------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(EXTRAS_DIR, exist_ok=True)
    write_sources()

    prefixes_by_source, failures = collect_all()
    domains = load_domains()

    write_combined(prefixes_by_source, domains, failures)
    write_split(prefixes_by_source, domains)

    print()
    if failures:
        print("=" * 60)
        print(f"[!] ГОТОВО, но {len(failures)} источник(ов) не загрузились:")
        for source, err in failures:
            print(f"    - {source}: {err}")
        print("[!] Файлы сформированы без них. Перезапусти позже.")
        print("=" * 60)
        sys.exit(1)  # файлы готовы, но код возврата сигналит о проблеме (CI/Actions)
    else:
        print("[+] Все источники загружены, файлы сформированы.")


if __name__ == "__main__":
    main()