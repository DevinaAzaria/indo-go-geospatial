# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: vector and area comparison preview; GPL-2.0-or-later.
import sys
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indo_go_geospatial.parcel import analyze_parcel, compare_document_area, format_comparison
from indo_go_geospatial.vector_parcel import analyze_selected_polygon

POLYGON = 3
COORDS = [(400000,9100000),(400010,9100000),(400010,9100016),(400000,9100016),(400000,9100000)]

def make_layer():
    layer = Mock()
    layer.isValid.return_value = True
    layer.providerType.return_value = "memory"
    layer.crs.return_value.isValid.return_value = True
    layer.crs.return_value.authid.return_value = "EPSG:32749"
    layer.selectedFeatureCount.return_value = 1
    feature = Mock()
    geometry = feature.geometry.return_value
    geometry.isNull.return_value = False
    geometry.isEmpty.return_value = False
    geometry.wkbType.return_value = POLYGON
    geometry.isGeosValid.return_value = True
    pts = [Mock(x=Mock(return_value=x), y=Mock(return_value=y)) for x,y in COORDS]
    geometry.asPolygon.return_value = [pts]
    layer.selectedFeatures.return_value = [feature]
    return layer, geometry

class VectorChecks(unittest.TestCase):
    def test_valid(self):
        layer, _ = make_layer()
        r = analyze_selected_polygon(layer, POLYGON)
        self.assertEqual(r["area_m2"], Decimal(160))
        self.assertEqual(r["perimeter_m"], Decimal(52))
    def test_provider_rejected_before_read(self):
        layer, _ = make_layer()
        layer.providerType.return_value = "postgres"
        with self.assertRaises(ValueError):
            analyze_selected_polygon(layer, POLYGON)
        layer.selectedFeatures.assert_not_called()
    def test_crs_and_selection(self):
        for count in (0,2):
            layer, _ = make_layer()
            layer.selectedFeatureCount.return_value = count
            with self.assertRaises(ValueError):
                analyze_selected_polygon(layer, POLYGON)
            layer.selectedFeatures.assert_not_called()
        layer, _ = make_layer()
        layer.crs.return_value.authid.return_value = "EPSG:4326"
        with self.assertRaises(ValueError):
            analyze_selected_polygon(layer, POLYGON)
        layer.selectedFeatures.assert_not_called()
    def test_geometry_failures(self):
        for attr, val in (("isNull",True),("isEmpty",True),("wkbType",6),("isGeosValid",False)):
            layer, g = make_layer()
            getattr(g,attr).return_value = val
            with self.assertRaises(ValueError):
                analyze_selected_polygon(layer, POLYGON)
    def test_holes_and_unclosed(self):
        layer, g = make_layer()
        ring = g.asPolygon.return_value[0]
        g.asPolygon.return_value = [ring,ring]
        with self.assertRaises(ValueError):
            analyze_selected_polygon(layer, POLYGON)
        g.asPolygon.return_value = [ring[:-1]]
        with self.assertRaises(ValueError):
            analyze_selected_polygon(layer, POLYGON)
    def test_nonfinite(self):
        layer, g = make_layer()
        g.asPolygon.return_value[0][1].x.return_value = float("nan")
        with self.assertRaises(ValueError):
            analyze_selected_polygon(layer, POLYGON)

class CompareChecks(unittest.TestCase):
    def setUp(self):
        self.r = {"area_m2": Decimal(160)}
    def test_positive_negative_and_equal(self):
        for reference, difference in (("150",10),("170",-10),("160",0)):
            with self.subTest(reference=reference):
                c = compare_document_area(self.r, reference)
                self.assertEqual(c["difference_m2"], Decimal(difference))
                self.assertEqual(c["absolute_m2"], abs(Decimal(difference)))
                self.assertIn("bukan penetapan toleransi",format_comparison(c))
    def test_percent_denominator(self):
        c = compare_document_area({"area_m2": Decimal(165)}, "150")
        self.assertEqual(c["difference_percent"], Decimal(10))
    def test_invalid_reference(self):
        for value in ("0","-1","NaN","Infinity","1,000","1e3","",None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                compare_document_area(self.r, value)

if __name__ == "__main__":
    unittest.main(verbosity=2)
