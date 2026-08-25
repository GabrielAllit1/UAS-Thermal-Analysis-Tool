"""Optional local AI interpretation layer.

AI output is supplemental. Quantitative temperatures, radiometric quality, geometry, severity,
confidence, identity, and geolocation remain owned by deterministic application authorities.
"""

from .enrichment import AIEnrichment, enrich_finding
from .ollama import OllamaProvider
from .provider import LocalAIModel, LocalAIProvider

__all__ = [
    "AIEnrichment",
    "LocalAIModel",
    "LocalAIProvider",
    "OllamaProvider",
    "enrich_finding",
]
