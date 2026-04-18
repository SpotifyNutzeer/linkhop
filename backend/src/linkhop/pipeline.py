from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from linkhop.adapters.base import AdapterError, ServiceAdapter
from linkhop.errors import SourceNotFoundError
from linkhop.matching import score_candidate, threshold_status
from linkhop.models.domain import ContentType, MatchType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl

TargetStatus = Literal["ok", "ok_low", "not_found", "error"]


@dataclass(slots=True)
class TargetOutcome:
    status: TargetStatus
    url: str | None = None
    confidence: float | None = None
    match: MatchType | None = None
    message: str | None = None


@dataclass(slots=True)
class ConvertOutcome:
    source: ResolvedContent
    targets: dict[str, TargetOutcome]


class Pipeline:
    def __init__(self, adapters: dict[str, ServiceAdapter]) -> None:
        self._adapters = adapters

    async def convert(self, parsed: ParsedUrl) -> ConvertOutcome:
        source_adapter = self._adapters.get(parsed.service)
        if source_adapter is None:
            raise SourceNotFoundError(f"no adapter for source service: {parsed.service}")

        source = await source_adapter.resolve(parsed)
        if source is None:
            raise SourceNotFoundError(f"source not found: {parsed.service}/{parsed.type}/{parsed.id}")

        target_ids = [sid for sid in self._adapters if sid != parsed.service]
        type_ = ContentType(parsed.type)

        tasks = [self._search_one(sid, source, type_) for sid in target_ids]
        results = await asyncio.gather(*tasks)

        targets = dict(zip(target_ids, results, strict=True))
        return ConvertOutcome(source=source, targets=targets)

    async def _search_one(
        self, service_id: str, source: ResolvedContent, type_: ContentType
    ) -> TargetOutcome:
        adapter = self._adapters[service_id]
        try:
            hits: list[SearchHit] = await adapter.search(source, type_)
        except AdapterError as e:
            return TargetOutcome(status="error", message=e.message)
        except Exception as e:  # defensive, unknown adapter bug
            return TargetOutcome(status="error", message=f"unexpected: {e}")

        if not hits:
            return TargetOutcome(status="not_found")

        id_hits = [h for h in hits if h.match in {"isrc", "upc"}]
        if id_hits:
            id_best = id_hits[0]
            return TargetOutcome(status="ok", url=id_best.url, confidence=1.0, match=id_best.match)

        best: SearchHit | None = None
        best_score = 0.0
        for h in hits:
            score = await self._score_hit(service_id, source, h, type_)
            if score > best_score:
                best, best_score = h, score

        status = threshold_status(best_score)
        if status == "not_found" or best is None:
            return TargetOutcome(status="not_found")
        # "ok" or "ok_low" — preserve the bucket so the UI can show a "~match" badge.
        return TargetOutcome(
            status=status, url=best.url,
            confidence=round(best_score, 3), match="metadata",
        )

    async def _score_hit(
        self, service_id: str, source: ResolvedContent, hit: SearchHit, type_: ContentType
    ) -> float:
        adapter = self._adapters[service_id]
        try:
            full = await adapter.resolve(
                ParsedUrl(service=service_id, type=type_.value, id=hit.id)
            )
        except Exception:
            # A failure fetching the candidate's full metadata must not kill the whole
            # convert call — just drop this hit out of scoring.
            return 0.0
        if full is None:
            return 0.0
        return score_candidate(source, full, match="metadata")
