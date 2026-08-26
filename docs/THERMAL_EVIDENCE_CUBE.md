# Thermal Evidence Cube

## Purpose

The Thermal Evidence Cube is a multiband float32 TIFF/GeoTIFF export that exposes the pixel-level evidence used around thermal candidate detection without creating a second quantitative authority.

Band 1 is the decoded Celsius temperature matrix. Every other band is deterministic derived evidence. Derived bands may support inspection review, GIS analysis, validation, and debugging, but they are not independent temperature measurements, defect proof, or certification.

## Band contract

| Band | Name | Meaning | Authority |
|---:|---|---|---|
| 1 | `temperature_c` | Decoded Celsius temperature matrix | Radiometric authority |
| 2 | `local_reference_c` | Best local annular reference corresponding to the strongest local contrast | Derived |
| 3 | `local_delta_c` | Maximum local temperature difference against configured analysis radii | Derived |
| 4 | `robust_scene_deviation` | Robust scene-deviation score | Derived |
| 5 | `scale_support` | Count of analysis scales supporting local contrast | Derived |
| 6 | `candidate_mask` | Pre-morphology candidate gate | Derived |
| 7 | `finding_mask` | Accepted finding bounding-region mask | Derived |
| 8 | `structural_residual_c` | Experimental temperature-minus-local-background residual | Derived / experimental |
| 9 | `texture_curvature_c` | Experimental local thermal curvature magnitude | Derived / experimental |

Bands 8 and 9 were inspired by the useful signal-processing pattern in FAM-SRM's structural/high-frequency residual products. They are intentionally described conservatively: the UAS Thermal Analysis implementation does not claim that they are mathematical graphons, formal fractal dimensions, or direct defect measurements.

## Quantitative boundary

```text
validated radiometric source
        ↓
Celsius temperature matrix ──────────────── Band 1 (authority)
        ↓
local reference / ΔT / robust support ───── Bands 2-5 (derived)
        ↓
pre-morphology candidate evidence ───────── Band 6 (derived)
        ↓
canonical finding projection ────────────── Band 7 (derived)
        ↓
experimental residual diagnostics ───────── Bands 8-9 (derived)
```

Nothing in the evidence-cube export modifies the source temperature matrix, detector thresholds, canonical finding identity, geometry, severity, confidence, or geolocation.

## Large-raster behavior

Oversized scalar radiometric GeoTIFFs reuse the existing bounded-memory `TiledGeoTiffReader` contract. Each analysis tile includes an overlap halo for local-context calculations, while only the non-overlapping core is written into the evidence cube. This preserves the same ownership semantics used by quantitative tiled analysis and avoids double-writing halo pixels.

## RGB illumination context

`thermal.evidence.compute_illumination_context()` provides a supplemental RGB brightness, large-scale illumination field, and local shadow score. This helper never modifies radiometric temperature.

Pixel-level RGB illumination context is deliberately not injected into canonical finding evidence until an authoritative thermal-visible registration is available. Timestamp/GPS pairing alone is not sufficient to assume pixel registration.

## Residual ablation

`thermal.evidence_validation.evaluate_residual_ablation()` compares the existing pre-morphology candidate mask with an experimental structural-residual gate. It is an evaluation hook only; it cannot change production detector behavior.

Use representative labeled fixtures before promoting any residual-derived feature into production candidate acceptance, suppression, or confidence logic. Required evaluation should include precision, recall, IoU, ΔT preservation, false-positive class analysis, and tiled seam behavior.

## Inspection-package integration

When the geospatial runtime is available, accepted artifacts are exported under:

```text
maps/evidence/<index>_<source>_thermal_evidence.tif
```

Every package also includes:

```text
report/engineering_evidence_appendix.json
report/engineering_evidence_appendix.md
```

The inspection manifest records the band contract, export status, file hash, and authority boundary. Evidence-cube export is additive: failure to generate a derived cube does not invalidate an otherwise accepted radiometric inspection package.
