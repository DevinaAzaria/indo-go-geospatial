# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-25: derivative branding; GPL-2.0-or-later.
"""Deteksi otomatis URL tile foto udara dari situs Peta Dasar ATR/BPN.

Cara kerja:
1. Baca konfigurasi jarak jauh (config.json di repo GitHub) bila tersedia.
2. Ambil halaman situs ATR/BPN (termasuk halaman peta di iframe) dan cari rujukan skrip peta (?js/...).
3. Unduh skrip peta tersebut, lalu baca semua definisi L.tileLayer(...).
4. Pilih layer foto udara berdasarkan teks atribusinya (CSRT / Foto Airbone / Drone).
5. Uji satu tile contoh dengan header Referer untuk memastikan URL benar-benar hidup.
6. Bila deteksi otomatis gagal, pakai tile_url dari konfigurasi jarak jauh (setelah diuji).

Sejak 25 Nov 2026 URL tile foto udara memuat token sesi (variabel JS `bw` di halaman
peta m=90), misalnya ?wms/{x}/{y}/{z}/2/<token>. Token hanya berlaku bersama cookie
sesi (PHPSESSID) dan berganti setiap beberapa menit. Karena itu plugin menyimpan
*template* URL dengan placeholder {token} dan memperbarui tokennya secara berkala
(lihat fetch_token() dan refresh()).
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
SESSION_SLOT = "{token}"  # placeholder token sesi di template URL
DEFAULT_TOKEN_VARS = ["bw"]  # nama variabel JS yang berisi token sesi
DETECT_ATTEMPTS = 3  # token baru kadang belum aktif sesaat setelah sesi diganti server
RETRY_DELAY = 3  # detik

# Original network configuration remains unchanged pending security and data-access review.
PROJECT_URL = "https://github.com/DevinaAzaria/indo-go-geospatial"
UPSTREAM_BASELINE = "1.1.3"
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


def http_safe(url, referer=REFERER, post=None):
    """Seperti http(), tetapi mengembalikan (None, "", b"") bila permintaan gagal."""
    try:
        return http(url, referer=referer, post=post)
    except Exception:
        return None, "", b""


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
        status, ctype, body = http_safe(u)
        if status == 200 and "image" in ctype and len(body) > 500:
            return True
    return False


# ---------- token sesi ----------
def _post_pages(remote):
    return list(dict.fromkeys(list((remote or {}).get("post_pages") or []) + DEFAULT_POST_PAGES))


def _token_vars(remote):
    return list(dict.fromkeys(list((remote or {}).get("token_vars") or []) + DEFAULT_TOKEN_VARS))


def find_token(page, remote=None):
    """Ambil nilai token sesi dari teks halaman, atau None."""
    for name in _token_vars(remote):
        m = re.search(r"""\b%s\s*=\s*['"]([0-9A-Za-z]{16,})['"]""" % re.escape(name), page)
        if m:
            return m.group(1)
    return None


def fetch_token(remote=None, log=None):
    """Minta token sesi baru dari halaman peta (POST m=90). Kembalikan string atau None."""
    log = log or (lambda *_: None)
    for data in _post_pages(remote):
        try:
            st, _, b = http(BASE, post=data.replace("{t}", str(int(time.time()))).encode())
        except Exception as e:
            log("Gagal meminta token sesi: %s" % e)
            continue
        if st == 200 and b:
            tok = find_token(_text(b), remote)
            if tok:
                return tok
    return None


def make_template(url, token):
    """Ganti nilai token di URL dengan placeholder {token}."""
    if token and token in url:
        return url.replace(token, SESSION_SLOT)
    return url


def resolve(template, token):
    """Isi placeholder {token}. Template tanpa {token} dikembalikan apa adanya."""
    if SESSION_SLOT not in template:
        return template
    return template.replace(SESSION_SLOT, token or "") if token else None


def needs_token(template):
    return SESSION_SLOT in (template or "")


def refresh(template, extra_points=(), remote=None, log=None, attempts=DETECT_ATTEMPTS):
    """URL siap pakai (token terbaru, sudah diuji) dari template, atau None bila gagal.

    Template tanpa {token} cukup diuji saja.
    """
    log = log or (lambda *_: None)
    for i in range(attempts):
        if i:
            time.sleep(RETRY_DELAY)
        if needs_token(template):
            url = resolve(template, fetch_token(remote, log))
            if not url:
                log("Token sesi tidak ditemukan di halaman peta ATR/BPN")
                continue
        else:
            url = template
        if test_url(url, extra_points):
            return url
    return None


# ---------- deteksi ----------
def _auto_detect(extra_points, remote, log):
    """Deteksi dari situs ATR/BPN. Kembalikan (kandidat_terpilih_atau_None, semua_layer)."""
    status, _, body = http(BASE)
    if status != 200:
        raise RuntimeError("Halaman utama ATR/BPN tidak bisa diakses (HTTP %s)" % status)
    pages = [_text(body)]
    for data in _post_pages(remote):
        st, _, b = http_safe(BASE, post=data.replace("{t}", str(int(time.time()))).encode())
        if st == 200 and b:
            pages.append(_text(b))
    variables, scripts, token = {}, set(), None
    for page in pages:
        token = token or find_token(page, remote)
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
    foto = [ly for ly in layers if any(k in ly["attribution"].lower() for k in keywords)]
    candidates = foto or [ly for ly in layers if "petadasar.atrbpn.go.id" in ly["url"] and "?wms/" in ly["url"]]
    if not candidates:
        raise RuntimeError("Layer foto udara tidak ditemukan pada skrip peta ATR/BPN")
    for c in candidates:
        c["template"] = make_template(c["url"], token)
    for c in candidates:
        if test_url(c["url"], extra_points):
            return dict(c, verified=True), layers
    return dict(candidates[0], verified=False), layers


def detect(extra_points=(), log=None, attempts=DETECT_ATTEMPTS):
    """Kembalikan dict {url, template, zmin, zmax, attribution, verified, source, all_layers, remote}.

    url = siap pakai (token sesi sudah terisi); template = url dengan placeholder {token}.
    source = "auto" (dari situs ATR/BPN) atau "config" (dari config.json di GitHub).
    Raise RuntimeError bila tidak ada URL yang bisa dipakai.
    """
    log = log or (lambda *_: None)
    remote = fetch_config(log)
    chosen, layers, error = None, [], None
    for i in range(max(1, attempts)):
        if i:
            log("Tile uji belum merespons, mencoba lagi dengan token sesi baru (%d/%d)..."
                % (i + 1, attempts))
            time.sleep(RETRY_DELAY)
        try:
            chosen, layers = _auto_detect(extra_points, remote, log)
            chosen["source"] = "auto"
            error = None
        except Exception as e:
            error = str(e)
            log("Deteksi otomatis gagal: %s" % e)
        if chosen is not None and chosen["verified"]:
            break

    if (chosen is None or not chosen["verified"]) and remote.get("tile_url"):
        tpl = remote["tile_url"]
        log("Mencoba URL dari konfigurasi jarak jauh: %s" % tpl)
        url = refresh(tpl, extra_points, remote, log, attempts=2)
        if url:
            chosen = {"url": url, "template": tpl, "attribution": "", "verified": True,
                      "source": "config",
                      "zmin": int(remote.get("zmin", 16)), "zmax": int(remote.get("zmax", 21))}

    if chosen is None:
        raise RuntimeError(error or "URL foto udara tidak ditemukan")
    chosen["zmin"] = max(chosen["zmin"], 16)  # tile < z16 kosong di server ATR
    chosen["zmax"] = min(chosen["zmax"], 21)
    chosen.setdefault("template", chosen["url"])
    chosen["all_layers"] = layers
    chosen["remote"] = remote
    return chosen


def build_uri(url, zmin, zmax):
    return ("type=xyz&url=" + quote(url, safe=":/?") +
            "&zmin=%d&zmax=%d" % (zmin, zmax) +
            "&http-header:referer=" + quote(REFERER, safe=""))
