# Apple-Music-Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apple Music als fünfter Service-Adapter (Tracks, Alben, Artists) via credential-freier iTunes Search/Lookup API.

**Architecture:** Neuer `AppleMusicAdapter` nach dem Deezer-Muster (httpx, kein Auth), URL-Parser-Erweiterung für `music.apple.com`/`geo.music.apple.com`/`itunes.apple.com`, Config-Flag + Storefront-Setting, Helm/Frontend/Docs-Wiring. Kein Eingriff in `matching.py` oder `pipeline.py`.

**Tech Stack:** Python 3.12 (uv), FastAPI, httpx, respx (Tests), SvelteKit-Frontend, Helm.

**Spec:** `docs/superpowers/specs/2026-07-22-apple-music-adapter-design.md`

## Global Constraints

- Service-ID ist überall exakt `apple_music`; Anzeigename `Apple Music`.
- Storefront: Setting `apple_music_storefront`, Default `"de"`; jeder iTunes-Request trägt `country=<storefront>`.
- iTunes-Antworten enthalten **kein** ISRC/UPC — `ResolvedContent.isrc`/`.upc` bleiben bei Apple-Quelle `None`. Das ist gewollt (Spec: „ISRC-Asymmetrie").
- Keine neue Python-Dependency (nur httpx).
- Backend-Kommandos laufen aus `backend/`: `uv run pytest …`, `uv run ruff check .` (line-length 100), `uv run mypy src`.
- Frontend-Kommandos laufen aus `frontend/`: `pnpm check`, `pnpm test`.
- Vor jedem Commit: Lint + betroffene Tests grün.
- Brand-Farbe Frontend: `#fa243c`.

---

### Task 1: URL-Parser für Apple-Music-Links

**Files:**
- Modify: `backend/src/linkhop/url_parser.py`
- Test: `backend/tests/test_url_parser.py`

**Interfaces:**
- Produces: `parse(url)` liefert `ParsedUrl(service="apple_music", type="track"|"album"|"artist", id="<numerisch>")` für Apple-Hosts. Task 2/3 verlassen sich auf `parsed.type`-Werte `track`/`album`/`artist` und numerische IDs als String.

- [ ] **Step 1: Failing Tests schreiben**

In `backend/tests/test_url_parser.py` in die `test_parse_valid`-Parametrize-Liste (vor der schließenden Klammer) einfügen:

```python
    # Apple Music: /<storefront>/<typ>/<slug>/<id>; Storefront und Slug optional.
    ("https://music.apple.com/de/song/nightcall/719245988", "apple_music", "track", "719245988"),
    ("https://music.apple.com/us/song/719245988", "apple_music", "track", "719245988"),
    ("https://music.apple.com/song/nightcall/719245988", "apple_music", "track", "719245988"),
    # ?i=<trackId> auf Album-URLs meint einen einzelnen Track und gewinnt.
    ("https://music.apple.com/de/album/outrun/719245563?i=719245988", "apple_music", "track", "719245988"),  # noqa: E501
    ("https://music.apple.com/de/album/outrun/719245563", "apple_music", "album", "719245563"),
    ("https://music.apple.com/de/album/719245563/", "apple_music", "album", "719245563"),
    ("https://music.apple.com/de/artist/kavinsky/358714030", "apple_music", "artist", "358714030"),  # noqa: E501
    ("https://geo.music.apple.com/de/album/outrun/719245563", "apple_music", "album", "719245563"),  # noqa: E501
    # Legacy-iTunes-Links präfixen die ID mit "id".
    ("https://itunes.apple.com/de/album/outrun/id719245563", "apple_music", "album", "719245563"),  # noqa: E501
    ("https://itunes.apple.com/de/artist/kavinsky/id358714030", "apple_music", "artist", "358714030"),  # noqa: E501
```

Und in die `test_parse_invalid_raises`-Liste:

```python
    "https://music.apple.com/de/playlist/pl.u-abc123",       # Playlists nicht unterstützt
    "https://music.apple.com/de/song/nightcall/notanumber",  # ID muss numerisch sein
    "https://music.apple.com/de/music-video/foo/123",        # Musikvideos nicht unterstützt
    "https://music.apple.com/de/album/outrun",               # Slug ohne ID
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && uv run pytest tests/test_url_parser.py -v`
Expected: die neuen `apple_music`-Fälle FAILen mit `UnsupportedUrlError` (bzw. die Invalid-Fälle sind schon grün — nur die Valid-Fälle müssen rot sein).

- [ ] **Step 3: Parser implementieren**

In `backend/src/linkhop/url_parser.py` nach dem `_YTM_BROWSE_PATH`-Regex ergänzen:

```python
# Apple Music: /<storefront>/<typ>/<slug>/<id>. Storefront (2-Buchstaben-Code)
# und Slug sind optional; Legacy-iTunes-Links präfixen die ID mit "id".
# Ein ?i=<trackId> auf Album-URLs verweist auf einen einzelnen Track.
_APPLE_PATH = re.compile(r"^(?:/[a-z]{2})?/(song|album|artist)/(?:[^/]+/)?(?:id)?(\d+)/?$")
```

Im Host-Dispatch von `parse()` (nach dem `music.youtube.com`-Block, vor dem abschließenden `raise`) einfügen:

```python
    elif host in {"music.apple.com", "geo.music.apple.com", "itunes.apple.com"}:
        m = _APPLE_PATH.match(path)
        if m:
            type_, id_ = m.group(1), m.group(2)
            if type_ == "song":
                return ParsedUrl("apple_music", "track", id_)
            if type_ == "album":
                track_id = parse_qs(parsed.query).get("i", [""])[0]
                if track_id.isdigit():
                    return ParsedUrl("apple_music", "track", track_id)
                return ParsedUrl("apple_music", "album", id_)
            return ParsedUrl("apple_music", "artist", id_)
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `cd backend && uv run pytest tests/test_url_parser.py -v`
Expected: PASS (alle, auch die bestehenden Fälle).

- [ ] **Step 5: Lint + Commit**

```bash
cd backend && uv run ruff check . && uv run mypy src
git add backend/src/linkhop/url_parser.py backend/tests/test_url_parser.py
git commit -m "feat(backend): parse apple music URLs"
```

---

### Task 2: AppleMusicAdapter — `resolve`

**Files:**
- Create: `backend/src/linkhop/adapters/apple_music.py`
- Create: `backend/tests/fixtures/apple_music_track.json`
- Create: `backend/tests/fixtures/apple_music_album.json`
- Create: `backend/tests/fixtures/apple_music_artist.json`
- Modify: `backend/src/linkhop/adapters/__init__.py`
- Test: `backend/tests/adapters/test_apple_music.py`

**Interfaces:**
- Consumes: `ParsedUrl` (Task 1), `ResolvedContent`, `AdapterCapabilities`, `AdapterError` (bestehend).
- Produces: Klasse `AppleMusicAdapter(client: httpx.AsyncClient, storefront: str)` mit `service_id = "apple_music"`, `capabilities = AdapterCapabilities(track=True, album=True, artist=True)`, `async resolve(parsed) -> ResolvedContent | None` und interner Methode `async _get(path: str, params: dict) -> list[dict]` (nutzt Task 3 mit). Task 4 importiert `AppleMusicAdapter` aus `linkhop.adapters`.

- [ ] **Step 1: Fixtures anlegen**

`backend/tests/fixtures/apple_music_track.json`:

```json
{
  "resultCount": 1,
  "results": [
    {
      "wrapperType": "track",
      "kind": "song",
      "artistId": 358714030,
      "collectionId": 719245563,
      "trackId": 719245988,
      "artistName": "Kavinsky",
      "collectionName": "OutRun",
      "trackName": "Nightcall",
      "trackViewUrl": "https://music.apple.com/de/album/nightcall/719245563?i=719245988",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/outrun/100x100bb.jpg",
      "trackTimeMillis": 258373
    }
  ]
}
```

`backend/tests/fixtures/apple_music_album.json`:

```json
{
  "resultCount": 1,
  "results": [
    {
      "wrapperType": "collection",
      "collectionType": "Album",
      "artistId": 358714030,
      "collectionId": 719245563,
      "artistName": "Kavinsky",
      "collectionName": "OutRun",
      "collectionViewUrl": "https://music.apple.com/de/album/outrun/719245563",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/outrun/100x100bb.jpg"
    }
  ]
}
```

`backend/tests/fixtures/apple_music_artist.json`:

```json
{
  "resultCount": 1,
  "results": [
    {
      "wrapperType": "artist",
      "artistType": "Artist",
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "artistLinkUrl": "https://music.apple.com/de/artist/kavinsky/358714030"
    }
  ]
}
```

- [ ] **Step 2: Failing Tests schreiben**

`backend/tests/adapters/test_apple_music.py` (neu):

```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.apple_music import AppleMusicAdapter
from linkhop.adapters.base import AdapterError
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"

LOOKUP = "https://itunes.apple.com/lookup"
SEARCH = "https://itunes.apple.com/search"

EMPTY = {"resultCount": 0, "results": []}


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield AppleMusicAdapter(client=client, storefront="de")


@respx.mock
async def test_resolve_track(adapter: AppleMusicAdapter):
    route = respx.get(LOOKUP, params={"id": "719245988"}).respond(
        json=fix("apple_music_track.json")
    )
    result = await adapter.resolve(ParsedUrl("apple_music", "track", "719245988"))
    assert result is not None
    assert result.service == "apple_music"
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.album == "OutRun"
    assert result.duration_ms == 258373
    # iTunes-Antworten enthalten keine Industry-IDs — bewusste Spec-Entscheidung.
    assert result.isrc is None
    assert result.upc is None
    # Artwork-Upscaling via CDN-Pfadersetzung.
    assert "600x600" in result.artwork
    # Konfigurierte Storefront muss als country mitgehen.
    assert route.calls.last.request.url.params["country"] == "de"


@respx.mock
async def test_resolve_album(adapter: AppleMusicAdapter):
    respx.get(LOOKUP, params={"id": "719245563"}).respond(json=fix("apple_music_album.json"))
    result = await adapter.resolve(ParsedUrl("apple_music", "album", "719245563"))
    assert result is not None
    assert result.title == "OutRun"
    assert result.url == "https://music.apple.com/de/album/outrun/719245563"


@respx.mock
async def test_resolve_artist(adapter: AppleMusicAdapter):
    respx.get(LOOKUP, params={"id": "358714030"}).respond(json=fix("apple_music_artist.json"))
    result = await adapter.resolve(ParsedUrl("apple_music", "artist", "358714030"))
    assert result is not None
    assert result.title == "Kavinsky"
    assert result.url == "https://music.apple.com/de/artist/kavinsky/358714030"
    assert result.artwork == ""


@respx.mock
async def test_resolve_not_found_returns_none(adapter: AppleMusicAdapter):
    respx.get(LOOKUP, params={"id": "0"}).respond(json=EMPTY)
    assert await adapter.resolve(ParsedUrl("apple_music", "track", "0")) is None


@respx.mock
async def test_resolve_type_mismatch_returns_none(adapter: AppleMusicAdapter):
    # Lookup nach ID ist typlos: eine Album-ID als Track angefragt ist Not-Found,
    # kein Fehler.
    respx.get(LOOKUP, params={"id": "719245563"}).respond(json=fix("apple_music_album.json"))
    assert await adapter.resolve(ParsedUrl("apple_music", "track", "719245563")) is None


@respx.mock
async def test_resolve_raises_on_http_error(adapter: AppleMusicAdapter):
    respx.get(LOOKUP, params={"id": "429429"}).respond(status_code=429)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("apple_music", "track", "429429"))


@respx.mock
async def test_resolve_raises_on_non_json_body(adapter: AppleMusicAdapter):
    # iTunes liefert bei manchen Fehlern text/html mit Status 200.
    respx.get(LOOKUP, params={"id": "1"}).respond(content=b"<html>error</html>")
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("apple_music", "track", "1"))
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && uv run pytest tests/adapters/test_apple_music.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'linkhop.adapters.apple_music'`.

- [ ] **Step 4: Adapter implementieren**

`backend/src/linkhop/adapters/apple_music.py` (neu):

```python
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
        raise NotImplementedError  # Task 3
```

In `backend/src/linkhop/adapters/__init__.py` Import und `__all__` ergänzen (alphabetisch):

```python
from linkhop.adapters.apple_music import AppleMusicAdapter
```

und in `__all__`: `"AppleMusicAdapter",` (vor `"DeezerAdapter"`).

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd backend && uv run pytest tests/adapters/test_apple_music.py -v`
Expected: PASS (7 Tests).

- [ ] **Step 6: Lint + Commit**

```bash
cd backend && uv run ruff check . && uv run mypy src
git add backend/src/linkhop/adapters/apple_music.py backend/src/linkhop/adapters/__init__.py backend/tests/adapters/test_apple_music.py backend/tests/fixtures/apple_music_track.json backend/tests/fixtures/apple_music_album.json backend/tests/fixtures/apple_music_artist.json
git commit -m "feat(backend): apple music adapter resolve via itunes lookup"
```

---

### Task 3: AppleMusicAdapter — `search`

**Files:**
- Modify: `backend/src/linkhop/adapters/apple_music.py`
- Create: `backend/tests/fixtures/apple_music_search_song.json`
- Create: `backend/tests/fixtures/apple_music_search_album.json`
- Create: `backend/tests/fixtures/apple_music_search_artist.json`
- Test: `backend/tests/adapters/test_apple_music.py`

**Interfaces:**
- Consumes: `AppleMusicAdapter._get` (Task 2).
- Produces: `async search(meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]` — ISRC-Hit `confidence=1.0, match="isrc"`, UPC-Hit `confidence=1.0, match="upc"`, sonst bis 3 × `confidence=0.0, match="metadata"`. Hit-IDs sind numerische Strings, die `resolve()` (Task 2) nachladen kann — die Pipeline verlässt sich darauf (`_score_hit`).

- [ ] **Step 1: Fixtures anlegen**

`backend/tests/fixtures/apple_music_search_song.json`:

```json
{
  "resultCount": 3,
  "results": [
    {
      "wrapperType": "track",
      "kind": "song",
      "trackId": 719245988,
      "collectionId": 719245563,
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "collectionName": "OutRun",
      "trackName": "Nightcall",
      "trackViewUrl": "https://music.apple.com/de/album/nightcall/719245563?i=719245988",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/outrun/100x100bb.jpg",
      "trackTimeMillis": 258373
    },
    {
      "wrapperType": "track",
      "kind": "song",
      "trackId": 111111111,
      "collectionId": 222222222,
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "collectionName": "Nightcall - EP",
      "trackName": "Nightcall (Live)",
      "trackViewUrl": "https://music.apple.com/de/album/nightcall-live/222222222?i=111111111",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/ep/100x100bb.jpg",
      "trackTimeMillis": 261000
    },
    {
      "wrapperType": "track",
      "kind": "song",
      "trackId": 333333333,
      "collectionId": 444444444,
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "collectionName": "Nightcall (Remixes)",
      "trackName": "Nightcall (Remix)",
      "trackViewUrl": "https://music.apple.com/de/album/nightcall-remix/444444444?i=333333333",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/rmx/100x100bb.jpg",
      "trackTimeMillis": 240000
    }
  ]
}
```

`backend/tests/fixtures/apple_music_search_album.json`:

```json
{
  "resultCount": 1,
  "results": [
    {
      "wrapperType": "collection",
      "collectionType": "Album",
      "collectionId": 719245563,
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "collectionName": "OutRun",
      "collectionViewUrl": "https://music.apple.com/de/album/outrun/719245563",
      "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/v4/outrun/100x100bb.jpg"
    }
  ]
}
```

`backend/tests/fixtures/apple_music_search_artist.json`:

```json
{
  "resultCount": 1,
  "results": [
    {
      "wrapperType": "artist",
      "artistType": "Artist",
      "artistId": 358714030,
      "artistName": "Kavinsky",
      "artistLinkUrl": "https://music.apple.com/de/artist/kavinsky/358714030"
    }
  ]
}
```

- [ ] **Step 2: Failing Tests schreiben**

In `backend/tests/adapters/test_apple_music.py` den Top-Import ergänzen:

```python
from linkhop.models.domain import ContentType, ResolvedContent
```

(einsortiert zwischen den `linkhop.adapters.*`- und `linkhop.url_parser`-Imports). Dann ans Dateiende anhängen:

```python
def _source(**overrides) -> ResolvedContent:
    defaults = dict(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="OutRun",
        duration_ms=258000, isrc=None, upc=None, artwork="",
    )
    defaults.update(overrides)
    return ResolvedContent(**defaults)


@respx.mock
async def test_search_by_isrc(adapter: AppleMusicAdapter):
    route = respx.get(LOOKUP, params={"isrc": "FR6V81200001"}).respond(
        json=fix("apple_music_track.json")
    )
    hits = await adapter.search(_source(isrc="FR6V81200001"), ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].match == "isrc"
    assert hits[0].confidence == 1.0
    assert hits[0].id == "719245988"
    assert hits[0].url == "https://music.apple.com/de/album/nightcall/719245563?i=719245988"
    assert route.calls.last.request.url.params["country"] == "de"


@respx.mock
async def test_search_isrc_miss_does_not_fall_through_to_metadata(adapter: AppleMusicAdapter):
    # Ein ISRC-Miss muss [] liefern, ohne einen zweiten /search-Request —
    # sonst bekommt die Matching-Engine unerwartete metadata-Hits.
    isrc_route = respx.get(LOOKUP, params={"isrc": "NOPE"}).respond(json=EMPTY)
    metadata_route = respx.get(SEARCH).respond(json=fix("apple_music_search_song.json"))
    hits = await adapter.search(_source(isrc="NOPE"), ContentType.TRACK)
    assert hits == []
    assert isrc_route.call_count == 1
    assert metadata_route.call_count == 0


@respx.mock
async def test_search_by_upc(adapter: AppleMusicAdapter):
    respx.get(LOOKUP, params={"upc": "3596972882128"}).respond(
        json=fix("apple_music_album.json")
    )
    source = _source(type=ContentType.ALBUM, album=None, duration_ms=None, upc="3596972882128")
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].match == "upc"
    assert hits[0].confidence == 1.0
    assert hits[0].id == "719245563"


@respx.mock
async def test_search_track_metadata_fallback(adapter: AppleMusicAdapter):
    route = respx.get(SEARCH).respond(json=fix("apple_music_search_song.json"))
    hits = await adapter.search(_source(), ContentType.TRACK)
    assert len(hits) == 3
    assert all(h.match == "metadata" and h.confidence == 0.0 for h in hits)
    params = route.calls.last.request.url.params
    assert params["term"] == "Nightcall Kavinsky"
    assert params["media"] == "music"
    assert params["entity"] == "song"
    assert params["limit"] == "3"
    assert params["country"] == "de"


@respx.mock
async def test_search_album_metadata_fallback(adapter: AppleMusicAdapter):
    route = respx.get(SEARCH).respond(json=fix("apple_music_search_album.json"))
    source = _source(type=ContentType.ALBUM, title="OutRun", album=None, duration_ms=None)
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].match == "metadata"
    assert hits[0].url == "https://music.apple.com/de/album/outrun/719245563"
    assert route.calls.last.request.url.params["entity"] == "album"


@respx.mock
async def test_search_artist_metadata_uses_title_only(adapter: AppleMusicAdapter):
    # Bei Artists ist title == Artist-Name; artists[0] anzuhängen würde den
    # Namen im Such-Term verdoppeln ("Kavinsky Kavinsky").
    route = respx.get(SEARCH).respond(json=fix("apple_music_search_artist.json"))
    source = _source(type=ContentType.ARTIST, title="Kavinsky", album=None, duration_ms=None)
    hits = await adapter.search(source, ContentType.ARTIST)
    assert len(hits) == 1
    assert hits[0].url == "https://music.apple.com/de/artist/kavinsky/358714030"
    params = route.calls.last.request.url.params
    assert params["term"] == "Kavinsky"
    assert params["entity"] == "musicArtist"


@respx.mock
async def test_search_track_without_artists_uses_title_only(adapter: AppleMusicAdapter):
    route = respx.get(SEARCH).respond(json=fix("apple_music_search_song.json"))
    hits = await adapter.search(_source(artists=()), ContentType.TRACK)
    assert hits
    assert route.calls.last.request.url.params["term"] == "Nightcall"


@respx.mock
async def test_search_raises_on_http_error(adapter: AppleMusicAdapter):
    respx.get(SEARCH).respond(status_code=500)
    with pytest.raises(AdapterError):
        await adapter.search(_source(), ContentType.TRACK)
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && uv run pytest tests/adapters/test_apple_music.py -v`
Expected: die neuen `test_search_*` FAILen mit `NotImplementedError`; die Task-2-Tests bleiben grün.

- [ ] **Step 4: `search` implementieren**

In `backend/src/linkhop/adapters/apple_music.py` auf Modulebene (nach `_artwork`) ergänzen:

```python
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
```

Die `search`-Methode (den `NotImplementedError`-Rumpf ersetzen):

```python
    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            results = await self._get("/lookup", {"isrc": meta.isrc})
            songs = [r for r in results if r.get("wrapperType") == "track"]
            if songs:
                id_, url = _id_and_url(songs[0], target_type)
                return [SearchHit(
                    service=self.service_id, id=id_, url=url, confidence=1.0, match="isrc",
                )]
            return []
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
```

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd backend && uv run pytest tests/adapters/test_apple_music.py -v`
Expected: PASS (15 Tests).

- [ ] **Step 6: Lint + Commit**

```bash
cd backend && uv run ruff check . && uv run mypy src
git add backend/src/linkhop/adapters/apple_music.py backend/tests/adapters/test_apple_music.py backend/tests/fixtures/apple_music_search_song.json backend/tests/fixtures/apple_music_search_album.json backend/tests/fixtures/apple_music_search_artist.json
git commit -m "feat(backend): apple music adapter search with isrc/upc lookup"
```

---

### Task 4: Config, Adapter-Registrierung, Services-Route

**Files:**
- Modify: `backend/src/linkhop/config.py`
- Modify: `backend/src/linkhop/deps.py`
- Modify: `backend/src/linkhop/routes/services.py`
- Test: `backend/tests/test_config.py`, `backend/tests/test_deps.py`, `backend/tests/routes/test_services.py`

**Interfaces:**
- Consumes: `AppleMusicAdapter` (Task 2/3).
- Produces: Settings-Felder `enable_apple_music: bool = True`, `apple_music_storefront: str = "de"` (Env: `LINKHOP_ENABLE_APPLE_MUSIC`, `LINKHOP_APPLE_MUSIC_STOREFRONT`); `build_adapter_map` registriert `"apple_music"`; `/api/v1/services` listet `Apple Music`.

- [ ] **Step 1: Failing Tests schreiben**

In `backend/tests/test_config.py` den bestehenden Test `test_service_enable_flags_default_true` um eine Zeile ergänzen:

```python
    assert settings.enable_apple_music is True
```

und darunter einen neuen Test anlegen:

```python
def test_apple_music_storefront_default_and_override(monkeypatch):
    assert Settings().apple_music_storefront == "de"
    monkeypatch.setenv("LINKHOP_APPLE_MUSIC_STOREFRONT", "us")
    assert Settings().apple_music_storefront == "us"
```

In `backend/tests/test_deps.py`: Import um `AppleMusicAdapter` erweitern:

```python
from linkhop.adapters import (
    AppleMusicAdapter,
    DeezerAdapter,
    SpotifyAdapter,
    TidalAdapter,
    YouTubeMusicAdapter,
)
```

Im bestehenden Test `test_all_flags_off_returns_empty` ergänzen (sonst schlägt er fehl, sobald apple_music per Default registriert):

```python
    monkeypatch.setenv("LINKHOP_ENABLE_APPLE_MUSIC", "false")
```

Neue Tests anhängen:

```python
async def test_apple_music_registered_by_default():
    # Auth-frei: kein Credential-Check, Default-Settings reichen.
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert isinstance(m["apple_music"], AppleMusicAdapter)


async def test_apple_music_disabled(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_APPLE_MUSIC", "false")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "apple_music" not in m


async def test_apple_music_gets_configured_storefront(monkeypatch):
    # Privates Attribut statt Verhaltens-Test: das Storefront-Verhalten selbst
    # ist in test_apple_music.py abgedeckt; hier geht es nur ums Durchreichen.
    monkeypatch.setenv("LINKHOP_APPLE_MUSIC_STOREFRONT", "us")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        adapter = m["apple_music"]
        assert isinstance(adapter, AppleMusicAdapter)
        assert adapter._storefront == "us"
```

In `backend/tests/routes/test_services.py` anhängen:

```python
def test_services_includes_apple_music():
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    body = resp.json()
    am = next(s for s in body["services"] if s["id"] == "apple_music")
    assert am["name"] == "Apple Music"
    assert set(am["capabilities"]) == {"track", "album", "artist"}


def test_services_excludes_disabled_apple_music(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_APPLE_MUSIC", "false")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    ids = {s["id"] for s in resp.json()["services"]}
    assert "apple_music" not in ids
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && uv run pytest tests/test_config.py tests/test_deps.py tests/routes/test_services.py -v`
Expected: FAIL — `Settings` hat kein `enable_apple_music`-Feld (AttributeError), `apple_music` fehlt in der Map bzw. Services-Liste.

- [ ] **Step 3: Implementieren**

`backend/src/linkhop/config.py` — nach `enable_youtube_music: bool = True`:

```python
    enable_apple_music: bool = True
```

Nach dem `tidal_client_secret`-Block:

```python
    # Apple-Music-Storefront (Länderkatalog) für iTunes-Lookups und erzeugte Links.
    apple_music_storefront: str = "de"
```

`backend/src/linkhop/deps.py` — Import erweitern:

```python
from linkhop.adapters import (
    AppleMusicAdapter,
    DeezerAdapter,
    ServiceAdapter,
    SpotifyAdapter,
    TidalAdapter,
    YouTubeMusicAdapter,
)
```

In `build_adapter_map` nach dem YouTube-Music-Block:

```python
    if settings.enable_apple_music:
        # Auth-frei (iTunes Search API), kein Credential-Check.
        adapters["apple_music"] = AppleMusicAdapter(
            client=http, storefront=settings.apple_music_storefront
        )
    return adapters
```

(das bestehende `return adapters` ersetzen bzw. den neuen Block davor einfügen).

`backend/src/linkhop/routes/services.py` — `_NAMES` erweitern:

```python
_NAMES = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "tidal": "Tidal",
    "youtube_music": "YouTube Music",
    "apple_music": "Apple Music",
}
```

- [ ] **Step 4: Gesamte Backend-Suite laufen lassen**

Run: `cd backend && uv run pytest -m "not integration"`
Expected: PASS komplett — insbesondere auch `tests/routes/test_convert.py` (nutzt injizierte Fake-Adapter, darf von der Registrierung unberührt sein). Falls dort etwas rot wird: Ursache prüfen, nicht blind fixen.

- [ ] **Step 5: Lint + Commit**

```bash
cd backend && uv run ruff check . && uv run mypy src
git add backend/src/linkhop/config.py backend/src/linkhop/deps.py backend/src/linkhop/routes/services.py backend/tests/test_config.py backend/tests/test_deps.py backend/tests/routes/test_services.py
git commit -m "feat(backend): register apple music adapter with storefront setting"
```

---

### Task 5: Frontend — Brand-Farbe und Placeholder

**Files:**
- Modify: `frontend/src/lib/components/ServiceItem.svelte`
- Modify: `frontend/src/lib/components/InputBar.svelte`

**Interfaces:**
- Consumes: Service-ID `apple_music` und Name `Apple Music` kommen zur Laufzeit aus `/api/v1/services` (Task 4) — im Frontend ist nichts weiter zu verdrahten.
- Produces: nichts, rein visuell.

- [ ] **Step 1: Brand-Farbe ergänzen**

In `frontend/src/lib/components/ServiceItem.svelte` nach der `youtube_music`-Zeile im `<style>`-Block:

```css
  .row[data-service-id='apple_music'] { --brand: #fa243c; }
```

- [ ] **Step 2: Placeholder erweitern**

In `frontend/src/lib/components/InputBar.svelte` Zeile 39 ersetzen:

```svelte
    placeholder="Spotify-, Deezer-, Tidal-, YouTube-Music- oder Apple-Music-Link einfügen …"
```

- [ ] **Step 3: Checks laufen lassen**

Run: `cd frontend && pnpm check && pnpm test`
Expected: `svelte-check` ohne Fehler, Vitest PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/components/ServiceItem.svelte frontend/src/lib/components/InputBar.svelte
git commit -m "feat(frontend): apple music brand color and placeholder"
```

---

### Task 6: Helm-Chart

**Files:**
- Modify: `helm/linkhop/values.yaml`
- Modify: `helm/linkhop/templates/backend-deployment.yaml`

**Interfaces:**
- Consumes: Env-Vars `LINKHOP_ENABLE_APPLE_MUSIC`, `LINKHOP_APPLE_MUSIC_STOREFRONT` (Task 4).
- Produces: Values `config.enableAppleMusic`, `config.appleMusicStorefront`.

- [ ] **Step 1: Values ergänzen**

In `helm/linkhop/values.yaml` im `config:`-Block nach `enableYoutubeMusic: true`:

```yaml
  # -- Apple Music braucht keine Credentials (iTunes Search API).
  enableAppleMusic: true
  # -- Apple-Music-Storefront (Länderkatalog) für Lookups und erzeugte Links
  appleMusicStorefront: "de"
```

- [ ] **Step 2: Deployment-Env verdrahten**

In `helm/linkhop/templates/backend-deployment.yaml` nach dem `LINKHOP_ENABLE_YOUTUBE_MUSIC`-Eintrag:

```yaml
            - name: LINKHOP_ENABLE_APPLE_MUSIC
              value: {{ .Values.config.enableAppleMusic | quote }}
            - name: LINKHOP_APPLE_MUSIC_STOREFRONT
              value: {{ .Values.config.appleMusicStorefront | quote }}
```

- [ ] **Step 3: Chart prüfen**

Run: `helm lint helm/linkhop && helm template helm/linkhop --set config.databaseUrl=x | grep -A1 APPLE`
Expected: `lint` ohne Fehler; im Template-Output erscheinen beide Env-Vars mit `"true"` und `"de"`.

- [ ] **Step 4: Commit**

```bash
git add helm/linkhop/values.yaml helm/linkhop/templates/backend-deployment.yaml
git commit -m "feat(helm): apple music enable flag and storefront value"
```

---

### Task 7: Dokumentation

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`

**Interfaces:** keine — reine Doku.

- [ ] **Step 1: Haupt-README**

In der „Supported services"-Tabelle nach der YouTube-Music-Zeile:

```markdown
| Apple Music   | ✓      | ✓      | ✓       | iTunes Search API, free   |
```

Direkt unter der Tabelle (nach der Zeile „Playlists are out of scope for V1.") ergänzen:

```markdown
Note: the iTunes API accepts ISRC/UPC as lookup *input* but does not return
them in responses — conversions *towards* Apple Music match via ISRC/UPC,
conversions *from* Apple Music fall back to metadata matching.
```

Außerdem im „Quick start"-Absatz die Klammer aktualisieren:

```markdown
(Deezer, YouTube Music and Apple Music work without credentials;
Spotify/Tidal need client credentials via env vars — see `backend/README.md`).
```

- [ ] **Step 2: Backend-README Env-Var-Referenz**

In `backend/README.md` in der Env-Var-Tabelle die Enable-Zeile ersetzen:

```markdown
| `LINKHOP_ENABLE_SPOTIFY` / `_DEEZER` / `_TIDAL` / `_YOUTUBE_MUSIC` / `_APPLE_MUSIC` | all `true` | Toggle individual adapters. |
```

und nach der `LINKHOP_TIDAL_CLIENT_ID`-Zeile ergänzen:

```markdown
| `LINKHOP_APPLE_MUSIC_STOREFRONT` | `de` | Apple Music country catalog for lookups and generated links. |
```

- [ ] **Step 3: Commit**

```bash
git add README.md backend/README.md
git commit -m "docs: document apple music support"
```

---

### Task 8: Live-Integration-Tests

**Files:**
- Modify: `backend/tests/integration/test_real_adapters.py`

**Interfaces:**
- Consumes: `AppleMusicAdapter` (Task 2/3), bestehende `clients`-Fixture.
- Produces: nichts — Live-Absicherung.

- [ ] **Step 1: Tests schreiben**

In `backend/tests/integration/test_real_adapters.py`:

Import ergänzen:

```python
from linkhop.adapters.apple_music import AppleMusicAdapter
from linkhop.url_parser import ParsedUrl, parse
```

(die bestehende `parse`-Import-Zeile ersetzen). In der `clients`-Fixture ergänzen:

```python
            "apple_music": AppleMusicAdapter(client=http, storefront="de"),
```

Tests anhängen:

```python
async def test_deezer_to_apple_music_via_isrc(clients):
    # Credential-freier Flow: Deezer liefert ISRC, Apple-Lookup matcht exakt.
    parsed = parse("https://www.deezer.com/track/3135556")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Deezer resolve returned no ISRC — ID rotated?"
    hits = await clients["apple_music"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_apple_music_source_to_deezer_metadata(clients):
    # Kein hartkodiertes Apple-ID-Fixture: die Apple-ID kommt aus dem ISRC-Hit,
    # resolve lädt sie nach (die Pipeline macht in _score_hit dasselbe).
    parsed = parse("https://www.deezer.com/track/3135556")
    deezer_source = await clients["deezer"].resolve(parsed)
    assert deezer_source is not None
    apple_hits = await clients["apple_music"].search(deezer_source, ContentType.TRACK)
    assert apple_hits
    apple_source = await clients["apple_music"].resolve(
        ParsedUrl("apple_music", "track", apple_hits[0].id)
    )
    assert apple_source is not None
    assert apple_source.title
    assert apple_source.duration_ms
    # iTunes-Antworten enthalten keine ISRCs — Rückrichtung ist metadata-only.
    assert apple_source.isrc is None
    hits = await clients["deezer"].search(apple_source, ContentType.TRACK)
    assert hits
    assert all(h.match == "metadata" for h in hits)
```

- [ ] **Step 2: Live laufen lassen (credential-frei möglich)**

Run: `cd backend && LINKHOP_LIVE_TESTS=1 uv run pytest tests/integration -k apple_music -v`
Expected: 2 PASSED (braucht nur Netz, keine Credentials). Falls Apple 403/429 liefert: kurz warten und erneut versuchen (Rate-Limit ~20/min).

- [ ] **Step 3: Lint + Commit**

```bash
cd backend && uv run ruff check .
git add backend/tests/integration/test_real_adapters.py
git commit -m "test(backend): apple music live integration tests"
```
