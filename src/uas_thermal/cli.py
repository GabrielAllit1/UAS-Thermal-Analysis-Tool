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
    sub.add_parser("profiles", help="List supported versioned inspection profiles")
    sub.add_parser("validate-synthetic", help="Run deterministic contextual detector validation")
    sub.add_parser("validation-sources", help="List external radiometric validation datasets")

    inspect = sub.add_parser(
        "inspect",
        help="Run the canonical autonomous inspection workflow over one or more radiometric sources",
    )
    inspect.add_argument("sources", type=Path, nargs="+")
    inspect.add_argument("--project", default="Untitled inspection")
    inspect.add_argument("--site", default="")
    inspect.add_argument("--client", default="")
    inspect.add_argument("--inspection-id", default="")
    inspect.add_argument("--profile", default="generic-thermal")
    inspect.add_argument("--adapter", default=None)
    inspect.add_argument("--output-dir", type=Path, default=None)
    inspect.add_argument("--emissivity", type=float, default=0.95)
    inspect.add_argument("--distance-m", type=float, default=5.0)
    inspect.add_argument("--humidity", type=float, default=0.50)
    inspect.add_argument("--reflected-c", type=float, default=20.0)

    dji_probe = sub.add_parser(
        "dji-probe",
        help="Decode one DJI R-JPEG and print radiometric diagnostics as JSON",
    )
    dji_probe.add_argument("source", type=Path, help="Path to a DJI radiometric JPEG")
    dji_probe.add_argument("--emissivity", type=float, default=0.95)
    dji_probe.add_argument("--distance-m", type=float, default=5.0)
    dji_probe.add_argument(
        "--humidity",
        type=float,
        default=0.50,
        help="Relative humidity as 0.0-1.0",
    )
    dji_probe.add_argument("--reflected-c", type=float, default=20.0)
    dji_probe.add_argument("--palette", default="IRONRED")

    geotiff_probe = sub.add_parser(
        "geotiff-probe",
        help="Inspect one thermal GeoTIFF and print raster/radiometric diagnostics as JSON",
    )
    geotiff_probe.add_argument("source", type=Path, help="Path to a thermal GeoTIFF")
    geotiff_probe.add_argument("--unit", default="auto")
    geotiff_probe.add_argument("--scale", type=float, default=1.0)
    geotiff_probe.add_argument("--offset", type=float, default=0.0)

    display_probe = sub.add_parser(
        "display-probe",
        help="Read a bounded GeoTIFF display preview without loading the full raster",
    )
    display_probe.add_argument("source", type=Path, help="Path to a GeoTIFF or TIFF")
    display_probe.add_argument("--max-edge", type=int, default=1600)
    return parser


def _run_inspect(args: argparse.Namespace) -> int:
    from .application.orchestrator import AutonomousInspectionOrchestrator
    from .application.projects import Project
    from .inspections.profiles import get_profile
    from .thermal.calibration import ThermalCalibration

    sources = [source.expanduser().resolve() for source in args.sources]
    missing = [str(source) for source in sources if not source.is_file()]
    if missing:
        print(json.dumps({"ok": False, "missing_sources": missing}, indent=2), file=sys.stderr)
        return 2
    project = Project(
        name=args.project,
        site=args.site,
        client=args.client,
        inspection_id=args.inspection_id,
        profile_id=args.profile,
    )
    calibration = ThermalCalibration(
        emissivity=args.emissivity,
        distance_m=args.distance_m,
        relative_humidity=args.humidity,
        reflected_temperature_c=args.reflected_c,
    )
    try:
        profile = get_profile(args.profile)
        run = AutonomousInspectionOrchestrator().analyze_inspection(
            project,
            sources,
            calibration=calibration,
            adapter_name=args.adapter,
            profile=profile,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error_type": type(exc).__name__, "error": str(exc)},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    payload = {"ok": bool(run.artifacts), **run.as_dict()}
    print(json.dumps(payload, indent=2))
    return 0 if run.artifacts else 1


def _run_profiles() -> int:
    from .inspections.profiles import available_profiles

    print(json.dumps([item.as_dict() for item in available_profiles()], indent=2))
    return 0


def _run_synthetic_validation() -> int:
    from .thermal.validation import evaluate_case, synthetic_cases

    payload = []
    for case in synthetic_cases():
        payload.append({"case": case.name, **asdict(evaluate_case(case))})
    print(json.dumps(payload, indent=2))
    return 0


def _run_validation_sources() -> int:
    from .validation.external_sources import SOURCES

    print(json.dumps([asdict(source) for source in SOURCES], indent=2))
    return 0


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


def _run_geotiff_probe(args: argparse.Namespace) -> int:
    from .sensors.generic import GenericGeoTiffAdapter
    from .thermal.statistics import summarize_temperature

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(
            json.dumps({"ok": False, "error": f"source not found: {source}"}, indent=2),
            file=sys.stderr,
        )
        return 2

    adapter = GenericGeoTiffAdapter(scale=args.scale, offset=args.offset, unit=args.unit)
    try:
        diagnostics = adapter.source_diagnostics(source)
    except Exception as exc:
        payload = {
            "ok": False,
            "source": str(source),
            "adapter": adapter.name,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 1

    base_payload = {
        "source": str(source),
        "adapter": adapter.name,
        **diagnostics,
        "requested_unit": args.unit,
        "requested_scale": args.scale,
        "requested_offset": args.offset,
        "probe_mode": "bounded-sample",
    }

    try:
        sample_temperature, encoding = adapter.sample_temperature(source)
        stats = summarize_temperature(sample_temperature)
    except Exception as exc:
        payload = {
            "ok": False,
            **base_payload,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        if not diagnostics.get("radiometric_candidate", True):
            payload["hint"] = (
                "This raster appears to be rendered/uncalibrated imagery, not scalar temperature "
                "data. Use the original radiometric source, a calibrated single-band thermal "
                "GeoTIFF, or the original camera R-JPEG rather than forcing a temperature unit."
            )
        else:
            payload["hint"] = (
                "Do not guess thermal units. If the export documentation identifies the raster "
                "encoding, retry with --unit and, only when specified, --scale/--offset."
            )
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 1

    tiled = bool(diagnostics.get("requires_tiled_processing"))
    payload = {
        "ok": True,
        **base_payload,
        "resolved_scale": encoding.get("scale"),
        "resolved_offset": encoding.get("offset"),
        "resolved_input_unit": encoding.get("input_unit"),
        "sample_temperature": asdict(stats),
        "full_frame_analysis_ready": True,
        "analysis_mode": "tiled" if tiled else "full-frame",
    }
    if tiled:
        payload["analysis_warning"] = (
            "The raster exceeds the in-memory frame limit. Canonical inspection analysis will "
            "process quantitative overlapping tiles while keeping memory bounded."
        )
    sidecars = diagnostics.get("sidecars", {})
    if diagnostics.get("crs") is None and isinstance(sidecars, dict):
        if sidecars.get("world_file") and not sidecars.get("projection"):
            payload["geospatial_warning"] = (
                "A world file supplies pixel placement but not a CRS. Add the matching .prj or "
                "configure the source CRS before latitude/longitude export."
            )
    print(json.dumps(payload, indent=2))
    return 0


def _run_display_probe(args: argparse.Namespace) -> int:
    from .geospatial.display import read_display_raster
    from .sensors.generic import GenericGeoTiffAdapter

    source = args.source.expanduser().resolve()
    if not source.is_file():
        print(
            json.dumps({"ok": False, "error": f"source not found: {source}"}, indent=2),
            file=sys.stderr,
        )
        return 2
    try:
        display = read_display_raster(source, max_edge=args.max_edge)
        diagnostics = GenericGeoTiffAdapter().source_diagnostics(source)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "source": str(source),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    payload = {
        "ok": True,
        "source": str(source),
        "mode": "display-gis",
        "preview_shape": list(display.rgb.shape),
        "bounded_preview": True,
        "radiometric_candidate": diagnostics.get("radiometric_candidate"),
        "radiometric_reasons": diagnostics.get("radiometric_reasons"),
        "requires_tiled_processing": diagnostics.get("requires_tiled_processing"),
        "pixel_count": diagnostics.get("pixel_count"),
        "crs": display.crs,
        "metadata": display.metadata,
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
    if args.command == "profiles":
        return _run_profiles()
    if args.command == "validate-synthetic":
        return _run_synthetic_validation()
    if args.command == "validation-sources":
        return _run_validation_sources()
    if args.command == "inspect":
        return _run_inspect(args)
    if args.command == "dji-probe":
        return _run_dji_probe(args)
    if args.command == "geotiff-probe":
        return _run_geotiff_probe(args)
    if args.command == "display-probe":
        return _run_display_probe(args)
    return 2
