# Modernization roadmap

## v0.2 — modular foundation

- Vendor-neutral package boundaries
- Generic radiometric GeoTIFF adapter
- Adapter registry and explicit vendor support states
- Delta-based anomaly model
- Project and report APIs
- CI and Pages documentation

## v0.3 — desktop parity

- Move the PyQt desktop into `application/desktop`
- Remove machine-specific GDAL and DLL paths
- Normalize DJI R-JPEG output into `ThermalFrame`
- Replace embedded site/customer report values with project metadata
- Add deterministic report fixtures and UI smoke tests

## v0.4 — vendor expansion

- Validate FLIR/Teledyne radiometric format support
- Validate Autel radiometric format support
- Add adapter conformance test kit and sanitized sample fixtures

## v0.5 — production packaging

- Windows installer and signed release artifacts
- Asymmetric license verification
- Release provenance and SBOM
- Plugin discovery for third-party sensor adapters
