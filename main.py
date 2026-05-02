"""
main.py
━━━━━━━
The entry point for Velvet Archive.

What happens when you run this:
  1. Logging is configured
  2. The database is initialised (tables created if needed)
  3. Example songs are seeded on first run
  4. The Telegram Application is built
  5. All handlers are registered
  6. The bot starts polling for updates

Run with:
  python main.py
"""

import asyncio
import logging

from telegram.ext import Application

from config.settings import BOT_TOKEN, ADMIN_IDS
from bot.utils.helpers import configure_logging
from database.db import init_db, seed_example_data
from bot.handlers import (
    register_command_handlers,
    register_callback_handlers,
    register_message_handlers,
    build_upload_handler,
)

log = logging.getLogger("velvet.main")


async def post_init(app: Application) -> None:
    """
    Called once after the Application is built but before polling starts.
    Perfect place for async startup tasks.
    """
    await init_db()

    # Seed example data for the first admin if archive is empty
    if ADMIN_IDS:
        first_admin = next(iter(ADMIN_IDS))
        await seed_example_data(first_admin)

    log.info("✦ Velvet Archive is online")
    log.info("✦ Admins: %s", ADMIN_IDS)


def build_app() -> Application:
    """Construct the fully configured Application instance."""
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register handlers in priority order.
    # ConversationHandler must come before the generic callback/message handlers
    # so upload flow gets first pick of updates.
    app.add_handler(build_upload_handler())
    register_command_handlers(app)
    register_callback_handlers(app)
    register_message_handlers(app)

    return app


def main() -> None:
    configure_logging()
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  V E L V E T   A R C H I V E")
    log.info("  underground music bot — starting up")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app = build_app()

    # run_polling blocks until Ctrl+C
    app.run_polling(
        drop_pending_updates=True,  # ignore any queued updates from when bot was offline
        allowed_updates=["message", "callback_query", "inline_query"],
    )


if __name__ == "__main__":
    main()
