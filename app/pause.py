"""Shopping list pause mode — temporarily suspend list additions."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import SystemState

_KEY = "pause_until"


def is_paused(db: Session) -> bool:
    """Check if shopping list additions are currently paused."""
    row = db.get(SystemState, _KEY)
    if not row or not row.value:
        return False
    try:
        resumes_at = datetime.fromisoformat(row.value)
        if resumes_at.tzinfo is None:
            resumes_at = resumes_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < resumes_at
    except (ValueError, TypeError):
        return False


def pause_until(db: Session, minutes: int) -> datetime:
    """Set pause mode for N minutes. Returns the resume time (UTC)."""
    resumes_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    row = db.get(SystemState, _KEY)
    if row:
        row.value = resumes_at.isoformat()
    else:
        db.add(SystemState(key=_KEY, value=resumes_at.isoformat()))
    db.commit()
    return resumes_at


def resume_now(db: Session) -> None:
    """Cancel pause mode immediately."""
    row = db.get(SystemState, _KEY)
    if row:
        row.value = None
        db.commit()


def get_pause_status(db: Session) -> dict:
    """Return pause status dict for API responses."""
    row = db.get(SystemState, _KEY)
    if not row or not row.value:
        return {"paused": False, "remaining_seconds": None, "resumes_at": None}
    try:
        resumes_at = datetime.fromisoformat(row.value)
        if resumes_at.tzinfo is None:
            resumes_at = resumes_at.replace(tzinfo=timezone.utc)
        remaining = (resumes_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return {"paused": False, "remaining_seconds": None, "resumes_at": None}
        return {
            "paused": True,
            "remaining_seconds": int(remaining),
            "resumes_at": resumes_at.isoformat(),
        }
    except (ValueError, TypeError):
        return {"paused": False, "remaining_seconds": None, "resumes_at": None}
