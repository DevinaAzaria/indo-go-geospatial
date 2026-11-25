# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
r"""
Membuat ZIP plugin INDO-GO GeoSpatial untuk rilis GitHub (dan plugins.qgis.org).

Cara menjalankan (pilih salah satu):
  a) QGIS > Plugins > Python Console, lalu ketik (sesuaikan folder versinya):
       p = r"X:\GIS\Project Plugin\versi_1.1.3\build_zip.py"
       exec(open(p, encoding="utf-8").read(), {"__file__": p})
  b) OSGeo4W Shell / terminal:
       python "X:\GIS\Project Plugin\versi_1.1.3\build_zip.py"

Hasil: <folder versi>\dist\indo_go_geospatial-<versi>.zip
"""
import configparser
import os
import re
import zipfile

ROOT = r"X:\GIS\Project Plugin"
if "__file__" in globals():
    ROOT = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "indo_go_geospatial"
SRC = os.path.join(ROOT, PLUGIN)
SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_EXT = (".pyc", ".pyo", ".bak", ".orig", ".tmp")

cp = configparser.ConfigParser()
cp.read(os.path.join(SRC, "metadata.txt"), encoding="utf-8")
meta = cp["general"]

# --- validasi ---
errors = []
for key in ("name", "qgisMinimumVersion", "description", "about", "version",
            "author", "email", "repository", "tracker", "homepage"):
    if not meta.get(key, "").strip():
        errors.append("Kolom '%s' di metadata.txt masih kosong." % key)
for key in ("email", "repository", "tracker", "homepage"):
    if "GANTI_" in meta.get(key, ""):
        errors.append("Kolom '%s' masih berisi placeholder GANTI_...: %s" % (key, meta.get(key)))
if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", meta.get("email", "")):
    errors.append("Email tidak valid: %s" % meta.get("email"))
for f in ("__init__.py", "metadata.txt", "LICENSE", meta.get("icon", "icon.png")):
    if not os.path.isfile(os.path.join(SRC, f)):
        errors.append("Berkas wajib tidak ditemukan: %s" % f)

if errors:
    print("ZIP BELUM DIBUAT. Perbaiki dulu:")
    for e in errors:
        print("  - " + e)
else:
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s-%s.zip" % (PLUGIN, meta["version"].strip()))
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in sorted(files):
                if fn.endswith(SKIP_EXT) or fn.startswith("."):
                    continue
                full = os.path.join(base, fn)
                arc = os.path.relpath(full, ROOT).replace("\\", "/")  # wajib garis miring /
                info = zipfile.ZipInfo.from_file(full, arc)
                info.external_attr = 0o644 << 16  # rw-r--r--, tanpa izin eksekusi
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(full, "rb") as fh:
                    z.writestr(info, fh.read())
                n += 1
    print("ZIP berhasil dibuat (%d berkas): %s" % (n, out))
