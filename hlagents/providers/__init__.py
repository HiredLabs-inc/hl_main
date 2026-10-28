"""Chat providers, one adapter per ProviderConfig.Kind (docs/hlagents.md §3.1).

Every provider speaks the same message format (ChatProvider), so runs can
switch provider without touching the loop or stored conversations.
"""
from .base import ChatProvider, ChatResult, ProviderError, call_with_limit
from .gemini import GeminiProvider
from .ollama import OllamaProvider

PROVIDERS = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
}


def get_provider(config, timeout=None) -> ChatProvider:
    """A provider for a ProviderConfig. `timeout` is seconds per call; each
    adapter has its own default."""
    if problem := config.key_problem():
        raise ProviderError(problem)
    return PROVIDERS[config.kind].from_config(config, timeout=timeout)
