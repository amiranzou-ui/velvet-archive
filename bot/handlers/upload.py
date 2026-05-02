from typing import Optional, List, Set
"""
bot/handlers/upload.py
━━━━━━━━━━━━━━━━━━━━━━
Multi-step conversation handler for uploading songs.
Uses python-telegram-bot's ConversationHandler state machine.

FLOW:
  /upload
    → WAIT_AUDIO     (send the audio file)
    → WAIT_TITLE     (type the title, or /auto to parse from filename)
    → WAIT_ARTIST    (type the artist name)
    → WAIT_ALBUM     (optional album, /skip to skip)
    → WAIT_YEAR      (optional year, /skip to skip)
    → WAIT_CAPTION   (poetic description, /skip to skip)
    → WAIT_GENRE     (genre, /skip to skip)
    → WAIT_MOODS     (inline keyboard multi-select)
    → WAIT_COVER     (optional cover photo, /skip to skip)
    → CONFIRM        (show preview, confirm or cancel)
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from config.settings import ADMIN_IDS
from bot.keyboards import mood_picker_kb, upload_confirm_kb, main_menu_kb
from bot.utils.captions import upload_instructions, upload_step, upload_success, song_card
from bot.utils.helpers import admin_only
from bot.utils.tags import auto_generate_tags
from database.db import add_song

log = logging.getLogger("velvet.upload")

# ── Conversation States ────────────────────────────────────────────────
(
    WAIT_AUDIO, WAIT_TITLE, WAIT_ARTIST, WAIT_ALBUM,
    WAIT_YEAR, WAIT_CAPTION, WAIT_GENRE, WAIT_MOODS,
    WAIT_COVER, CONFIRM,
) = range(10)

# Context key where we store upload data during the conversation
UPLOAD_KEY = "upload_data"


def _data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Access or initialise the upload scratchpad in user context."""
    if UPLOAD_KEY not in context.user_data:
        context.user_data[UPLOAD_KEY] = {"moods": []}
    return context.user_data[UPLOAD_KEY]


def _clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(UPLOAD_KEY, None)


async def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered by /upload command."""
    if not await _is_admin(update.effective_user.id):
        await update.message.reply_html("<i>✦ restricted to archivists only.</i>")
        return ConversationHandler.END

    _clear(context)  # fresh start
    await update.message.reply_html(upload_instructions())
    return WAIT_AUDIO


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Step Handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def receive_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent an audio file — save its file_id and ask for title."""
    msg = update.message

    if msg.audio:
        file_id = msg.audio.file_id
        # Try to pre-fill title/artist from Telegram's parsed filename
        auto_title = msg.audio.title or ""
        auto_artist = msg.audio.performer or ""
        duration = msg.audio.duration
    elif msg.document and msg.document.mime_type and "audio" in msg.document.mime_type:
        file_id = msg.document.file_id
        auto_title = ""
        auto_artist = ""
        duration = None
    else:
        await msg.reply_html("<i>✦ Please send an audio file.</i>")
        return WAIT_AUDIO

    d = _data(context)
    d["file_id"] = file_id
    d["duration_sec"] = duration
    d["auto_title"] = auto_title
    d["auto_artist"] = auto_artist

    hint = f"\n<i>(detected: {auto_title})</i>" if auto_title else ""
    await msg.reply_html(
        upload_step("Title", f"What is the song title?{hint}\n\nType it below, or send <code>/auto</code> to use the detected name.")
    )
    return WAIT_TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)

    if msg.text == "/auto":
        title = d.get("auto_title") or "Unknown Title"
    else:
        title = msg.text.strip()

    if not title:
        await msg.reply_html("<i>✦ Title can't be empty.</i>")
        return WAIT_TITLE

    d["title"] = title

    hint = f"\n<i>(detected: {d['auto_artist']})</i>" if d.get("auto_artist") else ""
    await msg.reply_html(
        upload_step("Artist", f"Who is the artist?{hint}\n\nType a name, or <code>/auto</code> for detected.")
    )
    return WAIT_ARTIST


async def receive_artist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)

    if msg.text == "/auto":
        artist = d.get("auto_artist") or "Unknown Artist"
    else:
        artist = msg.text.strip()

    if not artist:
        await msg.reply_html("<i>✦ Artist name can't be empty.</i>")
        return WAIT_ARTIST

    d["artist"] = artist
    await msg.reply_html(
        upload_step("Album", "Album name?\n\nSend <code>/skip</code> to leave empty.")
    )
    return WAIT_ALBUM


async def receive_album(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)
    d["album"] = "" if msg.text.strip() == "/skip" else msg.text.strip()

    await msg.reply_html(
        upload_step("Year", "Release year?\n\nSend <code>/skip</code> to leave empty.")
    )
    return WAIT_YEAR


async def receive_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)

    if msg.text.strip() == "/skip":
        d["year"] = None
    else:
        try:
            yr = int(msg.text.strip())
            if not (1900 <= yr <= 2099):
                raise ValueError
            d["year"] = yr
        except ValueError:
            await msg.reply_html("<i>✦ Enter a valid year (e.g. 2021), or /skip.</i>")
            return WAIT_YEAR

    await msg.reply_html(
        upload_step(
            "Description",
            "Write a short poetic caption for this song.\n"
            "<i>This shows under the song card. Make it atmospheric.</i>\n\n"
            "Or <code>/skip</code>."
        )
    )
    return WAIT_CAPTION


async def receive_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)
    d["caption"] = "" if msg.text.strip() == "/skip" else msg.text.strip()

    await msg.reply_html(
        upload_step("Genre", "Genre?\n<i>e.g. Ambient, Lo-fi, Synthwave, Arabic</i>\n\nOr <code>/skip</code>.")
    )
    return WAIT_GENRE


async def receive_genre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    d = _data(context)
    d["genre"] = "" if msg.text.strip() == "/skip" else msg.text.strip()

    await msg.reply_html(
        upload_step("Moods", "Select the moods that fit this track.\nYou can pick multiple.\nPress ✓ Done when finished."),
        reply_markup=mood_picker_kb([]),
    )
    return WAIT_MOODS


async def receive_mood_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles inline mood picker during upload."""
    query = update.callback_query
    await query.answer()
    d = _data(context)
    mood_id = query.data.split("|")[1]

    if mood_id == "__cancel__":
        _clear(context)
        await query.edit_message_text(
            "<i>✦ upload cancelled.</i>",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if mood_id == "__done__":
        # Move to cover art step
        await query.edit_message_text(
            upload_step("Cover Art", "Send a cover image for this track.\n\nOr <code>/skip</code> if none."),
            parse_mode="HTML",
        )
        return WAIT_COVER

    # Toggle mood selection
    moods = d.setdefault("moods", [])
    if mood_id in moods:
        moods.remove(mood_id)
    else:
        moods.append(mood_id)

    await query.edit_message_reply_markup(reply_markup=mood_picker_kb(moods))
    return WAIT_MOODS


async def receive_cover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User sent a cover photo or /skip."""
    msg = update.message
    d = _data(context)

    if msg.text and msg.text.strip() == "/skip":
        d["cover_file_id"] = None
    elif msg.photo:
        # Use the highest resolution version
        d["cover_file_id"] = msg.photo[-1].file_id
    else:
        await msg.reply_html("<i>✦ Send a photo or /skip.</i>")
        return WAIT_COVER

    return await show_confirm(update, context)


async def show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show a preview of what will be saved and ask for confirmation."""
    msg = update.message or (update.callback_query and update.callback_query.message)
    d = _data(context)

    # Auto-generate tags based on metadata
    d["tags"] = auto_generate_tags(
        title=d.get("title", ""),
        artist=d.get("artist", ""),
        genre=d.get("genre", ""),
        year=d.get("year"),
        caption=d.get("caption", ""),
    )

    preview = song_card({
        "title":    d.get("title", ""),
        "artist":   d.get("artist", ""),
        "album":    d.get("album", ""),
        "year":     d.get("year"),
        "genre":    d.get("genre", ""),
        "caption":  d.get("caption", ""),
        "moods":    d.get("moods", []),
        "tags":     d.get("tags", []),
        "duration_sec": d.get("duration_sec"),
    })

    await msg.reply_html(
        f"<b>✦ Preview</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{preview}\n\n<i>Save this to the archive?</i>",
        reply_markup=upload_confirm_kb(),
    )
    return CONFIRM


async def confirm_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped Confirm — write to DB."""
    query = update.callback_query
    await query.answer()
    d = _data(context)

    action = query.data.split("|")[1]
    if action == "cancel":
        _clear(context)
        await query.edit_message_text("<i>✦ upload cancelled.</i>", parse_mode="HTML")
        return ConversationHandler.END

    song_id = await add_song(
        title=d["title"],
        artist=d["artist"],
        album=d.get("album", ""),
        year=d.get("year"),
        duration_sec=d.get("duration_sec"),
        file_id=d["file_id"],
        cover_file_id=d.get("cover_file_id"),
        caption=d.get("caption", ""),
        genre=d.get("genre", ""),
        uploaded_by=update.effective_user.id,
        moods=d.get("moods", []),
        tags=d.get("tags", []),
    )

    await query.edit_message_text(
        upload_success({"title": d["title"], "artist": d["artist"]}),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    log.info("Admin %d uploaded song ID %d: %s", update.effective_user.id, song_id, d["title"])
    _clear(context)
    return ConversationHandler.END


async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/cancel at any point during upload."""
    _clear(context)
    await update.message.reply_html(
        "<i>✦ upload cancelled.</i>",
        reply_markup=main_menu_kb(),
    )
    return ConversationHandler.END


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Registration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_upload_handler() -> ConversationHandler:
    """Assemble and return the full ConversationHandler for uploads."""
    return ConversationHandler(
        entry_points=[CommandHandler("upload", upload_start)],
        states={
            WAIT_AUDIO:  [MessageHandler(filters.AUDIO | filters.Document.AUDIO | filters.ALL, receive_audio)],
            WAIT_TITLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title),
                          CommandHandler("auto", receive_title)],
            WAIT_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_artist),
                          CommandHandler("auto", receive_artist)],
            WAIT_ALBUM:  [MessageHandler(filters.TEXT, receive_album),
                          CommandHandler("skip", receive_album)],
            WAIT_YEAR:   [MessageHandler(filters.TEXT, receive_year),
                          CommandHandler("skip", receive_year)],
            WAIT_CAPTION:[MessageHandler(filters.TEXT, receive_caption),
                          CommandHandler("skip", receive_caption)],
            WAIT_GENRE:  [MessageHandler(filters.TEXT, receive_genre),
                          CommandHandler("skip", receive_genre)],
            WAIT_MOODS:  [CallbackQueryHandler(receive_mood_toggle, pattern=r"^upload_mood\|")],
            WAIT_COVER:  [MessageHandler(filters.PHOTO, receive_cover),
                          CommandHandler("skip", receive_cover)],
            CONFIRM:     [CallbackQueryHandler(confirm_upload, pattern=r"^upload\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)],
        per_user=True,
        allow_reentry=True,
    )
