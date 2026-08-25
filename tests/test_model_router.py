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


def test_router_does_not_choose_large_coder_for_narrative_when_general_model_exists():
    models = (
        LocalAIModel("qwen3-coder:30b", "test", parameter_size="30.5B"),
        LocalAIModel("phi4:14b", "test", parameter_size="14.7B"),
        LocalAIModel("qwen3:8b", "test", parameter_size="8.2B"),
    )
    selected = select_model(models, "engineering_narrative")
    assert selected is not None
    assert selected.name == "phi4:14b"


def test_router_prefers_small_but_capable_triage_over_one_billion_parameter_model():
    models = (
        LocalAIModel("gemma3:1b", "test", parameter_size="999.89M"),
        LocalAIModel("gemma3:4b", "test", parameter_size="4.3B"),
        LocalAIModel("qwen3:8b", "test", parameter_size="8.2B"),
    )
    selected = select_model(models, "fast_triage")
    assert selected is not None
    assert selected.name == "gemma3:4b"


def test_router_matches_observed_windows_model_mix():
    models = (
        LocalAIModel(
            "gemma4:12b",
            "ollama",
            capabilities=("completion", "vision", "audio", "tools", "thinking"),
            parameter_size="11.9B",
        ),
        LocalAIModel("qwen3:8b", "ollama", capabilities=("completion", "tools", "thinking"), parameter_size="8.2B"),
        LocalAIModel("minicpm-v:8b", "ollama", capabilities=("completion", "vision"), parameter_size="7.6B"),
        LocalAIModel("llama3.2-vision:11b", "ollama", capabilities=("completion", "vision", "tools"), parameter_size="10.7B"),
        LocalAIModel("qwen2.5vl:7b", "ollama", capabilities=("completion", "vision"), parameter_size="8.3B"),
        LocalAIModel("nomic-embed-text:latest", "ollama", capabilities=("embedding",), parameter_size="137M"),
        LocalAIModel("gemma3:1b", "ollama", capabilities=("completion",), parameter_size="999.89M"),
        LocalAIModel("qwen3-coder:30b", "ollama", capabilities=("completion", "tools"), parameter_size="30.5B"),
        LocalAIModel("phi4:14b", "ollama", capabilities=("completion",), parameter_size="14.7B"),
        LocalAIModel("mistral:7b", "ollama", capabilities=("completion", "tools"), parameter_size="7.2B"),
        LocalAIModel("llama3.1:8b", "ollama", capabilities=("completion", "tools"), parameter_size="8.0B"),
        LocalAIModel("deepseek-r1:7b", "ollama", capabilities=("completion", "tools", "thinking"), parameter_size="7.6B"),
        LocalAIModel("qwen2.5:7b", "ollama", capabilities=("completion", "tools"), parameter_size="7.6B"),
        LocalAIModel("gemma3:4b", "ollama", capabilities=("completion", "vision"), parameter_size="4.3B"),
    )
    plan = route_models(models)
    assert plan.vision_review == "qwen2.5vl:7b"
    assert plan.engineering_narrative == "phi4:14b"
    assert plan.fast_triage == "gemma3:4b"
