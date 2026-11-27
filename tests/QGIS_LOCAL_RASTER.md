# Local GeoTIFF acceptance v0.2.0

Status: not yet executed in real QGIS. Use disposable INDO-GO-TEST profile, blank project, disconnect network. Use only trusted synthetic or authorized non-client raster. Do not use remote URLs, network shares or sensitive records.

1. Install the inner v0.2.0 ZIP from the matching CI run.
2. Open Plugins > INDO-GO GeoSpatial > Buka GeoTIFF lokal.
3. Cancel picker: no layer added. Select a valid local georeferenced TIFF; cancel source dialog: no layer added. Confirm valid source and usage: raster should appear in Layers and source in Layer Properties > Information/Metadata.
4. Try invalid TIFF, missing CRS, blank attribution and decline usage confirmation: no layer added. Verify plugin activation/unload twice, one toolbar icon, both menu items, About shows 0.2.0.
5. Inspect logs and monitor network separately; no network-originating behavior claimed until observed. QGIS/GDAL sidecars and mounted filesystems are not a security sandbox; keep network disconnected.
6. Check project saves/reopens with layer and attribution. No production merge/release until runtime reviewed.

Expected limitations: only local TIFF, no remote basemaps or export, no automated cadastral assessment. A TIFF header is not complete file validation; GDAL checks raster readability and CRS. Source attribution is user-entered, not verified.

## QA fixtures (2026-11-27)

Generate trusted synthetic fixtures with `python tests/generate_raster_fixtures.py <empty-test-directory>` in a development environment with numpy and rasterio. No dependencies added to the QGIS plugin. Synthetic RGB grid: 128 x 128, 2 m pixel, EPSG:32749, no real imagery or parcel evidence. Expected results:

- indo_go_sintetis.tif: load with source "Data sintetis INDO-GO - QA", verify CRS and source metadata. Use Zoom to Layer if necessary.
- indo_go_invalid.tif: reject before provider creation.
- indo_go_tanpa_crs.tif: reject if provider reports invalid CRS. If QGIS assigns a default or asks for CRS, cancel and record actual behavior; do not mark pass without checking source georeferencing.
- Cancellation, empty attribution and declined permission: no new layer.

Simulated UI tests in raster_workflow_check.py cover nine cases, but do not execute GDAL or real QGIS. Runtime v0.2.0 remains unverified. Do not merge or release solely on CI results.
