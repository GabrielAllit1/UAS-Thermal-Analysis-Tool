from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

from ..platform.config import AppConfig
from .orchestrator import InspectionRun, ProcessingEvent, ProcessingStage


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ProcessingHistoryRecord:
    run_id: str
    project_id: str
    project_name: str
    started_at: str
    finished_at: str
    status: str
    source_count: int
    accepted_sources: int
    rejected_sources: int
    canonical_findings: int
    critical_findings: int
    package_dir: str = ""
    events: list[dict[str, object]] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_run(
        cls,
        run: InspectionRun,
        *,
        started_at: str,
        finished_at: str | None = None,
    ) -> ProcessingHistoryRecord:
        terminal = run.events[-1].stage if run.events else ProcessingStage.FAILED
        return cls(
            run_id=uuid4().hex,
            project_id=run.project.project_id,
            project_name=run.project.name,
            started_at=started_at,
            finished_at=finished_at or _now(),
            status=terminal.value,
            source_count=run.summary.images_discovered,
            accepted_sources=run.summary.images_accepted,
            rejected_sources=run.summary.images_rejected,
            canonical_findings=run.summary.canonical_findings,
            critical_findings=run.summary.critical,
            package_dir="" if run.package_dir is None else str(run.package_dir),
            events=[_event_payload(event) for event in run.events],
            failures=[asdict(item) for item in run.failures],
        )


def _event_payload(event: ProcessingEvent) -> dict[str, object]:
    payload = asdict(event)
    payload["stage"] = event.stage.value
    return payload


class ProcessingHistoryStore:
    """Append-only JSON record store for completed, failed, and canceled processing runs."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default(cls) -> ProcessingHistoryStore:
        return cls(AppConfig.from_env().data_dir / "processing-history")

    def _path(self, record: ProcessingHistoryRecord) -> Path:
        return self.root / f"{record.finished_at[:10]}-{record.run_id}.json"

    def save(self, record: ProcessingHistoryRecord) -> Path:
        destination = self._path(record)
        destination.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
        return destination

    def list_records(
        self,
        *,
        project_id: str = "",
        limit: int | None = 250,
    ) -> list[ProcessingHistoryRecord]:
        records: list[ProcessingHistoryRecord] = []
        for path in self.root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = ProcessingHistoryRecord(**payload)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if project_id and record.project_id != project_id:
                continue
            records.append(record)
        records.sort(key=lambda item: item.finished_at, reverse=True)
        return records if limit is None else records[: max(0, limit)]

    def get(self, run_id: str) -> ProcessingHistoryRecord | None:
        for record in self.list_records(limit=None):
            if record.run_id == run_id:
                return record
        return None
