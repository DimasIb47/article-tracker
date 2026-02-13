"""
discord_webhook.py — Discord webhook with PLAIN TEXT + Link Button.

Sends plain text messages (not embeds) for mobile push notification preview.
Includes a "View Dashboard" link button component.
"""

import logging
import time

import requests

from progress import make_progress_bar, format_earning_increment, calculate_daily_remaining, format_total_earned

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2


def _mention(user_id: str) -> str:
    if user_id:
        return f"<@{user_id}>"
    return ""


def _dashboard_button(dashboard_url: str) -> list | None:
    """Build Discord Link Button component for dashboard."""
    if not dashboard_url:
        return None
    return [
        {
            "type": 1,  # Action Row
            "components": [
                {
                    "type": 2,       # Button
                    "style": 5,      # Link
                    "label": "📊 View Dashboard",
                    "url": dashboard_url,
                }
            ],
        }
    ]


def send_article_notification(
    webhook_url: str,
    article_title: str,
    article_url: str,
    article_value: float,
    today_count: int,
    daily_target: int,
    monthly_count: int,
    monthly_target: int,
    streak: int,
    total_earned: float,
    user_id: str = "",
    dashboard_url: str = "",
):
    """Send a plain text Discord notification for a newly detected article."""
    daily_remaining = calculate_daily_remaining(today_count, daily_target)
    daily_bar = make_progress_bar(today_count, daily_target)
    monthly_bar = make_progress_bar(monthly_count, monthly_target)
    earning_str = format_earning_increment(article_value)
    total_str = format_total_earned(total_earned)
    mention = _mention(user_id)

    if daily_remaining > 0:
        goal_line = f"🎯  {daily_remaining} More To Daily Goal"
    else:
        goal_line = "🎯  ✅ Daily Goal Reached!"

    message = (
        f"💸  **{earning_str}**\n"
        f"💰  Total This Month: **{total_str}**\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"🚀  **ARTICLE PUBLISHED**\n"
        f"📰  {article_title}\n"
        f"🔗  {article_url}\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"📊  **Today**\n"
        f"`{daily_bar}`\n"
        f"**{today_count} / {daily_target}** Articles\n"
        f"\n"
        f"🔥  **Streak: {streak} Day{'s' if streak != 1 else ''}**\n"
        f"\n"
        f"{goal_line}\n"
        f"\n"
        f"📈  **Monthly Progress**\n"
        f"`{monthly_bar}`\n"
        f"**{monthly_count} / {monthly_target}** Articles\n"
        f"\n{mention}"
    )

    payload = {"content": message.strip()}

    # Add dashboard button
    button = _dashboard_button(dashboard_url)
    if button:
        payload["components"] = button

    _send_webhook(webhook_url, payload)


def send_error_alert(webhook_url: str, error_msg: str, consecutive_failures: int, user_id: str = ""):
    mention = _mention(user_id)
    message = (
        f"⚠️  **ARTICLE TRACKER — ERROR**\n\n"
        f"Sitemap polling has failed **{consecutive_failures}** consecutive times.\n"
        f"```\n{error_msg[:500]}\n```\n"
        f"Bot will keep retrying.\n"
        f"\n{mention}"
    )
    payload = {"content": message.strip()}
    _send_webhook(webhook_url, payload)


def send_startup_message(webhook_url: str, config_summary: str, user_id: str = "", dashboard_url: str = ""):
    mention = _mention(user_id)
    message = (
        f"✅  **ARTICLE TRACKER — ONLINE**\n\n"
        f"Bot is now running and monitoring articles.\n"
        f"```\n{config_summary}\n```\n"
        f"\n{mention}"
    )
    payload = {"content": message.strip()}

    button = _dashboard_button(dashboard_url)
    if button:
        payload["components"] = button

    _send_webhook(webhook_url, payload)


def _send_webhook(webhook_url: str, payload: dict):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(webhook_url, json=payload, timeout=15)

            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 5)
                logger.warning(f"Rate limited. Retrying after {retry_after}s...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            logger.info("Discord webhook sent successfully.")
            return

        except requests.RequestException as e:
            delay = BASE_DELAY ** attempt
            logger.warning(f"Webhook attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(delay)
            else:
                logger.error(f"Webhook delivery failed after {MAX_RETRIES} attempts.")
