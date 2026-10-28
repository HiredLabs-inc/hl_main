import base64
import json
from unittest import mock

from django.test import TestCase, override_settings
from google.genai import types

from hlagents.providers import GeminiProvider, ProviderError, get_provider
from hlagents.providers.gemini import DUMMY_SIGNATURE
from hlagents.tests.fakes import make_provider
from hlagents.tools import tool_schema


def gemini_response(text="Hello", prompt_tokens=12, output_tokens=3, thinking_tokens=None,
                    finish=types.FinishReason.STOP, parts=None, usage=True):
    if parts is None:
        parts = [types.Part(text=text)] if text else []
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens, candidates_token_count=output_tokens, thoughts_token_count=thinking_tokens
        ) if usage else None,
    )


def function_call(name="web_search", signature=None, call_id=None, **args):
    return types.Part(
        function_call=types.FunctionCall(name=name, args=args or {"query": "grants"}, id=call_id),
        thought_signature=signature,
    )


@override_settings(GCP_PROJECT_ID="test-project", GEMINI_LOCATION="global")
class GeminiProviderTest(TestCase):
    def setUp(self):
        patcher = mock.patch("hlagents.providers.gemini.genai.Client")
        self.client_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = self.client_class.return_value
        self.client.models.generate_content.return_value = gemini_response()

    def sent(self):
        return self.client.models.generate_content.call_args.kwargs

    def test_client_uses_vertex_with_the_default_location_and_no_deadline(self):
        GeminiProvider(timeout=45)
        # A timeout is sent to Vertex as a deadline, which made calls hang until it expired
        self.client_class.assert_called_once_with(vertexai=True, project="test-project", location="global")

    def test_get_provider_uses_the_configs_location(self):
        config = make_provider(kind="gemini", location="us-central1")
        provider = get_provider(config, timeout=30)
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(self.client_class.call_args.kwargs["location"], "us-central1")

    def test_chat_maps_messages_options_and_tokens(self):
        messages = [
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Again"},
        ]
        options = {"temperature": 0.5, "top_p": 0.8, "top_k": 40, "max_output_tokens": 1024, "thinking_budget": 0}
        result = GeminiProvider().chat("gemini-test", messages, None, options)

        kwargs = self.sent()
        self.assertEqual(kwargs["model"], "gemini-test")
        self.assertEqual([(c.role, c.parts[0].text) for c in kwargs["contents"]], [("user", "Hi"), ("model", "Hello"), ("user", "Again")])
        config = kwargs["config"]
        self.assertEqual(config.system_instruction, "Be brief.")
        self.assertEqual((config.temperature, config.top_p, config.top_k, config.max_output_tokens), (0.5, 0.8, 40, 1024))
        self.assertEqual(config.thinking_config.thinking_budget, 0)
        self.assertTrue(config.automatic_function_calling.disable)
        self.assertIsNone(config.tools)

        self.assertEqual(result.message, {"role": "assistant", "content": "Hello"})
        self.assertEqual((result.input_tokens, result.output_tokens), (12, 3))

    def test_no_options(self):
        GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], [])
        config = self.sent()["config"]
        self.assertIsNone(config.temperature)
        self.assertIsNone(config.thinking_config)
        self.assertIsNone(config.system_instruction)
        self.assertIsNone(config.tools)

    def test_tool_schemas_become_function_declarations(self):
        tools = [tool_schema("web_search", "Search for grants."), tool_schema("read_page")]
        GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], tools)

        config = self.sent()["config"]
        [tool] = config.tools
        declarations = tool.function_declarations
        self.assertEqual([d.name for d in declarations], ["web_search", "read_page"])
        self.assertEqual(declarations[0].description, "Search for grants.")
        self.assertEqual(declarations[0].parameters_json_schema, tools[0]["function"]["parameters"])
        # The loop runs the tools
        self.assertTrue(config.automatic_function_calling.disable)

    def test_a_reply_with_tool_calls_and_no_text(self):
        self.client.models.generate_content.return_value = gemini_response(
            parts=[function_call(signature=b"sig-1", call_id="call-1"), function_call("read_page", url="https://a.example.org/x")]
        )
        result = GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], [tool_schema("web_search")])
        self.assertEqual(result.message, {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "web_search", "arguments": {"query": "grants"}}, "id": "call-1",
                 "thought_signature": base64.b64encode(b"sig-1").decode()},
                {"function": {"name": "read_page", "arguments": {"url": "https://a.example.org/x"}}},
            ],
        })
        # The message is stored in a JSONField
        json.dumps(result.message)

    def test_thought_parts_are_not_the_answer(self):
        self.client.models.generate_content.return_value = gemini_response(
            parts=[types.Part(text="Let me think", thought=True), types.Part(text="[]")]
        )
        result = GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)
        self.assertEqual(result.message["content"], "[]")

    def test_tool_calls_and_replies_round_trip(self):
        signature = base64.b64encode(b"sig-1").decode()
        messages = [
            {"role": "system", "content": "Find grants."},
            {"role": "user", "content": "Find 2."},
            {"role": "assistant", "content": "Searching.", "tool_calls": [
                {"function": {"name": "web_search", "arguments": {"query": "grants"}}, "id": "call-1", "thought_signature": signature},
                {"function": {"name": "read_page", "arguments": {"url": "https://a.example.org/x"}}, "id": "call-2"},
            ]},
            {"role": "tool", "tool_name": "web_search", "content": json.dumps({"results": []})},
            {"role": "tool", "tool_name": "read_page", "content": json.dumps({"error": "Couldn't read it"})},
            {"role": "user", "content": "You're at the step limit.", "note": "Step limit"},
        ]
        GeminiProvider().chat("gemini-test", messages, None)

        contents = self.sent()["contents"]
        self.assertEqual([c.role for c in contents], ["user", "model", "user", "user"])
        model = contents[1].parts
        self.assertEqual(model[0].text, "Searching.")
        self.assertEqual((model[1].function_call.name, model[1].function_call.args, model[1].function_call.id),
                         ("web_search", {"query": "grants"}, "call-1"))
        self.assertEqual(model[1].thought_signature, b"sig-1")
        # Only the first call of a step carries a signature
        self.assertIsNone(model[2].thought_signature)

        # Both replies are one turn, and the note another: Vertex refuses a turn with both
        replies = contents[2].parts
        self.assertEqual(
            [(p.function_response.name, p.function_response.id, p.function_response.response) for p in replies],
            [("web_search", "call-1", {"results": []}), ("read_page", "call-2", {"error": "Couldn't read it"})],
        )
        self.assertEqual([p.text for p in contents[3].parts], ["You're at the step limit."])

    def test_a_call_from_another_provider_gets_the_dummy_signature(self):
        messages = [
            {"role": "user", "content": "Find 2."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search", "arguments": '{"query": "grants"}'}}]},
            {"role": "tool", "tool_name": "web_search", "content": "not json"},
        ]
        GeminiProvider().chat("gemini-test", messages, None)

        contents = self.sent()["contents"]
        [call] = contents[1].parts
        self.assertEqual(call.thought_signature, DUMMY_SIGNATURE)
        self.assertEqual(call.function_call.args, {"query": "grants"})
        self.assertEqual(contents[2].parts[0].function_response.response, {"output": "not json"})

    def test_unknown_roles_are_refused(self):
        with self.assertRaisesMessage(ProviderError, "can't take developer messages"):
            GeminiProvider().chat("gemini-test", [{"role": "developer", "content": "Hi"}], None)

    def test_empty_reply_is_an_error(self):
        self.client.models.generate_content.return_value = gemini_response(text=None)
        with self.assertRaisesMessage(ProviderError, "no text"):
            GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)

    def test_thinking_tokens_count_as_output(self):
        self.client.models.generate_content.return_value = gemini_response(output_tokens=40, thinking_tokens=700)
        result = GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)
        self.assertEqual(result.output_tokens, 740)

    def test_reply_cut_off_at_the_token_limit_is_an_error(self):
        self.client.models.generate_content.return_value = gemini_response(
            text='["Diagnosed and repaired', finish=types.FinishReason.MAX_TOKENS
        )
        with self.assertRaisesMessage(ProviderError, "stopped early"):
            GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)

    def test_malformed_function_call_is_an_error(self):
        self.client.models.generate_content.return_value = gemini_response(
            text=None, finish=types.FinishReason.MALFORMED_FUNCTION_CALL
        )
        with self.assertRaisesMessage(ProviderError, "MALFORMED_FUNCTION_CALL"):
            GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], [tool_schema("web_search")])

    def test_missing_usage_counts_zero(self):
        self.client.models.generate_content.return_value = gemini_response(usage=False)
        result = GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)
        self.assertEqual((result.input_tokens, result.output_tokens), (0, 0))
