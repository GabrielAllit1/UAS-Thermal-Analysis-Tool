from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from .models import Confidence, Finding


@dataclass(frozen=True, slots=True)
class DeduplicationConfig:
    maximum_distance_m: float = 3.0
    maximum_delta_difference_c: float = 8.0
    maximum_temperature_difference_c: float = 12.0


def _distance_m(a: Finding, b: Finding) -> float | None:
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    lat1, lon1, lat2, lon2 = map(
        radians,
        (float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude)),
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6_371_008.8 * asin(sqrt(value))


def _compatible(a: Finding, b: Finding, config: DeduplicationConfig) -> bool:
    distance = _distance_m(a, b)
    if distance is None or distance > config.maximum_distance_m:
        return False
    if abs(a.delta_temperature_c - b.delta_temperature_c) > config.maximum_delta_difference_c:
        return False
    if abs(a.max_temperature_c - b.max_temperature_c) > config.maximum_temperature_difference_c:
        return False
    return a.classification == b.classification or a.finding_type == b.finding_type


def deduplicate_findings(
    observations: list[Finding],
    config: DeduplicationConfig | None = None,
) -> list[Finding]:
    """Cluster probable duplicate observations without discarding provenance.

    Findings lacking geographic evidence are intentionally kept separate because image-space
    proximity alone is not proof that two frames observe the same physical condition.
    """

    config = config or DeduplicationConfig()
    clusters: list[list[Finding]] = []
    for observation in observations:
        for cluster in clusters:
            if any(_compatible(observation, member, config) for member in cluster):
                cluster.append(observation)
                break
        else:
            clusters.append([observation])

    canonical: list[Finding] = []
    for cluster_index, cluster in enumerate(clusters, 1):
        strongest = max(
            cluster,
            key=lambda item: (item.delta_temperature_c, item.max_temperature_c, item.area_px),
        )
        item = deepcopy(strongest)
        item.finding_id = f"A-{cluster_index:03d}"
        item.canonical_finding_id = item.finding_id
        item.duplicate_cluster_id = f"D-{cluster_index:03d}" if len(cluster) > 1 else ""
        observation_ids = [member.finding_id or member.source_image_id for member in cluster]
        item.supporting_observations = [value for value in observation_ids if value]
        if len(cluster) > 1:
            item.evidence = [*item.evidence, f"corroborated by {len(cluster)} geospatially compatible observations"]
            if item.confidence is Confidence.LOW:
                item.confidence = Confidence.MEDIUM
            elif item.confidence is Confidence.MEDIUM and len(cluster) >= 3:
                item.confidence = Confidence.HIGH
            item.confidence_components = {
                **item.confidence_components,
                "cross_frame_corroboration": len(cluster),
            }
        canonical.append(item)
    return canonical
