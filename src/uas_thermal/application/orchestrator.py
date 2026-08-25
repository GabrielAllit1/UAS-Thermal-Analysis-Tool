from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from ..inspections.deduplication import deduplicate_findings
from ..inspections.models import Finding, InspectionSummary
from ..inspections.profiles import InspectionProfile, get_profile
from ..thermal.calibration import ThermalCalibration
from .projects import Project
from .workflows import AnalysisArtifact, AnalysisWorkflow


class ProcessingStage(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    EXTRACTING_RADIOMETRY = "extracting_radiometry"
    DETECTING = "detecting"
    CHARACTERIZING = "characterizing"
    GEOLOCATING = "geolocating"
    DEDUPLICATING = "deduplicating"
    RENDERING = "rendering"
    GENERATING_REPORT = "generating_report"
    VERIFYING_OUTPUT = "verifying_output"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class ProcessingEvent:
    stage: ProcessingStage
    message: str
    completed: int = 0
    total: int = 0
    source: str = ""


@dataclass(frozen=True, slots=True)
class SourceFailure:
    source: str
    error_type: str
    error: str


@dataclass(slots=True)
class InspectionRun:
    project: Project
    profile: InspectionProfile
    artifacts: list[AnalysisArtifact] = field(default_factory=list)
    canonical_findings: list[Finding] = field(default_factory=list)
    failures: list[SourceFailure] = field(default_factory=list)
    summary: InspectionSummary = field(default_factory=InspectionSummary)
    events: list[ProcessingEvent] = field(default_factory=list)
    package_dir: Path | None = None
    status: ProcessingStage = ProcessingStage.QUEUED

    def as_dict(self) -> dict[str, object]:
        return {
            "project": self.project.report_metadata(),
            "profile": self.profile.as_dict(),
            "status": self.status.value,
            "summary": asdict(self.summary),
            "failures": [asdict(item) for item in self.failures],
            "canonical_finding_ids": [item.finding_id for item in self.canonical_findings],
            "package_dir": None if self.package_dir is None else str(self.package_dir),
        }


class AutonomousInspectionOrchestrator:
    """Single production authority for dataset -> canonical findings -> deliverables."""

    def __init__(self, workflow: AnalysisWorkflow | None = None):
        self.workflow = workflow or AnalysisWorkflow.default()

    def analyze_inspection(
        self,
        project: Project,
        sources: list[str | Path],
        *,
        calibration: ThermalCalibration | None = None,
        adapter_name: str | None = None,
        profile: InspectionProfile | None = None,
        output_dir: str | Path | None = None,
        on_event: Callable[[ProcessingEvent], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> InspectionRun:
        active_profile = profile or get_profile(project.profile_id)
        calibration = calibration or ThermalCalibration()
        run = InspectionRun(project=project, profile=active_profile)
        total = len(sources)

        def emit(
            stage: ProcessingStage,
            message: str,
            completed: int = 0,
            source: str = "",
        ) -> None:
            run.status = stage
            event = ProcessingEvent(stage, message, completed, total, source)
            run.events.append(event)
            if on_event:
                on_event(event)

        emit(ProcessingStage.QUEUED, f"Queued {total} source(s)")
        if not sources:
            emit(ProcessingStage.FAILED, "No thermal sources were supplied")
            return run

        canceled = False
        for index, source in enumerate(sources, 1):
            if is_cancelled and is_cancelled():
                canceled = True
                emit(ProcessingStage.CANCELED, "Inspection analysis canceled", index - 1)
                break
            source_path = Path(source)
            emit(
                ProcessingStage.VALIDATING,
                "Validating radiometric source",
                index - 1,
                str(source_path),
            )
            emit(
                ProcessingStage.EXTRACTING_RADIOMETRY,
                "Extracting normalized temperature data",
                index - 1,
                str(source_path),
            )
            try:
                emit(
                    ProcessingStage.DETECTING,
                    "Detecting contextual thermal candidates",
                    index - 1,
                    str(source_path),
                )
                artifact = self.workflow.analyze_artifact(
                    source_path,
                    calibration=calibration,
                    adapter_name=adapter_name,
                    project=project,
                    profile=active_profile,
                )
            except Exception as exc:
                run.failures.append(
                    SourceFailure(str(source_path), type(exc).__name__, str(exc))
                )
                continue
            emit(
                ProcessingStage.CHARACTERIZING,
                "Characterizing accepted findings",
                index,
                str(source_path),
            )
            for finding_index, finding in enumerate(artifact.result.findings, 1):
                observation_id = f"OBS-{index:05d}-{finding_index:03d}"
                finding.finding_id = observation_id
                finding.canonical_finding_id = ""
                finding.supporting_observations = [observation_id]
            run.artifacts.append(artifact)

        observations = [
            finding
            for artifact in run.artifacts
            for finding in artifact.result.findings
        ]
        if observations:
            emit(
                ProcessingStage.GEOLOCATING,
                "Geospatial evidence assigned where source authority permits",
                len(run.artifacts),
            )
            emit(
                ProcessingStage.DEDUPLICATING,
                "Clustering probable cross-frame duplicates",
                len(run.artifacts),
            )
            run.canonical_findings = deduplicate_findings(observations)

        for finding in run.canonical_findings:
            finding.inspection_id = project.inspection_id
            finding.project_id = project.project_id

        run.summary = InspectionSummary(
            images_discovered=total,
            images_accepted=len(run.artifacts),
            images_warned=sum(
                bool(artifact.result.quality.get("warnings"))
                for artifact in run.artifacts
            ),
            images_rejected=len(run.failures),
            observations=len(observations),
            canonical_findings=len(run.canonical_findings),
            critical=sum(
                item.severity.value == "critical" for item in run.canonical_findings
            ),
            moderate=sum(
                item.severity.value == "moderate" for item in run.canonical_findings
            ),
            minor=sum(item.severity.value == "minor" for item in run.canonical_findings),
            highest_temperature_c=max(
                (item.max_temperature_c for item in run.canonical_findings),
                default=None,
            ),
            highest_delta_c=max(
                (item.delta_temperature_c for item in run.canonical_findings),
                default=None,
            ),
        )

        if canceled:
            run.status = ProcessingStage.CANCELED
            return run

        if output_dir is not None and run.artifacts:
            emit(
                ProcessingStage.RENDERING,
                "Rendering finding annotations and evidence plates",
                len(run.artifacts),
            )
            from ..reporting.package import write_inspection_package

            emit(
                ProcessingStage.GENERATING_REPORT,
                "Generating inspection deliverables",
                len(run.artifacts),
            )
            run.package_dir = write_inspection_package(run, output_dir)
            emit(
                ProcessingStage.VERIFYING_OUTPUT,
                "Verifying output manifest and checksums",
                len(run.artifacts),
            )

        emit(
            ProcessingStage.COMPLETE,
            (
                f"Inspection complete: {len(run.canonical_findings)} canonical finding(s), "
                f"{len(run.failures)} rejected source(s)"
            ),
            len(run.artifacts),
        )
        return run
