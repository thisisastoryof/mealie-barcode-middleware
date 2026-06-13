"""Home Assistant webhook integration — push notifications for scans that need action."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def notify_scan(barcode: str, item: str | None, result: str, action_url: str) -> None:
    """POST scan data to the HA webhook. Fire-and-forget, never raises."""
    url = settings.ha_webhook_url
    if not url:
        return

    payload = {
        "barcode": barcode,
        "item": item or barcode,
        "result_type": result,
        "action_url": action_url,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=3)
        if resp.status_code >= 400:
            logger.warning("HA webhook returned %d: %s", resp.status_code, resp.text[:200])
        else:
            logger.debug("HA webhook notified: %s → %s", barcode, result)
    except httpx.TimeoutException:
        logger.warning("HA webhook timed out for barcode %s", barcode)
    except Exception:
        logger.warning("HA webhook failed for barcode %s", barcode, exc_info=True)
