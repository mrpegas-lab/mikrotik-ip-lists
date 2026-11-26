# MikroTik address-list: vpn-targets
# Домены источников обновлений списков
# Generated at 2026-11-26 08:37 UTC
#
# Через эти хосты скачиваются списки — они должны быть доступны
# роутеру (и его DNS) всегда, иначе обновление списков отвалится.
# Эти же записи уже входят в общий vpn-targets.rsc.
# Требуется рабочий DNS на роутере (см. extras/doh-google.rsc).
#
/ip firewall address-list
add list=vpn-targets address=cdn.statically.io comment="source"
add list=vpn-targets address=core.telegram.org comment="source"
add list=vpn-targets address=ip-ranges.amazonaws.com comment="source"
add list=vpn-targets address=openai.com comment="source"
add list=vpn-targets address=raw.githack.com comment="source"
add list=vpn-targets address=raw.githubusercontent.com comment="source"
add list=vpn-targets address=www.gstatic.com comment="source"
