# UAS Thermal Analysis

**Local-first AI-assisted thermal intelligence from mission data to client-ready deliverable.**

UAS Thermal Analysis is a vendor-neutral post-processing platform for drone, handheld, and fixed thermal imagery. The operator executes the mission; **Thermal Intelligence Autopilot** handles the post-flight workload: source classification, radiometric validation, quantitative thermal stitching when an approved backend is available, contextual analysis, optional local-AI interpretation, annotation, measurement, and delivery packaging.

The product is designed around a strict split between **automation** and **authority**. Local AI can interpret, summarize, prioritize review, and help explain established findings. It cannot silently change temperature matrices, finding identity, geometry, severity, confidence, or geolocation. Quantitative claims remain traceable to validated radiometric source data.

> **Operator in, deliverable out.** Autopilot is the orchestration layer; validated radiometry remains the temperature authority.

## Thermal Intelligence Autopilot

The Windows desktop opens into an AI-first mission-control workspace rather than a traditional file-processing utility.

```text
MISSION DATA
    ↓
INGEST / CLASSIFY
    ↓
RADIOMETRIC QUALITY GATE
    ↓
AI-ORCHESTRATED STITCH DECISION
    ↓
QUANTITATIVE THERMAL ORTHOMOSAIC   ← when a validated backend/source path exists
    ↓
CONTEXTUAL THERMAL ANALYSIS
    ↓
CANONICAL FINDINGS
    ↓
LOCAL VISION / TEXT AI REVIEW       ← optional; supplemental only
    ↓
ANNOTATIONS + THERMAL TUNING + MEASUREMENTS
    ↓
PDF + RADIOMETRIC GEOTIFF + CSV/JSON + GIS
    ↓
PORTABLE CLIENT / ENGINEERING VIEWER
    ↓
HASHED PROVENANCE MANIFEST
```

Autopilot scans the workstation for locally available Ollama models and quantitative stitching backends. It can automatically select an installed local model, preferring a vision-capable model when available. If local AI is unavailable, the deterministic pipeline continues instead of blocking the deliverable.

No model, SDK, runtime, or public dataset is downloaded automatically by the application.

## Current capabilities

### AI-first operations

- AI-first **Thermal Intelligence Autopilot** workspace with source, radiometry, stitching, local-AI, and deliverable readiness
- One-click autonomous post-processing with live stage telemetry: INGEST → RADIOMETRY → STITCH → ANALYZE → AI REVIEW → ANNOTATE → PACKAGE → COMPLETE
- Local Ollama discovery with model capability inspection and vision-model preference
- Optional local structured/vision enrichment for already-established findings
- Hard non-mutation boundary around quantitative temperature, geometry, severity, confidence, coordinates, classification, and finding identity
- Deterministic fallback when local AI is not installed or reachable
- Local-first design: source data stays on the workstation unless the operator explicitly configures another processing runtime

### Radiometric processing and thermal tuning

- Generic radiometric GeoTIFF adapter with explicit scale, offset, unit conversion, CRS, affine transform, radiometric classification, and bounded-memory tiled analysis
- Operational DJI DIRP adapter when a compatible authorized vendor runtime is installed locally
- Quantitative native GeoTIFF mosaicking for already-georeferenced scalar thermal rasters
- Optional OpenDroneMap thermal photogrammetry backend; output must pass the application's radiometric gate before quantitative use
- Thermal palettes including White Hot, Black Hot, Iron/Iron Bow, Arctic, Rainbow, and Rainbow HC
- Span/Level thermal tuning, explicit display ranges, and isotherms without changing the underlying temperature matrix
- Batch-tuned review thermograms with recorded visual-style provenance
- Temperature-under-cursor and ROI statistics
- Spot (4×4 average), Spot Delta, rectangle, circle, ellipse, line, and polygon measurement primitives
- Ambient-temperature provenance in addition to emissivity, distance, humidity, and reflected temperature

### Autonomous analysis

- Radiometric quality gate with accepted / accepted-with-warnings / rejected states
- Contextual multi-scale anomaly detection using local references, local ΔT, robust scene evidence, morphology, scale support, and explicit false-positive suppression
- Stable canonical findings with geometry, hotspot, local reference, severity, confidence, evidence, provenance, lifecycle state, and geolocation when authoritative
- Cross-frame geospatial deduplication while retaining supporting-observation provenance
- Versioned inspection profiles for Generic Thermal, Electrical, Photovoltaic, Roof / Building Envelope, Mechanical, Pipeline, Construction, Agriculture, Public Safety, and Natural Resources workflows
- Previous-inspection structured finding comparison
- Explicit thermal-visible pairing with opacity, swipe, and side-by-side review

### Client and engineering deliverables

- Automated annotated thermograms, finding crops, and evidence plates
- Professional PDF report with bounded **AI-assisted context** clearly labeled as supplemental
- Batch presentation thermograms using the selected palette/Span/Level
- Quantitative thermal orthomosaic when generated by an accepted backend
- CSV and JSON finding registers
- GeoJSON and KML when coordinates are authoritative
- Portable local HTML findings viewer for client/engineering review
- Processing report containing calibration, AI/model, automation, and stitching provenance
- SHA-256 manifest covering generated deliverable files

### Product workspace

- Projects, Overview, Data, Explore, Analyze, Processing, Findings, Compare, Reports, Exports, Analytics, Profiles, Settings, Measurements, Process, and Autopilot surfaces
- Persistent Processing Center history with completed/canceled/failed state, event telemetry, rejected-source counts, findings, and package provenance
- Virtualized project/source/history/finding tables
- Project portfolio search plus explicit-coordinate location view that never invents geocoding
- Bounded GeoTIFF display preview and quantitative overlapping-tile processing for large rasters
- Windows visual QA at 1280×720, 1440×900, and 1920×1080

## Quantitative authority

```text
RADIOMETRIC DATA                    DISPLAY / GIS DATA
original camera R-JPEG              rendered thermal image
calibrated thermal GeoTIFF          RGB/palette GeoTIFF
scalar temperature raster           KML / world-file positioned imagery
vendor-native radiometric file      basemap / context layer
          │                                   │
          ▼                                   ▼
ThermalFrame → quality gate          DisplayRaster → bounded preview
          │                                   │
          ▼                                   │
quantitative analysis                         │
          │                                   │
          └──────── canonical findings ───────┘
                         │
                         ▼
           AI context + annotations + exports
```

A filename containing `thermal` or `radiometric` is not evidence that a raster stores temperature values. The source adapter must establish a valid radiometric path before temperature analysis is allowed.

The core invariants are:

```text
display raster != radiometric source
high temperature != defect
candidate != finding
severity != confidence
confidence != certification
AI interpretation != quantitative authority
successful stitch != valid temperature orthomosaic
GPS coordinate != physical-defect identity
automated report != thermographer certification
unit test != field validation
```

## Architecture

```text
src/uas_thermal/
├── ai/                 # local provider contracts, Ollama runtime, bounded finding enrichment
├── application/        # Autopilot, desktop workspaces, projects, processing, orchestration
├── orthomosaic/        # quantitative stitching backend contracts, native GeoTIFF, optional ODM
├── thermal/            # calibration, presentation, measurements, quality, detection, statistics
├── sensors/            # generic/tiled + vendor decoders into ThermalFrame
├── geospatial/         # display raster, CRS transforms, overlays, KML, world files
├── inspections/        # canonical findings, profiles, lifecycle, comparison, deduplication
├── reporting/          # thermograms, annotations, PDF, JSON/CSV/GIS, portable deliverable
├── validation/         # external fixture contracts
└── platform/           # configuration, licensing boundary, logging, packaging helpers
```

Vendor-specific decoding stops at `sensors/`. Stitching stops at `orthomosaic/`. Downstream thermal analysis and reporting remain vendor-neutral.

See [ARCHITECTURE.md](ARCHITECTURE.md) for subsystem contracts and authority boundaries. See [docs/VALIDATION_DATASETS.md](docs/VALIDATION_DATASETS.md) for external fixture sources and claim boundaries.

## Install for development

Python 3.11+ is supported.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,desktop,geospatial,reporting,dji]"
pytest -p no:cacheprovider
```

Optional DJI support requires an authorized vendor DIRP runtime. Do not commit vendor DLLs.

```powershell
$env:UAS_THERMAL_DJI_SDK_DIR = "D:\path\to\dji\thermal-sdk\bin"
```

Optional local AI uses an already-installed Ollama runtime. The application does not install Ollama or pull models automatically.

## Run

Launch the AI-first desktop:

```powershell
python -m uas_thermal desktop
```

Inspect application capabilities, local models, and stitching backends:

```powershell
python -m uas_thermal info
python -m uas_thermal ai-models
python -m uas_thermal orthomosaic-status
```

Run the complete universal post-processing pipeline from the CLI:

```powershell
python -m uas_thermal process `
  "D:\mission\thermal_001.tif" `
  "D:\mission\thermal_002.tif" `
  --output-dir "D:\deliverables\Project-01" `
  --project "Project 01" `
  --profile roof-envelope `
  --stitch auto `
  --orthomosaic-backend auto `
  --ai auto `
  --palette ironbow
```

`--ai auto` selects from locally installed models. AI enrichment is never required for quantitative completion.

List supported profiles and external validation sources:

```powershell
python -m uas_thermal profiles
python -m uas_thermal validation-sources
```

Run deterministic detector validation:

```powershell
python -m uas_thermal validate-synthetic
```

Inspect GeoTIFF radiometric suitability without loading the full raster:

```powershell
python -m uas_thermal geotiff-probe "D:\path\source.tif"
```

Validate a DJI original radiometric JPEG against the locally configured DIRP runtime:

```powershell
python -m uas_thermal dji-probe "D:\path\original-rjpeg.jpg"
```

External real-data integration tests are opt-in. Normal CI does not redistribute DJI fixtures, customer data, or public research datasets.

## Deliverable structure

A universal thermal intelligence package is designed to be directly useful to clients, engineers, operators, and downstream business partners:

```text
inspection_output/
├── report/
│   ├── inspection_report.pdf
│   └── processing_report.json
├── findings/
│   └── <finding-id>/
│       ├── annotated_thermal.png
│       ├── thermal_crop.png
│       ├── finding_plate.png
│       └── finding.json
├── maps/
│   ├── thermal_orthomosaic.tif      # when quantitative stitch exists
│   ├── annotated_thermal_overview.png
│   ├── thermograms/
│   │   ├── *_thermal.png
│   │   └── thermogram_index.json
│   └── survey_overview.geojson      # when coordinates are authoritative
├── data/
│   ├── findings.csv
│   ├── findings.json
│   ├── findings.geojson
│   └── findings.kml
├── viewer/
│   └── index.html
└── inspection_manifest.json
```

A report claim, map feature, table row, annotation, JSON record, and AI-assisted explanation all reference the same canonical finding rather than creating independent truth.

## Validation status and claim boundary

CI proves software behavior against repository tests and synthetic fixtures. It does **not** prove universal camera compatibility, field detection accuracy, thermographer-equivalent diagnostic accuracy, or standards certification.

External fixtures can prove a named decoder, radiometric raster path, stitching workflow, or comparison operation against those fixtures. Raw-camera compatibility is claimed only after testing against a genuine supported source/runtime combination.

The platform may report automated anomaly evidence and prioritized inspection intelligence. It does not claim:

- thermographer certification;
- universal defect diagnosis from temperature alone;
- survey-grade positional accuracy beyond source authority;
- field precision/recall without labeled representative validation;
- standards compliance unless a specific standard is implemented and verified.

## Commercial licensing boundary

The legacy symmetric HMAC licensing path is not production-ready for a paid downloadable product. Subscription issuance, renewal, payment state, offline grace, revocation, and automated entitlement management remain isolated behind `platform/licensing.py` for a later production tranche after application, analysis, validation, and Windows distribution surfaces converge.

## Security and data handling

- Real inspection/customer datasets remain outside source control.
- Vendor SDK binaries and vendor test images remain outside source control.
- Large public research fixtures retain their own licenses and attribution requirements.
- License signing secrets must never be committed or embedded in the desktop client.
- Local AI is optional; model/runtime selection is explicit and observable.
- Removing a dataset from a project must not delete original survey files.
