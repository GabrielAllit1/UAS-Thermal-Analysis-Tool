from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    data_dir: Path
    log_level: str = "INFO"
    dji_sdk_dir: Path | None = None

    @classmethod
    def from_env(cls) -> AppConfig:
        data = Path(os.environ.get("UAS_THERMAL_DATA_DIR", Path.home() / ".uas-thermal"))
        sdk = os.environ.get("UAS_THERMAL_DJI_SDK_DIR")
        return cls(
            data_dir=data,
            log_level=os.environ.get("UAS_THERMAL_LOG_LEVEL", "INFO"),
            dji_sdk_dir=Path(sdk) if sdk else None,
        )
