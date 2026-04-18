from __future__ import annotations

from typing import Any

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


def _strip_quotes(s: str) -> str:
    # Deezer field queries use "..." as phrase delimiters; embedded quotes break the parser.
    return s.replace('"', "")


class DeezerAdapter:
    service_id = "deezer"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://api.deezer.com"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = client

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        resp = await self._http.get(f"{self._API}{path}", params=params)
        if resp.status_code >= 400:
            raise AdapterError("deezer", f"GET {path}: {resp.status_code}")
        data = resp.json()
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                # Deezer returns 200 with an error payload; code 800 means "no data"
                # (a legitimate not-found). Any other code is a real service error.
                if err.get("code") == 800:
                    return None
                raise AdapterError(
                    "deezer",
                    f"GET {path}: error {err.get('code')} {err.get('message', '')}".strip(),
                )
        return data

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(f"/track/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.TRACK, id=str(data["id"]),
                url=data["link"], title=data["title"],
                artists=(data["artist"]["name"],),
                album=data.get("album", {}).get("title"),
                duration_ms=(
                    int(data["duration"]) * 1000 if data.get("duration") is not None else None
                ),
                isrc=data.get("isrc"), upc=None,
                artwork=data.get("album", {}).get("cover_xl", ""),
            )
        if parsed.type == "album":
            data = await self._get(f"/album/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.ALBUM, id=str(data["id"]),
                url=data["link"], title=data["title"],
                artists=(data["artist"]["name"],),
                album=None, duration_ms=None,
                isrc=None, upc=data.get("upc"),
                artwork=data.get("cover_xl", ""),
            )
        if parsed.type == "artist":
            data = await self._get(f"/artist/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.ARTIST, id=str(data["id"]),
                url=data["link"], title=data["name"],
                artists=(data["name"],), album=None, duration_ms=None,
                isrc=None, upc=None, artwork=data.get("picture_xl", ""),
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            data = await self._get(f"/track/isrc:{meta.isrc}")
            if data:
                return [SearchHit(
                    service=self.service_id, id=str(data["id"]),
                    url=data["link"], confidence=1.0, match="isrc",
                )]
            return []
        if target_type == ContentType.ALBUM and meta.upc:
            data = await self._get(f"/album/upc:{meta.upc}")
            if data:
                return [SearchHit(
                    service=self.service_id, id=str(data["id"]),
                    url=data["link"], confidence=1.0, match="upc",
                )]
            return []
        title = _strip_quotes(meta.title)
        artist_clause = (
            f' artist:"{_strip_quotes(meta.artists[0])}"' if meta.artists else ""
        )
        if target_type == ContentType.TRACK:
            data = await self._get("/search/track", {"q": f'track:"{title}"{artist_clause}'})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        if target_type == ContentType.ALBUM:
            data = await self._get("/search/album", {"q": f'album:"{title}"{artist_clause}'})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        if target_type == ContentType.ARTIST:
            data = await self._get("/search/artist", {"q": title})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        return []
