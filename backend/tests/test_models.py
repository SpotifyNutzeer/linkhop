from linkhop.models.api import ConvertResponse, SourceContent, TargetResult
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit


def test_resolved_content_equality():
    a = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="https://...", title="T", artists=("A",), album="Al",
        duration_ms=200_000, isrc="ABC", upc=None, artwork="",
    )
    b = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="https://...", title="T", artists=("A",), album="Al",
        duration_ms=200_000, isrc="ABC", upc=None, artwork="",
    )
    assert a == b


def test_search_hit_carries_confidence():
    hit = SearchHit(service="deezer", id="1", url="https://...", confidence=0.82, match="metadata")
    assert hit.confidence == 0.82
    assert hit.match == "metadata"


def test_convert_response_serializes():
    resp = ConvertResponse(
        source=SourceContent(
            service="tidal", type="track", id="1",
            url="https://tidal.com/track/1",
            title="N", artists=["K"], album="O",
            duration_ms=225_000, isrc="FR", artwork="https://x",
        ),
        targets={"spotify": TargetResult(status="ok", url="https://u", confidence=1.0, match="isrc")},
        cache={"hit": False, "ttl_seconds": 604_800},
        share=None,
    )
    data = resp.model_dump(mode="json")
    assert data["source"]["title"] == "N"
    assert data["targets"]["spotify"]["confidence"] == 1.0
