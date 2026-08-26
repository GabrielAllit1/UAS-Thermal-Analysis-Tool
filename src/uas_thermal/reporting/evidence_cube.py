from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ..thermal.evidence import EvidenceConfig, compute_evidence_layers

if TYPE_CHECKING:
    from ..application.workflows import AnalysisArtifact
    from ..inspections.profiles import InspectionProfile
    from ..sensors.base import ThermalFrame


EVIDENCE_BANDS = (
    ("temperature_c", "Temperature (Celsius) - quantitative authority", "degC", "radiometric", False),
    ("local_reference_c", "Best local annular reference temperature", "degC", "derived", False),
    ("local_delta_c", "Maximum local temperature delta", "degC", "derived", False),
    ("robust_scene_deviation", "Robust scene deviation score", "score", "derived", False),
    ("scale_support", "Multi-scale local contrast support count", "count", "derived", False),
    ("candidate_mask", "Pre-morphology thermal candidate mask", "boolean", "derived", False),
    ("finding_mask", "Accepted finding bounding-region mask", "boolean", "derived", False),
    ("structural_residual_c", "Experimental thermal structural residual", "degC", "derived", True),
    ("texture_curvature_c", "Experimental thermal local curvature magnitude", "degC", "derived", True),
)


@dataclass(frozen=True, slots=True)
class EvidenceCubeResult:
    path: Path
    band_names: tuple[str, ...]
    georeferenced: bool
    tiled: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "band_names": list(self.band_names),
            "georeferenced": self.georeferenced,
            "tiled": self.tiled,
            "temperature_authority_band": 1,
            "derived_bands": list(range(2, len(self.band_names) + 1)),
            "experimental_bands": [index for index, spec in enumerate(EVIDENCE_BANDS, 1) if spec[4]],
        }


def band_manifest() -> list[dict[str, object]]:
    return [
        {
            "band": index,
            "name": name,
            "description": description,
            "unit": unit,
            "authority": authority,
            "experimental": experimental,
        }
        for index, (name, description, unit, authority, experimental) in enumerate(EVIDENCE_BANDS, 1)
    ]


def _rasterio():
    try:
        import rasterio
        from rasterio.transform import Affine
        from rasterio.windows import Window
    except ImportError as exc:
        raise RuntimeError("Install the geospatial extra to export thermal evidence cubes") from exc
    return rasterio, Affine, Window


def _profile_for_shape(
    *,
    width: int,
    height: int,
    crs: str | None,
    transform: tuple[float, ...] | None,
) -> dict[str, object]:
    _, Affine, _ = _rasterio()
    affine = Affine.identity() if transform is None else Affine(*transform[:6])
    return {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": len(EVIDENCE_BANDS),
        "dtype": "float32",
        "crs": crs,
        "transform": affine,
        "nodata": np.nan,
        "compress": "deflate",
        "predictor": 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }


def _set_metadata(destination) -> None:
    for index, (name, description, unit, authority, experimental) in enumerate(EVIDENCE_BANDS, 1):
        destination.set_band_description(index, description)
        destination.update_tags(
            index,
            NAME=name,
            UNIT=unit,
            AUTHORITY=authority,
            EXPERIMENTAL=str(experimental).lower(),
        )
    destination.update_tags(
        UAS_THERMAL_EVIDENCE_CUBE="1",
        TEMPERATURE_AUTHORITY_BAND="1",
        DERIVED_EVIDENCE_BANDS="2-9",
        EXPERIMENTAL_RESIDUAL_BANDS="8,9",
        CLAIM_BOUNDARY=(
            "Band 1 preserves decoded Celsius radiometry. Bands 2-9 are derived evidence and must not "
            "be interpreted as independent temperature measurements, defect proof, or certification."
        ),
    )


def _write_arrays(destination, layers, *, window=None, core_slice=None) -> None:
    arrays = layers.arrays()
    if core_slice is not None:
        row_slice, col_slice = core_slice
        arrays = tuple(array[row_slice, col_slice] for array in arrays)
    for index, array in enumerate(arrays, 1):
        destination.write(np.asarray(array, dtype=np.float32), index, window=window)


def write_frame_evidence_cube(
    frame: ThermalFrame,
    findings,
    path: str | Path,
    *,
    config: EvidenceConfig | None = None,
) -> EvidenceCubeResult:
    rasterio, _, _ = _rasterio()
    destination_path = Path(path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    layers = compute_evidence_layers(frame.temperature_c, config=config, findings=findings)
    height, width = frame.temperature_c.shape
    profile = _profile_for_shape(
        width=width,
        height=height,
        crs=frame.crs,
        transform=frame.transform,
    )
    with rasterio.open(destination_path, "w", **profile) as destination:
        _write_arrays(destination, layers)
        _set_metadata(destination)
    return EvidenceCubeResult(
        destination_path,
        tuple(item[0] for item in EVIDENCE_BANDS),
        georeferenced=bool(frame.crs and frame.transform),
        tiled=False,
    )


def _calibration_from_frame(frame: ThermalFrame):
    from ..thermal.calibration import ThermalCalibration

    payload = frame.metadata.get("calibration", {})
    if not isinstance(payload, dict):
        return ThermalCalibration()
    allowed = {
        key: payload[key]
        for key in (
            "emissivity",
            "distance_m",
            "relative_humidity",
            "reflected_temperature_c",
            "ambient_temperature_c",
        )
        if key in payload
    }
    return ThermalCalibration(**allowed)


def _write_tiled_generic_cube(
    artifact: AnalysisArtifact,
    path: Path,
    *,
    config: EvidenceConfig,
) -> EvidenceCubeResult:
    rasterio, _, Window = _rasterio()
    from ..sensors.generic import GenericGeoTiffAdapter
    from ..sensors.geotiff_tiles import TiledGeoTiffReader

    metadata = artifact.result.metadata
    source_path = Path(artifact.result.source)
    adapter = GenericGeoTiffAdapter(
        scale=float(metadata.get("scale", 1.0)),
        offset=float(metadata.get("offset", 0.0)),
        unit=str(metadata.get("input_unit", "auto")),
    )
    tile_size = int(metadata.get("tile_size", 2048))
    overlap = max(int(metadata.get("tile_overlap", 0)), max(config.local_radii) * 2, 64)
    reader = TiledGeoTiffReader(adapter, tile_size=tile_size, overlap=overlap)
    calibration = _calibration_from_frame(artifact.frame)

    with rasterio.open(source_path) as source:
        profile = source.profile.copy()
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        profile.update(
            count=len(EVIDENCE_BANDS),
            dtype="float32",
            nodata=np.nan,
            compress="deflate",
            predictor=3,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            BIGTIFF="IF_SAFER",
        )
        georeferenced = bool(source.crs is not None and source.transform is not None)

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as destination:
        for tile in reader.iter_tiles(source_path, calibration):
            bounds = tile.bounds
            layers = compute_evidence_layers(
                tile.frame.temperature_c,
                config=config,
                findings=artifact.result.findings,
                finding_offset=(bounds.read_col_off, bounds.read_row_off),
            )
            left, top, right, bottom = bounds.local_core
            window = Window(
                bounds.core_col_off,
                bounds.core_row_off,
                bounds.core_width,
                bounds.core_height,
            )
            _write_arrays(
                destination,
                layers,
                window=window,
                core_slice=(slice(top, bottom), slice(left, right)),
            )
        _set_metadata(destination)
        destination.update_tags(TILED_EVIDENCE="true", TILE_OVERLAP=str(overlap))

    return EvidenceCubeResult(
        path,
        tuple(item[0] for item in EVIDENCE_BANDS),
        georeferenced=georeferenced,
        tiled=True,
    )


def write_artifact_evidence_cube(
    artifact: AnalysisArtifact,
    profile: InspectionProfile,
    path: str | Path,
) -> EvidenceCubeResult:
    """Export one traceable evidence cube without changing canonical thermal analysis."""

    destination = Path(path)
    config = EvidenceConfig.from_profile(profile)
    if (
        artifact.result.adapter == "generic-geotiff"
        and bool(artifact.result.metadata.get("tiled_analysis"))
    ):
        return _write_tiled_generic_cube(artifact, destination, config=config)
    return write_frame_evidence_cube(
        artifact.frame,
        artifact.result.findings,
        destination,
        config=config,
    )
