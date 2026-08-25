from pathlib import Path

from uas_thermal.ai.enrichment import enrich_finding
from uas_thermal.ai.provider import LocalAIModel, LocalAIProvider
from uas_thermal.inspections.models import Confidence, Finding, Severity


class FakeProvider(LocalAIProvider):
    name = "fake-local"

    def available(self) -> bool:
        return True

    def list_models(self):
        return (LocalAIModel("vision-test", self.name, ("completion", "vision")),)

    def structured_chat(self, *, model, system, prompt, schema, images=()):
        assert "immutable upstream authorities" in system
        assert "Maximum temperature" in prompt
        assert schema["type"] == "object"
        return {
            "summary": "Localized thermal contrast warrants field verification.",
            "visual_observations": ["Compact warm region"],
            "possible_explanations": ["Possible loading or material-related contrast"],
            "recommended_verification": ["Inspect the corresponding asset area"],
            "limitations": ["Thermal imagery alone does not prove a defect"],
        }


def _finding():
    return Finding(
        center_x=10,
        center_y=20,
        area_px=50,
        max_temperature_c=72.0,
        mean_temperature_c=63.0,
        baseline_temperature_c=42.0,
        delta_temperature_c=30.0,
        severity=Severity.CRITICAL,
        confidence=Confidence.HIGH,
        bbox=(5, 15, 15, 25),
        polygon=[(5, 15), (15, 15), (15, 25), (5, 25)],
        finding_id="A-001",
        classification="Thermal anomaly",
    )


def test_ai_enrichment_is_supplemental_and_does_not_mutate_quantitative_authority(tmp_path):
    finding = _finding()
    quantitative_before = (
        finding.max_temperature_c,
        finding.delta_temperature_c,
        finding.severity,
        finding.confidence,
        finding.bbox,
        list(finding.polygon),
        finding.classification,
    )

    enrichment = enrich_finding(
        finding,
        FakeProvider(),
        model="vision-test",
        project_context={"site": "test"},
        image_paths=(Path(tmp_path / "missing.png"),),
    )

    assert enrichment.provider == "fake-local"
    assert finding.ai_enrichment["summary"].startswith("Localized")
    assert quantitative_before == (
        finding.max_temperature_c,
        finding.delta_temperature_c,
        finding.severity,
        finding.confidence,
        finding.bbox,
        list(finding.polygon),
        finding.classification,
    )
