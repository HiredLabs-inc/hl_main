from unittest import mock

from django.test import SimpleTestCase, override_settings

from hlagents.tools import ToolError
from hlagents.tools.read_page import PAGE_LENGTH, read_page
from hlagents.tools.web_search import SNIPPET_LENGTH, web_search


@override_settings(TAVILY_API_KEY="tavily-key")
@mock.patch("hlagents.tools.web_search.TavilyClient")
class WebSearchTest(SimpleTestCase):
    def test_returns_only_title_url_and_a_capped_snippet(self, tavily):
        tavily.return_value.search.return_value = {
            "query": "q",
            "images": ["x"],
            "results": [{"title": "T", "url": "https://a.org/p", "content": "c" * 5000, "score": 0.5, "raw_content": None}],
        }
        self.assertEqual(
            web_search("q"), {"results": [{"title": "T", "url": "https://a.org/p", "content": "c" * SNIPPET_LENGTH}]}
        )

    def test_max_results_is_clamped(self, tavily):
        tavily.return_value.search.return_value = {"results": []}
        web_search("q", max_results=99)
        tavily.return_value.search.assert_called_once_with(query="q", search_depth="advanced", max_results=20)


@override_settings(TAVILY_API_KEY="tavily-key")
@mock.patch("hlagents.tools.web_search.TavilyClient")
class ReadPageTest(SimpleTestCase):
    def test_returns_the_page_text(self, tavily):
        tavily.return_value.extract.return_value = {
            "results": [{"url": "https://a.org/grants", "raw_content": "Apply by June 1."}],
            "failed_results": [],
        }
        self.assertEqual(
            read_page("https://a.org/grants"),
            {"url": "https://a.org/grants", "content": "Apply by June 1.", "truncated": False},
        )
        tavily.return_value.extract.assert_called_once_with(urls=["https://a.org/grants"], format="markdown")

    def test_long_pages_are_truncated(self, tavily):
        tavily.return_value.extract.return_value = {"results": [{"url": "u", "raw_content": "x" * (PAGE_LENGTH + 1)}]}
        page = read_page("u")
        self.assertEqual((len(page["content"]), page["truncated"]), (PAGE_LENGTH, True))

    def test_a_page_that_cant_be_read_is_an_error(self, tavily):
        tavily.return_value.extract.return_value = {"results": [], "failed_results": [{"url": "u", "error": "403"}]}
        with self.assertRaisesMessage(ToolError, "Couldn't read u: 403"):
            read_page("u")

    @override_settings(TAVILY_API_KEY="")
    def test_needs_the_key(self, tavily):
        with self.assertRaisesMessage(ToolError, "TAVILY_API_KEY isn't set."):
            read_page("u")
