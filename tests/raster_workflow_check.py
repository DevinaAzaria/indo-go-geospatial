# -*- coding: utf-8 -*-
# INDO-GO GeoSpatial, 2026-11-27; GPL-2.0-or-later.
"""Simulated raster dialog tests. No real QGIS, GDAL or network."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lifecycle_check import fake_qgis, Interface


class RasterWorkflowChecks(unittest.TestCase):
    def setUp(self):
        import sys
        self.modules = patch.dict(sys.modules, fake_qgis())
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.plugin_module = importlib.import_module("indo_go_geospatial.plugin")
        self.plugin = self.plugin_module.IndoGoGeoSpatialPlugin(Interface())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.tif"
        self.path.write_bytes(b"II\x2a\x00mock TIFF; not a GDAL fixture")
        self.layer = Mock()
        self.layer.isValid.return_value = True
        self.layer.crs.return_value.isValid.return_value = True
        self.project = Mock()
        self.raster = self.replace("QgsRasterLayer", Mock(return_value=self.layer))
        self.replace("QgsProject", Mock(instance=Mock(return_value=self.project)))
        self.picker = Mock(return_value=(str(self.path), ""))
        self.replace("QFileDialog", Mock(getOpenFileName=self.picker))
        self.source = Mock(return_value=("Synthetic test data", True))
        self.replace("QInputDialog", Mock(getText=self.source))
        self.messages = Mock(Yes=1, No=2)
        self.messages.question.return_value = 1
        self.replace("QMessageBox", self.messages)

    def replace(self, name, value):
        p = patch.object(self.plugin_module, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def test_success_with_attribution(self):
        self.plugin.open_local_raster()
        self.raster.assert_called_once_with(str(self.path.resolve()), "synthetic", "gdal")
        self.layer.setCustomProperty.assert_called_once_with("indo_go_geospatial/source", "Synthetic test data")
        self.assertIn("Synthetic test data", self.layer.metadata.return_value.setAbstract.call_args.args[0])
        self.project.addMapLayer.assert_called_once_with(self.layer)
        self.messages.information.assert_called_once()

    def test_cancel_picker(self):
        self.picker.return_value = ("", "")
        self.plugin.open_local_raster()
        self.source.assert_not_called()
        self.raster.assert_not_called()

    def test_cancel_source(self):
        self.source.return_value = ("", False)
        self.plugin.open_local_raster()
        self.raster.assert_not_called()

    def test_blank_source(self):
        self.source.return_value = ("  ", True)
        self.plugin.open_local_raster()
        self.messages.warning.assert_called_once()
        self.raster.assert_not_called()

    def test_decline_usage(self):
        self.messages.question.return_value = 2
        self.plugin.open_local_raster()
        self.raster.assert_not_called()

    def test_reject_invalid_file(self):
        self.path.write_bytes(b"not TIFF")
        self.plugin.open_local_raster()
        self.messages.warning.assert_called_once()
        self.raster.assert_not_called()

    def test_reject_invalid_layer(self):
        self.layer.isValid.return_value = False
        self.plugin.open_local_raster()
        self.messages.warning.assert_called_once()
        self.project.addMapLayer.assert_not_called()

    def test_reject_invalid_crs(self):
        self.layer.crs.return_value.isValid.return_value = False
        self.plugin.open_local_raster()
        self.messages.warning.assert_called_once()
        self.project.addMapLayer.assert_not_called()

    def test_provider_exception(self):
        self.raster.side_effect = RuntimeError("simulated provider error")
        self.plugin.open_local_raster()
        self.messages.warning.assert_called_once()
        self.project.addMapLayer.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
