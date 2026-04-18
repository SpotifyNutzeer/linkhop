import pytest

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.pipeline import Pipeline
from linkhop.url_parser import ParsedUrl


def source_meta() -> ResolvedContent:
    return ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )


def target_meta(service: str, title: str = "Nightcall", duration_ms: int | None = 257000,
                artists: tuple[str, ...] = ("Kavinsky",)) -> ResolvedContent:
    return ResolvedContent(
        service=service, type=ContentType.TRACK, id="x",
        url=f"https://{service}/x", title=title,
        artists=artists, album=None,
        duration_ms=duration_ms, isrc=None, upc=None, artwork="",
    )


class FakeAdapter:
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    def __init__(self, service_id, resolve_value=None, search_value=None,
                 raise_on_search=False, resolve_by_id=None, raise_on_resolve=False):
        self.service_id = service_id
        self._resolve_value = resolve_value
        self._search_value = search_value or []
        self._raise_search = raise_on_search
        self._resolve_by_id = resolve_by_id or {}
        self._raise_resolve = raise_on_resolve

    async def resolve(self, parsed):
        if self._raise_resolve:
            raise AdapterError(self.service_id, "resolve boom")
        if parsed.id in self._resolve_by_id:
            return self._resolve_by_id[parsed.id]
        return self._resolve_value

    async def search(self, meta, target_type):
        if self._raise_search:
            raise AdapterError(self.service_id, "boom")
        return self._search_value


async def test_pipeline_resolves_and_searches():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter("spotify", search_value=[
        SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                  confidence=1.0, match="isrc"),
    ])
    deezer = FakeAdapter("deezer", search_value=[
        SearchHit(service="deezer", id="dz1", url="https://www.deezer.com/track/dz1",
                  confidence=1.0, match="isrc"),
    ])
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify, "deezer": deezer})

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.source.title == "Nightcall"
    assert result.targets["spotify"].status == "ok"
    assert result.targets["spotify"].match == "isrc"
    assert result.targets["deezer"].status == "ok"


async def test_pipeline_source_adapter_not_found_raises():
    tidal = FakeAdapter("tidal", resolve_value=None)
    pipeline = Pipeline({"tidal": tidal})

    with pytest.raises(LookupError):
        await pipeline.convert(ParsedUrl("tidal", "track", "missing"))


async def test_pipeline_unknown_source_service_raises():
    pipeline = Pipeline({"spotify": FakeAdapter("spotify")})
    with pytest.raises(LookupError):
        await pipeline.convert(ParsedUrl("tidal", "track", "1"))


async def test_pipeline_partial_results_on_adapter_error():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    good = FakeAdapter("spotify", search_value=[
        SearchHit(service="spotify", id="sp1", url="...", confidence=1.0, match="isrc"),
    ])
    bad = FakeAdapter("deezer", raise_on_search=True)
    pipeline = Pipeline({"tidal": tidal, "spotify": good, "deezer": bad})

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "ok"
    assert result.targets["deezer"].status == "error"
    assert "boom" in (result.targets["deezer"].message or "")


async def test_pipeline_skips_source_service_in_targets():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    pipeline = Pipeline({"tidal": tidal})

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert "tidal" not in result.targets


async def test_pipeline_metadata_hit_is_scored_and_marked_ok():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter(
        "spotify",
        search_value=[
            SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                      confidence=0.0, match="metadata"),
        ],
        resolve_by_id={"sp1": target_meta("spotify")},
    )
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify})
    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    # perfect metadata match on track → status "ok", confidence near 1.0
    assert result.targets["spotify"].status == "ok"
    assert result.targets["spotify"].match == "metadata"
    assert result.targets["spotify"].confidence is not None
    assert result.targets["spotify"].confidence >= 0.95


async def test_pipeline_low_confidence_is_marked_ok_low():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    # Weak candidate: same artist but clearly different title and a 7-second drift
    # lands the score between 0.4 and 0.7 — "ok_low".
    spotify = FakeAdapter(
        "spotify",
        search_value=[
            SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                      confidence=0.0, match="metadata"),
        ],
        resolve_by_id={
            "sp1": target_meta("spotify", title="Daybreak", artists=("Kavinsky",),
                               duration_ms=250000),
        },
    )
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify})
    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "ok_low"
    assert result.targets["spotify"].match == "metadata"


async def test_pipeline_metadata_hit_below_threshold_is_not_found():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter(
        "spotify",
        search_value=[
            SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                      confidence=0.0, match="metadata"),
        ],
        resolve_by_id={
            "sp1": target_meta("spotify", title="Completely Different",
                               artists=("Someone Else",), duration_ms=120000),
        },
    )
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify})
    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "not_found"


async def test_pipeline_empty_hits_is_not_found():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter("spotify", search_value=[])
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify})
    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "not_found"


async def test_pipeline_swallows_score_resolve_error():
    # A failure while fetching the target's full metadata for scoring must not
    # kill the whole conversion — that target becomes not_found, others proceed.
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter(
        "spotify",
        search_value=[
            SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                      confidence=0.0, match="metadata"),
        ],
        raise_on_resolve=True,
    )
    deezer = FakeAdapter("deezer", search_value=[
        SearchHit(service="deezer", id="dz1", url="https://www.deezer.com/track/dz1",
                  confidence=1.0, match="isrc"),
    ])
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify, "deezer": deezer})
    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "not_found"
    assert result.targets["deezer"].status == "ok"
