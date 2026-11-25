# INDO-GO GeoSpatial

**Land Intelligence & Spatial Due Diligence — development preview 0.1.0**

Independent QGIS plugin derivative of [ATR BPN Basemap 1.1.3](https://github.com/fadliarya/atrbpn-basemap), originally developed by Fadli Arya Wisnu Baradi. Modified on 2026-11-25. Licensed under GPL-2.0-or-later; original copyright, license and data attribution remain intact.

## Status / Status pengembangan

- Baseline: upstream 1.1.3, commit `e36cbcb0f42ed15143608e2b14f3f4d4328a8c9a`.
- This preview changes identity and documentation only, not imagery access mechanisms. No production release or runtime security certification yet.
- Package directory and settings identifiers remain compatible with the original for now. **Do not install alongside the original plugin**; isolated QGIS profile testing is required. The original icon is retained temporarily.
- Remote configuration and upstream release notices still use the original project pending security review. New issue reports belong to [INDO-GO Issues](https://github.com/DevinaAzaria/indo-go-geospatial/issues), not the original author.
- Belum dipublikasikan sebagai plugin INDO-GO di repositori resmi QGIS. Jangan memasang pada lingkungan produksi sebelum audit dan pengujian selesai.

## Existing features / Fitur dasar

Existing baseline features: XYZ imagery layer, URL detection and GeoTIFF export, subject to the data provider's rules. QGIS 3.22–3.99 is the upstream compatibility declaration, not a new compatibility test.

## Data rights and legal limitations / Hak data dan batasan hukum

Imagery and base maps are supplied by Kementerian ATR/BPN through [Peta Dasar ATR/BPN](https://petadasar.atrbpn.go.id/). The GPL applies to the code, not the imagery. Use only authorized access and permitted exports; respect provider terms and limits. This independent project has no affiliation with ATR/BPN. Imagery and spatial measurements are indicative, not proof of title, legal boundaries, or official cadastral survey results. Never commit client records, certificates, tokens or private parcel data to this public repository.

## Roadmap (planned, not implemented)

1. Security and data-rights review; isolate plugin identity and configuration.
2. Parcel area and coordinate tools using appropriate CRS.
3. Spatial due diligence checklist and local project data management.
4. Indicative report generation with sources, timestamps and limitations.

## Development / Pengembangan

Build and validate only in an isolated environment after reviewing source code. Existing upstream CI checks metadata, syntax and ZIP structure; these are not runtime or security tests. No INDO-GO release is currently available.

See [upstream documentation](https://github.com/fadliarya/atrbpn-basemap/tree/e36cbcb0f42ed15143608e2b14f3f4d4328a8c9a) for inherited feature details. The original README is retained in this repository as [UPSTREAM_README.md](https://github.com/DevinaAzaria/indo-go-geospatial/blob/branding/indo-go-v0.1/UPSTREAM_README.md).

## License / Lisensi

[GPL-2.0-or-later](LICENSE). Original author: Fadli Arya Wisnu Baradi. INDO-GO GeoSpatial is a separate derivative and must not be represented as the original project or an official ATR/BPN product.
