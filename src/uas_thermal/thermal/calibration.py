from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThermalCalibration:
    emissivity: float = 0.95
    distance_m: float = 5.0
    relative_humidity: float = 0.50
    reflected_temperature_c: float = 20.0

    def __post_init__(self) -> None:
        if not 0.1 <= self.emissivity <= 1.0:
            raise ValueError("emissivity must be between 0.1 and 1.0")
        if not 0.0 < self.distance_m <= 10000.0:
            raise ValueError("distance_m must be greater than 0")
        if not 0.0 <= self.relative_humidity <= 1.0:
            raise ValueError("relative_humidity must be between 0.0 and 1.0")
        if not -100.0 <= self.reflected_temperature_c <= 1000.0:
            raise ValueError("reflected_temperature_c is outside supported bounds")
