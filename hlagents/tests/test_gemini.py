from unittest import mock

from django.test import TestCase, override_settings
from google.genai import types

from hlagents.providers import GeminiProvider, ProviderError, get_provider
from hlagents.tests.fakes import make_provider


def gemini_response(text="Hello", prompt_tokens=12, output_tokens=3, thinking_tokens=None, finish=types.FinishReason.STOP):
    return mock.Mock(
        text=text,
        candidates=[mock.Mock(finish_reason=finish)],
        usage_metadata=mock.Mock(
            prompt_token_count=prompt_tokens, candidates_token_count=output_tokens, thoughts_token_count=thinking_tokens
        ),
    )


@override_settings(GCP_PROJECT_ID="test-project", GEMINI_LOCATION="global")
class GeminiProviderTest(TestCase):
    def setUp(self):
        patcher = mock.patch("hlagents.providers.gemini.genai.Client")
        self.client_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = self.client_class.return_value
        self.client.models.generate_content.return_value = gemini_response()

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

        kwargs = self.client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-test")
        self.assertEqual([(c.role, c.parts[0].text) for c in kwargs["contents"]], [("user", "Hi"), ("model", "Hello"), ("user", "Again")])
        config = kwargs["config"]
        self.assertEqual(config.system_instruction, "Be brief.")
        self.assertEqual((config.temperature, config.top_p, config.top_k, config.max_output_tokens), (0.5, 0.8, 40, 1024))
        self.assertEqual(config.thinking_config.thinking_budget, 0)
        self.assertTrue(config.automatic_function_calling.disable)

        self.assertEqual(result.message, {"role": "assistant", "content": "Hello"})
        self.assertEqual((result.input_tokens, result.output_tokens), (12, 3))

    def test_no_options(self):
        GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], [])
        config = self.client.models.generate_content.call_args.kwargs["config"]
        self.assertIsNone(config.temperature)
        self.assertIsNone(config.thinking_config)
        self.assertIsNone(config.system_instruction)

    def test_tools_are_refused(self):
        with self.assertRaisesMessage(ProviderError, "IDEA-008"):
            GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], [{"type": "function"}])
        self.client.models.generate_content.assert_not_called()

    def test_tool_messages_are_refused(self):
        messages = [{"role": "user", "content": "Hi"}, {"role": "tool", "tool_name": "web_search", "content": "{}"}]
        with self.assertRaisesMessage(ProviderError, "IDEA-008"):
            GeminiProvider().chat("gemini-test", messages, None)

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

    def test_missing_usage_counts_zero(self):
        self.client.models.generate_content.return_value = mock.Mock(text="Hi", candidates=[], usage_metadata=None)
        result = GeminiProvider().chat("gemini-test", [{"role": "user", "content": "Hi"}], None)
        self.assertEqual((result.input_tokens, result.output_tokens), (0, 0))
