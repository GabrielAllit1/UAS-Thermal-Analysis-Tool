from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..inspections.models import Finding
from .provider import LocalAIProvider

_PROMPT_VERSION = "thermal-finding-enrichment-v1"


@dataclass(frozen=True, slots=True)
class AIEnrichment:
    summary: str
    visual_observations: tuple[str, ...] = ()
    possible_explanations: tuple[str, ...] = ()
    recommended_verification: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    provider: str = ""
    model: str = ""
    prompt_version: str = _PROMPT_VERSION
    vision_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "visual_observations",
            "possible_explanations",
            "recommended_verification",
            "limitations",
        ):
            payload[key] = list(payload[key])
        return payload


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "visual_observations": {"type": "array", "items": {"type": "string"}},
            "possible_explanations": {"type": "array", "items": {"type": "string"}},
            "recommended_verification": {"type": "array", "items": {"type": "string"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "summary",
            "visual_observations",
            "possible_explanations",
            "recommended_verification",
            "limitations",
        ],
    }


def _prompt(finding: Finding, project_context: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Interpret this already-established thermal finding for a professional inspection deliverable.",
            "Do not change, recompute, or dispute the quantitative fields below.",
            "Do not claim that a defect is proven. Phrase causes as possibilities that require verification.",
            f"Industry/profile: {finding.profile_id}",
            f"Finding ID: {finding.finding_id}",
            f"Classification: {finding.classification or finding.finding_type}",
            f"Severity authority: {finding.severity.value}",
            f"Evidence confidence authority: {finding.confidence.value}",
            f"Maximum temperature: {finding.max_temperature_c:.3f} C",
            f"Local reference: {(finding.reference_temperature_c if finding.reference_temperature_c is not None else finding.baseline_temperature_c):.3f} C",
            f"Local delta-T: {finding.delta_temperature_c:.3f} C",
            f"Area: {finding.area_px} pixels",
            f"Evidence: {finding.evidence}",
            f"Project context: {project_context}",
        ]
    )


def enrich_finding(
    finding: Finding,
    provider: LocalAIProvider,
    *,
    model: str,
    project_context: dict[str, Any] | None = None,
    image_paths: tuple[str | Path, ...] = (),
) -> AIEnrichment:
    """Append bounded local-model interpretation without modifying finding authority fields."""

    baseline = (
        finding.max_temperature_c,
        finding.mean_temperature_c,
        finding.baseline_temperature_c,
        finding.delta_temperature_c,
        finding.severity,
        finding.confidence,
        finding.bbox,
        finding.polygon.copy(),
        finding.latitude,
        finding.longitude,
        finding.classification,
        finding.finding_id,
    )
    system = (
        "You are an inspection-assistance model. Quantitative radiometry, geometry, severity, "
        "confidence, geolocation and finding identity are immutable upstream authorities. Your role "
        "is limited to concise visual/context interpretation, plausible explanations, and field "
        "verification guidance. Never state that a defect is proven solely from thermal imagery."
    )
    payload = provider.structured_chat(
        model=model,
        system=system,
        prompt=_prompt(finding, project_context or {}),
        schema=_schema(),
        images=image_paths,
    )
    current = (
        finding.max_temperature_c,
        finding.mean_temperature_c,
        finding.baseline_temperature_c,
        finding.delta_temperature_c,
        finding.severity,
        finding.confidence,
        finding.bbox,
        finding.polygon.copy(),
        finding.latitude,
        finding.longitude,
        finding.classification,
        finding.finding_id,
    )
    if current != baseline:
        raise RuntimeError("AI provider mutated canonical finding authority")
    enrichment = AIEnrichment(
        summary=str(payload.get("summary", "")).strip(),
        visual_observations=tuple(str(item) for item in payload.get("visual_observations", [])),
        possible_explanations=tuple(str(item) for item in payload.get("possible_explanations", [])),
        recommended_verification=tuple(str(item) for item in payload.get("recommended_verification", [])),
        limitations=tuple(str(item) for item in payload.get("limitations", [])),
        provider=provider.name,
        model=model,
        vision_used=bool(image_paths),
    )
    finding.ai_enrichment = enrichment.as_dict()
    return enrichment
