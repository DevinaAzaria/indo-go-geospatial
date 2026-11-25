# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: derivative branding; GPL-2.0-or-later.
import configparser
import contextlib
import os
import time

from qgis.core import (Qgis, QgsApplication, QgsProject, QgsRasterLayer,
                       QgsSettings, QgsTask, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform, QgsMessageLog)
from qgis.PyQt.QtCore import QTimer, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QInputDialog, QMessageBox, QPushButton

from . import detector, exporter
from .export_dialog import ExportDialog

PLUGIN_NAME = "INDO-GO GeoSpatial"
LAYER_NAME = "INDO-GO | Foto Udara ATR/BPN"
CONN_NAME = "INDO-GO Foto Udara ATR/BPN"
SKEY = "atrbpn_basemap/"
PROP = "atrbpn_basemap"
CHECK_INTERVAL = 24 * 3600  # cek otomatis paling sering sekali sehari
# Token sesi di URL tile ATR/BPN berganti setiap beberapa menit; tile URL di layer
# diperiksa sesering ini dan tokennya diperbarui bila tile uji kosong.
TOKEN_CHECK_MS = 60 * 1000


def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)


def plugin_version():
    cp = configparser.ConfigParser()
    try:
        cp.read(os.path.join(os.path.dirname(__file__), "metadata.txt"), encoding="utf-8")
        return cp["general"]["version"].strip()
    except Exception:
        return "0"


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
        url = s.value(SKEY + "url", detector.DEFAULT_URL)
        return {
            "url": url,
            "template": s.value(SKEY + "template", "") or url,
            "zmin": int(s.value(SKEY + "zmin", 16)),
            "zmax": int(s.value(SKEY + "zmax", 21)),
            "auto": s.value(SKEY + "auto_check", True, type=bool),
            "last": float(s.value(SKEY + "last_check", 0)),
        }

    def save_cfg(self, url, zmin, zmax, template=None):
        s = QgsSettings()
        s.setValue(SKEY + "url", url)
        if template:
            s.setValue(SKEY + "template", template)
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
        self.token_task = None
        self.token_timer = QTimer()
        self.token_timer.timeout.connect(self.token_tick)
        self.token_timer.start(TOKEN_CHECK_MS)
        QTimer.singleShot(8000, self.token_tick)
        # proyek yang dibuka bisa berisi layer dengan token lama
        QgsProject.instance().readProject.connect(self._on_project_read)

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
        if getattr(self, "token_timer", None) is not None:
            self.token_timer.stop()
            self.token_timer = None
        with contextlib.suppress(Exception):
            QgsProject.instance().readProject.disconnect(self._on_project_read)
        if self.export_dlg is not None:
            self.export_dlg.close()
            self.export_dlg = None
        for a in self.actions:
            self.iface.removePluginMenu(self.menu, a)
            self.iface.removeToolBarIcon(a)
        self.actions = []

    def bar(self, msg, level=Qgis.Info, dur=6):
        self.iface.messageBar().pushMessage(PLUGIN_NAME, msg, level, dur)

    def bar_link(self, msg, url, label, level=Qgis.Warning, dur=0):
        """Pesan di message bar dengan tombol yang membuka url di browser."""
        bar = self.iface.messageBar()
        w = bar.createMessage(PLUGIN_NAME, msg)
        b = QPushButton(label, w)
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        w.layout().addWidget(b)
        bar.pushWidget(w, level, dur)

    def notify_remote(self, remote):
        """Tampilkan info versi baru dan pengumuman dari config.json (sekali per nilai)."""
        s = QgsSettings()
        latest = str(remote.get("latest_version") or "")
        if latest and detector.version_tuple(latest) > detector.version_tuple(detector.UPSTREAM_BASELINE) \
                and s.value(SKEY + "notified_version", "") != latest:
            s.setValue(SKEY + "notified_version", latest)
            self.bar_link("Versi upstream %s tersedia (baseline: %s)." % (latest, detector.UPSTREAM_BASELINE),
                          detector.RELEASES_URL, "Unduh di GitHub", Qgis.Info)
        msg = str(remote.get("message") or "").strip()
        if msg and s.value(SKEY + "notified_message", "") != msg:
            s.setValue(SKEY + "notified_message", msg)
            self.bar_link(msg, detector.REPO_URL, "Buka GitHub", Qgis.Info)

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
        # token sesi cepat kedaluwarsa: periksa segera di latar belakang (tanpa membekukan QGIS)
        QTimer.singleShot(0, self.token_tick)

    def toggle_auto(self, checked):
        QgsSettings().setValue(SKEY + "auto_check", bool(checked))

    def set_manual(self):
        c = self.cfg()
        url, ok = QInputDialog.getText(self.iface.mainWindow(), PLUGIN_NAME,
                                       "URL tile (pakai {x}, {y}, {z}):", text=c["url"])
        if ok and url.strip():
            url = url.strip()
            # template boleh memuat {token}; URL dengan token jadi dipakai apa adanya
            live = detector.refresh(url, log=log, attempts=1) if detector.needs_token(url) else url
            if not live:
                self.bar("Token sesi untuk {token} tidak didapat; URL tidak diubah.", Qgis.Warning, 10)
                return
            self.apply_new(live, c["zmin"], c["zmax"], note="URL diatur manual", template=url)

    def about(self):
        c = self.cfg()
        last = time.strftime("%d-%m-%Y %H:%M", time.localtime(c["last"])) if c["last"] else "belum pernah"
        QMessageBox.information(self.iface.mainWindow(), PLUGIN_NAME,
            "Menambahkan foto udara Peta Dasar ATR/BPN sebagai XYZ tile, lengkap dengan header Referer.\n\n"
            "Plugin membaca skrip peta di petadasar.atrbpn.go.id untuk menemukan URL tile terbaru, "
            "mengujinya, lalu memperbarui layer di proyek dan koneksi XYZ di Browser.\n\n"
            "URL saat ini:\n%s\nTemplate: %s\nZoom: %d-%d\nPengecekan terakhir: %s\n\n"
            "Kredit data:\n"
            "Foto udara dan Peta Dasar bersumber dari Kementerian Agraria dan Tata Ruang/"
            "Badan Pertanahan Nasional (ATR/BPN) Republik Indonesia, melalui layanan "
            "https://petadasar.atrbpn.go.id. Hak atas data sepenuhnya milik Kementerian ATR/BPN.\n\n"
            "INDO-GO GeoSpatial merupakan turunan independen ATR BPN Basemap 1.1.3, "
            "karya asli Fadli Arya Wisnu Baradi (GPL-2.0-or-later). Tidak berafiliasi dengan ATR/BPN.\n\n"
            "Versi INDO-GO: %s\nRepositori dan laporan masalah: %s"
            % (c["url"], c["template"], c["zmin"], c["zmax"], last, plugin_version(), detector.PROJECT_URL))

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
        c = self.cfg()
        # token kedaluwarsa diperbarui oleh ExportTask sendiri (di thread latar belakang)
        p["url"], p["template"] = c["url"], c["template"]
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
        # pengguna yang baru memperbarui dari versi < 1.1.1 belum punya template URL
        first_run = not QgsSettings().contains(SKEY + "template")
        if c["auto"] and (first_run or time.time() - c["last"] > CHECK_INTERVAL):
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
                # ditampilkan juga pada cek otomatis, supaya pengguna tahu kenapa layer kosong
                self.bar_link("URL foto udara ATR/BPN tidak dapat ditemukan (%s). Kemungkinan situs "
                              "ATR/BPN berubah. Cek versi plugin terbaru atau laporkan masalahnya." % exc,
                              detector.RELEASES_URL, "Buka GitHub", Qgis.Warning)
                return
            QgsSettings().setValue(SKEY + "last_check", time.time())
            self.notify_remote(result.get("remote") or {})
            c = self.cfg()
            log("Terdeteksi: %s (zoom %s-%s, terverifikasi=%s, sumber=%s)" %
                (result["url"], result["zmin"], result["zmax"], result["verified"], result.get("source")))
            src = " dari konfigurasi GitHub" if result.get("source") == "config" else ""
            tpl = result.get("template") or result["url"]
            if tpl == c["template"] and result["verified"] and result["url"] != c["url"] \
                    and result["zmin"] == c["zmin"] and result["zmax"] == c["zmax"]:
                # hanya token sesi yang berganti
                self.apply_token(result["url"])
                if manual:
                    self.bar("URL masih sama dan aktif%s (token sesi diperbarui)." % src, Qgis.Success)
                return
            if tpl != c["template"] or result["zmin"] != c["zmin"] or result["zmax"] != c["zmax"]:
                if not result["verified"]:
                    self.bar_link("URL baru terdeteksi tapi tile uji belum merespons; URL lama dipertahankan. "
                                  "Kandidat: %s" % result["url"], detector.RELEASES_URL, "Buka GitHub",
                                  Qgis.Warning, 15)
                    return
                self.apply_new(result["url"], result["zmin"], result["zmax"],
                               note="URL diperbarui otomatis" + src, template=tpl)
            elif manual:
                if result["verified"]:
                    self.bar("URL masih sama dan aktif%s." % src, Qgis.Success)
                else:
                    self.bar_link("URL masih sama, tapi tile uji tidak merespons (server ATR/BPN mungkin "
                                  "sedang gangguan, atau situsnya berubah).", detector.RELEASES_URL,
                                  "Buka GitHub", Qgis.Warning, 15)

        self.task = QgsTask.fromFunction("Cek URL ATR/BPN", run, on_finished=done)
        QgsApplication.taskManager().addTask(self.task)

    # ---------- token sesi ----------
    def _on_project_read(self, *args):
        QTimer.singleShot(2000, self.token_tick)

    def _has_atr_layer(self):
        return any(self._is_foto_layer(ly) for ly in QgsProject.instance().mapLayers().values())

    def token_tick(self):
        """Periksa token sesi di URL tile; perbarui di latar belakang bila sudah kedaluwarsa."""
        if getattr(self, "_unloaded", False) or self.token_task is not None or self.task is not None:
            return
        c = self.cfg()
        if not detector.needs_token(c["template"]) or not self._has_atr_layer():
            return
        pts = self._canvas_point()
        url, tpl = c["url"], c["template"]

        def run(task):
            if detector.test_url(url, pts):
                return None
            return detector.refresh(tpl, pts, log=lambda m: log(m)) or ""

        def done(exc, result=None):
            self.token_task = None
            if exc is not None:
                log("Gagal memeriksa token sesi: %s" % exc, Qgis.Warning)
            elif result == "":
                log("Token sesi ATR/BPN kedaluwarsa dan belum bisa diperbarui; dicoba lagi nanti.",
                    Qgis.Warning)
            elif result and self.cfg()["template"] == tpl:
                self.apply_token(result)

        flags = QgsTask.CanCancel
        if hasattr(QgsTask, "Silent"):  # QGIS >= 3.26: jangan munculkan notifikasi task
            flags = flags | QgsTask.Silent
        self.token_task = QgsTask.fromFunction("Perbarui token ATR/BPN", run, on_finished=done,
                                               flags=flags)
        QgsApplication.taskManager().addTask(self.token_task)

    def apply_token(self, url):
        """Ganti URL (token baru) di pengaturan, layer proyek, dan koneksi XYZ tanpa pesan."""
        c = self.cfg()
        if url == c["url"]:
            return
        self.save_cfg(url, c["zmin"], c["zmax"])
        n = self.update_project_layers(c["url"], url, c["zmin"], c["zmax"])
        self.update_connection(url, c["zmin"], c["zmax"])
        log("Token sesi diperbarui (%d layer)" % n)

    def apply_new(self, url, zmin, zmax, note="", template=None):
        old = self.cfg()["url"]
        self.save_cfg(url, zmin, zmax, template or url)
        n = self.update_project_layers(old, url, zmin, zmax)
        self.update_connection(url, zmin, zmax)
        self.bar("%s: %s (%d layer di proyek diperbarui)" % (note, url, n), Qgis.Success, 12)

    @staticmethod
    def _is_foto_layer(lyr):
        """Layer foto udara ATR (termasuk URL lama /main/wms/ dan proxy meritech),
        kecuali layer ATR lain seperti peta dasar ?tmi/."""
        if lyr.providerType() != "wms":
            return False
        if lyr.customProperty(PROP):
            return True
        src = lyr.source()
        ours = "petadasar" in src or "meritech" in src
        return ours and "tmi/" not in src and "tmi%2F" not in src

    def update_project_layers(self, old_url, url, zmin, zmax):
        uri = detector.build_uri(url, zmin, zmax)
        n = 0
        for lyr in QgsProject.instance().mapLayers().values():
            if self._is_foto_layer(lyr):
                lyr.setDataSource(uri, lyr.name(), "wms")
                lyr.setCustomProperty(PROP, 1)
                lyr.triggerRepaint()
                n += 1
        return n

    def update_connection(self, url, zmin, zmax):
        """Simpan/ubah koneksi XYZ di panel Browser.

        QgsXyzConnection/QgsXyzConnectionUtils tidak tersedia di API Python,
        jadi koneksi ditulis langsung ke QgsSettings dengan kunci yang dipakai QGIS.
        """
        try:
            s = QgsSettings()
            if Qgis.QGIS_VERSION_INT >= 33000:
                base = "connections/xyz/items/%s/" % CONN_NAME
                s.setValue(base + "http-header", {"referer": detector.REFERER})
                defaults = (("authcfg", ""), ("username", ""), ("password", ""),
                            ("interpretation", ""), ("tile-pixel-ratio", 0))
            else:
                base = "qgis/connections-xyz/%s/" % CONN_NAME
                s.setValue(base + "referer", detector.REFERER)
                defaults = (("authcfg", ""), ("username", ""), ("password", ""),
                            ("tilePixelRatio", 0))
            s.setValue(base + "url", url)
            s.setValue(base + "zmin", int(zmin))
            s.setValue(base + "zmax", int(zmax))
            for k, v in defaults:
                if s.value(base + k) is None:
                    s.setValue(base + k, v)
            with contextlib.suppress(Exception):
                self.iface.browserModel().reload()
        except Exception as e:
            log("Gagal memperbarui koneksi XYZ: %s" % e, Qgis.Warning)
