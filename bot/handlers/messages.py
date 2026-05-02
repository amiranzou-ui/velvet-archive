"""
bot/handlers/messages.py
━━━━━━━━━━━━━━━━━━━━━━━━
Handles regular text messages:
  - Search queries (when user typed text after pressing 🔍 Search)
  - /newplaylist admin command
  - Any unrecognised message (graceful fallback)
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters

from config.settings import PAGE_SIZE, ADMIN_IDS
from bot.keyboards import song_list_kb, main_menu_kb, back_kb
from bot.utils.captions import search_results_header, song_list_item
from bot.utils.helpers import pages_info
from database.db import search_songs, create_playlist

log = logging.getLogger("velvet.messages")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Intercepts free-text messages.
    If the user pressed Search, we treat their next message as a query.
    Otherwise, we auto-search anyway — the archive is always listening.
    """
    text = update.message.text.strip()
    if not text:
        return

    # Clear the "awaiting_search" flag if set
    context.user_data.pop("awaiting_search", None)

    songs, total = await search_songs(text, page=0, page_size=PAGE_SIZE)
    pi = pages_info(total, 0, PAGE_SIZE)

    header = search_results_header(text, total, 0, PAGE_SIZE)
    lines = [header]
    for i, s in enumerate(songs):
        lines.append(song_list_item(s, i + 1))

    await update.message.reply_html(
        "\n".join(lines),
        reply_markup=song_list_kb(
            songs,
            f"search|{text}",
            0,
            pi["total_pages"],
            "menu|search",
        ) if songs else back_kb("menu|search"),
    )


async def new_playlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /newplaylist name|description|emoji
    Admin-only command to create a new playlist.
    Example: /newplaylist Late Night Drives|Songs for 3am highways|🌃
    """
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_html("<i>✦ restricted to archivists only.</i>")
        return

    raw = " ".join(context.args) if context.args else ""
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 1 or not parts[0]:
        await update.message.reply_html(
            "<b>Usage:</b> <code>/newplaylist Name | Description | Emoji</code>\n"
            "<i>Example: /newplaylist Late Night | Songs for 3am | 🌃</i>"
        )
        return

    name = parts[0]
    desc = parts[1] if len(parts) > 1 else ""
    emoji = parts[2] if len(parts) > 2 else "🎵"

    pl_id = await create_playlist(
        name=name,
        description=desc,
        emoji=emoji,
        created_by=update.effective_user.id,
    )

    await update.message.reply_html(
        f"<b>✦ Playlist Created</b>\n"
        f"{emoji}  <b>{name}</b>\n"
        f"<code>ID: {pl_id}</code>\n\n"
        f"<i>Add songs via the admin panel → song → Add to Playlist.</i>",
        reply_markup=main_menu_kb(),
    )


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for anything unhandled."""
    # If we were waiting for a search, treat this as search input
    if context.user_data.get("awaiting_search"):
        await handle_text(update, context)
    else:
        await update.message.reply_html(
            "<i>✦ the archive doesn't understand that signal.</i>\n\n"
            "Try searching or use the menu below.",
            reply_markup=main_menu_kb(),
        )


def register_message_handlers(app) -> None:
    app.add_handler(CommandHandler("newplaylist", new_playlist_cmd))
    # Handle all non-command text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
