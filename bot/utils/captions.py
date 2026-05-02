from typing import Optional, List, Set
"""
bot/utils/captions.py
━━━━━━━━━━━━━━━━━━━━━
Everything that gets rendered as text in the bot lives here.
Centralising captions means the visual voice is consistent —
one place to adjust typography, spacing, and emoji language.

We use Telegram's HTML parse mode throughout. Bold = <b>, italic = <i>,
monospace = <code>, etc.
"""

from config.settings import MOODS, BOT_NAME


# ── Mood lookup helper ────────────────────────────────────────────────
_MOOD_MAP: dict[str, dict] = {m["id"]: m for m in MOODS}


def mood_name(mood_id: str) -> str:
    m = _MOOD_MAP.get(mood_id)
    return f"{m['emoji']} {m['name']}" if m else mood_id


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "—"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Menu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main_menu() -> str:
    return (
        f"<b>✦ {BOT_NAME}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>underground archive  ·  emotional curation\n"
        "late night frequencies  ·  curated silence</i>\n\n"
        "Where do you want to go?"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Song Card
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def song_card(song: dict, show_stats: bool = False) -> str:
    """
    Generate the caption shown when a song is sent.
    Uses layered typography: artist in bold, title in italic,
    metadata in small monospace-style lines.
    """
    moods_str = "  ".join(mood_name(m) for m in (song.get("moods") or []))
    tags_str = "  ".join(f"#{t}" for t in (song.get("tags") or [])[:5])

    lines = [
        f"<b>{song['artist']}</b>",
        f"<i>{song['title']}</i>",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    if song.get("album"):
        year = f"  {song['year']}" if song.get("year") else ""
        lines.append(f"<code>album  ·  {song['album']}{year}</code>")

    if song.get("genre"):
        lines.append(f"<code>genre  ·  {song['genre']}</code>")

    if song.get("duration_sec"):
        lines.append(f"<code>length ·  {format_duration(song['duration_sec'])}</code>")

    if moods_str:
        lines.append(f"\n{moods_str}")

    if song.get("caption"):
        lines.append(f"\n<i>❝ {song['caption']} ❞</i>")

    if tags_str:
        lines.append(f"\n<code>{tags_str}</code>")

    if show_stats:
        lines.append(f"\n<code>▶ played {song.get('plays', 0)} times</code>")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Search Results
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_results_header(query: str, total: int, page: int, page_size: int) -> str:
    total_pages = max(1, -(-total // page_size))  # ceiling division
    if total == 0:
        return (
            f"<b>✦ Search:</b> <i>{query}</i>\n\n"
            "nothing found in the archive.\n"
            "<i>the silence is also an answer.</i>"
        )
    return (
        f"<b>✦ Search:</b> <i>{query}</i>\n"
        f"<code>{total} result{'s' if total != 1 else ''}  ·  page {page+1}/{total_pages}</code>"
    )


def song_list_item(song: dict, index: int) -> str:
    """One line in a song list."""
    return f"<b>{index}.</b>  {song['artist']}  —  <i>{song['title']}</i>"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Mood & Browse Headers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def mood_header(mood_id: str, total: int, page: int, page_size: int) -> str:
    m = _MOOD_MAP.get(mood_id, {})
    name = m.get("name", mood_id)
    emoji = m.get("emoji", "🎵")
    desc = m.get("desc", "")
    total_pages = max(1, -(-total // page_size))
    return (
        f"{emoji}  <b>{name}</b>\n"
        f"<i>{desc}</i>\n"
        f"<code>{total} track{'s' if total != 1 else ''}  ·  page {page+1}/{total_pages}</code>"
    )


def artist_header(artist: str, total: int) -> str:
    return (
        f"<b>✦ {artist}</b>\n"
        f"<code>{total} track{'s' if total != 1 else ''} in the archive</code>"
    )


def playlist_header(playlist: dict, total: int, page: int, page_size: int) -> str:
    total_pages = max(1, -(-total // page_size))
    return (
        f"{playlist.get('cover_emoji', '🎵')}  <b>{playlist['name']}</b>\n"
        f"<i>{playlist.get('description', '')}</i>\n"
        f"<code>{total} track{'s' if total != 1 else ''}  ·  page {page+1}/{total_pages}</code>"
    )


def favorites_header(total: int) -> str:
    if total == 0:
        return (
            "<b>✦ Your Favorites</b>\n\n"
            "<i>nothing saved yet.\npress ♡ on any song to keep it.</i>"
        )
    return f"<b>✦ Your Favorites</b>  <code>({total} saved)</code>"


def recently_played_header(total: int) -> str:
    return f"<b>✦ Recently Played</b>  <code>({total} tracks)</code>"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Upload Flow (Admin)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def upload_instructions() -> str:
    return (
        "<b>✦ Upload to Archive</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send me the audio file.\n"
        "<i>After upload, I'll ask for metadata.</i>\n\n"
        "<code>supported: mp3  flac  ogg  m4a  wav</code>"
    )


def upload_step(step: str, prompt: str) -> str:
    return f"<b>✦ {step}</b>\n\n{prompt}"


def upload_success(song: dict) -> str:
    return (
        "<b>✦ Added to Archive</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{song['artist']}</b>  —  <i>{song['title']}</i>\n\n"
        "<i>the archive grows.</i>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Recommendations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def recommendations_header() -> str:
    return (
        "<b>✦ You might also feel</b>\n"
        "<i>selected by the archive  ·  mood-matched</i>"
    )


def random_header() -> str:
    return (
        "<b>✦ From the Archive</b>\n"
        "<i>the archive chose this for you</i>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Admin Stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def admin_stats(stats: dict) -> str:
    top = "\n".join(
        f"  <code>{i+1}. {s['artist']} — {s['title']}  ({s['count']}▶)</code>"
        for i, s in enumerate(stats.get("top_songs", []))
    ) or "  <i>no plays yet</i>"

    return (
        "<b>✦ Archive Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>songs      {stats['songs']}</code>\n"
        f"<code>artists    {stats['artists']}</code>\n"
        f"<code>playlists  {stats['playlists']}</code>\n\n"
        f"<b>Top Played</b>\n{top}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Error Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def error_not_found() -> str:
    return "<i>✦ this track has left the archive.</i>"


def error_not_admin() -> str:
    return "<i>✦ restricted to archivists only.</i>"


def error_generic() -> str:
    return "<i>✦ something broke in the signal. try again.</i>"
