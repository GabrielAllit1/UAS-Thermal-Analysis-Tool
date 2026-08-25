from __future__ import annotations

from dataclasses import dataclass

from ..ai.ollama import OllamaProvider
from ..ai.provider import LocalAIProvider
from ..orthomosaic import OrthomosaicService
from ..platform.config import AppConfig


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    ai_available: bool
    model_names: tuple[str, ...]
    vision_models: tuple[str, ...]
    orthomosaic_backends: tuple[tuple[str, bool], ...]
    ai_error: str = ""

    @property
    def preferred_ai_mode(self) -> str:
        return "auto" if self.ai_available and self.model_names else "off"

    @property
    def quantitative_stitch_available(self) -> bool:
        return any(available for _, available in self.orthomosaic_backends)


def scan_runtime(
    *,
    config: AppConfig | None = None,
    provider: LocalAIProvider | None = None,
    orthomosaics: OrthomosaicService | None = None,
) -> RuntimeSnapshot:
    """Inspect local AI and stitching runtimes without downloading or changing anything."""

    active_config = config or AppConfig.from_env()
    active_provider = provider or OllamaProvider(active_config.ollama_base_url, timeout_s=0.6)
    active_orthomosaics = orthomosaics or OrthomosaicService()
    status = tuple(
        (str(item["name"]), bool(item["available"]))
        for item in active_orthomosaics.status()
    )

    try:
        if not active_provider.available():
            return RuntimeSnapshot(False, (), (), status, "Local AI runtime not reachable")
        models = active_provider.list_models()
    except Exception as exc:
        return RuntimeSnapshot(False, (), (), status, f"{type(exc).__name__}: {exc}")

    names = tuple(model.name for model in models)
    vision = tuple(model.name for model in models if model.supports_vision)
    return RuntimeSnapshot(bool(names), names, vision, status)


def stage_for_event(message: str) -> str:
    """Map processor telemetry to the operator-facing autonomous mission stages."""

    text = message.lower()
    if "orthomosaic" in text or "stitch" in text:
        return "STITCH"
    if "radiometric analysis" in text or "canonical" in text:
        return "ANALYZE"
    if "ai" in text or "model" in text:
        return "AI REVIEW"
    if "deliverable" in text or "report" in text or "package" in text:
        return "PACKAGE"
    if "annotat" in text or "evidence" in text:
        return "ANNOTATE"
    if "validat" in text or "radiometr" in text:
        return "RADIOMETRY"
    return "INGEST"


def autopilot_summary(snapshot: RuntimeSnapshot, source_count: int) -> dict[str, str]:
    """Return concise UI-ready readiness copy for the autonomous workspace."""

    stitch = "READY" if snapshot.quantitative_stitch_available else "SOURCE-DEPENDENT"
    if source_count <= 1:
        stitch = "NOT REQUIRED"
    ai = "LOCAL AI READY" if snapshot.ai_available else "DETERMINISTIC FALLBACK"
    if snapshot.vision_models:
        ai = f"VISION AI READY · {len(snapshot.vision_models)}"
    return {
        "sources": str(source_count),
        "radiometry": "GATED",
        "stitch": stitch,
        "ai": ai,
        "deliverable": "AUTOMATED",
    }
