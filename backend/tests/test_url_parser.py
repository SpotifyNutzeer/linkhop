import pytest

from linkhop.url_parser import ParsedUrl, UnsupportedUrlError, parse


@pytest.mark.parametrize("url,service,type_,id_", [
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("https://open.spotify.com/album/2dIGnmEIy1WZIcZCFSj6i8", "spotify", "album", "2dIGnmEIy1WZIcZCFSj6i8"),
    ("https://open.spotify.com/artist/0du5cEVh5yTK9QJze8zA0C", "spotify", "artist", "0du5cEVh5yTK9QJze8zA0C"),
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb?si=abc", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("spotify:track:6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("https://www.deezer.com/track/3135556", "deezer", "track", "3135556"),
    ("https://www.deezer.com/album/302127", "deezer", "album", "302127"),
    ("https://www.deezer.com/artist/27", "deezer", "artist", "27"),
    ("https://deezer.com/en/track/3135556", "deezer", "track", "3135556"),
    ("https://tidal.com/browse/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/album/77640616", "tidal", "album", "77640616"),
    ("https://tidal.com/artist/3527", "tidal", "artist", "3527"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "youtube_music", "track", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/playlist?list=OLAK5uy_1234", "youtube_music", "album", "OLAK5uy_1234"),
    ("https://music.youtube.com/channel/UC1234", "youtube_music", "artist", "UC1234"),
])
def test_parse_valid(url, service, type_, id_):
    result = parse(url)
    assert result == ParsedUrl(service=service, type=type_, id=id_)


@pytest.mark.parametrize("url", [
    "",
    "not-a-url",
    "https://example.com/foo",
    "https://open.spotify.com/show/abc",      # Podcast, nicht unterstützt
    "https://www.deezer.com/podcast/123",
    "ftp://tidal.com/track/1",
    "spotify:track:",                          # empty ID
    "spotify:track:abc def",                   # whitespace in ID
    "spotify:track:has/slash",                 # invalid char
    "https://music.youtube.com/channel/../watch",  # path traversal
    "https://music.youtube.com/watch?v=bad id",    # whitespace in v
    "https://music.youtube.com/playlist?list=has/slash",  # invalid list char
    "http://[invalid",                          # malformed URL (urlparse raises)
])
def test_parse_invalid_raises(url):
    with pytest.raises(UnsupportedUrlError):
        parse(url)
