# Release readiness gates — INDO-GO GeoSpatial

No release or merge solely because CI succeeds. Current development line is offline, experimental.

| Gate | Required evidence | Current state |
|---|---|---|
| Build reproducibility and regression | CI for exact release candidate, pinned dependencies/actions, clean build, package checksum | CI infrastructure exists; pinning and reproducibility pending |
| Measurement correctness | Reference geometries, invalid geometry tests, independent numeric checks, documented CRS/precision | Unit tests exist; independent reference and real QGIS pending |
| QGIS runtime | Exact QGIS/OS matrix, install/uninstall/restart, raster/parcel/selected polygon workflows, project save/reopen | v0.1.2 user evidence 9/10; later runtime pending |
| Security | Review active code and inherited code, network observation, dependencies, local file handling, privacy and no secrets | Partial controls; full audit pending |
| Data rights | Document authorized sources and permitted storage/export, no inferred rights from GPL | ATR/BPN network and exports disabled; authorization unresolved |
| Documentation | Accurate feature limits, attribution, license, maintainer contact, user guide, recovery steps | Partial |
| Release decision | All in-scope gates signed off against exact commit; unresolved features excluded and clearly disclosed | BLOCKED |

First stable release may intentionally be offline-only. Online ATR/BPN is a separate decision, not a condition for shipping a useful authorized offline tool. No legal boundary/ownership verification or official survey claims. Do not commit client records. Keep draft PR until review.
