import json

from uas_thermal.ai.ollama import OllamaProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_discovers_capabilities_and_structured_chat(monkeypatch):
    def fake_urlopen(outbound, timeout):
        path = outbound.full_url
        if path.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "vision:latest"}]})
        if path.endswith("/api/show"):
            return FakeResponse(
                {
                    "capabilities": ["completion", "vision"],
                    "details": {"parameter_size": "7B", "quantization_level": "Q4_K_M"},
                }
            )
        if path.endswith("/api/chat"):
            body = json.loads(outbound.data.decode("utf-8"))
            assert body["stream"] is False
            assert body["options"]["temperature"] == 0
            assert body["format"]["type"] == "object"
            return FakeResponse({"message": {"content": '{"summary":"ok"}'}})
        raise AssertionError(path)

    monkeypatch.setattr("uas_thermal.ai.ollama.request.urlopen", fake_urlopen)
    provider = OllamaProvider()

    assert provider.available() is True
    models = provider.list_models()
    assert len(models) == 1
    assert models[0].supports_vision is True
    assert models[0].parameter_size == "7B"
    result = provider.structured_chat(
        model=models[0].name,
        system="system",
        prompt="prompt",
        schema={"type": "object", "properties": {"summary": {"type": "string"}}},
    )
    assert result == {"summary": "ok"}
