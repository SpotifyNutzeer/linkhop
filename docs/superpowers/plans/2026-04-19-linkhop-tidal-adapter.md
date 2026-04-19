# linkhop Tidal-Adapter Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tidal als dritter Streaming-Dienst nachrüsten. `GET /api/v1/convert` liefert nach Plan B Spotify ↔ Deezer ↔ Tidal bidirektional via ISRC/UPC/Metadata-Match. YouTube Music wird bewusst **komplett aus V1 gestrichen** (Spec-Abweichung — siehe Rationale unten).

**Scope-Abgrenzung gegenüber Plan A:**
- Plan A lieferte Backend-Core + Spotify + Deezer. Tidal-URL-Parser, Tidal-Config-Keys und ein Stub-Eintrag in `routes/services.py` `_NAMES` existieren bereits; ein Tidal-Adapter **nicht**.
- YouTube Music war in Plan A nie implementiert, aber URL-Parser-Regex (`music.youtube.com/*`), `enable_youtube_music`-Config-Flag, `_NAMES`-Eintrag und drei URL-Parser-Tests sind als Platzhalter drin — die fliegen raus.

**Rationale YouTube Music-Drop:**
Die offizielle YouTube Data API v3 ist **nicht** YouTube Music (sucht ganz YouTube: Karaoke, Covers, Reactions) und hat 100 Search-Units pro Request × 10k Default-Quota = 100 Konvertierungen/Tag total. Die inoffizielle `ytmusicapi` braucht Browser-Cookie-Header, die manuell rotiert werden müssen — Ops-Debt, den wir nicht in V1 tragen wollen. YT Music landet in einem separaten Mini-Plan, wenn der Cookie-Verwaltungsprozess sauber geklärt ist.

**Architecture:** Kein struktureller Eingriff — Adapter-Protocol aus Plan A Task 7 deckt Tidal komplett ab. Tidal nutzt OAuth-Client-Credentials (wie Spotify) und Token-Refresh. Neue Datei: `src/linkhop/adapters/tidal.py`, in `deps.py` + `adapters/__init__.py` + Composition-Root registriert.

**Tech Stack:** Keine neuen Pins. Tidal-Adapter nutzt `httpx.AsyncClient` (vorhandener Shared-Client aus Lifespan) und `respx` für Unit-Tests.

---

## File Structure (Änderungen)

```
backend/
├── src/linkhop/
│   ├── config.py             # MODIFY: enable_youtube_music-Feld entfernen
│   ├── url_parser.py         # MODIFY: _YTM_ID-Regex + music.youtube.com-Branch entfernen
│   ├── deps.py               # MODIFY: TidalAdapter registrieren
│   ├── adapters/
│   │   ├── __init__.py       # MODIFY: TidalAdapter exportieren
│   │   └── tidal.py          # CREATE
│   └── routes/
│       └── services.py       # MODIFY: "youtube_music" aus _NAMES entfernen
└── tests/
    ├── fixtures/
    │   ├── tidal_track.json      # CREATE
    │   ├── tidal_album.json      # CREATE
    │   ├── tidal_artist.json     # CREATE
    │   ├── tidal_search_isrc.json    # CREATE
    │   └── tidal_search_metadata.json # CREATE
    ├── adapters/
    │   └── test_tidal.py     # CREATE
    ├── integration/
    │   └── test_real_spotify_deezer.py  # MODIFY: Tidal-Live-Case ergänzen, Datei umbenennen zu test_real_adapters.py
    ├── test_url_parser.py    # MODIFY: YT-Music-Cases raus, Tidal-Cases dazu
    └── test_config.py        # MODIFY: enable_youtube_music-Assertion raus
```

**Decomposition-Logik:** Cleanup (Task 1) steht vor Implementation, weil die YT-Music-Platzhalter beim Tidal-Wiring sonst als "totes Feld" stehen bleiben. Adapter wird in drei Tasks (Recherche + Resolve, Search, Wiring) gesplittet, damit jede Phase isoliert reviewbar ist.

---

## Task 1: YouTube-Music-Platzhalter entfernen

**Files:**
- Modify: `backend/src/linkhop/config.py`
- Modify: `backend/src/linkhop/url_parser.py`
- Modify: `backend/src/linkhop/routes/services.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_url_parser.py`

- [ ] **Step 1.1: Config-Field `enable_youtube_music` entfernen**

In `src/linkhop/config.py`: Die Zeile `enable_youtube_music: bool = True` (und falls vorhanden ein dazugehöriger `AliasChoices`-Eintrag) ersatzlos streichen. Die anderen `enable_*`-Flags und Tidal-Credentials bleiben.

- [ ] **Step 1.2: URL-Parser aufräumen**

In `src/linkhop/url_parser.py`:
- `_YTM_ID`-Regex ersatzlos streichen.
- Den kompletten `elif host == "music.youtube.com":`-Block inkl. aller drei Sub-Branches (`/watch`, `/playlist`, `/channel/...`) streichen.

Der `parse_qs`-Import wird dadurch ungenutzt — ruff `F401` entfernt ihn auto-fix. In der Commit-Message erwähnen.

- [ ] **Step 1.3: `_NAMES`-Eintrag entfernen**

In `src/linkhop/routes/services.py`: Die Zeile `"youtube_music": "YouTube Music",` aus dem `_NAMES`-Dict streichen.

- [ ] **Step 1.4: Tests aufräumen**

In `tests/test_config.py`: Die Assertion `assert settings.enable_youtube_music is True` streichen.

In `tests/test_url_parser.py`: Die drei parametrisierten Cases mit `music.youtube.com` entfernen. Falls ein `test_yt_music_*`-Test existiert, ebenfalls.

- [ ] **Step 1.5: Tests laufen lassen**

```bash
cd backend && pytest -q
```

Expected: weiterhin grün, ggf. 3 Tests weniger (URL-Parser-Parametrisierung).

- [ ] **Step 1.6: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/src/linkhop/ backend/tests/
git commit -m "chore(backend): drop YouTube Music placeholders (Plan B Task 1)"
```

---

## Task 2: Tidal-Adapter Resolve

**Files:**
- Create: `backend/src/linkhop/adapters/tidal.py`
- Create: `backend/tests/fixtures/tidal_track.json`
- Create: `backend/tests/fixtures/tidal_album.json`
- Create: `backend/tests/fixtures/tidal_artist.json`
- Create: `backend/tests/adapters/test_tidal.py`

- [ ] **Step 2.0: Tidal-OpenAPI-Recherche (Pflicht vor Code)**

Der Implementer-Subagent **muss vor dem Schreiben von Code** die aktuelle Tidal-OpenAPI-Dokumentation fetchen und die folgenden Assumptions verifizieren, bevor der Adapter-Code entsteht. Assumptions stehen hier als Best-Knowledge-Start; sobald Docs widersprechen, zählt das Dokumentierte.

Assumptions (zu verifizieren):

| Aspekt | Annahme | Verifizieren |
|---|---|---|
| Base-URL | `https://openapi.tidal.com/v2/` | GET auf OpenAPI-Spec ziehen |
| Token-Endpoint | `https://auth.tidal.com/v1/oauth2/token`, Grant `client_credentials`, Basic-Auth mit `client_id:client_secret` | Tidal-Developer-Docs |
| Track-Resolve | `GET /tracks/{id}?countryCode=DE` → ISRC in `attributes.isrc`, Title in `attributes.title`, Duration in `attributes.duration` (ISO 8601 → ms konvertieren) | Response-Shape prüfen |
| Album-Resolve | `GET /albums/{id}?countryCode=DE` → UPC in `attributes.barcodeId`, Title in `attributes.title` | Response-Shape prüfen |
| Artist-Resolve | `GET /artists/{id}?countryCode=DE` → Name in `attributes.name` | Response-Shape prüfen |
| Track-ISRC-Search | `GET /tracks?filter[isrc]=...&countryCode=DE` | Response-Shape prüfen |
| Album-UPC-Search | `GET /albums?filter[barcodeId]=...&countryCode=DE` | Response-Shape prüfen |
| Metadata-Search | `GET /searchResults/{query}/relationships/{tracks\|albums\|artists}?countryCode=DE` oder `GET /search?query=...&type=...` | Docs prüfen — die Tidal-Such-API hat mehrere Pfade |
| Artist-Namen im Track-Resolve | Via `relationships.artists.data[].id` (JSON:API-Pattern) + separatem Lookup, ODER via `include=artists` im selben Request | Docs prüfen, `include=artists` bevorzugt (1 Request statt N+1) |
| Artwork | Via `attributes.imageLinks[].href` oder `relationships.coverArt`; Größe meist via `?dimensions=640x640` | Docs prüfen |

**Output dieser Step:** Ein Kommentar-Block am Kopf von `src/linkhop/adapters/tidal.py`, der die verifizierten Endpoints + Response-Shape in 5–8 Zeilen zusammenfasst. Beispiel:

```python
# Tidal OpenAPI v2 (verifiziert via https://openapi.tidal.com/ am 2026-04-19):
# - Base: https://openapi.tidal.com/v2/
# - Token: POST https://auth.tidal.com/v1/oauth2/token (client_credentials, Basic-Auth)
# - Track: GET /tracks/{id}?countryCode=DE&include=artists,albums
#   → data.attributes.{title,isrc,duration}, data.relationships.artists.data[]
# - ISRC-Search: GET /tracks?filter[isrc]=...&countryCode=DE
# - Metadata: GET /searchResults/{query}/relationships/tracks?countryCode=DE&include=...
```

Dieser Kommentar ist **Plan-Fidelity-Pflicht**: er begründet spätere Design-Entscheidungen und muss im Review verifizierbar sein.

- [ ] **Step 2.1: `AdapterCapabilities` und Grundgerüst**

In `src/linkhop/adapters/tidal.py`:

```python
from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, MatchType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


class TidalAdapter:
    service_id = "tidal"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://openapi.tidal.com/v2"
    _TOKEN = "https://auth.tidal.com/v1/oauth2/token"
    _COUNTRY = "DE"  # CountryCode ist bei Tidal OpenAPI required — DE ist der Deployment-Standort

    def __init__(self, client: httpx.AsyncClient, client_id: str, client_secret: str) -> None:
        self._http = client
        self._cid = client_id
        self._csec = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0
```

**Begründung `_COUNTRY` als Constant statt Settings-Field:**
Tidal serviert Katalog + Artwork regional gefiltert. Wenn der Backend-Standort wechselt, wird das ein Settings-Field (`LINKHOP_TIDAL_COUNTRY`); für V1 ist eine Konstante ausreichend und vermeidet Konfigurations-Oberfläche ohne Nutzen.

- [ ] **Step 2.2: Token-Refresh (wie Spotify)**

```python
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
            raise AdapterError("tidal", f"token fetch failed: {resp.status_code}")
        body = resp.json()
        token: str = body["access_token"]
        self._token = token
        self._token_exp = time.monotonic() + int(body.get("expires_in", 3600))
        return token
```

Identisch zum Spotify-Token-Pattern. 30s-Puffer vor Expiry verhindert Race beim Request-Boundary.

- [ ] **Step 2.3: `_get`-Helper mit 404/401-Handling**

```python
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        token = await self._ensure_token()
        p = {"countryCode": self._COUNTRY}
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
```

- [ ] **Step 2.4: `resolve()` für Track/Album/Artist**

Grundgerüst (Response-Felder an verifizierte Shape aus Step 2.0 anpassen):

```python
    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(f"/tracks/{parsed.id}", params={"include": "artists,albums"})
            if not data or not data.get("data"):
                return None
            attrs = data["data"]["attributes"]
            # Artists + Album aus den included-Resources (JSON:API-Pattern) joinen
            included = {(i["type"], i["id"]): i for i in data.get("included", [])}
            artist_rels = data["data"]["relationships"]["artists"]["data"]
            album_rels = data["data"]["relationships"].get("albums", {}).get("data", [])
            artists = tuple(
                included[("artists", r["id"])]["attributes"]["name"]
                for r in artist_rels if ("artists", r["id"]) in included
            )
            album_title = None
            if album_rels:
                album_key = ("albums", album_rels[0]["id"])
                if album_key in included:
                    album_title = included[album_key]["attributes"]["title"]
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.TRACK,
                id=data["data"]["id"],
                url=f"https://tidal.com/track/{data['data']['id']}",
                title=attrs["title"],
                artists=artists,
                album=album_title,
                duration_ms=_iso8601_to_ms(attrs["duration"]),
                isrc=attrs.get("isrc"),
                upc=None,
                artwork=_pick_artwork(attrs.get("imageLinks", [])),
            )
        if parsed.type == "album":
            ...
        if parsed.type == "artist":
            ...
        return None
```

**Warum `url` rekonstruiert statt aus Response:**
Tidal-Responses enthalten keinen kanonischen `external_url`. `https://tidal.com/track/{id}` ist der stabile, öffentlich teilbare Link — in Plan A Task 3 URL-Parser bereits als Input-Pattern anerkannt, damit Round-Trip konsistent.

**Helper-Funktionen am Ende der Datei:**

```python
def _iso8601_to_ms(duration: str | None) -> int | None:
    # Tidal liefert ISO 8601 Duration wie "PT4M17S"; wandle in Millisekunden um.
    # Wenn die verifizierte Shape in Step 2.0 stattdessen Integer-Sekunden liefert,
    # vereinfachen (return int(duration) * 1000).
    if not duration:
        return None
    import re
    m = re.match(r"^PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$", duration)
    if not m:
        return None
    minutes = int(m.group(1) or 0)
    seconds = float(m.group(2) or 0)
    return int((minutes * 60 + seconds) * 1000)


def _pick_artwork(image_links: list[dict[str, Any]]) -> str:
    # Größe ~640x640 bevorzugt (wie Spotify liefert); Fallback: erstes verfügbares.
    if not image_links:
        return ""
    best = next(
        (il for il in image_links if il.get("meta", {}).get("width") in (640, 750)),
        image_links[0],
    )
    return best.get("href", "")
```

- [ ] **Step 2.5: Fixtures anlegen**

Drei JSON-Fixtures mit der verifizierten Tidal-Response-Shape (Step 2.0):

- `tests/fixtures/tidal_track.json` — eine Track-Response mit ISRC, Artists, Album
- `tests/fixtures/tidal_album.json` — eine Album-Response mit UPC
- `tests/fixtures/tidal_artist.json` — eine Artist-Response

**Pflicht-Feld für Track-Fixture:** `attributes.isrc` gesetzt, damit Resolve→Search-Chain im E2E-Test Task 5 den ISRC-Pfad trifft. Ohne ISRC testen wir am Happy-Path vorbei.

- [ ] **Step 2.6: Unit-Tests für `resolve()` — `tests/adapters/test_tidal.py`**

```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.tidal import TidalAdapter
from linkhop.url_parser import ParsedUrl

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def adapter():
    http = httpx.AsyncClient()
    return TidalAdapter(client=http, client_id="cid", client_secret="csec"), http


@pytest.fixture
def token_route():
    with respx.mock(base_url="https://auth.tidal.com") as m:
        m.post("/v1/oauth2/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        )
        yield m


async def test_resolve_track_returns_isrc_and_metadata(adapter, token_route):
    ad, _ = adapter
    with respx.mock(base_url="https://openapi.tidal.com", assert_all_called=False) as api:
        api.get("/v2/tracks/1").mock(return_value=httpx.Response(200, json=_load("tidal_track.json")))
        out = await ad.resolve(ParsedUrl("tidal", "track", "1"))
    assert out is not None
    assert out.isrc  # muss aus Fixture kommen
    assert out.title
    assert out.artists
    assert out.duration_ms and out.duration_ms > 0
```

Plus analoge Tests für Album und Artist sowie einen 404-Test (`resp.status_code == 404` → `None`-Rückgabe).

- [ ] **Step 2.7: Tests laufen lassen**

```bash
cd backend && pytest -q tests/adapters/test_tidal.py
```

Expected: alle grün.

- [ ] **Step 2.8: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/src/linkhop/adapters/tidal.py backend/tests/
git commit -m "feat(backend): tidal adapter resolve (Plan B Task 2)"
```

---

## Task 3: Tidal-Adapter Search

**Files:**
- Modify: `backend/src/linkhop/adapters/tidal.py`
- Create: `backend/tests/fixtures/tidal_search_isrc.json`
- Create: `backend/tests/fixtures/tidal_search_metadata.json`
- Modify: `backend/tests/adapters/test_tidal.py`

- [ ] **Step 3.1: `search()`-Methode (ISRC/UPC-First, Metadata-Fallback)**

Analog zu `SpotifyAdapter.search()`, aber mit Tidal-OpenAPI-Pfaden aus Step 2.0:

```python
    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            return await self._search_tracks_by_isrc(meta.isrc)
        if target_type == ContentType.ALBUM and meta.upc:
            return await self._search_albums_by_upc(meta.upc)
        if target_type == ContentType.TRACK:
            return await self._search_metadata("tracks", meta, match="metadata")
        if target_type == ContentType.ALBUM:
            return await self._search_metadata("albums", meta, match="metadata")
        if target_type == ContentType.ARTIST:
            return await self._search_metadata("artists", meta, match="metadata")
        return []
```

Implementation der drei `_search_*`-Methoden nach verifizierter Shape aus Step 2.0. Wichtig: `confidence=1.0 if match == "isrc" else 0.0` (Matcher-Pipeline weist den finalen Score zu, Adapter liefert nur Kandidaten).

- [ ] **Step 3.2: Metadata-Query-Konstruktion**

```python
    async def _search_metadata(
        self, kind: str, meta: ResolvedContent, match: MatchType
    ) -> list[SearchHit]:
        # Tidal-Search-API nimmt einen Freitext-Query; "<Artist> <Title>" ist das
        # Pattern mit der höchsten Treffer-Qualität in Community-Benchmarks.
        artist = meta.artists[0] if meta.artists else ""
        query = f"{artist} {meta.title}".strip()
        ...
```

Reason-Kommentar ist kein Schmuck: im Review wurde in Plan A die identische Frage "warum 'Artist Title' und nicht 'Title Artist'" gestellt — Antwort gehört in den Code, nicht in den PR-Thread.

- [ ] **Step 3.3: Fixtures**

- `tests/fixtures/tidal_search_isrc.json` — Search-Response für ISRC-Treffer (1+ Kandidaten)
- `tests/fixtures/tidal_search_metadata.json` — Search-Response für Metadata-Query (2–3 Kandidaten)

- [ ] **Step 3.4: Unit-Tests ergänzen**

In `tests/adapters/test_tidal.py`:

```python
async def test_search_by_isrc_returns_confidence_1(adapter, token_route):
    ad, _ = adapter
    with respx.mock(base_url="https://openapi.tidal.com") as api:
        api.get("/v2/tracks").mock(
            return_value=httpx.Response(200, json=_load("tidal_search_isrc.json"))
        )
        meta = ResolvedContent(
            service="spotify", type=ContentType.TRACK, id="sp1",
            url="...", title="Nightcall", artists=("Kavinsky",),
            album=None, duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
        )
        hits = await ad.search(meta, ContentType.TRACK)
    assert len(hits) >= 1
    assert hits[0].match == "isrc"
    assert hits[0].confidence == 1.0


async def test_search_metadata_when_no_isrc(...):
    # match == "metadata", confidence == 0.0 (Matcher setzt final)
    ...
```

Plus: Test, dass `search(meta, ContentType.ALBUM)` mit `meta.upc` den UPC-Pfad trifft.

- [ ] **Step 3.5: Tests laufen lassen**

```bash
cd backend && pytest -q tests/adapters/test_tidal.py
```

- [ ] **Step 3.6: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/src/linkhop/adapters/tidal.py backend/tests/
git commit -m "feat(backend): tidal adapter search (Plan B Task 3)"
```

---

## Task 4: Composition-Root + Adapter-Registry

**Files:**
- Modify: `backend/src/linkhop/adapters/__init__.py`
- Modify: `backend/src/linkhop/deps.py`
- Modify: `backend/tests/test_deps.py`

- [ ] **Step 4.1: Export in `adapters/__init__.py`**

Den Import und `__all__`-Eintrag für `TidalAdapter` ergänzen:

```python
from linkhop.adapters.base import AdapterCapabilities, AdapterError, ServiceAdapter
from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.adapters.tidal import TidalAdapter

__all__ = [
    "AdapterCapabilities",
    "AdapterError",
    "DeezerAdapter",
    "ServiceAdapter",
    "SpotifyAdapter",
    "TidalAdapter",
]
```

Sortierung alphabetisch (ruff `RUF022`).

- [ ] **Step 4.2: `deps.py` erweitern**

```python
from linkhop.adapters import DeezerAdapter, ServiceAdapter, SpotifyAdapter, TidalAdapter


def build_adapter_map(settings: Settings, http: httpx.AsyncClient) -> dict[str, ServiceAdapter]:
    adapters: dict[str, ServiceAdapter] = {}
    if settings.enable_spotify and settings.spotify_client_id and settings.spotify_client_secret:
        adapters["spotify"] = SpotifyAdapter(
            client=http,
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
    if settings.enable_deezer:
        adapters["deezer"] = DeezerAdapter(client=http)
    if settings.enable_tidal and settings.tidal_client_id and settings.tidal_client_secret:
        adapters["tidal"] = TidalAdapter(
            client=http,
            client_id=settings.tidal_client_id,
            client_secret=settings.tidal_client_secret,
        )
    return adapters
```

Der alte Kommentar `# Tidal / YouTube Music kommen in Plan B` wird ersatzlos gestrichen.

**Absicherung wie bei Spotify:** Fehlende Credentials führen zu Skip, nicht zu einem registrierten aber defekten Adapter. Plan A Review-Finding — war die gleiche Logik, ist hier konsistent zu halten.

- [ ] **Step 4.3: Test für `build_adapter_map` erweitern**

In `tests/test_deps.py`: Einen Test-Case hinzufügen, der mit `enable_tidal=True, tidal_client_id="x", tidal_client_secret="y"` bewirkt, dass `"tidal"` im Map vorkommt. Und einen Case, wo nur `enable_tidal=True` ohne Credentials gesetzt ist → `"tidal" not in adapters`.

- [ ] **Step 4.4: Tests laufen lassen**

```bash
cd backend && pytest -q
```

Expected: alle grün, Tidal-Test-Count wächst um ~2.

- [ ] **Step 4.5: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/src/linkhop/ backend/tests/test_deps.py
git commit -m "feat(backend): wire tidal adapter into composition root (Plan B Task 4)"
```

---

## Task 5: Live-Integration-Test Tidal

**Files:**
- Rename: `backend/tests/integration/test_real_spotify_deezer.py` → `test_real_adapters.py`
- Modify (nach Rename): `backend/tests/integration/test_real_adapters.py`
- Modify: `backend/README.md` (neue Env-Vars dokumentieren)

- [ ] **Step 5.1: Datei umbenennen**

```bash
cd backend
git mv tests/integration/test_real_spotify_deezer.py tests/integration/test_real_adapters.py
```

Grund: Mit Tidal drin ist der Name nicht mehr akkurat; Rename jetzt vermeidet eine spätere kosmetische Umbenennung.

- [ ] **Step 5.2: Tidal-Fixture für Live-Test**

Am Ende des `clients`-Fixtures den Tidal-Adapter ergänzen:

```python
@pytest.fixture
async def clients():
    async with httpx.AsyncClient(timeout=15) as http:
        yield {
            "spotify": SpotifyAdapter(
                client=http,
                client_id=os.environ["LINKHOP_SPOTIFY_CLIENT_ID"],
                client_secret=os.environ["LINKHOP_SPOTIFY_CLIENT_SECRET"],
            ),
            "deezer": DeezerAdapter(client=http),
            "tidal": TidalAdapter(
                client=http,
                client_id=os.environ["LINKHOP_TIDAL_CLIENT_ID"],
                client_secret=os.environ["LINKHOP_TIDAL_CLIENT_SECRET"],
            ),
        }
```

- [ ] **Step 5.3: Zwei neue Tidal-Tests**

```python
async def test_tidal_to_spotify_via_isrc(clients):
    parsed = parse("https://tidal.com/track/77640617")  # stabile bekannte Track-ID — swap if 404
    source = await clients["tidal"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Tidal resolve returned no ISRC — ID rotated?"
    hits = await clients["spotify"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_spotify_to_tidal_via_isrc(clients):
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Spotify resolve returned no ISRC — ID rotated?"
    hits = await clients["tidal"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)
```

ISRC-Precondition-Assertion wie in Plan A Task 26: ohne ISRC-Payload würde der Test als "kein Match" scheitern statt als "Quelle hat keinen ISRC gemeldet" — die Diagnostik ist den zusätzlichen Assert wert.

- [ ] **Step 5.4: README-Update**

In `backend/README.md` unter dem Integration-Test-Block:

```markdown
Live-Integrationstests benötigen zusätzlich:
- `LINKHOP_TIDAL_CLIENT_ID` / `LINKHOP_TIDAL_CLIENT_SECRET` für Tidal-Tests.
```

- [ ] **Step 5.5: Live-Smoke lokal (optional, nur wenn Credentials vorhanden)**

```bash
cd backend
LINKHOP_LIVE_TESTS=1 \
  LINKHOP_SPOTIFY_CLIENT_ID=... LINKHOP_SPOTIFY_CLIENT_SECRET=... \
  LINKHOP_TIDAL_CLIENT_ID=... LINKHOP_TIDAL_CLIENT_SECRET=... \
  pytest -q tests/integration/test_real_adapters.py
```

Expected: 4 passed (Spotify↔Deezer aus Plan A + Tidal↔Spotify neu).

- [ ] **Step 5.6: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/
git commit -m "test(backend): live integration tests for tidal (Plan B Task 5)"
```

---

## Task 6: Full-Suite + Coverage-Check + Final-Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-04-19-linkhop-tidal-adapter.md` (Plan-Sync)

- [ ] **Step 6.1: Test-Lauf mit Coverage**

```bash
cd backend && pytest --cov=linkhop --cov-report=term-missing -v
```

Expected:
- Alle Tests grün (157 aus Plan A + neue Tidal-Tests − YT-Music-URL-Cases)
- Coverage bleibt ≥ 85 % (Plan-A-Niveau war 97 %; Tidal-Adapter darf das nicht unter 85 % drücken)

Wenn Coverage < 85 %: fehlende Branches in Tidal-Adapter identifizieren und Unit-Tests ergänzen, bis die Schwelle wieder steht.

- [ ] **Step 6.2: Ruff-Lint**

```bash
cd backend && ruff check .
```

Expected: clean. Wenn nicht: fixen (analog Plan A Task 27.2).

- [ ] **Step 6.3: Mypy (best effort)**

```bash
cd backend && mypy src/linkhop
```

Erwartung: die zwei bekannten Stub-Lücken aus Plan A bleiben (cache.py, api_keys.py). Neue Findings am Tidal-Adapter: fixen, falls billig; dokumentieren, falls Stub-Problem.

- [ ] **Step 6.4: Plan-Sync**

Checkboxen in diesem Plan setzen. Post-Impl-Bilanz am Ende ergänzen (commit-Count, Test-Delta, Coverage).

- [ ] **Step 6.5: Final-Commit**

```bash
git add docs/superpowers/plans/2026-04-19-linkhop-tidal-adapter.md
git commit -m "docs(plan): sync Plan B — tidal adapter complete"

git commit --allow-empty -m "chore(backend): plan B complete — tidal adapter wired"
```

---

## Spec Coverage Check

| Spec-Anforderung | Nach Plan B |
|---|---|
| V1-Dienste Spotify, Deezer, Tidal | ✓ (Plan A + Plan B) |
| YouTube Music | **bewusst gestrichen**, dokumentiert oben; kommt in separatem Mini-Plan |
| Tracks/Alben/Artists alle 3 Dienste | ✓ |
| Bidirektionales ISRC-Match | ✓ (Task 5 Live-Test verifiziert) |
| Bidirektionales UPC-Match | ✓ (Unit-Test Task 3; kein Live-Album-Test im Plan, optional) |
| Adapter-Capabilities in `/services` | ✓ (existiert seit Plan A, Tidal via `AdapterCapabilities` automatisch) |
| Rate-Limit, Cache, Short-IDs | unverändert gegenüber Plan A |

## Risiko-Bilanz

- **Tidal-API-Zugang bricht/läuft aus:** Low — Credentials kommen aus Paul's Developer-Registrierung; Skip-with-warning-Logik in `deps.py` fängt fehlende Credentials sauber ab, Service degradet auf 2-Dienste-Modus.
- **Tidal-OpenAPI-Shape ändert sich:** Medium — die JSON:API-Pattern (`attributes`, `relationships`, `included`) sind Tidal-intern stabilisiert, aber Field-Namen (`barcodeId`, `isrc`) sind proprietär. Step 2.0-Kommentar am Dateikopf dient als Verification-Anker bei Breakage.
- **Coverage-Regression:** Low — Plan A landete bei 97 %, Puffer bis 85 % ist ~12 Prozentpunkte. Ein kompletter Adapter sollte den Puffer nicht aufbrauchen.

## Nächster Plan (Plan C)

Frontend (React/TypeScript, Catppuccin, Layout C/B) gegen die Backend-API, die nach Plan B vollständig funktioniert.

## Post-Impl-Bilanz

_(wird bei Task 6.4 ergänzt)_
