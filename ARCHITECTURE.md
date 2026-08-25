# Architecture

## Design objective

UAS Thermal Analysis normalizes heterogeneous thermal sources into a common thermal frame, then keeps all analysis and deliverables vendor-neutral.

```text
Source imagery
    ↓
Sensor Registry → Adapter selection
    ↓
ThermalFrame (temperature matrix + display image + metadata + georeferencing)
    ↓
Calibration / statistics / anomaly detection
    ↓
Inspection findings + severity + recommendations
    ↓
Geospatial enrichment
    ↓
CSV / KML / PDF / future GIS exports
```

## Subsystems

### application
Coordinates end-user workflows. It owns project state and orchestration, not sensor decoding or thermal algorithms.

### thermal
Owns radiometric calibration parameters, array normalization, statistics, and anomaly detection. Detection policy is based primarily on temperature delta from local/background conditions rather than a single hard-coded absolute temperature.

### sensors
Defines `ThermalSensorAdapter` and `ThermalFrame`. Vendor integrations terminate here. Downstream modules must not import vendor SDKs.

### geospatial
Owns GeoTIFF metadata, coordinate transforms, KML parsing/writing, and world-file transforms. CRS assumptions are explicit and data-driven; no project-specific State Plane CRS is globally hard-coded.

### inspections
Owns finding models, severity policy, and maintenance recommendations. Recommendations remain general unless an inspection profile supplies domain-specific rules.

### reporting
Serializes inspection results into deliverables. Report generation must not embed customer names, site names, dates, or company emails in code.

### platform
Owns configuration, logging, licensing boundaries, and packaging helpers. Vendor binaries and secrets stay outside source control.

## Adapter contract

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

## Compatibility strategy

The original root-level modules remain temporarily as the legacy baseline. New code is added under `src/uas_thermal`. Migration happens by replacing legacy call sites with tested modular services rather than deleting the working application up front.

## Vendor support states

| Adapter | State | Notes |
|---|---|---|
| Generic radiometric GeoTIFF | Foundation implemented | Reads numeric raster temperature data with configurable scale/offset |
| DJI DIRP | Foundation implemented | Runtime SDK discovery; requires locally installed vendor binaries |
| FLIR/Teledyne | Contract only | Decoder intentionally not claimed until tested against supported radiometric formats |
| Autel | Contract only | Decoder intentionally not claimed until tested against supported radiometric formats |
