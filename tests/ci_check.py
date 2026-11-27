# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: parcel analysis preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: local raster preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: lifecycle preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Pemeriksaan tanpa QGIS, dijalankan oleh GitHub Actions (dan bisa dijalankan lokal).

    python tests/ci_check.py            # cek metadata.txt dan config.json
    python tests/ci_check.py dist/x.zip # juga cek isi ZIP

Keluar dengan kode 1 bila ada yang gagal.
"""
import configparser
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "indo_go_geospatial")
REQUIRED_META = ("name", "qgisMinimumVersion", "description", "about", "version", "author",
                 "email", "repository", "tracker", "homepage", "changelog", "icon")
REQUIRED_IN_ZIP = ("__init__.py", "plugin.py", "detector.py", "exporter.py", "export_dialog.py",
                   "metadata.txt", "icon.svg", "LICENSE", "security_policy.py", "local_raster.py", "parcel.py")
FORBIDDEN_IN_ZIP = ("__pycache__", ".pyc", ".pyo", ".bak", ".orig", ".tmp")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

errors = []


def fail(msg):
    errors.append(msg)
    print("GAGAL: " + msg)


def ok(msg):
    print("LULUS: " + msg)


# metadata.txt
cp = configparser.ConfigParser()
cp.read(os.path.join(PKG, "metadata.txt"), encoding="utf-8")
meta = cp["general"] if cp.has_section("general") else {}
missing = [k for k in REQUIRED_META if not str(meta.get(k, "")).strip()]
if missing:
    fail("metadata.txt: kolom kosong %s" % missing)
version = str(meta.get("version", "")).strip()
if not VERSION_RE.match(version):
    fail("metadata.txt: versi '%s' bukan format x.y.z" % version)
elif not str(meta.get("changelog", "")).strip().startswith(version):
    fail("metadata.txt: changelog harus diawali versi %s" % version)
if not missing and VERSION_RE.match(version):
    ok("metadata.txt versi %s" % version)
if not os.path.isfile(os.path.join(PKG, str(meta.get("icon", "icon.svg")))):
    fail("ikon %s tidak ditemukan" % meta.get("icon"))

# config.json
n_before = len(errors)
try:
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    url = cfg.get("tile_url", "")
    if not all(k in url for k in ("{x}", "{y}", "{z}")):
        fail("config.json: tile_url harus memuat {x}, {y}, {z}")
    if not (0 <= int(cfg.get("zmin", 0)) <= int(cfg.get("zmax", 0)) <= 22):
        fail("config.json: zmin/zmax tidak wajar")
    lv = str(cfg.get("latest_version", ""))
    if lv and not VERSION_RE.match(lv):
        fail("config.json: latest_version '%s' bukan format x.y.z" % lv)
    for key in ("scripts", "post_pages", "foto_keywords", "token_vars"):
        if key in cfg and not isinstance(cfg[key], list):
            fail("config.json: %s harus berupa list" % key)
    if len(errors) == n_before:
        ok("config.json valid (tile_url %s)" % url)
except Exception as e:  # noqa: BLE001
    fail("config.json tidak valid: %s" % e)

# ZIP (opsional)
if len(sys.argv) > 1:
    zp = sys.argv[1]
    try:
        names = zipfile.ZipFile(zp).namelist()
        if not all(n.startswith("indo_go_geospatial/") for n in names):
            fail("ZIP: ada berkas di luar folder indo_go_geospatial/")
        miss = [f for f in REQUIRED_IN_ZIP if "indo_go_geospatial/" + f not in names]
        if miss:
            fail("ZIP: berkas wajib hilang %s" % miss)
        junk = [n for n in names if any(b in n for b in FORBIDDEN_IN_ZIP)]
        if junk:
            fail("ZIP: berkas sampah ikut %s" % junk)
        if version and version not in os.path.basename(zp):
            fail("ZIP: nama berkas tidak memuat versi %s" % version)
        if not (miss or junk):
            ok("ZIP %s (%d berkas)" % (os.path.basename(zp), len(names)))
    except Exception as e:  # noqa: BLE001
        fail("ZIP tidak bisa dibaca: %s" % e)

print("\nHASIL: %s" % ("SEMUA LULUS" if not errors else "%d GAGAL" % len(errors)))
sys.exit(1 if errors else 0)
