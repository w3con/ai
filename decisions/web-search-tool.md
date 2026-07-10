# Decision log — the web-search tool

## 2026-07-10 — A committed script does the searching; the skill only decides when to search

**Decided by:** Alexander, in conversation with Opus.
**What:** the phrases «погугли» / «поищи в интернете» / «search the web» now reach a real search.
A skill at `skills/web-search/SKILL.md` (delivered to every project by the user-level symlink
`~/.claude/skills` → `Dev/ai/skills`) calls a committed script, `bin/websearch`, which tries
Tavily, then Brave, then DuckDuckGo, and returns one JSON object on standard output. When all
three fail it exits with code `3`, and only then does the skill fall back to Claude Code's own
`WebSearch` tool as a fourth level.

**Why the chain lives in code and not in the prompt.** Three things had to be true at once:
providers must be tried in order, requests must be paced so they do not hammer anyone's servers,
and a repeated question must not go to the network at all. A model cannot reliably wait between
requests, cannot check whether a provider is actually up, and has no memory of what it asked
fifteen minutes ago. A script can do all three: it keeps a timestamp per provider in
`~/.cache/websearch/` (Tavily 1.0s, Brave 1.1s because its free tier allows one request per
second, DuckDuckGo 2.5s plus jitter), retries twice with growing pauses on HTTP 429 and 5xx, and
caches every answer on disk for fifteen minutes under a key of provider, query and result count.
The cache is the real protection against hammering: an identical repeat never touches the network.
This also follows the standing preference recorded in `memory/feedback_reusable_tooling.md` — a
committed script plus a note in `CLAUDE.md` is the right weight for a self-documenting command;
a skill alone would have been ceremony around a shell call.

**Why the fourth level is in the skill and not in the script.** Claude Code's built-in `WebSearch`
is a model tool, not an HTTP endpoint. No script can call it. So the script says "everything I can
reach is down" by exiting `3`, and the skill — which does have the tool — takes it from there.

**Alternatives considered.** (1) Model Context Protocol servers for Brave and DuckDuckGo, run via
`uvx` — this was in fact the old, broken design, and it solved none of the three requirements: no
ordering, no pacing, no cache, no Tavily, and the servers were registered in `~/.claude/mcp.json`,
a path Claude Code never reads, so they had never once started. The file has been renamed to
`mcp.json.dead` with an explanation inside rather than deleted, so nobody recreates it. (2) A
`UserPromptSubmit` hook matching the trigger phrases — the only mechanism that would fire
deterministically; rejected by Alex, because when he writes «погугли» explicitly the skill's own
description already pulls it in, and a hook earns its keep for *implicit* needs. (3) Bash with
`curl` and `jq` — rejected because `jq` is not guaranteed on the second machine and parsing
DuckDuckGo's HTML with `sed` is unreadable. (4) Python with third-party packages — rejected
because bringing up a second machine already costs one manual step (writing `.env`), and a second
step is a poor trade for eighteen thousand tokens saved once. The script therefore uses nothing
beyond the standard library.

**Known weaknesses, stated rather than hidden.**
- **The DuckDuckGo level will break.** Not if, but when: it is HTML scraping, not an API, and the
  markup changes without notice. The failure is soft — that level returns nothing, the chain moves
  on to `WebSearch`, search keeps working — which is why it was kept: it is free and its death does
  not take the system down. But its parser is roughly a third of the script, and that is a debt
  that will one day come due.
- **Trigger is probabilistic.** The skill is picked up by the model reading its `description`, so
  "погугли" *can* start a search rather than *always* starts one. Verified end-to-end from a
  project with no local copy: a plain «Погугли ESPR textiles delegated act» returned `tavily`.
  If it ever misfires in practice, the deterministic cure is the rejected `UserPromptSubmit` hook,
  about ten thousand tokens of work; it costs nothing on the 97% of prompts that do not match.
- **Brave's free tier allows 2000 requests a month** and nothing counts them. Exhausting it
  produces HTTP 429, the backoff runs, and the chain falls through to DuckDuckGo. If that starts
  happening, add usage logging — a separate task.
- **The skill copies inside `Documents/Validite/.claude/skills/` and `.agents/skills/` were left in
  place** at Alex's decision. They are stale — they still declare MCP tools that do not exist — but
  they do not shadow the user-level skill: verified by running Claude inside Validité, which picks
  the new one. They mislead a reader, they do not break a run.
- **`BRAVE_API_KEY` was exposed in session output on 2026-07-10.** Both plaintext backups of the
  old settings file have been deleted, but the key also sits in the session transcripts under
  `~/.claude/projects` and in `~/.claude/file-history`, which cannot be scrubbed without destroying
  those histories. Only rotation closes this. Alex is aware and will rotate.

**Consequences.** The skill exists once, in `Dev/ai/skills/web-search/`, and reaches every project
through the user-level symlink; it was removed from the `kb-skeleton` template so that new projects
no longer come with a private copy that begins ageing the day it is created. Keys live in
`Dev/ai/.env`, which is git-ignored, so `git pull` does not carry them — the second-machine
procedure in `ai_readme.md` says so explicitly, and warns about the trap that matters: without
`.env` the script does not fail, it quietly falls through to DuckDuckGo, and the only way to notice
is to read the `provider` field it prints.
