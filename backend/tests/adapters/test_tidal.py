import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.base import AdapterError
from linkhop.adapters.tidal import TidalAdapter, _iso8601_to_ms, _pick_cover_art
from linkhop.models.domain import ContentType, ResolvedContent
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


def test_iso8601_to_ms_accepts_decimal_seconds():
    # ISO 8601 erlaubt Dezimal-Sekunden; Tidal liefert sie selten, aber die Spec
    # sieht sie vor — Matcher darf hier nicht silently 0 zurückgeben.
    assert _iso8601_to_ms("PT30.5S") == 30_500
    assert _iso8601_to_ms("PT1M0.25S") == 60_250


def test_iso8601_to_ms_rejects_bare_pt():
    # "PT" ohne Designatoren ist spec-widrig; wäre der Regex permissiv, würde
    # ein 0-ms-Track aus unserem Matching mit hoher Confidence herauskommen.
    assert _iso8601_to_ms("PT") is None


@respx.mock
async def test_resolve_track_handles_empty_artists(adapter: TidalAdapter):
    # Tidal liefert bei regional gefilterten Artists bisweilen data:[] — das
    # darf nicht crashen und muss artists=() ergeben.
    payload = {
        "data": {
            "id": "77640617",
            "type": "tracks",
            "attributes": {"title": "Nightcall", "duration": "PT4M17S"},
            "relationships": {
                "artists": {"data": []},
                "albums": {"data": []},
            },
        },
        "included": [],
    }
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(json=fix("tidal_token.json"))
    respx.get("https://openapi.tidal.com/v2/tracks/77640617").respond(json=payload)
    result = await adapter.resolve(ParsedUrl("tidal", "track", "77640617"))
    assert result is not None
    assert result.artists == ()
    assert result.album is None


def test_pick_cover_art_falls_back_to_first_file_without_640_750():
    # Wenn keine Datei eine 640- oder 750-px-Variante ist, liefert der Helper
    # das erste File — nicht leer, nicht None.
    rels = {"coverArt": {"data": [{"type": "artworks", "id": "cover-x"}]}}
    included = {
        ("artworks", "cover-x"): {
            "id": "cover-x",
            "type": "artworks",
            "attributes": {
                "files": [
                    {"href": "https://example.com/80.jpg", "meta": {"width": 80}},
                    {"href": "https://example.com/1280.jpg", "meta": {"width": 1280}},
                ]
            },
        }
    }
    assert _pick_cover_art(rels, included) == "https://example.com/80.jpg"


def test_pick_cover_art_returns_empty_when_no_coverart():
    # Kein coverArt-Relationship → leerer String, nicht None (ResolvedContent.artwork: str).
    assert _pick_cover_art({}, {}) == ""


# --- search() -----------------------------------------------------------------
# Quelle (meta) kommt im realen Flow von einem anderen Adapter (Spotify/Deezer);
# die Tests simulieren das mit einem service="spotify"-Meta-Objekt, damit die
# Cross-Service-Semantik der Matcher-Pipeline im Test sichtbar bleibt.

_META_TRACK_WITH_ISRC = ResolvedContent(
    service="spotify",
    type=ContentType.TRACK,
    id="sp1",
    url="https://open.spotify.com/track/sp1",
    title="Nightcall",
    artists=("Kavinsky",),
    album="OutRun",
    duration_ms=257_000,
    isrc="FR6V81200001",
    upc=None,
    artwork="",
)

_META_TRACK_NO_ISRC = ResolvedContent(
    service="spotify",
    type=ContentType.TRACK,
    id="sp1",
    url="https://open.spotify.com/track/sp1",
    title="Nightcall",
    artists=("Kavinsky",),
    album="OutRun",
    duration_ms=257_000,
    isrc=None,
    upc=None,
    artwork="",
)

_META_ALBUM_WITH_UPC = ResolvedContent(
    service="spotify",
    type=ContentType.ALBUM,
    id="sp_alb",
    url="https://open.spotify.com/album/sp_alb",
    title="OutRun",
    artists=("Kavinsky",),
    album=None,
    duration_ms=None,
    isrc=None,
    upc="0602537360697",
    artwork="",
)

_META_ARTIST = ResolvedContent(
    service="spotify",
    type=ContentType.ARTIST,
    id="sp_art",
    url="https://open.spotify.com/artist/sp_art",
    title="Kavinsky",
    artists=("Kavinsky",),
    album=None,
    duration_ms=None,
    isrc=None,
    upc=None,
    artwork="",
)


@respx.mock
async def test_search_track_by_isrc_returns_isrc_match(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    route = respx.get("https://openapi.tidal.com/v2/tracks").respond(
        json=fix("tidal_search_isrc.json")
    )
    hits = await adapter.search(_META_TRACK_WITH_ISRC, ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].service == "tidal"
    assert hits[0].id == "77640617"
    assert hits[0].url == "https://tidal.com/track/77640617"
    assert hits[0].match == "isrc"
    assert hits[0].confidence == 1.0
    # ISRC wandert als filter[isrc]-Query an /tracks, NICHT über /searchResults —
    # das ist der Hot-Path, der Cross-Service-Identität über eine Round-Trip gibt.
    params = route.calls.last.request.url.params
    assert params["filter[isrc]"] == "FR6V81200001"
    assert params["countryCode"] == "DE"


@respx.mock
async def test_search_album_by_upc_returns_upc_match(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    route = respx.get("https://openapi.tidal.com/v2/albums").respond(
        json=fix("tidal_search_upc.json")
    )
    hits = await adapter.search(_META_ALBUM_WITH_UPC, ContentType.ALBUM)
    assert len(hits) == 1
    assert hits[0].service == "tidal"
    assert hits[0].id == "17927863"
    assert hits[0].url == "https://tidal.com/album/17927863"
    assert hits[0].match == "upc"
    assert hits[0].confidence == 1.0
    params = route.calls.last.request.url.params
    assert params["filter[barcodeId]"] == "0602537360697"
    assert params["countryCode"] == "DE"


@respx.mock
async def test_search_track_metadata_fallback(adapter: TidalAdapter):
    # Kein ISRC in meta → Metadata-Pfad via /searchResults/{query}/relationships/tracks.
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    route = respx.get(
        "https://openapi.tidal.com/v2/searchResults/Kavinsky%20Nightcall/relationships/tracks"
    ).respond(json=fix("tidal_search_metadata.json"))
    hits = await adapter.search(_META_TRACK_NO_ISRC, ContentType.TRACK)
    assert len(hits) == 3
    # data[]-Reihenfolge ist Tidal-Ranking — ID[0] muss first hit bleiben.
    assert hits[0].id == "77640617"
    assert hits[0].url == "https://tidal.com/track/77640617"
    assert all(h.match == "metadata" for h in hits)
    assert all(h.confidence == 0.0 for h in hits)  # Matcher setzt finalen Score
    params = route.calls.last.request.url.params
    # Bewusst KEIN include= — data[] reicht für URL/ID, Sideload wäre tote Bandbreite.
    assert "include" not in params
    assert params["countryCode"] == "DE"


@respx.mock
async def test_search_artist_uses_searchresults(adapter: TidalAdapter):
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    route = respx.get(
        "https://openapi.tidal.com/v2/searchResults/Kavinsky/relationships/artists"
    ).respond(json=fix("tidal_search_artists.json"))
    hits = await adapter.search(_META_ARTIST, ContentType.ARTIST)
    assert len(hits) == 2
    assert hits[0].service == "tidal"
    assert hits[0].id == "3528266"
    assert hits[0].url == "https://tidal.com/artist/3528266"
    assert hits[0].match == "metadata"
    assert hits[0].confidence == 0.0
    params = route.calls.last.request.url.params
    assert "include" not in params


@respx.mock
async def test_search_track_empty_result_returns_empty_list(adapter: TidalAdapter):
    # ISRC nicht im Tidal-Katalog → leere Ergebnisliste, kein Crash.
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    respx.get("https://openapi.tidal.com/v2/tracks").respond(
        json={"data": [], "links": {"self": "/tracks"}}
    )
    hits = await adapter.search(_META_TRACK_WITH_ISRC, ContentType.TRACK)
    assert hits == []


@respx.mock
async def test_search_metadata_query_path_is_url_encoded(adapter: TidalAdapter):
    # Der Query wird als Pfad-Segment eingebettet — Leerzeichen/Sonderzeichen
    # MÜSSEN encoded werden, sonst splittet Tidal den Pfad falsch auf.
    respx.post("https://auth.tidal.com/v1/oauth2/token").respond(
        json=fix("tidal_token.json")
    )
    meta = ResolvedContent(
        service="spotify",
        type=ContentType.TRACK,
        id="sp1",
        url="https://open.spotify.com/track/sp1",
        title="Hello/World",
        artists=("Foo & Bar",),
        album=None,
        duration_ms=None,
        isrc=None,
        upc=None,
        artwork="",
    )
    route = respx.get(
        "https://openapi.tidal.com/v2/searchResults/"
        "Foo%20%26%20Bar%20Hello%2FWorld/relationships/tracks"
    ).respond(json={"data": [], "included": [], "links": {"self": "/searchResults"}})
    hits = await adapter.search(meta, ContentType.TRACK)
    assert hits == []
    assert route.call_count == 1
