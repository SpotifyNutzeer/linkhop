import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.models.domain import ContentType
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield SpotifyAdapter(client=client, client_id="cid", client_secret="csec")


@respx.mock
async def test_resolve_track(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/tracks/6habFhsOp2NvshLv26DqMb").respond(
        json=fix("spotify_track.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))
    assert result is not None
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.isrc == "FR6V81200001"
    assert result.duration_ms == 257000
    assert result.type == ContentType.TRACK
    assert result.artwork.startswith("https://i.scdn.co/image")


@respx.mock
async def test_resolve_album(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/albums/2dIGnmEIy1WZIcZCFSj6i8").respond(
        json=fix("spotify_album.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "album", "2dIGnmEIy1WZIcZCFSj6i8"))
    assert result is not None
    assert result.title == "OutRun"
    assert result.upc == "602537360697"


@respx.mock
async def test_resolve_artist(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/artists/0du5cEVh5yTK9QJze8zA0C").respond(
        json=fix("spotify_artist.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "artist", "0du5cEVh5yTK9QJze8zA0C"))
    assert result is not None
    assert result.title == "Kavinsky"
    assert result.type == ContentType.ARTIST


@respx.mock
async def test_resolve_returns_none_on_404(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/tracks/missing").respond(status_code=404)
    assert await adapter.resolve(ParsedUrl("spotify", "track", "missing")) is None


@respx.mock
async def test_resolve_caches_token(adapter: SpotifyAdapter):
    token_route = respx.post("https://accounts.spotify.com/api/token").respond(
        json=fix("spotify_token.json")
    )
    respx.get("https://api.spotify.com/v1/tracks/6habFhsOp2NvshLv26DqMb").respond(
        json=fix("spotify_track.json")
    )
    await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))
    await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))
    assert token_route.call_count == 1


@respx.mock
async def test_resolve_raises_on_5xx(adapter: SpotifyAdapter):
    from linkhop.adapters.base import AdapterError

    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/tracks/boom").respond(status_code=500)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("spotify", "track", "boom"))
