# Selected polygon and comparison acceptance — 0.3.1

Status: NOT EXECUTED in real QGIS. Use disposable profile INDO-GO-TEST, network disconnected, blank project and synthetic coordinates. No customer data.

1. Install exact CI build 0.3.1. Verify four menu actions, one toolbar icon and About.
2. In QGIS create a temporary scratch polygon layer (memory provider), EPSG:32749. Draw or create a synthetic rectangle with exact coordinates from tests/QGIS_PARCEL.md (10 × 16 m). Select exactly one feature.
3. Invoke Analisis poligon terpilih (memory UTM). Expect area 160 m², perimeter 52 m, four vertices; enter document area 150 m². Expect signed difference +10 m², absolute 10 m² and +6.67%. No claim of legal tolerance. Try 160, 170, blank, Cancel, zero and invalid text.
4. Verify rejection for no/multiple selections, non-UTM CRS, invalid geometry, holes, multipart and non-memory providers. No feature edits, layer mutation or saved measurements by analyzer. Retest manual parcel and local raster features.
5. Verify activation, unloading, reload, project reopen, QGIS logs, and no observed plugin-originated network requests with an independent monitor. Record actual results, platform, exact QGIS version and commit.

Only memory vector layers supported here; copying to scratch requires trusted authorized source and is not automatic. CRS declaration and coordinate provenance are not verified by this tool. No scale corrections or legal determination.
