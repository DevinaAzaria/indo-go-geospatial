# INDO-GO GeoSpatial

**Land Intelligence & Spatial Due Diligence — development preview 0.3.0**

Independent QGIS plugin derivative of [ATR BPN Basemap 1.1.3](https://github.com/fadliarya/atrbpn-basemap), originally developed by Fadli Arya Wisnu Baradi. Modified on 2026-11-25. Licensed under GPL-2.0-or-later; original copyright, license and data attribution remain intact.

## Status / Status pengembangan

- Baseline: upstream 1.1.3, commit `e36cbcb0f42ed15143608e2b14f3f4d4328a8c9a`.
- This security preview is intentionally offline: no online imagery requests, token refresh, or export via plugin UI. No production release or runtime security certification yet.
- Package directory and settings identifiers are now `indo_go_geospatial`. An independent SVG icon is included; test in an isolated QGIS profile before any use.
- Remote configuration and upstream release notices are disabled pending review. New issue reports belong to [INDO-GO Issues](https://github.com/DevinaAzaria/indo-go-geospatial/issues), not the original author.
- Belum dipublikasikan sebagai plugin INDO-GO di repositori resmi QGIS. Jangan memasang pada lingkungan produksi sebelum audit dan pengujian selesai.

## Existing features / Fitur dasar

Inherited features (disabled in this preview): XYZ imagery layer, URL detection and GeoTIFF export. Active QGIS actions: About, Buka GeoTIFF lokal, and Analisis bidang (koordinat UTM). Select a trusted local TIFF, enter source attribution, confirm usage rights, and load it as a GDAL raster with a valid CRS. Source attribution is user-provided, not verified. Test with the network disconnected; GDAL and QGIS are external dependencies, and filesystem or sidecar behavior is not comprehensively sandboxed. QGIS 3.22–3.99 is the upstream compatibility declaration, not a new compatibility test.

## Data rights and legal limitations / Hak data dan batasan hukum

Imagery and base maps are supplied by Kementerian ATR/BPN through [Peta Dasar ATR/BPN](https://petadasar.atrbpn.go.id/). The GPL applies to the code, not the imagery. Use only authorized access and permitted exports; respect provider terms and limits. This independent project has no affiliation with ATR/BPN. Imagery and spatial measurements are indicative, not proof of title, legal boundaries, or official cadastral survey results. Never commit client records, certificates, tokens or private parcel data to this public repository.

## Roadmap (planned, not implemented)

1. Security and data-rights review; isolate plugin identity and configuration.
2. Extend parcel analysis to validated local vector polygons and reviewed CRS transformations.
3. Spatial due diligence checklist and local project data management.
4. Indicative report generation with sources, timestamps and limitations.

## Development / Pengembangan

Build and validate only in an isolated environment after reviewing source code. CI checks syntax, metadata, ZIP structure, offline security policy a simulated QGIS lifecycle using mock Qt classes, and local file validation. See tests/QGIS_RUNTIME.md for the actual QGIS protocol. It does not validate QGIS runtime or provider authorization. No INDO-GO release is currently available.

See [upstream documentation](https://github.com/fadliarya/atrbpn-basemap/tree/e36cbcb0f42ed15143608e2b14f3f4d4328a8c9a) for inherited feature details. The original README is retained in this repository as [UPSTREAM_README.md](UPSTREAM_README.md).

## License / Lisensi

[GPL-2.0-or-later](LICENSE). Original author: Fadli Arya Wisnu Baradi. INDO-GO GeoSpatial is a separate derivative and must not be represented as the original project or an official ATR/BPN product.

## v0.2.0 testing

See [local raster acceptance protocol](tests/QGIS_LOCAL_RASTER.md) and [v0.1.2 runtime evidence](tests/RUNTIME_0.1.2.md). No real v0.2.0 runtime test yet.

## v0.3.0 Parcel Analyzer preview

Manual ordered Easting/Northing input, declared WGS 84 UTM CRS, simple polygons only, grid area and perimeter plus bounds. No holes, multipolygons, coordinate transforms, scale correction or official cadastral measurements. No storage or network calls by this module. See [parcel acceptance protocol](tests/QGIS_PARCEL.md). Real QGIS testing remains pending for v0.2.0 and v0.3.0.
