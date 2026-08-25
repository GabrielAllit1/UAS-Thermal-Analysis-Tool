from uas_thermal.inspections.deduplication import deduplicate_findings
from uas_thermal.inspections.models import Confidence, Finding, Severity


def _finding(identifier, lat, lon, delta=20.0, max_temp=50.0):
    return Finding(
        10,
        10,
        30,
        max_temp,
        45.0,
        max_temp - delta,
        delta,
        Severity.MODERATE,
        finding_id=identifier,
        classification="Thermal anomaly",
        latitude=lat,
        longitude=lon,
        confidence=Confidence.MEDIUM,
        evidence=["local thermal contrast"],
    )


def test_nearby_compatible_observations_cluster_and_preserve_provenance():
    first = _finding("OBS-1", 28.000000, -82.000000)
    second = _finding("OBS-2", 28.000010, -82.000010, delta=21.0)
    findings = deduplicate_findings([first, second])
    assert len(findings) == 1
    assert findings[0].duplicate_cluster_id == "D-001"
    assert set(findings[0].supporting_observations) == {"OBS-1", "OBS-2"}


def test_findings_without_geographic_evidence_are_not_overmerged():
    first = _finding("OBS-1", None, None)
    second = _finding("OBS-2", None, None)
    findings = deduplicate_findings([first, second])
    assert len(findings) == 2


def test_nearby_but_thermally_incompatible_findings_remain_separate():
    first = _finding("OBS-1", 28.000000, -82.000000, delta=10.0, max_temp=40.0)
    second = _finding("OBS-2", 28.000010, -82.000010, delta=35.0, max_temp=70.0)
    findings = deduplicate_findings([first, second])
    assert len(findings) == 2
