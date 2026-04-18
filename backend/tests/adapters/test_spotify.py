import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.models.domain import ContentType, ResolvedContent
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


@respx.mock
async def test_resolve_raises_on_token_fetch_failure(adapter: SpotifyAdapter):
    from linkhop.adapters.base import AdapterError

    respx.post("https://accounts.spotify.com/api/token").respond(status_code=503)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))


@respx.mock
async def test_resolve_invalidates_token_on_401(adapter: SpotifyAdapter):
    from linkhop.adapters.base import AdapterError

    token_route = respx.post("https://accounts.spotify.com/api/token").respond(
        json=fix("spotify_token.json")
    )
    respx.get("https://api.spotify.com/v1/tracks/revoked").respond(status_code=401)
    respx.get("https://api.spotify.com/v1/tracks/6habFhsOp2NvshLv26DqMb").respond(
        json=fix("spotify_track.json")
    )
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("spotify", "track", "revoked"))
    await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))
    assert token_route.call_count == 2


@respx.mock
async def test_search_by_isrc_returns_hit(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_track.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].match == "isrc"
    assert hits[0].confidence == 1.0
    assert hits[0].service == "spotify"


@respx.mock
async def test_search_falls_back_to_metadata(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_track.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) >= 1
    assert hits[0].match == "metadata"


@respx.mock
async def test_search_by_upc_returns_album_hit(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_album.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.ALBUM, id="1",
        url="https://tidal.com/album/1", title="OutRun",
        artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc="602537360697", artwork="",
    )
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].match == "upc"
    assert hits[0].confidence == 1.0
    assert hits[0].service == "spotify"


@respx.mock
async def test_search_artist_returns_metadata_hit(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_artist.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.ARTIST, id="1",
        url="https://tidal.com/artist/1", title="Kavinsky",
        artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.ARTIST)
    assert len(hits) == 1
    assert hits[0].match == "metadata"
    assert hits[0].confidence == 0.0
    assert hits[0].service == "spotify"


@respx.mock
async def test_search_query_strips_embedded_quotes(adapter: SpotifyAdapter):
    # Titles like `She Said "Yeah"` would break the Spotify phrase-query syntax.
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    search_route = respx.get("https://api.spotify.com/v1/search").respond(
        json=fix("spotify_search_track.json")
    )
    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title='She Said "Yeah"',
        artists=('AC/DC "The Band"',), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    await adapter.search(source, ContentType.TRACK)
    q = search_route.calls.last.request.url.params["q"]
    assert q == 'track:"She Said Yeah" artist:"AC/DC The Band"'


@respx.mock
async def test_search_omits_artist_clause_when_artists_empty(adapter: SpotifyAdapter):
    # Empty artists tuple must not produce a no-op `artist:""` clause.
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    search_route = respx.get("https://api.spotify.com/v1/search").respond(
        json=fix("spotify_search_track.json")
    )
    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=(), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    await adapter.search(source, ContentType.TRACK)
    q = search_route.calls.last.request.url.params["q"]
    assert q == 'track:"Nightcall"'
    assert "artist:" not in q
