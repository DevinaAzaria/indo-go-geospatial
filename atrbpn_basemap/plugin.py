# -*- coding: utf-8 -*-
import os
import time

from qgis.core import (Qgis, QgsApplication, QgsProject, QgsRasterLayer,
                       QgsSettings, QgsTask, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform, QgsMessageLog)
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QInputDialog, QMessageBox

from . import detector, exporter
from .export_dialog import ExportDialog

PLUGIN_NAME = "ATR BPN Basemap"
LAYER_NAME = "ATR BPN Foto Udara"
CONN_NAME = "ATR BPN Foto Udara"
SKEY = "atrbpn_basemap/"
PROP = "atrbpn_basemap"
CHECK_INTERVAL = 24 * 3600  # cek otomatis paling sering sekali sehari


def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)


class AtrBpnBasemapPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.task = None
        self.export_task = None
        self.export_dlg = None
        self.menu = "&" + PLUGIN_NAME

    # ---------- pengaturan tersimpan ----------
    def cfg(self):
        s = QgsSettings()
        return {
            "url": s.value(SKEY + "url", detector.DEFAULT_URL),
            "zmin": int(s.value(SKEY + "zmin", 16)),
            "zmax": int(s.value(SKEY + "zmax", 21)),
            "auto": s.value(SKEY + "auto_check", True, type=bool),
            "last": float(s.value(SKEY + "last_check", 0)),
        }

    def save_cfg(self, url, zmin, zmax):
        s = QgsSettings()
        s.setValue(SKEY + "url", url)
        s.setValue(SKEY + "zmin", zmin)
        s.setValue(SKEY + "zmax", zmax)

    # ---------- GUI ----------
    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self._add(icon, "Tambahkan Foto Udara ATR/BPN", self.add_layer, toolbar=True)
        self._add(QIcon(), "Ekspor foto udara ke GeoTIFF...", self.open_export)
        self._add(QIcon(), "Cek && perbarui URL dari situs ATR/BPN", lambda: self.check_update(manual=True))
        self._add(QIcon(), "Atur URL secara manual...", self.set_manual)
        self.auto_action = self._add(QIcon(), "Cek otomatis saat QGIS dibuka", self.toggle_auto)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(self.cfg()["auto"])
        self._add(QIcon(), "Tentang plugin", self.about)
        QTimer.singleShot(5000, self.auto_check)

    def _add(self, icon, text, cb, toolbar=False):
        a = QAction(icon, text, self.iface.mainWindow())
        a.triggered.connect(cb)
        self.iface.addPluginToMenu(self.menu, a)
        if toolbar:
            self.iface.addToolBarIcon(a)
        self.actions.append(a)
        return a

    def unload(self):
        self._unloaded = True
        if self.export_dlg is not None:
            self.export_dlg.close()
            self.export_dlg = None
        for a in self.actions:
            self.iface.removePluginMenu(self.menu, a)
            self.iface.removeToolBarIcon(a)
        self.actions = []

    def bar(self, msg, level=Qgis.Info, dur=6):
        self.iface.messageBar().pushMessage(PLUGIN_NAME, msg, level, dur)

    # ---------- aksi ----------
    def add_layer(self):
        c = self.cfg()
        uri = detector.build_uri(c["url"], c["zmin"], c["zmax"])
        lyr = QgsRasterLayer(uri, LAYER_NAME, "wms")
        if not lyr.isValid():
            self.bar("Layer tidak valid. Coba menu 'Cek & perbarui URL'.", Qgis.Warning)
            return
        lyr.setCustomProperty(PROP, 1)
        QgsProject.instance().addMapLayer(lyr)
        self.update_connection(c["url"], c["zmin"], c["zmax"])
        self.bar("Foto udara ATR/BPN ditambahkan (zoom %d-%d)." % (c["zmin"], c["zmax"]), Qgis.Success)

    def toggle_auto(self, checked):
        QgsSettings().setValue(SKEY + "auto_check", bool(checked))

    def set_manual(self):
        c = self.cfg()
        url, ok = QInputDialog.getText(self.iface.mainWindow(), PLUGIN_NAME,
                                       "URL tile (pakai {x}, {y}, {z}):", text=c["url"])
        if ok and url.strip():
            self.apply_new(url.strip(), c["zmin"], c["zmax"], note="URL diatur manual")

    def about(self):
        c = self.cfg()
        last = time.strftime("%d-%m-%Y %H:%M", time.localtime(c["last"])) if c["last"] else "belum pernah"
        QMessageBox.information(self.iface.mainWindow(), PLUGIN_NAME,
            "Menambahkan foto udara Peta Dasar ATR/BPN sebagai XYZ tile, lengkap dengan header Referer.\n\n"
            "Plugin membaca skrip peta di petadasar.atrbpn.go.id untuk menemukan URL tile terbaru, "
            "mengujinya, lalu memperbarui layer di proyek dan koneksi XYZ di Browser.\n\n"
            "URL saat ini:\n%s\nZoom: %d-%d\nPengecekan terakhir: %s" % (c["url"], c["zmin"], c["zmax"], last))

    # ---------- ekspor ----------
    def open_export(self):
        if self.export_task is not None:
            self.bar("Ekspor sebelumnya masih berjalan (lihat panel Task di kanan bawah).", Qgis.Warning)
            return
        if self.export_dlg is None:
            # non-modal supaya opsi "Draw on canvas" pada extent bisa dipakai
            self.export_dlg = ExportDialog(self.iface, self.cfg())
            self.export_dlg.accepted.connect(self.start_export)
        self.export_dlg.update_info()
        self.export_dlg.show()
        self.export_dlg.raise_()
        self.export_dlg.activateWindow()

    def start_export(self):
        p = self.export_dlg.params()
        p["url"] = self.cfg()["url"]
        if p["cut_layer"] is not None:
            try:
                path, folder, ext, crs = exporter.prepare_cutline(p["cut_layer"], p["cut_selected"])
            except Exception as e:
                self.bar(str(e), Qgis.Critical, 10)
                return
            p.update(cutline=path, cutline_dir=folder, extent=ext, extent_crs=crs)
        p.pop("cut_layer", None)
        self.export_task = exporter.ExportTask(p, on_done=self._export_done)
        QgsApplication.taskManager().addTask(self.export_task)
        self.bar("Ekspor dimulai, progres terlihat di panel Task (kanan bawah).", dur=5)

    def _export_done(self, ok, task):
        self.export_task = None
        p = task.p
        info = "%d tile terunduh, %d kosong/gagal" % (task.ok_tiles, task.empty_tiles)
        status = "selesai" if ok else ("dibatalkan" if task.isCanceled() else "gagal: %s" % task.error)
        log("Ekspor %s (%s)" % (status, info), Qgis.Info if ok else Qgis.Warning)
        if not ok:
            if task.isCanceled():
                self.bar("Ekspor dibatalkan.", Qgis.Warning)
            else:
                self.bar("Ekspor gagal: %s" % (task.error or "tidak diketahui"), Qgis.Critical, 15)
            return
        if p["add_map"]:
            name = os.path.splitext(os.path.basename(p["out_path"]))[0]
            QgsProject.instance().addMapLayer(QgsRasterLayer(p["out_path"], name))
        level = Qgis.Success if task.empty_tiles == 0 else Qgis.Warning
        self.bar("Ekspor selesai: %s (%s)" % (p["out_path"], info), level, 12)

    # ---------- deteksi ----------
    def _canvas_point(self):
        try:
            canvas = self.iface.mapCanvas()
            ct = QgsCoordinateTransform(canvas.mapSettings().destinationCrs(),
                                        QgsCoordinateReferenceSystem("EPSG:4326"), QgsProject.instance())
            p = ct.transform(canvas.extent().center())
            return [(p.x(), p.y())]
        except Exception:
            return []

    def auto_check(self):
        if getattr(self, "_unloaded", False):
            return
        c = self.cfg()
        if c["auto"] and time.time() - c["last"] > CHECK_INTERVAL:
            self.check_update(manual=False)

    def check_update(self, manual=True):
        if self.task is not None:
            if manual:
                self.bar("Pengecekan masih berjalan...")
            return
        pts = self._canvas_point()
        if manual:
            self.bar("Memeriksa situs ATR/BPN...", dur=3)

        def run(task):
            return detector.detect(extra_points=pts, log=lambda m: log(m))

        def done(exc, result=None):
            self.task = None
            if exc is not None or result is None:
                log("Gagal deteksi: %s" % exc, Qgis.Warning)
                if manual:
                    self.bar("Gagal membaca situs ATR/BPN: %s" % exc, Qgis.Warning, 10)
                return
            QgsSettings().setValue(SKEY + "last_check", time.time())
            c = self.cfg()
            log("Terdeteksi: %s (zoom %s-%s, terverifikasi=%s)" %
                (result["url"], result["zmin"], result["zmax"], result["verified"]))
            if result["url"] != c["url"] or result["zmin"] != c["zmin"] or result["zmax"] != c["zmax"]:
                if not result["verified"]:
                    self.bar("URL baru terdeteksi tapi tile uji belum merespons; URL lama dipertahankan. "
                             "Kandidat: %s" % result["url"], Qgis.Warning, 15)
                    return
                self.apply_new(result["url"], result["zmin"], result["zmax"], note="URL diperbarui otomatis")
            elif manual:
                msg = "URL masih sama dan aktif." if result["verified"] else \
                      "URL masih sama, tapi tile uji tidak merespons (server mungkin sedang gangguan)."
                self.bar(msg, Qgis.Success if result["verified"] else Qgis.Warning)

        self.task = QgsTask.fromFunction("Cek URL ATR/BPN", run, on_finished=done)
        QgsApplication.taskManager().addTask(self.task)

    def apply_new(self, url, zmin, zmax, note=""):
        old = self.cfg()["url"]
        self.save_cfg(url, zmin, zmax)
        n = self.update_project_layers(old, url, zmin, zmax)
        self.update_connection(url, zmin, zmax)
        self.bar("%s: %s (%d layer di proyek diperbarui)" % (note, url, n), Qgis.Success, 12)

    def update_project_layers(self, old_url, url, zmin, zmax):
        uri = detector.build_uri(url, zmin, zmax)
        n = 0
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.providerType() != "wms":
                continue
            src = lyr.source()
            ours = lyr.customProperty(PROP) or "petadasar" in src or "meritech" in src
            # semua layer foto udara ATR (termasuk URL lama /main/wms/ dan proxy meritech),
            # kecuali layer ATR lain seperti peta dasar ?tmi/
            is_foto = lyr.customProperty(PROP) or ("tmi/" not in src and "tmi%2F" not in src)
            if ours and is_foto:
                lyr.setDataSource(uri, lyr.name(), "wms")
                lyr.setCustomProperty(PROP, 1)
                lyr.triggerRepaint()
                n += 1
        return n

    def update_connection(self, url, zmin, zmax):
        """Simpan/ubah koneksi XYZ di panel Browser."""
        try:
            from qgis.core import QgsXyzConnection, QgsXyzConnectionUtils
            c = QgsXyzConnection()
            c.name = CONN_NAME
            c.url = url
            c.zMin = zmin
            c.zMax = zmax
            try:
                from qgis.core import QgsHttpHeaders
                h = QgsHttpHeaders()
                h.setValue("referer", detector.REFERER)
                c.httpHeaders = h
            except Exception:
                c.referer = detector.REFERER
            QgsXyzConnectionUtils.addConnection(c)
            try:
                self.iface.browserModel().reload()
            except Exception:
                pass
        except Exception as e:
            log("Gagal memperbarui koneksi XYZ: %s" % e, Qgis.Warning)
