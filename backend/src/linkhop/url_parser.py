from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


class UnsupportedUrlError(ValueError):
    """Raised when a URL is not recognized as a supported music-service URL."""


@dataclass(frozen=True)
class ParsedUrl:
    service: str
    type: str
    id: str


_SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]+$")
_SPOTIFY_PATH = re.compile(r"^/(track|album|artist)/([A-Za-z0-9]+)/?$")
_DEEZER_PATH = re.compile(r"^(?:/[a-z]{2})?/(track|album|artist)/(\d+)/?$")
# Tidal hängt bei Share-Links Suffixe wie `/u` (User-Share) hinter die ID.
# Alles nach der numerischen ID ignorieren — die ID ist eindeutig genug.
_TIDAL_PATH = re.compile(r"^(?:/browse)?/(track|album|artist)/(\d+)(?:/.*)?$")

# YouTube Music: Track-IDs stecken im Query-Parameter (watch?v=), Alben sind
# auto-generierte Playlists (OLAK5uy_…) oder Browse-IDs (MPREb_…, von linkhop
# selbst erzeugte Ziel-URLs), Artists sind Channels (UC…).
_YTM_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YTM_ALBUM_PLAYLIST = re.compile(r"^OLAK5uy_[A-Za-z0-9_-]+$")
_YTM_CHANNEL_PATH = re.compile(r"^/channel/(UC[A-Za-z0-9_-]+)/?$")
_YTM_BROWSE_PATH = re.compile(r"^/browse/(MPREb_[A-Za-z0-9_-]+)/?$")


def parse(url: str) -> ParsedUrl:
    if not url:
        raise UnsupportedUrlError("empty URL")

    if url.startswith("spotify:"):
        parts = url.split(":")
        if (
            len(parts) == 3
            and parts[1] in {"track", "album", "artist"}
            and _SPOTIFY_ID.match(parts[2])
        ):
            return ParsedUrl("spotify", parts[1], parts[2])
        raise UnsupportedUrlError("invalid spotify URI")

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise UnsupportedUrlError("invalid URL") from e

    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedUrlError(f"unsupported scheme: {parsed.scheme}")

    host = parsed.hostname or ""
    path = parsed.path or "/"

    if host in {"open.spotify.com", "spotify.com"}:
        m = _SPOTIFY_PATH.match(path)
        if m:
            return ParsedUrl("spotify", m.group(1), m.group(2))

    elif host in {"www.deezer.com", "deezer.com"}:
        m = _DEEZER_PATH.match(path)
        if m:
            return ParsedUrl("deezer", m.group(1), m.group(2))

    elif host in {"tidal.com", "www.tidal.com", "listen.tidal.com"}:
        m = _TIDAL_PATH.match(path)
        if m:
            return ParsedUrl("tidal", m.group(1), m.group(2))

    elif host == "music.youtube.com":
        query = parse_qs(parsed.query)
        if path.rstrip("/") == "/watch":
            vid = query.get("v", [""])[0]
            if _YTM_VIDEO_ID.match(vid):
                return ParsedUrl("youtube_music", "track", vid)
        elif path.rstrip("/") == "/playlist":
            lid = query.get("list", [""])[0]
            if _YTM_ALBUM_PLAYLIST.match(lid):
                return ParsedUrl("youtube_music", "album", lid)
        else:
            m = _YTM_CHANNEL_PATH.match(path)
            if m:
                return ParsedUrl("youtube_music", "artist", m.group(1))
            m = _YTM_BROWSE_PATH.match(path)
            if m:
                return ParsedUrl("youtube_music", "album", m.group(1))

    raise UnsupportedUrlError(f"no matching service for host: {host}")
