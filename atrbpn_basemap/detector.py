# -*- coding: utf-8 -*-
"""Deteksi otomatis URL tile foto udara dari situs Peta Dasar ATR/BPN.

Cara kerja:
1. Baca konfigurasi jarak jauh (config.json di repo GitHub) bila tersedia.
2. Ambil halaman situs ATR/BPN (termasuk halaman peta di iframe) dan cari rujukan skrip peta (?js/...).
3. Unduh skrip peta tersebut, lalu baca semua definisi L.tileLayer(...).
4. Pilih layer foto udara berdasarkan teks atribusinya (CSRT / Foto Airbone / Drone).
5. Uji satu tile contoh dengan header Referer untuk memastikan URL benar-benar hidup.
6. Bila deteksi otomatis gagal, pakai tile_url dari konfigurasi jarak jauh (setelah diuji).
"""
import json
import math
import re
import time
from urllib.parse import urljoin, quote

from qgis.core import QgsBlockingNetworkRequest, QgsSettings
from qgis.PyQt.QtCore import QUrl, QByteArray
from qgis.PyQt.QtNetwork import QNetworkRequest

BASE = "https://petadasar.atrbpn.go.id/"
REFERER = BASE
USER_AGENT = b"Mozilla/5.0 (QGIS; ATR BPN Basemap plugin)"
DEFAULT_URL = "https://petadasar.atrbpn.go.id/?wms/{x}/{y}/{z}/2"
DEFAULT_SCRIPTS = ["?js/map5/", "?js/2/map5/"]
# halaman yang dimuat lewat POST (sejak Nov 2026 peta ada di iframe "m=90")
DEFAULT_POST_PAGES = ["m=90&app=&t={t}"]
FOTO_KEYWORDS = ("foto airbone", "foto airborne", "csrt-foto", "drone")

REPO_URL = "https://github.com/fadliarya/atrbpn-basemap"
RELEASES_URL = REPO_URL + "/releases"
ISSUES_URL = REPO_URL + "/issues"
CONFIG_URL = "https://raw.githubusercontent.com/fadliarya/atrbpn-basemap/main/config.json"
CONFIG_KEY = "atrbpn_basemap/config_url"  # bisa diganti untuk pengujian

# Titik uji yang diketahui punya cakupan foto udara (lon, lat)
TEST_POINTS = [
    (112.6264, -7.3632),  # Driyorejo, Gresik
    (112.6914, -7.2724),  # Surabaya
]


def http(url, referer=REFERER, post=None):
    req = QNetworkRequest(QUrl(url))
    if referer:
        req.setRawHeader(b"Referer", referer.encode())
    req.setRawHeader(b"User-Agent", USER_AGENT)
    br = QgsBlockingNetworkRequest()
    if post is None:
        br.get(req, True)
    else:
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        br.post(req, QByteArray(post), True)
    rep = br.reply()
    status = rep.attribute(QNetworkRequest.HttpStatusCodeAttribute)
    ctype = bytes(rep.rawHeader(b"Content-Type")).decode("latin1").lower()
    return status, ctype, bytes(rep.content())


def _text(b):
    return b.decode("utf-8", "ignore")


# ---------- konfigurasi jarak jauh ----------
def fetch_config(log=None):
    """Baca config.json dari repo GitHub. Kembalikan dict (kosong bila gagal)."""
    log = log or (lambda *_: None)
    url = QgsSettings().value(CONFIG_KEY, "") or CONFIG_URL
    try:
        status, _, body = http(url, referer="")
        if body and (status == 200 or not url.startswith("http")):
            cfg = json.loads(_text(body))
            if isinstance(cfg, dict):
                log("Konfigurasi jarak jauh terbaca (diperbarui %s)" % cfg.get("updated", "?"))
                return cfg
        log("Konfigurasi jarak jauh tidak tersedia (HTTP %s)" % status)
    except Exception as e:
        log("Konfigurasi jarak jauh tidak terbaca: %s" % e)
    return {}


def version_tuple(v):
    """'1.10.2' -> (1, 10, 2); bagian non-angka diabaikan."""
    out = []
    for part in str(v).split("."):
        m = re.match(r"\d+", part.strip())
        out.append(int(m.group(0)) if m else 0)
    return tuple(out)


# ---------- parsing skrip peta ----------
def _find_vars(src):
    """Kumpulkan nilai variabel string sederhana: var x = '...';  x='...'"""
    out = {}
    for m in re.finditer(r"""(?:var\s+)?([A-Za-z_]\w*)\s*=\s*(['"])(.*?)\2\s*;""", src):
        out.setdefault(m.group(1), m.group(3))
    return out


def _eval_expr(expr, variables):
    """Evaluasi ekspresi concatenation JS sederhana: 'a' + tt + "b"."""
    parts = []
    for tok in re.split(r"\s*\+\s*", expr.strip().strip("()")):
        tok = tok.strip()
        if not tok:
            continue
        if tok[0] in "'\"" and tok[-1] == tok[0]:
            parts.append(tok[1:-1])
        elif tok in variables:
            parts.append(variables[tok])
        elif tok in ("tt", "ts", "time"):
            parts.append(str(int(time.time())))
        else:
            return None
    url = "".join(parts)
    return url or None


def parse_tile_layers(js, variables):
    layers = []
    pat = re.compile(r"L\.tileLayer\s*\(\s*([^,\n]+?)\s*,\s*\{(.*?)\}\s*\)", re.S)
    # setiap kemunculan L.tileLayer( diurai sendiri-sendiri supaya definisi yang
    # dikomentari tidak ikut "menelan" definisi sesudahnya
    for start in [s.start() for s in re.finditer(r"L\.tileLayer\s*\(", js)]:
        line_start = js.rfind("\n", 0, start) + 1
        if "//" in js[line_start:start]:
            continue
        m = pat.match(js, start)
        if not m:
            continue
        url = _eval_expr(m.group(1), variables)
        if not url or "{x}" not in url or "{y}" not in url or "{z}" not in url:
            continue
        opts = m.group(2)
        att = re.search(r"attribution\s*:\s*(['\"])(.*?)\1", opts, re.S)
        zmin = re.search(r"minZoom\s*:\s*(\d+)", opts)
        zmax = re.search(r"maxZoom\s*:\s*(\d+)", opts)
        layers.append({
            "url": urljoin(BASE, url),
            "attribution": re.sub(r"<[^>]+>|&nbsp;", " ", att.group(2)).strip() if att else "",
            "zmin": int(zmin.group(1)) if zmin else 0,
            "zmax": int(zmax.group(1)) if zmax else 21,
        })
    return layers


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def test_url(url, extra_points=(), zoom=18):
    """True bila minimal satu tile uji mengembalikan gambar."""
    for lon, lat in list(extra_points) + TEST_POINTS:
        x, y = _tile_xy(lon, lat, zoom)
        u = url.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(zoom))
        try:
            status, ctype, body = http(u)
        except Exception:
            continue
        if status == 200 and "image" in ctype and len(body) > 500:
            return True
    return False


# ---------- deteksi ----------
def _auto_detect(extra_points, remote, log):
    """Deteksi dari situs ATR/BPN. Kembalikan (kandidat_terpilih_atau_None, semua_layer)."""
    status, _, body = http(BASE)
    if status != 200:
        raise RuntimeError("Halaman utama ATR/BPN tidak bisa diakses (HTTP %s)" % status)
    pages = [_text(body)]
    post_pages = list(remote.get("post_pages") or []) + DEFAULT_POST_PAGES
    for data in dict.fromkeys(post_pages):
        try:
            st, _, b = http(BASE, post=data.replace("{t}", str(int(time.time()))).encode())
            if st == 200 and b:
                pages.append(_text(b))
        except Exception:
            pass
    variables, scripts = {}, set()
    for page in pages:
        for k, val in _find_vars(page).items():
            variables.setdefault(k, val)
        scripts.update(re.findall(r"""['"](\.?/?\?js/[\w/]+?/?)['"]""", page))
    scripts.update(remote.get("scripts") or [])
    scripts.update(DEFAULT_SCRIPTS)

    layers = []
    for url in sorted({urljoin(BASE, s) for s in scripts}):
        if url.endswith("/"):
            url += str(int(time.time()))
        log("Membaca skrip peta: %s" % url)
        st, _, js_b = http(url)
        if st != 200 or not js_b:
            continue
        js = _text(js_b)
        v = dict(variables)
        v.update(_find_vars(js))
        layers.extend(parse_tile_layers(js, v))
    if not layers:
        raise RuntimeError("Tidak menemukan definisi tile layer di skrip peta ATR/BPN")

    keywords = tuple(k.lower() for k in (remote.get("foto_keywords") or [])) + FOTO_KEYWORDS
    foto = [l for l in layers if any(k in l["attribution"].lower() for k in keywords)]
    candidates = foto or [l for l in layers if "petadasar.atrbpn.go.id" in l["url"] and "?wms/" in l["url"]]
    if not candidates:
        raise RuntimeError("Layer foto udara tidak ditemukan pada skrip peta ATR/BPN")
    for c in candidates:
        if test_url(c["url"], extra_points):
            return dict(c, verified=True), layers
    return dict(candidates[0], verified=False), layers


def detect(extra_points=(), log=None):
    """Kembalikan dict {url, zmin, zmax, attribution, verified, source, all_layers, remote}.

    source = "auto" (dari situs ATR/BPN) atau "config" (dari config.json di GitHub).
    Raise RuntimeError bila tidak ada URL yang bisa dipakai.
    """
    log = log or (lambda *_: None)
    remote = fetch_config(log)
    chosen, layers, error = None, [], None
    try:
        chosen, layers = _auto_detect(extra_points, remote, log)
        chosen["source"] = "auto"
    except Exception as e:
        error = str(e)
        log("Deteksi otomatis gagal: %s" % e)

    if (chosen is None or not chosen["verified"]) and remote.get("tile_url"):
        url = remote["tile_url"]
        log("Mencoba URL dari konfigurasi jarak jauh: %s" % url)
        if test_url(url, extra_points):
            chosen = {"url": url, "attribution": "", "verified": True, "source": "config",
                      "zmin": int(remote.get("zmin", 16)), "zmax": int(remote.get("zmax", 21))}

    if chosen is None:
        raise RuntimeError(error or "URL foto udara tidak ditemukan")
    chosen["zmin"] = max(chosen["zmin"], 16)  # tile < z16 kosong di server ATR
    chosen["zmax"] = min(chosen["zmax"], 21)
    chosen["all_layers"] = layers
    chosen["remote"] = remote
    return chosen


def build_uri(url, zmin, zmax):
    return ("type=xyz&url=" + quote(url, safe=":/?") +
            "&zmin=%d&zmax=%d" % (zmin, zmax) +
            "&http-header:referer=" + quote(REFERER, safe=""))
