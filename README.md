# ✦ Velvet Archive
### underground music bot · emotional curation · late night frequencies

> *An archive that feels like a digital music room. Part library, part mood board, part memory.*

---

## What Is This

Velvet Archive is a Telegram bot that turns a SQLite database into a curated music archive.
Users browse by mood, search for songs, discover recommendations, and build personal favorites lists.
Admins upload tracks with full metadata through a guided multi-step flow.

The aesthetic intention: **late night rain + old internet + underground archive + poetic digital loneliness.**

---

## Features

| Feature | Description |
|---|---|
| 🌙 Mood Navigation | Browse by emotion: Night Drive, Rain, Baghdad Core, Old Japan... |
| 🔍 Fast Search | FTS5 full-text search with fuzzy fallback (rapidfuzz) |
| 👤 Artist Pages | Paginated artist discographies |
| 📂 Playlists | Admin-curated collections |
| ➕ Upload System | Admin-only multi-step guided upload with metadata |
| 🏷 Auto Tags | Auto-generated tags from genre, title, mood, year |
| 🖼 Cover Art | Optional cover photos per track |
| ♡ Favorites | Per-user saved songs |
| ⏱ History | Per-user recently played (last 50) |
| ✨ Recommendations | Mood + tag + artist overlap scoring |
| 🎲 Random Pick | Archive-curated surprise selection |
| 📊 Admin Stats | Song/artist/play counts |
| 📋 Playlist Management | Add songs, create playlists via commands |

---

## Project Structure

```
velvet_archive/
│
├── main.py                  ← Entry point. Builds and starts the bot.
│
├── config/
│   └── settings.py          ← Reads .env, exposes typed constants + mood definitions
│
├── database/
│   └── db.py                ← Full data layer: schema, all async DB operations
│
├── bot/
│   ├── handlers/
│   │   ├── commands.py      ← /start /help /admin /stats
│   │   ├── callbacks.py     ← All inline button routing (the main dispatcher)
│   │   ├── messages.py      ← Text search + /newplaylist + fallback
│   │   └── upload.py        ← Multi-step ConversationHandler for song uploads
│   │
│   ├── keyboards/
│   │   └── inline.py        ← Every InlineKeyboardMarkup the bot sends
│   │
│   └── utils/
│       ├── captions.py      ← All text/HTML rendered in the bot (typography layer)
│       ├── tags.py          ← Auto-tagger + fuzzy search scorer
│       └── helpers.py       ← Logging config, admin_only decorator, pagination
│
├── assets/
│   └── covers/              ← Cover image storage (local backup, optional)
│
├── logs/
│   └── velvet.log           ← Rotating log file (auto-created)
│
├── .env.example             ← Template for environment variables
├── requirements.txt
├── Procfile                 ← For Railway/Render deployment
└── README.md
```

---

## Setup

### 1. Get a Bot Token

1. Open Telegram, message **@BotFather**
2. Send `/newbot`, follow the prompts
3. Copy the token (looks like `123456:ABC-DEF...`)

### 2. Get Your Telegram User ID

Message **@userinfobot** on Telegram. It replies with your numeric ID.

### 3. Clone and Install

```bash
git clone https://github.com/yourname/velvet-archive
cd velvet_archive

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=your_token_from_botfather
ADMIN_IDS=your_telegram_user_id
BOT_NAME=Velvet Archive
```

### 5. Run

```bash
python main.py
```

On first run, the bot will:
- Create `database/velvet.db` automatically
- Seed 5 example songs (with placeholder file IDs — see note below)
- Start listening for messages

---

## First Upload

The example songs use placeholder `file_id` values and won't play.
To populate with real tracks:

1. Open your bot in Telegram
2. Send `/upload`
3. Follow the guided steps:
   - Send an audio file
   - Type `/auto` to use detected metadata, or enter your own
   - Fill in album, year, caption, genre (all /skippable)
   - Select moods via the inline picker
   - Optionally attach a cover photo
   - Confirm

---

## Admin Commands

| Command | Description |
|---|---|
| `/upload` | Start guided song upload |
| `/admin` | Open admin panel |
| `/stats` | Show archive statistics |
| `/newplaylist Name\|Description\|Emoji` | Create a playlist |
| `/cancel` | Cancel upload mid-flow |

Example:
```
/newplaylist Late Night Drives|Songs for empty highways at 3am|🌃
```

---

## Adding More Moods

Edit `config/settings.py`, `MOODS` list:

```python
{"id": "desert_code", "name": "Desert Code", "emoji": "🏜", "desc": "Heat, static, vast silence"},
```

Mood IDs must be unique lowercase strings with underscores. That's it.

---

## Deployment

### Railway (Recommended — Free Tier Available)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Set environment variables in Railway's dashboard:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
4. Railway uses the `Procfile` automatically → `worker: python main.py`
5. The database file is ephemeral on Railway's free tier. For persistence, add a Railway Volume or use Railway's managed PostgreSQL (requires changing the DB layer).

**Recommended: Add a persistent volume at `/app/database`.**

### Render

1. Create a new **Background Worker** service
2. Set Build Command: `pip install -r requirements.txt`
3. Set Start Command: `python main.py`
4. Add environment variables in Render dashboard
5. For persistence: use Render Disks and set `DATABASE_PATH=/data/velvet.db`

### VPS / Self-hosted

```bash
# Using systemd
sudo nano /etc/systemd/system/velvet.service

[Unit]
Description=Velvet Archive Bot
After=network.target

[Service]
WorkingDirectory=/home/youruser/velvet_archive
ExecStart=/home/youruser/velvet_archive/venv/bin/python main.py
Restart=always
User=youruser
EnvironmentFile=/home/youruser/velvet_archive/.env

[Install]
WantedBy=multi-user.target

sudo systemctl enable velvet
sudo systemctl start velvet
sudo journalctl -u velvet -f   # view logs
```

---

## Database Schema Overview

```sql
songs           — core track data (title, artist, file_id, etc.)
song_moods      — many-to-many: tracks ↔ moods
song_tags       — auto + manual tags per song
playlists       — named collections
playlist_songs  — many-to-many: playlists ↔ songs
favorites       — per-user saved songs
recently_played — per-user play history
play_count      — global play counter per song
songs_fts       — FTS5 virtual table for fast text search
```

---

## Customisation

**Change the visual voice**: edit `bot/utils/captions.py`.
All bot text is centralised there — ASCII dividers, emoji usage, caption poetry.

**Add new moods**: `config/settings.py` → `MOODS` list.

**Change page size**: `.env` → `PAGE_SIZE=8`

**Add channel posting**: set `CHANNEL_ID=@yourchannel` in `.env`.
Then in `upload.py` after `add_song()`, use `context.bot.send_audio(chat_id=CHANNEL_ID, ...)`.

---

## Philosophy

This bot was designed to feel like a *place*, not a utility.
The text uses HTML formatting, monospace code blocks for metadata,
italic for poetry, and deliberate whitespace to create visual breathing room.

Every interaction should feel like opening a music app at 3am
in a quiet room — deliberate, calm, slightly melancholic.

---

*built with python-telegram-bot · sqlite · slowness*
