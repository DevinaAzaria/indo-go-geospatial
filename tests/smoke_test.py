# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Offline runtime smoke test; run inside an isolated QGIS profile only."""

def run_smoke_test():
    from indo_go_geospatial import plugin, security_policy
    assert plugin.plugin_version() == "0.1.1"
    try:
        security_policy.require_network_access()
    except PermissionError:
        return True
    raise AssertionError("Network policy unexpectedly allowed access")
