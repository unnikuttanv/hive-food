from __future__ import annotations
from datetime import datetime, timezone

def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def fmt_dt(dt: datetime) -> str:
    # Render in a human-friendly format (server local time)
    return dt.strftime("%Y-%m-%d %H:%M")

def euro(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v:.2f} €"
