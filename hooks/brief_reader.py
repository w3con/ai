#!/usr/bin/env python3
"""brief_reader.py — the one place both hooks/plan-gate.sh and hooks/card-touch-gate.sh
read a build agent's brief from, so the two can never disagree about which file is a run's
brief (HRN-109). Not a script of its own: each hook's inline python imports it after doing
sys.path.insert(0, <this file's own directory>), computed from the hook script's own $0 so
the import works whether the hook is invoked as ~/.claude/hooks/*.sh (a symlinked
directory, per bootstrap.sh) or directly as /Users/laptop/Dev/ai/hooks/*.sh.

Two separate jobs live here, because both gates need to answer "what .md-shaped path did a
piece of text name", but they need it at two different moments of a run's life.

plan-gate.sh sees the ORIGINAL spawn call itself — the Task/Agent tool_input, at the moment
the coordinator makes it, before the subagent exists. It hands that tool_input's own prompt
and description straight to brief_tokens() and resolve().

card-touch-gate.sh only ever sees calls made LATER, by the subagent itself once it is
already running (its payload carries an agent_id) — never the spawn call, which happened
before this agent existed and carried no agent_id at all. find_spawn_prompt() is how it
recovers that original prompt anyway: every PreToolUse payload for a subagent's own call
carries transcript_path, and that path names the coordinator's own durable session
transcript — confirmed directly against a live payload while building HRN-109 (see that
card's own Working state) — which records every Task/Agent spawn that session made as a
toolUseResult object, one per JSONL line, carrying that subagent's agentId, prompt and
description. Reading that record recovers the exact text plan-gate.sh already checked at
spawn time, and running it through the same brief_tokens()/resolve() pair used there means
the two gates read the same thing rather than each inferring their own guess.
"""
import json
import os
import re

# Any token ending in .md. Deliberately permissive about what comes before it — a bare
# name, a relative path, an absolute path, a ~-prefixed path — because each candidate is
# resolved and must exist on disk (or, for card-touch-gate, must reduce to a real
# task-card-shaped suffix) before it matters.
MD_PATH_RE = re.compile(r'[~\w./\\-]*[\w-]\.md\b')

# A task-card-shaped path specifically: ai/timeline/tasks/<name>.md or
# ai/harness/tasks/<name>.md, with or without a leading directory portion, absolute or
# relative alike. Narrower than MD_PATH_RE — legacy plan files (plans/*.md, ai/plans/*.md)
# are valid briefs for plan-gate.sh but are never a task card, so card-touch-gate.sh has no
# business tracking one. Used to DETECT a card-shaped token inside arbitrary free text (a
# prompt, a Bash command); its permissive `[~\w./\\-]*` prefix exists only so the match can
# start wherever a real path begins, not to be kept — canonical_card() below strips that
# prefix back off with a separate, narrower pattern, and must never be simplified to reuse
# this one's whole match, or a leading directory (e.g. an executor's own worktree prefix)
# gets swallowed into the "canonical" form instead of thrown away, which is exactly the bug
# that froze an executor outright before cfbd25d fixed it.
CARD_PATH_RE = re.compile(r'([~\w./\\-]*ai/(?:timeline|harness)/tasks/[\w.-]+\.md)')

# The identifying suffix alone, with no permissive prefix at all — this is what
# canonical_card() anchors on, so that whatever directory came before "ai/timeline/tasks/"
# or "ai/harness/tasks/" in the input (a shared checkout's path, an executor's own longer
# worktree path, nothing at all) is discarded rather than captured.
_CARD_SUFFIX_RE = re.compile(r'ai/(?:timeline|harness)/tasks/[\w.-]+\.md')

# Where a bare filename (no directory at all) is looked for, relative to a root. Cards
# first: that is where new work is.
BRIEF_DIRS = ("ai/timeline/tasks", "ai/harness/tasks", "plans", "ai/plans")


def candidate_texts(tool_input, keys=("prompt", "description")):
    """Yield each non-empty string field of tool_input that could plausibly carry a brief
    path — prompt and description are where an agent's spawn call, and its transcript-
    recovered equivalent, both put their text."""
    for key in keys:
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            yield v


def brief_tokens(tool_input, keys=("prompt", "description")):
    """Every distinct .md-shaped path token named anywhere in tool_input's prompt and
    description, in the order first seen."""
    tokens = []
    for text in candidate_texts(tool_input, keys):
        tokens.extend(MD_PATH_RE.findall(text))
    seen = set()
    return [t for t in tokens if not (t in seen or seen.add(t))]


def resolve(token, roots):
    """Every plausible on-disk location for a path token, most specific first. An absolute
    path (or a ~-prefixed home path) is returned as itself, unaffected by roots, so a brief
    named by absolute path always works, including across repositories. A relative token is
    tried directly under each root, and — when it names no directory of its own — also
    under each of BRIEF_DIRS beneath each root, so a bare filename resolves the same way a
    full relative path does."""
    t = os.path.expanduser(token)
    if os.path.isabs(t):
        return [os.path.normpath(t)]
    out = []
    for root in roots:
        if not root:
            continue
        out.append(os.path.normpath(os.path.join(root, t)))
        stripped = t[2:] if t.startswith("./") else t
        if "/" not in stripped:
            for d in BRIEF_DIRS:
                out.append(os.path.normpath(os.path.join(root, d, stripped)))
    return out


def canonical_card(token):
    """The part of a path token that identifies a task card and nothing else — everything
    from ai/timeline/tasks/ or ai/harness/tasks/ onwards, with whatever directory prefix
    came before it thrown away. This is what lets the shared checkout's copy of a card and
    an executor's own copy of the same card, sitting under two different directory
    prefixes, count as one card. Returns the token unchanged when it carries no such suffix
    at all — the caller decides whether that means "not a card"."""
    m = _CARD_SUFFIX_RE.search(token or "")
    return m.group(0) if m else token


def find_spawn_prompt(transcript_path, agent_id):
    """The {"prompt": …, "description": …} this agent_id was spawned with, read from the
    coordinator's own durable session transcript at transcript_path. That file records
    every Task/Agent spawn the coordinator's session made as a JSON object, one per line,
    carrying a top-level "toolUseResult" whose own "agentId" field names the spawned
    subagent. Returns None — never raises — when transcript_path is missing, unreadable,
    empty, or holds no record for this agent_id, so the caller can treat every one of those
    as "the brief cannot be determined" and fail open, exactly as a missing or malformed
    hook payload already does."""
    if not transcript_path or not agent_id:
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or '"agentId"' not in line or agent_id not in line:
                    continue  # cheap pre-filter before the more expensive json.loads
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                tur = obj.get("toolUseResult")
                if isinstance(tur, dict) and tur.get("agentId") == agent_id:
                    return {
                        "prompt": tur.get("prompt") or "",
                        "description": tur.get("description") or "",
                    }
    except OSError:
        return None
    return None
