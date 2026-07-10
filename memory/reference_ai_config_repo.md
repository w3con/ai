---
name: reference_ai_config_repo
description: "The versioned Claude Code configuration lives at ~/Dev/ai — commit config changes there, not to ~/.claude directly"
metadata: 
  node_type: memory
  type: reference
  originSessionId: a86b10f2-1b23-4d59-9479-6ba6643c0de5
---

`/Users/laptop/Dev/ai/` is a git repository that contains the versioned source of truth for all Claude Code configuration. `~/.claude/` files are symlinks into this repo, wired up by `bootstrap.sh`.

Files managed here: `CLAUDE.md`, `settings.json`, `statusline-command.sh`, `memory/`, `agents/`, `skills/`, `hooks/`.

**How to apply:** when editing any Claude Code config (statusline, CLAUDE.md, settings, agents, skills), commit to `/Users/laptop/Dev/ai/`, not to `~/.claude/` directly. If `~/.claude/statusline-command.sh` is not a symlink (check with `readlink`), copy the updated file into the repo and commit there.

Note: in the June 2026 session, `~/.claude/statusline-command.sh` was a regular file (not a symlink) — bootstrap may need to be re-run to restore the symlink: `bash /Users/laptop/Dev/ai/bootstrap.sh`.
