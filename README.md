# UAS Thermal Analysis

Vendor-neutral thermal inspection and geospatial analytics for aerial, handheld, and fixed thermal imagery.

UAS Thermal Analysis is evolving from a working radiometric inspection desktop application into a modular commercial platform. Sensor decoding, thermal analytics, geospatial transforms, inspection findings, reporting, desktop workflows, and platform services are separated so the product is not tied to one aircraft or camera vendor.

## Current capabilities

- Modular PyQt desktop application for project setup, source selection, bounded preview/classification, radiometric calibration, analysis, findings review, and report export
- Explicit separation between quantitative radiometric sources and display/GIS imagery so rendered thermal products are never treated as temperature matrices
- Bounded GeoTIFF preview path for very large orthomosaics; preview generation does not allocate the full raster
- Batch analysis workflow over normalized `ThermalFrame` objects
- Generic radiometric GeoTIFF adapter with explicit scale, offset, unit conversion, CRS, affine transform, radiometric classification, and full-frame safety limits
- Operational DJI DIRP adapter when the vendor runtime is installed locally; no machine-specific DLL path is required
- Thermal calibration parameters: emissivity, distance, humidity, reflected temperature
- Temperature statistics and configurable delta-based anomaly detection
- Automatic finding georeferencing from GeoTIFF CRS + affine transforms when geospatial dependencies are installed
- Project-backed inspection metadata instead of embedded customer/site values
- Vendor-neutral CSV, KML, and PDF report bundles
- Pluggable sensor adapter registry with explicit FLIR/Teledyne and Autel extension contracts
- Python 3.11/3.12 CI and GitHub Pages documentation

> FLIR/Teledyne and Autel remain adapter contracts in this release. They are not claimed as fully decoded radiometric formats until validated against vendor data and SDKs.

## Source lanes

```text
RADIOMETRIC DATA                    DISPLAY / GIS DATA
original camera R-JPEG              rendered thermal orthomosaic
calibrated thermal GeoTIFF          RGB/palette GeoTIFF
scalar temperature raster           KML / world-file positioned imagery
vendor-native radiometric file      basemap / context layer
          │                                   │
          ▼                                   ▼
ThermalFrame → quantitative         bounded preview / mapping
analysis + anomaly detection        no temperature claims
```

A filename containing words such as `thermal` or `radiometric` is not sufficient evidence that a raster stores temperature values. The generic adapter inspects actual raster structure and metadata before allowing quantitative analysis.

## Architecture

```text
src/uas_thermal/
├── application/        # desktop UI, projects, workflows
├── thermal/            # calibration, radiometry, anomaly detection, statistics
├── sensors/            # generic + vendor adapters and registry
├── geospatial/         # GeoTIFF, bounded display raster, CRS transforms, KML, world files
├── inspections/        # findings, severity, recommendations
├── reporting/          # PDF, CSV, KML, report bundles
└── platform/           # configuration, licensing, logging, packaging helpers
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for subsystem contracts and migration boundaries.

## Install for development

Python 3.11+ is recommended. On Windows, an isolated project environment is preferred over installing into a system-wide Conda base environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,desktop,geospatial,reporting,dji]"
pytest -p no:cacheprovider
```

Optional DJI support requires the vendor DIRP runtime. Do not commit vendor DLLs. Either place the runtime beside the packaged Windows application or point the adapter at an installed SDK directory:

```powershell
$env:UAS_THERMAL_DJI_SDK_DIR = "D:\path\to\dji\thermal-sdk\bin"
```

## Run

Capability status:

```powershell
python -m uas_thermal info
```

Launch the modular desktop:

```powershell
python -m uas_thermal desktop
```

Inspect radiometric suitability without loading a full GeoTIFF:

```powershell
python -m uas_thermal geotiff-probe "D:\path\source.tif"
```

Validate the bounded display/GIS path for a large raster:

```powershell
python -m uas_thermal display-probe "D:\path\orthomosaic.tif"
```

The original root application remains preserved as a compatibility reference while parity is verified. New product work should target `src/uas_thermal/`.

## Product direction

The platform is intentionally sensor-agnostic. A sensor adapter is responsible for decoding a quantitative source into a normalized `ThermalFrame`; every downstream thermal subsystem operates on that normalized frame. Display/GIS imagery follows a separate bounded raster path and can be used for context and future finding overlays without being misrepresented as temperature data.

## Commercial licensing boundary

The legacy symmetric HMAC licensing path is not considered production-ready for a paid downloadable product. The modular client intentionally keeps licensing behind `platform/licensing.py`. Subscription issuance, renewal, payment state, offline grace, revocation, and automated entitlement management will be designed as a separate production tranche after the application and packaging surfaces are complete.

## Security and data handling

- Real inspection/customer datasets are excluded from source control.
- Vendor SDK binaries are excluded from source control.
- License signing secrets must never be committed or embedded in the desktop client.
- Report/project metadata is supplied by the user or project file rather than hard-coded into application source.
