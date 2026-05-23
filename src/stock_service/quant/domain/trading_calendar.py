from datetime import datetime, time


def is_trading_time(now: datetime | None = None) -> tuple[bool, str]:
    """Check if current time is within A-share trading hours.

    Trading hours:
    - Monday to Friday (weekday 0-4)
    - 9:30 - 11:30 (morning session)
    - 13:00 - 15:00 (afternoon session)

    Returns:
        (is_trading, reason) tuple
    """
    if now is None:
        now = datetime.now()

    # Check weekday (0=Monday, 6=Sunday)
    if now.weekday() >= 5:
        return False, "非交易日（周末）"

    current_time = now.time()

    # Morning session: 9:30 - 11:30
    morning_start = time(9, 30)
    morning_end = time(11, 30)

    # Afternoon session: 13:00 - 15:00
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)

    if morning_start <= current_time <= morning_end:
        return True, "交易中（上午盘）"
    elif afternoon_start <= current_time <= afternoon_end:
        return True, "交易中（下午盘）"
    elif current_time < morning_start:
        return False, "未开盘（开盘时间 9:30）"
    elif morning_end < current_time < afternoon_start:
        return False, "午间休市（13:00 恢复）"
    else:
        return False, "已收盘（收盘时间 15:00）"


def is_trading_day(now: datetime | None = None) -> bool:
    """Check if current day is a trading day (weekday)."""
    if now is None:
        now = datetime.now()
    return now.weekday() < 5
