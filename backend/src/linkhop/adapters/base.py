from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

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


@runtime_checkable
class ServiceAdapter(Protocol):
    service_id: str
    capabilities: AdapterCapabilities

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        """URL in Form von ParsedUrl → Metadaten. None wenn nicht auffindbar."""
        ...

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        """Suche mit Metadaten vom Source-Dienst. Liefert bis zu 3 Kandidaten."""
        ...


@dataclass(frozen=True, slots=True)
class AdapterError(Exception):
    service: str
    message: str

    def __str__(self) -> str:
        return f"{self.service}: {self.message}"
