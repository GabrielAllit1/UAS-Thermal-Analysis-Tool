from __future__ import annotations

import os
from pathlib import Path

from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter
from ..thermal.calibration import ThermalCalibration


class DjiDirpAdapter(ThermalSensorAdapter):
    """DJI DIRP integration boundary with local SDK discovery."""

    name = "dji-dirp"
    vendor = "DJI"
    support_level = "legacy-compatible"

    def sdk_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if configured := os.environ.get("UAS_THERMAL_DJI_SDK_DIR"):
            candidates.append(Path(configured))
        candidates.extend([Path.cwd(), Path(__file__).resolve().parents[3]])
        return candidates

    def sdk_library(self) -> Path | None:
        for directory in self.sdk_candidates():
            candidate = directory / "libdirp.dll"
            if candidate.is_file():
                return candidate
        return None

    def can_read(self, path: Path) -> bool:
        return path.suffix.lower() in {".jpg", ".jpeg"} and self.sdk_library() is not None

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        if self.sdk_library() is None:
            raise AdapterUnavailableError(
                "DJI DIRP runtime not found. Set UAS_THERMAL_DJI_SDK_DIR to the SDK binary directory."
            )
        raise AdapterUnavailableError(
            "DJI normalized ThermalFrame extraction is still being migrated; use the legacy desktop for DJI R-JPEG analysis in this release."
        )
