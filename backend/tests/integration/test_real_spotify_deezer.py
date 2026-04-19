import os

import httpx
import pytest

from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.models.domain import ContentType
from linkhop.url_parser import parse

pytestmark = pytest.mark.skipif(
    not os.environ.get("LINKHOP_LIVE_TESTS"),
    reason="Live tests deaktiviert. Setze LINKHOP_LIVE_TESTS=1 und Credentials.",
)


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
        }


async def test_spotify_to_deezer_via_isrc(clients):
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    hits = await clients["deezer"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_deezer_to_spotify_via_isrc(clients):
    parsed = parse("https://www.deezer.com/track/3135556")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    hits = await clients["spotify"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)
