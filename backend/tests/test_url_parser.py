import pytest

from linkhop.url_parser import ParsedUrl, UnsupportedUrlError, parse


@pytest.mark.parametrize("url,service,type_,id_", [
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),  # noqa: E501
    ("https://open.spotify.com/album/2dIGnmEIy1WZIcZCFSj6i8", "spotify", "album", "2dIGnmEIy1WZIcZCFSj6i8"),  # noqa: E501
    ("https://open.spotify.com/artist/0du5cEVh5yTK9QJze8zA0C", "spotify", "artist", "0du5cEVh5yTK9QJze8zA0C"),  # noqa: E501
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb?si=abc", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),  # noqa: E501
    ("spotify:track:6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("https://www.deezer.com/track/3135556", "deezer", "track", "3135556"),
    ("https://www.deezer.com/album/302127", "deezer", "album", "302127"),
    ("https://www.deezer.com/artist/27", "deezer", "artist", "27"),
    ("https://deezer.com/en/track/3135556", "deezer", "track", "3135556"),
    ("https://tidal.com/browse/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/album/77640616", "tidal", "album", "77640616"),
    ("https://tidal.com/artist/3527", "tidal", "artist", "3527"),
    # Share-Suffix der Tidal-App (siehe Report von 2026-04-19)
    ("https://tidal.com/track/513174201/u", "tidal", "track", "513174201"),
    ("https://tidal.com/browse/album/77640616/u", "tidal", "album", "77640616"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "youtube_music", "track", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&si=AbC", "youtube_music", "track", "dQw4w9WgXcQ"),  # noqa: E501
    ("https://music.youtube.com/playlist?list=OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk", "youtube_music", "album", "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk"),  # noqa: E501
    # /browse/<MPREb_…> ist die Form, die linkhop selbst als Album-Ziel-URL erzeugt —
    # Round-Trip eigener Links muss funktionieren.
    ("https://music.youtube.com/browse/MPREb_K0OB6WlC9bF", "youtube_music", "album", "MPREb_K0OB6WlC9bF"),  # noqa: E501
    ("https://music.youtube.com/channel/UC0FvDIzS3wnvBJN1DyGZv6g", "youtube_music", "artist", "UC0FvDIzS3wnvBJN1DyGZv6g"),  # noqa: E501
    ("https://music.youtube.com/watch/?v=dQw4w9WgXcQ", "youtube_music", "track", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/playlist/?list=OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk", "youtube_music", "album", "OLAK5uy_kkmbD9ZRiBSpYRrrFiEW8u17rPWLKecJk"),  # noqa: E501
    # Apple Music: /<storefront>/<typ>/<slug>/<id>; Storefront und Slug optional.
    ("https://music.apple.com/de/song/nightcall/719245988", "apple_music", "track", "719245988"),
    ("https://music.apple.com/us/song/719245988", "apple_music", "track", "719245988"),
    ("https://music.apple.com/song/nightcall/719245988", "apple_music", "track", "719245988"),
    # ?i=<trackId> auf Album-URLs meint einen einzelnen Track und gewinnt.
    ("https://music.apple.com/de/album/outrun/719245563?i=719245988", "apple_music", "track", "719245988"),  # noqa: E501
    ("https://music.apple.com/de/album/outrun/719245563", "apple_music", "album", "719245563"),
    ("https://music.apple.com/de/album/719245563/", "apple_music", "album", "719245563"),
    ("https://music.apple.com/de/artist/kavinsky/358714030", "apple_music", "artist", "358714030"),
    ("https://geo.music.apple.com/de/album/outrun/719245563", "apple_music", "album", "719245563"),
    # Legacy-iTunes-Links präfixen die ID mit "id".
    ("https://itunes.apple.com/de/album/outrun/id719245563", "apple_music", "album", "719245563"),
    ("https://itunes.apple.com/de/artist/kavinsky/id358714030", "apple_music", "artist", "358714030"),  # noqa: E501
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
    "http://[invalid",                          # malformed URL (urlparse raises)
    "https://music.youtube.com/playlist?list=PLabc12345",   # normale Playlist, kein Album
    "https://music.youtube.com/watch",                       # kein v=-Parameter
    "https://music.youtube.com/watch?v=tooshort",            # Video-ID != 11 Zeichen
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",           # nur music.youtube.com erlaubt
    "https://youtu.be/dQw4w9WgXcQ",
    "https://music.youtube.com/browse/PLsome_normal_playlist",   # kein MPREb_-Präfix
    "https://music.youtube.com/channel/XCsomethingNotUC",        # kein UC-Präfix
    "https://music.apple.com/de/playlist/pl.u-abc123",       # Playlists nicht unterstützt
    "https://music.apple.com/de/song/nightcall/notanumber",  # ID muss numerisch sein
    "https://music.apple.com/de/music-video/foo/123",        # Musikvideos nicht unterstützt
    "https://music.apple.com/de/album/outrun",               # Slug ohne ID
])
def test_parse_invalid_raises(url):
    with pytest.raises(UnsupportedUrlError):
        parse(url)
