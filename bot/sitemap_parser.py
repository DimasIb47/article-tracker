"""
sitemap_parser.py — Parse Yoast News Sitemap XML.

Fetches the news-sitemap.xml and extracts article URLs, titles, and dates.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from lxml import etree

logger = logging.getLogger(__name__)

NAMESPACES = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
}

REQUEST_TIMEOUT = 30


@dataclass
class Article:
    url: str
    title: str
    publication_date: str = ""
    keywords: List[str] = field(default_factory=list)


def fetch_sitemap(sitemap_url: str) -> Optional[bytes]:
    # Add timestamp to bust CDN cache (WordPress W3 Total Cache caches for 24h)
    cache_buster = f"{'&' if '?' in sitemap_url else '?'}_cb={int(time.time())}"
    url = sitemap_url + cache_buster
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        logger.debug(f"Sitemap fetched: {len(response.content)} bytes")
        return response.content
    except requests.RequestException as e:
        logger.error(f"Failed to fetch sitemap: {e}")
        return None


def parse_sitemap(xml_content: bytes) -> List[Article]:
    articles = []
    try:
        root = etree.fromstring(xml_content)
    except etree.XMLSyntaxError as e:
        logger.error(f"Failed to parse sitemap XML: {e}")
        return articles

    url_elements = root.findall("sm:url", NAMESPACES)
    logger.info(f"Found {len(url_elements)} URL entries in sitemap")

    for url_el in url_elements:
        try:
            loc = url_el.findtext("sm:loc", default="", namespaces=NAMESPACES).strip()
            if not loc:
                continue

            title = url_el.findtext("news:news/news:title", default="", namespaces=NAMESPACES).strip()
            pub_date = url_el.findtext("news:news/news:publication_date", default="", namespaces=NAMESPACES).strip()
            keywords_str = url_el.findtext("news:news/news:keywords", default="", namespaces=NAMESPACES).strip()
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else []

            if not title:
                slug = loc.rstrip("/").split("/")[-1]
                title = slug.replace("-", " ").title()

            articles.append(Article(url=loc, title=title, publication_date=pub_date, keywords=keywords))
        except Exception as e:
            logger.warning(f"Error parsing URL element: {e}")
            continue

    return articles


def fetch_and_parse(sitemap_url: str) -> Optional[List[Article]]:
    xml_content = fetch_sitemap(sitemap_url)
    if xml_content is None:
        return None
    return parse_sitemap(xml_content)
