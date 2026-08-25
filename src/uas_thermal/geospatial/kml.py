from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class KmlBounds:
    north: float
    south: float
    east: float
    west: float


def read_bounds(path: str | Path) -> KmlBounds | None:
    root = ET.parse(path).getroot()
    values: dict[str, float] = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"north", "south", "east", "west"} and element.text:
            try:
                values[tag] = float(element.text.strip())
            except ValueError:
                continue
    if all(key in values for key in ("north", "south", "east", "west")):
        return KmlBounds(values["north"], values["south"], values["east"], values["west"])
    return None
