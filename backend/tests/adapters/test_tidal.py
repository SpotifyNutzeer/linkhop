import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.base import AdapterError
from linkhop.adapters.tidal import TidalAdapter, _iso8601_to_ms
from linkhop.models.domain import ContentType
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield TidalAdapter(client=client, client_id="cid", client_secret="csec")


@respx.mock
async def test_resolve_track(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/tracks/77640617").respond(
        json=fix("tidal_track.json")
    )
    result = await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    assert result is not None
    assert result.type == ContentType.TRACK
    assert result.id == "77640617"
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.album == "OutRun"
    assert result.isrc == "FR6V81200001"
    assert result.duration_ms == 257_000
    assert result.upc is None
    assert result.url == "https://tidal.com/track/77640617"


@respx.mock
async def test_resolve_album(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/albums/17927863").respond(
        json=fix("tidal_album.json")
    )
    result = await adapter.resolve(ParsedUrl("tidal", "album", "17927863"))
    assert result is not None
    assert result.type == ContentType.ALBUM
    assert result.title == "OutRun"
    assert result.artists == ("Kavinsky",)
    assert result.upc == "0602537360697"
    assert result.isrc is None
    # _pick_cover_art soll die 640x640-Variante bevorzugen (nicht 80 oder 1280).
    assert result.artwork == "https://resources.tidal.com/images/outrun/640x640.jpg"


@respx.mock
async def test_resolve_artist(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/artists/3528266").respond(
        json=fix("tidal_artist.json")
    )
    result = await adapter.resolve(ParsedUrl("tidal", "artist", "3528266"))
    assert result is not None
    assert result.type == ContentType.ARTIST
    assert result.title == "Kavinsky"
    assert result.artists == ("Kavinsky",)


@respx.mock
async def test_resolve_returns_none_on_404(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/tracks/missing").respond(status_code=404)
    assert await adapter.resolve(ParsedUrl("tidal", "track", "missing")) is None


@respx.mock
async def test_resolve_sends_country_code(adapter: TidalAdapter):
    # Availability-Filter — regressionsgefährlich, explizit asserten.
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    route = respx.get("https://openapi.tidal.com/v2/tracks/77640617").respond(
        json=fix("tidal_track.json")
    )
    await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    params = route.calls.last.request.url.params
    assert params["countryCode"] == "DE"
    assert params["include"] == "artists,albums"


@respx.mock
async def test_resolve_caches_token(adapter: TidalAdapter):
    token_route = respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    respx.get("https://openapi.tidal.com/v2/tracks/77640617").respond(
        json=fix("tidal_track.json")
    )
    await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    assert token_route.call_count == 1


@respx.mock
async def test_resolve_raises_on_token_fetch_failure(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(status_code=503)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))


@respx.mock
async def test_resolve_raises_on_5xx(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/tracks/boom").respond(status_code=500)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("tidal", "track", "boom"))


@respx.mock
async def test_resolve_invalidates_token_on_401(adapter: TidalAdapter):
    token_route = respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    respx.get("https://openapi.tidal.com/v2/tracks/revoked").respond(status_code=401)
    respx.get("https://openapi.tidal.com/v2/tracks/77640617").respond(
        json=fix("tidal_track.json")
    )
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("tidal", "track", "revoked"))
    await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    assert token_route.call_count == 2


def test_iso8601_to_ms_parses_standard_forms():
    assert _iso8601_to_ms("PT4M17S") == 257_000
    assert _iso8601_to_ms("PT46M17S") == 2_777_000
    assert _iso8601_to_ms("PT1H2M3S") == 3_723_000
    assert _iso8601_to_ms("PT30S") == 30_000
    assert _iso8601_to_ms(None) is None
    assert _iso8601_to_ms("nonsense") is None
