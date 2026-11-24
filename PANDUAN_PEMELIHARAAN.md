# Panduan Pemeliharaan ATR BPN Basemap

Catatan untuk pengembang. Berkas ini tidak ikut masuk ZIP plugin.

## Cara kerja pencarian URL (sejak v1.1.0)

Setiap kali pengecekan URL berjalan (otomatis sekali sehari, atau manual lewat menu), plugin:

1. Membaca `config.json` dari repo GitHub:
   `https://raw.githubusercontent.com/fadliarya/atrbpn-basemap/main/config.json`
2. Mendeteksi URL tile dari situs ATR/BPN (halaman utama, halaman peta lewat `post_pages`, dan skrip peta di `scripts`), lalu menguji tile contoh.
3. Bila deteksi otomatis gagal atau tile uji tidak merespons, plugin menguji `tile_url` dari `config.json` dan memakainya bila berhasil.
4. Bila keduanya gagal, pengguna mendapat pesan dengan tombol **Buka GitHub**.

Jadi, saat situs ATR/BPN berubah, **ubah dulu `config.json`**. Rilis kode baru hanya diperlukan bila cara deteksinya sendiri harus diubah.

## Isi config.json

| Kunci | Fungsi |
|---|---|
| `schema` | Versi format berkas. Biarkan `1` |
| `updated` | Tanggal terakhir diubah (hanya catatan, tampil di log plugin) |
| `tile_url` | URL tile foto udara cadangan, dengan `{x}`, `{y}`, `{z}` |
| `zmin`, `zmax` | Rentang zoom untuk `tile_url` |
| `scripts` | Alamat skrip peta tambahan, relatif terhadap `https://petadasar.atrbpn.go.id/` |
| `post_pages` | Isi form POST untuk membuka halaman peta. `{t}` diganti timestamp |
| `foto_keywords` | Kata kunci atribusi layer foto udara tambahan (huruf kecil) |
| `latest_version` | Versi plugin terbaru. Pengguna versi lebih lama mendapat pemberitahuan sekali |
| `message` | Pengumuman singkat untuk semua pengguna (kosongkan bila tidak ada). Tiap isi pesan hanya tampil sekali |

## Bila foto udara tiba-tiba kosong

1. Buka https://petadasar.atrbpn.go.id di browser, masuk ke peta, lalu tekan **F12 → tab Network**. Geser peta dan cari permintaan tile foto udara (berkas gambar dengan pola angka x/y/z).
2. Salin pola URL-nya, ganti angkanya dengan `{x}`, `{y}`, `{z}`. Contoh: `https://petadasar.atrbpn.go.id/?wms/{x}/{y}/{z}/2`.
3. Uji di QGIS lewat **Plugins > ATR BPN Basemap > Atur URL secara manual...**.
4. Bila berhasil, edit `config.json` di GitHub (buka berkasnya, klik ikon pensil), ganti `tile_url` dan `updated`, lalu **Commit changes**.
5. Dalam sehari (atau segera bila pengguna menekan **Cek & perbarui URL**), semua plugin v1.1.0 ke atas akan memakai URL baru.

Bila server juga mewajibkan Referer dari domain lain, perubahan itu belum bisa diatasi lewat `config.json`. Kodenya perlu diperbarui (`REFERER` di `detector.py`).

## Merilis versi baru

1. Salin folder versi terakhir menjadi `versi_<baru>`, kerjakan perubahan di sana.
2. Naikkan `version` dan tambah `changelog` di `atrbpn_basemap/metadata.txt`.
3. Jalankan `build_zip.py` dari Python Console QGIS (sesuaikan path):
   ```python
   exec(open(r"X:\GIS\Project Plugin\versi_<baru>\build_zip.py", encoding="utf-8").read(), {"__file__": r"X:\GIS\Project Plugin\versi_<baru>\build_zip.py"})
   ```
4. Unggah folder `atrbpn_basemap` ke repo, buat rilis dengan tag `v<baru>`, lampirkan ZIP dari `dist`.
5. Setelah rilis terbit, ubah `latest_version` di `config.json` agar pengguna lama mendapat pemberitahuan.

## Pengujian sebelum rilis

**Smoke test (wajib, di QGIS).** Setelah versi baru terpasang di QGIS dan ZIP-nya dibangun, jalankan di Python Console QGIS:

```python
p = r"X:\GIS\Project Plugin\versi_<baru>\tests\smoke_test.py"
ns = {}; exec(open(p, encoding="utf-8").read(), ns)
ns["run_smoke_test"](zip_path=r"X:\GIS\Project Plugin\versi_<baru>\dist\atrbpn_basemap-<baru>.zip")
```

Tujuh uji (metadata, config.json, deteksi URL, URL tersimpan, layer XYZ, ekspor GeoTIFF, isi ZIP) harus **SEMUA LULUS** sebelum rilis. Skrip ini tidak mengubah pengaturan atau proyek QGIS.

**CI GitHub Actions (otomatis).** Setiap push ke `main` menjalankan `.github/workflows/build.yml`: cek sintaks, `metadata.txt`, `config.json`, build ZIP, dan cek isi ZIP. Hasilnya terlihat di tab **Actions** repo (centang hijau atau silang merah). Bisa juga dijalankan lokal: `python tests/ci_check.py` dan `python tests/ci_check.py dist/<zip>`.

## Laporan dari pengguna

Repo memakai Issue template (`.github/ISSUE_TEMPLATE/`): pelapor wajib mengisi jenis masalah, versi plugin, versi QGIS, langkah, dan hasil; lokasi, log, dan screenshot dianjurkan. Issue kosong tanpa template dinonaktifkan.

## Menguji config.json tanpa mengubah GitHub

Di Python Console QGIS, arahkan plugin ke berkas lokal:

```python
from qgis.core import QgsSettings
QgsSettings().setValue("atrbpn_basemap/config_url", "file:///X:/GIS/Project Plugin/versi_1.1.0/config.json")
```

Kembalikan ke GitHub dengan:

```python
QgsSettings().remove("atrbpn_basemap/config_url")
```
