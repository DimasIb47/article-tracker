"""
progress.py — Progress bar generation and earnings formatting.
"""


def make_progress_bar(current: int, target: int, length: int = 10) -> str:
    """
    Generate a text-based progress bar.

    Examples:
        >>> make_progress_bar(5, 8)
        '██████░░░░ 62%'
        >>> make_progress_bar(8, 8)
        '██████████ 100%'
    """
    if target <= 0:
        return "░" * length + " 0%"

    ratio = min(current / target, 1.0)
    filled = int(ratio * length)
    empty = length - filled
    percentage = int(ratio * 100)

    return "█" * filled + "░" * empty + f" {percentage}%"


def format_earning_increment(value: float) -> str:
    return f"+ ${value:,.2f}"


def format_total_earned(total: float) -> str:
    return f"${total:,.2f}"


def calculate_daily_remaining(current: int, target: int) -> int:
    return max(0, target - current)
