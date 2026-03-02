#!/usr/bin/env python3
"""
WordPress REST API 投稿モジュール

scrape_kirishima.py から呼び出されて使用します。
WordPress Application Password で認証し、
取得した記事を WP に投稿します。
"""

import logging
import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)

# カテゴリ名 → ID のキャッシュ
_category_cache: dict[str, int] = {}


def _get_category_id(wp_url: str, auth: HTTPBasicAuth, slug: str) -> int | None:
    """カテゴリのスラッグから ID を取得（キャッシュ付き）"""
    if slug in _category_cache:
        return _category_cache[slug]

    try:
        resp = requests.get(
            f"{wp_url}/wp-json/wp/v2/categories",
            params={"slug": slug, "per_page": 1},
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            cat_id = data[0]["id"]
            _category_cache[slug] = cat_id
            return cat_id
    except Exception as e:
        log.warning(f"カテゴリ ID 取得失敗 ({slug}): {e}")

    return None


def _exists_by_slug(wp_url: str, auth: HTTPBasicAuth, slug: str) -> bool:
    """スラッグで既存投稿をチェック（重複防止の二重チェック）"""
    try:
        resp = requests.get(
            f"{wp_url}/wp-json/wp/v2/posts",
            params={"slug": slug, "per_page": 1, "_fields": "id"},
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        return len(resp.json()) > 0
    except Exception:
        return False


def build_post_content(item: dict) -> str:
    """投稿本文を HTML で構築"""
    source_name = item.get("source_name", "")
    source_url = item.get("url", "")
    excerpt = item.get("excerpt", "")
    date_str = item.get("date", "")

    content = ""

    if excerpt:
        content += f'<p>{excerpt}</p>\n\n'

    content += '<div class="kirishima-info-source" style="'
    content += 'margin-top:24px;padding:16px 20px;'
    content += 'background:#EAF4EE;border-left:4px solid #1E5C32;'
    content += 'border-radius:0 8px 8px 0;">\n'

    if date_str:
        content += f'<p style="margin:0 0 8px;font-size:13px;color:#6B7564;">'
        content += f'📅 掲載日：{date_str[:10]}</p>\n'

    content += f'<p style="margin:0 0 8px;font-size:13px;color:#6B7564;">'
    content += f'📰 出典：{source_name}</p>\n'

    if source_url:
        content += f'<p style="margin:0;"><a href="{source_url}" '
        content += f'target="_blank" rel="noopener noreferrer" '
        content += f'style="color:#1E5C32;font-weight:700;">'
        content += f'元記事を読む →</a></p>\n'

    content += '</div>\n'

    return content


def build_slug(item: dict) -> str:
    """URL の MD5 ハッシュからスラッグを生成"""
    import hashlib
    url = item.get("url", "")
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    source = item.get("source_site", "news")
    return f"kirishima-{source}-{h}"


def post_item(wp_url: str, wp_user: str, wp_app_pass: str, item: dict) -> bool:
    """
    1 件の記事を WordPress に投稿する。

    Returns:
        True  — 新規投稿成功
        False — スキップまたは失敗
    """
    wp_url = wp_url.rstrip("/")
    auth = HTTPBasicAuth(wp_user, wp_app_pass)

    title = item.get("title", "").strip()
    if not title:
        log.warning("タイトルが空のため投稿をスキップ")
        return False

    # カテゴリ ID を解決
    cat_slug = item.get("category", "kirishima-news")
    cat_id = _get_category_id(wp_url, auth, cat_slug)
    categories = [cat_id] if cat_id else []

    # スラッグ生成（重複投稿の二重チェック用）
    slug = build_slug(item)
    if _exists_by_slug(wp_url, auth, slug):
        log.debug(f"スラッグ重複のためスキップ: {slug}")
        return False

    # 投稿データ
    payload = {
        "title": title,
        "content": build_post_content(item),
        "status": "publish",
        "slug": slug,
        "date": item.get("date", ""),
        "categories": categories,
        "meta": {
            "source_url": item.get("url", ""),
            "source_site": item.get("source_site", ""),
            "source_name": item.get("source_name", ""),
        },
    }

    # date が空の場合は削除（WP がデフォルト日時を使用）
    if not payload["date"]:
        del payload["date"]

    # categories が空の場合は削除
    if not payload["categories"]:
        del payload["categories"]

    try:
        resp = requests.post(
            f"{wp_url}/wp-json/wp/v2/posts",
            json=payload,
            auth=auth,
            timeout=30,
        )

        if resp.status_code == 201:
            post_id = resp.json().get("id")
            log.info(f"投稿成功 (ID:{post_id}): {title[:50]}")
            return True

        elif resp.status_code == 422:
            # スラッグ重複などバリデーションエラー
            error = resp.json().get("message", "")
            if "slug" in error.lower() or "duplicate" in error.lower():
                log.debug(f"既存投稿のためスキップ: {title[:50]}")
            else:
                log.warning(f"バリデーションエラー: {error} | {title[:50]}")
            return False

        else:
            log.error(
                f"投稿失敗 HTTP {resp.status_code}: "
                f"{resp.text[:200]} | {title[:50]}"
            )
            return False

    except requests.exceptions.ConnectionError:
        log.error(f"WordPress への接続失敗: {wp_url}")
        return False
    except requests.exceptions.Timeout:
        log.error(f"タイムアウト: {title[:50]}")
        return False
    except Exception as e:
        log.error(f"予期しないエラー: {e} | {title[:50]}")
        return False
