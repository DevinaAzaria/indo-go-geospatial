# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: parcel analysis preview; GPL-2.0-or-later.
import sys
import unittest
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indo_go_geospatial.parcel import analyze_parcel, format_result, parse_utm_crs

CRS = "EPSG:32749"
def points(*pairs):
    return "\n".join(f"{400000+x} {9100000+y}" for x,y in pairs)

class ParcelChecks(unittest.TestCase):
    def test_rectangle_160(self):
        r = analyze_parcel(points((0,0),(10,0),(10,16),(0,16)),CRS)
        self.assertEqual(r["area_m2"], Decimal("160"))
        self.assertEqual(r["perimeter_m"], Decimal("52"))
        self.assertEqual(r["area_ha"], Decimal("0.016"))
        self.assertIn("Indikatif",format_result(r))
    def test_triangle(self):
        r = analyze_parcel(points((0,0),(3,0),(0,4)),CRS)
        self.assertEqual(r["area_m2"],Decimal(6))
        self.assertEqual(r["perimeter_m"],Decimal(12))
    def test_reverse_and_closed(self):
        r = analyze_parcel(points((0,0),(0,16),(10,16),(10,0),(0,0)),CRS)
        self.assertEqual(r["area_m2"],Decimal(160))
        self.assertEqual(r["vertices"],4)
    def test_concave(self):
        r = analyze_parcel(points((0,0),(10,0),(10,5),(5,5),(5,10),(0,10)),CRS)
        self.assertEqual(r["area_m2"],Decimal(75))
        self.assertEqual(r["perimeter_m"],Decimal(40))
    def test_decimal_precision(self):
        r = analyze_parcel("400000.001 9100000.001\n400000.011 9100000.001\n400000.011 9100000.021\n400000.001 9100000.021",CRS)
        self.assertEqual(r["area_m2"],Decimal("0.0002"))
    def test_invalid_geometry(self):
        for p in [points((0,0),(10,10),(0,10),(10,0)),
                  points((0,0),(10,0),(5,0),(0,10)),
                  points((0,0),(10,0),(20,0)),
                  points((0,0),(10,0),(10,10),(10,0),(0,10)),
                  points((0,0),(10,0),(10,10),(5,0),(0,10))]:
            with self.subTest(p=p),self.assertRaises(ValueError):
                analyze_parcel(p,CRS)
    def test_invalid_coordinates(self):
        for text in ["110.4 -7.8", "NaN 1\n2 3\n4 5",
                     "400000, 9100000\n400001 9100000\n400002 9100001",
                     "400000 10000001\n400001 9100000\n400002 9100001"]:
            with self.assertRaises(ValueError):
                analyze_parcel(text,CRS)
    def test_crs(self):
        for crs in ["EPSG:4326","EPSG:3857","EPSG:32700","EPSG:32761",""]:
            with self.assertRaises(ValueError):
                parse_utm_crs(crs)
        self.assertEqual(parse_utm_crs("epsg:32649"),"EPSG:32649")
    def test_bounds(self):
        r=analyze_parcel(points((0,0),(10,0),(10,16),(0,16)),CRS)
        self.assertEqual(r["bounds"],(400000,9100000,400010,9100016))

if __name__ == "__main__":
    unittest.main(verbosity=2)
