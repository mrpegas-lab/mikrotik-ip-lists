# ============================================================
#  Google DNS over HTTPS (DoH) для MikroTik RouterOS 7.19+
# ============================================================
#  ВНИМАНИЕ:
#   Начиная с RouterOS 7.19 корневые сертификаты встроены,
#   но при обновлении с более старой версии могут быть
#   НЕ активны.
#
#   Проверь:
#     /certificate/settings print
#   Если builtin-trust-anchors = untrusted — выполни:
#     /certificate/settings/set builtin-trust-anchors=trusted
#
#   Требуется RouterOS 7.19 или новее (в 6.x DoH нет).
# ============================================================

# Статическая запись, чтобы роутер знал IP dns.google до включения DoH
/ip dns static
add name=dns.google type=A address=8.8.4.4 comment="DoH bootstrap"
add name=dns.google type=A address=8.8.8.8 comment="DoH bootstrap"

# Включаем DoH
/ip dns
set use-doh-server=https://dns.google/dns-query verify-doh-cert=yes