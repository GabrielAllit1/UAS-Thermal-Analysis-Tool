from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..inspections.profiles import get_profile
from ..reporting.bundle import ReportBundle, write_report_bundle
from ..reporting.package import write_inspection_package
from ..thermal.calibration import ThermalCalibration
from .orchestrator import AutonomousInspectionOrchestrator, InspectionRun, ProcessingEvent
from .projects import Project
from .workflows import AnalysisArtifact, AnalysisWorkflow


@dataclass(slots=True)
class DesktopSession:
    workflow: AnalysisWorkflow = field(default_factory=AnalysisWorkflow.default)
    project: Project = field(default_factory=lambda: Project(name="Untitled inspection"))
    sources: list[Path] = field(default_factory=list)
    artifacts: list[AnalysisArtifact] = field(default_factory=list)
    last_run: InspectionRun | None = None

    def set_sources(self, sources: list[str | Path]) -> None:
        self.sources = [Path(source) for source in sources]
        self.artifacts.clear()
        self.last_run = None

    def analyze(
        self,
        calibration: ThermalCalibration,
        adapter_name: str | None = None,
    ) -> list[AnalysisArtifact]:
        """Compatibility path retained for existing callers."""

        if not self.sources:
            raise ValueError("Select at least one thermal source before analysis")
        self.artifacts = self.workflow.analyze_many(
            self.sources,
            calibration=calibration,
            adapter_name=adapter_name,
            project=self.project,
        )
        return self.artifacts

    def analyze_inspection(
        self,
        calibration: ThermalCalibration,
        *,
        adapter_name: str | None = None,
        profile_id: str | None = None,
        on_event=None,
        is_cancelled=None,
    ) -> InspectionRun:
        if not self.sources:
            raise ValueError("Add at least one thermal source before analysis")
        active_profile = get_profile(profile_id or self.project.profile_id)
        self.project.profile_id = active_profile.profile_id
        orchestrator = AutonomousInspectionOrchestrator(self.workflow)
        self.last_run = orchestrator.analyze_inspection(
            self.project,
            self.sources,
            calibration=calibration,
            adapter_name=adapter_name,
            profile=active_profile,
            on_event=on_event,
            is_cancelled=is_cancelled,
        )
        self.artifacts = list(self.last_run.artifacts)
        return self.last_run

    def export(self, output_dir: str | Path) -> list[ReportBundle]:
        if not self.artifacts:
            raise ValueError("Analyze thermal sources before exporting reports")
        return [
            write_report_bundle(
                artifact.result,
                output_dir,
                stem=Path(artifact.result.source).stem,
            )
            for artifact in self.artifacts
        ]

    def export_package(self, output_dir: str | Path) -> Path:
        if self.last_run is None or not self.last_run.artifacts:
            raise ValueError("Run Analyze Inspection before generating an inspection package")
        self.last_run.package_dir = write_inspection_package(self.last_run, output_dir)
        return self.last_run.package_dir


def launch() -> int:
    from .workspace_ui_v3 import launch_workspace

    return launch_workspace(DesktopSession())


__all__ = ["DesktopSession", "InspectionRun", "ProcessingEvent", "launch"]
