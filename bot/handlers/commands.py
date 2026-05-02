"""
bot/handlers/commands.py
━━━━━━━━━━━━━━━━━━━━━━━━
Entry point commands: /start, /help, /admin.
These are the doors into the archive.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from config.settings import ADMIN_IDS, BOT_NAME
from bot.keyboards import main_menu_kb, admin_menu_kb
from bot.utils.captions import main_menu
from bot.utils.helpers import admin_only

log = logging.getLogger("velvet.commands")

WELCOME_ART = """
✦ ━━━━━━━━━━━━━━━━━━━━━━━━ ✦
       V E L V E T
       A R C H I V E
✦ ━━━━━━━━━━━━━━━━━━━━━━━━ ✦
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start — First thing a user sees.
    Sends the welcome message and main navigation keyboard.
    """
    user = update.effective_user
    log.info("User %d (%s) started the bot", user.id, user.username)

    greeting = (
        f"<code>{WELCOME_ART}</code>\n"
        f"<i>welcome, {user.first_name}.</i>\n\n"
        f"{main_menu()}"
    )

    await update.message.reply_html(
        greeting,
        reply_markup=main_menu_kb(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help — Contextual help based on who's asking.
    Admins see the upload instructions. Users see navigation tips.
    """
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    if is_admin:
        text = (
            f"<b>✦ {BOT_NAME}  ·  Admin Guide</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Commands</b>\n"
            "<code>/start</code>   — open the archive\n"
            "<code>/admin</code>   — admin panel\n"
            "<code>/upload</code>  — start an upload\n"
            "<code>/stats</code>   — archive statistics\n\n"
            "<b>Uploading a Song</b>\n"
            "1. Send /upload\n"
            "2. Send the audio file\n"
            "3. Fill in the metadata fields I ask for\n"
            "4. Choose moods via the picker\n"
            "5. Confirm\n\n"
            "<i>The archive remembers everything.</i>"
        )
    else:
        text = (
            f"<b>✦ {BOT_NAME}  ·  Guide</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Explore</b>\n"
            "→ Browse by Mood — choose a feeling\n"
            "→ Search — find by title or artist\n"
            "→ Artists — browse by creator\n"
            "→ Playlists — curated collections\n\n"
            "<b>Discover</b>\n"
            "→ Random Pick — let the archive choose\n"
            "→ More like this — on any song\n\n"
            "<b>Personal</b>\n"
            "→ Favorites — songs you ♥\n"
            "→ Recently Played — your history\n\n"
            "<code>/start</code>  to open the archive."
        )

    await update.message.reply_html(text, reply_markup=main_menu_kb())


@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin — Opens the admin control panel."""
    from database.db import get_stats
    stats = await get_stats()

    text = (
        f"<b>✦ Admin Panel</b>\n"
        f"<code>{stats['songs']} songs  ·  {stats['artists']} artists</code>\n\n"
        "<i>what do you want to do?</i>"
    )
    await update.message.reply_html(text, reply_markup=admin_menu_kb())


@admin_only
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — Quick stats in chat."""
    from database.db import get_stats
    from bot.utils.captions import admin_stats
    stats = await get_stats()
    await update.message.reply_html(admin_stats(stats))


def register_command_handlers(app) -> None:
    """Register all command handlers with the Application."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats_cmd))
