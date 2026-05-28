from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification

router = APIRouter()


@router.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db)):
    """Return unread notifications as JSON for the bell dropdown."""
    items = (
        db.query(Notification)
        .filter(Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "barcode": n.barcode,
            "title": n.title,
            "message": n.message,
            "result": n.result,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]


@router.post("/api/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n:
        n.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-barcode/{barcode}")
def mark_read_by_barcode(barcode: str, db: Session = Depends(get_db)):
    """Mark all notifications for a given barcode as read."""
    db.query(Notification).filter(
        Notification.barcode == barcode,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}
