"""
sync_index.py — Sync article index from shanethegamer.com post-sitemap.

Fetches all post-sitemap pages, filters for esports-news and video-gaming
articles from August 2025 onwards, and upserts into the article_index table.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

import psycopg2
import requests

logger = logging.getLogger(__name__)

SITEMAP_PAGES = [
    "https://www.shanethegamer.com/post-sitemap.xml",
    "https://www.shanethegamer.com/post-sitemap2.xml",
    "https://www.shanethegamer.com/post-sitemap3.xml",
    "https://www.shanethegamer.com/post-sitemap4.xml",
    "https://www.shanethegamer.com/post-sitemap5.xml",
    "https://www.shanethegamer.com/post-sitemap6.xml",
    "https://www.shanethegamer.com/post-sitemap7.xml",
    "https://www.shanethegamer.com/post-sitemap8.xml",
    "https://www.shanethegamer.com/post-sitemap9.xml",
    "https://www.shanethegamer.com/post-sitemap10.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache",
}

CUTOFF = datetime(2025, 8, 1)
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ALLOWED_CATEGORIES = ("/esports-news/", "/video-gaming/")


def _title_from_slug(url: str) -> str:
    """Extract a human-readable title from a URL slug."""
    slug = url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()


def _detect_category(url: str) -> str:
    """Detect article category from URL path."""
    for cat in ALLOWED_CATEGORIES:
        if cat in url:
            return cat.strip("/")
    return ""


def fetch_all_articles() -> list[dict]:
    """Fetch all matching articles from all sitemap pages."""
    all_articles = []

    for sitemap_url in SITEMAP_PAGES:
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                logger.debug(f"{sitemap_url}: 404, stopping")
                break
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            urls = root.findall(f"{NS}url")

            count = 0
            for u in urls:
                loc_el = u.find(f"{NS}loc")
                lastmod_el = u.find(f"{NS}lastmod")
                if loc_el is None:
                    continue

                loc = loc_el.text.strip()

                # Filter by category
                if not any(cat in loc for cat in ALLOWED_CATEGORIES):
                    continue

                # Filter by date
                lastmod_str = ""
                if lastmod_el is not None and lastmod_el.text:
                    lastmod_str = lastmod_el.text.strip()
                    try:
                        dt_str = lastmod_str.split("T")[0]
                        dt = datetime.strptime(dt_str, "%Y-%m-%d")
                        if dt < CUTOFF:
                            continue
                    except (ValueError, IndexError):
                        pass

                title = _title_from_slug(loc)
                category = _detect_category(loc)

                all_articles.append({
                    "url": loc,
                    "title": title,
                    "category": category,
                    "lastmod": lastmod_str or None,
                })
                count += 1

            logger.info(f"{sitemap_url}: {count} matching articles (total: {len(urls)} URLs)")

        except requests.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.debug(f"{sitemap_url}: 404, stopping")
                break
            logger.error(f"{sitemap_url}: HTTP error {e}")
            break
        except Exception as e:
            logger.error(f"{sitemap_url}: error {e}")
            break

    logger.info(f"Total matching articles from sitemap: {len(all_articles)}")
    return all_articles


def sync_to_db(database_url: str) -> int:
    """Fetch articles from sitemap and upsert into article_index table."""
    articles = fetch_all_articles()
    if not articles:
        logger.warning("No articles fetched from sitemap.")
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
