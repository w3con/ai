#!/usr/bin/env python3
"""websearch-gate — the built-in WebSearch tool never runs in place of the chain.

Registered as a PreToolUse hook on WebSearch. Every search, by anyone — the
session itself or any subagent it raises — goes Tavily, then Brave, then
DuckDuckGo, through bin/websearch, and reaches the built-in tool only after
that whole chain has failed on this same query.

The chain says it failed by writing ~/.cache/websearch/exhausted.json, which
bin/websearch writes only on exit 3. This hook allows the built-in tool when
that file is fresh and names the same query, and refuses it otherwise, naming
the command to run instead.

CLAUDE_WEBSEARCH_BYPASS=1 lets the built-in tool through unconditionally.
"""
import json
import os
import sys
import time
from pathlib import Path

EXHAUSTED_PATH = Path.home() / ".cache" / "websearch" / "exhausted.json"
EXHAUSTED_TTL_SECONDS = 15 * 60
WEBSEARCH = Path.home() / "Dev" / "ai" / "bin" / "websearch"


def emit(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def normalize_query(query):
    return " ".join(str(query).lower().split())


def read_exhausted():
    try:
        with open(EXHAUSTED_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    at = payload.get("at")
    if not isinstance(at, (int, float)) or time.time() - at > EXHAUSTED_TTL_SECONDS:
        return None
    return payload


def main():
    if os.environ.get("CLAUDE_WEBSEARCH_BYPASS") == "1":
        emit("allow", "websearch-gate bypassed by CLAUDE_WEBSEARCH_BYPASS=1")

    try:
        data = json.load(sys.stdin)
    except Exception:
        # Fail closed: a payload this hook cannot read is not a licence to
        # spend on the most expensive search available.
        emit("deny", "Blocked by websearch-gate: the hook could not read its own payload, "
                     "so it cannot tell whether the provider chain has been tried. Run "
                     f"{WEBSEARCH} \"<запрос>\" instead.")

    if data.get("tool_name") != "WebSearch":
        emit("allow", "")

    query = (data.get("tool_input") or {}).get("query") or ""
    exhausted = read_exhausted()

    if exhausted is not None and exhausted.get("query") == normalize_query(query):
        failures = exhausted.get("failures") or []
        emit("allow",
             "websearch-gate: the provider chain was tried on this same query and every "
             "provider failed, so the built-in search is allowed once. REPORT THIS TO THE "
             "OWNER IN YOUR ANSWER, in one line, naming what failed: " + "; ".join(failures))

    if exhausted is not None:
        emit("deny",
             "Blocked by websearch-gate: a provider chain did fail recently, but on a "
             "different query (%r), not on this one. Run the chain on this query first:\n"
             "    %s \"%s\"\n"
             "Exit 0 means it found something and the built-in search is not needed. Exit 3 "
             "means the whole chain failed, and this hook will then let the built-in search "
             "through — and you must say in your answer which providers failed."
             % (exhausted.get("query"), WEBSEARCH, query))

    emit("deny",
         "Blocked by websearch-gate: the built-in WebSearch is the last resort, not the "
         "first. Every search goes Tavily, then Brave, then DuckDuckGo, through one command:\n"
         "    %s \"%s\"\n"
         "Exit 0 means it found something — use that, and if its output carries a «ВНИМАНИЕ» "
         "block naming a provider that did not work, repeat that line in your answer to the "
         "owner. Exit 3 means the whole chain failed, and only then does this hook let the "
         "built-in search through on this same query.\n"
         "The built-in search costs many times what the chain costs, so a silent fall-back "
         "to it is exactly what this hook exists to prevent." % (WEBSEARCH, query))


if __name__ == "__main__":
    main()
