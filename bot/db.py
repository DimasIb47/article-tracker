"""
db.py — PostgreSQL database layer.

Handles connection, table creation, and all queries for the article tracker.
"""

import logging
import os
from datetime import datetime, date

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# SQL for table creation
CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    earning NUMERIC(10,2) DEFAULT 4.15
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date DATE PRIMARY KEY,
    article_count INTEGER DEFAULT 0,
    earned NUMERIC(10,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS streak_info (
    id INTEGER PRIMARY KEY DEFAULT 1,
    current_streak INTEGER DEFAULT 0,
    last_publish_date DATE
);

-- Ensure streak_info has exactly one row
INSERT INTO streak_info (id, current_streak, last_publish_date)
VALUES (1, 0, NULL)
ON CONFLICT (id) DO NOTHING;
"""


def get_connection():
    """Get a new database connection from DATABASE_URL env var."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLES)
        conn.commit()
        logger.info("Database tables initialized.")
    finally:
        conn.close()


def is_known_url(url: str) -> bool:
    """Check if an article URL already exists in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM articles WHERE url = %s", (url,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def insert_article(url: str, title: str, published_at: datetime | None, earning: float, tz) -> None:
    """Insert a new article and update daily stats."""
    now = datetime.now(tz)
    today = now.date()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Insert article
            cur.execute(
                """INSERT INTO articles (url, title, published_at, detected_at, earning)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (url) DO NOTHING""",
                (url, title, published_at, now, earning),
            )

            # Upsert daily stats
            cur.execute(
                """INSERT INTO daily_stats (date, article_count, earned)
                   VALUES (%s, 1, %s)
                   ON CONFLICT (date) DO UPDATE
                   SET article_count = daily_stats.article_count + 1,
                       earned = daily_stats.earned + %s""",
                (today, earning, earning),
            )
        conn.commit()
        logger.info(f"Article inserted: {title}")
    finally:
        conn.close()


def get_today_count(tz) -> int:
    """Get article count for today."""
    today = datetime.now(tz).date()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT article_count FROM daily_stats WHERE date = %s", (today,))
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


def get_today_earned(tz) -> float:
    """Get total earnings for today."""
    today = datetime.now(tz).date()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT earned FROM daily_stats WHERE date = %s", (today,))
            row = cur.fetchone()
            return float(row[0]) if row else 0.0
    finally:
        conn.close()


def get_monthly_count(tz) -> int:
    """Get total article count for the current month."""
    now = datetime.now(tz)
    first_of_month = now.replace(day=1).date()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(article_count), 0) FROM daily_stats WHERE date >= %s",
                (first_of_month,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_monthly_earned(tz) -> float:
    """Get total earnings for the current month."""
    now = datetime.now(tz)
    first_of_month = now.replace(day=1).date()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(earned), 0) FROM daily_stats WHERE date >= %s",
                (first_of_month,),
            )
            return float(cur.fetchone()[0])
    finally:
        conn.close()


def get_total_earned() -> float:
    """Get all-time total earnings."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(earning), 0) FROM articles")
            return float(cur.fetchone()[0])
    finally:
        conn.close()


def get_total_articles() -> int:
    """Get all-time article count."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles")
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_streak() -> tuple[int, date | None]:
    """Get current streak and last publish date."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_streak, last_publish_date FROM streak_info WHERE id = 1")
            row = cur.fetchone()
            if row:
                return row[0], row[1]
            return 0, None
    finally:
        conn.close()


def update_streak(streak: int, last_publish_date: date) -> None:
    """Update streak info."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE streak_info SET current_streak = %s, last_publish_date = %s WHERE id = 1""",
                (streak, last_publish_date),
            )
        conn.commit()
    finally:
        conn.close()
