---
name: never-pipe-a-checking-tool-through-tail
description: Never run a checking or committing tool through `| tail` or `| head` — it hides the tool's own verdict and replaces its exit code with the pager's; redirect to a file and read the code instead
metadata:
  type: feedback
---

A tool that checks something reports in two channels: what it prints, and the code it exits with. Piping it through `tail`, `head` or `grep` destroys both. The verdict is usually printed last, so a tail that keeps the last few lines still cuts it when the tool prints a long trailing report; and in a shell pipeline the exit code belongs to the last command, so a failing check comes back as success.

**Why:** it cost me twice in one session on 2026-08-23. First `bin/trace-check | tail` printed `EXIT=0` while the real exit was 1. Then `python3 bin/commit-paths ... | tail -8` swallowed the script's own post-commit leftover report — the one it prints specifically to say that a regenerated `ai/REGISTRY.md` was left stale in the staging area — and swallowed its non-zero exit with it. I only found the stale index entry later, by reading `git status` by hand, and briefly took a working safeguard for a defect worth founding a card on.

**How to apply:** run the tool plainly and read all of it, or redirect it to a file and read `$?` immediately (`tool > out.txt 2>&1; echo "EXIT=$?"; cat out.txt`). Trim output only after the exit code has been read, and never trim the tail of a tool whose verdict is a summary. This is the practical face of [[feedback-check-the-checker]]: a safeguard you cannot see fire is a safeguard you do not have.
