"""
sync_index.py — Sync article index from shanethegamer.com post-sitemap.

Fetches all post-sitemap pages, filters for esports-news and video-gaming
articles from August 2025 onwards, and upserts into the article_index table.
"""

import logging
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

WP_API_URL = "https://www.shanethegamer.com/wp-json/wp/v2/posts"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cache-Control": "no-cache"
}

CUTOFF = "2025-08-01T00:00:00"
ALLOWED_CATEGORIES = ("/esports-news/", "/video-gaming/")

def _detect_category(url: str) -> str:
    """Detect article category from URL path."""
    for cat in ALLOWED_CATEGORIES:
        if cat in url:
            return cat.strip("/")
    return ""

def fetch_all_articles() -> list[dict]:
    """Fetch all matching articles from the WordPress REST API."""
    import html
    all_articles = []
    page = 1
    
    while True:
        try:
            params = {
                "per_page": 100,
                "page": page,
                "after": CUTOFF,
                "_fields": "id,link,title,modified"
            }
            resp = requests.get(WP_API_URL, headers=HEADERS, params=params, timeout=30)
            
            if resp.status_code == 400:  # End of pagination usually throws 400 in WP
                break
            resp.raise_for_status()
            
            posts = resp.json()
            if not posts:
                break
                
            count = 0
            for post in posts:
                loc = post.get("link", "")
                
                # Filter by category matching the slug structure
                if not any(cat in loc for cat in ALLOWED_CATEGORIES):
                    continue
                    
                # Try Yoast title first, then native post title
                yoast_title = post.get("yoast_head_json", {}).get("title", "")
                native_title = post.get("title", {}).get("rendered", "")
                
                title_raw = yoast_title if yoast_title else native_title
                title = html.unescape(title_raw).strip()
                
                # Remove typical " - Shane The Gamer" suffix from Yoast titles
                if " - Shane" in title:
                    title = title.split(" - Shane")[0].strip()
                    
                lastmod = post.get("modified", "")
                category = _detect_category(loc)
                
                all_articles.append({
                    "url": loc,
                    "title": title,
                    "category": category,
                    "lastmod": lastmod or None,
                })
                count += 1
                
            logger.info(f"WP Page {page}: {count} matching articles (total: {len(posts)} posts)")
            page += 1
            
        except requests.HTTPError as e:
            if e.response and e.response.status_code in (400, 404):
                break
            logger.error(f"WP API HTTP error on page {page}: {e}")
            break
        except Exception as e:
            logger.error(f"WP API error on page {page}: {e}")
            break

    logger.info(f"Total matching articles from WP API: {len(all_articles)}")
    return all_articles

def sync_to_db(database_url: str) -> int:
    """Fetch articles from WordPress API and upsert into article_index table."""
    import psycopg2
    
    articles = fetch_all_articles()
    if not articles:
        logger.warning("No articles fetched from WP API.")
        return 0

    conn = psycopg2.connect(database_url)
    inserted = 0
    try:
        with conn.cursor() as cur:
            for a in articles:
                cur.execute(
                    """INSERT INTO article_index (url, title, category, lastmod)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (url) DO UPDATE
                       SET title = EXCLUDED.title,
                           category = EXCLUDED.category,
                           lastmod = EXCLUDED.lastmod""",
                    (a["url"], a["title"], a["category"], a["lastmod"]),
                )
                inserted += 1
        conn.commit()
        logger.info(f"Synced {inserted} articles to article_index")
    finally:
        conn.close()

    return inserted
