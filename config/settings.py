from typing import Optional, List, Set
"""
config/settings.py
━━━━━━━━━━━━━━━━━━
Central configuration hub. Loads .env once at startup and provides
typed, named constants used across every module. Never scatter
os.getenv() calls throughout the codebase — import from here instead.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (the parent of /config)
load_dotenv(Path(__file__).parent.parent / ".env")


def _require(key: str) -> str:
    """Raise a clear error if a required env var is missing."""
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"\n\n  ✦ Missing required environment variable: {key}\n"
            f"  → Copy .env.example to .env and fill it in.\n"
        )
    return val


# ── Core ──────────────────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")
BOT_NAME: str = os.getenv("BOT_NAME", "Velvet Archive")

# ── Admin System ──────────────────────────────────────────────────────
# Parse comma-separated admin IDs into a Python set of integers
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: Set[int] = {
    int(uid.strip()) for uid in _raw_admins.split(",") if uid.strip().isdigit()
}

# ── Database ──────────────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "database/velvet.db")

# ── Channel Integration ───────────────────────────────────────────────
CHANNEL_ID: Optional[str] = os.getenv("CHANNEL_ID") or None
if CHANNEL_ID and not CHANNEL_ID.startswith("@"):
    CHANNEL_ID = f"@{CHANNEL_ID}"

# ── UX ────────────────────────────────────────────────────────────────
PAGE_SIZE: int = int(os.getenv("PAGE_SIZE", "5"))

# ── Moods ─────────────────────────────────────────────────────────────
# Each mood has: display name, emoji, and a short poetic description.
# These define the emotional DNA of the archive.
MOODS: List[dict] = [
    {"id": "night_drive",      "name": "Night Drive",      "emoji": "🌃", "desc": "Windows down, city lights, nowhere to be"},
    {"id": "rain",             "name": "Rain",             "emoji": "🌧", "desc": "Glass cold, streets reflect, time slows"},
    {"id": "nostalgia",        "name": "Nostalgia",        "emoji": "📼", "desc": "Old memories, worn cassettes, warm blur"},
    {"id": "baghdad_core",     "name": "Baghdad Core",     "emoji": "🌙", "desc": "Dust and neon, ancient and electric"},
    {"id": "old_japan",        "name": "Old Japan",        "emoji": "⛩", "desc": "Cherry blossoms over train windows"},
    {"id": "lonely_city",      "name": "Lonely City",      "emoji": "🏙", "desc": "Ten million people, perfectly alone"},
    {"id": "dreamy",           "name": "Dreamy",           "emoji": "☁️", "desc": "Soft edges, floating, half asleep"},
    {"id": "midnight_silence", "name": "Midnight Silence", "emoji": "🕯", "desc": "3am, the world stopped, just you"},
    {"id": "melancholy",       "name": "Melancholy",       "emoji": "🫧", "desc": "Beautiful sadness, bittersweet weight"},
    {"id": "euphoria",         "name": "Euphoria",         "emoji": "✨", "desc": "That feeling you can't explain"},
]

# ── Paths ─────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
COVERS_DIR = ROOT_DIR / "assets" / "covers"
LOGS_DIR = ROOT_DIR / "logs"

# Ensure directories exist at import time
COVERS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
