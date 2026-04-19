from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, MatchType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl

logger = logging.getLogger(__name__)


def _strip_quotes(s: str) -> str:
    # Spotify field queries use "..." as phrase delimiters; embedded quotes break the parser.
    return s.replace('"', "")


class SpotifyAdapter:
    service_id = "spotify"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://api.spotify.com/v1"
    _TOKEN = "https://accounts.spotify.com/api/token"

    def __init__(self, client: httpx.AsyncClient, client_id: str, client_secret: str) -> None:
        self._http = client
        self._cid = client_id
        self._csec = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_exp - 30:
            return self._token
        basic = base64.b64encode(f"{self._cid}:{self._csec}".encode()).decode()
        resp = await self._http.post(
            self._TOKEN,
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "client_credentials"},
        )
        if resp.status_code != 200:
            raise AdapterError("spotify", f"token fetch failed: {resp.status_code}")
        body = resp.json()
        token: str = body["access_token"]
        self._token = token
        self._token_exp = time.monotonic() + int(body.get("expires_in", 3600))
        return token

    def _bad_status(self, resp: httpx.Response, context: str) -> AdapterError:
        # Spotify liefert in 4xx meist {"error":{"status":...,"message":"..."}}.
        # Body ins Server-Log, aber NICHT in die AdapterError (Frontend-sichtbar).
        logger.warning(
            "spotify %s failed: %d %s",
            context,
            resp.status_code,
            resp.text[:500],
            extra={"service": "spotify", "status_code": resp.status_code},
        )
        return AdapterError("spotify", f"{context}: {resp.status_code}")

    async def _get(self, path: str) -> dict[str, Any] | None:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}{path}", headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            self._token = None
            self._token_exp = 0.0
        if resp.status_code >= 400:
            raise self._bad_status(resp, f"GET {path}")
        return resp.json()

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(f"/tracks/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.TRACK,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=tuple(a["name"] for a in data["artists"]),
                album=data["album"]["name"],
                duration_ms=data["duration_ms"],
                isrc=data.get("external_ids", {}).get("isrc"),
                upc=None,
                artwork=(data["album"].get("images") or [{"url": ""}])[0]["url"],
            )
        if parsed.type == "album":
            data = await self._get(f"/albums/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ALBUM,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=tuple(a["name"] for a in data["artists"]),
                album=None,
                duration_ms=None,
                isrc=None,
                upc=data.get("external_ids", {}).get("upc"),
                artwork=(data.get("images") or [{"url": ""}])[0]["url"],
            )
        if parsed.type == "artist":
            data = await self._get(f"/artists/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ARTIST,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=(data["name"],),
                album=None,
                duration_ms=None,
                isrc=None,
                upc=None,
                artwork=(data.get("images") or [{"url": ""}])[0]["url"],
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            return await self._search_tracks(f"isrc:{meta.isrc}", match="isrc")
        if target_type == ContentType.ALBUM and meta.upc:
            return await self._search_albums(f"upc:{meta.upc}", match="upc")
        title = _strip_quotes(meta.title)
        artist_clause = (
            f' artist:"{_strip_quotes(meta.artists[0])}"' if meta.artists else ""
        )
        if target_type == ContentType.TRACK:
            return await self._search_tracks(f'track:"{title}"{artist_clause}', match="metadata")
        if target_type == ContentType.ALBUM:
            return await self._search_albums(f'album:"{title}"{artist_clause}', match="metadata")
        if target_type == ContentType.ARTIST:
            # ResolvedContent for an artist stores the name in `title` (see resolve()).
            return await self._search_artists(f'artist:"{title}"')
        return []

    async def _search_tracks(self, q: str, match: MatchType) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "track", "limit": 3},
        )
        if resp.status_code >= 400:
            raise self._bad_status(resp, "search tracks")
        items = resp.json().get("tracks", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id,
                id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=1.0 if match == "isrc" else 0.0,  # matcher assigns final score
                match=match,
            )
            for it in items
        ]

    async def _search_albums(self, q: str, match: MatchType) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "album", "limit": 3},
        )
        if resp.status_code >= 400:
            raise self._bad_status(resp, "search albums")
        items = resp.json().get("albums", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id, id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=1.0 if match == "upc" else 0.0,
                match=match,
            )
            for it in items
        ]

    async def _search_artists(self, q: str) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "artist", "limit": 3},
        )
        if resp.status_code >= 400:
            raise self._bad_status(resp, "search artists")
        items = resp.json().get("artists", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id, id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=0.0,
                match="metadata",
            )
            for it in items
        ]
