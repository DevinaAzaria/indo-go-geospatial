# -*- coding: utf-8 -*-
"""Ekspor foto udara ATR/BPN menjadi GeoTIFF.

Alur kerja:
1. Hitung rentang tile XYZ yang menutupi extent pada zoom terpilih.
2. Unduh tile secara paralel (dengan header Referer) dan tempel ke mosaik
   GeoTIFF sementara di EPSG:3857.
3. gdal.Warp ke CRS tujuan, potong ke extent atau poligon (cutline).
4. gdal.Translate ke GeoTIFF akhir dengan kompresi, lalu bangun overview.
"""
import contextlib
import math
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from osgeo import gdal, osr
from qgis.core import (Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsMessageLog, QgsProject, QgsTask, QgsVectorFileWriter)

from . import detector

ORIGIN = 20037508.342789244
TILE = 256
LOG_TAG = "ATR BPN Basemap"


def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(msg, LOG_TAG, level)


@contextlib.contextmanager
def gdal_exceptions():
    """Aktifkan exception GDAL sementara (GDAL >= 3.7 pakai ExceptionMgr, versi lama fallback)."""
    if hasattr(gdal, "ExceptionMgr"):
        with gdal.ExceptionMgr(useExceptions=True):
            yield
    else:
        prev = gdal.GetUseExceptions()
        gdal.UseExceptions()
        try:
            yield
        finally:
            if not prev:
                gdal.DontUseExceptions()


def srs_string(crs):
    """String CRS yang dimengerti GDAL."""
    return crs.authid() or crs.toWkt()


# ---------- perhitungan tile ----------
def to_wgs84(extent, crs):
    ct = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem("EPSG:4326"),
                                QgsProject.instance())
    return ct.transformBoundingBox(extent)


def tile_range(extent, crs, z):
    """(x0, x1, y0, y1, rect_wgs84) untuk extent pada zoom z."""
    r = to_wgs84(extent, crs)
    lat_max = min(r.yMaximum(), 85.0511)
    lat_min = max(r.yMinimum(), -85.0511)
    x0, y0 = detector._tile_xy(r.xMinimum(), lat_max, z)
    x1, y1 = detector._tile_xy(r.xMaximum(), lat_min, z)
    n = 2 ** z - 1
    x0, x1 = max(0, min(x0, n)), max(0, min(x1, n))
    y0, y1 = max(0, min(y0, n)), max(0, min(y1, n))
    return x0, x1, y0, y1, r


def estimate(extent, crs, z):
    x0, x1, y0, y1, r = tile_range(extent, crs, z)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    lat = math.radians((r.yMinimum() + r.yMaximum()) / 2.0)
    res = 2 * ORIGIN / (TILE * 2 ** z) * math.cos(lat)
    return {
        "tiles": nx * ny,
        "width": nx * TILE,
        "height": ny * TILE,
        "ground_res": res,
        "mb": nx * ny * TILE * TILE * 4 / 1e6,
    }


# ---------- cutline ----------
def prepare_cutline(layer, selected_only):
    """Tulis poligon ke GPKG sementara. Kembalikan (path, folder, extent, crs)."""
    folder = tempfile.mkdtemp(prefix="atrbpn_cut_")
    path = os.path.join(folder, "cutline.gpkg")
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.onlySelectedFeatures = bool(selected_only)
    res = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, path, QgsProject.instance().transformContext(), opts)
    if res[0] != QgsVectorFileWriter.NoError:
        shutil.rmtree(folder, ignore_errors=True)
        raise RuntimeError("Gagal menyiapkan poligon pemotong: %s" % res[1])
    extent = layer.boundingBoxOfSelected() if selected_only else layer.extent()
    return path, folder, extent, layer.crs()


# ---------- unduh tile ----------
def fetch_tile(url, retries=2):
    """Bytes gambar tile, atau None bila kosong/gagal.

    Memakai detector.http() (QgsBlockingNetworkRequest) agar pengaturan
    proxy dan autentikasi jaringan QGIS ikut berlaku.
    """
    for i in range(retries + 1):
        try:
            status, ctype, data = detector.http(url)
        except Exception:
            status, ctype, data = None, "", b""
        if status == 200:
            return data if ("image" in ctype and data) else None
        if status in (204, 404):
            return None
        time.sleep(1 + i)
    return None


class ExportTask(QgsTask):
    def __init__(self, p, on_done=None):
        """p: dict hasil ExportDialog.params() ditambah 'url' dan info cutline."""
        super().__init__("Ekspor foto udara ATR/BPN", QgsTask.CanCancel)
        self.p = p
        self.on_done = on_done
        self.error = None
        self.ok_tiles = 0
        self.empty_tiles = 0
        # semua objek QGIS diubah ke tipe Python biasa di thread utama
        ext, crs = p["extent"], p["extent_crs"]
        self.x0, self.x1, self.y0, self.y1, _ = tile_range(ext, crs, p["zoom"])
        self.bounds = (ext.xMinimum(), ext.yMinimum(), ext.xMaximum(), ext.yMaximum())
        self.bounds_srs = srs_string(crs)
        self.dst_srs = srs_string(p["dst_crs"])

    # ---------- langkah 1-2: mosaik ----------
    def _paste(self, ds, data, xoff, yoff):
        vpath = "/vsimem/atrbpn_%d_%d.img" % (xoff, yoff)
        gdal.FileFromMemBuffer(vpath, data)
        src = None
        try:
            src = gdal.Open(vpath)
            if src is None:
                return False
            if src.RasterCount == 1 and src.GetRasterBand(1).GetColorTable() is not None:
                src = gdal.Translate("", src, format="MEM", rgbExpand="rgba")
            n = src.RasterCount
            sx, sy = src.RasterXSize, src.RasterYSize

            def rd(b):
                return src.GetRasterBand(b).ReadRaster(0, 0, sx, sy, TILE, TILE, gdal.GDT_Byte)

            if n >= 3:
                bands = [rd(1), rd(2), rd(3)]
                alpha = rd(4) if n >= 4 else b"\xff" * (TILE * TILE)
            else:
                g = rd(1)
                bands = [g, g, g]
                alpha = rd(2) if n == 2 else b"\xff" * (TILE * TILE)
            for i, buf in enumerate(bands + [alpha], start=1):
                ds.GetRasterBand(i).WriteRaster(xoff, yoff, TILE, TILE, buf)
            return True
        finally:
            src = None
            gdal.Unlink(vpath)

    def _build_mosaic(self, path):
        z = self.p["zoom"]
        nx, ny = self.x1 - self.x0 + 1, self.y1 - self.y0 + 1
        ds = gdal.GetDriverByName("GTiff").Create(
            path, nx * TILE, ny * TILE, 4, gdal.GDT_Byte,
            ["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"])
        tm = 2 * ORIGIN / 2 ** z
        ds.SetGeoTransform((-ORIGIN + self.x0 * tm, tm / TILE, 0,
                            ORIGIN - self.y0 * tm, 0, -tm / TILE))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(3857)
        ds.SetProjection(srs.ExportToWkt())
        for i, ci in enumerate((gdal.GCI_RedBand, gdal.GCI_GreenBand,
                                gdal.GCI_BlueBand, gdal.GCI_AlphaBand), start=1):
            ds.GetRasterBand(i).SetColorInterpretation(ci)

        url = self.p["url"]
        jobs = [(x, y) for y in range(self.y0, self.y1 + 1) for x in range(self.x0, self.x1 + 1)]
        total = len(jobs)
        with ThreadPoolExecutor(max_workers=self.p["workers"]) as ex:
            futs = {}
            for x, y in jobs:
                u = url.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(z))
                futs[ex.submit(fetch_tile, u)] = (x, y)
            for i, f in enumerate(as_completed(futs), start=1):
                if self.isCanceled():
                    for other in futs:
                        other.cancel()
                    break
                x, y = futs[f]
                data = f.result()
                if data and self._paste(ds, data, (x - self.x0) * TILE, (y - self.y0) * TILE):
                    self.ok_tiles += 1
                else:
                    self.empty_tiles += 1
                self.setProgress(80.0 * i / total)
        ds.FlushCache()
        ds = None

    # ---------- langkah 3-4: warp, kompresi, overview ----------
    def _gdal_cb(self, start, span):
        def cb(complete, msg, data):
            self.setProgress(start + span * complete)
            return 0 if self.isCanceled() else 1
        return cb

    def _finalize(self, mosaic, tmp):
        p = self.p
        vrt = os.path.join(tmp, "warp.vrt")
        kw = dict(format="VRT", dstSRS=self.dst_srs, dstAlpha=True,
                  resampleAlg=p["resampling"], multithread=True)
        if p.get("cutline"):
            kw.update(cutlineDSName=p["cutline"], cropToCutline=True)
        elif p["clip"]:
            kw.update(outputBounds=self.bounds, outputBoundsSRS=self.bounds_srs)
        if p["pixel_size"] > 0:
            kw.update(xRes=p["pixel_size"], yRes=p["pixel_size"], targetAlignedPixels=True)
        gdal.Warp(vrt, mosaic, **kw)

        out = p["out_path"]
        if os.path.exists(out):
            gdal.GetDriverByName("GTiff").Delete(out)
        comp = p["compression"]
        co = ["TILED=YES", "BIGTIFF=IF_SAFER"]
        if comp == "JPEG":
            opts = ["-b", "1", "-b", "2", "-b", "3", "-mask", "4"]
            co += ["COMPRESS=JPEG", "PHOTOMETRIC=YCBCR", "JPEG_QUALITY=90"]
        else:
            opts = []
            co += ["COMPRESS=%s" % comp] + (["PREDICTOR=2"] if comp in ("LZW", "DEFLATE") else [])
        gdal.SetConfigOption("GDAL_TIFF_INTERNAL_MASK", "YES")
        gdal.Translate(out, vrt, options=opts, creationOptions=co,
                       callback=self._gdal_cb(80, 12))
        if self.isCanceled():
            return

        if p["overviews"]:
            ds = gdal.Open(out, gdal.GA_Update)
            levels, f = [], 2
            while max(ds.RasterXSize, ds.RasterYSize) / f >= 256:
                levels.append(f)
                f *= 2
            if levels:
                if comp == "JPEG":
                    gdal.SetConfigOption("COMPRESS_OVERVIEW", "JPEG")
                    gdal.SetConfigOption("PHOTOMETRIC_OVERVIEW", "YCBCR")
                    gdal.SetConfigOption("JPEG_QUALITY_OVERVIEW", "90")
                else:
                    gdal.SetConfigOption("COMPRESS_OVERVIEW", "DEFLATE" if comp == "NONE" else comp)
                ds.BuildOverviews("AVERAGE", levels, callback=self._gdal_cb(92, 8))
            ds = None

    def run(self):
        tmp = tempfile.mkdtemp(prefix="atrbpn_exp_")
        try:
            with gdal_exceptions():
                mosaic = os.path.join(tmp, "mosaic_3857.tif")
                self._build_mosaic(mosaic)
                if self.isCanceled():
                    return False
                if self.ok_tiles == 0:
                    self.error = ("Tidak ada satu pun tile yang berhasil diunduh. Periksa koneksi, "
                                  "URL tile, atau pastikan area ini tercakup foto udara ATR/BPN.")
                    return False
                self._finalize(mosaic, tmp)
                return not self.isCanceled()
        except Exception as e:
            self.error = str(e)
            return False
        finally:
            for k in ("GDAL_TIFF_INTERNAL_MASK", "COMPRESS_OVERVIEW",
                      "PHOTOMETRIC_OVERVIEW", "JPEG_QUALITY_OVERVIEW"):
                gdal.SetConfigOption(k, None)
            shutil.rmtree(tmp, ignore_errors=True)
            if self.p.get("cutline_dir"):
                shutil.rmtree(self.p["cutline_dir"], ignore_errors=True)

    def finished(self, result):
        if self.on_done:
            self.on_done(result, self)
