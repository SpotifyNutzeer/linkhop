from __future__ import annotations

import httpx

from linkhop.adapters import DeezerAdapter, ServiceAdapter, SpotifyAdapter
from linkhop.config import Settings


def build_adapter_map(settings: Settings, http: httpx.AsyncClient) -> dict[str, ServiceAdapter]:
    adapters: dict[str, ServiceAdapter] = {}
    if settings.enable_spotify:
        adapters["spotify"] = SpotifyAdapter(
            client=http,
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
    if settings.enable_deezer:
        adapters["deezer"] = DeezerAdapter(client=http)
    # Tidal / YouTube Music kommen in Plan B
    return adapters
