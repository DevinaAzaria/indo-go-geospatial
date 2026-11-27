# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
def classFactory(iface):
    from .plugin import IndoGoGeoSpatialPlugin
    return IndoGoGeoSpatialPlugin(iface)
