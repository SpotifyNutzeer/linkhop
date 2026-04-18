from __future__ import annotations

import httpx

from linkhop.adapters import DeezerAdapter, ServiceAdapter, SpotifyAdapter
from linkhop.config import Settings


def build_adapter_map(settings: Settings, http: httpx.AsyncClient) -> dict[str, ServiceAdapter]:
    adapters: dict[str, ServiceAdapter] = {}
    # enable_spotify alone is not enough: a misconfigured deployment (e.g. only
    # _CLIENT_ID set) would register a broken adapter that 400s on every call.
    # Skip-with-warning at boot is clearer than a mystery runtime failure.
    if settings.enable_spotify and settings.spotify_client_id and settings.spotify_client_secret:
        adapters["spotify"] = SpotifyAdapter(
            client=http,
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
    if settings.enable_deezer:
        adapters["deezer"] = DeezerAdapter(client=http)
    # Tidal / YouTube Music kommen in Plan B
    return adapters
