import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import SessionLocal
from app.events import scan_events
from app.models import BarcodeMapping, Item, Notification, RetryQueue
from app.services.mealie import sync_items

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _run_item_sync():
    """Background job: sync Mealie items."""
    logger.info("Running scheduled item sync")
    db = SessionLocal()
    try:
        sync_items(db)
    except Exception as e:
        logger.error(f"Scheduled item sync failed: {e}")
    finally:
        db.close()


def _process_retry_queue():
    """Background job: retry failed Mealie shopping list additions."""
    import httpx

    db = SessionLocal()
    try:
        now = utcnow()
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
                    if item.attempts >= settings.max_retry_attempts:
                        _create_retry_failed_notification(item, db)
                        db.delete(item)
                        logger.warning(
                            f"Retry permanently failed for {item.barcode} after "
                            f"{item.attempts} attempts (HTTP {resp.status_code})"
                        )
                    else:
                        backoff = min(2**item.attempts, 60)
                        item.next_retry_at = now + timedelta(minutes=backoff)
                        logger.warning(
                            f"Retry failed for {item.barcode}: HTTP {resp.status_code}, "
                            f"next retry in {backoff}m"
                        )
            except httpx.HTTPError as e:
                item.attempts += 1
                if item.attempts >= settings.max_retry_attempts:
                    _create_retry_failed_notification(item, db)
                    db.delete(item)
                    logger.warning(
                        f"Retry permanently failed for {item.barcode} after "
                        f"{item.attempts} attempts: {e}"
                    )
                else:
                    backoff = min(2**item.attempts, 60)
                    item.next_retry_at = now + timedelta(minutes=backoff)
                    logger.warning(f"Retry error for {item.barcode}: {e}, next in {backoff}m")

        db.commit()
    finally:
        db.close()


def _create_retry_failed_notification(item: RetryQueue, db):
    """Create a notification when a retry queue item permanently fails."""
    try:
        payload = json.loads(item.payload)
        item_hint = payload.get("note") or payload.get("foodId") or item.barcode
    except (json.JSONDecodeError, TypeError):
        item_hint = item.barcode

    title = "Failed to add to shopping list"
    message = f"{item_hint} — could not reach Mealie after {item.attempts} retries"

    db.add(Notification(
        barcode=item.barcode,
        title=title,
        message=message,
        result="retry_failed",
    ))

    # Emit real-time SSE event so open browsers get a toast + browser notification
    scan_events.publish_threadsafe("scan", {
        "barcode": item.barcode,
        "result": "retry_failed",
        "food": str(item_hint),
    })


def _purge_old_notifications():
    """Delete read notifications older than 7 days."""
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(days=7)
        deleted = (
            db.query(Notification)
            .filter(Notification.is_read == True, Notification.created_at < cutoff)
            .delete()
        )
        db.commit()
        if deleted:
            logger.info(f"Purged {deleted} old read notifications")
    except Exception as e:
        logger.error(f"Notification purge failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler with item sync and retry queue jobs."""
    # Run initial sync if no items exist yet (first run)
    db = SessionLocal()
    try:
        if db.query(Item).first() is None:
            logger.info("No items found — running initial Mealie sync")
            try:
                sync_items(db)
            except Exception as e:
                logger.warning(f"Initial sync failed (will retry on schedule): {e}")
    finally:
        db.close()

    scheduler.add_job(
        _run_item_sync,
        "interval",
        hours=settings.food_sync_interval_hours,
        id="item_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        _process_retry_queue,
        "interval",
        minutes=2,
        id="retry_queue",
        replace_existing=True,
    )
    scheduler.add_job(
        _purge_old_notifications,
        "interval",
        hours=24,
        id="notification_purge",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (item sync + retry queue + notification purge)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
