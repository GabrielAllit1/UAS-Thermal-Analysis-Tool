# Architecture

## Design objective

UAS Thermal Analysis keeps quantitative radiometry separate from display/GIS imagery, then keeps all downstream analysis and deliverables vendor-neutral.

```text
Source imagery
    ↓
Classification / adapter selection
    ↓
┌───────────────────────────────┬───────────────────────────────┐
│ Quantitative radiometric lane │ Display / GIS lane            │
│                               │                               │
│ ThermalFrame                  │ DisplayRaster                 │
│ Celsius matrix                │ bounded RGB preview           │
│ optional display RGB          │ CRS / affine metadata         │
│ sensor metadata               │ no temperature claims        │
└───────────────┬───────────────┴───────────────┬───────────────┘
                │                               │
Calibration / statistics /             map/context rendering
anomaly detection                      future finding overlays
                │                               │
                └───────────────┬───────────────┘
                                ↓
                 inspection findings / reports
```

A filename or palette that looks thermal is never enough to enter the quantitative lane. The source must decode to actual temperature values or documented radiometric counts.

## Subsystems

### application
Coordinates end-user workflows. It owns project state and orchestration, not sensor decoding or thermal algorithms. The desktop exposes source classification and bounded preview before quantitative analysis.

### thermal
Owns radiometric calibration parameters, array normalization, statistics, and anomaly detection. Detection policy is based primarily on temperature delta from local/background conditions rather than a single hard-coded absolute temperature.

### sensors
Defines `ThermalSensorAdapter` and `ThermalFrame`. Vendor integrations terminate here. Downstream modules must not import vendor SDKs. Only validated quantitative sources become `ThermalFrame` instances.

### geospatial
Owns GeoTIFF metadata, coordinate transforms, KML parsing/writing, world-file transforms, and `DisplayRaster` bounded previews. Large display orthomosaics are sampled/resampled for preview instead of being loaded into memory at full resolution. CRS assumptions are explicit and data-driven; no project-specific State Plane CRS is globally hard-coded.

### inspections
Owns finding models, severity policy, and maintenance recommendations. Recommendations remain general unless an inspection profile supplies domain-specific rules.

### reporting
Serializes inspection results into deliverables. Report generation must not embed customer names, site names, dates, or company emails in code.

### platform
Owns configuration, logging, licensing boundaries, and packaging helpers. Vendor binaries and secrets stay outside source control.

## Quantitative adapter contract

An adapter implements:

- `name`: stable adapter identifier
- `can_read(path)`: cheap source compatibility check
- `read(path, calibration)`: decode to `ThermalFrame`

A `ThermalFrame` contains:

- Celsius temperature matrix
- optional display RGB image
- source path
- sensor/vendor metadata
- optional CRS and affine transform

## Display raster contract

`DisplayRaster` is intentionally not a `ThermalFrame`. It contains:

- bounded uint8 RGB preview
- source path
- raster/display metadata
- optional CRS and affine transform

It carries no temperature matrix. This prevents rendered RGB/palette GeoTIFFs and orthomosaics from being accidentally fed into anomaly detection.

## Memory boundary

Full-frame quantitative GeoTIFF analysis currently has a conservative 50,000,000-pixel safety limit. Oversized radiometric rasters require a future tiled quantitative workflow. Display/GIS previews use bounded resampling and are allowed for much larger rasters because they do not allocate the full source image.

## Compatibility strategy

The original root-level modules remain temporarily as the legacy baseline. New code is added under `src/uas_thermal`. Migration happens by replacing legacy call sites with tested modular services rather than deleting the working application up front.

## Vendor support states

| Adapter | State | Notes |
|---|---|---|
| Generic radiometric GeoTIFF | Operational with validation | Accepts scalar radiometric rasters with explicit/inferable units and rejects rendered uncalibrated imagery |
| Display/GIS GeoTIFF | Operational preview | Bounded RGB preview/classification; never treated as temperature data |
| DJI DIRP | Operational with SDK | Runtime SDK discovery; original camera R-JPEG still requires real-source Windows validation |
| FLIR/Teledyne | Contract only | Decoder intentionally not claimed until tested against supported radiometric formats |
| Autel | Contract only | Decoder intentionally not claimed until tested against supported radiometric formats |
