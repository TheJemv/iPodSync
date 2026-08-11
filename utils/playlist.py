import os
import re

PLAYLIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "downloads", "Playlists")
)
BASE_DOWNLOADS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "downloads")
)


def create_m3u_playlist(playlist_name, file_paths):
    """Generates or updates a Rockbox-compatible .m3u playlist file."""
    os.makedirs(PLAYLIST_DIR, exist_ok=True)
    clean_name = re.sub(r'[\\/*?:"<>|]', "", str(playlist_name)).strip()
    playlist_path = os.path.join(PLAYLIST_DIR, f"{clean_name}.m3u")

    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for path in file_paths:
            if path and os.path.exists(path):
                rel_path = os.path.relpath(path, start=BASE_DOWNLOADS)
                # UNIX path format with forward slashes for Rockbox on iPod SD card
                formatted_path = "/" + rel_path.replace(os.sep, "/")
                f.write(f"{formatted_path}\n")

    print(f"✨ Playlist updated: Playlists/{clean_name}.m3u")


def cleanup_orphaned_playlists(active_playlist_names):
    """
    Deletes local .m3u playlist files that were renamed or removed
    from Apple Music to keep the iPod clean.
    """
    if not os.path.exists(PLAYLIST_DIR):
        return

    valid_filenames = {
        f"{re.sub(r'[\\\\/*?:\"<>|]', '', str(name)).strip()}.m3u"
        for name in active_playlist_names
    }

    for file in os.listdir(PLAYLIST_DIR):
        if file.endswith(".m3u") and file not in valid_filenames:
            old_playlist_path = os.path.join(PLAYLIST_DIR, file)
            print(f"🧹 Removing outdated/renamed playlist: {file}")
            try:
                os.remove(old_playlist_path)
            except Exception as e:
                print(f"⚠️ Could not delete {file}: {e}")