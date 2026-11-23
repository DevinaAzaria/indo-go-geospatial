# ATR BPN Basemap (Plugin QGIS)

**English:** QGIS plugin that adds ATR/BPN (Indonesia) Peta Dasar aerial imagery as an XYZ basemap. The tile URL is detected and updated automatically from the ATR/BPN website. Imagery for a selected extent can be exported to GeoTIFF. Coverage is limited to Indonesia. Not affiliated with ATR/BPN. All commands are in **Plugins > ATR BPN Basemap**.

---

Plugin QGIS untuk menambahkan foto udara Peta Dasar ATR/BPN (petadasar.atrbpn.go.id) sebagai basemap XYZ. URL tile diperbarui secara otomatis dari situs ATR/BPN, sehingga pengguna tidak perlu mencari dan menyalin URL secara manual setiap kali alamatnya berubah.

## Fitur

- Menambahkan foto udara ATR/BPN sebagai layer XYZ dengan satu klik.
- Mendeteksi URL tile terbaru dari skrip peta di situs ATR/BPN, lalu menguji tile contoh sebelum dipakai.
- Memperbarui layer di proyek yang sedang terbuka dan koneksi XYZ di panel Browser.
- Pengecekan otomatis di latar belakang, paling sering sekali sehari (dapat dimatikan).
- Ekspor foto udara pada extent tertentu menjadi GeoTIFF.

## Instalasi

1. Buka QGIS, pilih menu **Plugins > Manage and Install Plugins**.
2. Pada tab **Settings**, centang **Show also experimental plugins** (selama plugin masih berstatus experimental).
3. Pada tab **All**, cari `ATR BPN Basemap`, lalu klik **Install Plugin**.

Instalasi manual dari berkas ZIP: **Plugins > Manage and Install Plugins > Install from ZIP**.

## Cara Pakai

Semua perintah ada di menu **Plugins > ATR BPN Basemap**:

| Menu | Fungsi |
|---|---|
| Tambahkan Foto Udara ATR/BPN | Menambahkan layer foto udara ke proyek (juga tersedia sebagai tombol di toolbar Plugins) |
| Ekspor foto udara ke GeoTIFF... | Mengunduh tile pada extent dan zoom level tertentu lalu menyimpannya sebagai GeoTIFF |
| Cek & perbarui URL dari situs ATR/BPN | Mencari URL tile terbaru secara manual |
| Atur URL secara manual... | Mengisi URL tile sendiri bila deteksi otomatis gagal |
| Cek otomatis saat QGIS dibuka | Menyalakan atau mematikan pengecekan otomatis |
| Tentang plugin | Informasi plugin |

## Batasan

- Cakupan data hanya wilayah Indonesia yang tersedia di Peta Dasar ATR/BPN; di luar area tersebut tile akan kosong.
- Membutuhkan koneksi internet. Ketersediaan data sepenuhnya bergantung pada layanan ATR/BPN.
- Gunakan fitur ekspor secara wajar (extent kecil, jumlah unduhan paralel rendah) agar tidak membebani server penyedia.

## Penafian

Plugin ini dikembangkan secara independen dan **tidak berafiliasi** dengan Kementerian Agraria dan Tata Ruang/Badan Pertanahan Nasional. Hak atas data foto udara tetap milik ATR/BPN. Pengguna bertanggung jawab mematuhi ketentuan penggunaan data dari penyedia.

## Laporan Masalah

Laporkan bug atau saran melalui halaman [Issues](https://github.com/fadliarya/atrbpn-basemap/issues).

## Lisensi

GNU General Public License v2.0 atau versi yang lebih baru. Lihat berkas [LICENSE](LICENSE).

Pengembang: Fadli Arya Wisnu Baradi
