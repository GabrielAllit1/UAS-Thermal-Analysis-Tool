# UAS Thermal Analysis

Vendor-neutral autonomous thermal inspection and geospatial intelligence for aerial, handheld, and fixed thermal imagery.

UAS Thermal Analysis is a project-centric thermal operations platform. Quantitative sensor decoding, radiometric quality control, contextual anomaly detection, finding characterization, geospatial evidence, inspection management, annotation, reporting, and machine-readable exports are separated so the product is not tied to one aircraft or camera vendor.

## Current capabilities

- Project-centric PyQt Thermal Intelligence Workspace with Projects, Overview, Data, Explore, Analyze, Findings, Compare, Reports, Exports, Analytics, Profiles, and Settings workspaces
- Canonical autonomous inspection orchestration from source validation through canonical findings and output-package generation
- Explicit separation between quantitative radiometric sources and display/GIS imagery so rendered thermal products are never treated as temperature matrices
- Bounded GeoTIFF preview path for very large orthomosaics; preview generation does not allocate the full raster
- Radiometric quality gate with accepted / accepted-with-warnings / rejected states
- Contextual multi-scale anomaly detection using local references, local ΔT, robust scene evidence, morphology, scale support, and explicit false-positive suppression
- Stable structured findings with geometry, hotspot, local reference, severity, confidence, evidence, provenance, lifecycle state, and geolocation when authoritative
- Versioned Generic Thermal, Electrical, Photovoltaic, Roof / Building Envelope, Mechanical, and Pipeline profiles over one domain-neutral detector
- Cross-frame geospatial deduplication that retains original observation provenance
- Thermal finding comparison for compatible repeated inspections
- Automated annotated thermograms, finding crops, finding plates, professional PDF reports, CSV/JSON, and GeoJSON/KML when coordinates exist
- Deterministic inspection package with SHA-256 manifest
- Generic radiometric GeoTIFF adapter with explicit scale, offset, unit conversion, CRS, affine transform, radiometric classification, and full-frame safety limits
- Operational DJI DIRP adapter when a compatible vendor runtime is installed locally; no machine-specific DLL path is required
- FLIR/Teledyne and Autel extension contracts without unsupported radiometric claims
- Python 3.11/3.12 CI

> Automated thermal analysis is inspection intelligence, not thermographer certification. Field accuracy depends on source radiometry, calibration assumptions, capture conditions, and validation against representative labeled data.

## Quantitative authority

```text
RADIOMETRIC DATA                    DISPLAY / GIS DATA
original camera R-JPEG              rendered thermal orthomosaic
calibrated thermal GeoTIFF          RGB/palette GeoTIFF
scalar temperature raster           KML / world-file positioned imagery
vendor-native radiometric file      basemap / context layer
          │                                   │
          ▼                                   ▼
ThermalFrame → quality gate          DisplayRaster → bounded preview
          │                          map / geographic presentation
          ▼                                   │
contextual thermal analysis                   │
          │                                   │
          └──────── canonical findings ───────┘
                         │
                         ▼
          annotations + report + exports
```

A filename containing `thermal` or `radiometric` is not evidence that a raster stores temperature values. The adapter inspects raster structure and metadata before allowing quantitative analysis.

## Autonomous inspection path

```text
PROJECT
  ↓
DATASET DISCOVERY
  ↓
RADIOMETRIC QUALITY GATE
  ↓
NORMALIZED ThermalFrame
  ↓
MULTI-SCALE CONTEXTUAL DETECTION
  ↓
LOCAL REFERENCE + ΔT
  ↓
CHARACTERIZATION + MORPHOLOGY
  ↓
FALSE-POSITIVE SUPPRESSION
  ↓
CLASSIFICATION
  ↓
SEVERITY + CONFIDENCE
  ↓
GEOLOCATION WHEN AUTHORITATIVE
  ↓
CROSS-FRAME DEDUPLICATION
  ↓
CANONICAL FINDINGS
  ↓
ANNOTATIONS + FINDING PLATES
  ↓
PDF + CSV + JSON + GeoJSON/KML
  ↓
CHECKSUMMED INSPECTION PACKAGE
```

Severity and confidence are intentionally independent. Numeric confidence components are internal evidence scores, not calibrated probabilities.

## Architecture

```text
src/uas_thermal/
├── application/        # workspace UI, projects, workflows, orchestration, pairing
├── thermal/            # calibration, quality gate, detection, statistics, validation
├── sensors/            # generic + vendor adapters and registry
├── geospatial/         # display raster, CRS transforms, overlays, KML, world files
├── inspections/        # canonical findings, profiles, lifecycle, comparison, deduplication
├── reporting/          # annotations, plates, PDF, CSV, JSON, GeoJSON, KML, packages
└── platform/           # configuration, licensing boundary, logging, packaging helpers
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for subsystem contracts and authority boundaries.

## Install for development

Python 3.11+ is supported. On Windows, use an isolated project environment instead of a system-wide Conda base environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,desktop,geospatial,reporting,dji]"
pytest -p no:cacheprovider
```

Optional DJI support requires the vendor DIRP runtime. Do not commit vendor DLLs. Place an authorized runtime beside the packaged Windows application or point the adapter at an installed SDK directory:

```powershell
$env:UAS_THERMAL_DJI_SDK_DIR = "D:\path\to\dji\thermal-sdk\bin"
```

## Run

Capability status:

```powershell
python -m uas_thermal info
```

Launch the Thermal Intelligence Workspace:

```powershell
python -m uas_thermal desktop
```

List inspection profiles:

```powershell
python -m uas_thermal profiles
```

Run deterministic detector validation:

```powershell
python -m uas_thermal validate-synthetic
```

Run a complete autonomous inspection from the CLI:

```powershell
python -m uas_thermal inspect "D:\path\thermal_001.jpg" "D:\path\thermal_002.jpg" `
  --project "Substation Inspection" `
  --profile electrical `
  --output-dir "D:\Inspections\output"
```

Inspect GeoTIFF radiometric suitability without loading the full raster:

```powershell
python -m uas_thermal geotiff-probe "D:\path\source.tif"
```

Validate the bounded display/GIS path for a large raster:

```powershell
python -m uas_thermal display-probe "D:\path\orthomosaic.tif"
```

The original root application remains preserved as a compatibility reference while measured parity is completed. New product work targets `src/uas_thermal/`.

## Inspection output

A generated inspection package uses the canonical finding model across all presentation layers:

```text
inspection_output/
├── report/inspection_report.pdf
├── findings/A-001/
│   ├── annotated_thermal.png
│   ├── thermal_crop.png
│   ├── finding_plate.png
│   └── finding.json
├── annotated/
├── maps/
├── data/
│   ├── findings.csv
│   ├── findings.json
│   ├── findings.geojson   # only when coordinates are authoritative
│   └── findings.kml       # only when coordinates are authoritative
└── inspection_manifest.json
```

A report claim, table row, map feature, annotation, and exported JSON record all project the same canonical finding rather than independently reconstructing truth.

## Claim boundary

The platform may report automated anomaly evidence and prioritized inspection intelligence. It does not claim:

- thermographer certification;
- universal defect diagnosis from temperature alone;
- survey-grade positional accuracy beyond source authority;
- field precision/recall without labeled representative validation;
- standards compliance unless a specific standard is implemented and verified.

## Commercial licensing boundary

The legacy symmetric HMAC licensing path is not production-ready for a paid downloadable product. Subscription issuance, renewal, payment state, offline grace, revocation, and automated entitlement management remain isolated behind `platform/licensing.py` for a later production tranche after application, analysis, and Windows distribution surfaces converge.

## Security and data handling

- Real inspection/customer datasets are excluded from source control.
- Vendor SDK binaries are excluded from source control.
- License signing secrets must never be committed or embedded in the desktop client.
- Report/project metadata is supplied by the user or project file rather than hard-coded into application source.
- Removing a dataset from a project must not delete original survey files.
