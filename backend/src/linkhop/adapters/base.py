from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, assert_never, runtime_checkable

from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    track: bool
    album: bool
    artist: bool

    def supports(self, type_: ContentType) -> bool:
        match type_:
            case ContentType.TRACK:
                return self.track
            case ContentType.ALBUM:
                return self.album
            case ContentType.ARTIST:
                return self.artist
            case _:
                assert_never(type_)


@runtime_checkable
class ServiceAdapter(Protocol):
    service_id: str
    capabilities: AdapterCapabilities

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        """Resolve a parsed URL to content metadata. Returns None if not found."""
        ...

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        """Search the service with source metadata. Returns up to 3 candidates."""
        ...


@dataclass(frozen=True, slots=True)
class AdapterError(Exception):
    service: str
    message: str

    def __str__(self) -> str:
        return f"{self.service}: {self.message}"
