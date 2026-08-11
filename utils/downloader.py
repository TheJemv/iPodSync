import io
import os
import re
import requests
import yt_dlp
from PIL import Image
from mutagen.mp4 import MP4, MP4Cover

DOWNLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "downloads", "Music")
)


def sanitize_filename(name):
    """Cleans invalid characters for FAT32 / Windows / iPod file systems."""
    return re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()


def get_apple_music_artwork(artwork_template, album_dir):
    """
    Downloads official Apple Music artwork, resizes it to 300x300 JPEG Baseline
    (compatible with iPod Classic 6.5G / Rockbox), and creates 'cover.jpg' for Windows Explorer.
    """
    if not artwork_template:
        return None

    artwork_url = artwork_template.replace("{w}", "300").replace("{h}", "300")
    if not artwork_url.endswith(".jpg") and not artwork_url.endswith(".png"):
        artwork_url = artwork_url.replace("/{w}x{h}", "/300x300bb.jpg")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(artwork_url, headers=headers, timeout=10)

        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content))

            if img.mode != "RGB":
                img = img.convert("RGB")

            img = img.resize((300, 300), Image.Resampling.LANCZOS)

            # 1. Save 'cover.jpg' in the album folder for Windows File Explorer
            cover_path = os.path.join(album_dir, "cover.jpg")
            if not os.path.exists(cover_path):
                img.save(cover_path, format="JPEG", quality=90, progressive=False)

            # 2. Return byte buffer for embedding inside the M4A container
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, progressive=False)
            return buffer.getvalue()
        else:
            return None

    except Exception as e:
        print(f"⚠️ Error processing Apple Music artwork: {e}")
        return None


def download_song_m4a(song_info):
    title = song_info.get("title", "Unknown Title")
    artist = song_info.get("artist", "Unknown Artist")
    album = song_info.get("album", "Unknown Album")
    artwork_url = song_info.get("artwork_url")

    clean_artist = sanitize_filename(artist)
    clean_album = sanitize_filename(album)
    clean_title = sanitize_filename(title)

    album_dir = os.path.join(DOWNLOAD_DIR, clean_artist, clean_album)
    os.makedirs(album_dir, exist_ok=True)

    file_path = os.path.join(album_dir, f"{clean_title}.m4a")

    if os.path.exists(file_path):
        print(f"⏩ Skipped (already exists): {clean_artist} - {clean_title}")
        return file_path

    search_query = f"ytsearch1:{artist} - {title} audio"
    print(f"🔍 Downloading M4A (MAX BITRATE 320k / 44.1kHz): {clean_artist} - {clean_title}...")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(album_dir, f"{clean_title}.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",  # Maximum quality
            }
        ],
        "postprocessor_args": [
            "-b:a", "320k", # Force 320 kbps audio bitrate
            "-ar", "44100",  # 44.1 kHz
            "-ac", "2",      # Stereo
        ],
        # Anti 403 Forbidden configuration
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "mweb", "web"]
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "retries": 10,
        "fragment_retries": 10,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])

        if os.path.exists(file_path):
            audio = MP4(file_path)

            # Write M4A metadata
            audio["\xa9nam"] = title
            audio["\xa9ART"] = artist
            audio["\xa9alb"] = album
            if song_info.get("track_number"):
                audio["trkn"] = [(int(song_info["track_number"]), 0)]

            # Fetch and embed Apple Music artwork
            artwork_data = get_apple_music_artwork(artwork_url, album_dir)
            if artwork_data:
                audio["covr"] = [
                    MP4Cover(artwork_data, imageformat=MP4Cover.FORMAT_JPEG)
                ]

            audio.save()
            print(f" COMPLETED (320k + Apple Music Artwork): {clean_title}.m4a")
            return file_path

    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Download error on '{title}': {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error on '{title}': {e}")
        return None