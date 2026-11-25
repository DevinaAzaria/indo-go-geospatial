# QGIS Runtime Acceptance — 0.1.2

Status: NOT EXECUTED in a real QGIS instance. Mock CI is not a substitute.

1. Use QGIS with a new disposable user profile and no client files. Disconnect external network access for the test.
2. Download the CI artifact for the exact 0.1.2 commit. Extract the outer artifact ZIP only; install the inner indo_go_geospatial-0.1.2.zip via Plugins > Manage and Install Plugins > Install from ZIP.
3. Confirm the plugin name/version, independent icon, and About dialog. It must state that network access is disabled and credit the original developer.
4. Disable and re-enable twice. Confirm no duplicate toolbar/menu item or startup exception.
5. For optional API smoke testing, disable the plugin first. In QGIS Python Console, load the reviewed tests/smoke_test.py from this exact commit and call run_smoke_test(). It creates and unloads a temporary instance.
6. In the disposable profile, verify the original plugin package is not overwritten. Do not activate its network functionality. Check the new package directory is distinct.
7. Check QGIS logs for errors and use a network monitor if available to confirm no plugin-originated outbound traffic. Do not claim this check passed without evidence.

Record QGIS version, OS, commit SHA, each pass/fail and any errors. No production data, no ATR/BPN access, no release until reviewed. Network functionality and parcel analysis remain unimplemented in this preview.
