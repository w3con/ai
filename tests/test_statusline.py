#!/usr/bin/env python3
"""JSON-input contract tests for the jq-free generic status line."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "statusline-command.sh"


class StatuslineTests(unittest.TestCase):
    def test_renders_model_context_cost_limits_and_git_directory(self) -> None:
        payload = {
            "cwd": "/tmp/sample-checkout",
            "model": {"display_name": "Example Model"},
            "context_window": {"used_percentage": 42, "total_input_tokens": 12345},
            "cost": {"total_cost_usd": 1.5},
            "thinking": {"enabled": True},
            "rate_limits": {
                "five_hour": {"used_percentage": 10},
                "seven_day": {"used_percentage": 80},
            },
        }
        result = subprocess.run(["bash", str(SCRIPT)], input=json.dumps(payload),
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Example Model", result.stdout)
        self.assertIn("ctx:42%", result.stdout)
        self.assertIn("$1.50", result.stdout)
        self.assertIn("5h:10%", result.stdout)
        self.assertIn("7d:80%", result.stdout)

    def test_missing_optional_fields_do_not_fail(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT)], input="{}", capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
