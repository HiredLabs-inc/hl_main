import json

from django.test import SimpleTestCase

from hlagents.conversation import conversation, note, tool_text


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
            {"role": "user", "content": "Only Texas."},
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
                ("user", "Only Texas."),
            ],
        )
        self.assertEqual([e["detail"] for e in conversation(messages) if e["kind"] == "user"], ["Request", "Follow-up"])

    def test_notes_and_pages(self):
        messages = [
            {"role": "user", "content": "Find grants."},
            note("We already know these funders: ...", "Already known"),
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "read_page", "arguments": {"url": "https://a.org/grants"}}}],
            },
            {"role": "tool", "tool_name": "read_page", "content": json.dumps({"url": "https://a.org/grants", "content": "x"})},
            {"role": "user", "content": "Only Texas."},
        ]
        entries = conversation(messages)
        self.assertEqual(
            [(e["kind"], e["text"], e.get("label")) for e in entries],
            [
                ("user", "Find grants.", None),
                ("note", "Already known", None),
                ("search", "https://a.org/grants", "Read"),
                ("result", "https://a.org/grants", "Page"),
                ("user", "Only Texas.", None),
            ],
        )
        # A note isn't counted as staff's request
        self.assertEqual(entries[-1]["detail"], "Follow-up")

    def test_tool_text_is_only_tool_output(self):
        messages = [{"role": "user", "content": "a@b.org"}, {"role": "tool", "content": "c@d.org"}, {"role": "tool", "content": "e"}]
        self.assertEqual(tool_text(messages), "c@d.org\ne")
