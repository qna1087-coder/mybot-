"""Pure schedule math. Windows may cross midnight; weekly masks key on the day a window STARTS."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from vigil.core.timeutil import as_aware_utc, local_to_utc_naive, parse_hhmm, safe_zone

WEEKDAY_BITS = tuple(1 << i for i in range(7))  # Mon=1 … Sun=64
ALL_DAYS = 127


def day_allowed(sched: Any, weekday: int) -> bool:
    if sched.kind != "weekly":
        return True
    return bool(int(sched.weekdays or 0) & (1 << weekday))


def _window_starting(sched: Any, day, tz) -> tuple[datetime, datetime] | None:  # noqa: ANN001
    start_t = parse_hhmm(sched.start_time)
    end_t = parse_hhmm(sched.end_time)
    if start_t is None or end_t is None:
        return None
    start = datetime.combine(day, start_t, tzinfo=tz)
    end = datetime.combine(day, end_t, tzinfo=tz)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def window_at(sched: Any, now_utc: datetime) -> tuple[datetime, datetime] | None:
    """If now is inside one of the schedule's windows, return (start, end) as naive UTC."""
    tz = safe_zone(sched.timezone)
    now_local = as_aware_utc(now_utc).astimezone(tz)
    for offset in (0, -1):
        day = now_local.date() + timedelta(days=offset)
        if not day_allowed(sched, day.weekday()):
            continue
        win = _window_starting(sched, day, tz)
        if win is None:
            return None
        start, end = win
        if start <= now_local < end:
            return local_to_utc_naive(start), local_to_utc_naive(end)
    return None


def next_window(sched: Any, now_utc: datetime, horizon_days: int = 8) -> tuple[datetime, datetime] | None:
    """The next window that starts strictly after now (naive UTC)."""
    tz = safe_zone(sched.timezone)
    now_local = as_aware_utc(now_utc).astimezone(tz)
    for offset in range(0, horizon_days):
        day = now_local.date() + timedelta(days=offset)
        if not day_allowed(sched, day.weekday()):
            continue
        win = _window_starting(sched, day, tz)
        if win is None:
            return None
        start, end = win
        if start > now_local:
            return local_to_utc_naive(start), local_to_utc_naive(end)
    return None


def describe_days(mask: int, labels: list[str]) -> str:
    mask = int(mask or 0)
    if mask == ALL_DAYS:
        return labels[7] if len(labels) > 7 else "Every day"
    return " ".join(labels[i] for i in range(7) if mask & (1 << i)) or "—"
