
import os
import json
import urllib.request
import urllib.error

token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
channel = os.environ["TELEGRAM_CHANNEL_ID"].strip()

message = "🚀 Tech Puls: тестовая публикация!"

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = json.dumps({
    "chat_id": channel,
    "text": message
}).encode("utf-8")

request = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
        print("SUCCESS: Message sent to Telegram")
except urllib.error.HTTPError as error:
    body = error.read().decode("utf-8", errors="replace")
    try:
        details = json.loads(body)
        description = details.get("description", "Unknown error")
    except json.JSONDecodeError:
        description = "Could not read Telegram error"

    print(f"Telegram HTTP error: {error.code}")
    print(f"Telegram says: {description}")
    raise SystemExit(1)

