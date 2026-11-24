# -*- coding: utf-8 -*-
"""Smoke test plugin ATR BPN Basemap. Wajib lolos sebelum rilis.

Dijalankan DI DALAM QGIS (butuh akses ke server ATR/BPN dan plugin yang sudah terpasang):

    QGIS > Plugins > Python Console:
    exec(open(r"<path>/tests/smoke_test.py", encoding="utf-8").read())
    run_smoke_test(zip_path=r"<path>/dist/atrbpn_basemap-<versi>.zip")   # zip_path opsional

Yang diuji:
  1. metadata.txt terbaca dan versinya sama dengan plugin_version()
  2. config.json di GitHub terbaca
  3. deteksi otomatis URL tile terverifikasi
  4. URL tile tersimpan masih mengembalikan gambar
  5. layer XYZ dari build_uri() valid
  6. ekspor GeoTIFF kecil (Driyorejo, zoom 18, UTM 49S, JPEG) berhasil dan berisi gambar
  7. (opsional) isi ZIP rilis lengkap dan bersih

Skrip ini tidak mengubah pengaturan plugin, layer, atau proyek QGIS. Berkas ekspor uji dihapus setelah dicek.
"""
import configparser
import os
import tempfile
import time
import zipfile

from osgeo import gdal
from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer, QgsRectangle, QgsSettings

REQUIRED_IN_ZIP = ("__init__.py", "plugin.py", "detector.py", "exporter.py", "export_dialog.py",
                   "metadata.txt", "icon.png", "LICENSE")
FORBIDDEN_IN_ZIP = ("__pycache__", ".pyc", ".pyo", ".bak", ".orig", ".tmp")
TEST_EXTENT = (112.6240, -7.3655, 112.6290, -7.3610)  # Driyorejo, Gresik (lon/lat)


def run_smoke_test(zip_path=None, verbose=True):
    """Jalankan semua uji. Kembalikan True bila semuanya lolos."""
    import atrbpn_basemap
    from atrbpn_basemap import detector, exporter, plugin

    plugin_dir = os.path.dirname(atrbpn_basemap.__file__)
    results = []

    def check(name, fn):
        t0 = time.time()
        try:
            detail = fn()
            results.append((name, True, detail, time.time() - t0))
        except Exception as e:  # noqa: BLE001 - laporkan semua jenis kegagalan
            results.append((name, False, "%s: %s" % (type(e).__name__, e), time.time() - t0))

    # 1. metadata
    def t_metadata():
        cp = configparser.ConfigParser()
        cp.read(os.path.join(plugin_dir, "metadata.txt"), encoding="utf-8")
        v = cp["general"]["version"].strip()
        assert v == plugin.plugin_version(), "plugin_version()=%s, metadata=%s" % (plugin.plugin_version(), v)
        return "versi %s" % v
    check("metadata.txt", t_metadata)

    # 2. config.json
    remote = {}

    def t_config():
        remote.update(detector.fetch_config())
        assert remote.get("tile_url"), "config.json tidak terbaca atau tile_url kosong"
        return "tile_url %s, latest_version %s" % (remote["tile_url"], remote.get("latest_version"))
    check("config.json GitHub", t_config)

    # 3. deteksi otomatis
    found = {}

    def t_detect():
        r = detector.detect()
        assert r["verified"], "URL terdeteksi tapi tile uji tidak merespons: %s" % r["url"]
        assert all(k in r["url"] for k in ("{x}", "{y}", "{z}")), "template URL tidak lengkap"
        found.update(r)
        warn = ""
        if remote.get("tile_url") and remote["tile_url"] != r["url"]:
            warn = " (BEDA dengan config.json: %s)" % remote["tile_url"]
        return "%s, sumber=%s, zoom %s-%s%s" % (r["url"], r.get("source"), r["zmin"], r["zmax"], warn)
    check("Deteksi URL otomatis", t_detect)

    # 4. URL tersimpan
    stored = QgsSettings().value("atrbpn_basemap/url", detector.DEFAULT_URL)

    def t_stored():
        assert detector.test_url(stored), "tile dari URL tersimpan kosong: %s" % stored
        return stored
    check("URL tersimpan", t_stored)

    # 5. layer XYZ
    url = found.get("url") or stored

    def t_layer():
        lyr = QgsRasterLayer(detector.build_uri(url, 16, 21), "smoke test", "wms")
        assert lyr.isValid(), "layer tidak valid"
        return "valid"
    check("Layer XYZ", t_layer)

    # 6. ekspor GeoTIFF
    def t_export():
        out = os.path.join(tempfile.gettempdir(), "atrbpn_smoke_%d.tif" % int(time.time()))
        p = {
            "extent": QgsRectangle(*TEST_EXTENT),
            "extent_crs": QgsCoordinateReferenceSystem("EPSG:4326"),
            "zoom": 18, "workers": 4,
            "dst_crs": QgsCoordinateReferenceSystem("EPSG:32749"),
            "pixel_size": 0.0, "resampling": "bilinear", "compression": "JPEG",
            "clip": True, "overviews": True, "add_map": False,
            "out_path": out, "url": url,
        }
        task = exporter.ExportTask(p)
        ok = task.run()  # dijalankan sinkron, tanpa task manager
        try:
            assert ok, "ExportTask.run() gagal: %s" % task.error
            assert task.ok_tiles > 0, "tidak ada tile terunduh"
            ds = gdal.Open(out)
            assert ds is not None, "berkas hasil tidak bisa dibuka"
            srs = ds.GetSpatialRef()
            assert srs is not None and srs.GetAuthorityCode(None) == "32749", "CRS bukan EPSG:32749"
            assert ds.RasterXSize > 100 and ds.RasterYSize > 100, "ukuran raster terlalu kecil"
            std = ds.GetRasterBand(1).ComputeStatistics(False)[3]
            assert std > 10, "gambar tampak kosong (std=%.1f)" % std
            size = "%dx%d px" % (ds.RasterXSize, ds.RasterYSize)
            ds = None
            return "%s, %d tile, %d kosong" % (size, task.ok_tiles, task.empty_tiles)
        finally:
            if os.path.exists(out):
                gdal.GetDriverByName("GTiff").Delete(out)
    check("Ekspor GeoTIFF", t_export)

    # 7. ZIP rilis
    if zip_path:
        def t_zip():
            z = zipfile.ZipFile(zip_path)
            names = z.namelist()
            assert all(n.startswith("atrbpn_basemap/") for n in names), "ada berkas di luar folder atrbpn_basemap/"
            missing = [f for f in REQUIRED_IN_ZIP if "atrbpn_basemap/" + f not in names]
            assert not missing, "berkas wajib hilang: %s" % missing
            junk = [n for n in names if any(b in n for b in FORBIDDEN_IN_ZIP)]
            assert not junk, "berkas sampah ikut: %s" % junk
            cp = configparser.ConfigParser()
            cp.read_string(z.read("atrbpn_basemap/metadata.txt").decode("utf-8"))
            zv = cp["general"]["version"].strip()
            assert zv in os.path.basename(zip_path), "versi metadata (%s) tidak cocok dengan nama ZIP" % zv
            assert zv == plugin.plugin_version(), "ZIP versi %s, plugin terpasang %s" % (zv, plugin.plugin_version())
            return "%d berkas, versi %s" % (len(names), zv)
        check("Isi ZIP rilis", t_zip)

    passed = all(r[1] for r in results)
    if verbose:
        print("\n=== Smoke test ATR BPN Basemap ===")
        for name, ok, detail, dt in results:
            print("[%s] %-22s %5.1fs  %s" % ("LULUS" if ok else "GAGAL", name, dt, detail))
        print("HASIL: %s (%d/%d lulus)\n" % ("SEMUA LULUS" if passed else "ADA YANG GAGAL",
                                             sum(r[1] for r in results), len(results)))
    return passed
