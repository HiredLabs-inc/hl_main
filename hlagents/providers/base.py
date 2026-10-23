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
    Adapters for other APIs translate to and from it."""

    def __init__(self, base_url="", api_key=""):
        self.base_url = base_url
        self.api_key = api_key

    def chat(self, model, messages, tools) -> ChatResult:
        raise NotImplementedError
