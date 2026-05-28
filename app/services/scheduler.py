import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.models import RetryQueue
from app.services.mealie import sync_foods

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_food_sync():
    """Background job: sync Mealie foods."""
    logger.info("Running scheduled food sync")
    db = SessionLocal()
    try:
        sync_foods(db)
    except Exception as e:
        logger.error(f"Scheduled food sync failed: {e}")
    finally:
        db.close()


def _process_retry_queue():
    """Background job: retry failed Mealie shopping list additions."""
    import httpx

    db = SessionLocal()
    try:
        now = _utcnow()
        pending = (
            db.query(RetryQueue)
            .filter(RetryQueue.next_retry_at <= now)
            .order_by(RetryQueue.next_retry_at.asc())
            .all()
        )
        if not pending:
            return

        logger.info(f"Processing {len(pending)} retry queue items")
        headers = {
            "Authorization": f"Bearer {settings.mealie_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{settings.mealie_url}/api/households/shopping/items"

        for item in pending:
            try:
                payload = json.loads(item.payload)
                resp = httpx.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code in (200, 201):
                    db.delete(item)
                    logger.info(f"Retry success for barcode={item.barcode}")
                else:
                    item.attempts += 1
                    backoff = min(2**item.attempts, 60)
                    item.next_retry_at = now + timedelta(minutes=backoff)
                    logger.warning(
                        f"Retry failed for {item.barcode}: HTTP {resp.status_code}, "
                        f"next retry in {backoff}m"
                    )
            except httpx.HTTPError as e:
                item.attempts += 1
                backoff = min(2**item.attempts, 60)
                item.next_retry_at = now + timedelta(minutes=backoff)
                logger.warning(f"Retry error for {item.barcode}: {e}, next in {backoff}m")

        db.commit()
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler with food sync and retry queue jobs."""
    scheduler.add_job(
        _run_food_sync,
        "interval",
        hours=settings.food_sync_interval_hours,
        id="food_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        _process_retry_queue,
        "interval",
        minutes=2,
        id="retry_queue",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (food sync + retry queue)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
