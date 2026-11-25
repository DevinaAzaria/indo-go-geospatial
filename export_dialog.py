# -*- coding: utf-8 -*-
"""Dialog pengaturan ekspor foto udara ATR/BPN."""
from qgis.core import Qgis, QgsMapLayerProxyModel, QgsProject
from qgis.gui import (QgsExtentGroupBox, QgsFileWidget, QgsMapLayerComboBox,
                      QgsProjectionSelectionWidget)
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                 QDoubleSpinBox, QFormLayout, QGroupBox, QLabel,
                                 QMessageBox, QSpinBox, QVBoxLayout)

from . import exporter

try:
    POLYGON_FILTER = Qgis.LayerFilter.PolygonLayer
except AttributeError:
    POLYGON_FILTER = QgsMapLayerProxyModel.PolygonLayer

RESAMPLING = [("Bilinear", "bilinear"), ("Cubic", "cubic"),
              ("Lanczos", "lanczos"), ("Nearest neighbour", "near")]
COMPRESSION = [("JPEG kualitas 90 (ukuran kecil, lossy)", "JPEG"),
               ("DEFLATE (lossless)", "DEFLATE"),
               ("LZW (lossless)", "LZW"),
               ("Tanpa kompresi", "NONE")]
TILE_WARN = 20000


class ExportDialog(QDialog):
    def __init__(self, iface, cfg, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Ekspor Foto Udara ATR/BPN")
        self.setMinimumWidth(520)
        canvas = iface.mapCanvas()
        canvas_crs = canvas.mapSettings().destinationCrs()
        lay = QVBoxLayout(self)

        # --- extent ---
        self.extent_box = QgsExtentGroupBox(self)
        self.extent_box.setTitle("Extent (box)")
        self.extent_box.setMapCanvas(canvas)
        self.extent_box.setOriginalExtent(canvas.extent(), canvas_crs)
        self.extent_box.setCurrentExtent(canvas.extent(), canvas_crs)
        self.extent_box.setOutputCrs(canvas_crs)
        self.extent_box.setOutputExtentFromCurrent()
        lay.addWidget(self.extent_box)

        # --- poligon pemotong ---
        cut = QGroupBox("Potong mengikuti poligon (opsional)")
        f = QFormLayout(cut)
        self.cut_layer = QgsMapLayerComboBox()
        self.cut_layer.setFilters(POLYGON_FILTER)
        self.cut_layer.setAllowEmptyLayer(True)
        self.cut_layer.setLayer(None)
        self.cut_selected = QCheckBox("Hanya fitur terpilih")
        f.addRow("Layer poligon", self.cut_layer)
        f.addRow("", self.cut_selected)
        f.addRow(QLabel("<i>Bila diisi, extent di atas diabaikan dan hasil dipotong mengikuti poligon.</i>"))
        lay.addWidget(cut)

        # --- sumber ---
        src = QGroupBox("Resolusi sumber")
        f = QFormLayout(src)
        self.zoom = QSpinBox()
        self.zoom.setRange(cfg["zmin"], cfg["zmax"])
        self.zoom.setValue(min(20, cfg["zmax"]))
        self.zoom.setToolTip("Zoom 20 kira-kira setara resolusi asli foto udara (±15 cm).")
        self.workers = QSpinBox()
        self.workers.setRange(1, 8)
        self.workers.setValue(4)
        self.info = QLabel()
        self.info.setWordWrap(True)
        f.addRow("Zoom level tile", self.zoom)
        f.addRow("Unduhan paralel", self.workers)
        f.addRow("Estimasi", self.info)
        lay.addWidget(src)

        # --- output ---
        out = QGroupBox("Output")
        f = QFormLayout(out)
        self.crs = QgsProjectionSelectionWidget()
        self.crs.setCrs(QgsProject.instance().crs())
        self.pixel = QDoubleSpinBox()
        self.pixel.setDecimals(8)  # derajat (EPSG:4326) butuh banyak desimal
        self.pixel.setRange(0, 1000)
        self.pixel.setSingleStep(0.05)
        self.pixel.setSpecialValueText("Otomatis (ikut zoom)")
        self.pixel.setToolTip("Ukuran piksel dalam unit CRS output (meter untuk UTM, derajat untuk EPSG:4326).")
        self.resampling = QComboBox()
        for label, val in RESAMPLING:
            self.resampling.addItem(label, val)
        self.compression = QComboBox()
        for label, val in COMPRESSION:
            self.compression.addItem(label, val)
        self.clip = QCheckBox("Potong tepat sesuai extent (bila tidak, ikut batas tile)")
        self.clip.setChecked(True)
        self.overviews = QCheckBox("Bangun overview (pyramid) internal")
        self.overviews.setChecked(True)
        self.add_map = QCheckBox("Tambahkan hasil ke peta")
        self.add_map.setChecked(True)
        self.out_file = QgsFileWidget()
        self.out_file.setStorageMode(QgsFileWidget.SaveFile)
        self.out_file.setFilter("GeoTIFF (*.tif *.tiff)")
        f.addRow("CRS output", self.crs)
        f.addRow("Ukuran piksel", self.pixel)
        f.addRow("Resampling", self.resampling)
        f.addRow("Kompresi", self.compression)
        f.addRow("", self.clip)
        f.addRow("", self.overviews)
        f.addRow("", self.add_map)
        f.addRow("Simpan ke", self.out_file)
        lay.addWidget(out)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Ekspor")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.extent_box.extentChanged.connect(self.update_info)
        self.zoom.valueChanged.connect(self.update_info)
        self.cut_layer.layerChanged.connect(self.update_info)
        self.cut_selected.toggled.connect(self.update_info)
        self.update_info()

    # ---------- bantu ----------
    def area(self):
        """(extent, crs) yang dipakai untuk menentukan tile."""
        lyr = self.cut_layer.currentLayer()
        if lyr is not None:
            ext = lyr.boundingBoxOfSelected() if self.cut_selected.isChecked() else lyr.extent()
            return ext, lyr.crs()
        return self.extent_box.outputExtent(), self.extent_box.outputCrs()

    def update_info(self, *_):
        ext, crs = self.area()
        if ext.isEmpty():
            self.info.setText("<span style='color:#c00'>Extent kosong.</span>")
            self._est = None
            return
        try:
            e = exporter.estimate(ext, crs, self.zoom.value())
        except Exception as ex:
            self.info.setText("Gagal menghitung: %s" % ex)
            self._est = None
            return
        self._est = e

        def num(v):
            return format(int(round(v)), ",").replace(",", ".")
        txt = ("%s tile | %s × %s px | resolusi ±%s m | ±%s MB sebelum kompresi" %
               (num(e["tiles"]), num(e["width"]), num(e["height"]),
                ("%.2f" % e["ground_res"]).replace(".", ","), num(e["mb"])))
        if e["tiles"] > TILE_WARN:
            txt = "<span style='color:#c00'>%s<br>Area sangat besar, pertimbangkan zoom lebih rendah.</span>" % txt
        self.info.setText(txt)

    def params(self):
        ext, crs = self.area()
        path = self.out_file.filePath().strip()
        if path and not path.lower().endswith((".tif", ".tiff")):
            path += ".tif"
        return {
            "extent": ext,
            "extent_crs": crs,
            "cut_layer": self.cut_layer.currentLayer(),
            "cut_selected": self.cut_selected.isChecked(),
            "zoom": self.zoom.value(),
            "workers": self.workers.value(),
            "dst_crs": self.crs.crs(),
            "pixel_size": self.pixel.value(),
            "resampling": self.resampling.currentData(),
            "compression": self.compression.currentData(),
            "clip": self.clip.isChecked(),
            "overviews": self.overviews.isChecked(),
            "add_map": self.add_map.isChecked(),
            "out_path": path,
        }

    def accept(self):
        p = self.params()
        if not p["out_path"]:
            QMessageBox.warning(self, self.windowTitle(), "Tentukan lokasi file output.")
            return
        if not p["dst_crs"].isValid():
            QMessageBox.warning(self, self.windowTitle(), "CRS output tidak valid.")
            return
        if p["cut_layer"] is not None and p["cut_selected"] and p["cut_layer"].selectedFeatureCount() == 0:
            QMessageBox.warning(self, self.windowTitle(), "Tidak ada fitur terpilih pada layer poligon.")
            return
        if self._est is None:
            QMessageBox.warning(self, self.windowTitle(), "Extent belum valid.")
            return
        if self._est["tiles"] > TILE_WARN:
            r = QMessageBox.question(
                self, self.windowTitle(),
                "Ekspor ini akan mengunduh %d tile (±%.0f MB). Lanjutkan?" %
                (self._est["tiles"], self._est["mb"]))
            if r != QMessageBox.Yes:
                return
        super().accept()
