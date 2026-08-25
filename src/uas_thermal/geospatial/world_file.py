from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorldFile:
    x_pixel_size: float
    y_rotation: float
    x_rotation: float
    y_pixel_size: float
    x_center: float
    y_center: float

    @classmethod
    def load(cls, path: str | Path) -> WorldFile:
        values = [
            float(line.strip())
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(values) != 6:
            raise ValueError("world file must contain exactly six numeric lines")
        return cls(*values)

    def pixel_to_map(self, x: float, y: float) -> tuple[float, float]:
        map_x = self.x_center + x * self.x_pixel_size + y * self.x_rotation
        map_y = self.y_center + x * self.y_rotation + y * self.y_pixel_size
        return map_x, map_y
