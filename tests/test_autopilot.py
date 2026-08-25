from __future__ import annotations

from uas_thermal.ai.provider import LocalAIModel, LocalAIProvider
from uas_thermal.application.autopilot import autopilot_summary, scan_runtime, stage_for_event


class FakeProvider(LocalAIProvider):
    name = "fake"

    def available(self) -> bool:
        return True

    def list_models(self):
        return (
            LocalAIModel("vision-model", self.name, capabilities=("vision",)),
            LocalAIModel("text-model", self.name),
        )

    def structured_chat(self, **kwargs):
        return {}


class FakeOrthomosaics:
    def status(self):
        return [
            {"name": "native-geotiff", "available": True},
            {"name": "opendronemap", "available": False},
        ]


def test_runtime_scan_exposes_local_ai_and_stitch_capabilities():
    snapshot = scan_runtime(provider=FakeProvider(), orthomosaics=FakeOrthomosaics())

    assert snapshot.ai_available is True
    assert snapshot.model_names == ("vision-model", "text-model")
    assert snapshot.vision_models == ("vision-model",)
    assert snapshot.quantitative_stitch_available is True
    assert snapshot.preferred_ai_mode == "auto"


def test_autopilot_summary_is_operator_facing_and_source_aware():
    snapshot = scan_runtime(provider=FakeProvider(), orthomosaics=FakeOrthomosaics())

    one = autopilot_summary(snapshot, 1)
    many = autopilot_summary(snapshot, 24)

    assert one["stitch"] == "NOT REQUIRED"
    assert many["stitch"] == "READY"
    assert many["ai"] == "VISION AI READY · 1"
    assert many["radiometry"] == "GATED"
    assert many["deliverable"] == "AUTOMATED"


def test_stage_mapping_keeps_ai_orchestration_visible():
    assert stage_for_event("Building quantitative thermal orthomosaic") == "STITCH"
    assert stage_for_event("Running canonical radiometric analysis") == "ANALYZE"
    assert stage_for_event("AI enriched F-001 with local vision model") == "AI REVIEW"
    assert stage_for_event("Generating client and engineering deliverable") == "PACKAGE"
