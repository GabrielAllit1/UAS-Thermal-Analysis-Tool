from __future__ import annotations

from dataclasses import dataclass
from collections import deque

import numpy as np

from ..inspections.models import Finding
from ..inspections.severity import SeverityPolicy


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    minimum_delta_c: float = 8.0
    minimum_area_px: int = 25
    absolute_threshold_c: float | None = None
    connectivity: int = 8


def _components(mask: np.ndarray, connectivity: int) -> list[list[tuple[int, int]]]:
    rows, cols = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    if connectivity == 4:
        offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
    elif connectivity == 8:
        offsets = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
    else:
        raise ValueError("connectivity must be 4 or 8")

    found: list[list[tuple[int, int]]] = []
    for row, col in zip(*np.nonzero(mask)):
        if seen[row, col]:
            continue
        queue = deque([(int(row), int(col))])
        seen[row, col] = True
        component: list[tuple[int, int]] = []
        while queue:
            r, c = queue.popleft()
            component.append((r, c))
            for dr, dc in offsets:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    queue.append((nr, nc))
        found.append(component)
    return found


def detect_anomalies(
    temperature_c: np.ndarray,
    config: DetectionConfig = DetectionConfig(),
    severity_policy: SeverityPolicy = SeverityPolicy(),
) -> list[Finding]:
    values = np.asarray(temperature_c, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return []

    baseline = float(np.median(finite))
    threshold = baseline + config.minimum_delta_c
    if config.absolute_threshold_c is not None:
        threshold = max(threshold, config.absolute_threshold_c)

    mask = np.isfinite(values) & (values >= threshold)
    findings: list[Finding] = []
    for component in _components(mask, config.connectivity):
        if len(component) < config.minimum_area_px:
            continue
        rr = np.fromiter((r for r, _ in component), dtype=int)
        cc = np.fromiter((c for _, c in component), dtype=int)
        temps = values[rr, cc]
        max_temp = float(np.max(temps))
        delta = max_temp - baseline
        severity = severity_policy.classify(delta)
        findings.append(
            Finding(
                center_x=int(round(float(np.mean(cc)))),
                center_y=int(round(float(np.mean(rr)))),
                area_px=len(component),
                max_temperature_c=max_temp,
                mean_temperature_c=float(np.mean(temps)),
                baseline_temperature_c=baseline,
                delta_temperature_c=delta,
                severity=severity,
                finding_type="Thermal anomaly",
            )
        )
    findings.sort(key=lambda item: item.delta_temperature_c, reverse=True)
    return findings
