# MikroTik IP Lists

Автоматически обновляемый набор `address-list` для MikroTik RouterOS 7+.
Источники: Google, Google Cloud, Telegram, AWS, OpenAI (GPTBot, ChatGPT).
Плюс опциональный файл для Google DNS over HTTPS (DoH).

## Что внутри

**Общий файл (всё сразу):**
- `output_rsc/vpn-targets.rsc` — домены + все IP-источники, с автоочисткой списка.

**Раздельные файлы (гибко, без автоочистки):**
- `output_rsc/google.rsc`
- `output_rsc/telegram.rsc`
- `output_rsc/amazon.rsc`
- `output_rsc/gptbot.rsc`
- `output_rsc/chatgpt.rsc`
- `output_rsc/domains.rsc`

**Дополнительно:**
- `extras/doh-google.rsc` — опционально: включает Google DoH (RouterOS 7.19+).
- `parser.py` — генератор (запускается на GitHub Actions раз в сутки).
- `domains.txt` — домены, которые MikroTik резолвит сам при импорте.

## Какой файл выбрать

- **Хочешь всё сразу** → `vpn-targets.rsc`. Он сам очистит старый список и зальёт новый.
- **Хочешь гибко** → бери раздельные файлы. Они **не удаляют** старые записи.
  Перед импортом при необходимости очисти вручную: