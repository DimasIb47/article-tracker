"""
bot.py — Main polling loop for the Article Tracker Bot (Docker/PostgreSQL version).

Usage:
    python bot.py          # Normal mode
    python bot.py --test   # Send test notification and exit
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime

import pytz

import db
from sitemap_parser import fetch_and_parse
from streak import update_streak
from discord_webhook import send_article_notification, send_error_alert, send_startup_message

# ─── Logging ────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logger = logging.getLogger("article_tracker")


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ─── Config from ENV ────────────────────────────────────────────────

def load_config() -> dict:
    """Load config from environment variables."""
    config = {
        "sitemap_url": os.environ.get("SITEMAP_URL", ""),
        "discord_webhook_url": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        "discord_user_id": os.environ.get("DISCORD_USER_ID", ""),
        "dashboard_url": os.environ.get("DASHBOARD_URL", ""),
        "article_value_usd": float(os.environ.get("ARTICLE_VALUE_USD", "4.15")),
        "daily_target": int(os.environ.get("DAILY_TARGET", "8")),
        "monthly_target": int(os.environ.get("MONTHLY_TARGET", "240")),
        "poll_interval": int(os.environ.get("POLL_INTERVAL", "180")),
        "timezone": os.environ.get("TIMEZONE", "Asia/Jakarta"),
    }

    # Validate required
    if not config["sitemap_url"]:
        logger.error("SITEMAP_URL not set!")
        sys.exit(1)
    if not config["discord_webhook_url"]:
        logger.error("DISCORD_WEBHOOK_URL not set!")
        sys.exit(1)

    return config


# ─── Shutdown ────────────────────────────────────────────────────────

shutdown_flag = False


def signal_handler(signum, frame):
    global shutdown_flag
    logger.info("Shutdown signal received...")
    shutdown_flag = True


# ─── Test Mode ───────────────────────────────────────────────────────

def run_test(config: dict):
    """Send a test notification to verify webhook + button."""
    logger.info("=== TEST MODE ===")

    send_article_notification(
        webhook_url=config["discord_webhook_url"],
        article_title="🧪 Test Article — Bot Works!",
        article_url="https://example.com/test-article",
        article_value=config["article_value_usd"],
        today_count=3,
        daily_target=config["daily_target"],
        monthly_count=42,
        monthly_target=config["monthly_target"],
        streak=5,
        total_earned=37.50,
        user_id=config["discord_user_id"],
        dashboard_url=config["dashboard_url"],
    )

    logger.info("Test notification sent! Check Discord.")


# ─── Main Loop ───────────────────────────────────────────────────────

def poll_cycle(config: dict, tz) -> int:
    """Execute one polling cycle. Returns new article count or -1 on failure."""
    articles = fetch_and_parse(config["sitemap_url"])
    if articles is None:
        return -1

    new_count = 0
    article_value = config["article_value_usd"]

    for article in articles:
        if db.is_known_url(article.url):
            continue

        logger.info(f"🆕 New article: {article.title}")

        # Update streak
        streak = update_streak(tz)

        # Insert article into database
        db.insert_article(
            url=article.url,
            title=article.title,
            published_at=None,  # Sitemap date could be parsed here
            earning=article_value,
            tz=tz,
        )

        # Get updated counts
        today_count = db.get_today_count(tz)
        today_earned = db.get_today_earned(tz)
        monthly_count = db.get_monthly_count(tz)
        monthly_earned = db.get_monthly_earned(tz)

        # Send Discord notification
        send_article_notification(
            webhook_url=config["discord_webhook_url"],
            article_title=article.title,
            article_url=article.url,
            article_value=article_value,
            today_count=today_count,
            daily_target=config["daily_target"],
            monthly_count=monthly_count,
            monthly_target=config["monthly_target"],
            streak=streak,
            today_earned=today_earned,
            monthly_earned=monthly_earned,
            user_id=config["discord_user_id"],
            dashboard_url=config["dashboard_url"],
        )

        new_count += 1
        if new_count > 1:
            time.sleep(1)

    return new_count


def main():
    parser = argparse.ArgumentParser(description="Article Tracker Bot")
    parser.add_argument("--test", action="store_true", help="Send test notification and exit")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    logger.info("=" * 50)
    logger.info("  ARTICLE TRACKER BOT v2")
    logger.info("=" * 50)

    config = load_config()

    # Timezone
    try:
        tz = pytz.timezone(config["timezone"])
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone: {config['timezone']}. Using UTC.")
        tz = pytz.UTC

    # Init database
    logger.info("Initializing database...")
    db.init_db()

    # Test mode
    if args.test:
        run_test(config)
        return

    # Shutdown handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Startup message
    config_summary = (
        f"Sitemap: {config['sitemap_url']}\n"
        f"Rate: ${config['article_value_usd']}/article\n"
        f"Daily target: {config['daily_target']}\n"
        f"Monthly target: {config['monthly_target']}\n"
        f"Poll interval: {config['poll_interval']}s\n"
        f"Dashboard: {config['dashboard_url']}"
    )
    logger.info(f"\n{config_summary}")

    send_startup_message(
        config["discord_webhook_url"],
        config_summary,
        user_id=config["discord_user_id"],
        dashboard_url=config["dashboard_url"],
    )

    # Main loop
    consecutive_failures = 0
    max_failures = 3
    poll_interval = config["poll_interval"]

    logger.info(f"Starting polling (every {poll_interval}s)...")

    while not shutdown_flag:
        try:
            now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            logger.info(f"--- Poll @ {now_str} ---")

            result = poll_cycle(config, tz)

            if result == -1:
                consecutive_failures += 1
                logger.warning(f"Poll failed ({consecutive_failures}/{max_failures})")
                if consecutive_failures >= max_failures:
                    send_error_alert(
                        webhook_url=config["discord_webhook_url"],
                        error_msg=f"Sitemap fetch failed {consecutive_failures}x in a row.",
                        consecutive_failures=consecutive_failures,
                        user_id=config["discord_user_id"],
                    )
                    consecutive_failures = 0
            else:
                consecutive_failures = 0
                if result > 0:
                    logger.info(f"✅ {result} new article(s)!")
                else:
                    logger.info("No new articles.")

        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            consecutive_failures += 1

        # Interruptible sleep
        for _ in range(poll_interval):
            if shutdown_flag:
                break
            time.sleep(1)

    logger.info("Bot stopped. Goodbye! 👋")


if __name__ == "__main__":
    main()
