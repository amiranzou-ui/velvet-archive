from .db import (
    init_db, add_song, get_song, search_songs,
    get_songs_by_mood, get_songs_by_artist,
    get_random_songs, get_similar_songs,
    get_all_artists, get_all_playlists,
    get_playlist_songs, create_playlist,
    add_song_to_playlist, toggle_favorite,
    get_favorites, record_play, get_recently_played,
    get_stats, seed_example_data,
)
