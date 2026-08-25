from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from ..thermal.presentation import ThermalStyle, render_with_style


def write_tuned_thermograms(
    artifacts,
    output_dir: str | Path,
    *,
    style: ThermalStyle,
) -> tuple[Path, ...]:
    """Export presentation-only thermograms for every accepted radiometric artifact.

    These PNGs are convenient review products. They never replace the underlying temperature matrix
    and are accompanied by an index that records the exact visual style used.
    """

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install the reporting extra to export tuned thermograms") from exc

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    records: list[dict[str, object]] = []
    for index, artifact in enumerate(artifacts, 1):
        source = Path(artifact.result.source)
        rgb, limits = render_with_style(artifact.frame.temperature_c, style)
        destination = root / f"{index:05d}_{source.stem}_thermal.png"
        Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB").save(destination)
        outputs.append(destination)
        records.append(
            {
                "source": str(source),
                "image": destination.name,
                "display_minimum_c": limits[0],
                "display_maximum_c": limits[1],
                "style": asdict(style),
                "quantitative_authority": str(source),
                "presentation_only": True,
            }
        )
    (root / "thermogram_index.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "claim_boundary": (
                    "Rendered thermograms are presentation products. Temperature measurement and "
                    "analysis remain authoritative only in the validated radiometric source data."
                ),
                "thermograms": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tuple(outputs)
