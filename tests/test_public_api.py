from pathlib import Path

from uas_thermal import api
from uas_thermal.application.projects import Project


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    def analyze_inspection(self, project, sources, **kwargs):
        self.calls.append((project, sources, kwargs))
        return {"project": project, "sources": sources, "kwargs": kwargs}


def test_run_inspection_delegates_to_canonical_orchestrator(monkeypatch, tmp_path):
    fake = FakeOrchestrator()
    monkeypatch.setattr(api, "AutonomousInspectionOrchestrator", lambda: fake)
    project = Project(name="SDK Proof", profile_id="photovoltaic")

    result = api.run_inspection(
        ["one.tif", "two.tif"],
        tmp_path,
        project=project,
    )

    assert result["project"] is project
    assert result["sources"] == [Path("one.tif"), Path("two.tif")]
    assert result["kwargs"]["output_dir"] == tmp_path
    assert result["kwargs"]["profile"].profile_id == "photovoltaic"
