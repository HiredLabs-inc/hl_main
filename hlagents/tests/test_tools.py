import socket
from unittest import mock

import requests_mock
from django.test import SimpleTestCase, TestCase

from hlagents.models import TaskCall, TaskConfig
from hlagents.providers import ChatResult
from hlagents.tests.fakes import FakeProvider
from hlagents.tools import ToolError
from hlagents.tools.read_page import MAX_BYTES, PAGE_LENGTH, read_page
from hlagents.tools.web_search import REDIRECT_HOST, SNIPPET_LENGTH, web_search

REDIRECT = f"https://{REDIRECT_HOST}/grounding-api-redirect/"


def make_pdf(*lines):
    """A one-page PDF showing the lines."""
    text = " ".join(f"({line}) Tj 0 -20 Td" for line in lines)
    stream = f"BT /F1 12 Tf 72 720 Td {text} ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, obj)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return pdf + b"trailer\n<< /Root 1 0 R /Size %d >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)


def grounded(*sources, suggestions="<div>chips</div>"):
    return ChatResult(
        message={"role": "assistant", "content": "Acme funds veterans."},
        input_tokens=50,
        output_tokens=10,
        sources=list(sources),
        suggestions=suggestions,
    )


def source(name, snippets=("Funds training.",)):
    return {"title": f"{name}.org", "uri": REDIRECT + name, "snippets": list(snippets)}


@requests_mock.Mocker()
class WebSearchTest(TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        patcher = mock.patch("hlagents.completion.get_provider", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def redirect(self, mocker, name, url):
        mocker.head(REDIRECT + name, status_code=302, headers={"Location": url})

    def test_results_have_real_urls_and_snippets_from_the_sources(self, mocker):
        self.redirect(mocker, "acme", "https://acme.example.org/grants")
        mocker.head(REDIRECT + "gone", status_code=404)
        self.provider.replies = [grounded(source("acme", ["Acme funds training.", "Deadlines are in June."]), source("gone"))]

        output = web_search("veteran grants")

        self.assertEqual(output, {
            "results": [{"title": "acme.org", "url": "https://acme.example.org/grants", "content": "Acme funds training. Deadlines are in June."}],
            "suggestions": "<div>chips</div>",
        })
        # The query is the task's user message, under the task's instructions
        messages = self.provider.calls[0]["messages"]
        self.assertEqual(messages[1], {"role": "user", "content": "veteran grants"})
        self.assertEqual(messages[0]["content"], TaskConfig.objects.get(key="web_search").instructions)
        self.assertTrue(self.provider.calls[0]["options"]["google_search"])
        # Each search is a task call, counted toward the daily cap
        call = TaskCall.objects.get()
        self.assertEqual((call.config.key, call.ok, call.input_tokens), ("web_search", True, 50))

    def test_urls_and_emails_are_removed_from_snippets(self, mocker):
        self.redirect(mocker, "acme", "https://acme.example.org/grants")
        self.provider.replies = [grounded(source("acme", ["Apply at https://made.up/x or write to jo@made.up today."]))]
        [result] = web_search("q")["results"]
        self.assertEqual(result["content"], "Apply at or write to today.")

    def test_results_are_deduped_capped_and_snippets_cut(self, mocker):
        for name in ("a", "b", "c"):
            self.redirect(mocker, name, f"https://{name}.example.org/p")
        self.redirect(mocker, "a2", "https://a.example.org/p")
        self.provider.replies = [grounded(source("a", ["x" * 5000]), source("a2"), source("b"), source("c"), suggestions="")]

        output = web_search("q", max_results=2)

        self.assertEqual([r["url"] for r in output["results"]], ["https://a.example.org/p", "https://b.example.org/p"])
        self.assertEqual(len(output["results"][0]["content"]), SNIPPET_LENGTH)
        self.assertNotIn("suggestions", output)
        # c isn't resolved once there are enough results
        self.assertNotIn(REDIRECT + "c", [r.url for r in mocker.request_history])

    def test_uris_that_arent_redirects_are_kept(self, mocker):
        self.provider.replies = [grounded({"title": "A", "uri": "https://a.example.org/p", "snippets": []})]
        self.assertEqual(web_search("q")["results"][0]["url"], "https://a.example.org/p")

    def test_a_failed_search_is_a_tool_error(self, mocker):
        TaskConfig.objects.filter(key="web_search").update(active=False)
        with self.assertRaisesMessage(ToolError, "The search failed: The Web search for agents task is turned off"):
            web_search("q")


def public_address(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))]


@requests_mock.Mocker()
@mock.patch("hlagents.tools.read_page.socket.getaddrinfo", side_effect=public_address)
class ReadPageTest(SimpleTestCase):
    def page(self, mocker, url, html, content_type="text/html; charset=utf-8", **kwargs):
        mocker.get(url, content=html.encode() if isinstance(html, str) else html, headers={"Content-Type": content_type}, **kwargs)

    def test_returns_the_text_with_links_and_emails(self, mocker, dns):
        self.page(mocker, "https://a.org/grants", """<html><head><title>Grants</title><style>p {color: red}</style>
            <script>var x = 1;</script></head><body><nav><a href="/">Home</a></nav>
            <p>Apply by <b>June 1</b> on <a href="/apply">our form</a>.</p><a href="/x"><img src="i.png"></a>
            <footer>Write to <a href="mailto:jo@a.org">Jo</a><br>or call.</footer></body></html>""")

        page = read_page("https://a.org/grants")

        self.assertEqual(page["url"], "https://a.org/grants")
        self.assertEqual(page["content"], (
            "Grants\nHome (https://a.org/)\nApply by June 1 on our form (https://a.org/apply) .\nhttps://a.org/x\n"
            "Write to Jo (mailto:jo@a.org)\nor call."
        ))
        self.assertFalse(page["truncated"])
        self.assertIn("Mozilla", mocker.last_request.headers["User-Agent"])

    def test_long_pages_are_truncated(self, mocker, dns):
        self.page(mocker, "https://a.org/p", "<p>" + "x" * (PAGE_LENGTH + 1) + "</p>")
        page = read_page("https://a.org/p")
        self.assertEqual((len(page["content"]), page["truncated"]), (PAGE_LENGTH, True))

    def test_only_max_bytes_are_downloaded(self, mocker, dns):
        self.page(mocker, "https://a.org/big.txt", b"y" * (MAX_BYTES + 100), content_type="text/plain")
        page = read_page("https://a.org/big.txt")
        self.assertTrue(page["truncated"])
        self.assertEqual(set(page["content"]), {"y"})

    def test_redirects_are_followed_and_reported(self, mocker, dns):
        mocker.get("https://a.org/old", status_code=301, headers={"Location": "/new"})
        self.page(mocker, "https://a.org/new", "<p>New page</p>")
        self.assertEqual(read_page("https://a.org/old"), {"url": "https://a.org/new", "content": "New page", "truncated": False})

    def test_too_many_redirects(self, mocker, dns):
        mocker.get("https://a.org/loop", status_code=302, headers={"Location": "/loop"})
        with self.assertRaisesMessage(ToolError, "too many redirects"):
            read_page("https://a.org/loop")

    def test_errors_and_other_content_types_are_tool_errors(self, mocker, dns):
        mocker.get("https://a.org/missing", status_code=404)
        self.page(mocker, "https://a.org/logo.png", b"\x89PNG", content_type="image/png")
        with self.assertRaisesMessage(ToolError, "Couldn't read https://a.org/missing: HTTP 404"):
            read_page("https://a.org/missing")
        with self.assertRaisesMessage(ToolError, "Can't read image/png pages."):
            read_page("https://a.org/logo.png")

    def test_pdfs_are_read(self, mocker, dns):
        self.page(mocker, "https://a.org/guide.pdf", make_pdf("Grants up to $50,000.", "Write to jo@a.org"), content_type="application/pdf")
        page = read_page("https://a.org/guide.pdf")
        self.assertEqual(page, {"url": "https://a.org/guide.pdf", "content": "Grants up to $50,000.\nWrite to jo@a.org", "truncated": False})

    def test_a_broken_pdf_is_a_tool_error(self, mocker, dns):
        self.page(mocker, "https://a.org/guide.pdf", b"%PDF-1.7 cut off", content_type="application/pdf")
        with self.assertRaisesMessage(ToolError, "Couldn't read the PDF"):
            read_page("https://a.org/guide.pdf")


class ReadPageGuardTest(SimpleTestCase):
    """The model picks the URL, so it mustn't reach internal addresses."""

    def resolves_to(self, address):
        return mock.patch(
            "hlagents.tools.read_page.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))],
        )

    def test_internal_addresses_are_refused(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.5", "100.64.0.1", "::1", "fd00::1"):
            with self.subTest(address=address), self.resolves_to(address), requests_mock.Mocker() as mocker:
                with self.assertRaisesMessage(ToolError, "isn't a public address"):
                    read_page("http://internal.example.org/")
                self.assertFalse(mocker.called)

    def test_a_redirect_to_an_internal_address_is_refused(self):
        def addresses(host, *args, **kwargs):
            address = "169.254.169.254" if host == "metadata.example.org" else "93.184.215.14"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))]

        with mock.patch("hlagents.tools.read_page.socket.getaddrinfo", side_effect=addresses), requests_mock.Mocker() as mocker:
            mocker.get("https://a.org/go", status_code=302, headers={"Location": "http://metadata.example.org/computeMetadata/v1/"})
            with self.assertRaisesMessage(ToolError, "metadata.example.org isn't a public address"):
                read_page("https://a.org/go")
            self.assertEqual(mocker.call_count, 1)

    def test_other_schemes_and_unknown_hosts_are_refused(self):
        with self.assertRaisesMessage(ToolError, "isn't an http or https URL"):
            read_page("file:///etc/passwd")
        with mock.patch("hlagents.tools.read_page.socket.getaddrinfo", side_effect=socket.gaierror):
            with self.assertRaisesMessage(ToolError, "Couldn't find nowhere.example.org."):
                read_page("https://nowhere.example.org/")
