import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.apple_music import AppleMusicAdapter
from linkhop.adapters.base import AdapterError
from linkhop.models.domain import ContentType, ResolvedContent
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


def _source(**overrides) -> ResolvedContent:
    defaults = dict(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="OutRun",
        duration_ms=258000, isrc=None, upc=None, artwork="",
    )
    defaults.update(overrides)
    return ResolvedContent(**defaults)


@respx.mock
async def test_search_track_with_isrc_uses_metadata_search(adapter: AppleMusicAdapter):
    # Ein Track mit ISRC muss trotzdem direkt in die Metadaten-Suche gehen —
    # der /lookup-Endpunkt mit isrc darf dafür gar nicht erst angefragt werden.
    lookup_route = respx.get(LOOKUP).respond(json=EMPTY)
    respx.get(SEARCH).respond(json=fix("apple_music_search_song.json"))
    hits = await adapter.search(_source(isrc="FR6V81200001"), ContentType.TRACK)
    assert len(hits) == 3
    assert all(h.match == "metadata" for h in hits)
    assert lookup_route.call_count == 0


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
async def test_search_upc_miss_does_not_fall_through_to_metadata(adapter: AppleMusicAdapter):
    # Ein UPC-Miss muss [] liefern, ohne einen zweiten /search-Request —
    # sonst bekommt die Matching-Engine unerwartete metadata-Hits.
    upc_route = respx.get(LOOKUP, params={"upc": "NOPE"}).respond(json=EMPTY)
    metadata_route = respx.get(SEARCH).respond(json=fix("apple_music_search_song.json"))
    source = _source(type=ContentType.ALBUM, album=None, duration_ms=None, upc="NOPE")
    hits = await adapter.search(source, ContentType.ALBUM)
    assert hits == []
    assert upc_route.call_count == 1
    assert metadata_route.call_count == 0


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
