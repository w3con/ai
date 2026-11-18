#!/usr/bin/env python3
"""Offline tests for provider ordering, private key lookup and cache contracts."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "websearch"
LOADER = importlib.machinery.SourceFileLoader("candidate_websearch", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("candidate_websearch", LOADER)
WEBSEARCH = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(WEBSEARCH)


class WebSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="websearch-test-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_environment_key_takes_precedence_even_when_empty(self) -> None:
        with mock.patch.dict(os.environ, {"SYNTHETIC_API_KEY": ""}, clear=False):
            self.assertEqual(WEBSEARCH.get_key("SYNTHETIC_API_KEY", {"SYNTHETIC_API_KEY": "private"}), "")

    def test_env_file_parser_uses_first_existing_file_without_logging_values(self) -> None:
        first = self.root / ".env-one"
        second = self.root / ".env-two"
        first.write_text("SYNTHETIC_API_KEY='fixture-value'\n", encoding="utf-8")
        second.write_text("SYNTHETIC_API_KEY=other-value\n", encoding="utf-8")
        self.assertEqual(WEBSEARCH.load_dotenv([first, second]),
                         {"SYNTHETIC_API_KEY": "fixture-value"})

    def test_exhausted_marker_uses_generic_cache_location_and_normalized_query(self) -> None:
        cache = self.root / "cache"
        marker = cache / "exhausted.json"
        with mock.patch.object(WEBSEARCH, "CACHE_DIR", cache), \
             mock.patch.object(WEBSEARCH, "EXHAUSTED_PATH", marker):
            WEBSEARCH.write_exhausted("  Synthetic   Query ", ["provider unavailable"])
        record = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(record["query"], "synthetic query")
        self.assertEqual(record["failures"], ["provider unavailable"])

    def test_provider_failure_exit_and_diagnostics_are_english(self) -> None:
        fake_providers = [
            {"name": "first", "key_env": None, "func": lambda *_: None},
            {"name": "second", "key_env": None, "func": lambda *_: None},
        ]
        stderr = io.StringIO()
        with mock.patch.object(WEBSEARCH, "PROVIDERS", fake_providers), \
             mock.patch.object(WEBSEARCH, "_throttle_wait"), \
             mock.patch.object(WEBSEARCH, "load_dotenv", return_value={}), \
             mock.patch.object(WEBSEARCH, "CACHE_DIR", self.root / "cache"), \
             mock.patch.object(WEBSEARCH, "EXHAUSTED_PATH", self.root / "cache" / "exhausted.json"), \
             contextlib.redirect_stderr(stderr):
            code = WEBSEARCH.main(["synthetic", "query", "--no-cache"])
        self.assertEqual(code, 3)
        self.assertIn("NOTICE", stderr.getvalue())
        self.assertIn("all providers were exhausted", stderr.getvalue())
        self.assertNotRegex(stderr.getvalue(), r"[\u0400-\u04ff]")

    def test_cache_hit_returns_without_network_call(self) -> None:
        payload = {"provider": "fixture", "query": "synthetic", "results": [], "cached": False}
        provider = {"name": "fixture", "key_env": None,
                    "func": mock.Mock(side_effect=AssertionError("network function called"))}
        output = io.StringIO()
        with mock.patch.object(WEBSEARCH, "PROVIDERS", [provider]), \
             mock.patch.object(WEBSEARCH, "load_dotenv", return_value={}), \
             mock.patch.object(WEBSEARCH, "_cache_key", return_value="fixture-key"), \
             mock.patch.object(WEBSEARCH, "_load_cache", return_value=payload), \
             contextlib.redirect_stdout(output):
            code = WEBSEARCH.main(["synthetic query"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output.getvalue())["cached"])
        provider["func"].assert_not_called()

    def test_invalid_argument_exit_contract(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            WEBSEARCH.parse_args([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
