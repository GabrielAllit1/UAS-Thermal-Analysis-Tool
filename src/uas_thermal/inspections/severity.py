from __future__ import annotations

from dataclasses import dataclass

from .models import Severity


@dataclass(frozen=True, slots=True)
class SeverityPolicy:
    moderate_delta_c: float = 15.0
    critical_delta_c: float = 30.0

    def __post_init__(self) -> None:
        if self.moderate_delta_c <= 0:
            raise ValueError("moderate_delta_c must be positive")
        if self.critical_delta_c <= self.moderate_delta_c:
            raise ValueError("critical_delta_c must exceed moderate_delta_c")

    def classify(self, delta_c: float) -> Severity:
        if delta_c >= self.critical_delta_c:
            return Severity.CRITICAL
        if delta_c >= self.moderate_delta_c:
            return Severity.MODERATE
        return Severity.MINOR
