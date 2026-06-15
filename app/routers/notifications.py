from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity
from app.templating import templates, _localtime

router = APIRouter()


@router.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db)):
    """Return non-dismissed notifications for the bell dropdown."""
    items = (
        db.query(Activity)
        .filter(Activity.is_dismissed == False)
        .order_by(Activity.created_at.desc())
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
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]


@router.post("/api/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.get(Activity, notification_id)
    if n:
        n.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Activity).filter(Activity.is_read == False).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-barcode/{barcode}")
def mark_read_by_barcode(barcode: str, db: Session = Depends(get_db)):
    """Mark all notifications for a given barcode as read."""
    db.query(Activity).filter(
        Activity.barcode == barcode,
        Activity.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.post("/api/notifications/{notification_id}/dismiss")
def dismiss_notification(notification_id: int, db: Session = Depends(get_db)):
    """Dismiss a single notification from the bell dropdown."""
    n = db.get(Activity, notification_id)
    if n:
        n.is_dismissed = True
        n.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/api/notifications/dismiss-read")
def dismiss_all_read(db: Session = Depends(get_db)):
    """Dismiss all read notifications from the bell dropdown."""
    db.query(Activity).filter(
        Activity.is_read == True,
        Activity.is_dismissed == False,
    ).update({"is_dismissed": True})
    db.commit()
    return {"ok": True}


@router.get("/activities", response_class=HTMLResponse)
def activity_page(
    request: Request,
    result: str = Query("all"),
    db: Session = Depends(get_db),
):
    """Activity log page — all notifications with filter tabs."""
    query = db.query(Activity).order_by(Activity.created_at.desc())
    if result == "unread":
        query = query.filter(Activity.is_read == False)
    elif result == "added":
        query = query.filter(Activity.result.in_(["added", "added_as_note", "queued"]))
    elif result != "all":
        query = query.filter(Activity.result == result)
    activities = query.limit(200).all()
    return templates.TemplateResponse(request, "activity.html", {
        "activities": activities,
        "current_filter": result,
    })


@router.get("/api/activities")
def get_activities(result: str = Query("all"), db: Session = Depends(get_db)):
    """JSON endpoint for live-refreshing the activities table."""
    query = db.query(Activity).order_by(Activity.created_at.desc())
    if result == "unread":
        query = query.filter(Activity.is_read == False)
    elif result == "added":
        query = query.filter(Activity.result.in_(["added", "added_as_note", "queued"]))
    elif result != "all":
        query = query.filter(Activity.result == result)
    activities = query.limit(200).all()
    return {
        "items": [
            {
                "id": a.id,
                "barcode": a.barcode,
                "title": a.title,
                "message": a.message,
                "result": a.result,
                "is_read": a.is_read,
                "created_at": _localtime(a.created_at),
            }
            for a in activities
        ]
    }


@router.post("/activities/mark-all-read")
def activity_mark_all_read(db: Session = Depends(get_db)):
    """HTML form action: mark all read and redirect back to activities."""
    db.query(Activity).filter(Activity.is_read == False).update({"is_read": True})
    db.commit()
    return RedirectResponse("/activities", status_code=303)



