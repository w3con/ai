#!/usr/bin/env python3
"""Offline tests for webscrape provider mapping, fallthrough, truncation and exit codes."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "webscrape"
LOADER = importlib.machinery.SourceFileLoader("candidate_webscrape", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("candidate_webscrape", LOADER)
WEBSCRAPE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(WEBSCRAPE)

URL = "https://example.test/page"


class WebScrapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="webscrape-test-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_main(self, argv, providers, env=None):
        """Run main() with the given provider chain, an isolated cache and no throttling."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(WEBSCRAPE, "PROVIDERS", providers), \
             mock.patch.object(WEBSCRAPE, "_throttle_wait"), \
             mock.patch.object(WEBSCRAPE, "load_dotenv", return_value=env or {}), \
             mock.patch.dict("os.environ", {}, clear=False), \
             mock.patch.object(WEBSCRAPE, "CACHE_DIR", self.root / "cache"), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = WEBSCRAPE.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_firecrawl_maps_markdown_and_sends_bearer_key(self) -> None:
        body = json.dumps({"success": True, "data": {
            "markdown": "# Synthetic page\n\nBody text.",
            "metadata": {"title": "Synthetic title"}}})
        fetch = mock.Mock(return_value=(200, body.encode(), "application/json"))
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry", fetch):
            page = WEBSCRAPE.scrape_firecrawl(URL, "fixture-key")
        self.assertEqual(page, {"title": "Synthetic title", "content": "# Synthetic page\n\nBody text."})
        request = fetch.call_args.args[1]
        self.assertEqual(request.full_url, "https://api.firecrawl.dev/v2/scrape")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-key")
        self.assertEqual(json.loads(request.data),
                         {"url": URL, "formats": ["markdown"], "onlyMainContent": True})

    def test_tavily_maps_raw_content_and_sends_key_in_body(self) -> None:
        body = json.dumps({"results": [{"url": URL, "raw_content": "Synthetic text."}],
                           "failed_results": []})
        fetch = mock.Mock(return_value=(200, body.encode(), "application/json"))
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry", fetch):
            page = WEBSCRAPE.scrape_tavily(URL, "fixture-key")
        self.assertEqual(page, {"title": "", "content": "Synthetic text."})
        request = fetch.call_args.args[1]
        self.assertEqual(request.full_url, "https://api.tavily.com/extract")
        self.assertEqual(json.loads(request.data), {
            "api_key": "fixture-key", "urls": [URL], "extract_depth": "basic", "format": "markdown"})

    def test_tavily_failed_results_counts_as_failure(self) -> None:
        body = json.dumps({"results": [], "failed_results": [{"url": URL, "error": "blocked"}]})
        fetch = mock.Mock(return_value=(200, body.encode(), "application/json"))
        stderr = io.StringIO()
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry", fetch), \
             contextlib.redirect_stderr(stderr):
            page = WEBSCRAPE.scrape_tavily(URL, "fixture-key")
        self.assertIsNone(page)
        self.assertIn("blocked", stderr.getvalue())

    def test_plain_converts_html_and_drops_script_style_nav(self) -> None:
        markup = ("<html><head><title> Synthetic  title </title><style>p{color:red}</style></head>"
                  "<body><nav>Menu item</nav><script>var x = 1;</script>"
                  "<h1>Heading</h1><p>First &amp; second.</p><p>Third</p></body></html>")
        fetch = mock.Mock(return_value=(200, markup.encode(), "text/html; charset=utf-8"))
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry", fetch):
            page = WEBSCRAPE.scrape_plain(URL, None)
        self.assertEqual(page["title"], "Synthetic title")
        self.assertEqual(page["content"], "Heading\n\nFirst & second.\n\nThird")

    def test_plain_returns_non_html_text_as_is_and_rejects_binary(self) -> None:
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry",
                               return_value=(200, b"line one\nline two\n", "text/plain")):
            self.assertEqual(WEBSCRAPE.scrape_plain(URL, None)["content"], "line one\nline two")
        stderr = io.StringIO()
        with mock.patch.object(WEBSCRAPE, "_fetch_with_retry",
                               return_value=(200, b"%PDF-1.7 synthetic", "application/pdf")), \
             contextlib.redirect_stderr(stderr):
            self.assertIsNone(WEBSCRAPE.scrape_plain(URL, None))
        self.assertIn("application/pdf", stderr.getvalue())

    def test_failed_provider_falls_through_and_notice_names_it(self) -> None:
        failing = mock.Mock(return_value=None)
        working = mock.Mock(return_value={"title": "T", "content": "Synthetic text."})
        providers = [
            {"name": "first", "key_env": None, "func": failing},
            {"name": "second", "key_env": None, "func": working},
        ]
        code, out, err = self.run_main([URL, "--no-cache"], providers)
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["provider"], "second")
        self.assertEqual(result["content"], "Synthetic text.")
        self.assertFalse(result["cached"])
        self.assertIn("NOTICE", err)
        self.assertIn("first:", err)

    def test_provider_without_key_is_skipped_and_named(self) -> None:
        keyed = mock.Mock(side_effect=AssertionError("called without a key"))
        plain = mock.Mock(return_value={"title": "", "content": "Synthetic text."})
        providers = [
            {"name": "keyed", "key_env": "SYNTHETIC_SCRAPE_KEY", "func": keyed},
            {"name": "plain", "key_env": None, "func": plain},
        ]
        with mock.patch.dict("os.environ", {"SYNTHETIC_SCRAPE_KEY": ""}):
            code, out, err = self.run_main([URL, "--no-cache"], providers)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["provider"], "plain")
        self.assertIn("missing SYNTHETIC_SCRAPE_KEY", err)
        keyed.assert_not_called()

    def test_truncation_sets_flag_and_length(self) -> None:
        providers = [{"name": "only", "key_env": None,
                      "func": lambda *_: {"title": "T", "content": "x" * 50}}]
        code, out, _ = self.run_main([URL, "--no-cache", "--max-chars", "10"], providers)
        result = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual((result["content"], result["chars"], result["truncated"]), ("x" * 10, 10, True))

    def test_text_output_prints_provider_title_url_then_content(self) -> None:
        providers = [{"name": "only", "key_env": None,
                      "func": lambda *_: {"title": "Synthetic title", "content": "Body."}}]
        code, out, _ = self.run_main([URL, "--no-cache", "--text"], providers)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["provider: only  (cached: False)", "title: Synthetic title",
                                            f"url: {URL}", "", "Body."])

    def test_cache_hit_returns_without_network_call_and_is_marked_cached(self) -> None:
        func = mock.Mock(return_value={"title": "T", "content": "Synthetic text."})
        providers = [{"name": "only", "key_env": None, "func": func}]
        code, _, _ = self.run_main([URL], providers)
        self.assertEqual(code, 0)
        self.assertEqual(func.call_count, 1)
        code, out, _ = self.run_main([URL], providers)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["cached"])
        self.assertEqual(func.call_count, 1)

    def test_non_http_url_and_missing_url_exit_2(self) -> None:
        for argv in (["ftp://example.test/file"], ["file:///etc/hosts"], ["example.test"], []):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    WEBSCRAPE.parse_args(argv)
                self.assertEqual(raised.exception.code, 2)

    def test_all_providers_failing_exits_3_with_english_notice(self) -> None:
        providers = [
            {"name": "first", "key_env": None, "func": lambda *_: None},
            {"name": "second", "key_env": None, "func": lambda *_: None},
        ]
        code, out, err = self.run_main([URL, "--no-cache"], providers)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("NOTICE", err)
        self.assertIn("all providers were exhausted", err)
        self.assertTrue(err.isascii())


if __name__ == "__main__":
    unittest.main()
