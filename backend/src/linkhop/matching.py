from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from linkhop.models.domain import MatchType, ResolvedContent

ThresholdStatus = Literal["ok", "ok_low", "not_found"]

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Connector tokens that join collaborating artists into one string on some services
# (Deezer tends to return "A feat. B" as a single artist name, Spotify splits them).
# Stripping these makes the two shapes comparable.
_ARTIST_STOPWORDS = frozenset({"feat", "ft", "featuring", "with", "and"})


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip().lower()
    return s


def _artist_tokens(names: tuple[str, ...]) -> set[str]:
    out: set[str] = set()
    for name in names:
        for tok in _normalize(name).split():
            if tok and tok not in _ARTIST_STOPWORDS:
                out.add(tok)
    return out


def title_similarity(a: str, b: str) -> float:
    na = _normalize(a)
    nb = _normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def artist_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    ta = _artist_tokens(a)
    tb = _artist_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def duration_score(a_ms: int | None, b_ms: int | None) -> float:
    if a_ms is None or b_ms is None:
        return 0.5  # neutral when either side lacks a duration
    diff_s = abs(a_ms - b_ms) / 1000
    return max(0.0, 1.0 - diff_s / 10.0)


def score_candidate(
    source: ResolvedContent, candidate: ResolvedContent, match: MatchType
) -> float:
    if match in {"isrc", "upc"}:
        return 1.0
    title = title_similarity(source.title, candidate.title)
    artists = artist_overlap(source.artists, candidate.artists)
    # Album and artist content have no duration on either side; duration_score would
    # contribute a constant 0.5, capping a perfect match at 0.9. Re-distribute its
    # weight across title and artists when duration is unavailable on either side.
    if source.duration_ms is None or candidate.duration_ms is None:
        return round(title * 0.5 + artists * 0.5, 3)
    dur = duration_score(source.duration_ms, candidate.duration_ms)
    return round(title * 0.4 + artists * 0.4 + dur * 0.2, 3)


def threshold_status(confidence: float) -> ThresholdStatus:
    """Bucket a confidence score into a canonical status label.

    - 'ok' for confidence >= 0.7 (auto-accept).
    - 'ok_low' for 0.4 <= confidence < 0.7 (UI shows a "~match" badge).
    - 'not_found' for < 0.4 (no candidate surfaced).
    """
    if confidence >= 0.7:
        return "ok"
    if confidence >= 0.4:
        return "ok_low"
    return "not_found"
