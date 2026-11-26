# MikroTik address-list: vpn-target
# Домены источников обновлений списков
# Generated at 2026-11-26 08:25 UTC
#
# Импортируй ЭТОТ ФАЙЛ ПЕРВЫМ, до vpn-targets.rsc.
# Через эти хосты скачиваются списки — они должны быть доступны
# роутеру (и его DNS) всегда, иначе обновление списков отвалится.
# Список vpn-target не очищается файлом vpn-targets.rsc.
# Требуется рабочий DNS на роутере (см. extras/doh-google.rsc).
#
/ip firewall address-list
add list=vpn-target address=cdn.statically.io comment="source"
add list=vpn-target address=core.telegram.org comment="source"
add list=vpn-target address=ip-ranges.amazonaws.com comment="source"
add list=vpn-target address=openai.com comment="source"
add list=vpn-target address=raw.githack.com comment="source"
add list=vpn-target address=raw.githubusercontent.com comment="source"
add list=vpn-target address=www.gstatic.com comment="source"
