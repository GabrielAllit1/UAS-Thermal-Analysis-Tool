from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..inspections.models import Finding, FindingStatus
from .orchestrator import ProcessingStage
from .projects import Project


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ProcessingJob:
    job_id: str
    project_id: str
    dataset_id: str = ""
    stage: ProcessingStage = ProcessingStage.QUEUED
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def progress_fraction(self) -> float | None:
        if self.progress_total <= 0:
            return None
        return min(1.0, max(0.0, self.progress_current / self.progress_total))


@dataclass(slots=True)
class SelectionState:
    selected_dataset_id: str = ""
    selected_source: str = ""
    selected_finding_id: str = ""
    selected_layer: str = ""

    def select_finding(self, finding: Finding) -> None:
        self.selected_finding_id = finding.finding_id
        self.selected_source = finding.source_path

    def clear(self) -> None:
        self.selected_dataset_id = ""
        self.selected_source = ""
        self.selected_finding_id = ""
        self.selected_layer = ""


@dataclass(frozen=True, slots=True)
class AnalyticsSnapshot:
    projects: int
    datasets: int
    findings: int
    critical_findings: int
    action_required: int
    rejected_sources: int


def summarize_workspace(
    projects: list[Project],
    findings: list[Finding],
    *,
    rejected_sources: int = 0,
) -> AnalyticsSnapshot:
    return AnalyticsSnapshot(
        projects=len(projects),
        datasets=sum(len(project.datasets) for project in projects),
        findings=len(findings),
        critical_findings=sum(item.severity.value == "critical" for item in findings),
        action_required=sum(item.lifecycle_status is FindingStatus.ACTION_REQUIRED for item in findings),
        rejected_sources=rejected_sources,
    )


class ProjectCatalog:
    """Filesystem-backed project index; removing an entry never deletes source survey data."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def project_path(self, project: Project) -> Path:
        return self.root / f"{project.project_id}.uasproject.json"

    def save(self, project: Project) -> Path:
        return project.save(self.project_path(project))

    def list_projects(self) -> list[tuple[Project, Path]]:
        projects: list[tuple[Project, Path]] = []
        for path in self.root.glob("*.uasproject.json"):
            try:
                projects.append((Project.load(path), path))
            except (OSError, ValueError, TypeError):
                continue
        projects.sort(key=lambda item: item[0].modified_at, reverse=True)
        return projects

    def search(
        self,
        query: str = "",
        *,
        profile_id: str = "",
        client: str = "",
    ) -> list[tuple[Project, Path]]:
        query_lower = query.strip().lower()
        results = []
        for project, path in self.list_projects():
            haystack = " ".join(
                [project.name, project.site, project.client, project.location, *project.tags]
            ).lower()
            if query_lower and query_lower not in haystack:
                continue
            if profile_id and project.profile_id != profile_id:
                continue
            if client and project.client.lower() != client.lower():
                continue
            results.append((project, path))
        return results


def finding_details(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.finding_id,
        "classification": finding.classification or finding.finding_type,
        "severity": finding.severity.value,
        "confidence": finding.confidence.value,
        "max_temperature_c": finding.max_temperature_c,
        "reference_temperature_c": finding.reference_temperature_c,
        "delta_temperature_c": finding.delta_temperature_c,
        "location": (
            None
            if finding.latitude is None or finding.longitude is None
            else [finding.latitude, finding.longitude]
        ),
        "source": finding.source_path,
        "evidence": list(finding.evidence),
        "recommendation": finding.recommendation,
        "status": finding.lifecycle_status.value,
    }
