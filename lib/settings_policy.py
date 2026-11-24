"""Settings ownership shared by bootstrap and the stamp gate.

Only the reviewed preferences below are user-owned. Source hook entries remain
controlled while independent additions coexist outside the integrity assurance.
Other fields, including new Claude fields, remain controlled.
Schemas: https://code.claude.com/docs/en/settings-reference.md
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, NamedTuple


BOOLEAN_PREFERENCES = frozenset({
    "alwaysThinkingEnabled", "agentPushNotifEnabled", "inputNeededNotifEnabled",
    "verbose", "showTurnDuration", "showThinkingSummaries", "spinnerTipsEnabled",
    "prefersReducedMotion", "terminalProgressBarEnabled", "syntaxHighlightingDisabled",
    "voiceEnabled", "skipDangerousModePermissionPrompt",
})
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh"})
ENUM_PREFERENCES = {
    "effortLevel": EFFORT_LEVELS,
    "editorMode": {"normal", "vim"},
    "viewMode": {"default", "verbose", "focus"},
    "tui": {"default", "fullscreen"},
    "preferredNotifChannel": {"auto", "terminal_bell", "iterm2", "iterm2_with_bell",
                              "kitty", "ghostty", "notifications_disabled"},
}
PREFERENCE_KEYS = BOOLEAN_PREFERENCES | ENUM_PREFERENCES.keys() | {
    "theme", "model", "language", "voice", "modelSettings",
}
STAMP_PREFIX = "managed-v1:"


class PolicyError(ValueError):
    """Unsafe or malformed settings; messages never contain setting values."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError("duplicate JSON object key")
        result[key] = value
    return result


def finite_number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise PolicyError("non-finite JSON number")
    return value


def reject_constant(text: str) -> Any:
    raise PolicyError("non-finite JSON constant")


def loads_object(payload: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload, object_pairs_hook=unique_object,
                           parse_float=finite_number, parse_constant=reject_constant)
    except (ValueError, UnicodeError) as exc:
        raise PolicyError("malformed JSON (including duplicate keys or non-finite numbers)") from exc
    if not isinstance(value, dict):
        raise PolicyError("settings root must be a JSON object")
    return value


def valid_preference(key: str, value: Any) -> bool:
    if key in BOOLEAN_PREFERENCES:
        return type(value) is bool
    if key in ENUM_PREFERENCES:
        return isinstance(value, str) and value in ENUM_PREFERENCES[key]
    if key in {"model", "language"}:
        return isinstance(value, str) and bool(value.strip())
    if key == "theme":
        return isinstance(value, str) and (value in {
            "auto", "dark", "light", "dark-daltonized", "light-daltonized",
            "dark-ansi", "light-ansi",
        } or bool(re.fullmatch(r"custom:[\w.-]+(?::[\w.-]+)?", value)))
    if key == "voice":
        return isinstance(value, dict) and all(
            (name in {"enabled", "autoSubmit"} and type(item) is bool) or
            (name == "mode" and isinstance(item, str) and item in {"hold", "tap"})
            for name, item in value.items())
    if key == "modelSettings":
        return isinstance(value, dict) and all(
            bool(model.strip()) and isinstance(options, dict) and all(
                (name in {"effortLevel", "maxEffortLevel"} and
                 isinstance(item, str) and item in EFFORT_LEVELS) or
                (name == "autoCompactWindow" and
                 ((type(item) in {int, float} and item >= 100000) or item == "auto"))
                for name, item in options.items())
            for model, options in value.items())
    return False


def validate_preferences(settings: dict[str, Any]) -> None:
    invalid = {key for key in settings.keys() & PREFERENCE_KEYS
               if not valid_preference(key, settings[key])}
    if invalid:
        raise PolicyError("invalid or unknown preference shape at keys: " + key_names(invalid))


def preferences(settings: dict[str, Any]) -> dict[str, Any]:
    validate_preferences(settings)
    return {key: value for key, value in settings.items() if key in PREFERENCE_KEYS}


def controlled(settings: dict[str, Any]) -> dict[str, Any]:
    validate_preferences(settings)
    return {key: value for key, value in settings.items() if key not in PREFERENCE_KEYS}


def canonical(value: Any) -> bytes:
    # JSON numbers have numeric semantics, but booleans are a separate type.
    def normalize(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: normalize(part) for key, part in item.items()}
        if isinstance(item, list):
            return [normalize(part) for part in item]
        if type(item) is float and item.is_integer():
            return int(item)
        return item
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def managed_stamp(settings: dict[str, Any]) -> str:
    return STAMP_PREFIX + hashlib.sha256(canonical(controlled(settings))).hexdigest()


def key_names(keys: Any) -> str:
    return ", ".join(json.dumps(key, ensure_ascii=True) for key in sorted(keys))


def differences(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Top-level key categories only; never include values or nested model names."""
    categories = {
        "added": after.keys() - before.keys(),
        "removed": before.keys() - after.keys(),
        "changed": {key for key in before.keys() & after.keys()
                    if canonical(before[key]) != canonical(after[key])},
    }
    return "; ".join(f"{label}: {key_names(keys)}" for label, keys in categories.items() if keys)


def read_settings(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise PolicyError("installed settings path is a symlink")
    if not path.is_file():
        raise PolicyError("installed settings file is missing or not a regular file")
    return loads_object(path.read_bytes())


def read_stamp(path: Path) -> str:
    if path.is_symlink():
        raise PolicyError("settings stamp path is a symlink")
    if not path.is_file():
        raise PolicyError("no settings stamp is installed")
    value = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(?:managed-v1:)?[0-9a-f]{64}", value):
        raise PolicyError("settings stamp is malformed")
    return value


class HookMismatch(PolicyError):
    """Required source entries cannot be identified intact and in order."""


class HookAtom(NamedTuple):
    metadata: dict[str, Any]
    hook: dict[str, Any] | None
    group: int
    index: int | None

    def token(self) -> bytes:
        return canonical([self.metadata, self.hook])


def hook_atoms(settings: dict[str, Any]) -> dict[str, list[HookAtom]]:
    """Structural validation only, not an execution/safety audit of hook options."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        raise PolicyError("hooks must be an event object")
    result = {}
    for event, groups in hooks.items():
        label = "hooks event " + key_names([event])
        if not event.strip() or not isinstance(groups, list):
            raise PolicyError(label + " must contain a group array")
        atoms = []
        for group_index, group in enumerate(groups):
            location = f"{label} group {group_index + 1}"
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise PolicyError(location + " must contain a hooks array")
            if "matcher" in group and not isinstance(group["matcher"], str):
                raise PolicyError(location + " has an invalid matcher shape")
            metadata = {key: value for key, value in group.items() if key != "hooks"}
            # Empty groups still own their metadata; they must not disappear or
            # be mistaken for an unrestricted external execution group.
            if not group["hooks"]:
                atoms.append(HookAtom(metadata, None, group_index, None))
            for hook_index, hook in enumerate(group["hooks"]):
                location = f"{label} group {group_index + 1} hook {hook_index + 1}"
                if not isinstance(hook, dict) or not isinstance(hook.get("type"), str) or not hook["type"].strip():
                    raise PolicyError(location + " must be a typed hook object")
                field = {"command": "command", "prompt": "prompt", "agent": "prompt", "http": "url"}.get(hook["type"])
                if field and (not isinstance(hook.get(field), str) or not hook[field].strip()):
                    raise PolicyError(location + " has an invalid execution payload shape")
                atoms.append(HookAtom(metadata, hook, group_index, hook_index))
        result[event] = atoms
    return result


def match_hooks(installed: dict[str, Any], source: dict[str, Any]) -> dict[str, list[int]]:
    """Identify source atoms as an ordered subsequence, with exact multiplicity.

    An additional atom identical to a source atom is ambiguous ownership, not a
    safe basis for deleting/replacing one of the copies on a later deployment.
    """
    live = hook_atoms(installed)
    matches = {}
    for event, required in hook_atoms(source).items():
        tokens = [atom.token() for atom in live.get(event, [])]
        wanted = [atom.token() for atom in required]
        counts, required_counts = Counter(tokens), Counter(wanted)
        cursor, positions = 0, []
        for index, token in enumerate(wanted):
            location = f"hooks event {key_names([event])} source entry {index + 1}"
            if counts[token] > required_counts[token]:
                raise HookMismatch(location + " has ambiguous duplicate ownership")
            while cursor < len(tokens) and tokens[cursor] != token:
                cursor += 1
            if cursor == len(tokens):
                raise HookMismatch(location + " is missing, modified, re-matched, or out of order")
            positions.append(cursor)
            cursor += 1
        matches[event] = positions
    return matches


def nonhook_controlled(settings: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in controlled(settings).items() if key != "hooks"}


def integrity_differences(source: dict[str, Any], installed: dict[str, Any]) -> str:
    changes = differences(nonhook_controlled(source), nonhook_controlled(installed))
    try:
        match_hooks(installed, source)
    except HookMismatch as exc:
        changes = "; ".join(part for part in (changes, str(exc)) if part)
    return changes


def matches_expected(installed: dict[str, Any], expected: dict[str, Any]) -> bool:
    return not integrity_differences(expected, installed)


def current_stamp(stamp: str | None, installed: dict[str, Any],
                  expected: dict[str, Any], rendered: bytes) -> bool:
    """Gate acceptance, including the narrowly scoped first-upgrade legacy path."""
    return matches_expected(installed, expected) and stamp in {
        managed_stamp(expected), hashlib.sha256(rendered).hexdigest(),
    }


def baseline_bytes(source: dict[str, Any]) -> bytes:
    return (json.dumps({"version": 1, "controlled": controlled(source)},
                       ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_baseline(path: Path, stamp: str | None) -> dict[str, Any] | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PolicyError("managed source baseline must be a regular file, not a symlink")
    if not path.exists():
        return None
    try:
        record = loads_object(path.read_bytes())
        if (set(record) != {"version", "controlled"} or type(record["version"]) is not int or
                record["version"] != 1 or not isinstance(record["controlled"], dict) or
                record["controlled"].keys() & (PREFERENCE_KEYS - {"skipDangerousModePermissionPrompt"})):
            raise PolicyError("invalid baseline schema")
        source = record["controlled"]
        validate_preferences(source)
        hook_atoms(source)
    except (OSError, ValueError, UnicodeError):
        raise PolicyError("managed source baseline is malformed or unsupported; see docs/settings.md for owner repair") from None
    # Older baselines may own the dialog Boolean. Verify their original hash
    # before dropping that newly user-owned key from the ownership projection.
    if stamp != STAMP_PREFIX + hashlib.sha256(canonical(source)).hexdigest():
        raise PolicyError("managed source baseline is not bound to the saved managed stamp; see docs/settings.md for owner repair")
    return controlled(source)


def replace_owned_hooks(installed: dict[str, Any], previous: dict[str, Any],
                        expected: dict[str, Any]) -> dict[str, Any]:
    positions = match_hooks(installed, previous)
    live_atoms = hook_atoms(installed)
    hooks = deepcopy(installed.get("hooks", {}))
    old, new = previous.get("hooks", {}), expected.get("hooks", {})
    for event in old.keys() | new.keys():
        if canonical(old.get(event, [])) == canonical(new.get(event, [])):
            continue
        owned = {(live_atoms[event][index].group, live_atoms[event][index].index)
                 for index in positions.get(event, [])}
        groups, inserted = [], False
        for group_index, group in enumerate(hooks.get(event, [])):
            owns_group = any(index == group_index for index, _ in owned)
            if owns_group and not inserted:
                groups.extend(deepcopy(new.get(event, [])))
                inserted = True
            remaining = [hook for index, hook in enumerate(group["hooks"])
                         if (group_index, index) not in owned]
            if remaining or not owns_group:
                groups.append({**group, "hooks": remaining})
        if not inserted:
            groups.extend(deepcopy(new.get(event, [])))
        hooks[event] = groups
    return hooks


def compose_settings(installed: dict[str, Any] | None, expected: dict[str, Any],
                     stamp: str | None, baseline: dict[str, Any] | None
                     ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compose a deployment and return the previous source used as ownership evidence."""
    hook_atoms(expected)
    validate_preferences(expected)
    if installed is None:
        if baseline is not None:
            raise PolicyError("installed settings are missing despite a managed source baseline; restore/review them before deployment")
        return expected, expected
    if baseline is not None:
        previous = baseline
    elif matches_expected(installed, expected):
        previous = controlled(expected)
    elif stamp == managed_stamp(installed):
        # First-upgrade compatibility ONLY: the old full controlled hash proves
        # there have been no independent additions since that old deployment.
        # Never use this path with an existing source baseline or a legacy hash.
        previous = controlled(installed)
    else:
        raise PolicyError("unexpected controlled settings drift: " + integrity_differences(expected, installed) +
                          "; no managed source baseline proves prior ownership; see docs/settings.md")
    drift = integrity_differences(previous, installed)
    if drift:
        raise PolicyError("unexpected controlled settings drift from last managed source: " + drift)
    deployed = {**controlled(expected), **preferences(installed)}
    if canonical(controlled(previous)) == canonical(controlled(expected)):
        if "hooks" in installed:
            deployed["hooks"] = deepcopy(installed["hooks"])
        else:
            deployed.pop("hooks", None)
    else:
        hooks = replace_owned_hooks(installed, previous, expected)
        if "hooks" in installed or "hooks" in expected:
            deployed["hooks"] = hooks
    # A newly required source entry identical to an external entry would make
    # ownership ambiguous. Fail before writing instead of claiming either copy.
    match_hooks(deployed, expected)
    return deployed, previous


def source_differences(before: dict[str, Any], after: dict[str, Any]) -> str:
    changes = [differences(nonhook_controlled(before), nonhook_controlled(after))]
    old, new = hook_atoms(before), hook_atoms(after)
    for event in sorted(old.keys() | new.keys()):
        left, right = old.get(event, []), new.get(event, [])
        for index in range(max(len(left), len(right))):
            kind = "added" if index >= len(left) else "removed" if index >= len(right) else "changed"
            if kind != "changed" or left[index].token() != right[index].token():
                changes.append(f"hooks event {key_names([event])} source entry {index + 1} {kind}")
    return "; ".join(part for part in changes if part)


def additional_hooks(installed: dict[str, Any], source: dict[str, Any]) -> str:
    owned = match_hooks(installed, source)
    return "; ".join(f"hooks event {key_names([event])}: preserve {count} additional entries"
                     for event, atoms in hook_atoms(installed).items()
                     if (count := len(atoms) - len(owned.get(event, []))))


def recovery(root: Path) -> str:
    import shlex
    command = "bash " + shlex.quote(str(root / "bootstrap.sh"))
    return (f"Diagnose with {command} --dry-run. The owner must deliberately review/edit "
            "the private source and repair owned entries using a trusted baseline. Back up "
            "settings/stamp/baseline and use bin/settings-render for source-only comparison "
            "(see docs/settings.md), preserving independent hooks, "
            f"then run {command}. Preference-only adoption: {command} --adopt --dry-run.")
