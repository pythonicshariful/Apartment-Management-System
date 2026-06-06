"""
telegram_backup.py
Asynchronous Telegram DB backup — triggered after every database write.
Sends the SQLite .db file to a Telegram Bot/Channel using the sendDocument API.
"""

import os
import threading
import time
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendDocument"
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID", "")
DB_PATH      = os.path.join(os.path.dirname(__file__), "apartments.db")

MAX_RETRIES  = 3
RETRY_DELAY  = 2  # seconds between retries


def _do_send(caption: str):
    """Internal: open the DB file and POST it to Telegram. Retries on failure."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.warning("[Telegram Backup] BOT_TOKEN not configured — skipping backup.")
        return
    if not CHAT_ID or CHAT_ID == "YOUR_TELEGRAM_CHANNEL_CHAT_ID_HERE":
        logger.warning("[Telegram Backup] CHAT_ID not configured — skipping backup.")
        return

    url = TELEGRAM_API.format(token=BOT_TOKEN)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(DB_PATH, "rb") as db_file:
                response = requests.post(
                    url,
                    data={"chat_id": CHAT_ID, "caption": caption},
                    files={"document": ("apartments.db", db_file, "application/octet-stream")},
                    timeout=20,
                )
            if response.ok:
                logger.info("[Telegram Backup] DB backup sent successfully (attempt %d).", attempt)
                return
            else:
                logger.warning(
                    "[Telegram Backup] Attempt %d failed: %s — %s",
                    attempt, response.status_code, response.text
                )
        except requests.RequestException as exc:
            logger.error("[Telegram Backup] Attempt %d error: %s", attempt, exc)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    logger.error("[Telegram Backup] All %d attempts failed. Backup not sent.", MAX_RETRIES)


def send_backup_to_telegram(action: str = "DB Updated", performed_by: str = "System"):
    """
    Public interface — fire-and-forget in a background daemon thread.
    Call this after any successful database commit.
    """
    caption = (
        f"📦 *Apartment DB Backup*\n"
        f"🕐 Action : `{action}`\n"
        f"👤 By     : `{performed_by}`\n"
        f"📁 File   : `apartments.db`"
    )
    thread = threading.Thread(target=_do_send, args=(caption,), daemon=True)
    thread.start()
