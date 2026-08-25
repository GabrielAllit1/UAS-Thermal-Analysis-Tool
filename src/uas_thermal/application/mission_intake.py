from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..sensors.registry import AdapterRegistry, default_registry

_IMAGE_EXTENSIONS = {".tif", ".tiff", ".jpg", ".jpeg", ".png"}
_CONTEXT_EXTENSIONS = {".kml", ".kmz", ".geojson", ".json", ".csv", ".tfw", ".prj", ".srt"}
_SUPPORTED_EXTENSIONS = _IMAGE_EXTENSIONS | _CONTEXT_EXTENSIONS

_PROFILE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("photovoltaic", ("solar", "photovoltaic", " pv ", "module", "array")),
    ("roof-envelope", ("roof", "envelope", "building envelope", "moisture")),
    ("electrical", ("electrical", "substation", "transformer", "switchgear", "powerline", "power line")),
    ("mechanical", ("mechanical", "motor", "bearing", "hvac", "pump", "compressor")),
    ("pipeline", ("pipeline", "pipe line", "linear infrastructure", "transmission line")),
    ("agriculture", ("agriculture", "agricultural", "crop", "orchard", "farm", "irrigation")),
    ("public-safety", ("public safety", "fire", "search and rescue", "sar", "incident")),
    ("natural-resources", ("forest", "forestry", "wildlife", "wetland", "environmental", "natural resources")),
    ("construction", ("construction", "building", "facade", "site survey")),
)


def _clean_name(value: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Thermal mission"


def infer_profile_id(root: Path, files: tuple[Path, ...]) -> str:
    """Infer only a conservative starting profile from path/file naming hints.

    The result controls domain thresholds/terminology, not radiometric validity. Generic thermal remains
    the fallback when the dataset does not contain a strong enough naming cue.
    """

    sample_names = [root.name]
    sample_names.extend(path.stem for path in files[:80])
    haystack = " " + " ".join(sample_names).lower().replace("_", " ").replace("-", " ") + " "
    for profile_id, tokens in _PROFILE_HINTS:
        if any(token in haystack for token in tokens):
            return profile_id
    return "generic-thermal"


def _analysis_candidates(files: tuple[Path, ...], registry: AdapterRegistry) -> tuple[Path, ...]:
    candidates: list[Path] = []
    for path in files:
        if path.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        for adapter in registry.adapters:
            if adapter.support_level == "contract-only":
                continue
            try:
                if adapter.can_read(path):
                    candidates.append(path)
                    break
            except Exception:
                continue
    return tuple(candidates)


@dataclass(frozen=True, slots=True)
class MissionIntake:
    root: Path
    discovered_files: tuple[Path, ...]
    analysis_sources: tuple[Path, ...]
    context_files: tuple[Path, ...]
    profile_id: str
    project_name: str
    dataset_name: str

    @property
    def image_count(self) -> int:
        return sum(path.suffix.lower() in _IMAGE_EXTENSIONS for path in self.discovered_files)

    @property
    def total_bytes(self) -> int:
        return sum(path.stat().st_size for path in self.discovered_files if path.is_file())

    @property
    def ready(self) -> bool:
        return bool(self.analysis_sources)


def scan_mission_folder(
    root: str | Path,
    *,
    registry: AdapterRegistry | None = None,
) -> MissionIntake:
    """Recursively discover a local mission folder without modifying source data."""

    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"Mission folder does not exist: {base}")
    files = tuple(
        sorted(
            (
                path
                for path in base.rglob("*")
                if path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS
            ),
            key=lambda item: str(item).lower(),
        )
    )
    active_registry = registry or default_registry()
    analysis_sources = _analysis_candidates(files, active_registry)
    context_files = tuple(path for path in files if path not in analysis_sources)
    project_name = _clean_name(base.name)
    return MissionIntake(
        root=base,
        discovered_files=files,
        analysis_sources=analysis_sources,
        context_files=context_files,
        profile_id=infer_profile_id(base, files),
        project_name=project_name,
        dataset_name=project_name,
    )


def scan_mission_files(
    sources: list[str | Path],
    *,
    registry: AdapterRegistry | None = None,
) -> MissionIntake:
    """Create the same intake contract for explicitly selected local files."""

    files = tuple(
        sorted(
            {
                Path(source).expanduser().resolve()
                for source in sources
                if Path(source).expanduser().is_file()
            },
            key=lambda item: str(item).lower(),
        )
    )
    if not files:
        raise ValueError("No mission files were selected")
    root = Path(__import__("os").path.commonpath([str(path.parent) for path in files]))
    active_registry = registry or default_registry()
    analysis_sources = _analysis_candidates(files, active_registry)
    context_files = tuple(path for path in files if path not in analysis_sources)
    project_name = _clean_name(root.name)
    return MissionIntake(
        root=root,
        discovered_files=files,
        analysis_sources=analysis_sources,
        context_files=context_files,
        profile_id=infer_profile_id(root, files),
        project_name=project_name,
        dataset_name=project_name,
    )
