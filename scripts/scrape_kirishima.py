#!/usr/bin/env python3
"""
Kirishima News Scraper
霧島市役所・きりなび・まいぷれ から情報を収集して data/news.json に保存する。
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(REPO_ROOT, 'data', 'news.json')

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

def make_session():
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.9'})
    return s


# ─── 霧島市役所 ──────────────────────────────────────────────
def scrape_city():
    """RSS フィードから最新情報を取得する"""
    items = []
    session = make_session()
    rss_url = 'https://www.city.kirishima.lg.jp/index.xml'
    try:
        resp = session.get(rss_url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:10]:
            title = entry.get('title', '').strip()
            link  = entry.get('link', '').strip()
            pub   = entry.get('published', '')
            desc  = BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text()[:200]
            if not (title and link):
                continue
            items.append({
                'title':       title,
                'url':         link,
                'source':      'kirishima_city',
                'source_name': '霧島市役所',
                'date':        _parse_date(pub),
                'description': desc,
                'category':    'kirishima-news',
            })
        logger.info(f'霧島市役所: {len(items)} 件')
    except Exception as e:
        logger.warning(f'霧島市役所 取得失敗: {e}')
    return items


# ─── きりなび ────────────────────────────────────────────────
def scrape_kirinavi():
    """きりなびのトップページからニュースを取得する"""
    items = []
    session = make_session()
    # イベント一覧ページを試す
    urls = [
        'https://kirinavi.com/event/',
        'https://kirinavi.com/news/',
        'https://kirinavi.com/',
    ]
    for url in urls:
        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f'きりなび {url} → {resp.status_code}')
                continue
            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.content, 'html.parser')

            # リンクを持つ見出し要素を広く取得
            for tag in soup.find_all(['h2', 'h3', 'h4'], limit=30):
                a = tag.find('a', href=True)
                if not a:
                    continue
                title = a.get_text(strip=True)
                href  = urljoin(url, a['href'])
                if not title or len(title) < 5:
                    continue
                items.append({
                    'title':       title,
                    'url':         href,
                    'source':      'kirinavi',
                    'source_name': 'きりなび',
                    'date':        datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    'description': '',
                    'category':    'events',
                })
            if items:
                logger.info(f'きりなび: {len(items)} 件 ({url})')
                return items[:10]
        except Exception as e:
            logger.warning(f'きりなび {url} 失敗: {e}')
    logger.warning('きりなび: 0 件取得')
    return items


# ─── まいぷれ霧島 ────────────────────────────────────────────
def scrape_myplace():
    """まいぷれ霧島のニュースを取得する"""
    items = []
    session = make_session()
    urls = [
        'https://kirishima.mypl.net/article/',
        'https://kirishima.mypl.net/shop/',
        'https://kirishima.mypl.net/',
    ]
    for url in urls:
        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f'まいぷれ {url} → {resp.status_code}')
                continue
            resp.encoding = resp.apparent_encoding or 'utf-8'
            soup = BeautifulSoup(resp.content, 'html.parser')

            for tag in soup.find_all(['h2', 'h3', 'h4'], limit=30):
                a = tag.find('a', href=True)
                if not a:
                    continue
                title = a.get_text(strip=True)
                href  = urljoin(url, a['href'])
                if not title or len(title) < 5:
                    continue
                items.append({
                    'title':       title,
                    'url':         href,
                    'source':      'myplace',
                    'source_name': 'まいぷれ霧島',
                    'date':        datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    'description': '',
                    'category':    'kirishima-news',
                })
            if items:
                logger.info(f'まいぷれ霧島: {len(items)} 件 ({url})')
                return items[:10]
        except Exception as e:
            logger.warning(f'まいぷれ {url} 失敗: {e}')
    logger.warning('まいぷれ霧島: 0 件取得')
    return items


def _parse_date(date_str):
    if not date_str:
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    try:
        return dateutil_parser.parse(date_str).strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def deduplicate(items):
    seen, result = set(), []
    for item in items:
        if item['url'] not in seen:
            seen.add(item['url'])
            result.append(item)
    return result


def main():
    logger.info('=== 霧島市情報収集 開始 ===')
    all_items = []

    for fn in [scrape_city, scrape_kirinavi, scrape_myplace]:
        try:
            all_items.extend(fn())
        except Exception as e:
            logger.error(f'{fn.__name__} 失敗: {e}')
        time.sleep(1)

    all_items = deduplicate(all_items)
    logger.info(f'合計収集件数: {len(all_items)} 件')

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    output = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'items':   all_items,
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f'保存完了 → {OUTPUT_FILE}')
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except Exception as e:
        logger.error(f'Fatal: {e}', exc_info=True)
        sys.exit(1)
