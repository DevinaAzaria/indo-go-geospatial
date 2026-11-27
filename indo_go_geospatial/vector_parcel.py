# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: vector and area comparison preview; GPL-2.0-or-later.
"""Read one selected simple 2D polygon from a trusted offline QGIS memory layer."""
import math
from .parcel import analyze_parcel, parse_utm_crs, MAX_VERTICES


def analyze_selected_polygon(layer, polygon_type):
    # Restrict to memory provider before retrieving any features.
    # A future version may explicitly support verified local file providers.
    if layer is None or not layer.isValid() or layer.providerType() != "memory":
        raise ValueError("Gunakan layer vektor memory lokal yang tepercaya; provider lain belum didukung.")
    crs = layer.crs()
    if not crs.isValid():
        raise ValueError("CRS layer tidak valid.")
    authid = parse_utm_crs(crs.authid())
    if layer.selectedFeatureCount() != 1:
        raise ValueError("Pilih tepat satu fitur poligon.")
    features = layer.selectedFeatures()
    if len(features) != 1:
        raise ValueError("Seleksi berubah; pilih ulang satu fitur.")
    geometry = features[0].geometry()
    if geometry.isNull() or geometry.isEmpty() or geometry.wkbType() != polygon_type:
        raise ValueError("Hanya poligon tunggal 2D tanpa kurva yang didukung.")
    if not geometry.isGeosValid():
        raise ValueError("Geometri tidak valid; periksa di QGIS tanpa mengubah data asli.")
    rings = geometry.asPolygon()
    if len(rings) != 1:
        raise ValueError("Poligon berlubang belum didukung.")
    ring = rings[0]
    if not 4 <= len(ring) <= MAX_VERTICES + 1:
        raise ValueError("Poligon harus berisi 3–500 titik batas dan titik penutup.")
    pairs = [(point.x(), point.y()) for point in ring]
    if not all(math.isfinite(x) and math.isfinite(y) for x,y in pairs):
        raise ValueError("Koordinat tidak hingga.")
    if pairs[0] != pairs[-1]:
        raise ValueError("Ring poligon tidak tertutup.")
    text = "\n".join(f"{x:.6f} {y:.6f}" for x,y in pairs)
    result = analyze_parcel(text, authid)
    # Detect vertex collapse from serialization at the stated precision.
    if result["vertices"] != len(pairs)-1:
        raise ValueError("Resolusi koordinat menyebabkan titik berimpit.")
    return result
