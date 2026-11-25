# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: lifecycle preview; GPL-2.0-or-later.
"""Mock-only lifecycle tests: no QGIS installation or network required."""
import importlib
import sys
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Signal:
    def connect(self, callback):
        self.callback = callback
    def emit(self):
        self.callback()


class Action:
    def __init__(self, icon, text, parent):
        self.icon, self.text, self.parent = icon, text, parent
        self.triggered = Signal()
        self.deleted = False
    def deleteLater(self):
        self.deleted = True


class Icon:
    def __init__(self, path):
        assert Path(path).is_file()
        self.path = path


class MessageBox:
    messages = []
    @classmethod
    def information(cls, parent, title, text):
        cls.messages.append((title, text))


class Interface:
    def __init__(self):
        self.menu, self.toolbar = [], []
    def mainWindow(self):
        return self
    def addPluginToMenu(self, menu, action):
        self.menu.append((menu, action))
    def addToolBarIcon(self, action):
        self.toolbar.append(action)
    def removePluginMenu(self, menu, action):
        self.menu.remove((menu, action))
    def removeToolBarIcon(self, action):
        self.toolbar.remove(action)


def fake_qgis():
    modules = {n: ModuleType(n) for n in ("qgis", "qgis.PyQt", "qgis.PyQt.QtGui", "qgis.PyQt.QtWidgets")}
    modules["qgis.PyQt.QtGui"].QIcon = Icon
    modules["qgis.PyQt.QtWidgets"].QAction = Action
    modules["qgis.PyQt.QtWidgets"].QMessageBox = MessageBox
    return modules


class LifecycleChecks(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.dict(sys.modules, fake_qgis())
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.pkg = importlib.import_module("indo_go_geospatial")
        self.iface = Interface()
        self.plugin = self.pkg.classFactory(self.iface)
        MessageBox.messages.clear()
        self.addCleanup(self.plugin.unload)

    def test_activate_and_unload(self):
        self.plugin.initGui()
        self.assertEqual(len(self.iface.menu), 1)
        self.assertEqual(len(self.iface.toolbar), 1)
        action = self.iface.toolbar[0]
        self.assertTrue(action.icon.path.endswith("icon.svg"))
        self.plugin.unload()
        self.assertEqual(self.iface.menu, [])
        self.assertEqual(self.iface.toolbar, [])
        self.assertTrue(action.deleted)

    def test_idempotent_activation_and_reload(self):
        self.plugin.initGui()
        self.plugin.initGui()
        self.assertEqual(len(self.iface.toolbar), 1)
        self.plugin.unload()
        self.plugin.unload()
        self.plugin.initGui()
        self.assertEqual(len(self.iface.toolbar), 1)

    def test_about_and_no_inherited_network_imports(self):
        self.plugin.initGui()
        self.iface.toolbar[0].triggered.emit()
        title, text = MessageBox.messages[-1]
        self.assertEqual(title, "INDO-GO GeoSpatial")
        for expected in ("0.1.2", "disabled", "Fadli Arya Wisnu Baradi", "not affiliated"):
            self.assertIn(expected, text)
        for name in ("detector", "exporter", "export_dialog"):
            self.assertNotIn("indo_go_geospatial." + name, sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
