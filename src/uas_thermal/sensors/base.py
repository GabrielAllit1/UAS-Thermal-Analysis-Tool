from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..thermal.calibration import ThermalCalibration


class AdapterUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class ThermalFrame:
    temperature_c: np.ndarray
    source: Path
    display_rgb: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    crs: str | None = None
    transform: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if self.temperature_c.ndim != 2:
            raise ValueError("temperature_c must be a two-dimensional matrix")
        if self.display_rgb is not None:
            if self.display_rgb.ndim != 3 or self.display_rgb.shape[2] != 3:
                raise ValueError("display_rgb must be an HxWx3 array")
            if self.display_rgb.shape[:2] != self.temperature_c.shape:
                raise ValueError("display_rgb dimensions must match temperature_c")


class ThermalSensorAdapter(ABC):
    name = "unknown"
    vendor = "generic"
    support_level = "experimental"

    @abstractmethod
    def can_read(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        raise NotImplementedError

    def describe(self) -> dict[str, str]:
        return {"name": self.name, "vendor": self.vendor, "support_level": self.support_level}
