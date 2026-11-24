"""Privacy-boundary tests using synthetic paths and disposable Git repositories."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import ast
import hashlib
import io
import json
import os
import subprocess
import tempfile
import tarfile
import tokenize
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LOADER = SourceFileLoader("public_check", str(ROOT / "bin" / "public-check"))
SPEC = importlib.util.spec_from_loader("public_check", LOADER)
assert SPEC and SPEC.loader
public_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(public_check)


def registered_legacy_literal(rel: str, symbol: str) -> str:
    source = (ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(source)
    expected = public_check.PYTHON_ALIAS_VALUE_HASHES[rel][symbol]
    for node in ast.walk(tree):
        names: set[str] = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(child.id for child in ast.walk(target) if isinstance(child, ast.Name))
        elif isinstance(node, ast.AnnAssign):
            names.update(child.id for child in ast.walk(node.target) if isinstance(child, ast.Name))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
        if symbol not in names:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                normalized = public_check.decode_unicode_escapes(child.value)
                digest = hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()
                if digest in expected:
                    return child.value
    raise AssertionError(f"no exact registered legacy input literal found for {rel}")


def registered_legacy_fstring(rel: str, symbol: str) -> str:
    source = (ROOT / rel).read_text(encoding="utf-8")
    lines = source.splitlines()
    expected = public_check.PYTHON_ALIAS_VALUE_HASHES[rel][symbol]
    tokens = list(tokenize.generate_tokens(iter(source.splitlines(keepends=True)).__next__))
    start_type = getattr(tokenize, "FSTRING_START", None)
    end_type = getattr(tokenize, "FSTRING_END", None)
    if start_type is not None and end_type is not None:
        for index, token in enumerate(tokens):
            if token.type != start_type:
                continue
            depth = 1
            end_index = index + 1
            while end_index < len(tokens) and depth:
                if tokens[end_index].type == start_type:
                    depth += 1
                elif tokens[end_index].type == end_type:
                    depth -= 1
                end_index += 1
            if depth:
                continue
            ending = tokens[end_index - 1]
            start, end = token.start, ending.end
            if start[0] == end[0]:
                raw = lines[start[0] - 1][start[1]:end[1]]
            else:
                raw = "\n".join([lines[start[0] - 1][start[1]:]] +
                                 lines[start[0]:end[0] - 1] + [lines[end[0] - 1][:end[1]]])
            digest = hashlib.sha256(b"fstring-template\0" +
                                    public_check.decode_unicode_escapes(raw).encode(
                                        "utf-8", errors="surrogatepass")).hexdigest()
            if digest in expected:
                return raw
    for token in tokens:
        if token.type != tokenize.STRING:
            continue
        import re
        prefix = re.match(r"(?i)^([rubf]*)['\"]", token.string)
        if not prefix or "f" not in prefix.group(1).lower():
            continue
        digest = hashlib.sha256(b"fstring-template\0" +
                                public_check.decode_unicode_escapes(token.string).encode(
                                    "utf-8", errors="surrogatepass")).hexdigest()
        if digest in expected:
            return token.string
    raise AssertionError(f"no exact registered legacy f-string found for {rel}")


class PublicCheckUnitTests(unittest.TestCase):
    def test_private_and_machine_local_export_paths_are_blocked(self) -> None:
        for path in (".private/rules.md", "session/log.txt", "settings.json", "notes/.env",
                     ".harness-managed.json", "notes/installed-managed.original"):
            with self.subTest(path=path):
                self.assertIsNotNone(public_check.blocked_path(path))
        self.assertIsNone(public_check.blocked_path("templates/settings.json.template"))

    def test_language_check_rejects_cyrillic_and_encoded_identifiers(self) -> None:
        cyrillic = "".join(chr(codepoint) for codepoint in (0x041F, 0x0440, 0x0438, 0x043C, 0x0435, 0x0440))
        self.assertEqual(public_check.inspect_text("readme.md", cyrillic.encode()),
                         [(1, "public text contains Cyrillic characters")])
        encoded_escape = chr(92) + "u0410"
        encoded = f'identifier = "{encoded_escape}"\n'.encode()
        self.assertEqual(public_check.inspect_text("readme.md", encoded),
                         [(1, "encoded Unicode is not a declared legacy input alias")])

    def test_named_legacy_constants_are_ast_scoped_allowlist_entries(self) -> None:
        style_literal = registered_legacy_literal("bin/style-check", "LEGACY_STYLE_MARKERS")
        unknown = "unrecognized-output-" + chr(0x0410)
        style_source = ("LEGACY_STYLE_MARKERS = [" + json.dumps(style_literal, ensure_ascii=True) +
                        ", " + json.dumps(unknown, ensure_ascii=True) + "]\n")
        allowed = public_check.allowed_encoded_alias_spans("bin/style-check", style_source)
        self.assertTrue(allowed)
        self.assertEqual(public_check.unicode_escape_findings("bin/style-check", style_source),
                         [(1, "encoded Unicode is not a declared legacy input alias")])
        migration_literal = registered_legacy_literal(
            "bin/migrate-public-release", "LEGACY_STYLE_HEADING_PATTERN")
        migration_source = ("LEGACY_STYLE_HEADING_PATTERN = " +
                            json.dumps(migration_literal, ensure_ascii=True) + "\n")
        self.assertTrue(public_check.allowed_encoded_alias_spans(
            "bin/migrate-public-release", migration_source))

    def test_only_named_aliases_inside_python_shell_heredocs_are_allowed(self) -> None:
        known = registered_legacy_literal("hooks/work-gate.test.py", "legacy_brief_template")
        unknown = "human-facing heredoc output " + chr(0x0410)
        source = "\n".join((
            "python3 - <<'PY'",
            "LEGACY_BRIEF_HEADINGS = [" + json.dumps(known, ensure_ascii=True) +
            ", " + json.dumps(unknown, ensure_ascii=True) + "]",
            "PY",
        ))
        allowed = public_check.allowed_encoded_alias_spans("hooks/work-gate.sh", source)
        self.assertTrue(allowed)
        self.assertEqual(public_check.unicode_escape_findings("hooks/work-gate.sh", source),
                         [(2, "encoded Unicode is not a declared legacy input alias")])
        non_python = "\n".join(("cat <<'PY'", "LEGACY_BRIEF_HEADINGS = " +
                                 json.dumps(known, ensure_ascii=True), "PY"))
        findings = public_check.unicode_escape_findings("hooks/work-gate.sh", non_python)
        self.assertTrue(findings)
        self.assertEqual({line for line, _ in findings}, {2})

    def test_python_heredoc_fake_legacy_output_helper_is_rejected(self) -> None:
        output = "human-facing output " + chr(0x0410)
        source = "\n".join((
            "python3 - <<'PY'",
            "def legacy_output_label():",
            "    return " + json.dumps(output, ensure_ascii=True),
            "PY",
        ))
        self.assertEqual(public_check.unicode_escape_findings("hooks/work-gate.sh", source), [
            (3, "encoded Unicode is not a declared legacy input alias")])

    def test_exact_legacy_brief_fixture_function_is_allowed_but_other_text_is_not(self) -> None:
        known = registered_legacy_literal("hooks/work-gate.test.py", "legacy_brief_template")
        unknown = "human-facing message " + chr(0x0410)
        source = "\n".join((
            "def legacy_brief_template():",
            "    synthetic_input = " + json.dumps(known, ensure_ascii=True),
            "    return " + json.dumps(unknown, ensure_ascii=True),
        ))
        self.assertEqual(public_check.unicode_escape_findings("hooks/work-gate.test.py", source),
                         [(3, "encoded Unicode is not a declared legacy input alias")])

        fake_output = "\n".join((
            "def legacy_output_label():",
            "    return " + json.dumps(unknown, ensure_ascii=True),
        ))
        self.assertEqual(public_check.unicode_escape_findings("hooks/work-gate.test.py", fake_output),
                         [(2, "encoded Unicode is not a declared legacy input alias")])

    def test_exact_legacy_card_fstring_allows_schema_but_not_an_added_output(self) -> None:
        template = registered_legacy_fstring("tests/test_plan_check.py", "legacy_card")
        unknown = "human-facing return " + chr(0x0410)
        source = "\n".join((
            "def legacy_card():",
            "    input_template = " + template,
            "    return input_template + " + json.dumps(unknown, ensure_ascii=True),
        ))
        findings = public_check.unicode_escape_findings("tests/test_plan_check.py", source)
        self.assertEqual(findings, [(len(source.splitlines()),
                                     "encoded Unicode is not a declared legacy input alias")])

    def test_actual_legacy_input_literals_match_only_registered_ast_values(self) -> None:
        paths = ("bin/plan-check", "bin/style-check", "bin/migrate-public-release",
                 "tests/test_plan_check.py", "hooks/work-gate.test.py", "hooks/work-gate.sh")
        for rel in paths:
            with self.subTest(file=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(public_check.unicode_escape_findings(rel, text), [])

    def test_private_pattern_report_contains_only_matched_line_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "private-findings.json"
            payload = b"marker=SYNTHETIC_DISCLOSURE_42\n"
            rules = {"patterns": [{"id": "fixture", "regex": "SYNTHETIC_DISCLOSURE_42"}]}
            findings = public_check.private_content_findings("src/example.txt", payload, rules)
            self.assertEqual(len(findings), 1)
            self.assertNotIn("SYNTHETIC_DISCLOSURE_42", json.dumps(findings))
            public_check.private_report(report, root / "candidate", findings)
            self.assertEqual(json.loads(report.read_text())["findings"], findings)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_scanner_binary_discovers_the_verified_default_cache_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / ".cache" / "ai-toolkit" / "public-check" / "gitleaks-8.24.3" / "gitleaks"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\nprintf '%s\\n' '8.24.3'\n", encoding="utf-8")
            binary.chmod(0o700)
            with mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.dict(os.environ, {"GITLEAKS_BIN": ""}), \
                    mock.patch.object(public_check.shutil, "which", return_value=None):
                self.assertEqual(public_check.scanner_binary(None), binary.resolve())

    def test_scanner_binary_rejects_neighbor_version_82430(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / ".cache" / "ai-toolkit" / "public-check" / "gitleaks-8.24.3" / "gitleaks"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\nprintf '%s\\n' '8.24.30'\n", encoding="utf-8")
            binary.chmod(0o700)
            with mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.dict(os.environ, {"GITLEAKS_BIN": ""}), \
                    mock.patch.object(public_check.shutil, "which", return_value=None):
                with self.assertRaises(public_check.CheckError):
                    public_check.scanner_binary(None)

    def test_installer_rejects_neighbor_version_82430(self) -> None:
        binary = b"#!/bin/sh\nprintf '%s\\n' '8.24.30'\n"
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
            info = tarfile.TarInfo("gitleaks")
            info.mode = 0o755
            info.size = len(binary)
            archive.addfile(info, io.BytesIO(binary))
        payload = archive_bytes.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "scanner-cache"
            with mock.patch.object(public_check, "scanner_platform",
                                   return_value=("fixture", hashlib.sha256(payload).hexdigest(), "fixture.tar.gz")), \
                    mock.patch.object(public_check.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
                with self.assertRaisesRegex(public_check.CheckError, "did not report the pinned version"):
                    public_check.install_scanner(destination)
            self.assertFalse((destination / "gitleaks").exists())
            self.assertEqual(list(destination.iterdir()), [])


class PublicCheckIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "candidate"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitleaks.toml").write_bytes((ROOT / ".gitleaks.toml").read_bytes())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python3", str(ROOT / "bin" / "public-check"), "check",
                               "--root", str(self.root), *args], text=True,
                              capture_output=True, check=False)

    def test_tree_check_rejects_synthetic_secret_without_printing_value(self) -> None:
        marker = "SYNTHETIC" + "_" + "TOKEN" + "_" + ("A" * 32)
        (self.root / "fixture.txt").write_text(f'api_key="{marker}"\n', encoding="utf-8")
        result = self.run_check("--tree")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        combined = result.stdout + result.stderr
        self.assertIn("secret detected", combined)
        self.assertNotIn(marker, combined)

    def test_gitleaks_rule_ignores_long_code_expression_after_embedded_token_name(self) -> None:
        (self.root / "fixture.py").write_text(
            "record.token = get_agent_transcript_path(data.get(\"transcript_path\"))\n",
            encoding="utf-8")
        result = self.run_check("--tree")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_history_scan_detects_secret_removed_from_current_tree(self) -> None:
        marker = "SYNTHETIC" + "_" + "HISTORY" + "_" + ("B" * 32)
        (self.root / "fixture.txt").write_text(f'secret="{marker}"\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Example",
                        "-c", "user.email=example.invalid", "commit", "--quiet", "-m",
                        "synthetic test fixture"], check=True)
        (self.root / "fixture.txt").unlink()
        result = self.run_check("--tree")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        combined = result.stdout + result.stderr
        self.assertIn("secret detected", combined)
        self.assertNotIn(marker, combined)

    def test_private_history_rule_rejects_a_reachable_forbidden_commit(self) -> None:
        (self.root / "ordinary.txt").write_text("synthetic ordinary content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Example",
                        "-c", "user.email=example.invalid", "commit", "--quiet", "-m",
                        "synthetic history fixture"], check=True)
        revision = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                  check=True, text=True, capture_output=True).stdout.strip()
        findings = public_check.check_history(self.root, {"forbidden_commits": [revision]})
        self.assertTrue(any(item["kind"] == "private forbidden commit is reachable"
                            for item in findings))

    def test_tree_check_rejects_private_path_before_scanning_contents(self) -> None:
        private_dir = self.root / ".private"
        private_dir.mkdir()
        (private_dir / "fixture.txt").write_text("generic content", encoding="utf-8")
        result = self.run_check("--tree")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("<blocked-private-path>", result.stdout)
        self.assertNotIn(".private", result.stdout)

    def test_explicit_manifest_rejects_escape_paths(self) -> None:
        manifest = Path(self.temporary.name) / "manifest.json"
        manifest.write_text(json.dumps(["../outside.txt"]), encoding="utf-8")
        result = self.run_check("--manifest", str(manifest))
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("path escapes the candidate root", result.stdout)

    def test_staged_fresh_repo_ignores_only_git_empty_ref_notices(self) -> None:
        (self.root / "ordinary.txt").write_text("synthetic ordinary content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        result = self.run_check("--staged")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_unreachable_loose_object_remains_a_history_finding(self) -> None:
        subprocess.run(["git", "-C", str(self.root), "hash-object", "-w", "--stdin"],
                       input=b"synthetic dangling history object\n", check=True,
                       stdout=subprocess.PIPE)
        result = self.run_check("--tree")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("unreachable Git objects or object-database errors", result.stdout)


if __name__ == "__main__":
    unittest.main()
