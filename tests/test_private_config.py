#!/usr/bin/env python3
"""Isolated tests for the optional private configuration interface."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lib.private_config import ConfigError, config_path, find_root, load, resolved_path


class PrivateConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="private-config-test-")
        self.root = Path(self.temp.name) / "toolkit"
        (self.root / "bin").mkdir(parents=True)
        (self.root / "settings.json.template").write_text("{}", encoding="utf-8")
        self.private = self.root / ".private"
        self.private.mkdir()

    def tearDown(self) -> None:
        os.environ.pop("AI_TOOLKIT_CONFIG", None)
        self.temp.cleanup()

    def test_missing_file_is_an_optional_empty_configuration(self) -> None:
        self.assertEqual(load(self.root), {})

    def test_loads_private_roots_and_extension_mapping(self) -> None:
        config = {
            "memory_root": "~/.local/share/toolkit/memory",
            "rules_file": ".private/rules.md",
            "external_roots": ["~/work/one", "/srv/work/two"],
            "extensions": {"workspace-root-notice": ".private/adapters/workspace.sh"},
            "sync": {"repositories": ["~/work/one"],
                     "pull_repositories": [], "fetch_interval": 0},
        }
        (self.private / "config.json").write_text(json.dumps(config), encoding="utf-8")
        self.assertEqual(load(self.root), config)
        self.assertEqual(config_path(self.root), self.private / "config.json")

    def test_external_config_path_override(self) -> None:
        other = Path(self.temp.name) / "external-config.json"
        other.write_text('{"external_roots": ["/tmp/example"]}', encoding="utf-8")
        os.environ["AI_TOOLKIT_CONFIG"] = str(other)
        self.assertEqual(load(self.root), {"external_roots": ["/tmp/example"]})
        self.assertEqual(config_path(self.root), other)

    def test_invalid_values_fail_explicitly(self) -> None:
        (self.private / "config.json").write_text(
            '{"sync":{"pull_repositories":["/private/repo"],"fetch_interval":-1}}',
            encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "non-negative integer"):
            load(self.root)

    def test_malformed_file_does_not_silently_disable_private_config(self) -> None:
        (self.private / "config.json").write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "cannot read valid private configuration"):
            load(self.root)

    def test_root_discovery_uses_source_location_not_checkout_name(self) -> None:
        nested = self.root / "hooks" / "test.sh"
        nested.parent.mkdir()
        nested.touch()
        self.assertEqual(find_root(nested), self.root.resolve())

    def test_relative_paths_resolve_against_checkout_root(self) -> None:
        self.assertEqual(resolved_path(self.root, ".private/rules.md"),
                         self.root / ".private/rules.md")


if __name__ == "__main__":
    unittest.main()
