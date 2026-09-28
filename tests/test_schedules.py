from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from vigil.core.timeutil import parse_duration, parse_hhmm
from vigil.services.shield.schedules import next_window, window_at


def sched(kind="daily", start="22:00", end="06:00", weekdays=127, tz="Asia/Baghdad"):
    return SimpleNamespace(kind=kind, start_time=start, end_time=end, weekdays=weekdays, timezone=tz)


def test_window_crossing_midnight():
    s = sched()
    # 23:30 Baghdad (UTC+3) == 20:30 UTC → inside
    assert window_at(s, datetime(2026, 9, 28, 20, 30)) is not None
    # 03:00 Baghdad == 00:00 UTC next day → still inside (window started yesterday)
    win = window_at(s, datetime(2026, 9, 29, 0, 0))
    assert win is not None and win[1] == datetime(2026, 9, 29, 3, 0)  # 06:00 Baghdad
    # 12:00 Baghdad → outside
    assert window_at(s, datetime(2026, 9, 28, 9, 0)) is None


def test_weekly_mask_keys_on_start_day():
    fri_only = sched(kind="weekly", weekdays=1 << 4)  # Friday
    # Sat 2026-10-03 02:00 Baghdad (window started Fri 22:00) → inside
    assert window_at(fri_only, datetime(2026, 10, 2, 23, 0)) is not None
    # Sat 23:00 Baghdad → Saturday not allowed → outside
    assert window_at(fri_only, datetime(2026, 10, 3, 20, 0)) is None


def test_next_window():
    s = sched(start="09:00", end="10:00", tz="UTC")
    now = datetime(2026, 9, 28, 12, 0)
    nxt = next_window(s, now)
    assert nxt == (datetime(2026, 9, 29, 9, 0), datetime(2026, 9, 29, 10, 0))
    weekly = sched(kind="weekly", start="09:00", end="10:00", weekdays=1 << 0, tz="UTC")  # Monday
    nxt = next_window(weekly, now)  # 2026-09-28 is a Monday, 12:00 already past → next Monday
    assert nxt[0] == datetime(2026, 10, 5, 9, 0)


def test_time_parsers():
    assert parse_hhmm("22:00").hour == 22
    assert parse_hhmm("٢٢:٣٠").minute == 30
    assert parse_hhmm("2200").hour == 22
    assert parse_hhmm("25:00") is None
    assert parse_duration("90") == timedelta(minutes=90)
    assert parse_duration("2h") == timedelta(hours=2)
    assert parse_duration("1h30m") == timedelta(minutes=90)
    assert parse_duration("1:30") == timedelta(minutes=90)
    assert parse_duration("abc") is None
