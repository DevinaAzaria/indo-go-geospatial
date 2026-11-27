# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: vector and area comparison preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-27: parcel analysis preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: local raster preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: lifecycle preview; GPL-2.0-or-later.
"""Actual QGIS API smoke check; execute only in an isolated QGIS profile."""
def run_smoke_test():
    from pathlib import Path
    from qgis.PyQt.QtGui import QIcon
    from qgis.utils import iface
    from indo_go_geospatial import classFactory, plugin, security_policy
    assert plugin.plugin_version() == "0.3.1"
    assert not QIcon(str(Path(plugin.__file__).with_name("icon.svg"))).isNull()
    # Run only when the installed plugin is disabled, to avoid duplicate toolbar items.
    candidate = classFactory(iface)
    try:
        candidate.initGui()
        candidate.initGui()
        assert len(candidate.actions) == 4
        try:
            security_policy.require_network_access()
        except PermissionError:
            return True
        raise AssertionError("Network policy unexpectedly allowed access")
    finally:
        candidate.unload()
        assert not candidate.actions
