"""Async API clients for *arr applications."""

from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient

__all__ = ["LidarrClient", "RadarrClient", "SonarrClient"]
