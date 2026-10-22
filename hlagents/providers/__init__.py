"""Chat providers, one adapter per ProviderConfig.Kind (docs/hlagents.md §3.1).

Every provider speaks the same message format (ChatProvider), so runs can
switch provider without touching the loop or stored conversations.
"""
from .base import ChatProvider, ChatResult, ProviderError
from .ollama import OllamaProvider

PROVIDERS = {
    "ollama": OllamaProvider,
}


def get_provider(config) -> ChatProvider:
    """A provider for a ProviderConfig."""
    if config.secret_env and not config.api_key():
        raise ProviderError(f"{config.secret_env} isn't set, so {config} can't be used.")
    return PROVIDERS[config.kind](base_url=config.base_url, api_key=config.api_key())
