from __future__ import annotations

import argparse
import json

from . import __version__
from .sensors.registry import default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uas-thermal")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("info", help="Show installed capabilities and adapter state")
    return parser


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
    return 2
