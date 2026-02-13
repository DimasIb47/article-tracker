"""
streak.py — Calendar-based streak tracking (PostgreSQL version).

Streak logic:
- If last publish was yesterday → streak continues (+1)
- If last publish was today → streak stays (already counted for today)
- If last publish was before yesterday → streak resets to 1
- If no previous publish → streak starts at 1
"""

import logging
from datetime import datetime

import db

logger = logging.getLogger(__name__)


def update_streak(tz) -> int:
    """
    Update streak based on calendar dates.
    Called when a NEW article is detected.

    Returns:
        Updated streak count.
    """
    now = datetime.now(tz)
    today = now.date()
    current_streak, last_publish = db.get_streak()

    if last_publish is None:
        new_streak = 1
        logger.info(f"First article ever! Streak: {new_streak}")
    else:
        delta = (today - last_publish).days

        if delta == 0:
            new_streak = current_streak if current_streak > 0 else 1
            logger.debug(f"Same day publish. Streak unchanged: {new_streak}")
        elif delta == 1:
            new_streak = current_streak + 1
            logger.info(f"Consecutive day! Streak: {new_streak} 🔥")
        else:
            new_streak = 1
            logger.info(f"Missed {delta - 1} day(s). Streak reset to: {new_streak}")

    db.update_streak(new_streak, today)
    return new_streak
