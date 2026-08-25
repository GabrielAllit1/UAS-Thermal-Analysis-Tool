from __future__ import annotations

import re
from dataclasses import dataclass

from .provider import LocalAIModel


@dataclass(frozen=True, slots=True)
class ModelScore:
    model: LocalAIModel
    task: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelRoutingPlan:
    vision_review: str = ""
    engineering_narrative: str = ""
    fast_triage: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "vision_review": self.vision_review,
            "engineering_narrative": self.engineering_narrative,
            "fast_triage": self.fast_triage,
        }


def _parameter_billions(model: LocalAIModel) -> float:
    text = model.parameter_size or model.name
    match = re.search(r"(\d+(?:\.\d+)?)\s*[bB](?:\b|$)", text)
    if match:
        return float(match.group(1))
    match = re.search(r":(\d+(?:\.\d+)?)b(?:\b|$)", model.name.lower())
    return float(match.group(1)) if match else 0.0


def _base_penalties(name: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if "embed" in name:
        score -= 1000.0
        reasons.append("embedding model is not a generative review model")
    if "coder" in name or "codellama" in name:
        score -= 14.0
        reasons.append("code-specialized model is deprioritized for thermal interpretation")
    return score, reasons


def score_model(model: LocalAIModel, task: str) -> ModelScore:
    name = model.name.lower()
    params = _parameter_billions(model)
    score, reasons = _base_penalties(name)

    if task == "vision_review":
        if not model.supports_vision:
            return ModelScore(model, task, -10000.0, ("vision capability is required",))
        score += 100.0
        reasons.append("declares vision capability")
        for token, boost in (
            ("qwen2.5vl", 24.0),
            ("qwen2.5-vl", 24.0),
            ("minicpm-v", 20.0),
            ("llama3.2-vision", 18.0),
            ("vision", 10.0),
            ("vl", 8.0),
        ):
            if token in name:
                score += boost
                reasons.append(f"{token} family is favored for visual evidence review")
                break
        score += min(params, 32.0) * 0.7
        if params:
            reasons.append(f"{params:g}B parameter class adds review capacity")
    elif task == "engineering_narrative":
        for token, boost in (
            ("qwen3", 20.0),
            ("phi4", 18.0),
            ("gemma4", 17.0),
            ("llama3.1", 16.0),
            ("gemma3", 14.0),
            ("mistral", 11.0),
            ("deepseek-r1", 10.0),
        ):
            if token in name:
                score += boost
                reasons.append(f"{token} family is favored for structured narrative/reasoning")
                break
        score += min(params, 30.0) * 0.85
        if model.supports_vision:
            score += 2.0
        if params:
            reasons.append(f"{params:g}B parameter class supports richer engineering synthesis")
    elif task == "fast_triage":
        if params:
            if params <= 4.5:
                score += 24.0
                reasons.append("small model class favors low-latency triage")
            elif params <= 9.0:
                score += 18.0
                reasons.append("mid-size model balances latency and reasoning")
            elif params <= 14.0:
                score += 8.0
        for token, boost in (("qwen3", 10.0), ("gemma3", 8.0), ("mistral", 6.0)):
            if token in name:
                score += boost
                reasons.append(f"{token} family is suitable for fast structured work")
                break
    else:
        raise ValueError(f"unknown model-routing task: {task}")

    return ModelScore(model, task, score, tuple(reasons))


def rank_models(models: tuple[LocalAIModel, ...], task: str) -> tuple[ModelScore, ...]:
    scored = [score_model(model, task) for model in models]
    scored.sort(key=lambda item: (-item.score, item.model.name.lower()))
    return tuple(scored)


def select_model(models: tuple[LocalAIModel, ...], task: str) -> LocalAIModel | None:
    ranked = rank_models(models, task)
    if not ranked or ranked[0].score <= -999.0:
        return None
    return ranked[0].model


def route_models(models: tuple[LocalAIModel, ...]) -> ModelRoutingPlan:
    vision = select_model(models, "vision_review")
    narrative = select_model(models, "engineering_narrative")
    fast = select_model(models, "fast_triage")
    return ModelRoutingPlan(
        vision_review="" if vision is None else vision.name,
        engineering_narrative="" if narrative is None else narrative.name,
        fast_triage="" if fast is None else fast.name,
    )
