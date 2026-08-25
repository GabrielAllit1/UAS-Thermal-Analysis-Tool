from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .autel import AutelAdapter
from .base import ThermalSensorAdapter
from .dji import DjiDirpAdapter
from .flir import FlirTeledyneAdapter
from .generic import GenericGeoTiffAdapter


@dataclass(slots=True)
class AdapterRegistry:
    adapters: list[ThermalSensorAdapter] = field(default_factory=list)

    def register(self, adapter: ThermalSensorAdapter) -> None:
        if any(existing.name == adapter.name for existing in self.adapters):
            raise ValueError(f"adapter already registered: {adapter.name}")
        self.adapters.append(adapter)

    def select(self, path: str | Path, preferred: str | None = None) -> ThermalSensorAdapter:
        source = Path(path)
        if preferred:
            for adapter in self.adapters:
                if adapter.name == preferred:
                    if not adapter.can_read(source):
                        raise ValueError(f"adapter {preferred!r} cannot read {source.name}")
                    return adapter
            raise LookupError(f"unknown adapter: {preferred}")
        for adapter in self.adapters:
            if adapter.can_read(source):
                return adapter
        raise LookupError(f"no registered thermal adapter can read {source.name}")


def default_registry() -> AdapterRegistry:
    return AdapterRegistry([
        GenericGeoTiffAdapter(),
        DjiDirpAdapter(),
        FlirTeledyneAdapter(),
        AutelAdapter(),
    ])
