# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: local raster preview; GPL-2.0-or-later.
"""Validation of explicitly selected local TIFFs; no URL or service support."""
import os
from pathlib import Path

TIFF_HEADERS = (b"II\x2a\x00", b"MM\x00\x2a", b"II\x2b\x00", b"MM\x00\x2b")


def _check_drive(path):
    if os.name == "nt":
        import ctypes
        # Only fixed or removable drives; reject mapped network drives.
        if ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor)) not in (2, 3):
            raise ValueError("Pilih file pada drive lokal.")


def validate_local_tiff(raw):
    if not isinstance(raw, str) or not raw or any(c in raw for c in ("|", "\n", "\r", "\x00")):
        raise ValueError("Path file tidak valid.")
    if raw.startswith(("//", "\\")) or "://" in raw:
        raise ValueError("URL dan network share tidak didukung.")
    candidate = Path(raw)
    if not candidate.is_absolute() or candidate.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("Pilih file TIFF lokal dengan path absolut.")
    _check_drive(candidate)
    path = candidate.resolve(strict=True)
    if str(path).startswith(("//", "\\")) or any(c in str(path) for c in ("|", "\n", "\r")):
        raise ValueError("Path hasil resolusi tidak didukung.")
    _check_drive(path)
    if not path.is_file() or path.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("File TIFF lokal tidak ditemukan.")
    with path.open("rb") as stream:
        if stream.read(4) not in TIFF_HEADERS:
            raise ValueError("Header file bukan TIFF.")
    return path


def validate_attribution(source):
    if not isinstance(source, str):
        raise ValueError("Sumber data wajib diisi.")
    source = source.strip()
    if not source or len(source) > 250 or any(ord(c) < 32 for c in source):
        raise ValueError("Isi sumber data 1–250 karakter, satu baris.")
    return source
