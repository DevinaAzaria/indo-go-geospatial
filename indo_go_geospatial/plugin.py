# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: local raster preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: lifecycle preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Local raster QGIS preview derived from ATR BPN Basemap 1.1.3.
Original author: Fadli Arya Wisnu Baradi. Full original implementation remains in Git history.
"""
import configparser
from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QFileDialog, QInputDialog
from qgis.core import QgsProject, QgsRasterLayer

from .security_policy import NETWORK_DISABLED
from .local_raster import validate_local_tiff, validate_attribution

PLUGIN_NAME = "INDO-GO GeoSpatial"
SKEY = "indo_go_geospatial/"
PROP = "indo_go_geospatial"


def plugin_version():
    cp = configparser.ConfigParser()
    cp.read(str(Path(__file__).with_name("metadata.txt")), encoding="utf-8")
    return cp["general"]["version"].strip()


class IndoGoGeoSpatialPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.menu = "&" + PLUGIN_NAME

    def initGui(self):
        if self.actions:
            return
        icon = QIcon(str(Path(__file__).with_name("icon.svg")))
        action = QAction(icon, "Tentang INDO-GO GeoSpatial", self.iface.mainWindow())
        action.triggered.connect(self.about)
        self.iface.addPluginToMenu(self.menu, action)
        self.iface.addToolBarIcon(action)
        self.actions.append(action)
        local_action = QAction(icon, "Buka GeoTIFF lokal...", self.iface.mainWindow())
        local_action.triggered.connect(self.open_local_raster)
        self.iface.addPluginToMenu(self.menu, local_action)
        self.actions.append(local_action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            if action is self.actions[0]:
                self.iface.removeToolBarIcon(action)
            action.deleteLater()
        self.actions.clear()

    def about(self):
        QMessageBox.information(self.iface.mainWindow(), PLUGIN_NAME,
            "INDO-GO GeoSpatial " + plugin_version() + "\n\n" + NETWORK_DISABLED +
            "\n\nBased on ATR BPN Basemap 1.1.3 by Fadli Arya Wisnu Baradi (GPL-2.0-or-later)." +
            "\nIndependent project; not affiliated with ATR/BPN." +
            "\nData rights remain with the respective provider.")

    def open_local_raster(self):
        parent = self.iface.mainWindow()
        raw, _ = QFileDialog.getOpenFileName(parent, "Pilih GeoTIFF lokal", "", "GeoTIFF (*.tif *.tiff *.TIF *.TIFF)")
        if not raw:
            return
        try:
            path = validate_local_tiff(raw)
        except (OSError, ValueError, RuntimeError):
            QMessageBox.warning(parent, PLUGIN_NAME, "File tidak valid atau bukan TIFF lokal yang dapat dibaca.")
            return
        source, ok = QInputDialog.getText(parent, PLUGIN_NAME, "Sumber data / atribusi (wajib):")
        if not ok:
            return
        try:
            source = validate_attribution(source)
        except ValueError:
            QMessageBox.warning(parent, PLUGIN_NAME, "Sumber data wajib diisi (maksimum 250 karakter, satu baris).")
            return
        if QMessageBox.question(parent, PLUGIN_NAME,
                "Pastikan file berasal dari sumber tepercaya, Anda berhak menggunakannya, dan pengujian dilakukan tanpa koneksi jaringan. Lanjutkan?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            layer = QgsRasterLayer(str(path), path.stem, "gdal")
            if not layer.isValid() or not layer.crs().isValid():
                QMessageBox.warning(parent, PLUGIN_NAME, "Raster tidak valid atau CRS tidak tersedia. Periksa georeferensi sumber.")
                return
            metadata = layer.metadata()
            metadata.setTitle(path.stem)
            metadata.setAbstract("Sumber data (diisi pengguna, belum diverifikasi): " + source +
                                 "\nPeta indikatif; bukan bukti hak atau batas bidang resmi.")
            layer.setMetadata(metadata)
            layer.setCustomProperty(PROP + "/source", source)
            QgsProject.instance().addMapLayer(layer)
        except Exception:
            QMessageBox.warning(parent, PLUGIN_NAME, "Raster tidak dapat ditambahkan. Periksa file dan log QGIS.")
            return
        QMessageBox.information(parent, PLUGIN_NAME, "GeoTIFF lokal ditambahkan. Informasi sumber tersimpan pada metadata layer.")
