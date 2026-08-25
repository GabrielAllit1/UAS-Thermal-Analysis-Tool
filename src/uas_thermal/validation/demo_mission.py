from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..platform.config import AppConfig

_DEMO_SCHEMA = "uas-thermal-demo-mission/v1"
_DEMO_NAME = "Solar_Farm_Demo"
_TILE_SIZE = 48
_PIXEL_SIZE_M = 0.5
_ORIGIN_X = 500_000.0
_ORIGIN_Y = 3_100_000.0
_CRS = "EPSG:32617"


def bundled_demo_blueprint() -> dict[str, object]:
    """Return the public synthetic ground-truth contract for the learning mission."""

    return {
        "schema": _DEMO_SCHEMA,
        "name": "Solar Farm Demo",
        "synthetic": True,
        "profile_hint": "photovoltaic",
        "crs": _CRS,
        "temperature_unit": "celsius",
        "pixel_size_m": _PIXEL_SIZE_M,
        "tile_size_px": _TILE_SIZE,
        "tile_layout": [2, 2],
        "expected_canonical_findings": 3,
        "expected_severity_counts": {"minor": 1, "moderate": 1, "critical": 1},
        "seeded_findings": [
            {
                "id": "DEMO-A001",
                "tile": "thermal_r1_c1.tif",
                "delta_c": 8.0,
                "expected_severity": "minor",
                "pixel_box": [16, 16, 25, 25],
            },
            {
                "id": "DEMO-A002",
                "tile": "thermal_r1_c2.tif",
                "delta_c": 14.0,
                "expected_severity": "moderate",
                "pixel_box": [16, 14, 25, 23],
            },
            {
                "id": "DEMO-A003",
                "tile": "thermal_r2_c1.tif",
                "delta_c": 26.0,
                "expected_severity": "critical",
                "pixel_box": [18, 16, 27, 25],
            },
        ],
        "intentional_non_findings": [
            "3.5 C coherent warm region below the photovoltaic minimum-delta threshold",
            "30 C single-pixel spike that should be suppressed for insufficient region support",
            "small nodata patch",
        ],
        "claim_boundary": (
            "Synthetic functional acceptance data only. This demo is not field-validation evidence, "
            "thermographer certification, or proof of universal detection accuracy."
        ),
    }


def _temperature_tiles() -> dict[tuple[int, int], np.ndarray]:
    rng = np.random.default_rng(20_260_825)
    yy, xx = np.mgrid[0:_TILE_SIZE, 0:_TILE_SIZE]

    def baseline() -> np.ndarray:
        values = (
            33.0
            + 0.25 * (xx / (_TILE_SIZE - 1))
            + 0.15 * (yy / (_TILE_SIZE - 1))
            + rng.normal(0.0, 0.025, (_TILE_SIZE, _TILE_SIZE))
        )
        return values.astype(np.float32)

    tiles = {(row, col): baseline() for row in range(2) for col in range(2)}
    tiles[(0, 0)][16:26, 16:26] += np.float32(8.0)
    tiles[(0, 1)][14:24, 16:26] += np.float32(14.0)
    tiles[(1, 0)][16:26, 18:28] += np.float32(26.0)

    # Deliberate rejection/suppression challenges.
    tiles[(1, 1)][12:22, 12:22] += np.float32(3.5)
    tiles[(1, 1)][35, 35] += np.float32(30.0)
    tiles[(1, 1)][2:4, 2:4] = np.nan
    return tiles


def _write_context_png(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return

    image = Image.new("RGB", (960, 540), (7, 15, 22))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 920, 500), outline=(48, 112, 145), width=3)
    for row in range(4):
        for col in range(9):
            x0 = 90 + col * 88
            y0 = 105 + row * 86
            draw.rectangle((x0, y0, x0 + 72, y0 + 54), fill=(22, 56, 78), outline=(56, 161, 193))
            draw.line((x0 + 36, y0, x0 + 36, y0 + 54), fill=(35, 104, 134), width=1)
    draw.text((70, 55), "SYNTHETIC SOLAR FARM DEMO", fill=(92, 228, 255))
    draw.text((70, 465), "CONTEXT ONLY - NOT RADIOMETRIC", fill=(255, 192, 72))
    image.save(path)


def _write_context_geojson(root: Path) -> None:
    west = _ORIGIN_X
    east = _ORIGIN_X + 2 * _TILE_SIZE * _PIXEL_SIZE_M
    north = _ORIGIN_Y
    south = _ORIGIN_Y - 2 * _TILE_SIZE * _PIXEL_SIZE_M
    boundary = {
        "type": "FeatureCollection",
        "name": "Synthetic demo boundary",
        "crs": {"type": "name", "properties": {"name": _CRS}},
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Solar Farm Demo", "synthetic": True},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
                },
            }
        ],
    }
    path = root / "GIS" / "site_boundary.geojson"
    path.write_text(json.dumps(boundary, indent=2), encoding="utf-8")

    flight = {
        "type": "FeatureCollection",
        "name": "Synthetic demo flight path",
        "crs": {"type": "name", "properties": {"name": _CRS}},
        "features": [
            {
                "type": "Feature",
                "properties": {"synthetic": True},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [west + 4.0, north - 8.0],
                        [east - 4.0, north - 8.0],
                        [east - 4.0, south + 8.0],
                        [west + 4.0, south + 8.0],
                    ],
                },
            }
        ],
    }
    (root / "GIS" / "flight_path.geojson").write_text(
        json.dumps(flight, indent=2), encoding="utf-8"
    )


def materialize_demo_mission(output_root: str | Path | None = None) -> Path:
    """Create a small deterministic radiometric mission for one-click learning/acceptance tests.

    The generated files live in the application data directory by default, never in customer source
    folders. Re-running the function safely rewrites only the known synthetic demo assets.
    """

    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError as exc:
        raise RuntimeError(
            "The bundled demo requires the geospatial extra (rasterio). Install the normal desktop "
            "package extras, then run the demo again."
        ) from exc

    if output_root is None:
        root = AppConfig.from_env().data_dir / "demo" / _DEMO_NAME
    else:
        candidate = Path(output_root).expanduser().resolve()
        root = candidate if candidate.name == _DEMO_NAME else candidate / _DEMO_NAME

    thermal_dir = root / "Thermal"
    context_dir = root / "Context"
    gis_dir = root / "GIS"
    for directory in (thermal_dir, context_dir, gis_dir):
        directory.mkdir(parents=True, exist_ok=True)

    tags = {
        "THERMAL_UNIT": "celsius",
        "THERMAL_SCALE": "1.0",
        "THERMAL_OFFSET": "0.0",
        "isCalibrated": "true",
        "DEMO_DATA": "true",
        "DATASET": _DEMO_NAME,
        "SENSOR": "Synthetic Radiometric Thermal",
        "acquisitionStartDate": "2026-08-25T14:00:00Z",
        "acquisitionEndDate": "2026-08-25T14:05:00Z",
    }
    for (row, col), values in _temperature_tiles().items():
        west = _ORIGIN_X + col * _TILE_SIZE * _PIXEL_SIZE_M
        north = _ORIGIN_Y - row * _TILE_SIZE * _PIXEL_SIZE_M
        destination = thermal_dir / f"thermal_r{row + 1}_c{col + 1}.tif"
        with rasterio.open(
            destination,
            "w",
            driver="GTiff",
            height=_TILE_SIZE,
            width=_TILE_SIZE,
            count=1,
            dtype="float32",
            crs=_CRS,
            transform=from_origin(west, north, _PIXEL_SIZE_M, _PIXEL_SIZE_M),
            nodata=np.nan,
        ) as dataset:
            dataset.write(values, 1)
            dataset.update_tags(**tags)

    _write_context_png(context_dir / "site_overview.png")
    _write_context_geojson(root)
    blueprint = bundled_demo_blueprint()
    (root / "mission.json").write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
    (root / "expected_findings.json").write_text(
        json.dumps(
            {
                "schema": "uas-thermal-demo-ground-truth/v1",
                "expected_canonical_findings": blueprint["expected_canonical_findings"],
                "expected_severity_counts": blueprint["expected_severity_counts"],
                "seeded_findings": blueprint["seeded_findings"],
                "intentional_non_findings": blueprint["intentional_non_findings"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return root


__all__ = ["bundled_demo_blueprint", "materialize_demo_mission"]
