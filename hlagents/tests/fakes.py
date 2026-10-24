import itertools
import json

from django.contrib.auth.models import User

from hlagents import services
from hlagents.models import AgentConfig, ProviderConfig
from hlagents.providers import ChatProvider, ChatResult


class FakeProvider(ChatProvider):
    """Returns scripted replies in order and records what it was sent. A reply
    that is an exception is raised instead."""

    def __init__(self, *replies):
        super().__init__()
        self.replies = list(replies)
        self.calls = []

    def chat(self, model, messages, tools, options=None):
        self.calls.append({"model": model, "messages": [dict(m) for m in messages], "tools": tools, "options": options})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def tool_call(name="web_search", tokens=(100, 20), **arguments):
    return ChatResult(
        message={
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": arguments or {"query": "grants"}}}],
        },
        input_tokens=tokens[0],
        output_tokens=tokens[1],
    )


def answer(candidates, fenced=False, tokens=(200, 50)):
    text = candidates if isinstance(candidates, str) else json.dumps(candidates)
    if fenced:
        text = f"```json\n{text}\n```"
    return ChatResult(message={"role": "assistant", "content": text}, input_tokens=tokens[0], output_tokens=tokens[1])


_ids = itertools.count(1)


def make_provider(**kwargs):
    return ProviderConfig.objects.create(
        **{"name": f"Test provider {next(_ids)}", "kind": "ollama", "secret_env": "", **kwargs}
    )


def make_config(agent_type="funding", provider=None, **kwargs):
    return AgentConfig.objects.create(
        **{
            "name": f"Test {agent_type} {next(_ids)}",
            "agent_type": agent_type,
            "provider": provider or make_provider(),
            "model": "test-model",
            "system_prompt": "You find things.",
            "default_request": "Find 2 things.",
            "tools": ["web_search"],
            **kwargs,
        }
    )


def cite(run, candidates):
    """Add a tool result that mentions the candidates, as if the agent had found
    them, so they pass the check against sources."""
    run.messages.append({"role": "tool", "tool_name": "web_search", "content": json.dumps({"results": candidates})})
    run.save()
    return candidates


def make_run(config=None, **kwargs):
    user = User.objects.get_or_create(username="staff@example.com", defaults={"is_staff": True})[0]
    return services.create_run(config or make_config(), user, **kwargs)


FUNDERS = [
    {
        "org_name": "Acme Foundation",
        "funding_amount": 50000,
        "application_deadline": "2026-12-01",
        "application_url": "https://acme.example.org/grants",
        "justification": "Funds workforce training for veterans.",
    },
    {
        "org_name": "  Bolt  Giving ",
        "funding_amount": "$25,000 - $40,000",
        "application_deadline": "Rolling",
        "application_url": "https://bolt.example.org/giving",
        "justification": "Corporate giving for tech education.",
    },
]
