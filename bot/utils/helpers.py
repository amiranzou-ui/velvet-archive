from typing import Optional, List, Set
"""
bot/utils/helpers.py
━━━━━━━━━━━━━━━━━━━━
Shared utilities:
  - configure_logging(): set up rotating file + console logs
  - admin_only: decorator that blocks non-admins with a polite error
  - answer_callback: safe wrapper around callback query answering
"""

import logging
import logging.handlers
from functools import wraps
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import ADMIN_IDS, LOGS_DIR
from bot.utils.captions import error_not_admin


def configure_logging() -> None:
    """
    Set up two log handlers:
    1. Console (INFO level) — colourised via a custom formatter
    2. Rotating file in /logs/ (DEBUG level) — full trace

    Call this once at the start of main.py.
    """
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%H:%M:%S"

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # Rotating file handler (10 MB × 5 backups)
    log_path = LOGS_DIR / "velvet.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Suppress noisy library loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def admin_only(func):
    """
    Decorator for handlers that should only work for admin users.
    Works with both message handlers and callback query handlers.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id not in ADMIN_IDS:
            msg = error_not_admin()
            if update.callback_query:
                await update.callback_query.answer(
                    "✦ restricted to archivists only.", show_alert=True
                )
            elif update.message:
                await update.message.reply_html(msg)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


async def safe_answer(callback_query, text: str = "", alert: bool = False) -> None:
    """
    Answer a callback query without raising if it's already expired.
    Telegram callbacks expire after 60 seconds.
    """
    try:
        await callback_query.answer(text, show_alert=alert)
    except Exception:
        pass  # callback already answered or expired, silently ignore


def pages_info(total: int, page: int, page_size: int) -> dict:
    """Return a dict with pagination metadata."""
    total_pages = max(1, -(-total // page_size))
    return {
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 0,
        "has_next": page < total_pages - 1,
    }
