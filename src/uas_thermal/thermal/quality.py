from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from ..inspections.models import QualityStatus
from ..sensors.base import ThermalFrame
from .calibration import ThermalCalibration


@dataclass(slots=True)
class QualityAssessment:
    status: QualityStatus
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float | int | str | bool | None] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status is not QualityStatus.REJECTED

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["accepted"] = self.accepted
        return payload


def evaluate_radiometric_quality(
    frame: ThermalFrame,
    calibration: ThermalCalibration | None = None,
    *,
    minimum_valid_fraction: float = 0.70,
    plausible_range_c: tuple[float, float] = (-80.0, 1000.0),
) -> QualityAssessment:
    """Fail closed before quantitative anomaly analysis.

    The gate intentionally validates evidence that can be inferred from the normalized frame;
    it does not claim calibration accuracy that the source metadata cannot prove.
    """

    values = np.asarray(frame.temperature_c, dtype=np.float32)
    reasons: list[str] = []
    warnings: list[str] = []
    metadata = frame.metadata or {}
    tags = metadata.get("tags") if isinstance(metadata.get("tags"), dict) else {}

    if values.ndim != 2 or min(values.shape, default=0) <= 0:
        return QualityAssessment(QualityStatus.REJECTED, ["invalid temperature dimensions"])

    finite = np.isfinite(values)
    valid_count = int(np.count_nonzero(finite))
    total = int(values.size)
    valid_fraction = valid_count / total if total else 0.0
    if valid_count == 0:
        reasons.append("no finite temperature samples")
    elif valid_fraction < minimum_valid_fraction:
        reasons.append(f"valid temperature coverage {valid_fraction:.1%} is below required {minimum_valid_fraction:.0%}")

    if str(tags.get("isCalibrated", metadata.get("is_calibrated", ""))).strip().lower() == "false":
        reasons.append("source metadata declares radiometry uncalibrated")
    if metadata.get("radiometric_candidate") is False:
        reasons.append("source adapter classified input as non-radiometric")

    minimum = maximum = dynamic_range = None
    clipped_fraction = 0.0
    if valid_count:
        samples = values[finite]
        minimum = float(np.min(samples))
        maximum = float(np.max(samples))
        dynamic_range = maximum - minimum
        low, high = plausible_range_c
        implausible = int(np.count_nonzero((samples < low) | (samples > high)))
        if implausible:
            reasons.append(f"{implausible} temperature samples are outside the supported plausibility range")
        min_count = int(np.count_nonzero(samples == minimum))
        max_count = int(np.count_nonzero(samples == maximum))
        clipped_fraction = max(min_count, max_count) / valid_count
        if clipped_fraction > 0.20:
            warnings.append("large fraction of pixels share an extreme value; clipping or saturation is possible")
        if dynamic_range < 0.05:
            warnings.append("temperature dynamic range is extremely small")

    if calibration is None:
        warnings.append("explicit analysis calibration parameters were not supplied")
    else:
        # ThermalCalibration validates numeric bounds. Here we retain the values as provenance.
        if calibration.emissivity == 0.95:
            warnings.append("emissivity is using the generic default; verify it for the inspected surface")

    if not frame.crs or frame.transform is None:
        warnings.append("source is not fully georeferenced; geographic finding export may be unavailable")
    if not metadata.get("capture_time") and not metadata.get("timestamp"):
        warnings.append("capture timestamp was not established from source metadata")

    status = QualityStatus.REJECTED if reasons else (
        QualityStatus.PASS_WITH_WARNINGS if warnings else QualityStatus.PASS
    )
    return QualityAssessment(
        status=status,
        reasons=reasons,
        warnings=warnings,
        metrics={
            "width": int(values.shape[1]),
            "height": int(values.shape[0]),
            "total_pixels": total,
            "valid_pixels": valid_count,
            "valid_fraction": round(valid_fraction, 6),
            "minimum_c": minimum,
            "maximum_c": maximum,
            "dynamic_range_c": dynamic_range,
            "extreme_value_fraction": round(float(clipped_fraction), 6),
        },
    )
