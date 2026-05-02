from typing import Optional, List, Set
"""
bot/utils/tags.py
━━━━━━━━━━━━━━━━━
Auto-tagging logic: given song metadata, generate a relevant
set of descriptive tags. Also houses the fuzzy-search scorer
built on rapidfuzz for approximate title/artist matching.
"""

import re
from rapidfuzz import fuzz, process


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Auto Tagger
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Genre → auto tags mapping
GENRE_TAGS: dict[str, List[str]] = {
    "ambient":              ["ambient", "atmospheric", "slow", "calm"],
    "lo-fi":                ["lofi", "chill", "warm", "bedroom"],
    "electronic":           ["electronic", "synth", "digital"],
    "synthwave":            ["synthwave", "retro", "80s", "neon"],
    "jazz":                 ["jazz", "late night", "smooth", "instrumental"],
    "classical":            ["classical", "orchestral", "piano"],
    "hip hop":              ["hiphop", "rap", "beats", "urban"],
    "r&b":                  ["rnb", "soul", "smooth", "vocal"],
    "rock":                 ["rock", "guitar", "live"],
    "post-rock":            ["postrock", "cinematic", "crescendo"],
    "experimental":         ["experimental", "abstract", "noise", "textural"],
    "shoegaze":             ["shoegaze", "dreamy", "reverb", "walls"],
    "arabic":               ["arabic", "maqam", "oud", "eastern"],
    "folk":                 ["folk", "acoustic", "storytelling"],
    "japanese ambient":     ["japan", "ambient", "minimalist", "wabi"],
    "drone":                ["drone", "minimal", "meditative"],
    "indie":                ["indie", "alternative", "underground"],
}

# Decade → era tags
DECADE_TAGS: dict[int, List[str]] = {
    1970: ["70s", "vintage", "classic"],
    1980: ["80s", "retro", "cassette"],
    1990: ["90s", "grunge era", "analog"],
    2000: ["2000s", "digital age"],
    2010: ["2010s", "modern"],
    2020: ["contemporary", "2020s"],
}


def auto_generate_tags(
    title: str = "",
    artist: str = "",
    genre: str = "",
    year: Optional[int] = None,
    caption: str = "",
) -> List[str]:
    """
    Produce a deduplicated list of lowercase tags based on metadata.
    Combines genre rules, decade heuristics, and keyword extraction.
    """
    tags: set[str] = set()

    # Genre-based tags
    genre_lower = genre.lower()
    for key, genre_tags in GENRE_TAGS.items():
        if key in genre_lower:
            tags.update(genre_tags)
    if genre_lower:
        tags.add(genre_lower.split("/")[0].strip())

    # Decade-based tags
    if year:
        decade_start = (year // 10) * 10
        if decade_start in DECADE_TAGS:
            tags.update(DECADE_TAGS[decade_start])

    # Keyword extraction from title and caption
    text = f"{title} {caption}".lower()
    keyword_rules = {
        "rain":      ["rain", "rainy", "drizzle", "storm", "wet"],
        "night":     ["night", "midnight", "dark", "3am", "late"],
        "city":      ["city", "urban", "street", "neon", "traffic"],
        "memories":  ["memory", "remember", "memories", "past", "nostalgia"],
        "sad":       ["sad", "sadness", "tears", "cry", "broken"],
        "love":      ["love", "heart", "romance", "longing", "miss"],
        "drive":     ["drive", "road", "highway", "window", "speed"],
        "ocean":     ["ocean", "sea", "wave", "shore", "water"],
        "sleep":     ["sleep", "dream", "drift", "haze", "blur"],
        "piano":     ["piano", "keys", "melody", "chord"],
    }
    for tag, keywords in keyword_rules.items():
        if any(kw in text for kw in keywords):
            tags.add(tag)

    # Sanitise: lowercase, max 20 chars, alphanumeric + spaces
    clean = set()
    for t in tags:
        t = re.sub(r"[^\w\s]", "", t).strip()[:20]
        if t:
            clean.add(t)

    return sorted(clean)[:15]  # cap at 15 tags


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fuzzy Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fuzzy_rank(query: str, songs: List[dict], limit: int = 10) -> List[dict]:
    """
    Given a list of song dicts and a query string, return the top-ranked
    songs by fuzzy score across title+artist. Score threshold: 50/100.
    Used as a post-processing layer on top of DB results for typo tolerance.
    """
    if not songs:
        return []

    # Build searchable strings: "title artist"
    choices = {i: f"{s['title']} {s['artist']}" for i, s in enumerate(songs)}

    results = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=40,
    )

    # Sort by score descending, return original dicts
    ranked = sorted(results, key=lambda x: x[1], reverse=True)
    return [songs[idx] for _, _, idx in ranked]
