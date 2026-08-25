from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MediaObservation:
    path: Path
    capture_time: str = ""
    latitude: float | None = None
    longitude: float | None = None
    sensor_role: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class MediaPair:
    thermal: MediaObservation
    visible: MediaObservation
    confidence: str
    time_difference_s: float | None
    distance_m: float | None
    rationale: tuple[str, ...]


def _time_difference_seconds(a: str, b: str) -> float | None:
    if not a or not b:
        return None
    try:
        left = datetime.fromisoformat(a.replace("Z", "+00:00"))
        right = datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return None
    return abs((left - right).total_seconds())


def _distance_m(a: MediaObservation, b: MediaObservation) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    lat1, lon1, lat2, lon2 = map(
        radians,
        (float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude)),
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6_371_008.8 * asin(sqrt(h))


def pair_thermal_visible(
    thermal: MediaObservation,
    candidates: list[MediaObservation],
    *,
    maximum_time_difference_s: float = 2.5,
    maximum_distance_m: float = 8.0,
) -> MediaPair | None:
    """Pair only when timestamp/GPS evidence supports the relationship."""

    ranked: list[tuple[float, MediaObservation, float | None, float | None, tuple[str, ...]]] = []
    for visible in candidates:
        time_delta = _time_difference_seconds(thermal.capture_time, visible.capture_time)
        distance = _distance_m(thermal, visible)
        reasons: list[str] = []
        score = 0.0
        if time_delta is not None and time_delta <= maximum_time_difference_s:
            score += 0.6 * (1.0 - time_delta / maximum_time_difference_s)
            reasons.append(f"capture time within {time_delta:.2f} s")
        if distance is not None and distance <= maximum_distance_m:
            score += 0.4 * (1.0 - distance / maximum_distance_m)
            reasons.append(f"GPS positions within {distance:.1f} m")
        if not reasons:
            continue
        ranked.append((score, visible, time_delta, distance, tuple(reasons)))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    score, visible, time_delta, distance, reasons = ranked[0]
    confidence = "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"
    return MediaPair(thermal, visible, confidence, time_delta, distance, reasons)
