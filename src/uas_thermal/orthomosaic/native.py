from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np

from ..sensors.base import AdapterUnavailableError
from ..sensors.generic import (
    GenericGeoTiffAdapter,
    _encoding,
    _infer_unit,
    masked_band_to_float,
    temperature_to_celsius,
)
from ..thermal.radiometry import apply_scale_offset
from .base import OrthomosaicBackend, OrthomosaicRequest, OrthomosaicResult


class NativeGeoTiffMosaicBackend(OrthomosaicBackend):
    """Mosaic already-georeferenced scalar radiometric GeoTIFFs into Celsius.

    This backend is intentionally not photogrammetry. It mosaics georeferenced thermal rasters whose
    spatial placement is already authoritative. Raw camera frames require a photogrammetry backend.
    """

    name = "native-geotiff"

    def __init__(self, *, mem_limit_mb: int = 256):
        self.mem_limit_mb = max(64, int(mem_limit_mb))
        self.adapter = GenericGeoTiffAdapter()

    def available(self) -> bool:
        try:
            import rasterio  # noqa: F401
        except ImportError:
            return False
        return True

    def can_process(self, request: OrthomosaicRequest) -> bool:
        return bool(request.sources) and all(
            path.suffix.lower() in {".tif", ".tiff"} for path in request.sources
        )

    @staticmethod
    def _canonical_unit(unit: str, sample: np.ndarray) -> str:
        key = unit.strip().lower().replace("°", "").replace(" ", "")
        if key == "auto":
            return _infer_unit(sample)
        aliases = {
            "c": "celsius",
            "degc": "celsius",
            "celsius": "celsius",
            "k": "kelvin",
            "kelvin": "kelvin",
            "f": "fahrenheit",
            "degf": "fahrenheit",
            "fahrenheit": "fahrenheit",
            "decic": "decicelsius",
            "decicelsius": "decicelsius",
            "0.1c": "decicelsius",
            "decik": "decikelvin",
            "decikelvin": "decikelvin",
            "0.1k": "decikelvin",
            "centik": "centikelvin",
            "centikelvin": "centikelvin",
            "0.01k": "centikelvin",
        }
        return aliases.get(key, key)

    def _source_contract(self, path: Path):
        try:
            import rasterio
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to build thermal mosaics") from exc

        diagnostics = self.adapter.source_diagnostics(path)
        if not diagnostics.get("radiometric_candidate"):
            reasons = "; ".join(str(item) for item in diagnostics.get("radiometric_reasons", []))
            raise AdapterUnavailableError(f"Non-radiometric mosaic source {path.name}: {reasons}")
        with rasterio.open(path) as source:
            if source.count != 1:
                raise AdapterUnavailableError(
                    f"Native quantitative mosaic requires one scalar band: {path.name} has {source.count}"
                )
            if source.crs is None:
                raise AdapterUnavailableError(
                    f"Native quantitative mosaic requires an explicit CRS: {path.name}"
                )
            tags = source.tags()
            scale, offset, unit = _encoding(source, tags, self.adapter.scale, self.adapter.offset, self.adapter.unit)
            sample = source.read(
                1,
                out_shape=(min(256, source.height), min(256, source.width)),
                masked=True,
            )
            sample_raw = masked_band_to_float(sample)
            sample_scaled = apply_scale_offset(sample_raw, scale, offset)
            canonical_unit = self._canonical_unit(unit, sample_scaled)
            temperature_to_celsius(sample_scaled, canonical_unit)
            return {
                "crs": str(source.crs),
                "scale": float(scale),
                "offset": float(offset),
                "unit": canonical_unit,
                "nodata": source.nodata,
            }

    def process(self, request: OrthomosaicRequest) -> OrthomosaicResult:
        if not self.can_process(request):
            raise AdapterUnavailableError(
                "native-geotiff accepts only already-georeferenced radiometric TIFF/GeoTIFF sources"
            )
        try:
            import rasterio
            from rasterio.merge import merge
        except ImportError as exc:
            raise AdapterUnavailableError("Install the geospatial extra to build thermal mosaics") from exc

        request.output_dir.mkdir(parents=True, exist_ok=True)
        contracts = [self._source_contract(path) for path in request.sources]
        crs_values = {item["crs"] for item in contracts}
        if len(crs_values) != 1:
            raise AdapterUnavailableError(
                "Native thermal mosaic requires sources in one CRS; reproject explicitly before mosaicking"
            )
        encoding_values = {
            (item["scale"], item["offset"], item["unit"])
            for item in contracts
        }
        if len(encoding_values) != 1:
            raise AdapterUnavailableError(
                "Native thermal mosaic requires one shared radiometric encoding across all source tiles"
            )
        scale, offset, unit = next(iter(encoding_values))

        handles = [rasterio.open(path) for path in request.sources]
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix="uas-thermal-raw-mosaic-",
            suffix=".tif",
            dir=request.output_dir,
        )
        os.close(file_descriptor)
        temporary = Path(temporary_name)
        destination = request.output_dir / "thermal_orthomosaic.tif"
        report_path = request.output_dir / "orthomosaic_processing.json"
        try:
            merge_kwargs = {
                "dst_path": temporary,
                "mem_limit": self.mem_limit_mb,
                "dtype": "float32",
            }
            if request.resolution is not None:
                merge_kwargs["res"] = float(request.resolution)
            merge(handles, **merge_kwargs)

            with rasterio.open(temporary) as raw:
                profile = raw.profile.copy()
                # rasterio.merge may carry small source block sizes into the temporary profile.
                # GeoTIFF tiled blocks must be multiples of 16 on all supported GDAL builds.
                profile.pop("blockxsize", None)
                profile.pop("blockysize", None)
                profile.update(
                    dtype="float32",
                    count=1,
                    nodata=np.nan,
                    compress="deflate",
                    predictor=3,
                    tiled=True,
                    blockxsize=256,
                    blockysize=256,
                    BIGTIFF="IF_SAFER",
                )
                with rasterio.open(destination, "w", **profile) as output:
                    for _, window in raw.block_windows(1):
                        source_values = masked_band_to_float(raw.read(1, window=window, masked=True))
                        scaled = apply_scale_offset(source_values, float(scale), float(offset))
                        celsius = temperature_to_celsius(scaled, str(unit))
                        output.write(celsius.astype(np.float32, copy=False), 1, window=window)
                    output.update_tags(
                        THERMAL_UNIT="celsius",
                        THERMAL_SCALE="1.0",
                        THERMAL_OFFSET="0.0",
                        isCalibrated="true",
                        UAS_THERMAL_MOSAIC_BACKEND=self.name,
                        UAS_THERMAL_SOURCE_COUNT=str(len(request.sources)),
                    )
        finally:
            for handle in handles:
                handle.close()
            temporary.unlink(missing_ok=True)

        diagnostics = self.adapter.source_diagnostics(destination)
        if not diagnostics.get("radiometric_candidate"):
            raise RuntimeError("Generated thermal orthomosaic failed the radiometric source gate")
        report = {
            "backend": self.name,
            "source_count": len(request.sources),
            "output": str(destination),
            "quantitative": True,
            "output_unit": "celsius",
            "input_encoding": {"scale": scale, "offset": offset, "unit": unit},
            "crs": next(iter(crs_values)),
            "memory_limit_mb": self.mem_limit_mb,
            "request": {
                "project_name": request.project_name,
                "resolution": request.resolution,
                "target_crs": request.target_crs,
                "metadata": request.metadata,
            },
            "diagnostics": diagnostics,
        }
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return OrthomosaicResult(
            orthomosaic=destination,
            backend=self.name,
            quantitative=True,
            temperature_unit="celsius",
            source_count=len(request.sources),
            processing_report=report_path,
            metadata={"source_contracts": contracts, "diagnostics": diagnostics},
        )
