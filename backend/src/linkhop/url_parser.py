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
_TIDAL_PATH = re.compile(r"^(?:/browse)?/(track|album|artist)/(\d+)/?$")
_YTM_ID = re.compile(r"^[A-Za-z0-9_-]+$")


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
        if path == "/watch":
            v = parse_qs(parsed.query).get("v", [None])[0]
            if v and _YTM_ID.match(v):
                return ParsedUrl("youtube_music", "track", v)
        elif path == "/playlist":
            lst = parse_qs(parsed.query).get("list", [None])[0]
            if lst and _YTM_ID.match(lst):
                return ParsedUrl("youtube_music", "album", lst)
        elif path.startswith("/channel/"):
            chan = path[len("/channel/") :].rstrip("/")
            if chan and _YTM_ID.match(chan):
                return ParsedUrl("youtube_music", "artist", chan)

    raise UnsupportedUrlError(f"no matching service for host: {host}")
