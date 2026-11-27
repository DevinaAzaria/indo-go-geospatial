# -*- coding: utf-8 -*-
# INDO-GO GeoSpatial, 2026-11-27; GPL-2.0-or-later.
"""Generate synthetic QA fixtures. Development-only: requires rasterio and numpy."""
import argparse
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    y, x = np.indices((128, 128))
    grid = (x // 32 + y // 32) % 2
    rgb = np.stack([np.where(grid, 90, 190), np.where(grid, 150, 215),
                    np.where(grid, 115, 150)]).astype("uint8")
    rgb[:, 60:68, :] = 235
    rgb[:, :, 60:68] = 235
    files = (("indo_go_sintetis.tif", "EPSG:32749"),
             ("indo_go_tanpa_crs.tif", None))
    for name, crs in files:
        with rasterio.open(output / name, "w", driver="GTiff", width=128,
                           height=128, count=3, dtype="uint8", crs=crs,
                           transform=from_origin(400000, 9100000, 2, 2),
                           compress="deflate", photometric="RGB") as ds:
            ds.write(rgb)
            ds.update_tags(DESCRIPTION="Synthetic test grid; not a survey or actual aerial image")
    (output / "indo_go_invalid.tif").write_bytes(b"Not a TIFF. Synthetic negative test.")
    for name, crs in files:
        with rasterio.open(output / name) as ds:
            assert ds.driver == "GTiff" and ds.width == ds.height == 128
            assert ds.count == 3 and ds.read().shape == (3, 128, 128)
            assert (ds.crs.to_string() if ds.crs else None) == crs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    generate(parser.parse_args().output)
