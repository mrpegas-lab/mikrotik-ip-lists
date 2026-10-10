# MikroTik address-list: vpn-targets
# Domains only
# Generated at 2026-10-10 15:48 UTC
#
# This file does NOT remove old entries.
# To clean up: /ip firewall address-list remove [find list=vpn-targets]
#
/ip firewall address-list
# --- Telegram_Domains ---
add list=vpn-targets address=api.telegram.org comment="Telegram_Domains"
add list=vpn-targets address=cdn-telegram.org comment="Telegram_Domains"
add list=vpn-targets address=core.telegram.org comment="Telegram_Domains"
add list=vpn-targets address=desktop.telegram.org comment="Telegram_Domains"
add list=vpn-targets address=graph.org comment="Telegram_Domains"
add list=vpn-targets address=t.me comment="Telegram_Domains"
add list=vpn-targets address=telegra.ph comment="Telegram_Domains"
add list=vpn-targets address=telegram-cdn.org comment="Telegram_Domains"
add list=vpn-targets address=telegram.org comment="Telegram_Domains"
add list=vpn-targets address=telesco.pe comment="Telegram_Domains"
add list=vpn-targets address=web.telegram.org comment="Telegram_Domains"

# --- google ---
add list=vpn-targets address=accounts.youtube.com comment="google"
add list=vpn-targets address=android.googleapis.com comment="google"
add list=vpn-targets address=android.l.google.com comment="google"
add list=vpn-targets address=clients.l.google.com comment="google"
add list=vpn-targets address=firebaseinstallations.googleapis.com comment="google"
add list=vpn-targets address=i.ytimg.com comment="google"
add list=vpn-targets address=jnn-pa.googleapis.com comment="google"
add list=vpn-targets address=s.youtube.com comment="google"
add list=vpn-targets address=wide-youtube.l.google.com comment="google"
add list=vpn-targets address=youtube.googleapis.com comment="google"
add list=vpn-targets address=youtubei.googleapis.com comment="google"
add list=vpn-targets address=yt3.ggpht.com comment="google"
add list=vpn-targets address=ytimg.com comment="google"

