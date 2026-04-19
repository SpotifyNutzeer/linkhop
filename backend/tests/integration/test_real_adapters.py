import os

import httpx
import pytest

from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.adapters.tidal import TidalAdapter
from linkhop.models.domain import ContentType
from linkhop.url_parser import parse

# Sowohl Marker als auch Env-Gate: `pytest -m "not integration"` schließt die
# Tests aus (marker-Sweep in CI), `LINKHOP_LIVE_TESTS=1` schaltet sie live
# (Env-Sweep lokal). Ohne den Marker wäre die pyproject-Registrierung dead code.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LINKHOP_LIVE_TESTS"),
        reason="Live tests deaktiviert. Setze LINKHOP_LIVE_TESTS=1 und Credentials.",
    ),
]


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


async def test_spotify_to_deezer_via_isrc(clients):
    # Stabile, bekannte Track-ID — swap ID if Spotify returns 404 for this item.
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    # Ohne ISRC kann der nachgelagerte Deezer-Search keine `match=="isrc"`-Hits
    # produzieren; der Test würde unter "no ISRC match" scheitern und die Ursache
    # (Spotify ohne ISRC-Payload) verschweigen.
    assert source.isrc, "Spotify resolve returned no ISRC — ID rotated?"
    hits = await clients["deezer"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_deezer_to_spotify_via_isrc(clients):
    # Stabile, bekannte Track-ID — swap ID if Deezer returns error code 800.
    parsed = parse("https://www.deezer.com/track/3135556")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Deezer resolve returned no ISRC — ID rotated?"
    hits = await clients["spotify"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_tidal_to_spotify_via_isrc(clients):
    # Track 1566 = Weather Report "Crystal" (1972), ISRC USSM10023644 — klassischer
    # Katalog-Eintrag, stabiler als aktuelle Releases. Am 2026-04-19 als Tidal-Smoke
    # live geprüft; swap if Tidal 404s.
    # Grüner Test verifiziert implizit die 3 offenen Task-3-Fragen:
    # (1) httpx' filter%5Bisrc%5D-Encoding wird von Tidal akzeptiert,
    # (2) countryCode=DE liefert nicht-leere Resolve-Response,
    # (3) Tidal liefert ISRC im attributes-Feld für den Happy-Path.
    parsed = parse("https://tidal.com/track/1566")
    source = await clients["tidal"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Tidal resolve returned no ISRC — ID rotated?"
    hits = await clients["spotify"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_spotify_to_tidal_via_isrc(clients):
    # Prüft Tidal-SEARCH-Pfad (filter[isrc]) — Gegenprobe zu oben, wo Tidal nur
    # resolved wurde. Wenn dieser Test grün ist, akzeptiert Tidal die
    # %5B%5D-Encodings auf der /tracks-Route.
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    assert source.isrc, "Spotify resolve returned no ISRC — ID rotated?"
    hits = await clients["tidal"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)
