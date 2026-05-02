"""
bot/keyboards/inline.py
━━━━━━━━━━━━━━━━━━━━━━━
Every InlineKeyboardMarkup the bot ever sends is built here.
Keyboard builders are pure functions: in → keyboard out.
Callback data strings follow a simple pipe-separated protocol:
  "action|param1|param2"
This makes parsing in handlers trivial: data.split("|").
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import MOODS, PAGE_SIZE


def _btn(text: str, data: str) -> InlineKeyboardButton:
    """Shorthand for creating an inline button."""
    return InlineKeyboardButton(text, callback_data=data)


def _url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Menu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🌙  Browse by Mood",     "menu|moods"),
         _btn("🔍  Search",             "menu|search")],
        [_btn("👤  Artists",            "menu|artists"),
         _btn("📂  Playlists",          "menu|playlists")],
        [_btn("✨  Random Pick",        "action|random"),
         _btn("♡  Favorites",          "menu|favorites")],
        [_btn("⏱  Recently Played",    "menu|recent")],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("➕  Upload Song",        "admin|upload"),
         _btn("📊  Stats",             "admin|stats")],
        [_btn("📋  Manage Playlists",  "admin|playlists")],
        [_btn("← Back",               "menu|main")],
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Mood Browser
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def moods_kb() -> InlineKeyboardMarkup:
    """2-column grid of all mood options."""
    rows = []
    for i in range(0, len(MOODS), 2):
        row = []
        for mood in MOODS[i:i+2]:
            label = f"{mood['emoji']}  {mood['name']}"
            row.append(_btn(label, f"mood|{mood['id']}|0"))
        rows.append(row)
    rows.append([_btn("← Back", "menu|main")])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Song List (used in search, moods, artists, etc.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def song_list_kb(
    songs: list[dict],
    context_action: str,  # e.g. "mood|rain", "search|query", "artist|Boards of Canada"
    page: int,
    total_pages: int,
    back_action: str = "menu|main",
) -> InlineKeyboardMarkup:
    """
    Display a numbered list of songs as buttons, with pagination row.
    Each song button's callback: "song|{song_id}|{context_action}|{page}"
    so we can return to the right page after viewing a song.
    """
    rows = []

    for i, song in enumerate(songs):
        label = f"{i + 1 + page * PAGE_SIZE}.  {song['artist']}  —  {song['title']}"
        # Trim long labels to fit Telegram's 64-char button limit
        if len(label) > 60:
            label = label[:57] + "…"
        rows.append([_btn(label, f"song|{song['id']}|{context_action}|{page}")])

    # Pagination row
    nav = []
    if page > 0:
        nav.append(_btn("◀", f"{context_action}|{page - 1}"))
    nav.append(_btn(f"· {page + 1} / {total_pages} ·", "noop"))
    if page < total_pages - 1:
        nav.append(_btn("▶", f"{context_action}|{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([_btn("← Back", back_action)])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Single Song View
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def song_view_kb(
    song_id: int,
    is_favorite: bool,
    context_action: str,
    page: int,
) -> InlineKeyboardMarkup:
    """
    The action bar shown below a song.
    - Play: no-op (audio was already sent)
    - Favorite toggle
    - More like this (recommendations)
    - Back to list
    """
    fav_label = "♥  Remove Fav" if is_favorite else "♡  Add to Fav"
    return InlineKeyboardMarkup([
        [
            _btn(fav_label,           f"fav|{song_id}|{context_action}|{page}"),
            _btn("∿  More like this", f"similar|{song_id}"),
        ],
        [
            _btn("🎲  Random",        "action|random"),
            _btn("← Back",           f"{context_action}|{page}"),
        ],
    ])


def song_admin_kb(song_id: int) -> InlineKeyboardMarkup:
    """Extra admin row shown only to admins below a song."""
    return InlineKeyboardMarkup([
        [
            _btn("🗑  Delete",         f"admin|delete|{song_id}"),
            _btn("⭐  Feature",        f"admin|feature|{song_id}"),
            _btn("📋  Add to Playlist",f"admin|addpl|{song_id}"),
        ],
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Artist List
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def artists_kb(artists: list[str]) -> InlineKeyboardMarkup:
    """Two-column grid of artist names."""
    rows = []
    for i in range(0, len(artists), 2):
        row = [_btn(a, f"artist|{a}|0") for a in artists[i:i+2]]
        rows.append(row)
    rows.append([_btn("← Back", "menu|main")])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Playlist List
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def playlists_kb(playlists: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for pl in playlists:
        label = f"{pl['cover_emoji']}  {pl['name']}  ({pl['song_count']})"
        rows.append([_btn(label, f"playlist|{pl['id']}|0")])
    rows.append([_btn("← Back", "menu|main")])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Recommendations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def recommendations_kb(songs: list[dict], origin_id: int) -> InlineKeyboardMarkup:
    """List of recommended songs, each openable, with a back button."""
    rows = []
    for song in songs:
        label = f"  {song['artist']}  —  {song['title']}"[:60]
        rows.append([_btn(label, f"song|{song['id']}|similar|{origin_id}")])
    rows.append([
        _btn("🎲  Different picks", f"similar|{origin_id}"),
        _btn("← Back",             "menu|main"),
    ])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Upload Flow (step-by-step mood picker)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def mood_picker_kb(selected: list[str]) -> InlineKeyboardMarkup:
    """
    Multi-select mood picker for the upload flow.
    Selected moods show a ✓ checkmark.
    """
    rows = []
    for i in range(0, len(MOODS), 2):
        row = []
        for mood in MOODS[i:i+2]:
            check = "✓ " if mood["id"] in selected else ""
            label = f"{check}{mood['emoji']} {mood['name']}"
            row.append(_btn(label, f"upload_mood|{mood['id']}"))
        rows.append(row)
    rows.append([
        _btn("✓  Done selecting moods", "upload_mood|__done__"),
        _btn("✗  Cancel upload",        "upload_mood|__cancel__"),
    ])
    return InlineKeyboardMarkup(rows)


def upload_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✓  Confirm & Save",    "upload|confirm"),
            _btn("✗  Cancel",            "upload|cancel"),
        ]
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Admin Playlist Picker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def admin_playlist_picker_kb(playlists: list[dict], song_id: int) -> InlineKeyboardMarkup:
    rows = []
    for pl in playlists:
        label = f"{pl['cover_emoji']}  {pl['name']}"
        rows.append([_btn(label, f"admin|addpl_confirm|{song_id}|{pl['id']}")])
    rows.append([_btn("← Cancel", f"song|{song_id}|menu|main|0")])
    return InlineKeyboardMarkup(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Misc
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def back_kb(action: str = "menu|main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("← Back", action)]])


def confirm_delete_kb(song_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            _btn("✓  Yes, delete",  f"admin|delete_confirm|{song_id}"),
            _btn("✗  Cancel",       f"song|{song_id}|menu|main|0"),
        ]
    ])
