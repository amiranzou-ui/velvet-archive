from typing import Optional, List, Set, Dict
"""
database/db.py
━━━━━━━━━━━━━━
The entire data layer of Velvet Archive. Uses aiosqlite for non-blocking
async access so the bot never freezes while talking to the database.

SCHEMA OVERVIEW:
  songs        — the archive's core: every uploaded track
  song_moods   — many-to-many: one song can belong to multiple moods
  song_tags    — auto-generated and manual tags per song
  playlists    — named collections of songs
  playlist_songs — many-to-many: songs in playlists
  favorites    — per-user list of loved tracks
  recently_played — per-user play history (last 50)
  play_count   — global popularity counter per song
"""

import aiosqlite
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from config.settings import DATABASE_PATH

log = logging.getLogger("velvet.db")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Schema — SQL that creates every table
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    artist          TEXT    NOT NULL,
    album           TEXT,
    year            INTEGER,
    duration_sec    INTEGER,         -- track length in seconds
    file_id         TEXT    NOT NULL, -- Telegram file_id for the audio
    cover_file_id   TEXT,            -- Telegram file_id for the cover photo
    caption         TEXT,            -- poetic description
    uploaded_by     INTEGER NOT NULL, -- Telegram user_id of uploader
    uploaded_at     TEXT    NOT NULL,
    genre           TEXT,
    language        TEXT,
    bpm             INTEGER,
    is_featured     INTEGER DEFAULT 0  -- 1 = pinned to top
);

CREATE TABLE IF NOT EXISTS song_moods (
    song_id  INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    mood_id  TEXT NOT NULL,
    PRIMARY KEY (song_id, mood_id)
);

CREATE TABLE IF NOT EXISTS song_tags (
    song_id  INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    PRIMARY KEY (song_id, tag)
);

CREATE TABLE IF NOT EXISTS playlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT,
    cover_emoji TEXT    DEFAULT '🎵',
    created_by  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    is_public   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id  INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    song_id      INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    position     INTEGER DEFAULT 0,
    PRIMARY KEY (playlist_id, song_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id  INTEGER NOT NULL,
    song_id  INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    added_at TEXT    NOT NULL,
    PRIMARY KEY (user_id, song_id)
);

CREATE TABLE IF NOT EXISTS recently_played (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    song_id  INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    played_at TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS play_count (
    song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    count   INTEGER DEFAULT 0
);

-- Full-text search virtual table for fast song lookup
CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
    title, artist, album, genre,
    content=songs, content_rowid=id
);

-- Trigger: keep FTS index in sync when songs are inserted
CREATE TRIGGER IF NOT EXISTS songs_fts_insert AFTER INSERT ON songs BEGIN
    INSERT INTO songs_fts(rowid, title, artist, album, genre)
    VALUES (new.id, new.title, new.artist, new.album, new.genre);
END;

CREATE TRIGGER IF NOT EXISTS songs_fts_delete AFTER DELETE ON songs BEGIN
    INSERT INTO songs_fts(songs_fts, rowid, title, artist, album, genre)
    VALUES ('delete', old.id, old.title, old.artist, old.album, old.genre);
END;

CREATE TRIGGER IF NOT EXISTS songs_fts_update AFTER UPDATE ON songs BEGIN
    INSERT INTO songs_fts(songs_fts, rowid, title, artist, album, genre)
    VALUES ('delete', old.id, old.title, old.artist, old.album, old.genre);
    INSERT INTO songs_fts(rowid, title, artist, album, genre)
    VALUES (new.id, new.title, new.artist, new.album, new.genre);
END;
"""


async def init_db() -> None:
    """
    Run once at startup. Creates all tables if they don't exist yet.
    Safe to call multiple times (uses IF NOT EXISTS everywhere).
    """
    # Ensure the database directory exists
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row  # rows behave like dicts
        await db.executescript(SCHEMA)
        await db.commit()

    log.info("✦ Database initialised at %s", DATABASE_PATH)


def _db():
    """Return a connected aiosqlite context manager."""
    return aiosqlite.connect(DATABASE_PATH)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Song Operations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_song(
    title: str,
    artist: str,
    file_id: str,
    uploaded_by: int,
    album: str = "",
    year: Optional[int] = None,
    duration_sec: Optional[int] = None,
    cover_file_id: Optional[str] = None,
    caption: str = "",
    genre: str = "",
    language: str = "",
    bpm: Optional[int] = None,
    moods: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> int:
    """Insert a new song and return its new ID."""
    now = datetime.utcnow().isoformat()

    async with _db() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """INSERT INTO songs
               (title, artist, album, year, duration_sec, file_id,
                cover_file_id, caption, uploaded_by, uploaded_at,
                genre, language, bpm)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title, artist, album, year, duration_sec, file_id,
             cover_file_id, caption, uploaded_by, now,
             genre, language, bpm),
        )
        song_id = cur.lastrowid

        # Insert mood associations
        if moods:
            await db.executemany(
                "INSERT OR IGNORE INTO song_moods (song_id, mood_id) VALUES (?,?)",
                [(song_id, m) for m in moods],
            )

        # Insert tags
        if tags:
            await db.executemany(
                "INSERT OR IGNORE INTO song_tags (song_id, tag) VALUES (?,?)",
                [(song_id, t.lower()) for t in tags],
            )

        # Initialise play count row
        await db.execute(
            "INSERT OR IGNORE INTO play_count (song_id, count) VALUES (?,0)", (song_id,)
        )

        await db.commit()

    log.info("✦ Song added: [%d] %s – %s", song_id, artist, title)
    return song_id


async def get_song(song_id: int) -> Optional[dict]:
    """Fetch a single song with its moods and tags."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row

        row = await db.execute_fetchall(
            """SELECT s.*, COALESCE(pc.count, 0) as plays
               FROM songs s
               LEFT JOIN play_count pc ON pc.song_id = s.id
               WHERE s.id = ?""",
            (song_id,),
        )
        if not row:
            return None
        song = dict(row[0])

        moods = await db.execute_fetchall(
            "SELECT mood_id FROM song_moods WHERE song_id = ?", (song_id,)
        )
        song["moods"] = [r["mood_id"] for r in moods]

        tags = await db.execute_fetchall(
            "SELECT tag FROM song_tags WHERE song_id = ?", (song_id,)
        )
        song["tags"] = [r["tag"] for r in tags]

        return song


async def search_songs(query: str, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    """
    Fast FTS5 search. Returns (results_page, total_count).
    Falls back to LIKE search if FTS returns nothing.
    """
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size

        # Try FTS first (fastest, ranked by relevance)
        fts_rows = await db.execute_fetchall(
            """SELECT s.*, COALESCE(pc.count,0) as plays
               FROM songs s
               JOIN songs_fts fts ON fts.rowid = s.id
               LEFT JOIN play_count pc ON pc.song_id = s.id
               WHERE songs_fts MATCH ?
               ORDER BY rank
               LIMIT ? OFFSET ?""",
            (query, page_size, offset),
        )

        if fts_rows:
            total_row = await db.execute_fetchall(
                "SELECT COUNT(*) as c FROM songs_fts WHERE songs_fts MATCH ?", (query,)
            )
            total = total_row[0]["c"] if total_row else 0
            return [dict(r) for r in fts_rows], total

        # Fallback: fuzzy LIKE on title + artist
        like = f"%{query}%"
        rows = await db.execute_fetchall(
            """SELECT s.*, COALESCE(pc.count,0) as plays
               FROM songs s
               LEFT JOIN play_count pc ON pc.song_id = s.id
               WHERE s.title LIKE ? OR s.artist LIKE ? OR s.album LIKE ?
               ORDER BY s.title
               LIMIT ? OFFSET ?""",
            (like, like, like, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            """SELECT COUNT(*) as c FROM songs
               WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?""",
            (like, like, like),
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def get_songs_by_mood(mood_id: str, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    """Return paginated songs for a given mood ID."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size

        rows = await db.execute_fetchall(
            """SELECT s.*, COALESCE(pc.count,0) as plays
               FROM songs s
               JOIN song_moods sm ON sm.song_id = s.id
               LEFT JOIN play_count pc ON pc.song_id = s.id
               WHERE sm.mood_id = ?
               ORDER BY s.is_featured DESC, pc.count DESC
               LIMIT ? OFFSET ?""",
            (mood_id, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM song_moods WHERE mood_id = ?", (mood_id,)
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def get_songs_by_artist(artist: str, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    """Return all songs by a specific artist, paginated."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size
        like = f"%{artist}%"

        rows = await db.execute_fetchall(
            """SELECT s.*, COALESCE(pc.count,0) as plays
               FROM songs s
               LEFT JOIN play_count pc ON pc.song_id = s.id
               WHERE s.artist LIKE ?
               ORDER BY s.year DESC, s.title
               LIMIT ? OFFSET ?""",
            (like, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM songs WHERE artist LIKE ?", (like,)
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def get_random_songs(limit: int = 3, exclude_id: Optional[int] = None) -> List[dict]:
    """Return random songs, optionally excluding one (for 'more like this')."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        if exclude_id:
            rows = await db.execute_fetchall(
                """SELECT s.* FROM songs s
                   WHERE s.id != ?
                   ORDER BY RANDOM() LIMIT ?""",
                (exclude_id, limit),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM songs ORDER BY RANDOM() LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]


async def get_similar_songs(song_id: int, limit: int = 3) -> List[dict]:
    """
    AI-like recommendation: find songs sharing the most moods + tags.
    Scored by overlap count, then randomised among ties.
    """
    async with _db() as db:
        db.row_factory = aiosqlite.Row

        rows = await db.execute_fetchall(
            """SELECT s.*, COUNT(*) as score
               FROM songs s
               WHERE s.id != ?
               AND (
                   s.id IN (
                       SELECT song_id FROM song_moods
                       WHERE mood_id IN (SELECT mood_id FROM song_moods WHERE song_id = ?)
                   )
                   OR s.id IN (
                       SELECT song_id FROM song_tags
                       WHERE tag IN (SELECT tag FROM song_tags WHERE song_id = ?)
                   )
                   OR s.artist = (SELECT artist FROM songs WHERE id = ?)
               )
               GROUP BY s.id
               ORDER BY score DESC, RANDOM()
               LIMIT ?""",
            (song_id, song_id, song_id, song_id, limit),
        )
        return [dict(r) for r in rows]


async def get_all_artists() -> List[str]:
    """Return distinct artist names, sorted alphabetically."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT DISTINCT artist FROM songs ORDER BY artist"
        )
        return [r["artist"] for r in rows]


async def get_all_playlists(public_only: bool = True) -> List[dict]:
    """Return all playlists with their song count."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        condition = "WHERE p.is_public = 1" if public_only else ""
        rows = await db.execute_fetchall(
            f"""SELECT p.*, COUNT(ps.song_id) as song_count
                FROM playlists p
                LEFT JOIN playlist_songs ps ON ps.playlist_id = p.id
                {condition}
                GROUP BY p.id
                ORDER BY p.name""",
        )
        return [dict(r) for r in rows]


async def get_playlist_songs(playlist_id: int, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size
        rows = await db.execute_fetchall(
            """SELECT s.* FROM songs s
               JOIN playlist_songs ps ON ps.song_id = s.id
               WHERE ps.playlist_id = ?
               ORDER BY ps.position, s.title
               LIMIT ? OFFSET ?""",
            (playlist_id, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,),
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def create_playlist(name: str, description: str, emoji: str, created_by: int) -> int:
    now = datetime.utcnow().isoformat()
    async with _db() as db:
        cur = await db.execute(
            """INSERT INTO playlists (name, description, cover_emoji, created_by, created_at)
               VALUES (?,?,?,?,?)""",
            (name, description, emoji, created_by, now),
        )
        await db.commit()
        return cur.lastrowid


async def add_song_to_playlist(playlist_id: int, song_id: int) -> None:
    async with _db() as db:
        # Position = current count
        row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,),
        )
        pos = row[0]["c"] if row else 0
        await db.execute(
            "INSERT OR IGNORE INTO playlist_songs (playlist_id, song_id, position) VALUES (?,?,?)",
            (playlist_id, song_id, pos),
        )
        await db.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Favorites & History
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def toggle_favorite(user_id: int, song_id: int) -> bool:
    """Add or remove from favorites. Returns True if now a favorite."""
    async with _db() as db:
        existing = await db.execute_fetchall(
            "SELECT 1 FROM favorites WHERE user_id=? AND song_id=?",
            (user_id, song_id),
        )
        if existing:
            await db.execute(
                "DELETE FROM favorites WHERE user_id=? AND song_id=?",
                (user_id, song_id),
            )
            await db.commit()
            return False
        else:
            now = datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO favorites (user_id, song_id, added_at) VALUES (?,?,?)",
                (user_id, song_id, now),
            )
            await db.commit()
            return True


async def get_favorites(user_id: int, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size
        rows = await db.execute_fetchall(
            """SELECT s.* FROM songs s
               JOIN favorites f ON f.song_id = s.id
               WHERE f.user_id = ?
               ORDER BY f.added_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM favorites WHERE user_id=?", (user_id,)
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def record_play(user_id: int, song_id: int) -> None:
    """Log a play to history and increment global count."""
    now = datetime.utcnow().isoformat()
    async with _db() as db:
        await db.execute(
            "INSERT INTO recently_played (user_id, song_id, played_at) VALUES (?,?,?)",
            (user_id, song_id, now),
        )
        await db.execute(
            """INSERT INTO play_count (song_id, count) VALUES (?,1)
               ON CONFLICT(song_id) DO UPDATE SET count = count + 1""",
            (song_id,),
        )
        # Trim history to last 50 per user
        await db.execute(
            """DELETE FROM recently_played WHERE id NOT IN (
               SELECT id FROM recently_played
               WHERE user_id = ?
               ORDER BY played_at DESC
               LIMIT 50)
               AND user_id = ?""",
            (user_id, user_id),
        )
        await db.commit()


async def get_recently_played(user_id: int, page: int = 0, page_size: int = 5) -> tuple[List[dict], int]:
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        offset = page * page_size
        rows = await db.execute_fetchall(
            """SELECT DISTINCT s.* FROM songs s
               JOIN recently_played rp ON rp.song_id = s.id
               WHERE rp.user_id = ?
               ORDER BY rp.played_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, offset),
        )
        total_row = await db.execute_fetchall(
            "SELECT COUNT(DISTINCT song_id) as c FROM recently_played WHERE user_id=?",
            (user_id,),
        )
        total = total_row[0]["c"] if total_row else 0
        return [dict(r) for r in rows], total


async def get_stats() -> dict:
    """Admin stats overview."""
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        songs = (await db.execute_fetchall("SELECT COUNT(*) as c FROM songs"))[0]["c"]
        artists = (await db.execute_fetchall("SELECT COUNT(DISTINCT artist) as c FROM songs"))[0]["c"]
        playlists = (await db.execute_fetchall("SELECT COUNT(*) as c FROM playlists"))[0]["c"]
        top = await db.execute_fetchall(
            """SELECT s.title, s.artist, pc.count
               FROM play_count pc JOIN songs s ON s.id = pc.song_id
               ORDER BY pc.count DESC LIMIT 3"""
        )
        return {
            "songs": songs,
            "artists": artists,
            "playlists": playlists,
            "top_songs": [dict(r) for r in top],
        }


async def seed_example_data(admin_id: int) -> None:
    """
    Insert example songs so the archive isn't empty on first run.
    Uses placeholder file_ids — swap with real Telegram file_ids after uploading.
    Called only if the songs table is empty.
    """
    async with _db() as db:
        db.row_factory = aiosqlite.Row
        count = (await db.execute_fetchall("SELECT COUNT(*) as c FROM songs"))[0]["c"]
        if count > 0:
            return  # Already seeded

    songs = [
        {
            "title": "Neon Rain",
            "artist": "Corridor Echo",
            "album": "Midnight Objects",
            "year": 2021,
            "file_id": "PLACEHOLDER_FILE_ID_1",
            "caption": "Headlights in the rain. A city that never asked for you.",
            "genre": "Ambient Electronic",
            "moods": ["night_drive", "rain"],
            "tags": ["ambient", "rain", "city", "neon", "electronic"],
        },
        {
            "title": "Dust & Frequency",
            "artist": "Al-Mutanabbi St.",
            "album": "Baghdad Tapes",
            "year": 2020,
            "file_id": "PLACEHOLDER_FILE_ID_2",
            "caption": "Old frequencies in new dust. The archive remembers.",
            "genre": "Experimental",
            "moods": ["baghdad_core", "nostalgia"],
            "tags": ["arabic", "experimental", "poetry", "dust", "memory"],
        },
        {
            "title": "Sakura Static",
            "artist": "Kira Yamabuki",
            "album": "Train Window",
            "year": 2019,
            "file_id": "PLACEHOLDER_FILE_ID_3",
            "caption": "Between stations. Petals on the glass.",
            "genre": "Japanese Ambient",
            "moods": ["old_japan", "dreamy"],
            "tags": ["japan", "ambient", "soft", "train", "sakura"],
        },
        {
            "title": "Glass Towers",
            "artist": "Solitude FM",
            "album": "No Signal",
            "year": 2022,
            "file_id": "PLACEHOLDER_FILE_ID_4",
            "caption": "Forty floors up, window open, nobody calling.",
            "genre": "Lo-fi",
            "moods": ["lonely_city", "midnight_silence"],
            "tags": ["lofi", "city", "night", "alone", "silence"],
        },
        {
            "title": "Worn Cassette",
            "artist": "VHS Memory",
            "album": "1987",
            "year": 1987,
            "file_id": "PLACEHOLDER_FILE_ID_5",
            "caption": "Tape hiss is just time trying to speak.",
            "genre": "Synthwave",
            "moods": ["nostalgia", "dreamy"],
            "tags": ["synthwave", "retro", "cassette", "80s", "warm"],
        },
    ]

    for s in songs:
        await add_song(
            title=s["title"],
            artist=s["artist"],
            album=s.get("album", ""),
            year=s.get("year"),
            file_id=s["file_id"],
            caption=s.get("caption", ""),
            genre=s.get("genre", ""),
            uploaded_by=admin_id,
            moods=s.get("moods", []),
            tags=s.get("tags", []),
        )

    log.info("✦ Example songs seeded.")
