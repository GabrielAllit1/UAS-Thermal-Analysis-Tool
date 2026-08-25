# Modernization roadmap

## v0.2 — modular foundation ✅

- Vendor-neutral package boundaries
- Adapter registry and explicit vendor support states
- Delta-based anomaly model
- Project and report APIs
- CI and Pages documentation

## v0.3 — product core migration ✅

- Modular PyQt desktop entry point under `application/desktop`
- Batch `AnalysisWorkflow` over normalized `ThermalFrame` artifacts
- Remove machine-specific DJI DLL paths
- Normalize proven DJI DIRP R-JPEG decoding into `ThermalFrame`
- Operational generic radiometric GeoTIFF conversion with explicit units
- Georeference findings from GeoTIFF CRS + affine transform
- Replace embedded site/customer report values with project metadata
- Vendor-neutral PDF / CSV / KML report bundles

## v0.4 — vendor expansion

- Validate FLIR/Teledyne radiometric format support against sanitized vendor fixtures
- Validate Autel radiometric format support against sanitized vendor fixtures
- Add adapter conformance test kit and sensor capability matrix
- Add calibrated cross-vendor reference datasets

## v0.5 — Windows production distribution

- Professional Windows installer and upgrade path
- Signed release artifacts
- Release provenance and SBOM
- Packaged optional vendor runtimes without committing redistributables that prohibit redistribution
- Desktop smoke tests on Windows runners

## v0.6 — automated commercial entitlement

- Subscription-backed monthly and annual plans
- Payment-provider webhooks as entitlement authority
- Automatic activation, renewal, cancellation, failed-payment handling, grace periods, and revocation
- Asymmetric signed entitlements: private signing key remains server-side; desktop ships only a public verification key
- Secure device/account binding with bounded offline operation
- In-app billing/renewal portal and automatic entitlement refresh
- No human-issued keys and no operator intervention for normal customer lifecycle events
