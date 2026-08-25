from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class OrthomosaicRequest:
    sources: tuple[Path, ...]
    output_dir: Path
    project_name: str = "thermal-project"
    calibration_mode: str = "camera"
    target_crs: str | None = None
    resolution: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("orthomosaic request requires at least one source")


@dataclass(frozen=True, slots=True)
class OrthomosaicResult:
    orthomosaic: Path
    backend: str
    quantitative: bool
    temperature_unit: str | None = None
    source_count: int = 0
    processing_report: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OrthomosaicBackend(ABC):
    name = "orthomosaic"

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def can_process(self, request: OrthomosaicRequest) -> bool:
        raise NotImplementedError

    @abstractmethod
    def process(self, request: OrthomosaicRequest) -> OrthomosaicResult:
        raise NotImplementedError
