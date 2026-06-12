from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, ClassVar

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl

_BASE = "https://music.youtube.com"
_ALBUM_PLAYLIST_PREFIX = "OLAK5uy_"


def _best_thumbnail(thumbnails: list[dict[str, Any]] | None) -> str:
    if not thumbnails:
        return ""
    best = max(thumbnails, key=lambda t: t.get("width") or 0)
    return best.get("url", "")


def _artist_names(artists: list[dict[str, Any]] | None) -> tuple[str, ...]:
    return tuple(a["name"] for a in artists or [] if a.get("name"))


class YouTubeMusicAdapter:
    service_id = "youtube_music"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    def __init__(self, client: Any) -> None:
        # `Any` statt `YTMusic`: Tests injizieren ein MagicMock, und der Adapter
        # nutzt ohnehin nur vier Methoden der Library.
        self._yt = client
        # ytmusicapi teilt eine requests.Session, die nicht thread-sicher ist.
        # Der Lock serialisiert alle Library-Aufrufe — bei der erwarteten Last
        # (wenige Calls pro Konvertierung) ist das billiger als Client-pro-Call.
        self._lock = asyncio.Lock()

    async def _call(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        # ytmusicapi ist synchron (requests-basiert); to_thread hält den Event-Loop
        # frei. Library-Exceptions sind undifferenziert → pauschal AdapterError,
        # die Pipeline degradiert damit pro Ziel statt die Konvertierung zu killen.
        try:
            async with self._lock:
                return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as e:
            name = getattr(fn, "__name__", "call")
            raise AdapterError("youtube_music", f"{name}: {e}") from e

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            return await self._resolve_track(parsed.id)
        if parsed.type == "album":
            return await self._resolve_album(parsed.id)
        if parsed.type == "artist":
            return await self._resolve_artist(parsed.id)
        return None

    async def _resolve_track(self, video_id: str) -> ResolvedContent | None:
        data = await self._call(self._yt.get_song, video_id) or {}
        details = data.get("videoDetails") or {}
        status = (data.get("playabilityStatus") or {}).get("status")
        if status != "OK" or not details.get("videoId") or not details.get("title"):
            return None
        length = details.get("lengthSeconds")
        vid = details["videoId"]
        return ResolvedContent(
            service=self.service_id, type=ContentType.TRACK, id=vid,
            url=f"{_BASE}/watch?v={vid}",
            title=details["title"],
            artists=(details["author"],) if details.get("author") else (),
            album=None,
            duration_ms=int(length) * 1000 if length else None,
            isrc=None, upc=None,
            artwork=_best_thumbnail((details.get("thumbnail") or {}).get("thumbnails")),
        )

    async def _resolve_album(self, album_id: str) -> ResolvedContent | None:
        # Geteilte URLs liefern Audio-Playlist-IDs (OLAK5uy_…), get_album braucht
        # Browse-IDs (MPREb_…) — Suchkandidaten der Pipeline kommen direkt als
        # Browse-ID an, beide Formen müssen funktionieren.
        browse_id = album_id
        if album_id.startswith(_ALBUM_PLAYLIST_PREFIX):
            browse_id = await self._call(self._yt.get_album_browse_id, album_id)
            if not browse_id:
                return None
        data = await self._call(self._yt.get_album, browse_id)
        if not data or not data.get("title"):
            return None
        playlist_id = data.get("audioPlaylistId")
        url = (
            f"{_BASE}/playlist?list={playlist_id}"
            if playlist_id
            else f"{_BASE}/browse/{browse_id}"
        )
        return ResolvedContent(
            service=self.service_id, type=ContentType.ALBUM, id=browse_id,
            url=url, title=data["title"],
            artists=_artist_names(data.get("artists")),
            album=None, duration_ms=None, isrc=None, upc=None,
            artwork=_best_thumbnail(data.get("thumbnails")),
        )

    async def _resolve_artist(self, channel_id: str) -> ResolvedContent | None:
        data = await self._call(self._yt.get_artist, channel_id)
        if not data or not data.get("name"):
            return None
        cid = data.get("channelId") or channel_id
        return ResolvedContent(
            service=self.service_id, type=ContentType.ARTIST, id=cid,
            url=f"{_BASE}/channel/{cid}",
            title=data["name"], artists=(data["name"],),
            album=None, duration_ms=None, isrc=None, upc=None,
            artwork=_best_thumbnail(data.get("thumbnails")),
        )

    _FILTERS: ClassVar[dict[ContentType, str]] = {
        ContentType.TRACK: "songs",
        ContentType.ALBUM: "albums",
        ContentType.ARTIST: "artists",
    }

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        # Kein ISRC/UPC bei YouTube Music — immer Freitext-Suche, die Pipeline
        # bewertet die Kandidaten anschließend per Metadaten-Scoring.
        filter_ = self._FILTERS.get(target_type)
        if filter_ is None:
            return []
        if target_type == ContentType.ARTIST or not meta.artists:
            query = meta.title
        else:
            query = f"{meta.artists[0]} {meta.title}"
        items = await self._call(self._yt.search, query, filter=filter_, limit=3) or []
        hits: list[SearchHit] = []
        # ytmusicapi behandelt limit als Richtwert, nicht als harte Grenze.
        for item in items[:3]:
            hit = self._to_hit(item, target_type)
            if hit is not None:
                hits.append(hit)
        return hits

    def _to_hit(self, item: dict[str, Any], target_type: ContentType) -> SearchHit | None:
        if target_type == ContentType.TRACK:
            vid = item.get("videoId")
            if not vid:
                return None
            return SearchHit(
                service=self.service_id, id=vid,
                url=f"{_BASE}/watch?v={vid}", confidence=0.0, match="metadata",
            )
        browse_id = item.get("browseId")
        if not browse_id:
            return None
        url = (
            f"{_BASE}/channel/{browse_id}"
            if target_type == ContentType.ARTIST
            else f"{_BASE}/browse/{browse_id}"
        )
        return SearchHit(
            service=self.service_id, id=browse_id,
            url=url, confidence=0.0, match="metadata",
        )
