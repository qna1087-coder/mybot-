from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow() -> datetime:
    """Naive UTC — the single representation stored in the database."""
    return datetime.now(UTC).replace(tzinfo=None)


def as_aware_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def safe_zone(name: str | None, fallback: str = "UTC") -> ZoneInfo:
    for candidate in (name, fallback, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def to_local(dt: datetime, tz: str | None) -> datetime:
    return as_aware_utc(dt).astimezone(safe_zone(tz))


def local_to_utc_naive(dt_local: datetime) -> datetime:
    return dt_local.astimezone(UTC).replace(tzinfo=None)


def fmt_clock(dt: datetime, tz: str | None) -> str:
    return to_local(dt, tz).strftime("%H:%M")


def fmt_datetime(dt: datetime, tz: str | None) -> str:
    return to_local(dt, tz).strftime("%d %b %H:%M")


def fmt_date(dt: datetime, tz: str | None) -> str:
    return to_local(dt, tz).strftime("%a %d %b")


def humanize_ago(dt: datetime, lang: str = "en", now: datetime | None = None) -> str:
    now = now or utcnow()
    delta = now - dt
    seconds = max(int(delta.total_seconds()), 0)
    if lang == "ar":
        if seconds < 60:
            return "الآن"
        if seconds < 3600:
            return f"قبل {seconds // 60} د"
        if seconds < 86400:
            return f"قبل {seconds // 3600} س"
        return f"قبل {seconds // 86400} ي"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def humanize_duration(seconds: int, lang: str = "en") -> str:
    seconds = max(int(seconds), 0)
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if lang == "ar":
        parts = []
        if h:
            parts.append(f"{h} س")
        if m or not parts:
            parts.append(f"{m} د")
        return " ".join(parts)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)


def parse_hhmm(value: str) -> time | None:
    value = value.strip().replace("：", ":")
    # Accept Arabic-Indic digits as well.
    value = value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if ":" not in value:
        if value.isdigit() and len(value) in (3, 4):
            value = f"{value[:-2]}:{value[-2:]}"
        else:
            return None
    try:
        hh, mm = value.split(":", 1)
        h, m = int(hh), int(mm)
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(hour=h, minute=m)


def parse_duration(value: str) -> timedelta | None:
    """'90' (minutes), '2h', '45m', '1h30m', '1:30'."""
    v = value.strip().lower().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if not v:
        return None
    if v.isdigit():
        return timedelta(minutes=int(v))
    if ":" in v:
        t = parse_hhmm(v)
        return timedelta(hours=t.hour, minutes=t.minute) if t else None
    total = 0
    num = ""
    for ch in v:
        if ch.isdigit():
            num += ch
        elif ch in "hm" and num:
            total += int(num) * (60 if ch == "h" else 1)
            num = ""
        elif ch in " ":
            continue
        else:
            return None
    if num:
        total += int(num)
    return timedelta(minutes=total) if total > 0 else None
