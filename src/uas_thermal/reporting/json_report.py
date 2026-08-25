from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

from ..inspections.models import Finding, InspectionResult


def _json_default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def finding_payload(finding: Finding) -> dict[str, Any]:
    return json.loads(json.dumps(asdict(finding), default=_json_default))


def write_json(result: InspectionResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": result.source,
        "adapter": result.adapter,
        "statistics": asdict(result.statistics),
        "project": result.project,
        "metadata": result.metadata,
        "quality": result.quality,
        "profile": result.profile,
        "summary": None if result.summary is None else asdict(result.summary),
        "findings": [finding_payload(item) for item in result.findings],
        "suppressions": [asdict(item) for item in result.suppressions],
    }
    destination.write_text(
        json.dumps(payload, indent=2, default=_json_default, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def write_findings_json(
    findings: list[Finding],
    path: str | Path,
    *,
    project: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project": project or {},
        "summary": summary or {},
        "findings": [finding_payload(item) for item in findings],
    }
    destination.write_text(
        json.dumps(payload, indent=2, default=_json_default, sort_keys=True),
        encoding="utf-8",
    )
    return destination
