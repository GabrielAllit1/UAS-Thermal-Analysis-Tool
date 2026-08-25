from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib import error, request

from .provider import LocalAIModel, LocalAIProvider


class OllamaProvider(LocalAIProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        *,
        probe_timeout_s: float = 3.0,
        generation_timeout_s: float = 180.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.probe_timeout_s = float(probe_timeout_s)
        self.generation_timeout_s = float(generation_timeout_s)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
    ) -> Any:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        outbound = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with request.urlopen(
                outbound,
                timeout=self.probe_timeout_s if timeout_s is None else timeout_s,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

    def available(self) -> bool:
        try:
            payload = self._request("GET", "/api/tags")
        except RuntimeError:
            return False
        return isinstance(payload, dict) and isinstance(payload.get("models"), list)

    def show_model(self, model: str) -> LocalAIModel:
        payload = self._request("POST", "/api/show", {"model": model})
        details = payload.get("details") or {}
        return LocalAIModel(
            name=model,
            provider=self.name,
            capabilities=tuple(str(item) for item in payload.get("capabilities", [])),
            parameter_size=str(details.get("parameter_size", "")),
            quantization=str(details.get("quantization_level", "")),
        )

    def _fallback_model(self, item: dict[str, Any], name: str) -> LocalAIModel:
        details = item.get("details") or {}
        return LocalAIModel(
            name=name,
            provider=self.name,
            parameter_size=str(details.get("parameter_size", "")),
            quantization=str(details.get("quantization_level", "")),
        )

    def list_models(self) -> tuple[LocalAIModel, ...]:
        payload = self._request("GET", "/api/tags")
        tagged: list[tuple[dict[str, Any], str]] = []
        for item in payload.get("models", []):
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                tagged.append((item, name))
        if not tagged:
            return ()

        def inspect(entry: tuple[dict[str, Any], str]) -> LocalAIModel:
            item, name = entry
            try:
                return self.show_model(name)
            except RuntimeError:
                return self._fallback_model(item, name)

        # Capability probes are independent. Bounded parallelism avoids a slow/unloaded model making
        # runtime discovery serially block for N * timeout while preserving the /api/tags order.
        workers = min(6, len(tagged))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ollama-show") as pool:
            return tuple(pool.map(inspect, tagged))

    @staticmethod
    def _image_payload(images: tuple[str | Path, ...]) -> list[str]:
        encoded: list[str] = []
        for item in images:
            path = Path(item)
            if not path.is_file():
                continue
            encoded.append(base64.b64encode(path.read_bytes()).decode("ascii"))
        return encoded

    def structured_chat(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        images: tuple[str | Path, ...] = (),
    ) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "user", "content": prompt}
        image_payload = self._image_payload(images)
        if image_payload:
            message["images"] = image_payload
        payload = self._request(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    message,
                ],
                "stream": False,
                "format": schema,
                "options": {"temperature": 0},
            },
            timeout_s=self.generation_timeout_s,
        )
        content = str((payload.get("message") or {}).get("content", "")).strip()
        if not content:
            raise RuntimeError("Ollama returned an empty structured response")
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid structured JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Ollama structured response must be a JSON object")
        return decoded
