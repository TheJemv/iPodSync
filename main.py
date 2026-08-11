import os
import sys
from dotenv import load_dotenv
from utils.api import get_library_songs, get_playlists, get_playlist_tracks
from utils.downloader import download_song_m4a
from utils.playlist import create_m3u_playlist, cleanup_orphaned_playlists
from utils.sync import find_ipod_mountpoint, sync_to_ipod

load_dotenv()

AUTO_MODE = os.getenv("AUTO_MODE", "false").lower() in ("true", "1", "yes")


def process_playlist(pl_name, tracks):
    """Downloads and integrates playlist tracks into M4A 320k + .m3u"""
    print(f"\n📂 Processing Playlist: '{pl_name}' ({len(tracks)} songs)")
    downloaded_files = []

    for idx, track in enumerate(tracks, 1):
        print(f"[{idx}/{len(tracks)}]", end=" ")
        file_path = download_song_m4a(track)
        if file_path:
            downloaded_files.append(file_path)

    if downloaded_files:
        create_m3u_playlist(pl_name, downloaded_files)


def download_everything():
    """Downloads the entire library and all user playlists."""
    user_playlists = get_playlists()

    # 1. Gather active names to clean up orphaned .m3u playlists
    active_names = ["Library - Favorites"] + [pl["name"] for pl in user_playlists]
    cleanup_orphaned_playlists(active_names)

    # 2. Process General Library
    print("\n🚀 [1/2] Processing General Library / Favorite Songs...")
    library_songs = get_library_songs()
    if library_songs:
        process_playlist("Library - Favorites", library_songs)

    # 3. Process Playlists
    print("\n🚀 [2/2] Processing ALL User Playlists...")
    for pl in user_playlists:
        tracks = get_playlist_tracks(pl["id"])
        if tracks:
            process_playlist(pl["name"], tracks)


def main():
    print("=" * 65)
    print(" 🚀 APPLE MUSIC -> ROCKBOX (M4A 320k / AAC)")
    print("=" * 65)

    print("\n🔍 Connecting to Apple Music and fetching data...")
    user_playlists = get_playlists()

    if AUTO_MODE:
        print("\n⚡ AUTOMATIC MODE ACTIVATED (`AUTO_MODE=true` in .env)")
        print("Starting full download of library and playlists...")
        download_everything()
    else:
        # Interactive Mode
        print("\n" + "=" * 65)
        print(" SELECT WHAT YOU WANT TO DOWNLOAD/SYNC:")
        print("=" * 65)
        print(" [0] 🌟 Download ALL playlists and complete Library")
        print(" [B] 🎵 Download General Library / Favorite Songs only")
        print("-" * 65)

        for idx, pl in enumerate(user_playlists, 1):
            print(f" [{idx}] 📁 {pl['name']}")

        print("=" * 65)

        option = input("\n👉 Enter your choice (0, B, or playlist number): ").strip()

        if option == "0":
            download_everything()

        elif option.upper() == "B":
            print("\n🚀 Processing General Library only...")
            library_songs = get_library_songs()
            if library_songs:
                process_playlist("Library - Favorites", library_songs)

        elif option.isdigit():
            num = int(option)
            if 1 <= num <= len(user_playlists):
                selected_pl = user_playlists[num - 1]
                tracks = get_playlist_tracks(selected_pl["id"])
                if tracks:
                    process_playlist(selected_pl["name"], tracks)
            else:
                print("❌ Playlist number out of range.")
                sys.exit(1)
        else:
            print("❌ Invalid option. Canceling...")
            sys.exit(1)

    # Final Step: Check if iPod is connected to trigger sync
    ipod_dir = find_ipod_mountpoint()
    if ipod_dir:
        sync_to_ipod(ipod_dir)
    else:
        print("\nℹ️ iPod not currently detected. Files are ready in /downloads.")

    print("\n" + "=" * 65)
    print(" 🎉 PROCESS COMPLETED SUCCESSFULLY.")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Execution canceled by user. Goodbye!")