from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass


class ProviderError(Exception):
    pass


@dataclass
class ChatResult:
    # {"role": "assistant", "content": ..., "tool_calls": [{"function": {"name", "arguments"}}]}
    message: dict
    input_tokens: int = 0
    output_tokens: int = 0


class ChatProvider:
    """Messages use the Ollama/OpenAI shape: role, content, tool_calls with
    arguments as a dict, and {"role": "tool", "tool_name", "content"} replies.
    Adapters for other APIs translate to and from it.

    `options` tunes one call: temperature, top_p, top_k, max_output_tokens and
    thinking_budget. An adapter maps the ones its API has and ignores the rest."""

    def __init__(self, base_url="", api_key="", timeout=None):
        self.base_url = base_url
        self.api_key = api_key

    @classmethod
    def from_config(cls, config, timeout=None):
        """A provider for a ProviderConfig whose key has been checked."""
        return cls(base_url=config.base_url, api_key=config.api_key(), timeout=timeout)

    def chat(self, model, messages, tools, options=None) -> ChatResult:
        raise NotImplementedError


def call_with_limit(func, seconds, model=""):
    """func() if it returns within `seconds`, else ProviderError
    (docs/gcp-agents.md §3.7). Gemini's own timeout can't be used (GeminiProvider),
    so the call runs in a thread that's abandoned at the limit; its reply is
    thrown away when it arrives. func mustn't use the database: the thread has
    its own connection, which can't see the caller's transaction."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    try:
        return future.result(timeout=max(seconds, 0))
    except FutureTimeout:
        raise ProviderError(f"{model or 'The model'} didn't answer within {seconds:.3g} s.") from None
    finally:
        executor.shutdown(wait=False)
