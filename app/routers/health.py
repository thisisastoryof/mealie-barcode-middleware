from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.mealie import check_connectivity

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_ok = False

    mealie_reachable = check_connectivity()

    status = "ok" if (db_ok and mealie_reachable) else "degraded"
    return {
        "status": status,
        "mealie_reachable": mealie_reachable,
        "db_ok": db_ok,
    }
