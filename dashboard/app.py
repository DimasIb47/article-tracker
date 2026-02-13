"""
app.py — FastAPI Dashboard for Article Tracker.

Serves a web dashboard showing earnings, streaks, progress, and article history.
Protected with a simple password query param.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
import pytz
import uvicorn
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Article Tracker Dashboard")

# Static files & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Config from env
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Jakarta")
ARTICLE_VALUE = float(os.environ.get("ARTICLE_VALUE_USD", "12.5"))
DAILY_TARGET = int(os.environ.get("DAILY_TARGET", "8"))
MONTHLY_TARGET = int(os.environ.get("MONTHLY_TARGET", "240"))


def get_db():
    return psycopg2.connect(DATABASE_URL)


def get_tz():
    try:
        return pytz.timezone(TIMEZONE)
    except Exception:
        return pytz.UTC


def check_auth(key: str) -> bool:
    """Simple password check. Empty password = no auth required."""
    if not DASHBOARD_PASSWORD:
        return True
    return key == DASHBOARD_PASSWORD


# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, key: str = Query(default="")):
    if not check_auth(key):
        return HTMLResponse(
            content="<h1>🔒 Access Denied</h1><p>Add <code>?key=YOUR_PASSWORD</code> to the URL.</p>",
            status_code=403,
        )

    tz = get_tz()
    now = datetime.now(tz)
    today = now.date()
    first_of_month = now.replace(day=1).date()

    conn = get_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Today stats
            cur.execute("SELECT COALESCE(article_count, 0) as count, COALESCE(earned, 0) as earned FROM daily_stats WHERE date = %s", (today,))
            today_row = cur.fetchone() or {"count": 0, "earned": 0}

            # Monthly stats
            cur.execute("SELECT COALESCE(SUM(article_count), 0) as count, COALESCE(SUM(earned), 0) as earned FROM daily_stats WHERE date >= %s", (first_of_month,))
            monthly_row = cur.fetchone() or {"count": 0, "earned": 0}

            # All-time stats
            cur.execute("SELECT COUNT(*) as count, COALESCE(SUM(earning), 0) as earned FROM articles")
            total_row = cur.fetchone() or {"count": 0, "earned": 0}

            # Streak
            cur.execute("SELECT current_streak, last_publish_date FROM streak_info WHERE id = 1")
            streak_row = cur.fetchone() or {"current_streak": 0, "last_publish_date": None}

            # Recent articles (last 20)
            cur.execute("SELECT title, url, detected_at, earning FROM articles ORDER BY detected_at DESC LIMIT 20")
            recent_articles = cur.fetchall()

            # Daily chart data (last 30 days)
            thirty_days_ago = today - timedelta(days=30)
            cur.execute(
                "SELECT date, article_count, earned FROM daily_stats WHERE date >= %s ORDER BY date ASC",
                (thirty_days_ago,),
            )
            chart_rows = cur.fetchall()

            # Streak heatmap data (last 90 days)
            ninety_days_ago = today - timedelta(days=90)
            cur.execute(
                "SELECT date, article_count FROM daily_stats WHERE date >= %s ORDER BY date ASC",
                (ninety_days_ago,),
            )
            heatmap_rows = cur.fetchall()
    finally:
        conn.close()

    # Build chart data
    chart_labels = []
    chart_values = []
    for row in chart_rows:
        chart_labels.append(row["date"].strftime("%b %d"))
        chart_values.append(int(row["article_count"]))

    # Build heatmap data
    heatmap_data = {}
    for row in heatmap_rows:
        heatmap_data[row["date"].isoformat()] = int(row["article_count"])

    # Progress percentages
    today_count = int(today_row["count"])
    monthly_count = int(monthly_row["count"])
    today_pct = min(100, int((today_count / DAILY_TARGET) * 100)) if DAILY_TARGET > 0 else 0
    monthly_pct = min(100, int((monthly_count / MONTHLY_TARGET) * 100)) if MONTHLY_TARGET > 0 else 0
    daily_remaining = max(0, DAILY_TARGET - today_count)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "key": key,
        "now": now.strftime("%Y-%m-%d %H:%M %Z"),

        # Earnings
        "today_earned": float(today_row["earned"]),
        "monthly_earned": float(monthly_row["earned"]),
        "total_earned": float(total_row["earned"]),
        "article_value": ARTICLE_VALUE,

        # Counts
        "today_count": today_count,
        "daily_target": DAILY_TARGET,
        "monthly_count": monthly_count,
        "monthly_target": MONTHLY_TARGET,
        "total_count": int(total_row["count"]),
        "daily_remaining": daily_remaining,

        # Progress
        "today_pct": today_pct,
        "monthly_pct": monthly_pct,

        # Streak
        "streak": int(streak_row["current_streak"]),
        "last_publish": streak_row["last_publish_date"],

        # Articles
        "recent_articles": recent_articles,

        # Chart
        "chart_labels": chart_labels,
        "chart_values": chart_values,

        # Heatmap
        "heatmap_data": heatmap_data,
    })


@app.get("/api/stats")
async def api_stats(key: str = Query(default="")):
    """JSON API endpoint for stats."""
    if not check_auth(key):
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    tz = get_tz()
    now = datetime.now(tz)
    today = now.date()
    first_of_month = now.replace(day=1).date()

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(article_count, 0), COALESCE(earned, 0) FROM daily_stats WHERE date = %s", (today,))
            today_row = cur.fetchone() or (0, 0)

            cur.execute("SELECT COALESCE(SUM(article_count), 0), COALESCE(SUM(earned), 0) FROM daily_stats WHERE date >= %s", (first_of_month,))
            monthly_row = cur.fetchone() or (0, 0)

            cur.execute("SELECT current_streak FROM streak_info WHERE id = 1")
            streak_row = cur.fetchone() or (0,)
    finally:
        conn.close()

    return {
        "today_count": today_row[0],
        "today_earned": float(today_row[1]),
        "monthly_count": monthly_row[0],
        "monthly_earned": float(monthly_row[1]),
        "streak": streak_row[0],
        "daily_target": DAILY_TARGET,
        "monthly_target": MONTHLY_TARGET,
    }


if __name__ == "__main__":
    host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.environ.get("DASHBOARD_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")
