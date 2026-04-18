from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ContentType(StrEnum):
    TRACK = "track"
    ALBUM = "album"
    ARTIST = "artist"


@dataclass(frozen=True, slots=True)
class ResolvedContent:
    service: str
    type: ContentType
    id: str
    url: str
    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_ms: int | None
    isrc: str | None
    upc: str | None
    artwork: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    service: str
    id: str
    url: str
    confidence: float
    match: str  # "isrc" | "upc" | "metadata"
