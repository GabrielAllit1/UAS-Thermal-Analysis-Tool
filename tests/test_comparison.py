from uas_thermal.inspections.comparison import ChangeState, compare_finding_sets
from uas_thermal.inspections.models import Finding, Severity


def _finding(identifier, lat, lon, delta):
    return Finding(
        10,
        10,
        25,
        50.0 + delta,
        45.0,
        50.0,
        delta,
        Severity.MODERATE,
        finding_id=identifier,
        classification="Thermal anomaly",
        latitude=lat,
        longitude=lon,
    )


def test_compare_marks_worsened_and_resolved_findings():
    previous = [
        _finding("A-001", 28.0, -82.0, 10.0),
        _finding("A-002", 28.01, -82.01, 15.0),
    ]
    current = [_finding("A-101", 28.00001, -82.00001, 18.0)]
    changes = compare_finding_sets(previous, current)
    states = {item.state for item in changes}
    assert ChangeState.WORSENED in states
    assert ChangeState.RESOLVED in states


def test_compare_does_not_quantitatively_match_unlocated_findings():
    previous = [_finding("A-001", None, None, 10.0)]
    current = [_finding("A-101", None, None, 11.0)]
    changes = compare_finding_sets(previous, current)
    assert {item.state for item in changes} == {ChangeState.NEW, ChangeState.RESOLVED}
