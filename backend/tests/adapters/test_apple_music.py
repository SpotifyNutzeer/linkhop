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
