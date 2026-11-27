# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: local raster preview; GPL-2.0-or-later.
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indo_go_geospatial.local_raster import validate_local_tiff, validate_attribution


class LocalRasterChecks(unittest.TestCase):
    def test_valid_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, header in enumerate((b"II\x2a\x00", b"MM\x00\x2a", b"II\x2b\x00", b"MM\x00\x2b")):
                p = Path(tmp) / (str(i) + ".tif")
                p.write_bytes(header + b"fixture")
                self.assertEqual(validate_local_tiff(str(p)), p.resolve())

    def test_invalid_paths(self):
        for value in ("https://example.org/image.tif", "//server/share/a.tif", "relative.tif", "/vsicurl/https://example.org/a.tif", "bad|source.tif", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_local_tiff(value)

    def test_bad_header_missing_and_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.tif"
            p.write_bytes(b"not a TIFF")
            with self.assertRaises(ValueError):
                validate_local_tiff(str(p))
            with self.assertRaises(OSError):
                validate_local_tiff(str(Path(tmp) / "missing.tif"))
            p = Path(tmp) / "a.vrt"
            p.write_bytes(b"II\x2a\x00")
            with self.assertRaises(ValueError):
                validate_local_tiff(str(p))

    def test_attribution(self):
        self.assertEqual(validate_attribution("  Local survey  "), "Local survey")
        for value in ("", " ", "x" * 251, "a\nb", None):
            with self.assertRaises(ValueError):
                validate_attribution(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
