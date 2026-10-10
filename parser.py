import ipaddress
import os
import sys
from datetime import datetime, timezone

import requests

# --- Пути считаем относительно самого скрипта, а не cwd ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output_rsc")
DOMAINS_FILE = os.path.join(BASE_DIR, "domains.txt")

# --- Источники JSON ---
GOOGLE_SOURCES = {
    "https://www.gstatic.com/ipranges/goog.json": "google",
    "https://www.gstatic.com/ipranges/cloud.json": "google",
}

SOURCES = {
    "https://openai.com/gptbot.json": "gptbot",
    "https://openai.com/chatgpt-user.json": "chatgpt",
    "https://ip-ranges.amazonaws.com/ip-ranges.json": "amazon",
}

# --- Источники текстовых CIDR ---
TELEGRAM_CIDR_URL = "https://core.telegram.org/resources/cidr.txt"

COMBINED_FILE = "vpn-targets.rsc"
LIST_NAME = "vpn-targets"
TIMEOUT = 30

SOURCE_ORDER = ("google", "telegram", "amazon", "gptbot", "chatgpt")


# ---------- Загрузка ----------

def download_json(url):
    r = requests.get(url, timeout=TIMEOUT,
                     headers={"User-Agent": "MikroTik-IP-Lists/1.0"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Некорректный формат JSON")
    return data


def download_text(url):
    r = requests.get(url, timeout=TIMEOUT,
                     headers={"User-Agent": "MikroTik-IP-Lists/1.0"})
    r.raise_for_status()
    return r.text


# ---------- Парсинг ----------

def extract_ipv4_prefixes_json(data, source):
    prefixes = set()
    items = data.get("prefixes") or data.get("ipv4Prefixes") or []
    if not isinstance(items, list):
        raise ValueError("Некорректное поле prefixes")

    for item in items:
        if not isinstance(item, dict):
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
    result = {}

    for url in GOOGLE_SOURCES:
        print(f"[*] Загружаю Google: {url}")
        data = download_json(url)
        cur = extract_ipv4_prefixes_json(data, "google")
        if not cur:
            raise ValueError(f"Google: пусто ({url})")
        result.setdefault("google", set()).update(cur)
        print(f"    Получено: {len(cur)}")

    for url, source in SOURCES.items():
        print(f"[*] Загружаю {source}: {url}")
        data = download_json(url)
        cur = extract_ipv4_prefixes_json(data, source)
        if not cur:
            raise ValueError(f"{source}: пусто")
        result.setdefault(source, set()).update(cur)
        print(f"    Получено: {len(cur)}")

    print(f"[*] Загружаю Telegram CIDR: {TELEGRAM_CIDR_URL}")
    text = download_text(TELEGRAM_CIDR_URL)
    cur = extract_ipv4_prefixes_text(text)
    if not cur:
        raise ValueError("Telegram: пусто")
    result.setdefault("telegram", set()).update(cur)
    print(f"    Получено: {len(cur)}")

    return result


# ---------- Генерация RSC ----------

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


def write_combined(prefixes_by_source, domains):
    """Общий файл: домены + все источники + автоочистка."""
    filename = os.path.join(OUTPUT_DIR, COMBINED_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total = sum(len(v) for v in prefixes_by_source.values())

    lines = []
    lines.append(f"# MikroTik address-list: {LIST_NAME}")
    lines.append(f"# Combined list (domains + all sources)")
    lines.append(f"# Generated at {now}")
    lines.append(f"# Sources: domains, google, telegram, amazon, gptbot, chatgpt")
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
        nets = prefixes_by_source.get(source)
        if not nets:
            continue
        lines.append(f"# --- {source} ---")
        for net in sorted(nets, key=sort_key):
            lines.append(f'add list={LIST_NAME} address={net} comment="{source}"')
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
    prefixes_by_source = collect_all()
    domains = load_domains()

    write_combined(prefixes_by_source, domains)
    write_split(prefixes_by_source, domains)


if __name__ == "__main__":
    main()