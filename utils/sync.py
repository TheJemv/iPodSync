import os
import shutil
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_DOWNLOADS = os.path.join(BASE_DIR, "downloads")


def find_ipod_mountpoint():
    """
    Searches for the mounted iPod Classic drive once.
    Checks drive letters on Windows (e.g., E:\, F:\, G:\)
    or /media/ /mnt/ directories on Linux / Raspberry Pi.
    """
    if sys.platform.startswith("win"):
        import string

        for letter in string.ascii_uppercase[2:]:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                if (
                    os.path.exists(os.path.join(drive, ".rockbox"))
                    or os.path.exists(os.path.join(drive, "Music"))
                    or os.path.exists(os.path.join(drive, "Playlists"))
                ):
                    return drive
    else:
        media_dirs = ["/media", "/mnt", f"/media/{os.getenv('USER', 'pi')}"]
        for base in media_dirs:
            if os.path.exists(base):
                for drive_name in os.listdir(base):
                    full_path = os.path.join(base, drive_name)
                    if os.path.isdir(full_path):
                        if os.path.exists(
                            os.path.join(full_path, ".rockbox")
                        ) or os.path.exists(os.path.join(full_path, "Music")):
                            return full_path

    return None


def sync_to_ipod(ipod_path):
    """Incrementally syncs music and playlists to the iPod without duplicating existing files."""
    print(f"\n=======================================================")
    print(f" 🔌 IPOD CLASSIC DETECTED AT: {ipod_path}")
    print(f"=======================================================")
    print("🔄 Syncing data to iPod...")

    local_music = os.path.join(LOCAL_DOWNLOADS, "Music")
    local_playlists = os.path.join(LOCAL_DOWNLOADS, "Playlists")

    target_music = os.path.join(ipod_path, "Music")
    target_playlists = os.path.join(ipod_path, "Playlists")

    os.makedirs(target_music, exist_ok=True)
    os.makedirs(target_playlists, exist_ok=True)

    copied_count = 0
    skipped_count = 0

    # 1. Copy Music Files
    if os.path.exists(local_music):
        for root, dirs, files in os.walk(local_music):
            rel_path = os.path.relpath(root, local_music)
            dest_dir = os.path.join(target_music, rel_path)
            os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                if file == ".gitkeep":
                    continue
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dest_dir, file)

                if not os.path.exists(dst_file) or os.path.getsize(
                    src_file
                ) != os.path.getsize(dst_file):
                    print(f" 📥 Copying to iPod: {file}")
                    shutil.copy2(src_file, dst_file)
                    copied_count += 1
                else:
                    skipped_count += 1

    # 2. Copy Playlists
    if os.path.exists(local_playlists):
        for file in os.listdir(local_playlists):
            if file.endswith(".m3u"):
                src_pl = os.path.join(local_playlists, file)
                dst_pl = os.path.join(target_playlists, file)
                shutil.copy2(src_pl, dst_pl)

    print(f"\n✨ Sync completed successfully:")
    print(f"   - New files copied: {copied_count}")
    print(f"   - Existing files skipped: {skipped_count}")
    print(f"=======================================================\n")