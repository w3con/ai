#!/usr/bin/env python3
"""Tests for generic brief path extraction and transcript lookup."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "hooks" / "brief_reader.py"
LOADER = importlib.machinery.SourceFileLoader("brief_reader_tested", str(PATH))
SPEC = importlib.util.spec_from_loader("brief_reader_tested", LOADER)
BRIEF = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(BRIEF)


class BriefReaderTests(unittest.TestCase):
    def test_prompt_and_description_paths_keep_first_seen_order(self) -> None:
        value = BRIEF.brief_tokens({
            "prompt": "Read `tasks/TASK-1.md` and `plans/old-plan.md`.",
            "description": "Repeat `tasks/TASK-1.md` only once.",
        })
        self.assertEqual(value, ["tasks/TASK-1.md", "plans/old-plan.md"])

    def test_relative_and_bare_names_resolve_under_roots(self) -> None:
        paths = BRIEF.resolve("TASK-2.md", ["/tmp/work"])
        self.assertIn("/tmp/work/tasks/TASK-2.md", paths)
        self.assertIn("/tmp/work/plans/TASK-2.md", paths)

    def test_card_canonicalization_discards_checkout_prefix(self) -> None:
        self.assertEqual(BRIEF.canonical_card("/tmp/work/tasks/TASK-2.md"), "tasks/TASK-2.md")
        self.assertEqual(BRIEF.canonical_card("ordinary.md"), "ordinary.md")

    def test_transcript_lookup_matches_agent_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="brief-transcript-") as temp:
            transcript = Path(temp) / "session.jsonl"
            transcript.write_text("\n".join(json.dumps(item) for item in (
                {"toolUseResult": {"agentId": "other", "prompt": "wrong"}},
                {"toolUseResult": {"agentId": "agent-1", "prompt": "Read tasks/TASK-1.md",
                                    "description": "description"}},
            )), encoding="utf-8")
            self.assertEqual(BRIEF.find_spawn_prompt(str(transcript), "agent-1"), {
                "prompt": "Read tasks/TASK-1.md", "description": "description"})

    def test_missing_or_malformed_transcript_fails_open(self) -> None:
        self.assertIsNone(BRIEF.find_spawn_prompt("/no/such/transcript", "agent-1"))
        with tempfile.TemporaryDirectory(prefix="brief-transcript-invalid-") as temp:
            transcript = Path(temp) / "broken.jsonl"
            transcript.write_text('{"agentId":"agent-1"}\n', encoding="utf-8")
            self.assertIsNone(BRIEF.find_spawn_prompt(str(transcript), "agent-1"))


if __name__ == "__main__":
    unittest.main()
