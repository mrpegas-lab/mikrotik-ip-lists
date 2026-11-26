# MikroTik address-list: vpn-targets
# Source: apple
# Generated at 2026-11-26 08:25 UTC
#
# This file does NOT remove old entries.
# To clean up: /ip firewall address-list remove [find list=vpn-targets]
#
/ip firewall address-list
add list=vpn-targets address=17.0.0.0/8 comment="apple"
add list=vpn-targets address=57.102.0.0/15 comment="apple"
add list=vpn-targets address=65.199.22.0/23 comment="apple"
add list=vpn-targets address=139.178.128.0/18 comment="apple"
add list=vpn-targets address=144.178.0.0/18 comment="apple"
