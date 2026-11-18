"""Load optional machine-local toolkit configuration without project defaults.

Configuration is JSON in an ignored ``.private/config.json`` file.  An explicit
``AI_TOOLKIT_CONFIG`` path takes precedence.  Missing configuration is a normal
portable-install state; malformed configuration is reported to its caller rather
than silently falling back to a project-specific path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """The optional private config exists but is invalid."""


def find_root(start: str | Path) -> Path:
    path = Path(start).expanduser().resolve()
    if path.is_file():
        path = path.parent
    for parent in (path, *path.parents):
        if (parent / "settings.json.template").is_file() and (parent / "bin").is_dir():
            return parent
    raise ConfigError(f"cannot locate toolkit root from {path}")


def config_path(root: str | Path) -> Path:
    override = os.environ.get("AI_TOOLKIT_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(root) / ".private" / "config.json"


def _string_list(value: Any, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ConfigError(f"{key} must be an array of non-empty strings")
    return value


def load(root: str | Path) -> dict[str, Any]:
    path = config_path(root)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read valid private configuration at {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ConfigError("private configuration root must be a JSON object")

    for key in ("memory_root", "rules_file"):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()):
            raise ConfigError(f"{key} must be a non-empty path string")
    _string_list(config.get("external_roots"), "external_roots")
    _string_list(config.get("coordinator_source_roots"), "coordinator_source_roots")
    _string_list(config.get("brief_card_prefixes"), "brief_card_prefixes")
    _string_list(config.get("brief_directories"), "brief_directories")
    marker_name = config.get("executor_marker_environment", "TOOLKIT_EXECUTOR")
    if not isinstance(marker_name, str) or not marker_name:
        raise ConfigError("executor_marker_environment must be a non-empty string")
    extensions = config.get("extensions", {})
    if not isinstance(extensions, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in extensions.items()
    ):
        raise ConfigError("extensions must map string identifiers to string paths")
    inbox = config.get("inbox")
    if inbox is not None:
        if not isinstance(inbox, dict):
            raise ConfigError("inbox must be a JSON object")
        if not isinstance(inbox.get("root"), str) or not inbox["root"].strip():
            raise ConfigError("inbox.root must be a non-empty path")
        command = inbox.get("command")
        if not isinstance(command, list) or not command or any(
            not isinstance(part, str) or not part for part in command
        ):
            raise ConfigError("inbox.command must be a non-empty argv array")
    sync = config.get("sync", {})
    if not isinstance(sync, dict):
        raise ConfigError("sync must be a JSON object")
    _string_list(sync.get("repositories"), "sync.repositories")
    _string_list(sync.get("pull_repositories"), "sync.pull_repositories")
    interval = sync.get("fetch_interval", 14400)
    if isinstance(interval, bool) or not isinstance(interval, int) or interval < 0:
        raise ConfigError("sync.fetch_interval must be a non-negative integer")
    knowledge_base = config.get("knowledge_base", {})
    if not isinstance(knowledge_base, dict):
        raise ConfigError("knowledge_base must be a JSON object")
    _string_list(knowledge_base.get("collection_order"), "knowledge_base.collection_order")
    _string_list(knowledge_base.get("skip_folders"), "knowledge_base.skip_folders")
    notice = knowledge_base.get("notice", {})
    if not isinstance(notice, dict):
        raise ConfigError("knowledge_base.notice must be a JSON object")
    for key in ("workspace_markers", "code_roots", "knowledge_roots", "work_commands"):
        _string_list(notice.get(key), f"knowledge_base.notice.{key}")
    for key in ("index_command", "path_check_command"):
        value = notice.get(key)
        if value is not None and (not isinstance(value, list) or not value or
                                  any(not isinstance(part, str) or not part for part in value)):
            raise ConfigError(f"knowledge_base.notice.{key} must be a non-empty argv array")
    for key in ("card_path_pattern", "state_directory", "disable_environment"):
        if key in notice and not isinstance(notice[key], str):
            raise ConfigError(f"knowledge_base.notice.{key} must be a string")
    for key in ("model", "prompt"):
        if key in knowledge_base and not isinstance(knowledge_base[key], str):
            raise ConfigError(f"knowledge_base.{key} must be a string")
    if "secrets_file" in config and (
        not isinstance(config["secrets_file"], str) or not config["secrets_file"].strip()
    ):
        raise ConfigError("secrets_file must be a non-empty path string")
    _string_list(config.get("style_roots"), "style_roots")
    _string_list(config.get("style_settings"), "style_settings")
    if "style_recovery_root" in config and (
        not isinstance(config["style_recovery_root"], str) or
        not config["style_recovery_root"].strip()
    ):
        raise ConfigError("style_recovery_root must be a non-empty path string")
    work_management = config.get("work_management", {})
    if not isinstance(work_management, dict):
        raise ConfigError("work_management must be a JSON object")
    if "enabled" in work_management and not isinstance(work_management["enabled"], bool):
        raise ConfigError("work_management.enabled must be a boolean")
    return config


def resolved_path(root: str | Path, value: str) -> Path:
    """Resolve a configured path relative to toolkit root or its user's home."""
    expanded = Path(os.path.expandvars(os.path.expanduser(value)))
    return expanded if expanded.is_absolute() else Path(root) / expanded
