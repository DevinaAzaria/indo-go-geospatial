# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: lifecycle preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Offline checks; do not import QGIS or contact any server."""
import ast
import configparser
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "indo_go_geospatial"
spec = importlib.util.spec_from_file_location("policy", PKG / "security_policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class SecurityChecks(unittest.TestCase):
    def test_network_denied(self):
        with self.assertRaises(PermissionError):
            policy.require_network_access()

    def test_export_limits(self):
        policy.validate_export_limits(1, 1)
        policy.validate_export_limits(512, 2)
        for args in [(0, 1), (513, 1), (1, 0), (1, 3), (True, 1), (1.0, 1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                policy.validate_export_limits(*args)

    def test_package_and_metadata(self):
        self.assertFalse((ROOT / "atrbpn_basemap").exists())
        cp = configparser.ConfigParser()
        cp.read(PKG / "metadata.txt", encoding="utf-8")
        self.assertEqual(cp["general"]["version"], "0.1.2")
        self.assertEqual(cp["general"]["license"], "GPL-2.0-or-later")
        self.assertIn("Fadli Arya Wisnu Baradi", cp["general"]["author"])
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (PKG / "LICENSE").read_bytes())

    def test_gui_is_offline(self):
        source = (PKG / "plugin.py").read_text(encoding="utf-8")
        ast.parse(source)
        for forbidden in ("QgsRasterLayer", "QTimer", "QgsSettings", "QDesktopServices", "detector", "exporter", "QgsProject"):
            self.assertNotIn(forbidden, source)

    def test_network_and_uri_guard(self):
        module = ast.parse((PKG / "detector.py").read_text(encoding="utf-8"))
        for name in ("http", "build_uri"):
            fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.unparse(fn.body[0]), "require_network_access()")


if __name__ == "__main__":
    unittest.main(verbosity=2)
