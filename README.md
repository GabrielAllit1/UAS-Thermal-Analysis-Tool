# UAS Thermal Analysis

Vendor-neutral thermal inspection and geospatial analytics for aerial, handheld, and fixed thermal imagery.

UAS Thermal Analysis is being evolved from a working radiometric inspection desktop application into a modular platform. The new architecture separates sensor decoding, thermal analytics, geospatial transforms, inspection findings, reporting, and application workflows so support is not tied to one aircraft or camera vendor.

## Current capabilities

- Radiometric image and GeoTIFF processing foundations
- Thermal calibration parameters: emissivity, distance, humidity, reflected temperature
- Temperature statistics and configurable anomaly detection
- GeoTIFF metadata, CRS transforms, KML, and world-file utilities
- Inspection findings, severity policy, and maintenance recommendations
- CSV, KML, and PDF reporting APIs
- Pluggable sensor adapter registry
- DJI DIRP adapter path with runtime SDK discovery
- Generic radiometric GeoTIFF adapter
- Explicit FLIR/Teledyne and Autel adapter extension points
- Desktop, project, and workflow layers

> FLIR/Teledyne and Autel are adapter contracts in this release, not claimed as fully decoded radiometric formats yet. Vendor-specific decoding is enabled only when a tested adapter exists.

## Architecture

```text
src/uas_thermal/
├── application/        # desktop UI, projects, workflows
├── thermal/            # calibration, radiometry, anomaly detection, statistics
├── sensors/            # generic + vendor adapters and registry
├── geospatial/         # GeoTIFF, CRS transforms, KML, world files
├── inspections/        # findings, severity, recommendations
├── reporting/          # PDF, CSV, KML
└── platform/           # configuration, licensing, logging, packaging helpers
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for subsystem contracts and migration boundaries.

## Install for development

Python 3.11+ is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,desktop,geospatial,reporting]"
pytest
```

Optional DJI support requires the vendor DIRP runtime. Do not commit vendor DLLs. Point the application at an installed SDK directory with:

```powershell
$env:UAS_THERMAL_DJI_SDK_DIR = "D:\path\to\dji\thermal-sdk\bin"
```

## Run

The original application is preserved during migration. The modular package exposes a capability/status CLI:

```powershell
python -m uas_thermal info
```

The desktop migration will progressively replace the legacy root modules while retaining compatibility until parity is verified.

## Product direction

The platform is intentionally sensor-agnostic. A sensor adapter is responsible for decoding a source file into a normalized `ThermalFrame`; every downstream subsystem operates on that normalized frame. This keeps anomaly logic, mapping, inspection records, and reporting independent of DJI, FLIR/Teledyne, Autel, or future sensors.

## Security and data handling

- Real inspection/customer datasets are excluded from source control.
- Vendor SDK binaries are excluded from source control.
- License signing secrets must never be committed.
- The legacy symmetric HMAC licensing path is retained only for compatibility and is scheduled for asymmetric verification migration.

## Status

This repository is in active modernization. The legacy baseline remains available while the new modular architecture is introduced behind tested interfaces.
