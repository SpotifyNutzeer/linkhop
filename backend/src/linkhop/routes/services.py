from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from linkhop.models.api import ServiceInfo, ServicesResponse

router = APIRouter(prefix="/api/v1", tags=["services"])

_NAMES = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "tidal": "Tidal",
    "youtube_music": "YouTube Music",
}


@router.get("/services", response_model=ServicesResponse)
async def list_services(request: Request) -> ServicesResponse:
    adapters = request.app.state.adapters
    entries = []
    for sid, adapter in adapters.items():
        caps: list[Literal["track", "album", "artist"]] = []
        if adapter.capabilities.track:
            caps.append("track")
        if adapter.capabilities.album:
            caps.append("album")
        if adapter.capabilities.artist:
            caps.append("artist")
        entries.append(ServiceInfo(id=sid, name=_NAMES.get(sid, sid), capabilities=caps))
    return ServicesResponse(services=entries)
