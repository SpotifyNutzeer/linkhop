import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from linkhop.adapters.base import AdapterError
from linkhop.adapters.youtube_music import YouTubeMusicAdapter
from linkhop.models.domain import ContentType, ResolvedContent
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"

_BROWSE_ID = "MPREb_K0OB6WlC9bF"
_PLAYLIST_ID = "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk"
_CHANNEL_ID = "UC0FvDIzS3wnvBJN1DyGZv6g"


def fix(name: str):
    return json.loads((FIX / name).read_text())


def make_source(type_: ContentType, **overrides) -> ResolvedContent:
    base = dict(
        service="spotify", type=type_, id="x", url="",
        title="Nightcall", artists=("Kavinsky",), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )
    base.update(overrides)
    return ResolvedContent(**base)


@pytest.fixture
def yt() -> MagicMock:
    # ytmusicapi nutzt eigenes `requests`, respx greift nicht — daher wird die
    # YTMusic-Instanz selbst gemockt (sync-Methoden, vom Adapter via to_thread gerufen).
    return MagicMock()


@pytest.fixture
def adapter(yt: MagicMock) -> YouTubeMusicAdapter:
    return YouTubeMusicAdapter(client=yt)


async def test_resolve_track(adapter, yt):
    yt.get_song.return_value = fix("youtube_music_song.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "track", "AjgWa4BLvz4"))
    assert result is not None
    assert result.service == "youtube_music"
    assert result.type == ContentType.TRACK
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.duration_ms == 257000
    assert result.url == "https://music.youtube.com/watch?v=AjgWa4BLvz4"
    assert result.isrc is None
    assert result.upc is None
    # größtes Thumbnail gewinnt
    assert result.artwork.endswith("maxresdefault.jpg")
    yt.get_song.assert_called_once_with("AjgWa4BLvz4")


async def test_resolve_track_unplayable_returns_none(adapter, yt):
    yt.get_song.return_value = {
        "playabilityStatus": {"status": "ERROR", "reason": "Video unavailable"},
        "videoDetails": {"videoId": "gone4w9WgXcQ", "title": "Gone", "lengthSeconds": "1"},
    }
    result = await adapter.resolve(ParsedUrl("youtube_music", "track", "gone4w9WgXcQ"))
    assert result is None


async def test_resolve_album_from_playlist_id(adapter, yt):
    # OLAK5uy_-IDs (geteilte URLs) werden erst in eine Browse-ID übersetzt.
    yt.get_album_browse_id.return_value = _BROWSE_ID
    yt.get_album.return_value = fix("youtube_music_album.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", _PLAYLIST_ID))
    assert result is not None
    assert result.id == _BROWSE_ID
    assert result.title == "OutRun"
    assert result.artists == ("Kavinsky",)
    assert result.url == f"https://music.youtube.com/playlist?list={_PLAYLIST_ID}"
    assert result.upc is None
    yt.get_album_browse_id.assert_called_once_with(_PLAYLIST_ID)
    yt.get_album.assert_called_once_with(_BROWSE_ID)


async def test_resolve_album_from_browse_id(adapter, yt):
    # MPREb_-IDs (aus Suchergebnissen, via pipeline._score_hit) direkt auflösen.
    yt.get_album.return_value = fix("youtube_music_album.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", _BROWSE_ID))
    assert result is not None
    assert result.id == _BROWSE_ID
    yt.get_album_browse_id.assert_not_called()


async def test_resolve_album_playlist_lookup_miss_returns_none(adapter, yt):
    yt.get_album_browse_id.return_value = None
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", "OLAK5uy_unknown0"))
    assert result is None
    yt.get_album.assert_not_called()


async def test_resolve_artist(adapter, yt):
    yt.get_artist.return_value = fix("youtube_music_artist.json")
    result = await adapter.resolve(ParsedUrl("youtube_music", "artist", _CHANNEL_ID))
    assert result is not None
    assert result.type == ContentType.ARTIST
    assert result.title == "Kavinsky"
    assert result.artists == ("Kavinsky",)
    assert result.url == f"https://music.youtube.com/channel/{_CHANNEL_ID}"


async def test_resolve_album_without_audio_playlist_falls_back_to_browse_url(adapter, yt):
    album = fix("youtube_music_album.json")
    del album["audioPlaylistId"]
    yt.get_album.return_value = album
    result = await adapter.resolve(ParsedUrl("youtube_music", "album", _BROWSE_ID))
    assert result is not None
    assert result.url == f"https://music.youtube.com/browse/{_BROWSE_ID}"


async def test_resolve_wraps_library_error(adapter, yt):
    yt.get_song.side_effect = RuntimeError("YouTube changed something")
    with pytest.raises(AdapterError) as exc:
        await adapter.resolve(ParsedUrl("youtube_music", "track", "AjgWa4BLvz4"))
    assert exc.value.service == "youtube_music"


async def test_search_track(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_songs.json")
    hits = await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
    # 4 Fixture-Einträge: items[:3] schneidet den 4. ab, der kaputte 3. (ohne
    # videoId) wird übersprungen → genau 2 Hits.
    assert len(hits) == 2
    assert hits[0].id == "AjgWa4BLvz4"
    assert hits[0].url == "https://music.youtube.com/watch?v=AjgWa4BLvz4"
    assert all(h.match == "metadata" and h.confidence == 0.0 for h in hits)
    yt.search.assert_called_once_with("Kavinsky Nightcall", filter="songs", limit=3)


async def test_search_album(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_albums.json")
    source = make_source(ContentType.ALBUM, title="OutRun")
    hits = await adapter.search(source, ContentType.ALBUM)
    assert len(hits) == 2
    assert hits[0].id == "MPREb_K0OB6WlC9bF"
    assert hits[0].url == "https://music.youtube.com/browse/MPREb_K0OB6WlC9bF"
    yt.search.assert_called_once_with("Kavinsky OutRun", filter="albums", limit=3)


async def test_search_artist_uses_plain_name_query(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_artists.json")
    source = make_source(ContentType.ARTIST, title="Kavinsky")
    hits = await adapter.search(source, ContentType.ARTIST)
    assert len(hits) == 1
    assert hits[0].id == "UC0FvDIzS3wnvBJN1DyGZv6g"
    assert hits[0].url == "https://music.youtube.com/channel/UC0FvDIzS3wnvBJN1DyGZv6g"
    # Bei Artists wäre "Kavinsky Kavinsky" (artists[0] + title) eine verzerrte Query.
    yt.search.assert_called_once_with("Kavinsky", filter="artists", limit=3)


async def test_search_without_artists_uses_title_only(adapter, yt):
    yt.search.return_value = fix("youtube_music_search_songs.json")
    source = make_source(ContentType.TRACK, artists=())
    await adapter.search(source, ContentType.TRACK)
    yt.search.assert_called_once_with("Nightcall", filter="songs", limit=3)


async def test_search_empty_returns_empty(adapter, yt):
    yt.search.return_value = []
    hits = await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
    assert hits == []


async def test_search_wraps_library_error(adapter, yt):
    yt.search.side_effect = RuntimeError("quota? block? who knows")
    with pytest.raises(AdapterError):
        await adapter.search(make_source(ContentType.TRACK), ContentType.TRACK)
