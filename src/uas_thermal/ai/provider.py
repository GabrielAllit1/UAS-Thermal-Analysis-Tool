from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LocalAIModel:
    name: str
    provider: str
    capabilities: tuple[str, ...] = ()
    parameter_size: str = ""
    quantization: str = ""

    @property
    def supports_vision(self) -> bool:
        return "vision" in {item.lower() for item in self.capabilities}


class LocalAIProvider(ABC):
    name = "local-ai"

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> tuple[LocalAIModel, ...]:
        raise NotImplementedError

    @abstractmethod
    def structured_chat(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        images: tuple[str | Path, ...] = (),
    ) -> dict[str, Any]:
        raise NotImplementedError
