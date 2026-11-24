# -*- coding: utf-8 -*-
"""Deteksi otomatis URL tile foto udara dari situs Peta Dasar ATR/BPN.

Cara kerja:
1. Ambil halaman utama petadasar.atrbpn.go.id dan cari rujukan skrip peta (?js/...).
2. Unduh skrip peta tersebut, lalu baca semua definisi L.tileLayer(...).
3. Pilih layer foto udara berdasarkan teks atribusinya (CSRT / Foto Airbone / Drone).
4. Uji satu tile contoh dengan header Referer untuk memastikan URL benar-benar hidup.
"""
import math
import re
import time
from urllib.parse import urljoin, quote

from qgis.core import QgsBlockingNetworkRequest
from qgis.PyQt.QtCore import QUrl, QByteArray
from qgis.PyQt.QtNetwork import QNetworkRequest

BASE = "https://petadasar.atrbpn.go.id/"
REFERER = BASE
USER_AGENT = b"Mozilla/5.0 (QGIS; ATR BPN Basemap plugin)"
DEFAULT_URL = "https://petadasar.atrbpn.go.id/?wms/{x}/{y}/{z}/2"
DEFAULT_SCRIPTS = ["?js/map5/", "?js/2/map5/"]
FOTO_KEYWORDS = ("foto airbone", "foto airborne", "csrt-foto", "drone")

# Titik uji yang diketahui punya cakupan foto udara (lon, lat)
TEST_POINTS = [
    (112.6264, -7.3632),  # Driyorejo, Gresik
    (112.6914, -7.2724),  # Surabaya
]


def http(url, referer=REFERER, post=None):
    req = QNetworkRequest(QUrl(url))
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


def detect(extra_points=(), log=None):
    """Kembalikan dict {url, zmin, zmax, attribution, all_layers, verified} atau raise RuntimeError."""
    log = log or (lambda *_: None)
    status, _, body = http(BASE)
    if status != 200:
        raise RuntimeError("Halaman utama ATR/BPN tidak bisa diakses (HTTP %s)" % status)
    pages = [_text(body)]
    # sejak Nov 2026 peta dimuat di iframe lewat POST m=90; skrip peta dirujuk dari sana
    try:
        st2, _, body2 = http(BASE, post=("m=90&app=&t=%d" % int(time.time())).encode())
        if st2 == 200 and body2:
            pages.append(_text(body2))
    except Exception:
        pass
    variables, scripts = {}, set()
    for page in pages:
        for k, val in _find_vars(page).items():
            variables.setdefault(k, val)
        scripts.update(re.findall(r"""['"](\.?/?\?js/[\w/]+?/?)['"]""", page))
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

    foto = [l for l in layers if any(k in l["attribution"].lower() for k in FOTO_KEYWORDS)]
    candidates = foto or [l for l in layers if "petadasar.atrbpn.go.id" in l["url"] and "?wms/" in l["url"]]
    if not candidates:
        raise RuntimeError("Layer foto udara tidak ditemukan pada skrip peta ATR/BPN")

    chosen = None
    for c in candidates:
        if test_url(c["url"], extra_points):
            chosen = dict(c, verified=True)
            break
    if chosen is None:
        chosen = dict(candidates[0], verified=False)
    chosen["zmin"] = max(chosen["zmin"], 16)  # tile < z16 kosong di server ATR
    chosen["zmax"] = min(chosen["zmax"], 21)
    chosen["all_layers"] = layers
    return chosen


def build_uri(url, zmin, zmax):
    return ("type=xyz&url=" + quote(url, safe=":/?") +
            "&zmin=%d&zmax=%d" % (zmin, zmax) +
            "&http-header:referer=" + quote(REFERER, safe=""))
