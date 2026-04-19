from __future__ import annotations

from linkhop.adapters.base import AdapterCapabilities, ServiceAdapter
from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.adapters.tidal import TidalAdapter

__all__ = [
    "AdapterCapabilities",
    "DeezerAdapter",
    "ServiceAdapter",
    "SpotifyAdapter",
    "TidalAdapter",
]
