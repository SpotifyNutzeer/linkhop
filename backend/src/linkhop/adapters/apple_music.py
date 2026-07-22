from __future__ import annotations

from typing import Any

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


def _artwork(item: dict[str, Any]) -> str:
    # artworkUrl100 ist die größte dokumentierte Variante; das CDN liefert
    # beliebige Größen, wenn man das Größensegment im Pfad ersetzt.
    url: str = item.get("artworkUrl100", "")
    return url.replace("100x100", "600x600")


_ENTITY = {
    ContentType.TRACK: "song",
    ContentType.ALBUM: "album",
    ContentType.ARTIST: "musicArtist",
}


def _id_and_url(item: dict[str, Any], target_type: ContentType) -> tuple[str, str]:
    if target_type == ContentType.TRACK:
        return str(item["trackId"]), item["trackViewUrl"]
    if target_type == ContentType.ALBUM:
        return str(item["collectionId"]), item["collectionViewUrl"]
    return str(item["artistId"]), item["artistLinkUrl"]


class AppleMusicAdapter:
    service_id = "apple_music"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://itunes.apple.com"

    def __init__(self, client: httpx.AsyncClient, storefront: str) -> None:
        self._http = client
        self._storefront = storefront

    async def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        resp = await self._http.get(
            f"{self._API}{path}", params={**params, "country": self._storefront}
        )
        if resp.status_code >= 400:
            raise AdapterError("apple_music", f"GET {path}: {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            # iTunes liefert bei manchen Fehlern text/html mit Status 200.
            raise AdapterError("apple_music", f"GET {path}: non-JSON response") from e
        results = data.get("results", [])
        return results if isinstance(results, list) else []

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        results = await self._get("/lookup", {"id": parsed.id})
        if not results:
            return None
        item = results[0]
        # Lookup nach ID ist typlos — falsche ID-Art ist Not-Found, kein Fehler.
        if parsed.type == "track" and item.get("wrapperType") == "track":
            return ResolvedContent(
                service=self.service_id, type=ContentType.TRACK, id=str(item["trackId"]),
                url=item["trackViewUrl"], title=item["trackName"],
                artists=(item["artistName"],),
                album=item.get("collectionName"),
                duration_ms=item.get("trackTimeMillis"),
                isrc=None, upc=None,  # iTunes-Antworten enthalten keine Industry-IDs
                artwork=_artwork(item),
            )
        if parsed.type == "album" and item.get("wrapperType") == "collection":
            return ResolvedContent(
                service=self.service_id, type=ContentType.ALBUM, id=str(item["collectionId"]),
                url=item["collectionViewUrl"], title=item["collectionName"],
                artists=(item["artistName"],),
                album=None, duration_ms=None, isrc=None, upc=None,
                artwork=_artwork(item),
            )
        if parsed.type == "artist" and item.get("wrapperType") == "artist":
            return ResolvedContent(
                service=self.service_id, type=ContentType.ARTIST, id=str(item["artistId"]),
                url=item["artistLinkUrl"], title=item["artistName"],
                artists=(item["artistName"],), album=None, duration_ms=None,
                isrc=None, upc=None, artwork=_artwork(item),
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        # Kein ISRC-Pfad: der isrc-Parameter des iTunes-Lookups liefert real immer
        # 0 Treffer (live verifiziert 2026-07). Tracks gehen direkt in die Metadaten-Suche.
        if target_type == ContentType.ALBUM and meta.upc:
            results = await self._get("/lookup", {"upc": meta.upc})
            albums = [r for r in results if r.get("wrapperType") == "collection"]
            if albums:
                id_, url = _id_and_url(albums[0], target_type)
                return [SearchHit(
                    service=self.service_id, id=id_, url=url, confidence=1.0, match="upc",
                )]
            return []
        if target_type == ContentType.ARTIST:
            # title ist bei Artists bereits der Name — artists[0] anzuhängen
            # würde ihn im Such-Term verdoppeln.
            term = meta.title
        else:
            term = f"{meta.title} {meta.artists[0]}" if meta.artists else meta.title
        results = await self._get(
            "/search",
            {"term": term, "media": "music", "entity": _ENTITY[target_type], "limit": 3},
        )
        return [
            SearchHit(
                service=self.service_id, id=id_, url=url, confidence=0.0, match="metadata",
            )
            for id_, url in (_id_and_url(item, target_type) for item in results[:3])
        ]
