from typing import Optional, List, Set
"""
bot/handlers/callbacks.py
━━━━━━━━━━━━━━━━━━━━━━━━━
The central dispatcher for all InlineKeyboard button presses.

Every callback_data string follows the format: "action|param|param..."
We split on "|" and route based on the first token.

This file is intentionally large — having all routing logic in one place
makes it easy to trace exactly what happens when any button is pressed.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from config.settings import ADMIN_IDS, PAGE_SIZE, MOODS
from bot.keyboards import (
    main_menu_kb, admin_menu_kb, moods_kb,
    song_list_kb, song_view_kb, song_admin_kb,
    artists_kb, playlists_kb, recommendations_kb,
    back_kb, confirm_delete_kb, admin_playlist_picker_kb,
)
from bot.utils.captions import (
    main_menu, mood_header, search_results_header,
    song_card, song_list_item, artist_header, playlist_header,
    favorites_header, recently_played_header,
    recommendations_header, random_header, admin_stats, error_not_found,
)
from bot.utils.helpers import safe_answer, pages_info
from database.db import (
    get_song, get_songs_by_mood, search_songs, get_songs_by_artist,
    get_all_artists, get_all_playlists, get_playlist_songs,
    toggle_favorite, get_favorites, record_play, get_recently_played,
    get_random_songs, get_similar_songs, get_stats,
)

log = logging.getLogger("velvet.callbacks")


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Master router. Splits callback data and dispatches to sub-handlers.
    Every action is a separate async function below.
    """
    query = update.callback_query
    data = query.data or ""
    parts = data.split("|")
    action = parts[0]

    try:
        if action == "noop":
            await safe_answer(query)

        elif action == "menu":
            await handle_menu(query, parts, update, context)

        elif action == "mood":
            await handle_mood(query, parts, update, context)

        elif action == "song":
            await handle_song(query, parts, update, context)

        elif action == "search":
            await handle_search_page(query, parts, update, context)

        elif action == "artist":
            await handle_artist(query, parts, update, context)

        elif action == "playlist":
            await handle_playlist(query, parts, update, context)

        elif action == "fav":
            await handle_favorite(query, parts, update, context)

        elif action == "similar":
            await handle_similar(query, parts, update, context)

        elif action == "action":
            await handle_action(query, parts, update, context)

        elif action == "admin":
            await handle_admin(query, parts, update, context)

        else:
            await safe_answer(query, "unknown action")

    except Exception as e:
        log.exception("Callback error for data=%r: %s", data, e)
        await safe_answer(query, "✦ signal interrupted. try again.", alert=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Menu Navigation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_menu(query, parts, update, context):
    """menu|{target}"""
    await safe_answer(query)
    target = parts[1] if len(parts) > 1 else "main"

    if target == "main":
        await query.edit_message_text(
            main_menu(), parse_mode="HTML", reply_markup=main_menu_kb()
        )

    elif target == "moods":
        await query.edit_message_text(
            "<b>✦ Choose a Mood</b>\n<i>how do you feel tonight?</i>",
            parse_mode="HTML",
            reply_markup=moods_kb(),
        )

    elif target == "search":
        context.user_data["awaiting_search"] = True
        await query.edit_message_text(
            "<b>✦ Search</b>\n\n<i>send me a title, artist, or feeling.</i>",
            parse_mode="HTML",
            reply_markup=back_kb("menu|main"),
        )

    elif target == "artists":
        artists = await get_all_artists()
        if not artists:
            await query.edit_message_text(
                "<i>✦ no artists in the archive yet.</i>",
                parse_mode="HTML",
                reply_markup=back_kb(),
            )
            return
        await query.edit_message_text(
            "<b>✦ Artists</b>\n<i>whose world do you want to enter?</i>",
            parse_mode="HTML",
            reply_markup=artists_kb(artists),
        )

    elif target == "playlists":
        playlists = await get_all_playlists()
        if not playlists:
            await query.edit_message_text(
                "<i>✦ no playlists yet.</i>",
                parse_mode="HTML",
                reply_markup=back_kb(),
            )
            return
        await query.edit_message_text(
            "<b>✦ Playlists</b>\n<i>curated paths through the archive</i>",
            parse_mode="HTML",
            reply_markup=playlists_kb(playlists),
        )

    elif target == "favorites":
        user_id = update.effective_user.id
        songs, total = await get_favorites(user_id, page=0, page_size=PAGE_SIZE)
        pi = pages_info(total, 0, PAGE_SIZE)

        header = favorites_header(total)
        if not songs:
            await query.edit_message_text(header, parse_mode="HTML", reply_markup=back_kb())
            return

        lines = [header]
        for i, s in enumerate(songs):
            lines.append(song_list_item(s, i + 1))
        text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=song_list_kb(songs, "favorites", 0, pi["total_pages"], "menu|main"),
        )

    elif target == "recent":
        user_id = update.effective_user.id
        songs, total = await get_recently_played(user_id, page=0, page_size=PAGE_SIZE)
        pi = pages_info(total, 0, PAGE_SIZE)

        header = recently_played_header(total)
        if not songs:
            await query.edit_message_text(
                header + "\n<i>nothing played yet.</i>",
                parse_mode="HTML",
                reply_markup=back_kb(),
            )
            return

        lines = [header]
        for i, s in enumerate(songs):
            lines.append(song_list_item(s, i + 1))

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=song_list_kb(songs, "recent", 0, pi["total_pages"], "menu|main"),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Mood Browser
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_mood(query, parts, update, context):
    """mood|{mood_id}|{page}"""
    await safe_answer(query)
    mood_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    songs, total = await get_songs_by_mood(mood_id, page=page, page_size=PAGE_SIZE)
    pi = pages_info(total, page, PAGE_SIZE)

    header = mood_header(mood_id, total, page, PAGE_SIZE)
    if not songs:
        await query.edit_message_text(
            header + "\n\n<i>no tracks in this mood yet.</i>",
            parse_mode="HTML",
            reply_markup=back_kb("menu|moods"),
        )
        return

    lines = [header]
    for i, s in enumerate(songs):
        lines.append(song_list_item(s, i + 1 + page * PAGE_SIZE))

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=song_list_kb(
            songs,
            f"mood|{mood_id}",
            page,
            pi["total_pages"],
            "menu|moods",
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Song View
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_song(query, parts, update, context):
    """song|{song_id}|{context_action}|{page}"""
    await safe_answer(query)
    song_id = int(parts[1])
    context_action = "|".join(parts[2:-1]) if len(parts) > 3 else "menu|main"
    page = int(parts[-1]) if len(parts) > 2 else 0

    song = await get_song(song_id)
    if not song:
        await query.edit_message_text(error_not_found(), parse_mode="HTML", reply_markup=back_kb())
        return

    user_id = update.effective_user.id
    await record_play(user_id, song_id)

    # Check if in favorites (for button label)
    favs, _ = await get_favorites(user_id, page=0, page_size=999)
    is_fav = any(f["id"] == song_id for f in favs)

    caption = song_card(song)
    kb = song_view_kb(song_id, is_fav, context_action, page)

    # Show admin buttons if applicable
    if user_id in ADMIN_IDS:
        from telegram import InlineKeyboardMarkup
        admin_rows = song_admin_kb(song_id).inline_keyboard
        combined = kb.inline_keyboard + admin_rows
        kb = InlineKeyboardMarkup(combined)

    # If song has a cover, send it as a photo with caption
    if song.get("cover_file_id"):
        try:
            await query.message.reply_photo(
                photo=song["cover_file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
            # Also send the audio
            await query.message.reply_audio(
                audio=song["file_id"],
                title=song["title"],
                performer=song["artist"],
            )
            await query.edit_message_text(
                caption, parse_mode="HTML", reply_markup=kb
            )
            return
        except Exception:
            pass  # fall through to text-only if photo fails

    # Text + audio
    await query.edit_message_text(caption, parse_mode="HTML", reply_markup=kb)
    try:
        await query.message.reply_audio(
            audio=song["file_id"],
            title=song["title"],
            performer=song["artist"],
        )
    except Exception as e:
        log.warning("Could not send audio for song %d: %s", song_id, e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Search Pagination
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_search_page(query, parts, update, context):
    """search|{query_encoded}|{page}"""
    await safe_answer(query)

    if len(parts) < 3:
        return

    # The raw query might contain "|" — re-join everything between action and page
    raw_query = parts[1]
    page = int(parts[2]) if parts[-1].isdigit() else 0

    songs, total = await search_songs(raw_query, page=page, page_size=PAGE_SIZE)
    pi = pages_info(total, page, PAGE_SIZE)

    header = search_results_header(raw_query, total, page, PAGE_SIZE)
    lines = [header]
    for i, s in enumerate(songs):
        lines.append(song_list_item(s, i + 1 + page * PAGE_SIZE))

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=song_list_kb(
            songs,
            f"search|{raw_query}",
            page,
            pi["total_pages"],
            "menu|search",
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Artist Pages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_artist(query, parts, update, context):
    """artist|{artist_name}|{page}"""
    await safe_answer(query)
    artist = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    songs, total = await get_songs_by_artist(artist, page=page, page_size=PAGE_SIZE)
    pi = pages_info(total, page, PAGE_SIZE)

    header = artist_header(artist, total)
    lines = [header]
    for i, s in enumerate(songs):
        lines.append(song_list_item(s, i + 1 + page * PAGE_SIZE))

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=song_list_kb(
            songs,
            f"artist|{artist}",
            page,
            pi["total_pages"],
            "menu|artists",
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Playlist Pages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_playlist(query, parts, update, context):
    """playlist|{playlist_id}|{page}"""
    await safe_answer(query)
    pl_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    playlists = await get_all_playlists(public_only=False)
    pl = next((p for p in playlists if p["id"] == pl_id), None)
    if not pl:
        await query.edit_message_text(error_not_found(), parse_mode="HTML", reply_markup=back_kb())
        return

    songs, total = await get_playlist_songs(pl_id, page=page, page_size=PAGE_SIZE)
    pi = pages_info(total, page, PAGE_SIZE)

    header = playlist_header(pl, total, page, PAGE_SIZE)
    lines = [header]
    for i, s in enumerate(songs):
        lines.append(song_list_item(s, i + 1 + page * PAGE_SIZE))

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=song_list_kb(
            songs,
            f"playlist|{pl_id}",
            page,
            pi["total_pages"],
            "menu|playlists",
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Favorites Toggle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_favorite(query, parts, update, context):
    """fav|{song_id}|{context_action}|{page}"""
    song_id = int(parts[1])
    context_action = "|".join(parts[2:-1])
    page = int(parts[-1]) if parts[-1].isdigit() else 0

    user_id = update.effective_user.id
    now_fav = await toggle_favorite(user_id, song_id)

    await safe_answer(
        query,
        "♥ added to favorites" if now_fav else "♡ removed from favorites"
    )

    # Refresh the song view with updated button
    song = await get_song(song_id)
    if not song:
        return

    caption = song_card(song)
    kb = song_view_kb(song_id, now_fav, context_action, page)

    if user_id in ADMIN_IDS:
        from telegram import InlineKeyboardMarkup
        admin_rows = song_admin_kb(song_id).inline_keyboard
        kb = InlineKeyboardMarkup(kb.inline_keyboard + admin_rows)

    try:
        await query.edit_message_text(caption, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass  # message unchanged, Telegram raises if content is identical


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Similar / Recommendations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_similar(query, parts, update, context):
    """similar|{song_id}"""
    await safe_answer(query)
    song_id = int(parts[1])

    similar = await get_similar_songs(song_id, limit=4)
    if not similar:
        similar = await get_random_songs(limit=4, exclude_id=song_id)

    header = recommendations_header()
    lines = [header]
    for i, s in enumerate(similar):
        lines.append(song_list_item(s, i + 1))

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=recommendations_kb(similar, song_id),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Random & Other Actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_action(query, parts, update, context):
    """action|{action_name}"""
    await safe_answer(query)
    act = parts[1] if len(parts) > 1 else ""

    if act == "random":
        songs = await get_random_songs(limit=1)
        if not songs:
            await query.edit_message_text(
                "<i>✦ archive is empty.</i>", parse_mode="HTML", reply_markup=back_kb()
            )
            return

        song = await get_song(songs[0]["id"])
        user_id = update.effective_user.id
        await record_play(user_id, song["id"])

        favs, _ = await get_favorites(user_id, page=0, page_size=999)
        is_fav = any(f["id"] == song["id"] for f in favs)

        caption = random_header() + "\n\n" + song_card(song)
        kb = song_view_kb(song["id"], is_fav, "action|random", 0)

        await query.edit_message_text(caption, parse_mode="HTML", reply_markup=kb)

        try:
            await query.message.reply_audio(
                audio=song["file_id"],
                title=song["title"],
                performer=song["artist"],
            )
        except Exception:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Admin Actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handle_admin(query, parts, update, context):
    """admin|{sub_action}|..."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await safe_answer(query, "✦ archivists only.", alert=True)
        return

    await safe_answer(query)
    sub = parts[1] if len(parts) > 1 else ""

    if sub == "stats":
        stats = await get_stats()
        await query.edit_message_text(
            admin_stats(stats), parse_mode="HTML", reply_markup=back_kb("menu|main")
        )

    elif sub == "upload":
        await query.edit_message_text(
            "<i>✦ Send /upload to begin adding a track.</i>",
            parse_mode="HTML",
            reply_markup=back_kb("menu|main"),
        )

    elif sub == "playlists":
        playlists = await get_all_playlists(public_only=False)
        await query.edit_message_text(
            "<b>✦ Playlists</b>\n<i>send /newplaylist name|description|emoji to create one.</i>",
            parse_mode="HTML",
            reply_markup=playlists_kb(playlists) if playlists else back_kb("menu|main"),
        )

    elif sub == "delete":
        song_id = int(parts[2])
        song = await get_song(song_id)
        if not song:
            return
        await query.edit_message_text(
            f"<b>Delete?</b>\n<i>{song['artist']} — {song['title']}</i>\n\n"
            "<i>This cannot be undone.</i>",
            parse_mode="HTML",
            reply_markup=confirm_delete_kb(song_id),
        )

    elif sub == "delete_confirm":
        import aiosqlite
        from config.settings import DATABASE_PATH
        song_id = int(parts[2])
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM songs WHERE id=?", (song_id,))
            await db.commit()
        await query.edit_message_text(
            "<i>✦ track removed from the archive.</i>",
            parse_mode="HTML",
            reply_markup=back_kb(),
        )

    elif sub == "feature":
        import aiosqlite
        from config.settings import DATABASE_PATH
        song_id = int(parts[2])
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Toggle featured status
            row = await db.execute_fetchall(
                "SELECT is_featured FROM songs WHERE id=?", (song_id,)
            )
            current = row[0][0] if row else 0
            await db.execute(
                "UPDATE songs SET is_featured=? WHERE id=?", (0 if current else 1, song_id)
            )
            await db.commit()
        label = "unfeatured" if current else "featured"
        await safe_answer(query, f"✦ track {label}.", alert=False)

    elif sub == "addpl":
        song_id = int(parts[2])
        playlists = await get_all_playlists(public_only=False)
        if not playlists:
            await query.edit_message_text(
                "<i>✦ no playlists. Create one with /newplaylist.</i>",
                parse_mode="HTML",
                reply_markup=back_kb(),
            )
            return
        await query.edit_message_text(
            "<b>✦ Add to Playlist</b>\n<i>choose a playlist:</i>",
            parse_mode="HTML",
            reply_markup=admin_playlist_picker_kb(playlists, song_id),
        )

    elif sub == "addpl_confirm":
        song_id = int(parts[2])
        pl_id = int(parts[3])
        from database.db import add_song_to_playlist
        await add_song_to_playlist(pl_id, song_id)
        await query.edit_message_text(
            "<i>✦ track added to playlist.</i>",
            parse_mode="HTML",
            reply_markup=back_kb(),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Registration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def register_callback_handlers(app) -> None:
    """Register the master callback router."""
    app.add_handler(CallbackQueryHandler(route_callback))
