import io
import os
import re
import time
import requests
import yt_dlp
from PIL import Image
from mutagen.mp4 import MP4, MP4Cover
from tqdm import tqdm

DOWNLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "downloads", "Music")
)

# Cuántos videos candidatos distintos traer de la búsqueda
SEARCH_CANDIDATES = 5

# Segundos de pausa VISIBLE entre intento y intento de la misma canción.
# (Antes esto se hacía con sleep_interval de yt-dlp, pero pausaba en silencio
# antes de CADA request interna, dando la sensación de que el script se colgó.)
CANDIDATE_DELAY_SECONDS = 4


def pause_with_message(seconds, reason):
    """Sleeps while printing a visible countdown, so it never looks frozen."""
    print(f"   ⏳ {reason} ({seconds}s)...")
    time.sleep(seconds)


def sanitize_filename(name):
    """Cleans invalid characters for FAT32 / Windows / iPod file systems."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()
    # Windows silently strips trailing dots/spaces when creating files or folders
    # (e.g. "Cia." becomes "Cia" on disk). If we don't strip them ourselves too,
    # our own path strings stop matching what Windows actually created, and
    # os.path.exists()/open() calls fail with "No such file or directory"
    # even though the folder or file is right there.
    cleaned = cleaned.rstrip(". ")
    return cleaned


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


def base_ydl_opts():
    """Options shared by every yt-dlp call (search + download)."""
    return {
        # cookies.txt exportado con "Get cookies.txt LOCALLY" (logueado en YouTube).
        # Más confiable en Windows que sacar cookies en vivo del navegador, porque
        # evita el problema de cifrado DPAPI de Chrome y los bloqueos de archivo.
        "cookiefile": os.path.abspath("cookies.txt"),
        # Descarga automáticamente el script "solver" que resuelve los challenges
        # de JS de YouTube (firma / n-challenge). Sin esto, aunque tengas Deno
        # instalado, YouTube solo entrega miniaturas/storyboards y nada de audio,
        # lo cual se ve como "Sign in to confirm you're not a bot" o formatos vacíos.
        "remote_components": "ejs:github",
        # "android" fue removido: YouTube está forzando SABR en ese cliente y
        # con frecuencia deja los formatos sin URL ("Requested format is not available").
        # "tv" normalmente no requiere PO token y es más estable ahora mismo.
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web", "mweb"]
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


def search_candidates(artist, title):
    """
    Returns a list of candidate video URLs for a song, WITHOUT downloading anything.
    This is what actually lets us fall back to a different video if the top
    result is broken/SABR-blocked, instead of retrying the same one 3 times.
    """
    search_query = f"ytsearch{SEARCH_CANDIDATES}:{artist} - {title} audio"
    opts = base_ydl_opts()
    opts["extract_flat"] = "in_playlist"  # don't resolve formats yet, just list entries

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get("entries", []) if info else []
            urls = []
            for e in entries:
                vid = e.get("id") or e.get("url")
                if vid:
                    urls.append(f"https://www.youtube.com/watch?v={vid}" if len(vid) == 11 else vid)
            return urls
    except Exception as e:
        print(f"⚠️ Search failed for '{artist} - {title}': {e}")
        return []


def _make_progress_hook():
    """
    Returns a progress_hook that drives a live tqdm progress bar
    (speed + ETA + bar) instead of printing throttled percentage lines.
    """
    state = {"bar": None}

    def hook(d):
        status = d.get("status")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)

            if state["bar"] is None:
                state["bar"] = tqdm(
                    total=total,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="   ⏬ Descargando",
                    leave=False,
                    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]",
                )

            bar = state["bar"]
            if total and bar.total != total:
                bar.total = total
            bar.n = downloaded
            bar.refresh()

        elif status == "finished":
            if state["bar"] is not None:
                state["bar"].n = state["bar"].total or state["bar"].n
                state["bar"].refresh()
                state["bar"].close()
                state["bar"] = None
            print("   🔄 Convirtiendo a M4A (320k)...")

        elif status == "error":
            if state["bar"] is not None:
                state["bar"].close()
                state["bar"] = None

    return hook


def try_download(video_url, album_dir, clean_title):
    """Attempts to download a single, specific video URL as m4a. Returns True on success."""
    opts = base_ydl_opts()
    opts.update({
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(album_dir, f"{clean_title}.%(ext)s"),
        "progress_hooks": [_make_progress_hook()],
        "noprogress": True,  # yt-dlp's own progress line is off; tqdm draws the bar instead
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ],
        "postprocessor_args": [
            "-b:a", "320k",
            "-ar", "44100",
            "-ac", "2",
        ],
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])
        return True
    except yt_dlp.utils.DownloadError as e:
        print(f"⚠️ Fallo al descargar {video_url}: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Error inesperado con {video_url}: {e}")
        return False


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

    print(f"🔍 Buscando candidatos para: {clean_artist} - {clean_title}...")
    print("   (la primera búsqueda del día puede tardar unos segundos: yt-dlp verifica el solver de JS)")
    candidates = search_candidates(artist, title)

    if not candidates:
        print(f"❌ No search results found for '{title}'.")
        return None

    for i, video_url in enumerate(candidates, start=1):
        print(
            f"⬇️ [Candidato {i}/{len(candidates)}] Downloading M4A "
            f"(MAX BITRATE 320k / 44.1kHz): {clean_artist} - {clean_title} ({video_url})..."
        )

        if try_download(video_url, album_dir, clean_title):
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
                print(f"✅ COMPLETED (320k + Apple Music Artwork): {clean_title}.m4a")
                return file_path

        # Si este candidato falló y aún quedan más por probar, pausa visible
        # antes del siguiente (en vez del sleep silencioso de antes).
        if i < len(candidates):
            pause_with_message(CANDIDATE_DELAY_SECONDS, "Esperando antes de probar el siguiente candidato")

    print(f"❌ Could not download '{title}' after trying {len(candidates)} different videos.")
    return None