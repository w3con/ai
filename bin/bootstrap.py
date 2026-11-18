#!/usr/bin/env python3
"""Install the toolkit into Claude Code without requiring private repositories.

The installer changes only its explicit target HOME and this checkout's local Git
configuration. It never discovers a business vault or writes shell startup files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import stat
from pathlib import Path
from typing import Any


def load_renderer(root: Path):
    path = root / "bin" / "settings-render"
    loader = importlib.machinery.SourceFileLoader("toolkit_settings_renderer", str(path))
    spec = importlib.util.spec_from_loader("toolkit_settings_renderer", loader)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared settings renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_text(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_symlink(source: Path, target: Path, dry_run: bool,
                   allow_missing_source: bool = False) -> str | None:
    if not source.exists() and not source.is_symlink() and not (dry_run and allow_missing_source):
        return f"required toolkit source is missing: {source}"
    if target.is_symlink():
        if Path(os.path.realpath(target)) == Path(os.path.realpath(source)):
            print(f"[ok] {target} -> {source}")
            return None
        return f"refusing to replace existing symlink with a different target: {target}"
    if target.exists() and not target.is_symlink():
        return f"refusing to replace existing non-symlink target: {target}"
    if dry_run:
        print(f"[dry-run] create/update {target} -> {source}")
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.new-{os.getpid()}")
    try:
        temporary.symlink_to(source, target_is_directory=source.is_dir())
        os.replace(temporary, target)
    finally:
        if temporary.is_symlink():
            temporary.unlink()
    print(f"[link] {target} -> {source}")
    return None


def ignore_private_alias(root: Path, target: Path, dry_run: bool) -> str | None:
    """Keep a generated historical hook alias local to this checkout."""
    git_meta = root / ".git"
    if not git_meta.is_dir():
        return f"private hook aliases require a Git checkout to ignore {target}"
    exclude = git_meta / "info" / "exclude"
    pattern = "/" + target.relative_to(root).as_posix()
    try:
        lines = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
    except (OSError, UnicodeError) as exc:
        return f"cannot read local Git exclude rules {exclude}: {exc}"
    if pattern in lines:
        return None
    if dry_run:
        print(f"[dry-run] add private alias to local Git exclude rules: {pattern}")
        return None
    try:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        previous = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        atomic_text(exclude, previous + ("" if not previous or previous.endswith("\n") else "\n") +
                    pattern + "\n", 0o644)
    except OSError as exc:
        return f"cannot record private hook alias in local Git exclude rules: {exc}"
    return None


class FileTransaction:
    """In-memory snapshots for the small, explicit set of installer-owned paths."""

    def __init__(self) -> None:
        self.entries: list[tuple[Path, str, Any]] = []
        self.seen: set[Path] = set()

    def capture(self, path: Path) -> None:
        path = Path(os.path.abspath(path))
        if path in self.seen:
            return
        self.seen.add(path)
        try:
            info = path.lstat()
        except FileNotFoundError:
            self.entries.append((path, "missing", None))
            return
        if stat.S_ISLNK(info.st_mode):
            self.entries.append((path, "symlink", os.readlink(path)))
        elif stat.S_ISREG(info.st_mode):
            self.entries.append((path, "file", (path.read_bytes(), stat.S_IMODE(info.st_mode))))
        elif stat.S_ISDIR(info.st_mode):
            self.entries.append((path, "directory", stat.S_IMODE(info.st_mode)))
        else:
            raise OSError(f"unsupported installer target type: {path.name}")

    def capture_path(self, path: Path) -> None:
        path = Path(os.path.abspath(path))
        missing_parents: list[Path] = []
        parent = path.parent
        while parent != parent.parent and not parent.exists() and not parent.is_symlink():
            missing_parents.append(parent)
            parent = parent.parent
        for missing in reversed(missing_parents):
            self.capture(missing)
        self.capture(path)

    @staticmethod
    def _remove(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()

    def restore(self) -> list[str]:
        failures: list[str] = []
        for path, kind, value in reversed(self.entries):
            try:
                if kind == "missing":
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                elif kind == "symlink":
                    if path.exists() or path.is_symlink():
                        self._remove(path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(value)
                elif kind == "file":
                    if path.exists() or path.is_symlink():
                        self._remove(path)
                    payload, mode = value
                    atomic_text_bytes(path, payload, mode)
                elif kind == "directory":
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                    path.mkdir(parents=True, exist_ok=True)
                    os.chmod(path, value)
            except OSError:
                failures.append(path.name)
        return failures


def atomic_text_bytes(path: Path, value: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.restore-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def installation_failpoint(name: str) -> None:
    """Isolated acceptance-test failpoints for deployment rollback."""
    if os.environ.get("AI_TOOLKIT_BOOTSTRAP_FAILPOINT") == name:
        raise RuntimeError(f"synthetic installation failure at {name}")


def symlink_problem(source: Path, target: Path) -> str | None:
    if not source.exists() and not source.is_symlink():
        return f"required toolkit source is missing: {source.name}"
    if not (target.exists() or target.is_symlink()):
        return None
    if not target.is_symlink():
        return f"refusing to replace existing non-symlink target: {target.name}"
    if Path(os.path.realpath(target)) != Path(os.path.realpath(source)):
        return f"refusing to replace an existing link with a different target: {target.name}"
    return None


def prepare_install(root: Path, home: Path, config: dict[str, Any], renderer: Any,
                    path_resolver: Any) -> tuple[dict[str, Any], list[str]]:
    """Read and validate every deployment input before touching the installation."""
    failures: list[str] = []
    claude = home / ".claude"
    if (claude.exists() or claude.is_symlink()) and not claude.is_dir():
        failures.append(f"installation home is not a directory: {claude}")

    link_sources: dict[str, Path] = {}
    for name in ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh"):
        source = root / name
        required_directory = name in {"agents", "hooks", "skills", "commands"}
        if (required_directory and not source.is_dir()) or (not required_directory and not source.is_file()):
            failures.append(f"required toolkit source is missing: {name}")
            continue
        link_sources[name] = source
        problem = symlink_problem(source, claude / name)
        if problem:
            failures.append(problem)

    configured_file = os.environ.get("AI_TOOLKIT_CONFIG")
    private_file = Path(configured_file).expanduser().resolve() if configured_file else None
    private_link = root / ".private" / "config.json"
    if private_file:
        if not private_file.is_file():
            failures.append(f"configured private settings file is missing: {private_file}")
        elif private_link.exists() or private_link.is_symlink():
            if not private_link.is_symlink() or private_link.resolve() != private_file:
                failures.append(f"{private_link} already contains a different private config; preserve it and configure one source explicitly")

    memory_target = claude / "memory"
    configured_memory = config.get("memory_root")
    if memory_target.is_symlink() and not memory_target.resolve().is_dir():
        failures.append(f"existing memory symlink does not resolve to a directory: {memory_target}")
    if memory_target.exists() and not memory_target.is_symlink():
        if not memory_target.is_dir():
            failures.append(f"existing memory path is not a directory: {memory_target}")
        memory_root, link_memory = memory_target, False
    elif memory_target.is_symlink() and configured_memory is None and memory_target.resolve().is_dir():
        memory_root, link_memory = memory_target.resolve(), False
    else:
        memory_root = path_resolver(root, configured_memory) if configured_memory else \
            home / ".local" / "share" / "ai-toolkit" / "memory"
        if memory_root.exists() and not memory_root.is_dir():
            failures.append(f"configured memory root is not a directory: {memory_root}")
        if configured_memory is not None or memory_root.exists():
            problem = symlink_problem(memory_root, memory_target)
            if problem:
                failures.append(problem)
        link_memory = True

    projects_dir = claude / "projects"
    project_memory: list[Path] = []
    if projects_dir.is_dir():
        try:
            projects = sorted(path for path in projects_dir.iterdir() if path.is_dir())
        except OSError as exc:
            failures.append(f"cannot inspect project memory paths under {projects_dir}: {exc}")
            projects = []
        for project in projects:
            path = project / "memory"
            if path.is_dir() and not path.is_symlink():
                try:
                    if next(path.iterdir(), None) is not None:
                        failures.append(f"preserving non-empty project memory without merging: {path}; configure its private destination before retrying")
                        continue
                except OSError as exc:
                    failures.append(f"cannot inspect existing private memory {path}: {exc}")
                    continue
            elif path.exists() and not path.is_symlink():
                failures.append(f"project memory path is not a directory or symlink: {path}")
                continue
            project_memory.append(path)

    extensions: list[tuple[str, Path, Path]] = []
    extension_config: Any = config.get("extensions", {})
    if not isinstance(extension_config, dict):
        failures.append("private extensions must be an object mapping legacy paths to sources")
    else:
        if extension_config and not (root / ".git").is_dir():
            failures.append("private hook aliases require a Git checkout with local exclude rules")
        for legacy, source_rel in extension_config.items():
            if not isinstance(legacy, str) or not isinstance(source_rel, str):
                failures.append("private extension names and source paths must be strings")
                continue
            legacy_path = Path(legacy)
            if legacy_path.is_absolute() or ".." in legacy_path.parts or not legacy_path.parts:
                failures.append(f"unsafe private extension destination: {legacy}")
                continue
            if legacy_path.parts[0] != "hooks":
                failures.append(f"private extension destination must be under hooks/: {legacy}")
                continue
            source = Path(source_rel).expanduser()
            if not source.is_absolute():
                source = root / source
            target = root / legacy_path
            problem = symlink_problem(source, target)
            if problem:
                failures.append(problem)
                continue
            extensions.append((legacy, source, target))

    optional_rules = root / ".private" / "rules.md"
    if optional_rules.is_symlink() and not optional_rules.exists():
        failures.append(f"optional rules import is a broken symlink: {optional_rules}")
    elif optional_rules.exists() and not optional_rules.is_file():
        failures.append(f"optional rules import target is not a file: {optional_rules}")

    overlay_value = config.get("settings_overlay", ".private/settings.json")
    if not isinstance(overlay_value, str) or not overlay_value.strip():
        failures.append("settings_overlay must be a non-empty path")
        overlay = None
    else:
        overlay = path_resolver(root, overlay_value)
    settings_path = claude / "settings.json"
    stamp_path = claude / ".harness-stamp"
    rendered: bytes | None = None
    digest: str | None = None
    try:
        rendered = renderer.render(root / "settings.json.template",
                                   overlay if overlay and overlay.exists() else None,
                                   str(home))
        digest = hashlib.sha256(rendered).hexdigest()
    except Exception as exc:
        failures.append(f"settings render failed: {exc}")
    if settings_path.is_symlink():
        failures.append(f"refusing to replace a settings symlink: {settings_path}")
    elif settings_path.exists() and not settings_path.is_file():
        failures.append(f"installed settings path is not a regular file: {settings_path}")
    elif settings_path.is_file() and rendered is not None:
        try:
            if settings_path.read_bytes() != rendered:
                failures.append(f"machine-local settings differ from this render: {settings_path}; preserve desired values in the ignored private settings overlay first")
        except OSError as exc:
            failures.append(f"cannot read existing settings safely: {exc}")
    if stamp_path.is_symlink() or (stamp_path.exists() and not stamp_path.is_file()):
        failures.append(f"installed settings stamp is not a regular file: {stamp_path}")

    exclude = root / ".git" / "info" / "exclude"
    if extensions and exclude.is_symlink():
        failures.append(f"local Git exclude path is a symlink: {exclude}")
    if extensions and exclude.exists() and not exclude.is_file():
        failures.append(f"local Git exclude path is not a regular file: {exclude}")
    git_config = root / ".git" / "config"
    if (root / ".git").is_dir() and git_config.is_symlink():
        failures.append(f"local Git config is a symlink: {git_config}")

    return {"claude": claude, "link_sources": link_sources, "private_file": private_file,
            "private_link": private_link, "memory_target": memory_target,
            "memory_root": memory_root, "link_memory": link_memory,
            "project_memory": project_memory, "extensions": extensions,
            "optional_rules": optional_rules, "settings_path": settings_path,
            "stamp_path": stamp_path, "rendered": rendered, "digest": digest,
            "exclude": exclude, "git_config": git_config}, failures


def install(root: Path, home: Path, dry_run: bool) -> int:
    sys.path.insert(0, str(root))
    try:
        from lib.private_config import ConfigError, load, resolved_path
        config = load(root)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"bootstrap: invalid optional private configuration: {exc}", file=sys.stderr)
        return 1
    try:
        plan, failures = prepare_install(root, home, config, load_renderer(root), resolved_path)
    except Exception as exc:
        print(f"bootstrap: preflight failed: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"FAILED: {failure}", file=sys.stderr)
        return 1

    claude = plan["claude"]
    if dry_run:
        print("[dry-run] no filesystem changes will be made")
        for name, source in plan["link_sources"].items():
            print(f"[dry-run] create/update {claude / name} -> {source}")
        if plan["link_memory"]:
            print(f"[dry-run] create/update {plan['memory_target']} -> {plan['memory_root']}")
        for legacy, source, target in plan["extensions"]:
            print(f"[dry-run] create/update {target} -> {source}")
        if not plan["optional_rules"].exists():
            print(f"[dry-run] create empty optional rules target {plan['optional_rules']}")
        if plan["rendered"] is not None:
            print(f"[dry-run] render settings at {plan['settings_path']}; expected digest {plan['digest']}")
        return 0

    transaction = FileTransaction()
    managed_paths = [claude, *[claude / name for name in plan["link_sources"]],
                     plan["memory_target"], *plan["project_memory"],
                     plan["settings_path"], plan["stamp_path"], plan["private_link"],
                     plan["optional_rules"], plan["git_config"]]
    if plan["link_memory"]:
        managed_paths.append(plan["memory_root"])
    if plan["extensions"]:
        managed_paths.append(plan["exclude"])
        managed_paths.extend(target for _, _, target in plan["extensions"])
    try:
        for path in managed_paths:
            transaction.capture_path(path)

        if plan["private_file"]:
            error = atomic_symlink(plan["private_file"], plan["private_link"], False)
            if error:
                raise OSError(error)

        claude.mkdir(parents=True, exist_ok=True)
        if plan["stamp_path"].exists():
            plan["stamp_path"].unlink()

        for name, source in plan["link_sources"].items():
            error = atomic_symlink(source, claude / name, False)
            if error:
                raise OSError(error)
        installation_failpoint("after-links")

        if plan["link_memory"]:
            plan["memory_root"].mkdir(parents=True, exist_ok=True)
            error = atomic_symlink(plan["memory_root"], plan["memory_target"], False)
            if error:
                raise OSError(error)
        else:
            print(f"[keep] preserving existing local memory directory: {plan['memory_target']}")

        for project_memory in plan["project_memory"]:
            if project_memory.is_dir() and not project_memory.is_symlink():
                project_memory.rmdir()
            error = atomic_symlink(plan["memory_root"], project_memory, False,
                                   allow_missing_source=(not plan["memory_root"].exists()))
            if error:
                raise OSError(error)

        for _, source, target in plan["extensions"]:
            error = atomic_symlink(source, target, False)
            if error:
                raise OSError(error)
            error = ignore_private_alias(root, target, False)
            if error:
                raise OSError(error)

        if not plan["optional_rules"].exists():
            atomic_text(plan["optional_rules"], "", 0o600)

        git_dir = root / ".git"
        if git_dir.exists():
            current = subprocess.run(["git", "-C", str(root), "config", "--local", "--get",
                                      "core.hooksPath"], capture_output=True, text=True)
            if current.stdout.strip() != ".githooks":
                result = subprocess.run(["git", "-C", str(root), "config", "--local",
                                         "core.hooksPath", ".githooks"], check=False)
                if result.returncode != 0:
                    raise OSError("failed to register repository hooks")

        if plan["rendered"] is None:
            raise OSError("settings renderer did not produce output")
        renderer = load_renderer(root)
        renderer.write_atomic(plan["settings_path"], plan["rendered"])
        installation_failpoint("after-settings")
        atomic_text(plan["stamp_path"], plan["digest"] + "\n")
        print(f"[render] {plan['settings_path']}")
        print(f"[stamp] {plan['stamp_path']}")
        print("bootstrap: deployment checks passed")
        return 0
    except BaseException as exc:
        rollback_failures = transaction.restore()
        print(f"bootstrap: deployment failed and was rolled back: {exc}", file=sys.stderr)
        if rollback_failures:
            print("bootstrap: rollback could not restore these paths: " + ", ".join(rollback_failures),
                  file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    home = Path.home().resolve()
    return install(root, home, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
