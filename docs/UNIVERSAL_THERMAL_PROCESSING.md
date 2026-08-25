# Universal Thermal Processing

## Product objective

UAS Thermal Analysis is a post-processing and deliverable system for professional thermal drone work. The target workflow is intentionally closer to an automated mapping/inspection pipeline than a single-image thermography editor:

```text
THERMAL / VISIBLE SOURCE DATA
          |
          v
INGEST + SOURCE CLASSIFICATION
          |
          v
RADIOMETRIC NORMALIZATION
          |
          v
THERMAL ORTHOMOSAIC / STITCHING
          |
          v
ORTHOMOSAIC QUALITY + PROVENANCE
          |
          v
CANONICAL QUANTITATIVE ANALYSIS
          |
          v
LOCAL AI-ASSISTED INTERPRETATION (OPTIONAL)
          |
          v
ANNOTATIONS + MEASUREMENTS + FINDING PLATES
          |
          v
CLIENT / ENGINEERING DELIVERABLE
```

The system remains vendor-neutral. Camera-specific radiometric decoding terminates at sensor adapters. Photogrammetry is replaceable through an orthomosaic backend contract. Local AI is provider/model replaceable and is never a source of temperature truth.

## Competitive deliverable baseline

The following public product capabilities define the practical deliverable baseline we want to meet or exceed without copying their product architectures.

### FLIR Thermal Studio

Relevant public capabilities:

- visual thermal tuning using temperature range/color distribution without changing the underlying measurement values;
- multiple thermal palettes;
- spot and area measurements;
- batch edit/normalization for repetitive thermal image operations;
- report templates and PDF/CSV/image export.

Sources:

- <https://www.flir.com/products/flir-thermal-studio-suite/>
- <https://docs.flir.com/T810635/en-US/latest/s04.html>

### DroneDeploy

Relevant public capabilities:

- stitched thermal maps and inspection context;
- radiometric visualization and spot temperature inspection when the source supports it;
- map annotations and measurements;
- issue/anomaly reports that communicate location/severity and close-up imagery;
- browser-based collaboration and shareable project/report outputs.

Sources:

- <https://www.dronedeploy.com/blog/how-to-perform-thermal-inspections-in-dronedeploy/>
- <https://www.dronedeploy.com/product/analysis>

### PIX4Dmatic

Relevant public capabilities:

- thermal datasets from FLIR, DJI and radiometric TIFF sources;
- georeferenced 2D thermal orthomosaics;
- temperature visualization in Kelvin/Celsius/Fahrenheit;
- dedicated thermal color palettes;
- atmospheric/reflected-temperature/humidity/emissivity controls when metadata supports quantitative processing;
- ROI crop and GeoTIFF/JPG/KML export.

Sources:

- <https://support.pix4d.com/hc/technical-release-note-pix4dmatic>
- <https://support.pix4d.com/hc/en-us/articles/360048200292>

### ArcGIS Drone2Map

Relevant public capabilities:

- automated single-band thermal True Ortho products;
- thermal/RGB/multispectral 2D processing templates;
- annotations using points, lines, polygons and text;
- inspection reports;
- tile-based processing/output options for large projects.

Sources:

- <https://doc.arcgis.com/en/drone2map/2025.2/help/2d-full.htm>
- <https://doc.arcgis.com/en/drone2map/2024.2/help/thermal-camera-support.htm>

### Raptor Maps

Relevant solar-inspection deliverables include a summary CSV and detailed anomaly data with circuit/location context, latitude/longitude, temperature delta where applicable, priority/status and imagery references. That is a useful benchmark for machine-readable engineering handoff even outside solar.

Source:

- <https://pages.raptormaps.com/raptor-maps-knowledge-hub/sharing-links-or-report-exports>

### OpenDroneMap

OpenDroneMap provides an open photogrammetry path for radiometric thermal data and can generate temperature orthophotos when `--radiometric-calibration camera` is supported by the input camera/metadata. It is therefore useful as an optional backend rather than as a product authority.

Sources:

- <https://docs.opendronemap.org/thermal/>
- <https://docs.opendronemap.org/arguments/radiometric-calibration/>

ODM's documented best-tested thermal cameras do not currently establish universal DJI Mavic 3 Thermal compatibility. A successful configured ODM path is evidence for that source/runtime combination only.

## v0.7 deliverable contract

The universal pipeline now targets this output shape:

```text
<inspection>/
|-- maps/
|   |-- thermal_orthomosaic.tif          # when stitching produced a quantitative ortho
|   |-- annotated_thermal_overview.png   # tuned presentation + canonical finding overlay
|   `-- survey_overview.geojson          # when coordinates are authoritative
|-- findings/
|   `-- A-###/
|       |-- annotated_thermal.png
|       |-- thermal_crop.png
|       |-- finding_plate.png
|       `-- finding.json
|-- data/
|   |-- findings.csv
|   |-- findings.json
|   |-- findings.geojson                 # when authoritative
|   `-- findings.kml                     # when authoritative
|-- report/
|   |-- inspection_report.pdf
|   `-- processing_report.json
|-- viewer/
|   `-- index.html                       # self-contained client/engineering review page
`-- inspection_manifest.json             # SHA-256 provenance
```

The PDF is the static professional deliverable. The HTML viewer is a portable review surface. The GeoTIFF and machine-readable files are engineering/GIS handoff. All three project the same canonical findings.

## Image optimization / thermal tuning

Thermal tuning is presentation-only. `ThermalStyle` supports:

- White Hot;
- Black Hot;
- Iron / Iron Bow;
- Arctic;
- Rainbow;
- Rainbow HC;
- Span / Level;
- explicit min/max range;
- isotherm range.

A style never changes the `float32` Celsius matrix. Batch rendering applies the same style to many matrices without mutating any quantitative input.

## Quantitative measurement tools

The measurement layer supports:

- Spot: configurable square neighborhood, default 4 x 4 average;
- Delta between two spot averages;
- Rectangle;
- Circle;
- Ellipse;
- Line with width;
- Freeform polygon.

Area measurements return min/max/mean/median/stddev/p95 and valid-pixel count. Measurement parameters are separate from radiometric calibration parameters.

## Orthomosaic backends

### `native-geotiff`

For already-georeferenced, single-band radiometric GeoTIFF tiles. It validates every input, requires one CRS and one compatible radiometric encoding, mosaics with a bounded memory budget, converts output to float32 Celsius and marks the product with explicit thermal provenance tags.

This is geospatial mosaicking, not photogrammetric reconstruction.

### `opendronemap`

For raw image collections when a local ODM runtime is installed and configured. The application stages input data and requests radiometric camera calibration. No runtime/container is downloaded automatically. The generated orthophoto is admitted to quantitative analysis only after it passes the UAS Thermal Analysis radiometric gate.

Configure with:

```powershell
$env:UAS_THERMAL_ODM_COMMAND = "<your local ODM command>"
```

## Local AI contract

The first provider implementation is Ollama, but the `LocalAIProvider` contract is model/provider neutral.

The application discovers installed models and their declared capabilities rather than hard-coding a single model family. Vision-capable models may receive a finding evidence crop. Text-only models receive structured canonical measurements/evidence.

Ollama integration uses local structured JSON output and temperature 0. No model is downloaded automatically.

Default local API:

```text
http://localhost:11434
```

Override:

```powershell
$env:UAS_THERMAL_OLLAMA_URL = "http://localhost:11434"
```

AI may generate only supplemental fields:

- concise finding summary;
- visual observations;
- possible explanations;
- recommended field verification;
- limitations.

AI may not change:

- source temperature matrix;
- radiometric quality decision;
- finding identity;
- bounding geometry;
- geolocation;
- max/mean/reference temperature;
- Delta-T;
- deterministic severity;
- deterministic confidence.

This boundary is enforced in code and tests.

Official Ollama references:

- <https://docs.ollama.com/api/introduction>
- <https://docs.ollama.com/capabilities/vision>
- <https://docs.ollama.com/capabilities/structured-outputs>

## Cross-industry profiles

The universal processing pipeline exposes initial profiles for:

- Generic thermal survey;
- Electrical;
- Photovoltaic;
- Roof/building envelope;
- Construction/building performance;
- Agriculture/crop thermal survey;
- Public safety;
- Natural resources/environmental survey;
- Mechanical;
- Pipeline/linear infrastructure.

These are interpretation profiles over the common quantitative detector. Profile names do not imply certification or standards compliance.

## Claim boundary

The automation target is **source data to review-ready deliverable**, not autonomous certification.

```text
AI summary != temperature measurement
thermal contrast != proven defect
stitched thermal visualization != proven quantitative ortho
successful photogrammetry != camera validation
inspection report != thermographer certification
```

A quantitative orthomosaic must preserve defensible temperature values. A field-accuracy claim still requires representative labeled/controlled validation data and predefined acceptance criteria.
