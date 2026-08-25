from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


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
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Project:
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def report_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload.update(
            {
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
            }
        )
        return payload
