import os

import httpx
import pytest
from ytmusicapi import YTMusic

from linkhop.adapters.apple_music import AppleMusicAdapter
from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.adapters.tidal import TidalAdapter
from linkhop.adapters.youtube_music import YouTubeMusicAdapter
from linkhop.models.domain import ContentType
from linkhop.url_parser import ParsedUrl, parse

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
            # .get() statt []: LINKHOP_LIVE_TESTS=1 -k youtube_music darf im
            # Fixture-Setup nicht an fehlenden Spotify/Tidal-Creds scheitern.
            "spotify": SpotifyAdapter(
                client=http,
                client_id=os.environ.get("LINKHOP_SPOTIFY_CLIENT_ID", ""),
                client_secret=os.environ.get("LINKHOP_SPOTIFY_CLIENT_SECRET", ""),
            ),
            "deezer": DeezerAdapter(client=http),
            "tidal": TidalAdapter(
                client=http,
                client_id=os.environ.get("LINKHOP_TIDAL_CLIENT_ID", ""),
                client_secret=os.environ.get("LINKHOP_TIDAL_CLIENT_SECRET", ""),
            ),
            "youtube_music": YouTubeMusicAdapter(client=YTMusic()),
            "apple_music": AppleMusicAdapter(client=http, storefront="de"),
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


async def test_deezer_to_apple_music_via_metadata(clients):
    # Credential-freier Flow: Deezer liefert Metadaten, Apple-Search matcht.
    # Der Adapter hat keinen ISRC-Pfad für Tracks (iTunes liefert dafür real
    # immer 0 Treffer) — es geht direkt in die Metadaten-Suche.
    parsed = parse("https://www.deezer.com/track/3135556")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    assert source.title, "Deezer resolve returned no title"
    assert source.artists, "Deezer resolve returned no artists"

    hits = await clients["apple_music"].search(source, ContentType(parsed.type))
    assert hits, "No Apple Music hits found for Deezer track"
    assert any(h.match == "metadata" for h in hits)


async def test_apple_music_resolve_from_search_hit(clients):
    # Credential-freie Validierung: die Apple-ID kommt aus dem Metadaten-Hit,
    # resolve lädt Metadaten nach (die Pipeline macht in _score_hit dasselbe).
    parsed = parse("https://www.deezer.com/track/3135556")
    deezer_source = await clients["deezer"].resolve(parsed)
    assert deezer_source is not None

    # Search Apple Music by Deezer metadata
    apple_hits = await clients["apple_music"].search(deezer_source, ContentType.TRACK)
    assert apple_hits, "No Apple Music hits for Deezer track metadata"

    # Resolve the first Apple Music hit liefert vollständige Metadaten
    apple_source = await clients["apple_music"].resolve(
        ParsedUrl("apple_music", "track", apple_hits[0].id)
    )
    assert apple_source is not None
    assert apple_source.title, "Apple Music track has no title"
    assert apple_source.duration_ms, "Apple Music track has no duration"
    assert apple_source.artists, "Apple Music track has no artists"
    # iTunes-Antworten enthalten keine ISRCs — das ist dokumentiertes Verhalten.
    assert apple_source.isrc is None, "iTunes should not return ISRC"


async def test_deezer_to_apple_music_album_via_upc(clients):
    # Daft Punk "Discovery" — stabiler Katalog-Eintrag. Live verifiziert:
    # iTunes findet UPC 724384960650 (2026-07).
    parsed = parse("https://www.deezer.com/album/302127")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    assert source.upc, "Deezer resolve returned no UPC — ID rotated?"

    hits = await clients["apple_music"].search(source, ContentType.ALBUM)
    assert any(h.match == "upc" for h in hits)
