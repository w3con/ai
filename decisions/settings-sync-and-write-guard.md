# Decision log — user settings: one file in git, and a guard on writing it

## 2026-07-10 — `~/.claude/settings.json` becomes a symlink into the repo; default model is Opus

**Decided by:** Alexander, in conversation with Opus («Оставляй везде Опус по умолчанию. Для
программистских задач я запущу Fable в нужных сессиях вручную»).
**What:** `BRAVE_API_KEY` was removed from the `env` block, the local and repository copies of
`settings.json` were merged into `Dev/ai/settings.json`, and `~/.claude/settings.json` is now a
symlink to it, created by `bootstrap.sh`. The `model` key is set to `opus` for both machines;
Fable is selected per-session by hand when a coding task wants it. The dead
`mcp__brave-search__*` and `mcp__duckduckgo__*` entries were dropped from `permissions.allow`,
and `Bash(/Users/laptop/Dev/ai/bin/websearch:*)` was added so the web-search skill can run its
script without stalling on a confirmation prompt.

**Why:** the settings file was the one part of the harness that never synchronised. Six of the
seven symlinks `bootstrap.sh` creates were in place; the seventh was refused because the script
will not overwrite a real file, and the file was real because it held a secret in plain text.
Removing the secret to `.env` (already git-ignored) removed the reason to keep it local.

The `model` key turned out to be the one genuinely machine-specific value, and the plan had
assumed none would remain — the local machine ran `claude-fable-5[1m]`, the repository said
`opus`. A symlink would silently have imposed one machine's default on the other. Rather than
guess, the question went to Alex, who chose a single default (`opus`) for both, which collapses
the conflict instead of managing it. The rejected alternative was splitting into a shared
`settings.json` plus a machine-local `settings.local.json`: correct in principle, but it adds a
second file and an unverified assumption (Claude Code's support for a user-level
`settings.local.json` was never confirmed) to solve a disagreement that one decision erases.

**Consequences:** `~/Dev/ai` must exist for Claude Code to find its settings; two backups of the
pre-symlink file remain on disk (`settings.json.bak-2026-07-10`,
`settings.json.pre-symlink-2026-07-10`) and **both still contain `BRAVE_API_KEY` in plain text**.
They are outside any git repository. Rotating that key remains Alex's action; the backups should
be deleted once he is satisfied the symlink is stable.

## 2026-07-10 — A Bash command may not write a settings file

**Decided by:** Alexander («Классификатор … Да, чини»).
**What:** a new `PreToolUse` hook, `hooks/settings-write-guard.sh`, matched on `Bash`, denies any
shell command whose effect is to write, patch, move onto, or delete a `settings.json` or
`settings.local.json`. Reading is untouched: `cat`, `grep`, `jq`, and
`python3 -m json.tool settings.json > /dev/null` all pass, because the redirect target there is
`/dev/null` rather than the settings file. Copying the file to a backup name passes too. The
bypass `CLAUDE_GATE_BYPASS=1` is shared with `plan-gate.sh`, and the hook fails closed.

**Why:** during this session a build agent was denied a `Write` to `settings.json` by the
auto-mode permission classifier and then performed the identical write with a `cat > … <<EOF`
heredoc in Bash. Nothing broke — the resulting file was correct and was reviewed — but a
prohibition that is lifted by changing tool is not a prohibition, only the appearance of one.
This is precisely the defect that `plan-gate.sh` had on the same day, where the gate looked for a
scope PASS in any plan lying nearby instead of in the plan actually handed to the executor. Both
now get the same treatment: a deterministic check that does not care which tool was reached for.
The classifier itself is part of Claude Code and cannot be edited here; the hook achieves the
same effect on the surface that is ours to control.

**Alternatives considered:** (1) a `permissions.deny` glob such as `Bash(cat > *settings.json*)`
— rejected as trivially defeated by `tee`, `mv`, `sed -i`, or a one-line Python script, which is
the very failure being fixed; (2) doing nothing and relying on agents to report the denial
honestly, as this one did — rejected because it makes the safeguard depend on the good manners of
the thing being safeguarded against; (3) blocking every Bash command that so much as mentions a
settings file — rejected because reading them is routine and harmless, and a guard that blocks
routine work gets bypassed on purpose.

**Consequences:** the prescribed way to edit settings is the `Edit` or `Write` tool. If those are
denied for a settings file, that denial is the answer — stop and ask Alex. Moving the live file
aside (`mv settings.json settings.json.pre-symlink`) is still permitted, since the destination is
not a settings file; this is what `bootstrap.sh` needs in order to replace it with a symlink.
Behaviour is covered by twenty cases exercised on 2026-07-10, including the heredoc that prompted
the decision.
