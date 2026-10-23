from ollama import Client

from .base import ChatProvider, ChatResult

OLLAMA_CLOUD_URL = "https://ollama.com"
# Seconds to wait for one reply, so a stuck call can't outlast the worker
TIMEOUT = 180


class OllamaProvider(ChatProvider):
    def __init__(self, base_url="", api_key=""):
        super().__init__(base_url or OLLAMA_CLOUD_URL, api_key)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self.client = Client(host=self.base_url, headers=headers, timeout=TIMEOUT)

    def chat(self, model, messages, tools):
        response = self.client.chat(model=model, messages=messages, tools=tools or None)
        return ChatResult(
            message=response.message.model_dump(exclude_none=True),
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )
