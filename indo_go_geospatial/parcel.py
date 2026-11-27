# -*- coding: utf-8 -*-
# Modified by INDO-GO GeoSpatial, 2026-11-27: vector and area comparison preview; GPL-2.0-or-later.
# Modified by INDO-GO GeoSpatial, 2026-11-27: parcel analysis preview; GPL-2.0-or-later.
"""Planar grid measurements for a simple UTM polygon; no CRS transformation."""
from decimal import Decimal, localcontext
import re

MAX_VERTICES = 500
NUMBER = re.compile(r"[+-]?[0-9]{1,8}(?:\.[0-9]{1,6})?")
CRS = re.compile(r"EPSG:32[67](?:0[1-9]|[1-5][0-9]|60)")


def parse_utm_crs(value):
    if not isinstance(value, str) or not CRS.fullmatch(value.strip().upper()):
        raise ValueError("Gunakan kode UTM WGS 84, misalnya EPSG:32749.")
    return value.strip().upper()


def parse_vertices(text):
    if not isinstance(text, str) or len(text) > 30000:
        raise ValueError("Input koordinat tidak valid atau terlalu panjang.")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not 3 <= len(lines) <= MAX_VERTICES + 1:
        raise ValueError("Masukkan 3–500 titik; titik penutup opsional.")
    points = []
    for line in lines:
        fields = line.split()
        if len(fields) != 2 or not all(NUMBER.fullmatch(x) for x in fields):
            raise ValueError("Setiap baris harus berisi Easting Northing, titik desimal, dipisah spasi.")
        x, y = map(Decimal, fields)
        if not (Decimal(100000) <= x <= Decimal(900000) and Decimal(0) <= y <= Decimal(10000000)):
            raise ValueError("Koordinat di luar rentang UTM yang diterima.")
        points.append((x, y))
    if points[0] == points[-1]:
        points.pop()
    if not 3 <= len(points) <= MAX_VERTICES or len(set(points)) != len(points):
        raise ValueError("Titik harus unik, kecuali titik penutup.")
    return points


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on(a, b, p):
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _intersects(a, b, c, d):
    x, y, z, w = _cross(a,b,c), _cross(a,b,d), _cross(c,d,a), _cross(c,d,b)
    if (x == 0 and _on(a,b,c) or y == 0 and _on(a,b,d)
            or z == 0 and _on(c,d,a) or w == 0 and _on(c,d,b)):
        return True
    return ((x > 0 and y < 0) or (x < 0 and y > 0)) and ((z > 0 and w < 0) or (z < 0 and w > 0))


def _validate_simple(points):
    n = len(points)
    for i in range(n):
        a,b,c = points[i-1],points[i],points[(i+1)%n]
        if _cross(a,b,c) == 0:
            dot = (a[0]-b[0])*(c[0]-b[0]) + (a[1]-b[1])*(c[1]-b[1])
            if dot > 0:
                raise ValueError("Sisi berimpit atau berbalik arah.")
    for i in range(n):
        for j in range(i+1,n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            if _intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):
                raise ValueError("Poligon berpotongan atau menyentuh dirinya sendiri.")


def analyze_parcel(text, crs):
    """Inputs are declared UTM coordinates in metres; outputs are grid measures."""
    crs = parse_utm_crs(crs)
    points = parse_vertices(text)
    with localcontext() as ctx:
        ctx.prec = 42
        _validate_simple(points)
        x0,y0 = points[0]
        p = [(x-x0,y-y0) for x,y in points]
        area2 = Decimal(0)
        perimeter = Decimal(0)
        for (x,y),(u,v) in zip(p,p[1:]+p[:1]):
            area2 += x*v-u*y
            perimeter += ((u-x)**2+(v-y)**2).sqrt()
        if area2 == 0:
            raise ValueError("Luas nol; poligon tidak valid.")
        area = abs(area2)/2
        return {"crs":crs, "vertices":len(points), "area_m2":area,
                "area_ha":area/10000, "perimeter_m":perimeter,
                "bounds":(min(x for x,y in points),min(y for x,y in points),
                          max(x for x,y in points),max(y for x,y in points))}


def format_result(result):
    x1,y1,x2,y2 = result["bounds"]
    return (f"CRS (deklarasi pengguna): {result['crs']}\n"
            f"Jumlah titik: {result['vertices']}\n"
            f"Luas grid: {result['area_m2']:.2f} m² ({result['area_ha']:.6f} ha)\n"
            f"Keliling grid: {result['perimeter_m']:.2f} m\n"
            f"Batas koordinat E/N: {x1}, {y1} — {x2}, {y2}\n\n"
            "Indikatif; bukan hasil ukur resmi atau bukti batas/hak. "
            "CRS dan koordinat belum diverifikasi. Tidak ada koreksi skala grid ke tanah.")

def compare_document_area(result, text):
    """Compare grid area with user-entered document area, without legal thresholds."""
    if not isinstance(text, str) or not NUMBER.fullmatch(text.strip()):
        raise ValueError("Luas dokumen harus berupa angka positif dalam m², tanpa pemisah ribuan.")
    document = Decimal(text.strip())
    if document <= 0:
        raise ValueError("Luas dokumen harus lebih besar dari nol.")
    with localcontext() as ctx:
        ctx.prec = 42
        difference = result["area_m2"] - document
        return {"document_m2": document, "difference_m2": difference,
                "absolute_m2": abs(difference),
                "difference_percent": difference / document * 100}


def format_comparison(comparison):
    return (f"\n\nLuas dokumen (input pengguna): {comparison['document_m2']:.2f} m²\n"
            f"Selisih grid − dokumen: {comparison['difference_m2']:+.2f} m²\n"
            f"Selisih absolut: {comparison['absolute_m2']:.2f} m²\n"
            f"Selisih relatif terhadap dokumen: {comparison['difference_percent']:+.2f}%\n"
            "Selisih aritmetis saja; bukan penetapan toleransi, kesesuaian hukum, atau indikasi sengketa.")
