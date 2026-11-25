# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Offline preview policy. Network access requires a future reviewed implementation."""

MAX_TILES = 512
MAX_WORKERS = 2
NETWORK_DISABLED = "Network access is disabled in INDO-GO GeoSpatial 0.1.1 pending data-rights and security review."


def require_network_access():
    """Fail closed: no settings, tokens or remote config can enable network access."""
    raise PermissionError(NETWORK_DISABLED)


def validate_export_limits(tiles, workers):
    if type(tiles) is not int or not 1 <= tiles <= MAX_TILES:
        raise ValueError("Tile count outside preview policy")
    if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
        raise ValueError("Worker count outside preview policy")
