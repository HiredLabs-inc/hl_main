import base64
import json

from django.conf import settings
from google import genai
from google.genai import types

from .base import ChatProvider, ChatResult, ProviderError

GENERATION_OPTIONS = ("temperature", "top_p", "top_k", "max_output_tokens")
# Sent in place of a thought signature on a tool call made by another provider,
# such as a run that started on Ollama. Google documents this value for history
# that didn't come from Gemini.
DUMMY_SIGNATURE = b"skip_thought_signature_validator"


class GeminiProvider(ChatProvider):
    """Gemini on Vertex AI, with Application Default Credentials (no API key).

    Translates the canonical messages to Gemini contents and back, tool calls
    included (docs/gcp-agents.md §3.1). The loop runs the tools, so automatic
    function calling is always off."""

    def __init__(self, base_url="", api_key="", timeout=None, location=""):
        super().__init__(base_url, api_key)
        self.location = location or settings.GEMINI_LOCATION
        # `timeout` is ignored. HttpOptions(timeout=...) is also sent to Vertex as a
        # deadline, and with it set, calls that take 3 s without it ran until the
        # deadline and failed with 504 DEADLINE_EXCEEDED (2026-10-23, global endpoint).
        # Agent runs limit each call with call_with_limit instead.
        self.client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=self.location)

    @classmethod
    def from_config(cls, config, timeout=None):
        return cls(timeout=timeout, location=config.location)

    def chat(self, model, messages, tools, options=None):
        options = options or {}
        system = [m["content"] for m in messages if m["role"] == "system"]
        config = types.GenerateContentConfig(
            system_instruction="\n\n".join(system) or None,
            tools=[_tool(tools)] if tools else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            **{name: options[name] for name in GENERATION_OPTIONS if name in options},
        )
        if "thinking_budget" in options:
            config.thinking_config = types.ThinkingConfig(thinking_budget=options["thinking_budget"])

        contents = _contents([m for m in messages if m["role"] != "system"])
        response = self.client.models.generate_content(model=model, contents=contents, config=config)
        candidate = response.candidates[0] if response.candidates else None
        parts = (candidate and candidate.content and candidate.content.parts) or []
        text = "".join(part.text for part in parts if part.text and not part.thought)
        calls = [_tool_call(part) for part in parts if part.function_call]
        # A reply cut off by the token limit or a safety filter would be saved half-written
        finish = candidate.finish_reason if candidate else None
        if finish not in (None, types.FinishReason.STOP):
            raise ProviderError(f"{model} stopped early ({finish}).")
        if not text and not calls:
            raise ProviderError(f"{model} returned no text.")

        message = {"role": "assistant", "content": text}
        if calls:
            message["tool_calls"] = calls
        usage = response.usage_metadata
        return ChatResult(
            message=message,
            input_tokens=(usage and usage.prompt_token_count) or 0,
            # Thinking is billed as output
            output_tokens=((usage and usage.candidates_token_count) or 0) + ((usage and usage.thoughts_token_count) or 0),
        )


def _tool(tools):
    """One Gemini Tool declaring every canonical function schema."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=function["name"],
                description=function.get("description"),
                parameters_json_schema=function.get("parameters"),
            )
            for function in (tool["function"] for tool in tools)
        ]
    )


def _contents(messages):
    """Gemini contents for the non-system messages. Tool replies in a row are one
    turn, since Gemini expects all of a step's replies together, and take the
    ids of the calls before them, in order. Text gets a turn of its own: Vertex
    refuses a turn with both ("Requests ending with a model turn are not
    supported", 2026-10-28), but takes user turns in a row."""
    contents = []
    call_ids = []
    previous = None
    for message in messages:
        role = message["role"]
        if role == "assistant":
            gemini_role = "model"
            calls = message.get("tool_calls") or []
            parts = [types.Part(text=message["content"])] if message.get("content") else []
            parts += [_function_call(call, first=index == 0) for index, call in enumerate(calls)]
            call_ids = [call.get("id") for call in calls]
        elif role == "tool":
            gemini_role = "user"
            parts = [_function_response(message, call_ids.pop(0) if call_ids else None)]
        elif role == "user":
            gemini_role = "user"
            parts = [types.Part(text=message.get("content") or "")]
        else:
            raise ProviderError(f"Gemini can't take {role} messages.")
        if not parts:
            continue
        if role == "tool" and previous == "tool":
            contents[-1].parts.extend(parts)
        else:
            contents.append(types.Content(role=gemini_role, parts=parts))
        previous = role
    return contents


def _function_call(call, first):
    """A canonical tool call as a Gemini part. Gemini 3 refuses a step whose first
    call comes back without the thought signature it was sent with."""
    function = call.get("function", {})
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if signature := call.get("thought_signature"):
        signature = base64.b64decode(signature)
    elif first:
        signature = DUMMY_SIGNATURE
    return types.Part(
        function_call=types.FunctionCall(name=function.get("name", ""), args=arguments, id=call.get("id")),
        thought_signature=signature or None,
    )


def _function_response(message, call_id):
    """A tool reply as a Gemini part. Tools return a JSON object, which is the
    response as is, so errors arrive under "error" as Gemini expects."""
    try:
        output = json.loads(message.get("content") or "{}")
    except json.JSONDecodeError:
        output = message.get("content")
    part = types.Part.from_function_response(
        name=message.get("tool_name") or "", response=output if isinstance(output, dict) else {"output": output}
    )
    part.function_response.id = call_id
    return part


def _tool_call(part):
    """A Gemini function-call part as a canonical tool call. The thought
    signature is kept, base64-encoded, so the next call can send it back."""
    call = {"function": {"name": part.function_call.name, "arguments": dict(part.function_call.args or {})}}
    if part.function_call.id:
        call["id"] = part.function_call.id
    if part.thought_signature:
        call["thought_signature"] = base64.b64encode(part.thought_signature).decode()
    return call
