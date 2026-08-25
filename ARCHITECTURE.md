# Architecture

## Design objective

UAS Thermal Analysis is a project-centric thermal intelligence platform. It preserves a strict quantitative authority boundary, routes every quantitative inspection through one canonical orchestration path, and projects one canonical finding model into the UI, maps, annotations, reports, and exports.

```text
PROJECT / DATASETS
        ↓
SOURCE CLASSIFICATION
        ↓
┌────────────────────────────────┬────────────────────────────────┐
│ QUANTITATIVE RADIOMETRIC LANE  │ DISPLAY / GIS LANE             │
│                                │                                │
│ ThermalFrame                   │ DisplayRaster                  │
│ Celsius matrix                 │ bounded RGB preview            │
│ sensor/calibration provenance  │ CRS / affine metadata          │
│ optional display RGB           │ no temperature claims         │
└───────────────┬────────────────┴───────────────┬────────────────┘
                │                                │
                ▼                                ▼
      Radiometric quality gate            map/context rendering
                │                                │
                ▼                                │
      contextual thermal analysis                │
                │                                │
                └──────────────┬─────────────────┘
                               ▼
                       Canonical Finding
                               │
              ┌────────────────┼─────────────────┐
              ▼                ▼                 ▼
            UI/map       annotation/plate   report/exports
```

A filename, palette, or thermal-looking image is never enough to enter the quantitative lane. The source must decode to actual temperature values or documented radiometric counts.

## Canonical autonomous inspection path

`application.orchestrator.AutonomousInspectionOrchestrator` is the production authority for inspection execution:

```text
analyze_inspection(project, sources, profile)
    ↓
discover / validate source
    ↓
extract normalized ThermalFrame
    ↓
radiometric quality gate
    ↓
contextual multi-scale candidate detection
    ↓
local reference + ΔT characterization
    ↓
morphology + false-positive suppression
    ↓
classification + severity + confidence
    ↓
geolocation when authoritative
    ↓
cross-frame deduplication
    ↓
canonical findings
    ↓
annotation + finding plates
    ↓
inspection summary
    ↓
PDF / CSV / JSON / GeoJSON / KML
    ↓
checksummed inspection package
```

GUI, CLI, batch, and future API paths should reuse this authority rather than reimplementing analysis logic.

## Subsystems

### application
Owns project/dataset state, the Thermal Intelligence Workspace, source/media pairing, processing state, shared selection, and orchestration. It does not decode vendor radiometry or implement thermal algorithms.

Key authorities:

- `projects.Project` / `DatasetRecord`: persisted project and dataset context.
- `orchestrator.AutonomousInspectionOrchestrator`: canonical inspection execution.
- `workspace.SelectionState`: shared map/table/inspector selection.
- `desktop.DesktopSession`: thin desktop application session; delegates inspection analysis to the orchestrator.
- `workspace_ui`: Projects, Overview, Data, Explore, Analyze, Findings, Compare, Reports, Exports, Analytics, Profiles, and Settings surfaces.

### thermal
Owns quantitative calibration, source-quality assessment, statistics, contextual anomaly detection, suppression, and deterministic validation.

- `quality.evaluate_radiometric_quality`: PASS / PASS_WITH_WARNINGS / REJECTED gate.
- `anomaly_detection.analyze_temperature`: contextual detector and characterization authority.
- `validation`: synthetic test cases and precision/recall/IoU/ΔT harness.

The principal detector is no longer a global-median threshold. It combines local annular references, local ΔT, multi-scale support, robust scene evidence, connected-region morphology, and explicit suppression. A scene-wide median remains only a documented fallback when a local reference cannot be established.

### sensors
Defines `ThermalSensorAdapter` and `ThermalFrame`. Vendor integrations terminate here. Downstream modules must not import vendor SDKs.

A quantitative adapter implements:

- `name`: stable adapter identifier;
- `can_read(path)`: cheap source compatibility check;
- `read(path, calibration)`: decode to a normalized `ThermalFrame`.

A `ThermalFrame` contains a Celsius temperature matrix, optional display RGB, source path, sensor/vendor metadata, and optional CRS/affine transform.

### geospatial
Owns CRS transforms, pixel/map conversion, bounded raster presentation, display overlays, KML support, and world-file transforms.

- `DisplayRaster` is intentionally not a `ThermalFrame`.
- `transforms.crs_warning` prevents internally suspicious/local CRS metadata from silently becoming authoritative WGS84.
- `overlays.finding_to_display_point` projects already-geolocated canonical findings onto a display raster when both authorities are valid.

The source radiometric frame remains the temperature authority; an orthomosaic is a geographic presentation canvas.

### inspections
Owns canonical thermal findings and their operational interpretation.

- `models.Finding`: one structured record shared by every downstream presentation layer.
- `profiles.InspectionProfile`: versioned domain interpretation over one quantitative detector.
- `deduplication`: probable cross-frame duplicate clustering with observation provenance.
- `comparison`: compatible repeated-inspection finding change states.
- `lifecycle`: human operational states and audit trail, separate from algorithm evidence.
- `severity`: thermal consequence classification.

Severity and confidence are deliberately independent. Numeric confidence components are internal evidence scores, not empirically calibrated probabilities.

### reporting
Projects canonical findings into professional deliverables without creating report-only truth.

- `annotations`: annotated thermograms, crops, reusable finding plates.
- `pdf_report`: executive summary, inspection information, data quality, finding summary/details, methodology, and limitations.
- `csv_report`, `json_report`, `geojson_report`, `kml_report`: machine-readable projections.
- `package`: deterministic inspection directory and SHA-256 manifest.

Every report statement must remain traceable to a canonical finding and its source radiometric evidence.

### platform
Owns configuration, logging, packaging helpers, and the commercial licensing boundary. Vendor binaries and secrets stay outside source control. Subscription entitlement remains a later production tranche.

## Finding authority

A canonical `Finding` can carry, when evidence exists:

- stable finding / inspection / project / source IDs;
- classification and rationale;
- severity and rationale;
- confidence level and evidence components;
- bounding box, polygon, centroid, and hotspot;
- min/mean/max temperature;
- local reference temperature and method;
- local ΔT;
- area/morphology;
- latitude/longitude/altitude;
- sensor/capture/radiometric provenance;
- quality status and suppression checks;
- recommendation;
- annotation/crop paths;
- duplicate cluster and supporting observations;
- profile/engine versions;
- lifecycle status and audit history.

Unavailable values remain null/empty; presentation layers must not fabricate them.

## Inspection profiles

The detector remains vendor- and domain-neutral. Profiles supply domain interpretation and terminology. Initial versioned profiles are:

- Generic Thermal Survey;
- Electrical;
- Photovoltaic;
- Roof / Building Envelope;
- Mechanical;
- Pipeline / Linear Infrastructure.

No profile is described as standards-compliant unless a specific standard is separately implemented and verified.

## Display raster contract

`DisplayRaster` contains a bounded uint8 RGB preview, source path, display metadata, and optional CRS/affine transform. It carries no temperature matrix. This prevents rendered RGB/palette GeoTIFFs and orthomosaics from entering quantitative anomaly detection.

## Memory boundary

Full-frame quantitative GeoTIFF analysis currently has a conservative 50,000,000-pixel safety limit. Oversized quantitative rasters require a tiled radiometric workflow. Display/GIS previews use bounded resampling and can represent much larger rasters without allocating the full source image.

Inspection orchestration isolates per-source decode/quality failures so one invalid source does not automatically discard otherwise valid observations.

## Provenance invariant

```text
PDF / MAP / TABLE / ANNOTATION / CSV / JSON
                    ↓
             Canonical Finding
                    ↓
          Analysis characterization
                    ↓
             ThermalFrame region
                    ↓
       original radiometric source
```

Presentation layers may format quantitative truth; they may not mutate it.

## Claim boundaries

The following distinctions are architecture invariants:

```text
display raster != radiometric source
high temperature != defect
candidate != finding
severity != confidence
confidence != certification
GPS coordinate != proven physical-defect identity
duplicate cluster != proven same asset without evidence
automated report != thermographer certification
unit test != field validation
```

## Compatibility strategy

The original root-level modules remain temporarily as the legacy baseline. New product work is authoritative under `src/uas_thermal`. Legacy surfaces should be removed only after measured functional parity and explicit migration evidence.

## Vendor support states

| Adapter | State | Notes |
|---|---|---|
| Generic radiometric GeoTIFF | Operational with validation | Scalar radiometric rasters with explicit/inferable units; rendered uncalibrated imagery is rejected |
| Display/GIS GeoTIFF | Operational preview | Bounded RGB preview/context; never treated as temperature data |
| DJI DIRP | Operational with SDK | Runtime discovery and current ABI binding implemented; original camera R-JPEG still requires representative real-source Windows proof |
| FLIR/Teledyne | Contract only | Decoder intentionally not claimed until validated against supported radiometric formats |
| Autel | Contract only | Decoder intentionally not claimed until validated against supported radiometric formats |
