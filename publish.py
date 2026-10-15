import hashlib
import html
import json
import uuid
import os
import re
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

FEEDS = {
    'ai': [
        'https://habr.com/ru/rss/hubs/artificial_intelligence/articles/?fl=ru',
        'https://habr.com/ru/rss/hubs/machine_learning/articles/?fl=ru',
        'https://3dnews.ru/news/rss/',
    ],
    'gadgets': ['https://www.ixbt.com/export/news.rss', 'https://3dnews.ru/news/rss/'],
    'it': ['https://habr.com/ru/rss/articles/?fl=ru', 'https://3dnews.ru/news/rss/'],
}

PATTERNS = {
    'ai': [r'\bии\b', r'нейросет', r'искусственн\w* интеллект', r'\bai\b', r'chatgpt', r'\bgpt(?:-\d|\b)', r'gemini', r'claude', r'deepseek', r'машинн\w* обучен', r'генеративн\w* модел'],
    'gadgets': [r'смартфон', r'\biphone\b', r'\bandroid\b', r'планшет', r'ноутбук', r'гаджет', r'наушник', r'\bipad\b', r'\bmacbook\b', r'видеокарт', r'умн\w* час', r'\bplaystation\b', r'\bnintendo\b'],
    'it': [r'кибербезопасност', r'уязвимост', r'\blinux\b', r'\bwindows\b', r'\bgithub\b', r'браузер', r'хакер', r'утечк\w* данн', r'программирован', r'операционн\w* систем', r'\bpython\b', r'\btelegram\b', r'\bинтернет\b'],
}
EMOJI = {'ai': '🤖', 'gadgets': '📱', 'it': '💻'}
LABEL = {'ai': 'Нейросети', 'gadgets': 'Гаджеты', 'it': 'IT и технологии'}


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'TechPulsRSSBot/2.0 (+https://t.me/tech_puls3)'})
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read()


def clean(value):
    value = re.sub(r'<[^>]*>', ' ', value or '')
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


def item_text(item, names):
    for child in item:
        if child.tag.split('}')[-1] in names and child.text:
            return child.text.strip()
    return ''


def image_from_item(item):
    # Prefer explicit RSS media fields, then the first image in the RSS description.
    for child in item.iter():
        tag = child.tag.split('}')[-1].lower()
        url = child.attrib.get('url', '')
        medium = child.attrib.get('medium', '').lower()
        mime = child.attrib.get('type', '').lower()
        if tag in ('thumbnail', 'content') and url and (tag == 'thumbnail' or medium == 'image' or mime.startswith('image/')):
            if url.startswith('https://'):
                return url
        if tag == 'enclosure' and url and mime.startswith('image/') and url.startswith('https://'):
            return url
    for child in item.iter():
        if child.tag.split('}')[-1] in ('description', 'summary', 'encoded', 'content'):
            raw = child.text or ''
            match = re.search(r'<img\b[^>]*\bsrc=["\'](https://[^"\']+)["\']', raw, re.I)
            if match:
                return html.unescape(match.group(1))
    return None


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
        if title and link.startswith(('https://', 'http://')):
            yield {'title': title, 'link': link, 'description': description, 'date': dt, 'image': image_from_item(item)}


def key_for(article):
    parsed = urllib.parse.urlsplit(article['link'])
    normalized = urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def title_key(title):
    normalized = re.sub(r'[^\w]+', ' ', title.casefold()).strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def compact(text, limit=260):
    text = clean(text)
    if len(text) <= limit:
        return text
    shortened = text[:limit + 1]
    sentences = re.findall(r'.+?[.!?](?=\s|$)', shortened)
    if sentences and len(sentences[0]) >= 55:
        return sentences[0].strip()
    return shortened[:limit].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


def telegram_call(method, payload):
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/{method}',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.load(response)
            if not result.get('ok'):
                raise RuntimeError(f'Telegram {method} did not confirm publication')
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('description', 'Unknown error')
        except (ValueError, UnicodeError):
            detail = 'Unknown error'
        raise RuntimeError(f'Telegram {method} HTTP {exc.code}: {detail}') from None


def send_photo_file(image_url, caption):
    # Download on the GitHub runner, then upload bytes to Telegram via multipart/form-data.
    parsed = urllib.parse.urlsplit(image_url)
    if parsed.scheme != 'https':
        raise ValueError('Image URL must use HTTPS')
    request = urllib.request.Request(image_url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; TechPulsRSSBot/3.1)',
        'Referer': f'{parsed.scheme}://{parsed.netloc}/',
        'Accept': 'image/jpeg,image/png,image/webp,image/*;q=0.8',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        mime = response.headers.get_content_type().lower()
        image = response.read(9 * 1024 * 1024 + 1)
    if len(image) > 9 * 1024 * 1024:
        raise ValueError('Image exceeds 9 MB safety limit')
    if image.startswith(b'\xff\xd8\xff'):
        mime, extension = 'image/jpeg', 'jpg'
    elif image.startswith(b'\x89PNG\r\n\x1a\n'):
        mime, extension = 'image/png', 'png'
    else:
        raise ValueError(f'Unsupported image format: {mime}')

    boundary = 'TechPuls' + uuid.uuid4().hex
    fields = {'chat_id': CHANNEL, 'caption': caption, 'parse_mode': 'HTML'}
    body = bytearray()
    for name, value in fields.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8'))
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="news.{extension}"\r\nContent-Type: {mime}\r\n\r\n'.encode('utf-8'))
    body.extend(image)
    body.extend(f'\r\n--{boundary}--\r\n'.encode('utf-8'))
    upload = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/sendPhoto',
        data=bytes(body),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(upload, timeout=40) as response:
            result = json.load(response)
            if not result.get('ok'):
                raise RuntimeError('Telegram did not confirm photo publication')
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('description', 'Unknown error')
        except (ValueError, UnicodeError):
            detail = 'Unknown error'
        raise RuntimeError(f'Telegram sendPhoto HTTP {exc.code}: {detail}') from None


def publish(text, image_url=None):
    # Telegram photo captions are limited to 1024 characters after entity parsing.
    if image_url and len(html.unescape(re.sub(r'<[^>]+>', '', text))) <= 1000:
        try:
            send_photo_file(image_url, text)
            print('Published with uploaded image')
            return
        except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f'Image unavailable; posting text instead: {exc}')
    elif image_url:
        print('Caption too long for photo; posting text instead')
    telegram_call('sendMessage', {
        'chat_id': CHANNEL, 'text': text, 'parse_mode': 'HTML',
        'link_preview_options': {'is_disabled': True},
    })
    print('Published text-only')


def main():
    if CATEGORY not in FEEDS:
        raise ValueError('CATEGORY must be ai, gadgets, or it')
    data = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'posted': []}
    posted = set(data.get('posted', []))
    posted_titles = set(data.get('posted_titles', []))
    now = datetime.now(timezone.utc)
    candidates = []
    seen = set()
    for feed in FEEDS[CATEGORY]:
        try:
            for article in parse_feed(get(feed)):
                if article['date'] and not now - timedelta(days=3) <= article['date'] <= now + timedelta(hours=2):
                    continue
                key = key_for(article)
                tkey = title_key(article['title'])
                if key in posted or tkey in posted_titles or (key, tkey) in seen:
                    continue
                title_matches = sum(bool(re.search(p, article['title'], re.I)) for p in PATTERNS[CATEGORY])
                description_matches = sum(bool(re.search(p, article['description'], re.I)) for p in PATTERNS[CATEGORY])
                if title_matches == 0 and description_matches < 2:
                    continue
                article['score'] = title_matches * 3 + description_matches
                candidates.append(article)
                seen.add((key, tkey))
        except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError) as exc:
            print(f'Feed unavailable: {feed}: {type(exc).__name__}')
    if not candidates:
        print('No suitable new articles. Nothing published.')
        return
    candidates.sort(key=lambda a: (a['score'], a['date'] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    article = candidates[0]
    title = compact(article['title'], 180)
    description = compact(article['description'], 260)
    if description.casefold() == article['title'].casefold() or description.casefold() in article['title'].casefold():
        description = ''
    message = f"{EMOJI[CATEGORY]} <b>{html.escape(title)}</b>\n\n"
    if description:
        message += f"{html.escape(description)}\n\n"
    message += f"🔗 <a href=\"{html.escape(article['link'], quote=True)}\">Читать источник ↗</a>\n\n⚡ @tech_puls3 · {LABEL[CATEGORY]}"
    publish(message, article.get('image'))
    posted.add(key_for(article))
    posted_titles.add(title_key(article['title']))
    data['posted'] = sorted(posted)
    data['posted_titles'] = sorted(posted_titles)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {CATEGORY}: {article["title"]}')


if __name__ == '__main__':
    main()
