#!/usr/bin/env python3
"""Synthetic English and encoded legacy-heading compatibility tests."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).resolve().parents[1] / "bin" / "plan-check"


def english_card() -> str:
    return """---
status: approved
---
## Out of scope
Do not alter adjacent products.
## Acceptance Criteria
The validation command passes.
## Checkpoints
- [ ] 1.1 — Validate the public behavior.
"""


def legacy_card() -> str:
    status = "\u0421\u0442\u0430\u0442\u0443\u0441"
    scope = "\u0412\u043d\u0435 \u0440\u0430\u043c\u043e\u043a"
    acceptance = "\u041a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a\u0438"
    checkpoints = "\u041a\u043e\u043d\u0442\u0440\u043e\u043b\u044c\u043d\u044b\u0435 \u0442\u043e\u0447\u043a\u0438"
    return f"""**{status}:** \u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e
## {scope}
Do not alter adjacent products.
## {acceptance}
The validation command passes.
## {checkpoints}
- [ ] 1.1 — Validate the public behavior.
"""


def legacy_interview_card() -> str:
    interview = "\u0418\u043d\u0442\u0435\u0440\u0432\u044c\u044e"
    sources = "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438"
    summary = "\u0420\u0435\u0437\u044e\u043c\u0435"
    approval = "\u0420\u0435\u0437\u044e\u043c\u0435 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e"
    return legacy_card() + f"""## {interview}
### 1 Requester
The toolkit maintainer.
### 2 Problem
Private project data was mixed with reusable tools.
### 3 Result
A portable candidate with compatible paths.
### 4 Constraints
Do not change the live installation.
### 5 Prior work
An inventory is available.
### 6 Affected systems
The isolated candidate only.
## {sources}
The source manifest and compatibility inventory.
## {summary}
**{approval}:** 2026-11-17 — approved synthetic plan
"""


class PlanCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="plan-check-test-")
        self.root = Path(self.temp.name)
        self.card = self.root / "card.md"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_check(self, contents: str, *, interview: bool = False) -> subprocess.CompletedProcess[str]:
        self.card.write_text(contents, encoding="utf-8")
        if interview:
            (self.root / ".plan-check-interview").write_text("", encoding="utf-8")
        return subprocess.run([str(CHECKER), str(self.card), "--check"],
                              capture_output=True, text=True, check=False)

    def test_current_english_header_aliases_are_accepted(self) -> None:
        result = self.run_check(english_card())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("<!-- card:ready -->", self.card.read_text(encoding="utf-8"))

    def test_encoded_legacy_status_scope_acceptance_and_checkpoint_headers_are_accepted(self) -> None:
        result = self.run_check(legacy_card())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_encoded_legacy_interview_sources_summary_and_approval_are_accepted(self) -> None:
        result = self.run_check(legacy_interview_card(), interview=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bad_checkpoint_is_rejected_without_modifying_card(self) -> None:
        invalid = english_card().replace("1.1 —", "checkpoint —")
        result = self.run_check(invalid)
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed checkpoint", result.stdout)
        self.assertEqual(self.card.read_text(encoding="utf-8"), invalid)


if __name__ == "__main__":
    unittest.main()
