"""各サイトのRSSを取得して news.json に保存する（GitHub Actions から定期実行）"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = [
    ('dcwatch', 'https://dc.watch.impress.co.jp/data/rss/1.0/dcw/feed.rdf'),
    ('digicame', 'https://digicame-info.com/rss.xml'),
    ('capa', 'https://getnavi.jp/capa/feed/'),
    ('shasha', 'https://www.kitamura.jp/shasha/feed/'),
    ('petapixel', 'https://petapixel.com/feed/'),
]
PER_FEED = 8
OUT = Path(__file__).resolve().parent.parent / 'news.json'
UA = 'Mozilla/5.0 (compatible; camera-news/1.0; +https://kotoru66.github.io/camera-news/)'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names and (c.text or '').strip():
            return c.text.strip()
        if local(c.tag) == 'link' and 'link' in names and c.get('href'):
            return c.get('href')
    return ''


def to_iso(s):
    if not s:
        return ''
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            return ''
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def clean(s):
    s = re.sub(r'<[^>]+>', '', html.unescape(s or ''))
    return re.sub(r'\s+', ' ', s).strip()[:130]


def fetch(key, url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        root = ET.fromstring(res.read())
    entries = [e for e in root.iter() if local(e.tag) in ('item', 'entry')]
    items = []
    for e in entries[:PER_FEED]:
        title = clean(child_text(e, 'title'))
        if not title:
            continue
        items.append({
            'key': key,
            'title': title,
            'link': child_text(e, 'link') or '#',
            'desc': clean(child_text(e, 'description', 'summary', 'encoded', 'content')),
            'date': to_iso(child_text(e, 'pubDate', 'date', 'published', 'updated')),
        })
    return items


def main():
    items, failed = [], []
    for key, url in FEEDS:
        try:
            got = fetch(key, url)
            print(f'{key}: {len(got)}件')
            items += got
        except Exception as e:
            print(f'{key}: 取得失敗 {e}', file=sys.stderr)
            failed.append(key)
    if not items:
        sys.exit('すべてのフィードの取得に失敗したため、news.json は更新しません')
    items.sort(key=lambda i: i['date'], reverse=True)
    data = {
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'failed': failed,
        'items': items,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
