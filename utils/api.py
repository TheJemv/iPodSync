import os
import requests
from dotenv import load_dotenv

load_dotenv()

MEDIA_USER_TOKEN = os.getenv("MEDIA_USER_TOKEN")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Music-User-Token": MEDIA_USER_TOKEN,
    "Accept": "application/json",
    "Origin": "https://music.apple.com",
    "Referer": "https://music.apple.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

BASE_URL = "https://api.music.apple.com/v1/me/library"


def extract_artwork_url(attributes):
    """Extracts the official Apple Music artwork template URL."""
    artwork = attributes.get("artwork", {})
    return artwork.get("url", "")


def get_library_songs():
    """Fetches all songs saved in the user's library with their official artwork URLs."""
    url = f"{BASE_URL}/songs?limit=100"
    tracks = []

    while url:
        if not url.startswith("https://"):
            url = f"https://api.music.apple.com{url}"

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"❌ Apple Music API Error: {response.status_code}")
            break

        res_json = response.json()
        for item in res_json.get("data", []):
            attrs = item.get("attributes", {})
            tracks.append({
                "id": item.get("id"),
                "title": attrs.get("name"),
                "artist": attrs.get("artistName"),
                "album": attrs.get("albumName"),
                "track_number": attrs.get("trackNumber"),
                "artwork_url": extract_artwork_url(attrs)
            })

        url = res_json.get("next")

    return tracks


def get_playlists():
    """Fetches user playlists."""
    url = f"{BASE_URL}/playlists?limit=100"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return []

    playlists = []
    for item in response.json().get("data", []):
        attrs = item.get("attributes", {})
        playlists.append({
            "id": item.get("id"),
            "name": attrs.get("name"),
        })

    return playlists


def get_playlist_tracks(playlist_id):
    """Fetches all tracks from a specific playlist with official artwork URLs."""
    url = f"{BASE_URL}/playlists/{playlist_id}/tracks?limit=100"
    tracks = []

    while url:
        if not url.startswith("https://"):
            url = f"https://api.music.apple.com{url}"

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            break

        res_json = response.json()
        for item in res_json.get("data", []):
            attrs = item.get("attributes", {})
            tracks.append({
                "title": attrs.get("name"),
                "artist": attrs.get("artistName"),
                "album": attrs.get("albumName"),
                "track_number": attrs.get("trackNumber"),
                "artwork_url": extract_artwork_url(attrs)
            })

        url = res_json.get("next")

    return tracks