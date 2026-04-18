from linkhop.matching import (
    artist_overlap,
    duration_score,
    score_candidate,
    threshold_status,
    title_similarity,
)
from linkhop.models.domain import ContentType, ResolvedContent


def make_meta(title="Nightcall", artists=("Kavinsky",), duration_ms=257000, isrc=None):
    return ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x", url="",
        title=title, artists=artists, album=None,
        duration_ms=duration_ms, isrc=isrc, upc=None, artwork="",
    )


def test_title_similarity_perfect():
    assert title_similarity("Nightcall", "Nightcall") == 1.0


def test_title_similarity_case_and_punct():
    assert title_similarity("Nightcall", "night-call!") > 0.85


def test_title_similarity_different():
    assert title_similarity("Nightcall", "Daybreak") < 0.3


def test_artist_overlap_exact():
    assert artist_overlap(("Kavinsky",), ("Kavinsky",)) == 1.0


def test_artist_overlap_partial():
    assert 0 < artist_overlap(("Kavinsky", "Daft Punk"), ("Kavinsky",)) < 1.0


def test_artist_overlap_none():
    assert artist_overlap(("Kavinsky",), ("Other",)) == 0.0


def test_artist_overlap_empty_returns_zero():
    assert artist_overlap((), ("Kavinsky",)) == 0.0
    assert artist_overlap(("Kavinsky",), ()) == 0.0


def test_duration_score_exact():
    assert duration_score(257000, 257000) == 1.0


def test_duration_score_off_by_5s():
    assert 0.4 < duration_score(257000, 252000) < 0.6


def test_duration_score_off_by_30s():
    assert duration_score(257000, 227000) == 0.0


def test_duration_score_none_returns_neutral():
    assert duration_score(None, 257000) == 0.5
    assert duration_score(257000, None) == 0.5
    assert duration_score(None, None) == 0.5


def test_score_candidate_perfect_metadata():
    meta = make_meta()
    cand_meta = make_meta()
    score = score_candidate(meta, cand_meta, match="metadata")
    assert score >= 0.95


def test_score_candidate_isrc_always_one():
    meta = make_meta(title="wrong", artists=("also wrong",), duration_ms=1)
    cand_meta = make_meta()
    assert score_candidate(meta, cand_meta, match="isrc") == 1.0


def test_threshold_status():
    assert threshold_status(1.0) == "ok"
    assert threshold_status(0.8) == "ok"
    assert threshold_status(0.5) == "ok_low"
    assert threshold_status(0.3) == "not_found"


def test_threshold_status_boundaries():
    # exact boundary values belong to the higher bucket
    assert threshold_status(0.7) == "ok"
    assert threshold_status(0.4) == "ok_low"
    assert threshold_status(0.69999) == "ok_low"
    assert threshold_status(0.39999) == "not_found"


def test_artist_overlap_handles_feat_notation():
    # Deezer often returns a single "A feat. B" name where Spotify returns ("A", "B").
    # Tokenised overlap must cross that representational gap.
    assert artist_overlap(("Kavinsky feat. Daft Punk",), ("Kavinsky", "Daft Punk")) == 1.0
    assert artist_overlap(("Kavinsky ft Daft Punk",), ("Kavinsky",)) > 0.3


def test_title_similarity_returns_zero_when_either_side_normalises_to_empty():
    # Pure-symbol or pure-combining-mark titles normalise to "" and would otherwise
    # compare equal to another empty-normalising title via SequenceMatcher("", "")==1.0.
    assert title_similarity("🎵🎶", "Nightcall") == 0.0
    assert title_similarity("🎵🎶", "🎵🎶") == 0.0


def make_album(title, artists, duration_ms=None):
    return ResolvedContent(
        service="spotify", type=ContentType.ALBUM, id="x", url="",
        title=title, artists=artists, album=None,
        duration_ms=duration_ms, isrc=None, upc=None, artwork="",
    )


def make_artist(name):
    return ResolvedContent(
        service="spotify", type=ContentType.ARTIST, id="x", url="",
        title=name, artists=(name,), album=None,
        duration_ms=None, isrc=None, upc=None, artwork="",
    )


def test_score_candidate_album_perfect_match_reaches_one():
    # Albums carry no duration on either side; weights must re-distribute so
    # a perfect match scores 1.0 rather than the 0.9 cap of the track formula.
    src = make_album("OutRun", ("Kavinsky",))
    cand = make_album("OutRun", ("Kavinsky",))
    assert score_candidate(src, cand, match="metadata") == 1.0


def test_score_candidate_artist_perfect_match_reaches_one():
    src = make_artist("Kavinsky")
    cand = make_artist("Kavinsky")
    assert score_candidate(src, cand, match="metadata") == 1.0
