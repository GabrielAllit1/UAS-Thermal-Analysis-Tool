from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import __version__
from ..geospatial.transforms import pixel_to_map, transform_point
from ..inspections.models import (
    InspectionResult,
    InspectionSummary,
    QualityStatus,
    SuppressionRecord,
)
from ..inspections.profiles import InspectionProfile, get_profile
from ..inspections.recommendations import maintenance_recommendation
from ..sensors.base import AdapterUnavailableError, ThermalFrame
from ..sensors.generic import GenericGeoTiffAdapter
from ..sensors.geotiff_tiles import TiledGeoTiffReader
from ..sensors.registry import AdapterRegistry, default_registry
from ..thermal.anomaly_detection import DetectionConfig, analyze_temperature
from ..thermal.calibration import ThermalCalibration
from ..thermal.quality import evaluate_radiometric_quality
from ..thermal.statistics import TemperatureStatistics, summarize_temperature
from .projects import Project


@dataclass(slots=True)
class AnalysisArtifact:
    result: InspectionResult
    frame: ThermalFrame


@dataclass(slots=True)
class _StreamingTemperatureStats:
    total_pixels: int
    sample_target: int = 250_000
    valid_pixels: int = 0
    total: float = 0.0
    total_squares: float = 0.0
    minimum: float = float("inf")
    maximum: float = float("-inf")
    samples: list[np.ndarray] = field(default_factory=list)

    @property
    def sample_stride(self) -> int:
        return max(1, self.total_pixels // self.sample_target)

    def update(self, values: np.ndarray) -> None:
        finite = np.asarray(values, dtype=np.float32)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return
        values64 = finite.astype(np.float64, copy=False)
        self.valid_pixels += int(values64.size)
        self.total += float(np.sum(values64, dtype=np.float64))
        self.total_squares += float(np.sum(values64 * values64, dtype=np.float64))
        self.minimum = min(self.minimum, float(np.min(values64)))
        self.maximum = max(self.maximum, float(np.max(values64)))
        self.samples.append(finite[:: self.sample_stride].copy())

    def finalize(self) -> TemperatureStatistics:
        if self.valid_pixels == 0:
            raise AdapterUnavailableError("GeoTIFF contains no finite thermal samples")
        mean = self.total / self.valid_pixels
        variance = max(0.0, self.total_squares / self.valid_pixels - mean * mean)
        sample = np.concatenate(self.samples) if self.samples else np.array([mean], dtype=np.float32)
        return TemperatureStatistics(
            minimum_c=self.minimum,
            maximum_c=self.maximum,
            mean_c=mean,
            median_c=float(np.median(sample)),
            stddev_c=float(np.sqrt(variance)),
            p95_c=float(np.percentile(sample, 95)),
            valid_pixels=self.valid_pixels,
        )


@dataclass(slots=True)
class AnalysisWorkflow:
    registry: AdapterRegistry
    detection: DetectionConfig = field(default_factory=DetectionConfig)

    @classmethod
    def default(cls) -> AnalysisWorkflow:
        return cls(default_registry())

    def analyze_artifact(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> AnalysisArtifact:
        source_path = Path(source)
        calibration = calibration or ThermalCalibration()
        active_profile = profile or get_profile(project.profile_id if project else None)
        adapter = self.registry.select(source_path, preferred=adapter_name)

        if isinstance(adapter, GenericGeoTiffAdapter):
            diagnostics = adapter.source_diagnostics(source_path)
            if diagnostics.get("requires_tiled_processing"):
                return self._analyze_tiled_geotiff(
                    source_path,
                    adapter,
                    calibration,
                    project,
                    active_profile,
                )

        frame = adapter.read(source_path, calibration)
        quality = evaluate_radiometric_quality(frame, calibration)
        if not quality.accepted:
            raise AdapterUnavailableError(
                "Radiometric quality gate rejected source: " + "; ".join(quality.reasons)
            )

        stats = summarize_temperature(frame.temperature_c)
        config = self._active_detection(active_profile)
        outcome = analyze_temperature(
            frame.temperature_c,
            config=config,
            profile=active_profile,
        )
        findings = outcome.findings
        metadata = dict(frame.metadata)
        metadata["analysis_engine_version"] = __version__
        metadata["detection"] = outcome.diagnostics
        self._georeference(findings, frame, metadata)

        self._populate_finding_provenance(
            findings,
            source_path=source_path,
            adapter_name=adapter.name,
            quality_status=quality.status,
            calibration=calibration,
            project=project,
            profile=active_profile,
            frame_metadata=frame.metadata,
        )
        summary = self._summary(findings, stats, warned=bool(quality.warnings))
        result = InspectionResult(
            source=str(source_path),
            adapter=adapter.name,
            statistics=stats,
            findings=findings,
            metadata=metadata,
            project=project.report_metadata() if project else {},
            suppressions=outcome.suppressions,
            quality=quality.as_dict(),
            profile=active_profile.as_dict(),
            summary=summary,
        )
        return AnalysisArtifact(result=result, frame=frame)

    def _analyze_tiled_geotiff(
        self,
        source_path: Path,
        adapter: GenericGeoTiffAdapter,
        calibration: ThermalCalibration,
        project: Project | None,
        active_profile: InspectionProfile,
    ) -> AnalysisArtifact:
        config = self._active_detection(active_profile)
        overlap = max(64, max(config.local_radii, default=1) * 2)
        reader = TiledGeoTiffReader(adapter, tile_size=2048, overlap=overlap)
        context = reader.context(source_path)
        stats_accumulator = _StreamingTemperatureStats(context.width * context.height)
        findings = []
        suppressions: list[SuppressionRecord] = []
        tile_count = 0
        georeferenced = 0
        detection_candidates = 0

        for tile in reader.iter_tiles(source_path, calibration):
            tile_count += 1
            stats_accumulator.update(tile.core_temperature())
            outcome = analyze_temperature(
                tile.frame.temperature_c,
                config=config,
                profile=active_profile,
            )
            detection_candidates += len(outcome.findings)
            for finding in outcome.findings:
                if not tile.owns(finding.center_x, finding.center_y):
                    continue
                local_metadata: dict[str, object] = {}
                self._georeference([finding], tile.frame, local_metadata)
                if finding.latitude is not None and finding.longitude is not None:
                    georeferenced += 1
                self._shift_finding(
                    finding,
                    tile.bounds.read_col_off,
                    tile.bounds.read_row_off,
                )
                findings.append(finding)
            for item in outcome.suppressions:
                if item.center_x is None or item.center_y is None:
                    continue
                if not tile.owns(item.center_x, item.center_y):
                    continue
                suppressions.append(
                    SuppressionRecord(
                        item.reason,
                        item.area_px,
                        item.center_x + tile.bounds.read_col_off,
                        item.center_y + tile.bounds.read_row_off,
                        dict(item.details),
                    )
                )

        stats = stats_accumulator.finalize()
        valid_fraction = stats.valid_pixels / max(context.width * context.height, 1)
        if valid_fraction < 0.70:
            raise AdapterUnavailableError(
                "Radiometric quality gate rejected source: "
                f"valid temperature coverage {valid_fraction:.1%} is below required 70%"
            )

        findings.sort(key=lambda item: item.delta_temperature_c, reverse=True)
        for index, finding in enumerate(findings, 1):
            finding.finding_id = f"A-{index:03d}"
            finding.canonical_finding_id = finding.finding_id

        warnings = []
        if calibration.emissivity == 0.95:
            warnings.append("emissivity is using the generic default; verify it for the inspected surface")
        if not context.crs:
            warnings.append("source is not fully georeferenced; geographic finding export may be unavailable")
        tags = context.metadata.get("tags")
        if not isinstance(tags, dict) or not any(
            key.lower() in {"capture_time", "timestamp", "datetime", "datetimeoriginal"}
            for key in tags
        ):
            warnings.append("capture timestamp was not established from source metadata")
        warnings.append(
            "median and p95 use a deterministic bounded sample; min/max/mean/stddev use all valid pixels"
        )
        quality_status = QualityStatus.PASS_WITH_WARNINGS if warnings else QualityStatus.PASS
        quality = {
            "status": quality_status.value,
            "accepted": True,
            "reasons": [],
            "warnings": warnings,
            "metrics": {
                "width": context.width,
                "height": context.height,
                "total_pixels": context.width * context.height,
                "valid_pixels": stats.valid_pixels,
                "valid_fraction": round(valid_fraction, 6),
                "minimum_c": stats.minimum_c,
                "maximum_c": stats.maximum_c,
                "dynamic_range_c": stats.maximum_c - stats.minimum_c,
            },
        }
        self._populate_finding_provenance(
            findings,
            source_path=source_path,
            adapter_name=adapter.name,
            quality_status=quality_status,
            calibration=calibration,
            project=project,
            profile=active_profile,
            frame_metadata=context.metadata,
        )

        metadata = dict(context.metadata)
        metadata.update(
            {
                "analysis_engine_version": __version__,
                "tiled_analysis": True,
                "tile_count": tile_count,
                "full_raster_statistics": True,
                "percentile_statistics": "deterministic-bounded-sample",
                "detection": {
                    "tile_count": tile_count,
                    "tile_candidates": detection_candidates,
                    "accepted_findings": len(findings),
                    "suppressed_candidates": len(suppressions),
                },
                "georeferenced_findings": georeferenced,
                "georeferencing_status": "assigned" if georeferenced else "not_authoritative",
            }
        )
        preview_frame = reader.preview_frame(source_path, calibration)
        preview_frame.metadata.update(
            {
                "source_width": context.width,
                "source_height": context.height,
                "analysis_extent": "full-raster-tiled",
                "temperature_matrix_scope": "bounded-preview",
            }
        )
        summary = self._summary(findings, stats, warned=True)
        result = InspectionResult(
            source=str(source_path),
            adapter=adapter.name,
            statistics=stats,
            findings=findings,
            metadata=metadata,
            project=project.report_metadata() if project else {},
            suppressions=suppressions,
            quality=quality,
            profile=active_profile.as_dict(),
            summary=summary,
        )
        return AnalysisArtifact(result=result, frame=preview_frame)

    def _active_detection(self, active_profile: InspectionProfile) -> DetectionConfig:
        config = DetectionConfig.from_profile(active_profile)
        if self.detection != DetectionConfig():
            config = self.detection
        return config

    @staticmethod
    def _shift_finding(finding, x_offset: int, y_offset: int) -> None:
        finding.center_x += x_offset
        finding.center_y += y_offset
        if finding.hotspot_x is not None:
            finding.hotspot_x += x_offset
        if finding.hotspot_y is not None:
            finding.hotspot_y += y_offset
        if finding.bbox is not None:
            x0, y0, x1, y1 = finding.bbox
            finding.bbox = (
                x0 + x_offset,
                y0 + y_offset,
                x1 + x_offset,
                y1 + y_offset,
            )
        if finding.polygon:
            finding.polygon = [
                (x + x_offset, y + y_offset)
                for x, y in finding.polygon
            ]

    @staticmethod
    def _populate_finding_provenance(
        findings,
        *,
        source_path: Path,
        adapter_name: str,
        quality_status: QualityStatus,
        calibration: ThermalCalibration,
        project: Project | None,
        profile: InspectionProfile,
        frame_metadata: dict,
    ) -> None:
        inspection_id = project.inspection_id if project else ""
        project_id = project.project_id if project else ""
        source_id = source_path.name
        source_sensor = (
            " ".join(filter(None, [project.sensor_vendor, project.sensor_model]))
            if project
            else str(frame_metadata.get("sensor", ""))
        )
        for finding in findings:
            finding.inspection_id = inspection_id
            finding.project_id = project_id
            finding.source_image_id = source_id
            finding.source_path = str(source_path)
            finding.source_sensor = source_sensor
            finding.radiometric_provenance = {
                "adapter": adapter_name,
                "quality_status": quality_status.value,
                "calibration": {
                    "emissivity": calibration.emissivity,
                    "distance_m": calibration.distance_m,
                    "relative_humidity": calibration.relative_humidity,
                    "reflected_temperature_c": calibration.reflected_temperature_c,
                },
            }
            finding.quality_status = quality_status
            finding.analysis_engine_version = __version__
            finding.recommendation = maintenance_recommendation(finding, profile)

    @staticmethod
    def _summary(
        findings,
        stats: TemperatureStatistics,
        *,
        warned: bool,
    ) -> InspectionSummary:
        return InspectionSummary(
            images_discovered=1,
            images_accepted=1,
            images_warned=int(warned),
            observations=len(findings),
            canonical_findings=len(findings),
            critical=sum(item.severity.value == "critical" for item in findings),
            moderate=sum(item.severity.value == "moderate" for item in findings),
            minor=sum(item.severity.value == "minor" for item in findings),
            highest_temperature_c=max(
                (item.max_temperature_c for item in findings),
                default=stats.maximum_c,
            ),
            highest_delta_c=max((item.delta_temperature_c for item in findings), default=None),
        )

    def analyze(
        self,
        source: str | Path,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> InspectionResult:
        return self.analyze_artifact(source, calibration, adapter_name, project, profile).result

    def analyze_many(
        self,
        sources: Iterable[str | Path],
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        project: Project | None = None,
        profile: InspectionProfile | None = None,
    ) -> list[AnalysisArtifact]:
        return [
            self.analyze_artifact(source, calibration, adapter_name, project, profile)
            for source in sources
        ]

    @staticmethod
    def _georeference(findings, frame: ThermalFrame, metadata: dict) -> None:
        if not findings or frame.transform is None or not frame.crs:
            return
        assigned = 0
        try:
            for finding in findings:
                map_x, map_y = pixel_to_map(
                    finding.center_x,
                    finding.center_y,
                    frame.transform,
                )
                lon, lat = transform_point(map_x, map_y, frame.crs)
                finding.longitude = float(lon)
                finding.latitude = float(lat)
                assigned += 1
        except (RuntimeError, ValueError) as exc:
            metadata.setdefault("warnings", []).append(str(exc))
            metadata["georeferencing_status"] = "not_authoritative"
            return
        metadata["georeferenced_findings"] = assigned
        metadata["georeferencing_status"] = "assigned"
