from ollama import Client

from .base import ChatProvider, ChatResult

OLLAMA_CLOUD_URL = "https://ollama.com"
# Seconds to wait for one reply, so a stuck call can't outlast the worker
TIMEOUT = 180
# ChatProvider option names that Ollama spells differently
OPTION_NAMES = {"max_output_tokens": "num_predict"}
OLLAMA_OPTIONS = {"temperature", "top_p", "top_k", "num_predict"}


class OllamaProvider(ChatProvider):
    def __init__(self, base_url="", api_key="", timeout=None):
        super().__init__(base_url or OLLAMA_CLOUD_URL, api_key)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self.client = Client(host=self.base_url, headers=headers, timeout=timeout or TIMEOUT)

    def chat(self, model, messages, tools, options=None):
        kwargs = {}
        if options := _ollama_options(options):
            kwargs["options"] = options
        response = self.client.chat(model=model, messages=messages, tools=tools or None, **kwargs)
        return ChatResult(
            message=response.message.model_dump(exclude_none=True),
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )


def _ollama_options(options):
    renamed = {OPTION_NAMES.get(name, name): value for name, value in (options or {}).items()}
    return {name: value for name, value in renamed.items() if name in OLLAMA_OPTIONS}
