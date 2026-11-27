# Parcel Analyzer runtime acceptance — v0.3.0

Status: NOT EXECUTED in real QGIS. Use disposable INDO-GO-TEST profile offline. Synthetic coordinates only, no customer data.

1. Install exact v0.3.0 CI artifact. Confirm three menu items, one toolbar icon.
2. Choose Plugins > INDO-GO GeoSpatial > Analisis bidang (koordinat UTM).
3. Enter EPSG:32749 and the four points below in order:

```
400000 9100000
400010 9100000
400010 9100016
400000 9100016
```

Expected: 4 vertices, grid area 160.00 m², 0.016000 ha, perimeter 52.00 m. Bounds E/N 400000, 9100000 to 400010, 9100016.
4. Reverse order, repeat closing vertex, verify same measurements. Try crossing edges, repeated internal vertex, decimal degrees with EPSG:4326, blank input; reject. Cancel either dialog; no result.
5. Confirm that results explicitly say grid, declared CRS not verified, indicative and not official measurements. No layer created or edited, no automatic data storage.
6. Re-run v0.2.0 raster acceptance separately; monitor network and logs. Record actual QGIS version, OS, commit and results. No merge/release solely on unit tests.

Limits: no coordinate transform, grid-to-ground correction, holes/multipolygons, automatic cadastral recognition or legal validation. UTM code is only validated syntactically; the actual CRS/zone must be established by the user from source data.
