from __future__ import annotations

from datetime import datetime


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_timestamp() -> str:
    return now_local().isoformat(timespec="seconds")


def file_timestamp() -> str:
    return now_local().strftime("%Y%m%d_%H%M%S")


def format_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "00:00"
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

