from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class DatasetRecord:
    dataset_id: str
    name: str
    source_paths: list[str] = field(default_factory=list)
    data_type: str = "thermal-radiometric"
    capture_time: str = ""
    sensor: str = ""
    image_count: int = 0
    size_bytes: int = 0
    radiometric_status: str = "unknown"
    gps_status: str = "unknown"
    processing_state: str = "not_processed"
    analysis_state: str = "not_analyzed"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Project:
    name: str
    site: str = ""
    client: str = ""
    operator: str = ""
    inspection_id: str = ""
    asset_type: str = ""
    location: str = ""
    inspection_date: str = field(default_factory=lambda: date.today().isoformat())
    sensor_vendor: str = ""
    sensor_model: str = ""
    report_title: str = "Thermal Inspection Report"
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    project_id: str = field(default_factory=lambda: uuid4().hex)
    description: str = ""
    profile_id: str = "generic-thermal"
    tags: list[str] = field(default_factory=list)
    datasets: list[DatasetRecord] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)
    exports: list[dict[str, Any]] = field(default_factory=list)
    modified_at: str = field(default_factory=_now)

    def touch(self) -> None:
        self.modified_at = _now()

    def add_dataset(
        self,
        sources: list[str | Path],
        *,
        name: str | None = None,
        data_type: str = "thermal-radiometric",
    ) -> DatasetRecord:
        paths = [Path(source) for source in sources]
        record = DatasetRecord(
            dataset_id=uuid4().hex,
            name=name or (paths[0].parent.name if paths else "Dataset"),
            source_paths=[str(path) for path in paths],
            data_type=data_type,
            image_count=len(paths),
            size_bytes=sum(path.stat().st_size for path in paths if path.is_file()),
        )
        self.datasets.append(record)
        self.touch()
        return record

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        destination.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Project:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        payload["datasets"] = [
            item if isinstance(item, DatasetRecord) else DatasetRecord(**item)
            for item in payload.get("datasets", [])
        ]
        return cls(**payload)

    def report_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(
            {
                "project_id": self.project_id,
                "name": self.name,
                "site": self.site,
                "client": self.client,
                "operator": self.operator,
                "inspection_id": self.inspection_id,
                "asset_type": self.asset_type,
                "location": self.location,
                "inspection_date": self.inspection_date,
                "sensor_vendor": self.sensor_vendor,
                "sensor_model": self.sensor_model,
                "report_title": self.report_title,
                "notes": self.notes,
                "description": self.description,
                "profile_id": self.profile_id,
            }
        )
        return payload
