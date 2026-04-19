# Tidal OpenAPI v2 — verifiziert am 2026-04-19 gegen tidal-music/tidal-sdk-web
# @ 0ccc13e9ed9108dcc09c6d515acde3f58eac5767 (HEAD zum Verifizierungs-Zeitpunkt).
# (generierte OpenAPI-TS-Types, /packages/api/src/allAPI.generated.ts + auth package).
# - Base:   https://openapi.tidal.com/v2
# - Token:  POST https://auth.tidal.com/v1/oauth2/token
#           Form-Body: client_id / client_secret / grant_type=client_credentials
#           (SDK nutzt Form-Felder statt HTTP-Basic; Plan-Annahme war Basic — korrigiert.)
# - Track:  GET /tracks/{id}?countryCode=DE&include=artists,albums
#           → data.attributes.{title,isrc,duration(ISO8601),explicit}
#             data.relationships.{artists,albums}.data[] (JSON:API, included[])
# - Album:  GET /albums/{id}?countryCode=DE&include=artists,coverArt
#           → data.attributes.{title,barcodeId(=UPC),duration}
#             coverArt → Artworks-Resource (attributes.files[{href,meta.width}])
# - Artist: GET /artists/{id}?countryCode=DE → data.attributes.name
# - ISRC-Search:  GET /tracks?filter[isrc]={isrc}&countryCode=DE
#                 → data[] sind volle Track-Resources (Tracks_Multi_Resource_Data_Document)
#                 mit attributes.isrc — direkter Filter ist per OpenAPI garantiert.
# - UPC-Search:   GET /albums?filter[barcodeId]={upc}&countryCode=DE  (analog)
# - Metadata:     GET /searchResults/{query}/relationships/{tracks|albums|artists}
#                     ?countryCode=DE&include={tracks|albums|artists}
#                 {query} ist das URL-encoded Suchwort als Pfad-Segment (Spec:
#                 "Search query string used as the resource identifier"). data[]
#                 enthält nur Resource_Identifier; Full-Resources landen in included[].
#                 Kein page[limit] — API paginiert per cursor; wir slicen client-seitig.
# VERIFY: countryCode ist per Spec optional — wir senden DE defensiv, weil Availability
# regional gefiltert wird (ohne countryCode liefert die API zwar 200, aber leere Listen
# bei regional-nicht-verfügbaren Inhalten).
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, MatchType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl

# Obergrenze für Search-Hits — Tidal paginiert cursor-basiert ohne page[limit]-Param;
# wir schneiden client-seitig auf denselben Wert wie Spotify/Deezer (limit=3).
_SEARCH_LIMIT = 3

_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")


class TidalAdapter:
    service_id = "tidal"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://openapi.tidal.com/v2"
    _TOKEN = "https://auth.tidal.com/v1/oauth2/token"
    # CountryCode ist bei Tidal OpenAPI-Queries de-facto Pflicht für Availability-Filter.
    # V1: Backend-Standort DE — wird Settings-Field, wenn das Deployment regional variiert.
    _COUNTRY = "DE"

    def __init__(self, client: httpx.AsyncClient, client_id: str, client_secret: str) -> None:
        self._http = client
        self._cid = client_id
        self._csec = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_exp - 30:
            return self._token
        # Tidal-OAuth: client_id/secret werden im Form-Body gesendet (nicht als Basic-Auth),
        # gemäß offiziellem tidal-sdk-web/packages/auth.
        resp = await self._http.post(
            self._TOKEN,
            data={
                "client_id": self._cid,
                "client_secret": self._csec,
                "grant_type": "client_credentials",
            },
        )
        if resp.status_code != 200:
            raise AdapterError("tidal", f"token fetch failed: {resp.status_code}")
        body = resp.json()
        token: str = body["access_token"]
        self._token = token
        self._token_exp = time.monotonic() + int(body.get("expires_in", 3600))
        return token

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        token = await self._ensure_token()
        p: dict[str, Any] = {"countryCode": self._COUNTRY}
        if params:
            p.update(params)
        resp = await self._http.get(
            f"{self._API}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=p,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            self._token = None
            self._token_exp = 0.0
        if resp.status_code >= 400:
            raise AdapterError("tidal", f"GET {path}: {resp.status_code}")
        return resp.json()

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(
                f"/tracks/{parsed.id}", params={"include": "artists,albums"}
            )
            if not data or not data.get("data"):
                return None
            obj = data["data"]
            attrs = obj.get("attributes") or {}
            included = {(i["type"], i["id"]): i for i in data.get("included", [])}
            rels = obj.get("relationships") or {}
            artists = _join_artists(rels, included)
            album_title = _first_album_title(rels, included)
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.TRACK,
                id=obj["id"],
                # Tidal liefert keine kanonische external_url im Response;
                # tidal.com/track/{id} ist der stabile Share-Link (URL-Parser erkennt ihn).
                url=f"https://tidal.com/track/{obj['id']}",
                title=attrs.get("title", ""),
                artists=artists,
                album=album_title,
                duration_ms=_iso8601_to_ms(attrs.get("duration")),
                isrc=attrs.get("isrc"),
                upc=None,
                artwork="",
            )
        if parsed.type == "album":
            data = await self._get(
                f"/albums/{parsed.id}", params={"include": "artists,coverArt"}
            )
            if not data or not data.get("data"):
                return None
            obj = data["data"]
            attrs = obj.get("attributes") or {}
            included = {(i["type"], i["id"]): i for i in data.get("included", [])}
            rels = obj.get("relationships") or {}
            artists = _join_artists(rels, included)
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ALBUM,
                id=obj["id"],
                url=f"https://tidal.com/album/{obj['id']}",
                title=attrs.get("title", ""),
                artists=artists,
                album=None,
                duration_ms=None,
                isrc=None,
                upc=attrs.get("barcodeId"),
                artwork=_pick_cover_art(rels, included),
            )
        if parsed.type == "artist":
            data = await self._get(f"/artists/{parsed.id}")
            if not data or not data.get("data"):
                return None
            obj = data["data"]
            attrs = obj.get("attributes") or {}
            name = attrs.get("name", "")
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ARTIST,
                id=obj["id"],
                url=f"https://tidal.com/artist/{obj['id']}",
                title=name,
                artists=(name,) if name else (),
                album=None,
                duration_ms=None,
                isrc=None,
                upc=None,
                artwork="",
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        # ISRC/UPC sind global eindeutige IDs — direkter Filter liefert definitionsgemäß
        # dieselbe Aufnahme. Ohne diese IDs fällt die Suche auf Metadata-Query zurück.
        if target_type == ContentType.TRACK and meta.isrc:
            return await self._search_tracks_by_isrc(meta.isrc)
        if target_type == ContentType.ALBUM and meta.upc:
            return await self._search_albums_by_upc(meta.upc)
        if target_type == ContentType.TRACK:
            return await self._search_metadata_tracks(meta)
        if target_type == ContentType.ALBUM:
            return await self._search_metadata_albums(meta)
        if target_type == ContentType.ARTIST:
            return await self._search_metadata_artists(meta)
        return []

    async def _search_tracks_by_isrc(self, isrc: str) -> list[SearchHit]:
        # /tracks mit filter[isrc] liefert volle Track-Resources direkt in data[];
        # anders als bei /searchResults brauchen wir kein include=, um an die IDs
        # zu kommen.
        data = await self._get("/tracks", params={"filter[isrc]": isrc})
        if not data:
            return []
        return [
            SearchHit(
                service=self.service_id,
                id=item["id"],
                url=f"https://tidal.com/track/{item['id']}",
                confidence=1.0,
                match="isrc",
            )
            for item in (data.get("data") or [])[:_SEARCH_LIMIT]
        ]

    async def _search_albums_by_upc(self, upc: str) -> list[SearchHit]:
        data = await self._get("/albums", params={"filter[barcodeId]": upc})
        if not data:
            return []
        return [
            SearchHit(
                service=self.service_id,
                id=item["id"],
                url=f"https://tidal.com/album/{item['id']}",
                confidence=1.0,
                match="upc",
            )
            for item in (data.get("data") or [])[:_SEARCH_LIMIT]
        ]

    async def _search_metadata_tracks(self, meta: ResolvedContent) -> list[SearchHit]:
        query = _metadata_query(meta)
        if not query:
            return []
        data = await self._search_relationship(query, "tracks")
        return _hits_from_search(data, kind="tracks", service=self.service_id, match="metadata")

    async def _search_metadata_albums(self, meta: ResolvedContent) -> list[SearchHit]:
        query = _metadata_query(meta)
        if not query:
            return []
        data = await self._search_relationship(query, "albums")
        return _hits_from_search(data, kind="albums", service=self.service_id, match="metadata")

    async def _search_metadata_artists(self, meta: ResolvedContent) -> list[SearchHit]:
        # Artist-Resolve legt den Namen in `title` ab; ist eine Artist-Query ohne
        # Namen (theoretisch Tolerant-Pfad), leere Ergebnisliste statt Leer-Query.
        query = meta.title.strip()
        if not query:
            return []
        data = await self._search_relationship(query, "artists")
        return _hits_from_search(data, kind="artists", service=self.service_id, match="metadata")

    async def _search_relationship(
        self, query: str, kind: str
    ) -> dict[str, Any] | None:
        # Tidal-Suche hängt den Query-String als Pfad-Segment hinter /searchResults/.
        # Pfad-Encoding via quote(safe=""): auch '/' in Queries muss escaped werden,
        # sonst kollidiert es mit dem nachfolgenden /relationships/-Segment.
        path = f"/searchResults/{quote(query, safe='')}/relationships/{kind}"
        return await self._get(path, params={"include": kind})


def _metadata_query(meta: ResolvedContent) -> str:
    # "<Artist> <Title>" ist das Query-Pattern mit der empirisch höchsten Treffer-
    # Qualität auf der Tidal-Search — Artist-First bewirkt, dass Tidal-Ranking
    # Künstler-Treffer vor Covern/Remixen priorisiert.
    artist = meta.artists[0] if meta.artists else ""
    return f"{artist} {meta.title}".strip()


def _hits_from_search(
    data: dict[str, Any] | None, *, kind: str, service: str, match: MatchType
) -> list[SearchHit]:
    # /searchResults/{q}/relationships/{kind} liefert data[] als Resource-Identifier
    # (type+id) und die vollen Resources in included[]. Wir nehmen die ID-Reihenfolge
    # aus data[] als Relevance-Ranking (von Tidal vorsortiert) und bauen die URL
    # aus dem Typ (Tidal-Responses enthalten keinen external_url).
    if not data:
        return []
    # Kind "tracks" → URL-Prefix "track". JSON:API-Type-Name ist Plural, URL-Pfad Singular.
    url_prefix = kind.rstrip("s")
    refs = (data.get("data") or [])[:_SEARCH_LIMIT]
    return [
        SearchHit(
            service=service,
            id=ref["id"],
            url=f"https://tidal.com/{url_prefix}/{ref['id']}",
            # Matcher setzt den finalen Score aus Title/Artist/Duration-Vergleich;
            # der Adapter liefert hier nur unbewertete Kandidaten.
            confidence=0.0,
            match=match,
        )
        for ref in refs
    ]


def _join_artists(
    rels: dict[str, Any], included: dict[tuple[str, str], dict[str, Any]]
) -> tuple[str, ...]:
    # JSON:API: relationships.artists.data ist Liste von {type,id}-Identifiern.
    # Namen leben in included[] unter derselben (type,id)-Kombination.
    refs = (rels.get("artists") or {}).get("data") or []
    names: list[str] = []
    for ref in refs:
        key = ("artists", ref["id"])
        inc = included.get(key)
        # Silent-Drop: fehlt ein Artist im included[] (Tidal liefert partielle
        # Sideloads bei Rate-Limits / sparse-fieldsets), lieber Teilmenge
        # zurückgeben als harten Fail — Matching nutzt artists[0] + Title/ISRC.
        if inc is None:
            continue
        name = (inc.get("attributes") or {}).get("name")
        if name:
            names.append(name)
    return tuple(names)


def _first_album_title(
    rels: dict[str, Any], included: dict[tuple[str, str], dict[str, Any]]
) -> str | None:
    refs = (rels.get("albums") or {}).get("data") or []
    if not refs:
        return None
    inc = included.get(("albums", refs[0]["id"]))
    if inc is None:
        return None
    title = (inc.get("attributes") or {}).get("title")
    return title if isinstance(title, str) else None


def _pick_cover_art(
    rels: dict[str, Any], included: dict[tuple[str, str], dict[str, Any]]
) -> str:
    # Cover-Art ist eine eigene Ressource (type="artworks") mit attributes.files[].
    # Bevorzuge 640- oder 750-px-Variante (Standard-Thumbnail-Größen), sonst das
    # erste File aus der Liste — Tidal garantiert keine sortierte Reihenfolge.
    refs = (rels.get("coverArt") or {}).get("data") or []
    for ref in refs:
        inc = included.get(("artworks", ref["id"]))
        if inc is None:
            continue
        files = (inc.get("attributes") or {}).get("files") or []
        if not files:
            continue
        target = next(
            (f for f in files if (f.get("meta") or {}).get("width") in (640, 750)),
            files[0],
        )
        href = target.get("href")
        if isinstance(href, str):
            return href
    return ""


def _iso8601_to_ms(duration: str | None) -> int | None:
    # Tidal liefert Duration als ISO 8601 "PT2M58S" bzw. "PT1H02M30S".
    if not duration:
        return None
    m = _DURATION_RE.match(duration)
    if not m or not any(m.groups()):
        # "PT" allein ist spec-widrig (ISO 8601 verlangt mind. einen Designator);
        # 0ms würde der Matcher fälschlich als "Null-Sekunden-Track" werten.
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return int(total * 1000)
