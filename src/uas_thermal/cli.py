from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import __version__
from .sensors.registry import default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uas-thermal")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("info", help="Show installed capabilities and adapter state")
    sub.add_parser("desktop", help="Launch the desktop application")

    probe = sub.add_parser(
        "dji-probe",
        help="Decode one DJI R-JPEG and print radiometric diagnostics as JSON",
    )
    probe.add_argument("source", type=Path, help="Path to a DJI radiometric JPEG")
    probe.add_argument("--emissivity", type=float, default=0.95)
    probe.add_argument("--distance-m", type=float, default=5.0)
    probe.add_argument("--humidity", type=float, default=0.50, help="Relative humidity as 0.0-1.0")
    probe.add_argument("--reflected-c", type=float, default=20.0)
    probe.add_argument("--palette", default="IRONRED")
    return parser


def _run_dji_probe(args: argparse.Namespace) -> int:
    from .sensors.dji import DjiDirpAdapter
    from .thermal.calibration import ThermalCalibration
    from .thermal.statistics import summarize_temperature

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(
            json.dumps({"ok": False, "error": f"source not found: {source}"}, indent=2),
            file=sys.stderr,
        )
        return 2

    calibration = ThermalCalibration(
        emissivity=args.emissivity,
        distance_m=args.distance_m,
        relative_humidity=args.humidity,
        reflected_temperature_c=args.reflected_c,
    )
    adapter = DjiDirpAdapter(palette=args.palette)

    try:
        frame = adapter.read(source, calibration)
        stats = summarize_temperature(frame.temperature_c)
    except Exception as exc:
        payload = {
            "ok": False,
            "source": str(source),
            "adapter": adapter.name,
            **adapter.source_diagnostics(source),
            **adapter.sdk_diagnostics(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        if payload.get("export_like_filename"):
            payload["hint"] = (
                "The filename looks like an exported derivative. DJI DIRP requires the original "
                "camera R-JPEG with its radiometric payload intact. If a radiometric GeoTIFF was "
                "exported alongside it, analyze the .tif with generic-geotiff instead."
            )
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "source": str(source),
        "adapter": adapter.name,
        "vendor": adapter.vendor,
        "sdk_library": frame.metadata.get("sdk_library"),
        "sdk_api": frame.metadata.get("sdk_api"),
        **adapter.sdk_diagnostics(),
        "width": int(frame.temperature_c.shape[1]),
        "height": int(frame.temperature_c.shape[0]),
        "palette": frame.metadata.get("palette"),
        "calibration": frame.metadata.get("calibration"),
        "temperature": asdict(stats),
        "display_rgb": frame.display_rgb is not None,
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in (None, "info"):
        registry = default_registry()
        payload = {
            "name": "UAS Thermal Analysis",
            "version": __version__,
            "adapters": [adapter.describe() for adapter in registry.adapters],
        }
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "desktop":
        from .application.desktop import launch

        return launch()
    if args.command == "dji-probe":
        return _run_dji_probe(args)
    return 2
