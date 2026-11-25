# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: offline security preview; GPL-2.0-or-later.
"""Offline-only QGIS shell derived from ATR BPN Basemap 1.1.3.
Original author: Fadli Arya Wisnu Baradi. Full original implementation remains in Git history.
"""
import configparser
from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .security_policy import NETWORK_DISABLED

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
        icon = QIcon(str(Path(__file__).with_name("icon.png")))
        action = QAction(icon, "Tentang INDO-GO GeoSpatial", self.iface.mainWindow())
        action.triggered.connect(self.about)
        self.iface.addPluginToMenu(self.menu, action)
        self.iface.addToolBarIcon(action)
        self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
            action.deleteLater()
        self.actions.clear()

    def about(self):
        QMessageBox.information(self.iface.mainWindow(), PLUGIN_NAME,
            "INDO-GO GeoSpatial " + plugin_version() + "\n\n" + NETWORK_DISABLED +
            "\n\nBased on ATR BPN Basemap 1.1.3 by Fadli Arya Wisnu Baradi (GPL-2.0-or-later)." +
            "\nIndependent project; not affiliated with ATR/BPN." +
            "\nData rights remain with the respective provider.")
