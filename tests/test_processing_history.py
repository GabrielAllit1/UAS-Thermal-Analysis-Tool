from uas_thermal.application.orchestrator import (
    InspectionRun,
    ProcessingEvent,
    ProcessingStage,
)
from uas_thermal.application.processing import ProcessingHistoryRecord, ProcessingHistoryStore
from uas_thermal.application.projects import Project
from uas_thermal.inspections.models import InspectionSummary
from uas_thermal.inspections.profiles import get_profile


def test_processing_history_round_trip(tmp_path):
    project = Project(name="History test")
    run = InspectionRun(project=project, profile=get_profile("generic-thermal"))
    run.summary = InspectionSummary(
        images_discovered=3,
        images_accepted=2,
        images_rejected=1,
        canonical_findings=4,
        critical=1,
    )
    run.events.append(ProcessingEvent(ProcessingStage.QUEUED, "queued", 0, 3))
    run.events.append(ProcessingEvent(ProcessingStage.COMPLETE, "done", 2, 3))

    record = ProcessingHistoryRecord.from_run(
        run,
        started_at="2026-08-25T12:00:00+00:00",
        finished_at="2026-08-25T12:01:00+00:00",
    )
    store = ProcessingHistoryStore(tmp_path)
    store.save(record)

    loaded = store.list_records(project_id=project.project_id)
    assert len(loaded) == 1
    assert loaded[0].status == "complete"
    assert loaded[0].canonical_findings == 4
    assert loaded[0].events[-1]["stage"] == "complete"
