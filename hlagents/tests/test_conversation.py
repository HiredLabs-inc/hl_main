import json

from django.test import SimpleTestCase

from hlagents.conversation import conversation


class ConversationTest(SimpleTestCase):
    def test_entries(self):
        messages = [
            {"role": "system", "content": "Be useful."},
            {"role": "user", "content": "Find grants."},
            {
                "role": "assistant",
                "content": "",
                "thinking": "Let me search.",
                "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "veteran grants"}}}],
            },
            {"role": "tool", "tool_name": "web_search", "content": json.dumps({"results": [{}, {}]})},
            {"role": "tool", "tool_name": "web_search", "content": json.dumps({"error": "rate limited"})},
            {"role": "assistant", "content": "[]"},
        ]
        self.assertEqual(
            [(e["kind"], e["text"]) for e in conversation(messages)],
            [
                ("system", "System prompt"),
                ("user", "Find grants."),
                ("thinking", "Thinking"),
                ("search", "veteran grants"),
                ("result", "2 results"),
                ("result", "Error: rate limited"),
                ("answer", "[]"),
            ],
        )
