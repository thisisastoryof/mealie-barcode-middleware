from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.templating import templates

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


@router.get("/activities", response_class=HTMLResponse)
def activity_page(
    request: Request,
    result: str = Query("all"),
    db: Session = Depends(get_db),
):
    """Activity log page — all notifications with filter tabs."""
    query = db.query(Notification).order_by(Notification.created_at.desc())
    if result == "added":
        query = query.filter(Notification.result.in_(["added", "added_as_note", "queued"]))
    elif result != "all":
        query = query.filter(Notification.result == result)
    notifications = query.limit(200).all()
    return templates.TemplateResponse(request, "activity.html", {
        "notifications": notifications,
        "current_filter": result,
    })


@router.post("/activities/mark-all-read")
def activity_mark_all_read(db: Session = Depends(get_db)):
    """HTML form action: mark all read and redirect back to activities."""
    db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
    db.commit()
    return RedirectResponse("/activities", status_code=303)


@router.post("/activities/delete-read")
def activity_delete_read(db: Session = Depends(get_db)):
    """HTML form action: delete all read notifications."""
    db.query(Notification).filter(Notification.is_read == True).delete()
    db.commit()
    return RedirectResponse("/activities", status_code=303)
