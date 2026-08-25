from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


_PALETTES: dict[str, tuple[tuple[float, tuple[int, int, int]], ...]] = {
    "whitehot": ((0.0, (0, 0, 0)), (1.0, (255, 255, 255))),
    "gray": ((0.0, (0, 0, 0)), (1.0, (255, 255, 255))),
    "blackhot": ((0.0, (255, 255, 255)), (1.0, (0, 0, 0))),
    "iron": (
        (0.0, (0, 0, 0)),
        (0.20, (55, 0, 100)),
        (0.45, (185, 25, 30)),
        (0.72, (255, 145, 20)),
        (1.0, (255, 255, 235)),
    ),
    "ironbow": (
        (0.0, (0, 0, 0)),
        (0.20, (55, 0, 100)),
        (0.45, (185, 25, 30)),
        (0.72, (255, 145, 20)),
        (1.0, (255, 255, 235)),
    ),
    "arctic": (
        (0.0, (0, 20, 80)),
        (0.35, (0, 150, 220)),
        (0.65, (180, 240, 255)),
        (1.0, (255, 255, 255)),
    ),
    "rainbow": (
        (0.0, (0, 0, 100)),
        (0.20, (0, 80, 255)),
        (0.40, (0, 220, 200)),
        (0.60, (220, 240, 0)),
        (0.80, (255, 100, 0)),
        (1.0, (180, 0, 0)),
    ),
    "rainbow-hc": (
        (0.0, (0, 0, 90)),
        (0.10, (0, 0, 255)),
        (0.25, (0, 200, 255)),
        (0.40, (0, 255, 100)),
        (0.55, (255, 255, 0)),
        (0.70, (255, 120, 0)),
        (0.85, (255, 0, 0)),
        (1.0, (255, 255, 255)),
    ),
}


@dataclass(frozen=True, slots=True)
class ThermalStyle:
    """Visual presentation parameters; never a quantitative calibration authority."""

    palette: str = "ironbow"
    span_c: float | None = None
    level_c: float | None = None
    minimum_c: float | None = None
    maximum_c: float | None = None
    isotherm_min_c: float | None = None
    isotherm_max_c: float | None = None

    def __post_init__(self) -> None:
        key = self.palette.strip().lower()
        if key not in _PALETTES:
            raise ValueError(f"unsupported palette: {self.palette!r}")
        if (self.span_c is None) != (self.level_c is None):
            raise ValueError("span_c and level_c must be supplied together")
        if self.span_c is not None and self.span_c <= 0:
            raise ValueError("span_c must be positive")
        if self.minimum_c is not None and self.maximum_c is not None:
            if self.maximum_c <= self.minimum_c:
                raise ValueError("maximum_c must exceed minimum_c")

    def limits(self) -> tuple[float | None, float | None]:
        if self.span_c is not None and self.level_c is not None:
            half = self.span_c / 2.0
            return self.level_c - half, self.level_c + half
        return self.minimum_c, self.maximum_c

    @classmethod
    def from_limits(
        cls,
        minimum_c: float,
        maximum_c: float,
        *,
        palette: str = "ironbow",
        isotherm_min_c: float | None = None,
        isotherm_max_c: float | None = None,
    ) -> ThermalStyle:
        if maximum_c <= minimum_c:
            raise ValueError("maximum_c must exceed minimum_c")
        return cls(
            palette=palette,
            span_c=maximum_c - minimum_c,
            level_c=(minimum_c + maximum_c) / 2.0,
            isotherm_min_c=isotherm_min_c,
            isotherm_max_c=isotherm_max_c,
        )

    def as_dict(self) -> dict[str, float | str | None]:
        return asdict(self)


def available_palettes() -> tuple[str, ...]:
    return tuple(_PALETTES)


def automatic_style(
    temperature_c: np.ndarray,
    *,
    palette: str = "ironbow",
    lower_percentile: float = 2.0,
    upper_percentile: float = 98.0,
) -> ThermalStyle:
    values = np.asarray(temperature_c, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return ThermalStyle(palette=palette, span_c=1.0, level_c=0.5)
    low = float(np.percentile(finite, lower_percentile))
    high = float(np.percentile(finite, upper_percentile))
    if high <= low:
        high = low + 1.0
    return ThermalStyle.from_limits(low, high, palette=palette)


def _interpolate(values: np.ndarray, palette: str) -> np.ndarray:
    anchors = _PALETTES[palette]
    flat = values.reshape(-1)
    rgb = np.empty((flat.size, 3), dtype=np.float32)
    positions = np.array([item[0] for item in anchors], dtype=np.float32)
    colors = np.array([item[1] for item in anchors], dtype=np.float32)
    for channel in range(3):
        rgb[:, channel] = np.interp(flat, positions, colors[:, channel])
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8).reshape((*values.shape, 3))


def render_with_style(
    temperature_c: np.ndarray,
    style: ThermalStyle | None = None,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Render temperatures without mutating or recalibrating the quantitative matrix."""

    values = np.asarray(temperature_c, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("temperature_c must be a two-dimensional matrix")
    active = style or automatic_style(values)
    requested_low, requested_high = active.limits()
    finite = values[np.isfinite(values)]
    if finite.size:
        low = float(np.percentile(finite, 2)) if requested_low is None else float(requested_low)
        high = float(np.percentile(finite, 98)) if requested_high is None else float(requested_high)
    else:
        low = 0.0 if requested_low is None else float(requested_low)
        high = 1.0 if requested_high is None else float(requested_high)
    if high <= low:
        high = low + 1.0
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    normalized = np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0)
    rgb = _interpolate(normalized, active.palette.strip().lower())
    if active.isotherm_min_c is not None:
        mask = np.isfinite(values) & (values >= float(active.isotherm_min_c))
        if active.isotherm_max_c is not None:
            mask &= values <= float(active.isotherm_max_c)
        rgb = rgb.copy()
        rgb[mask] = np.array([255, 255, 0], dtype=np.uint8)
    return rgb, (low, high)


def batch_render(
    matrices: list[np.ndarray],
    style: ThermalStyle,
) -> list[np.ndarray]:
    """Apply one presentation style across a batch without modifying any input matrix."""

    return [render_with_style(matrix, style)[0] for matrix in matrices]
