
import os
import json
import urllib.request
import urllib.error

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]

message = (
    "🚀 Tech Puls — тестовая публикация!\n\n"
    "🤖 Автоматическая система публикаций подключена.\n\n"
    "Скоро здесь будут появляться свежие новости "
    "об искусственном интеллекте и технологиях.\n\n"
    "⚡ Tech Puls | Технологии будущего"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

payload = json.dumps({
    "chat_id": CHANNEL,
    "text": message,
    "disable_web_page_preview": True
}).encode("utf-8")

request = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
        if not result.get("ok"):
            raise RuntimeError("Telegram rejected the message")
        print("SUCCESS: Message published in Tech Puls")
except urllib.error.HTTPError as error:
    print(f"Telegram API error: HTTP {error.code}")
    raise
