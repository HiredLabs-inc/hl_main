from django.conf import settings
from google import genai
from google.genai import types

from .base import ChatProvider, ChatResult, ProviderError

GENERATION_OPTIONS = ("temperature", "top_p", "top_k", "max_output_tokens")


class GeminiProvider(ChatProvider):
    """Gemini on Vertex AI, with Application Default Credentials (no API key).

    Text only for now: tool calls arrive with IDEA-008 (docs/ai-tasks.md §2)."""

    def __init__(self, base_url="", api_key="", timeout=None, location=""):
        super().__init__(base_url, api_key)
        self.location = location or settings.GEMINI_LOCATION
        # `timeout` is ignored. HttpOptions(timeout=...) is also sent to Vertex as a
        # deadline, and with it set, calls that take 3 s without it ran until the
        # deadline and failed with 504 DEADLINE_EXCEEDED (2026-10-23, global endpoint).
        self.client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=self.location)

    @classmethod
    def from_config(cls, config, timeout=None):
        return cls(timeout=timeout, location=config.location)

    def chat(self, model, messages, tools, options=None):
        if tools:
            raise ProviderError("Gemini can't use tools yet (IDEA-008).")
        options = options or {}
        system = [m["content"] for m in messages if m["role"] == "system"]
        contents = [_content(m) for m in messages if m["role"] != "system"]
        config = types.GenerateContentConfig(
            system_instruction="\n\n".join(system) or None,
            # No tools are passed, so automatic function calling only logs a warning
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            **{name: options[name] for name in GENERATION_OPTIONS if name in options},
        )
        if "thinking_budget" in options:
            config.thinking_config = types.ThinkingConfig(thinking_budget=options["thinking_budget"])

        response = self.client.models.generate_content(model=model, contents=contents, config=config)
        if not response.text:
            raise ProviderError(f"{model} returned no text.")
        # A reply cut off by the token limit or a safety filter would be saved half-written
        finish = response.candidates[0].finish_reason if response.candidates else None
        if finish not in (None, types.FinishReason.STOP):
            raise ProviderError(f"{model} stopped early ({finish}).")
        usage = response.usage_metadata
        return ChatResult(
            message={"role": "assistant", "content": response.text},
            input_tokens=(usage and usage.prompt_token_count) or 0,
            # Thinking is billed as output
            output_tokens=((usage and usage.candidates_token_count) or 0) + ((usage and usage.thoughts_token_count) or 0),
        )


def _content(message):
    if message["role"] not in ("user", "assistant"):
        raise ProviderError(f"Gemini can't take {message['role']} messages yet (IDEA-008).")
    role = "model" if message["role"] == "assistant" else "user"
    return types.Content(role=role, parts=[types.Part(text=message.get("content") or "")])
