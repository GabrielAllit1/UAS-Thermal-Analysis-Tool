from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import asin, cos, radians, sin, sqrt

from .models import Finding


class ChangeState(StrEnum):
    NEW = "new"
    PERSISTED = "persisted"
    WORSENED = "worsened"
    IMPROVED = "improved"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class FindingChange:
    state: ChangeState
    current_id: str | None
    previous_id: str | None
    delta_t_change_c: float | None = None
    max_temperature_change_c: float | None = None


def _distance_m(a: Finding, b: Finding) -> float | None:
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


def compare_finding_sets(
    previous: list[Finding],
    current: list[Finding],
    *,
    maximum_match_distance_m: float = 3.0,
    material_delta_change_c: float = 3.0,
) -> list[FindingChange]:
    """Compare compatible geolocated findings without inventing cross-inspection identity."""

    unmatched_previous = set(range(len(previous)))
    changes: list[FindingChange] = []
    for item in current:
        candidates: list[tuple[float, int]] = []
        for index in unmatched_previous:
            prior = previous[index]
            distance = _distance_m(prior, item)
            if distance is None or distance > maximum_match_distance_m:
                continue
            if prior.classification != item.classification and prior.finding_type != item.finding_type:
                continue
            candidates.append((distance, index))
        if not candidates:
            changes.append(FindingChange(ChangeState.NEW, item.finding_id or None, None))
            continue
        _, index = min(candidates)
        unmatched_previous.remove(index)
        prior = previous[index]
        delta_change = item.delta_temperature_c - prior.delta_temperature_c
        max_change = item.max_temperature_c - prior.max_temperature_c
        if delta_change >= material_delta_change_c:
            state = ChangeState.WORSENED
        elif delta_change <= -material_delta_change_c:
            state = ChangeState.IMPROVED
        else:
            state = ChangeState.PERSISTED
        changes.append(
            FindingChange(
                state,
                item.finding_id or None,
                prior.finding_id or None,
                delta_change,
                max_change,
            )
        )
    for index in sorted(unmatched_previous):
        prior = previous[index]
        changes.append(FindingChange(ChangeState.RESOLVED, None, prior.finding_id or None))
    return changes
