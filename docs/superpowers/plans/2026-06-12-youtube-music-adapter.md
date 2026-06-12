# YouTube-Music-Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vierter Service-Adapter (YouTube Music) für linkhop — bidirektionale Konvertierung von Tracks, Alben und Artists, ohne Authentifizierung.

**Architecture:** Neuer `YouTubeMusicAdapter` auf Basis der sync `ytmusicapi`-Library, deren Aufrufe per `asyncio.to_thread` gewrappt werden. Kein ISRC/UPC verfügbar → Matching läuft immer über den bestehenden Metadaten-Pfad; `matching.py` und `pipeline.py` bleiben unangetastet. URL-Parser lernt `music.youtube.com` (Track via `watch?v=`, Album via `playlist?list=OLAK5uy_…` oder `browse/MPREb_…`, Artist via `channel/UC…`).

**Tech Stack:** Python 3.12, FastAPI, `ytmusicapi`, pytest (Mock der `YTMusic`-Instanz statt respx — die Library nutzt eigenes `requests`), Helm, SvelteKit.

**Spec:** `docs/superpowers/specs/2026-06-12-youtube-music-adapter-design.md`

**Arbeitsverzeichnis:** Alle `pytest`/`pip`-Kommandos laufen in `backend/` mit aktiviertem venv (`source backend/.venv/bin/activate` bzw. `backend/.venv/bin/pytest`). Frontend-Kommandos in `frontend/`.

**Hinweis Album-IDs (zieht sich durch alle Tasks):** Geteilte YT-Music-Album-URLs enthalten eine Audio-Playlist-ID (`OLAK5uy_…`); `ytmusicapi`-Suchergebnisse und `get_album` arbeiten mit Browse-IDs (`MPREb_…`). Der Adapter übersetzt `OLAK5uy_…` → Browse-ID via `get_album_browse_id()`. Beide Formen müssen in `resolve()` funktionieren, weil die Pipeline (`pipeline.py:_score_hit`) Suchkandidaten per `resolve()` nachlädt.

---

### Task 1: Dependency `ytmusicapi`

**Files:**
- Modify: `backend/pyproject.toml` (dependencies-Liste)

- [ ] **Step 1: Aktuelle Version ermitteln**

Run: `pip index versions ytmusicapi`
Expected: Ausgabe wie `ytmusicapi (1.11.4)` — die aktuelle 1.x-Minor merken. Die Schritte unten nehmen `1.11` an; falls inzwischen eine neuere Minor aktuell ist, diese stattdessen pinnen.

- [ ] **Step 2: Dependency eintragen**

In `backend/pyproject.toml`, im `dependencies`-Array nach `"python-rapidjson==1.23",` einfügen:

```toml
    "ytmusicapi==1.11.*",
```

- [ ] **Step 3: Installieren**

Run: `cd backend && pip install -e ".[dev]"`
Expected: `Successfully installed … ytmusicapi-1.11.x …`

(Falls das Projekt lokal mit uv verwaltet wird — `backend/uv.lock` existiert —, zusätzlich `uv lock` ausführen, damit der Lockfile aktuell bleibt.)

- [ ] **Step 4: Import-Smoke-Test**

Run: `cd backend && python -c "from ytmusicapi import YTMusic; YTMusic(); print('ok')"`
Expected: `ok` — bestätigt nebenbei, dass der unauthentifizierte Konstruktor keinen Netzwerkfehler wirft.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "build(backend): add ytmusicapi dependency"
```

---

### Task 2: URL-Parser für music.youtube.com

**Files:**
- Modify: `backend/src/linkhop/url_parser.py`
- Test: `backend/tests/test_url_parser.py`

- [ ] **Step 1: Failing Tests schreiben**

In `backend/tests/test_url_parser.py` an die `test_parse_valid`-Parametrize-Liste (vor der schließenden `])`) anhängen:

```python
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "youtube_music", "track", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&si=AbC", "youtube_music", "track", "dQw4w9WgXcQ"),  # noqa: E501
    ("https://music.youtube.com/playlist?list=OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk", "youtube_music", "album", "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk"),  # noqa: E501
    # /browse/<MPREb_…> ist die Form, die linkhop selbst als Album-Ziel-URL erzeugt —
    # Round-Trip eigener Links muss funktionieren.
    ("https://music.youtube.com/browse/MPREb_K0OB6WlC9bF", "youtube_music", "album", "MPREb_K0OB6WlC9bF"),  # noqa: E501
    ("https://music.youtube.com/channel/UC0FvDIzS3wnvBJN1DyGZv6g", "youtube_music", "artist", "UC0FvDIzS3wnvBJN1DyGZv6g"),  # noqa: E501
```

An die `test_parse_invalid_raises`-Liste anhängen:

```python
    "https://music.youtube.com/playlist?list=PLabc12345",   # normale Playlist, kein Album
    "https://music.youtube.com/watch",                       # kein v=-Parameter
    "https://music.youtube.com/watch?v=tooshort",            # Video-ID != 11 Zeichen
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",           # nur music.youtube.com erlaubt
    "https://youtu.be/dQw4w9WgXcQ",
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && pytest tests/test_url_parser.py -v`
Expected: Die neuen `test_parse_valid`-Fälle FAILen mit `UnsupportedUrlError` (no matching service for host), die neuen Invalid-Fälle PASSen bereits (Host unbekannt → Fehler ist schon das Soll-Verhalten).

- [ ] **Step 3: Parser implementieren**

In `backend/src/linkhop/url_parser.py` den Import erweitern:

```python
from urllib.parse import parse_qs, urlparse
```

Nach `_TIDAL_PATH = …` ergänzen:

```python
# YouTube Music: Track-IDs stecken im Query-Parameter (watch?v=), Alben sind
# auto-generierte Playlists (OLAK5uy_…) oder Browse-IDs (MPREb_…, von linkhop
# selbst erzeugte Ziel-URLs), Artists sind Channels (UC…).
_YTM_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YTM_ALBUM_PLAYLIST = re.compile(r"^OLAK5uy_[A-Za-z0-9_-]+$")
_YTM_CHANNEL_PATH = re.compile(r"^/channel/(UC[A-Za-z0-9_-]+)/?$")
_YTM_BROWSE_PATH = re.compile(r"^/browse/(MPREb_[A-Za-z0-9_-]+)/?$")
```

In `parse()`, nach dem `elif`-Block für Tidal und vor dem abschließenden `raise UnsupportedUrlError(…)`:

```python
    elif host == "music.youtube.com":
        query = parse_qs(parsed.query)
        if path.rstrip("/") == "/watch":
            vid = (query.get("v") or [""])[0]
            if _YTM_VIDEO_ID.match(vid):
                return ParsedUrl("youtube_music", "track", vid)
        elif path.rstrip("/") == "/playlist":
            lid = (query.get("list") or [""])[0]
            if _YTM_ALBUM_PLAYLIST.match(lid):
                return ParsedUrl("youtube_music", "album", lid)
        else:
            m = _YTM_CHANNEL_PATH.match(path)
            if m:
                return ParsedUrl("youtube_music", "artist", m.group(1))
            m = _YTM_BROWSE_PATH.match(path)
            if m:
                return ParsedUrl("youtube_music", "album", m.group(1))
```

- [ ] **Step 4: Tests laufen lassen — müssen passen**

Run: `cd backend && pytest tests/test_url_parser.py -v`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/linkhop/url_parser.py backend/tests/test_url_parser.py
git commit -m "feat(backend): parse music.youtube.com URLs"
```

---

### Task 3: Adapter — `resolve()`

**Files:**
- Create: `backend/src/linkhop/adapters/youtube_music.py`
- Create: `backend/tests/adapters/test_youtube_music.py`
- Create: `backend/tests/fixtures/youtube_music_song.json`
- Create: `backend/tests/fixtures/youtube_music_album.json`
- Create: `backend/tests/fixtures/youtube_music_artist.json`

- [ ] **Step 1: Fixtures anlegen**

`backend/tests/fixtures/youtube_music_song.json` (Form der `get_song()`-Antwort):

```json
{
  "playabilityStatus": {"status": "OK"},
  "videoDetails": {
    "videoId": "AjgWa4BLvz4",
    "title": "Nightcall",
    "lengthSeconds": "257",
    "author": "Kavinsky",
    "channelId": "UC0FvDIzS3wnvBJN1DyGZv6g",
    "thumbnail": {
      "thumbnails": [
        {"url": "https://i.ytimg.com/vi/AjgWa4BLvz4/default.jpg", "width": 120, "height": 90},
        {"url": "https://i.ytimg.com/vi/AjgWa4BLvz4/maxresdefault.jpg", "width": 1280, "height": 720}
      ]
    }
  }
}
```

`backend/tests/fixtures/youtube_music_album.json` (Form der `get_album()`-Antwort):

```json
{
  "title": "OutRun",
  "type": "Album",
  "year": "2013",
  "artists": [{"name": "Kavinsky", "id": "UC0FvDIzS3wnvBJN1DyGZv6g"}],
  "audioPlaylistId": "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk",
  "thumbnails": [
    {"url": "https://lh3.googleusercontent.com/album-small", "width": 226, "height": 226},
    {"url": "https://lh3.googleusercontent.com/album-large", "width": 544, "height": 544}
  ],
  "tracks": []
}
```

`backend/tests/fixtures/youtube_music_artist.json` (Form der `get_artist()`-Antwort):

```json
{
  "name": "Kavinsky",
  "channelId": "UC0FvDIzS3wnvBJN1DyGZv6g",
  "description": "",
  "thumbnails": [
    {"url": "https://lh3.googleusercontent.com/artist-small", "width": 540, "height": 225},
    {"url": "https://lh3.googleusercontent.com/artist-large", "width": 1440, "height": 600}
  ]
}
```

- [ ] **Step 2: Failing Tests für `resolve()` schreiben**

`backend/tests/adapters/test_youtube_music.py` anlegen:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from linkhop.adapters.base import AdapterError
from linkhop.adapters.youtube_music import YouTubeMusicAdapter
from linkhop.models.domain import ContentType, ResolvedContent
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"

_BROWSE_ID = "MPREb_K0OB6WlC9bF"
_PLAYLIST_ID = "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk"
_CHANNEL_ID = "UC0FvDIzS3wnvBJN1DyGZv6g"


def fix(name: str):
    return json.loads((FIX / name).read_text())


def make_source(type_: ContentType, **overrides) -> ResolvedContent:
    base = dict(
        service="spotify", type=type_, id="x", url="",
        title="Nightcall", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    base.update(overrides)
    return ResolvedContent(**base)


@pytest.fixture
def yt() -> MagicMock:
    # ytmusicapi nutzt eigenes `requests`, respx greift nicht — daher wird die
    # YTMusic-Instanz selbst gemockt (sync-Methoden, vom Adapter via to_thread gerufen).
    return MagicMock()


@pytest.fixture
def adapter(yt: MagicMock) -> YouTubeMusicAdapter:
    return YouTubeMusicAdapter(client=yt)


async def test_resolve_track(adapter, yt):
    yt.get_song.return_value = fix("youtube_music_song.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "track", "AjgWa4BLvz4"))
    assert result is not None
    assert result.service == "youtube_music"
    assert result.type == ContentType.TRACK
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.duration_ms == 257000
    assert result.url == "https://music.youtube.com/watch?v=AjgWa4BLvz4"
    assert result.isrc is None
    assert result.upc is None
    # größtes Thumbnail gewinnt
    assert result.artwork.endswith("maxresdefault.jpg")
    yt.get_song.assert_called_once_with("AjgWa4BLvz4")


async def test_resolve_track_unplayable_returns_none(adapter, yt):
    yt.get_song.return_value = {
        "playabilityStatus": {"status": "ERROR", "reason": "Video unavailable"}
    }
    result = await adapter.resolve(ParsedUrl("youtube_music", "track", "gone4w9WgXcQ"))
    assert result is None


async def test_resolve_album_from_playlist_id(adapter, yt):
    # OLAK5uy_-IDs (geteilte URLs) werden erst in eine Browse-ID übersetzt.
    yt.get_album_browse_id.return_value = _BROWSE_ID
    yt.get_album.return_value = fix("youtube_music_album.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", _PLAYLIST_ID))
    assert result is not None
    assert result.id == _BROWSE_ID
    assert result.title == "OutRun"
    assert result.artists == ("Kavinsky",)
    assert result.url == f"https://music.youtube.com/playlist?list={_PLAYLIST_ID}"
    assert result.upc is None
    yt.get_album_browse_id.assert_called_once_with(_PLAYLIST_ID)
    yt.get_album.assert_called_once_with(_BROWSE_ID)


async def test_resolve_album_from_browse_id(adapter, yt):
    # MPREb_-IDs (aus Suchergebnissen, via pipeline._score_hit) direkt auflösen.
    yt.get_album.return_value = fix("youtube_music_album.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", _BROWSE_ID))
    assert result is not None
    assert result.id == _BROWSE_ID
    yt.get_album_browse_id.assert_not_called()


async def test_resolve_album_playlist_lookup_miss_returns_none(adapter, yt):
    yt.get_album_browse_id.return_value = None
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", "OLAK5uy_unknown0"))
    assert result is None
    yt.get_album.assert_not_called()


async def test_resolve_artist(adapter, yt):
    yt.get_artist.return_value = fix("youtube_music_artist.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "artist", _CHANNEL_ID))
    assert result is not None
    assert result.type == ContentType.ARTIST
    assert result.title == "Kavinsky"
    assert result.artists == ("Kavinsky",)
    assert result.url == f"https://music.youtube.com/channel/{_CHANNEL_ID}"


async def test_resolve_wraps_library_error(adapter, yt):
    yt.get_song.side_effect = RuntimeError("YouTube changed something")
    with pytest.raises(AdapterError) as exc:
        await adapter.resolve(ParsedUrl("youtube_music", "track", "AjgWa4BLvz4"))
    assert exc.value.service == "youtube_music"
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && pytest tests/adapters/test_youtube_music.py -v`
Expected: FAIL bei den Imports — `ModuleNotFoundError: No module named 'linkhop.adapters.youtube_music'`.

- [ ] **Step 4: Adapter mit `resolve()` implementieren**

`backend/src/linkhop/adapters/youtube_music.py` anlegen:

```python
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

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

    async def _call(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        # ytmusicapi ist synchron (requests-basiert); to_thread hält den Event-Loop
        # frei. Library-Exceptions sind undifferenziert → pauschal AdapterError,
        # die Pipeline degradiert damit pro Ziel statt die Konvertierung zu killen.
        try:
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
        if status != "OK" or not details:
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
        if not data:
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

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        return []
```

(`search()` ist hier bewusst noch ein Stub — Task 4 macht ihn per TDD vollständig.)

- [ ] **Step 5: Tests laufen lassen — müssen passen**

Run: `cd backend && pytest tests/adapters/test_youtube_music.py -v`
Expected: alle PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/linkhop/adapters/youtube_music.py \
        backend/tests/adapters/test_youtube_music.py \
        backend/tests/fixtures/youtube_music_song.json \
        backend/tests/fixtures/youtube_music_album.json \
        backend/tests/fixtures/youtube_music_artist.json
git commit -m "feat(backend): YouTube Music adapter resolve()"
```

---

### Task 4: Adapter — `search()`

**Files:**
- Modify: `backend/src/linkhop/adapters/youtube_music.py`
- Modify: `backend/tests/adapters/test_youtube_music.py`
- Create: `backend/tests/fixtures/youtube_music_search_songs.json`
- Create: `backend/tests/fixtures/youtube_music_search_albums.json`
- Create: `backend/tests/fixtures/youtube_music_search_artists.json`

- [ ] **Step 1: Such-Fixtures anlegen**

`backend/tests/fixtures/youtube_music_search_songs.json` (Form von `search(…, filter="songs")`; Eintrag 3 hat absichtlich keine videoId — wird übersprungen; Eintrag 4 testet das Limit):

```json
[
  {"category": "Songs", "resultType": "song", "videoId": "AjgWa4BLvz4", "title": "Nightcall", "artists": [{"name": "Kavinsky", "id": "UC0FvDIzS3wnvBJN1DyGZv6g"}], "album": {"name": "OutRun", "id": "MPREb_K0OB6WlC9bF"}, "duration_seconds": 257},
  {"category": "Songs", "resultType": "song", "videoId": "MV53Dpw1BRY", "title": "Nightcall (Live)", "artists": [{"name": "Kavinsky"}], "duration_seconds": 312},
  {"category": "Songs", "resultType": "song", "title": "Kaputter Eintrag ohne videoId", "artists": []},
  {"category": "Songs", "resultType": "song", "videoId": "zTbf3RKvIbM", "title": "Nightcall Cover", "artists": [{"name": "Somebody"}], "duration_seconds": 260}
]
```

`backend/tests/fixtures/youtube_music_search_albums.json`:

```json
[
  {"category": "Albums", "resultType": "album", "browseId": "MPREb_K0OB6WlC9bF", "title": "OutRun", "artists": [{"name": "Kavinsky"}], "type": "Album", "year": "2013"},
  {"category": "Albums", "resultType": "album", "browseId": "MPREb_8aHhkPo3kq2", "title": "OutRun (Deluxe)", "artists": [{"name": "Kavinsky"}], "type": "Album"}
]
```

`backend/tests/fixtures/youtube_music_search_artists.json` (Achtung: Name-Key heißt hier `artist`, nicht `title`):

```json
[
  {"category": "Artists", "resultType": "artist", "browseId": "UC0FvDIzS3wnvBJN1DyGZv6g", "artist": "Kavinsky"}
]
```

- [ ] **Step 2: Failing Tests für `search()` schreiben**

An `backend/tests/adapters/test_youtube_music.py` anhängen:

```python
async def test_search_track(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_songs.json")
    hits = await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
    # 4 Fixture-Einträge: items[:3] schneidet den 4. ab, der kaputte 3. (ohne
    # videoId) wird übersprungen → genau 2 Hits.
    assert len(hits) == 2
    assert hits[0].id == "AjgWa4BLvz4"
    assert hits[0].url == "https://music.youtube.com/watch?v=AjgWa4BLvz4"
    assert all(h.match == "metadata" and h.confidence == 0.0 for h in hits)
    yt.search.assert_called_once_with("Kavinsky Nightcall", filter="songs", limit=3)


async def test_search_album(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_albums.json")
    source = make_source(ContentType.ALBUM, title="OutRun")
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 2
    assert hits[0].id == "MPREb_K0OB6WlC9bF"
    assert hits[0].url == "https://music.youtube.com/browse/MPREb_K0OB6WlC9bF"
    yt.search.assert_called_once_with("Kavinsky OutRun", filter="albums", limit=3)


async def test_search_artist_uses_plain_name_query(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_artists.json")
    source = make_source(ContentType.ARTIST, title="Kavinsky")
    hits = await adapter.search(source, ContentType.ARTIST)
    assert len(hits) == 1
    assert hits[0].id == "UC0FvDIzS3wnvBJN1DyGZv6g"
    assert hits[0].url == "https://music.youtube.com/channel/UC0FvDIzS3wnvBJN1DyGZv6g"
    # Bei Artists wäre "Kavinsky Kavinsky" (artists[0] + title) eine verzerrte Query.
    yt.search.assert_called_once_with("Kavinsky", filter="artists", limit=3)


async def test_search_without_artists_uses_title_only(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_songs.json")
    source = make_source(ContentType.TRACK, artists=())
    await adapter.search(source, ContentType.TRACK)
    yt.search.assert_called_once_with("Nightcall", filter="songs", limit=3)


async def test_search_empty_returns_empty(adapter, yt):
    yt.search.return_value = []
    hits = await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
    assert hits == []


async def test_search_wraps_library_error(adapter, yt):
    yt.search.side_effect = RuntimeError("quota? block? who knows")
    with pytest.raises(AdapterError):
        await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && pytest tests/adapters/test_youtube_music.py -v`
Expected: Die neuen `test_search_*`-Tests FAILen (`assert 0 == 2` etc.), die `resolve`-Tests aus Task 3 bleiben PASS.

- [ ] **Step 4: `search()` implementieren**

In `backend/src/linkhop/adapters/youtube_music.py` den `search()`-Stub ersetzen durch:

```python
    _FILTERS: dict[ContentType, str] = {
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
```

- [ ] **Step 5: Tests laufen lassen — müssen passen**

Run: `cd backend && pytest tests/adapters/test_youtube_music.py -v`
Expected: alle PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/linkhop/adapters/youtube_music.py \
        backend/tests/adapters/test_youtube_music.py \
        backend/tests/fixtures/youtube_music_search_songs.json \
        backend/tests/fixtures/youtube_music_search_albums.json \
        backend/tests/fixtures/youtube_music_search_artists.json
git commit -m "feat(backend): YouTube Music adapter search()"
```

---

### Task 5: Registrierung — Config, deps, Services-Route

**Files:**
- Modify: `backend/src/linkhop/config.py:44-46`
- Modify: `backend/src/linkhop/deps.py`
- Modify: `backend/src/linkhop/adapters/__init__.py`
- Modify: `backend/src/linkhop/routes/services.py:11-15`
- Test: `backend/tests/test_deps.py`, `backend/tests/routes/test_services.py`

- [ ] **Step 1: Failing Tests schreiben**

An `backend/tests/test_deps.py` anhängen (Import oben ergänzen: `YouTubeMusicAdapter` in die bestehende `from linkhop.adapters import …`-Zeile aufnehmen):

```python
async def test_youtube_music_registered_by_default():
    # Auth-frei: kein Credential-Check, Default-Settings reichen.
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert isinstance(m["youtube_music"], YouTubeMusicAdapter)


async def test_youtube_music_disabled(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_YOUTUBE_MUSIC", "false")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "youtube_music" not in m
```

**Bestehenden Test anpassen** — `test_all_flags_off_returns_empty` würde sonst fehlschlagen, weil YouTube Music per Default aktiv ist. Im Test ergänzen:

```python
    monkeypatch.setenv("LINKHOP_ENABLE_YOUTUBE_MUSIC", "false")
```

(direkt nach den drei bestehenden `monkeypatch.setenv`-Zeilen.)

In `backend/tests/routes/test_services.py`, in `test_services_lists_enabled_adapters` nach `assert "deezer" in ids` ergänzen:

```python
    assert "youtube_music" in ids
    ytm = next(s for s in body["services"] if s["id"] == "youtube_music")
    assert ytm["name"] == "YouTube Music"
    assert set(ytm["capabilities"]) == {"track", "album", "artist"}
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && pytest tests/test_deps.py tests/routes/test_services.py -v`
Expected: FAIL — `ImportError` (YouTubeMusicAdapter nicht in `linkhop.adapters`) bzw. `KeyError: 'youtube_music'`.

- [ ] **Step 3: Export, Config, deps, Route implementieren**

`backend/src/linkhop/adapters/__init__.py` komplett ersetzen:

```python
from __future__ import annotations

from linkhop.adapters.base import AdapterCapabilities, ServiceAdapter
from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.adapters.tidal import TidalAdapter
from linkhop.adapters.youtube_music import YouTubeMusicAdapter

__all__ = [
    "AdapterCapabilities",
    "DeezerAdapter",
    "ServiceAdapter",
    "SpotifyAdapter",
    "TidalAdapter",
    "YouTubeMusicAdapter",
]
```

`backend/src/linkhop/config.py` — nach `enable_tidal: bool = True` einfügen:

```python
    enable_youtube_music: bool = True
```

`backend/src/linkhop/deps.py` — Imports erweitern und Registrierung ergänzen; Datei komplett ersetzen:

```python
from __future__ import annotations

import httpx
from ytmusicapi import YTMusic

from linkhop.adapters import (
    DeezerAdapter,
    ServiceAdapter,
    SpotifyAdapter,
    TidalAdapter,
    YouTubeMusicAdapter,
)
from linkhop.config import Settings


def build_adapter_map(settings: Settings, http: httpx.AsyncClient) -> dict[str, ServiceAdapter]:
    adapters: dict[str, ServiceAdapter] = {}
    # enable_spotify alone is not enough: a misconfigured deployment (e.g. only
    # _CLIENT_ID set) would register a broken adapter that 400s on every call.
    # Skip-with-warning at boot is clearer than a mystery runtime failure.
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
    if settings.enable_youtube_music:
        # Auth-frei, kein Credential-Check. YTMusic() initialisiert nur lokale
        # Header/Session, macht beim Konstruieren keinen Netzwerk-Call.
        adapters["youtube_music"] = YouTubeMusicAdapter(client=YTMusic())
    return adapters
```

`backend/src/linkhop/routes/services.py` — `_NAMES` erweitern:

```python
_NAMES = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "tidal": "Tidal",
    "youtube_music": "YouTube Music",
}
```

- [ ] **Step 4: Tests laufen lassen — müssen passen**

Run: `cd backend && pytest tests/test_deps.py tests/routes/test_services.py -v`
Expected: alle PASS. Falls `test_services_*` mit Netzwerkfehlern aus `YTMusic()` scheitert (sollte laut Step-4-Smoke-Test in Task 1 nicht passieren), wäre die Instanziierung in einen Lazy-Init im Adapter zu verschieben — dann hier stoppen und das im Review besprechen.

- [ ] **Step 5: Gesamte Backend-Suite laufen lassen**

Run: `cd backend && pytest`
Expected: alle PASS (Integration-Tests werden ohne `LINKHOP_LIVE_TESTS=1` geskippt).

- [ ] **Step 6: Lint und Typen prüfen**

Run: `cd backend && ruff check src tests && mypy src`
Expected: keine neuen Fehler.

- [ ] **Step 7: Commit**

```bash
git add backend/src/linkhop/adapters/__init__.py backend/src/linkhop/config.py \
        backend/src/linkhop/deps.py backend/src/linkhop/routes/services.py \
        backend/tests/test_deps.py backend/tests/routes/test_services.py
git commit -m "feat(backend): register YouTube Music adapter"
```

---

### Task 6: Frontend — Brand-Farbe

**Files:**
- Modify: `frontend/src/lib/components/ServiceItem.svelte:134-136`

- [ ] **Step 1: Brand-Farbe ergänzen**

In `frontend/src/lib/components/ServiceItem.svelte`, nach der Zeile
`.row[data-service-id='tidal']   { --brand: #25d1da; }` einfügen:

```css
  .row[data-service-id='youtube_music'] { --brand: #ff0000; }
```

- [ ] **Step 2: Frontend-Tests laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle PASS (die Komponente rendert Services generisch aus der API; die CSS-Regel bricht nichts).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/ServiceItem.svelte
git commit -m "feat(frontend): YouTube Music brand color"
```

---

### Task 7: Helm-Chart

**Files:**
- Modify: `helm/linkhop/values.yaml:52-54`
- Modify: `helm/linkhop/templates/backend-deployment.yaml:48-49`
- Modify: `helm/linkhop/Chart.yaml:5`

- [ ] **Step 1: Value ergänzen**

In `helm/linkhop/values.yaml`, nach `enableTidal: true` einfügen:

```yaml
  # -- YouTube Music braucht keine Credentials (unauthentifizierte ytmusicapi).
  enableYoutubeMusic: true
```

- [ ] **Step 2: Env-Var im Deployment verdrahten**

In `helm/linkhop/templates/backend-deployment.yaml`, nach dem `LINKHOP_ENABLE_TIDAL`-Block einfügen:

```yaml
            - name: LINKHOP_ENABLE_YOUTUBE_MUSIC
              value: {{ .Values.config.enableYoutubeMusic | quote }}
```

- [ ] **Step 3: Chart-Version bumpen**

In `helm/linkhop/Chart.yaml`: `version: 0.1.0` → `version: 0.2.0` (neues Feature, kein Breaking Change).

- [ ] **Step 4: Chart validieren**

Run: `helm lint helm/linkhop && helm template helm/linkhop --set config.databaseUrl=postgres://x --set ingress.host=example.com | grep -A1 LINKHOP_ENABLE_YOUTUBE_MUSIC`
Expected: `1 chart(s) linted, 0 chart(s) failed` und die gerenderte Env-Var mit Wert `"true"`.
(Falls `helm dependency build` wegen des Redis-Subcharts verlangt wird, vorher ausführen.)

- [ ] **Step 5: Commit**

```bash
git add helm/linkhop/values.yaml helm/linkhop/templates/backend-deployment.yaml helm/linkhop/Chart.yaml
git commit -m "feat(helm): enableYoutubeMusic value"
```

---

### Task 8: Dokumentation

**Files:**
- Modify: `backend/README.md:50` (Env-Var-Tabelle)

- [ ] **Step 1: Env-Var-Tabelle aktualisieren**

In `backend/README.md` die Zeile

```markdown
| `LINKHOP_ENABLE_SPOTIFY` / `_DEEZER` / `_TIDAL` | all `true` | Toggle individual adapters. |
```

ersetzen durch:

```markdown
| `LINKHOP_ENABLE_SPOTIFY` / `_DEEZER` / `_TIDAL` / `_YOUTUBE_MUSIC` | all `true` | Toggle individual adapters. |
```

Das Haupt-README listet YouTube Music bereits korrekt (`ytmusicapi`, unofficial) — keine Änderung nötig; nach diesem Plan stimmt die Tabelle erstmals mit der Realität überein.

- [ ] **Step 2: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): document LINKHOP_ENABLE_YOUTUBE_MUSIC"
```

---

### Task 9: Live-Integrationstests

**Files:**
- Modify: `backend/tests/integration/test_real_adapters.py`

- [ ] **Step 1: Adapter in Live-Fixture aufnehmen und Tests ergänzen**

In `backend/tests/integration/test_real_adapters.py`:

Imports ergänzen:

```python
from ytmusicapi import YTMusic

from linkhop.adapters.youtube_music import YouTubeMusicAdapter
```

Im `clients`-Fixture-Dict nach dem `"tidal"`-Eintrag:

```python
            "youtube_music": YouTubeMusicAdapter(client=YTMusic()),
```

Am Dateiende anhängen:

```python
# Rick Astley "Never Gonna Give You Up" — einer der stabilsten Katalog-Einträge
# auf YouTube überhaupt; swap if the video ever disappears.
_YTM_TRACK_URL = "https://music.youtube.com/watch?v=dQw4w9WgXcQ"


async def test_youtube_music_resolve_track(clients):
    parsed = parse(_YTM_TRACK_URL)
    source = await clients["youtube_music"].resolve(parsed)
    assert source is not None
    assert source.title
    assert source.duration_ms


async def test_spotify_to_youtube_music_metadata(clients):
    # YT Music hat kein ISRC — es darf nur metadata-Hits geben, deren Scoring
    # übernimmt die Pipeline (hier nicht unter Test).
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    hits = await clients["youtube_music"].search(source, ContentType(parsed.type))
    assert hits
    assert all(h.match == "metadata" for h in hits)


async def test_youtube_music_to_deezer_metadata(clients):
    parsed = parse(_YTM_TRACK_URL)
    source = await clients["youtube_music"].resolve(parsed)
    assert source is not None
    hits = await clients["deezer"].search(source, ContentType(parsed.type))
    assert hits
```

- [ ] **Step 2: Skip-Verhalten verifizieren (ohne Live-Flag)**

Run: `cd backend && pytest tests/integration/ -v`
Expected: alle Tests SKIPPED (`Live tests deaktiviert…`).

- [ ] **Step 3: Live laufen lassen (optional, braucht Internet + Spotify/Tidal-Creds)**

Run: `cd backend && LINKHOP_LIVE_TESTS=1 pytest tests/integration/ -v -k youtube_music`
Expected: die drei neuen Tests PASS. (Ohne Spotify-Creds schlägt `test_spotify_to_youtube_music_metadata` im Fixture fehl — dann nur `test_youtube_music_resolve_track` und `test_youtube_music_to_deezer_metadata` prüfen.)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_real_adapters.py
git commit -m "test(backend): YouTube Music live integration tests"
```

---

### Task 10: Abschluss-Verifikation

**Files:** keine neuen Änderungen — reiner Verifikationslauf.

- [ ] **Step 1: Gesamte Backend-Suite + Lint**

Run: `cd backend && pytest && ruff check src tests && mypy src`
Expected: alle Tests PASS, kein Lint-/Typ-Fehler.

- [ ] **Step 2: Frontend-Tests**

Run: `cd frontend && pnpm test`
Expected: alle PASS.

- [ ] **Step 3: End-to-End-Smoke (manuell, optional)**

Backend + Frontend lokal starten (siehe Haupt-README Quick start), dann eine Deezer-Track-URL einfügen.
Expected: Ergebnisliste enthält eine YouTube-Music-Zeile mit Link `music.youtube.com/watch?v=…` und ggf. `~match`-Badge. Gegenrichtung: YT-Music-URL einfügen → Deezer-Treffer.
