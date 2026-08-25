from uas_thermal.ai.provider import LocalAIModel
from uas_thermal.ai.router import rank_models, route_models, select_model


def _models():
    return (
        LocalAIModel("deepseek-coder-v2:16b", "test", parameter_size="16B"),
        LocalAIModel("qwen3:8b", "test", parameter_size="8B"),
        LocalAIModel("qwen2.5vl:7b", "test", capabilities=("vision",), parameter_size="7B"),
        LocalAIModel("llama3.2-vision:11b", "test", capabilities=("vision",), parameter_size="11B"),
        LocalAIModel("gemma3:4b", "test", parameter_size="4B"),
        LocalAIModel("nomic-embed-text:latest", "test"),
    )


def test_router_prefers_vision_specialist_for_finding_review():
    selected = select_model(_models(), "vision_review")
    assert selected is not None
    assert selected.name == "qwen2.5vl:7b"


def test_router_avoids_coder_and_embedding_models_for_engineering_narrative():
    ranked = rank_models(_models(), "engineering_narrative")
    assert ranked[0].model.name == "qwen3:8b"
    assert ranked[-1].model.name == "nomic-embed-text:latest"


def test_router_assigns_distinct_task_routes():
    plan = route_models(_models())
    assert plan.vision_review == "qwen2.5vl:7b"
    assert plan.engineering_narrative == "qwen3:8b"
    assert plan.fast_triage in {"gemma3:4b", "qwen3:8b"}
