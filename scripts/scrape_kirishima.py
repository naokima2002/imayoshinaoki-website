#!/usr/bin/env python3
"""
霧島市情報スクレイパー
収集元: 霧島市役所 / きりなび / まいぷれ霧島

使い方:
  python scrape_kirishima.py             # 実行して WordPress に投稿
  python scrape_kirishima.py --dry-run   # 収集のみ（WordPress 投稿なし）

環境変数 (GitHub Secrets に設定):
  WP_URL       WordPress サイトの URL (例: https://your-wp-site.com)
  WP_USER      WordPress ユーザー名
  WP_APP_PASS  WordPress Application Password
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# ── ロギング設定 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ── 設定 ──
DRY_RUN = "--dry-run" in sys.argv
STATE_FILE = Path(__file__).parent / "state.json"

# WordPress API（環境変数から取得）
WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASS = os.getenv("WP_APP_PASS", "")

# WordPress カテゴリ スラッグ
CAT_NEWS = "kirishima-news"
CAT_EVENTS = "events"

# 最大取得件数
MAX_ITEMS_PER_SOURCE = 10

# ── 状態管理（重複投稿防止） ──
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posted_urls": [], "last_run": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def already_posted(state, url: str) -> bool:
    return url_hash(url) in state["posted_urls"]

def mark_posted(state, url: str):
    h = url_hash(url)
    if h not in state["posted_urls"]:
        state["posted_urls"].append(h)
    # 最大 1000 件保持
    if len(state["posted_urls"]) > 1000:
        state["posted_urls"] = state["posted_urls"][-1000:]

# ── HTTP ヘルパー ──
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KirishimaInfoBot/1.0; +https://imayoshinaoki.fun)",
    "Accept-Language": "ja,en;q=0.8",
}

def get_page(url: str, timeout: int = 15) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.warning(f"ページ取得失敗: {url} — {e}")
        return None

def get_rss(url: str) -> list:
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        log.warning(f"RSS 取得失敗: {url} — {e}")
        return []

# ── 霧島市役所スクレイパー ──
def scrape_city_hall() -> list:
    """
    霧島市役所の新着情報を取得
    URL: https://www.city.kirishima.lg.jp/
    RSS: https://www.city.kirishima.lg.jp/rss.xml (存在する場合)
    """
    items = []

    # RSS を試みる
    rss_url = "https://www.city.kirishima.lg.jp/feed/"
    entries = get_rss(rss_url)

    if entries:
        for entry in entries[:MAX_ITEMS_PER_SOURCE]:
            pub = entry.get("published", "") or entry.get("updated", "")
            try:
                dt = dateparser.parse(pub) if pub else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)

            items.append({
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", ""),
                "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "excerpt": BeautifulSoup(entry.get("summary", ""), "lxml").get_text()[:200],
                "source_site": "city",
                "source_name": "霧島市役所",
                "category": CAT_NEWS,
            })
        log.info(f"霧島市役所 RSS: {len(items)} 件取得")
        return items

    # RSS が取得できない場合は HTML スクレイピング
    base_url = "https://www.city.kirishima.lg.jp"
    soup = get_page(base_url)
    if not soup:
        return items

    # 新着情報リストを探す（サイト構造に合わせて調整が必要）
    # 一般的なパターンで探索
    news_selectors = [
        "ul.list-news li",
        ".new-info li",
        ".topics li",
        ".info-list li",
        "article",
    ]

    found = []
    for selector in news_selectors:
        found = soup.select(selector)
        if found:
            break

    for item in found[:MAX_ITEMS_PER_SOURCE]:
        a_tag = item.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")
        if not href.startswith("http"):
            href = base_url + href

        if not title or not href:
            continue

        # 日付を探す
        date_text = ""
        for cls in ["date", "day", "time", "pub-date"]:
            date_el = item.find(class_=cls) or item.find(cls)
            if date_el:
                date_text = date_el.get_text(strip=True)
                break

        try:
            dt = dateparser.parse(date_text) if date_text else datetime.now(timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)

        items.append({
            "title": title,
            "url": href,
            "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "excerpt": title,
            "source_site": "city",
            "source_name": "霧島市役所",
            "category": CAT_NEWS,
        })

    log.info(f"霧島市役所 HTML: {len(items)} 件取得")
    return items


# ── きりなびスクレイパー ──
def scrape_kirinavi() -> list:
    """
    きりなびのイベント・スポット情報を取得
    URL: https://kirinavi.com/
    """
    items = []
    base_url = "https://kirinavi.com"

    # イベントページを試みる
    event_pages = [
        f"{base_url}/event/",
        f"{base_url}/events/",
        f"{base_url}/",
    ]

    for page_url in event_pages:
        soup = get_page(page_url)
        if not soup:
            continue

        # イベントリストを探す
        selectors = [
            ".event-list article",
            ".event-item",
            ".post-list article",
            "article.post",
            ".entry",
        ]

        found = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                break

        if not found:
            # 汎用的な記事リスト
            found = soup.find_all("article")[:MAX_ITEMS_PER_SOURCE]

        for item in found[:MAX_ITEMS_PER_SOURCE]:
            a_tag = item.find("a")
            if not a_tag:
                continue

            title_el = item.find(["h2", "h3", "h4"]) or a_tag
            title = title_el.get_text(strip=True)
            href = a_tag.get("href", "")
            if not href.startswith("http"):
                href = base_url + href

            if not title or not href:
                continue

            # 日付
            date_el = item.find("time") or item.find(class_="date")
            date_str = ""
            if date_el:
                date_str = date_el.get("datetime", "") or date_el.get_text(strip=True)

            try:
                dt = dateparser.parse(date_str) if date_str else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)

            # カテゴリ判定（タイトルや内容からイベントか判断）
            cat = CAT_EVENTS if any(k in title for k in ["イベント", "祭", "まつり", "フェス", "ライブ", "展覧会", "コンサート"]) else CAT_NEWS

            items.append({
                "title": title,
                "url": href,
                "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "excerpt": item.get_text(strip=True)[:200],
                "source_site": "kirinavi",
                "source_name": "きりなび",
                "category": cat,
            })

        if items:
            break

    log.info(f"きりなび: {len(items)} 件取得")
    return items[:MAX_ITEMS_PER_SOURCE]


# ── まいぷれスクレイパー ──
def scrape_mypl() -> list:
    """
    まいぷれ霧島の地域ニュース・イベント情報を取得
    URL: https://kirishima.mypl.net/
    """
    items = []
    base_url = "https://kirishima.mypl.net"

    # まいぷれのニュースページ
    pages = [
        f"{base_url}/news/",
        f"{base_url}/event/",
        f"{base_url}/article/",
        f"{base_url}/",
    ]

    for page_url in pages:
        soup = get_page(page_url)
        if not soup:
            continue

        selectors = [
            ".news-list li",
            ".article-list li",
            ".event-list li",
            ".list-item",
            "article",
        ]

        found = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                break

        for item in found[:MAX_ITEMS_PER_SOURCE]:
            a_tag = item.find("a")
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True) or (item.find(["h2","h3","h4"]) or a_tag).get_text(strip=True)
            href = a_tag.get("href", "")
            if not href.startswith("http"):
                href = base_url.rstrip("/") + "/" + href.lstrip("/")

            if not title or not href:
                continue

            date_el = item.find("time") or item.find(class_=["date", "day"])
            date_str = ""
            if date_el:
                date_str = date_el.get("datetime", "") or date_el.get_text(strip=True)

            try:
                dt = dateparser.parse(date_str) if date_str else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)

            cat = CAT_EVENTS if "event" in page_url else CAT_NEWS

            items.append({
                "title": title,
                "url": href,
                "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "excerpt": item.get_text(strip=True)[:200],
                "source_site": "mypl",
                "source_name": "まいぷれ霧島",
                "category": cat,
            })

        if items:
            break

    log.info(f"まいぷれ霧島: {len(items)} 件取得")
    return items[:MAX_ITEMS_PER_SOURCE]


# ── WordPress 投稿 ──
def post_to_wordpress(items: list, state: dict) -> int:
    """WordPress REST API に記事を投稿する"""
    if not WP_URL or not WP_USER or not WP_APP_PASS:
        log.error("WordPress 認証情報が設定されていません（WP_URL / WP_USER / WP_APP_PASS）")
        return 0

    from post_to_wordpress import post_item
    posted = 0

    for item in items:
        if already_posted(state, item["url"]):
            log.debug(f"スキップ（既投稿）: {item['title'][:50]}")
            continue

        if DRY_RUN:
            log.info(f"[DRY-RUN] 投稿予定: [{item['source_name']}] {item['title'][:60]}")
            mark_posted(state, item["url"])
            posted += 1
            continue

        try:
            result = post_item(WP_URL, WP_USER, WP_APP_PASS, item)
            if result:
                mark_posted(state, item["url"])
                posted += 1
                log.info(f"投稿完了: [{item['source_name']}] {item['title'][:60]}")
        except Exception as e:
            log.error(f"投稿失敗: {item['title'][:50]} — {e}")

    return posted


# ── メイン ──
def main():
    log.info(f"=== 霧島市情報収集 開始 {'[DRY-RUN]' if DRY_RUN else ''} ===")

    state = load_state()
    state["last_run"] = datetime.now(timezone.utc).isoformat()

    # 各サイトからスクレイピング
    all_items = []

    log.info("--- 霧島市役所 ---")
    all_items.extend(scrape_city_hall())

    log.info("--- きりなび ---")
    all_items.extend(scrape_kirinavi())

    log.info("--- まいぷれ霧島 ---")
    all_items.extend(scrape_mypl())

    log.info(f"合計収集件数: {len(all_items)} 件")

    # WordPress に投稿
    if all_items:
        posted = post_to_wordpress(all_items, state)
        log.info(f"WordPress 投稿件数: {posted} 件")

    save_state(state)
    log.info("=== 完了 ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
