import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.deezer import DeezerAdapter
from linkhop.models.domain import ContentType, ResolvedContent
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield DeezerAdapter(client=client)


@respx.mock
async def test_resolve_track(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/3135556").respond(json=fix("deezer_track.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "track", "3135556"))
    assert result is not None
    assert result.title == "Nightcall"
    assert result.duration_ms == 257000
    assert result.isrc == "FR6V81200001"


@respx.mock
async def test_resolve_album(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/album/302127").respond(json=fix("deezer_album.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "album", "302127"))
    assert result is not None
    assert result.upc == "602537360697"


@respx.mock
async def test_resolve_artist(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/artist/27").respond(json=fix("deezer_artist.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "artist", "27"))
    assert result is not None
    assert result.title == "Kavinsky"


@respx.mock
async def test_resolve_404_returns_none(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/missing").respond(
        json={"error": {"code": 800, "message": "no data"}}
    )
    assert await adapter.resolve(ParsedUrl("deezer", "track", "missing")) is None


@respx.mock
async def test_search_by_isrc(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/isrc:FR6V81200001").respond(
        json=fix("deezer_track.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].match == "isrc"


@respx.mock
async def test_search_fallback_metadata(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/search/track").respond(json=fix("deezer_search_track.json"))
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) >= 1
    assert hits[0].match == "metadata"


@respx.mock
async def test_search_by_upc_returns_album_hit(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/album/upc:602537360697").respond(
        json=fix("deezer_album.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.ALBUM, id="x",
        url="", title="OutRun", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc="602537360697", artwork="",
    )
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].match == "upc"
    assert hits[0].confidence == 1.0


@respx.mock
async def test_search_artist_returns_metadata_hit(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/search/artist").respond(
        json=fix("deezer_search_artist.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.ARTIST, id="x",
        url="", title="Kavinsky", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.ARTIST)
    assert len(hits) == 1
    assert hits[0].match == "metadata"
    assert hits[0].confidence == 0.0


@respx.mock
async def test_search_query_strips_embedded_quotes(adapter: DeezerAdapter):
    search_route = respx.get("https://api.deezer.com/search/track").respond(
        json=fix("deezer_search_track.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title='She Said "Yeah"', artists=('AC/DC "The Band"',), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    await adapter.search(source, ContentType.TRACK)
    q = search_route.calls.last.request.url.params["q"]
    assert q == 'track:"She Said Yeah" artist:"AC/DC The Band"'


@respx.mock
async def test_search_omits_artist_clause_when_artists_empty(adapter: DeezerAdapter):
    search_route = respx.get("https://api.deezer.com/search/track").respond(
        json=fix("deezer_search_track.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=(), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    await adapter.search(source, ContentType.TRACK)
    q = search_route.calls.last.request.url.params["q"]
    assert q == 'track:"Nightcall"'
    assert "artist:" not in q


@respx.mock
async def test_resolve_raises_on_5xx(adapter: DeezerAdapter):
    from linkhop.adapters.base import AdapterError

    respx.get("https://api.deezer.com/track/boom").respond(status_code=500)
    with pytest.raises(AdapterError):
        await adapter.resolve(ParsedUrl("deezer", "track", "boom"))


@respx.mock
async def test_search_raises_on_non_800_error_payload(adapter: DeezerAdapter):
    # Deezer signals real service errors via a 200+error payload; code 800 = not found
    # (handled as None), other codes (e.g. 4=quota) must surface as AdapterError.
    from linkhop.adapters.base import AdapterError

    respx.get("https://api.deezer.com/search/track").respond(
        json={"error": {"code": 4, "message": "Quota exceeded"}}
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    with pytest.raises(AdapterError):
        await adapter.search(source, ContentType.TRACK)


@respx.mock
async def test_search_album_metadata_fallback(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/search/album").respond(
        json=fix("deezer_search_album.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.ALBUM, id="x",
        url="", title="OutRun", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].match == "metadata"
    assert hits[0].confidence == 0.0


@respx.mock
async def test_search_isrc_miss_does_not_fall_through_to_metadata(adapter: DeezerAdapter):
    # An ISRC lookup miss must return [] without performing a second /search/track request —
    # otherwise the matching engine receives unexpected metadata hits.
    isrc_route = respx.get("https://api.deezer.com/track/isrc:NOPE").respond(
        json={"error": {"code": 800, "message": "no data"}}
    )
    metadata_route = respx.get("https://api.deezer.com/search/track").respond(
        json=fix("deezer_search_track.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc="NOPE", upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert hits == []
    assert isrc_route.call_count == 1
    assert metadata_route.call_count == 0
