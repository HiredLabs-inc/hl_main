import os
from unittest import mock

from django.test import TestCase
from ollama import ChatResponse, Message

from hlagents.providers import OllamaProvider, ProviderError, get_provider
from hlagents.tests.fakes import make_provider


class OllamaProviderTest(TestCase):
    def test_defaults_to_ollama_cloud_with_bearer_key(self):
        with mock.patch("hlagents.providers.ollama.Client") as client:
            OllamaProvider(api_key="secret")
        client.assert_called_once_with(host="https://ollama.com", headers={"Authorization": "Bearer secret"})

    def test_local_server_without_key(self):
        with mock.patch("hlagents.providers.ollama.Client") as client:
            OllamaProvider(base_url="http://ollama:11434")
        client.assert_called_once_with(host="http://ollama:11434", headers=None)

    def test_chat_maps_the_response(self):
        response = ChatResponse(
            model="gpt-oss:120b",
            prompt_eval_count=120,
            eval_count=30,
            message=Message(
                role="assistant",
                content="",
                tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(name="web_search", arguments={"query": "q"}))],
            ),
        )
        provider = OllamaProvider(api_key="secret")
        tools = [{"type": "function", "function": {"name": "web_search"}}]
        with mock.patch.object(provider.client, "chat", return_value=response) as chat:
            result = provider.chat("gpt-oss:120b", [{"role": "user", "content": "hi"}], tools)

        chat.assert_called_once_with(model="gpt-oss:120b", messages=[{"role": "user", "content": "hi"}], tools=tools)
        self.assertEqual(
            result.message,
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "q"}}}],
            },
        )
        self.assertEqual((result.input_tokens, result.output_tokens), (120, 30))


class GetProviderTest(TestCase):
    def test_reads_the_key_from_the_named_env_var(self):
        config = make_provider(secret_env="HLAGENTS_TEST_KEY", base_url="https://ollama.example.com")
        with mock.patch.dict(os.environ, {"HLAGENTS_TEST_KEY": "secret"}):
            provider = get_provider(config)
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual((provider.base_url, provider.api_key), ("https://ollama.example.com", "secret"))

    def test_missing_key_is_an_error(self):
        config = make_provider(secret_env="HLAGENTS_TEST_UNSET_KEY")
        with self.assertRaisesMessage(ProviderError, "HLAGENTS_TEST_UNSET_KEY isn't set"):
            get_provider(config)
