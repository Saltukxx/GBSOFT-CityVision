"""FlightHub 2 OpenAPI integration.

A DJI Dock binds to exactly one cloud platform, so we cannot run FlightHub 2 and a
self-hosted Cloud API broker against the same dock. The dock stays on FlightHub 2 —
which handles routes, scheduling, dock health and live view — and CityVision pulls
finished flights out over the OpenAPI: task status, media files, flight trajectory.

Detection stays entirely ours: downloaded media goes through the existing
`analyze_video` job (run_pipeline → events → PostGIS → work orders).
"""

from cityvision.flighthub.client import FlightHubClient, FlightHubError
from cityvision.flighthub.config import FlightHubConfig, load_flighthub_config

__all__ = [
    "FlightHubClient",
    "FlightHubConfig",
    "FlightHubError",
    "load_flighthub_config",
]
