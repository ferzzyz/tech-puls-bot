import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

TOKEN = os.environ['TELEGRAM_BOT_TOKEN'].strip()
CHANNEL = os.environ['TELEGRAM_CHANNEL_ID'].strip()
CATEGORY = os.environ.get('CATEGORY', 'ai').strip()
STATE = Path('posted.json')

# RSS feeds from Russian-language technology publications. If a feed is unavailable,
# the script tries the next one and exits without posting rather than inventing news.
FEEDS = {
    'ai': [
        'https://habr.com/ru/rss/hubs/artificial_intelligence/articles/?fl=ru',
        'https://habr.com/ru/rss/hubs/machine_learning/articles/?fl=ru',
        'https://3dnews.ru/news/rss/',
    ],
    'gadgets': [
        'https://www.ixbt.com/export/news.rss',
        'https://3dnews.ru/news/rss/',
    ],
    'it': [
        'https://habr.com/ru/rss/articles/?fl=ru',
        'https://3dnews.ru/news/rss/',
    ],
}
KEYWORDS = {
    'ai': ('ии', 'нейросет', 'искусственн', 'ai', 'chatgpt', 'gpt', 'модел', 'нейрон', 'машинн', 'генератив'),
    'gadgets': ('смартфон', 'телефон', 'iphone', 'android', 'планшет', 'ноутбук', 'гаджет', 'наушник', 'apple', 'samsung', 'процессор', 'видеокарт'),
    'it': ('разработ', 'программ', 'кибер', 'безопасност', 'linux', 'windows', 'интернет', 'сервер', 'github', 'браузер', 'it', 'технолог'),
}
EMOJI = {'ai': '🤖', 'gadgets': '📱', 'it': '💻'}
LABEL = {'ai': 'ИИ и нейросети', 'gadgets': 'Гаджеты и технологии', 'it': 'IT и цифровой мир'}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'TechPulsRSSBot/1.0 (+https://t.me/tech_puls3)'})
    with urllib.request.urlopen(req, timeout=18) as response:
        return response.read()


def clean(text):
    text = re.sub(r'<[^>]*>', ' ', text or '')
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def item_text(item, names):
    for child in item:
        if child.tag.split('}')[-1] in names and child.text:
            return child.text.strip()
    return ''


def parse_feed(xml_data):
    root = ET.fromstring(xml_data)
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        title = clean(item_text(item, ('title',)))
        link = item_text(item, ('link',))
        if not link:
            for child in item:
                if child.tag.split('}')[-1] == 'link' and child.attrib.get('href'):
                    link = child.attrib['href']
                    break
        description = clean(item_text(item, ('description', 'summary', 'content')))
        date_text = item_text(item, ('pubDate', 'published', 'updated'))
        try:
            dt = parsedate_to_datetime(date_text) if date_text else None
            if dt is None and date_text:
                dt = datetime.fromisoformat(date_text.replace('Z', '+00:00'))
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, IndexError):
            dt = None
        if title and link.startswith(('http://', 'https://')):
            yield {'title': title, 'link': link, 'description': description, 'date': dt}


def key_for(article):
    parsed = urllib.parse.urlsplit(article['link'])
    normalized = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def send_message(text):
    payload = json.dumps({'chat_id': CHANNEL, 'text': text, 'disable_web_page_preview': False}).encode('utf-8')
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/sendMessage',
        data=payload, headers={'Content-Type': 'application/json'}, method='POST'
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
            if not result.get('ok'):
                raise RuntimeError('Telegram did not confirm publication')
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('description', 'Unknown error')
        except (ValueError, UnicodeError):
            detail = 'Unknown error'
        raise RuntimeError(f'Telegram HTTP {exc.code}: {detail}') from None


def main():
    if CATEGORY not in FEEDS:
        raise ValueError('CATEGORY must be ai, gadgets, or it')
    if STATE.exists():
        data = json.loads(STATE.read_text(encoding='utf-8'))
    else:
        data = {'posted': []}
    posted = set(data.get('posted', []))
    candidates = []
    now = datetime.now(timezone.utc)
    for feed in FEEDS[CATEGORY]:
        try:
            for article in parse_feed(get(feed)):
                if article['date'] and (article['date'] < now - timedelta(days=3) or article['date'] > now + timedelta(hours=2)):
                    continue
                if key_for(article) in posted:
                    continue
                text = (article['title'] + ' ' + article['description']).lower()
                if not any(word in text for word in KEYWORDS[CATEGORY]):
                    continue
                candidates.append(article)
        except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError) as exc:
            print(f'Feed unavailable: {feed}: {type(exc).__name__}')
    if not candidates:
        print('No suitable new articles. Nothing published.')
        return
    candidates.sort(key=lambda x: x['date'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    article = candidates[0]
    title = article['title'][:220]
    description = article['description'][:300].rstrip()
    message = f"{EMOJI[CATEGORY]} {LABEL[CATEGORY]} | Tech Puls\n\n{title}\n"
    if description and description.lower() != title.lower():
        message += f'\n{description}\n'
    message += f"\n🔗 Источник: {article['link']}\n\n⚡ @tech_puls3"
    send_message(message)
    posted.add(key_for(article))
    data['posted'] = sorted(posted)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {CATEGORY}: {title}')


if __name__ == '__main__':
    main()

