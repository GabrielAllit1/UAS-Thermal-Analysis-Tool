from pathlib import Path

from .base import AdapterUnavailableError, ThermalFrame, ThermalSensorAdapter
from ..thermal.calibration import ThermalCalibration


class AutelAdapter(ThermalSensorAdapter):
    name = "autel"
    vendor = "Autel"
    support_level = "contract-only"

    def can_read(self, path: Path) -> bool:
        return False

    def read(self, path: Path, calibration: ThermalCalibration) -> ThermalFrame:
        raise AdapterUnavailableError("Autel radiometric decoding is not implemented in this release")
