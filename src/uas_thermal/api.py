from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from .application.orchestrator import (
    AutonomousInspectionOrchestrator,
    InspectionRun,
    ProcessingEvent,
)
from .application.projects import Project
from .inspections.profiles import get_profile
from .thermal.calibration import ThermalCalibration


def run_inspection(
    sources: Sequence[str | Path],
    output_dir: str | Path,
    *,
    project: Project | None = None,
    project_name: str = "Thermal Inspection",
    profile_id: str | None = None,
    calibration: ThermalCalibration | None = None,
    adapter_name: str | None = None,
    on_event: Callable[[ProcessingEvent], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> InspectionRun:
    """Stable public facade for the canonical autonomous inspection path.

    This function intentionally delegates every quantitative operation to
    ``AutonomousInspectionOrchestrator`` rather than creating a second analysis path.
    """

    active_project = project or Project(name=project_name)
    if profile_id is not None:
        active_project.profile_id = profile_id
    active_profile = get_profile(active_project.profile_id)
    return AutonomousInspectionOrchestrator().analyze_inspection(
        active_project,
        [Path(source) for source in sources],
        calibration=calibration,
        adapter_name=adapter_name,
        profile=active_profile,
        output_dir=output_dir,
        on_event=on_event,
        is_cancelled=is_cancelled,
    )
