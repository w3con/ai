# The task: no wrong path ever again, anywhere on this machine

You are one iteration of a loop that repeats until this machine can no longer be broken by a path written for the other machine. The same prompt is fed to you again and again. You do not remember previous iterations. Everything you learn must be written to disk, or it is lost.

## The disease you are curing

This person works on two machines. The configuration, the hooks, the skills, the memory store and several repositories are shared between them through git. Their home directories are different: one is `/Users/laptop`, the other is `/Users/tknff`, and the checkouts sit in different places too — `~/Dev` on this machine is a symbolic link to `/Volumes/SSD/Dev`, and the business vault is at `/Volumes/Documents/startup/Validite` here and somewhere else there.

Every time an absolute path naming one machine's own home, or one machine's own checkout location, is written into a file that both machines run or read, that file silently stops working on the other machine. This has already cost real damage, and each time it was found the same expensive way — something stopped working, nobody noticed for hours, and the cause turned out to be one literal path:

* Two `PreToolUse` hooks looked for their shared helper module at a literal path. On this machine `plan-gate.sh`, which fails closed by design, denied **every** agent spawn with an internal error; `card-touch-gate.sh`, which fails open, silently stopped enforcing anything at all and nobody could have told from the outside.
* All seven hook test suites defaulted to the same literal path, so on this machine every one of them reported hundreds of failures against a script that does not exist here — a red result that said nothing about the hooks.
* A skill told the model to run a search script at a path that is not there.
* The `Stop` hook and the `SessionStart` hook both named the application repository by a literal path.
* Three scripts resolved the business vault to a directory that does not exist, so the vault silently counted as absent.

The owner's instruction, in his own words, is that this must never happen again — not one hook that failed to fire, not one thing blocked, not any problem at all traceable to a path left behind by synchronisation between the two machines.

## What you must actually do

**Work through the areas listed in the journal, in order, one at a time.** The journal is your only memory. Read it first, every single iteration, before doing anything else:

    ~/Dev/ai/ralph/path-sweep-journal.md

If that file does not exist yet, create it from the template at the bottom of this prompt and stop there for this iteration — founding the journal is a complete iteration's work.

For each area, the work is the same four steps:

1. **Find.** Search that area for absolute paths that name a specific machine: anything matching `/Users/<name>/`, and anything naming a checkout location that exists on only one of the two machines (`/Volumes/SSD/...`, `/Volumes/Documents/...`, a hard-coded `~/Dev/app` where the repository is really somewhere else). Look inside scripts, configuration files, JSON, YAML, plist files, git config, shell startup files, agent and skill definitions, hook registrations, and any Markdown that an agent reads as a standing instruction rather than as a record of the past.

2. **Judge each hit.** Not every hit is a fault, and rewriting the ones that are not is itself damage. A path is **fine** when it is inside a comment that explains a path that was already removed, when it is in a document under `decisions/`, `plans/`, `ai/incidents.md` or any `archive/` directory recording what actually happened on a given day, when it is a quoted piece of evidence such as a log line, when the name is a documented placeholder (`__HOME__`, `alice`), or when the machine-specific path is the very subject of the note and the note says so. A path is a **fault** when something executes it, imports from it, registers it, or reads it as an instruction about what to do now.

3. **Fix each fault.** Derive the location instead of naming it: from the running file's own position, from `$HOME` or `os.path.expanduser`, from an environment variable the machine already sets, from a short list of candidate locations where the first that actually exists wins, or from the `__HOME__` placeholder that `bootstrap.sh` substitutes at deploy time. Where an occurrence genuinely must stay, put the marker `path-check: allow` on that line, so the exception is visible in the file itself rather than hidden in a checker.

4. **Prove the fix.** Run whatever that area has: the hook's own test suite, the script's `--help`, the repository's checks, `bash -n`, `python3 -m py_compile`. A fix you have not run is not a fix. Then run the guard, `~/Dev/ai/bin/path-check`, over that repository, and confirm it is quiet.

Then **write what you did into the journal** — which area, what you found, what you fixed, what you deliberately left alone and why, and what you proved. Mark the area's box. Commit your work in that repository before the iteration ends, naming the paths you changed explicitly.

## The guard, and extending it

`~/Dev/ai/bin/path-check` already exists and already refuses a machine-specific home directory in any load-bearing file. Read it before you change it. It currently understands only `/Users/<name>/`. Part of this task is to widen it, carefully and one step at a time, to the other shapes listed above, and to wire it into the commit hook of every repository that does not yet run it — and each time you widen it, first prove the new rule fires on a deliberately broken scratch fixture and stays quiet on the exempt cases. A checker nobody proved is worth nothing.

## Rules you must not break

* **Never `git add -A` or `git add .`.** Stage exactly the paths you changed, by name. Other sessions and other agents work in these same trees and a blanket stage sweeps their unfinished work into your commit.
* **Never spawn another agent**, never run `bin/card-launch`, never run anything that starts a paid worker. This loop is one process, not a fleet.
* **Never edit a live hook under `~/Dev/ai/hooks/` in place.** Assemble the change in `~/Dev/ai/candidates/` and install it with `~/Dev/ai/bin/hook-install <candidate> <hook-name>`, which refuses unless that hook's own suite passes against the candidate.
* **Never edit `~/.claude/settings.json` by hand.** It is rendered from `~/Dev/ai/settings.json.template`; edit the template, then run `~/Dev/ai/bootstrap.sh` and check that `shasum -a 256 ~/.claude/settings.json | cut -d' ' -f1` prints exactly what `cat ~/.claude/.harness-stamp` prints.
* **Never copy a credential out of a `.env` file into any document, card or commit message.** Name the variable that holds it.
* **Never rewrite the historical record** to make a checker pass. If a decision document or an incident log quotes a real path from a real event, that path stays.
* **Commit messages are in English and follow Conventional Commits**: `type(scope): summary in the imperative`, with a body in full connected prose. Everything else you write — the journal included — is in the same plain, fully-explained prose, never clipped fragments.
* **Do not touch product source code** under `dpp_demo/app/`, `dpp_frontend/src/` or `dpp-vldt/src/` in the application repository. A hook refuses those edits, and the refusal is correct.

## One area per iteration

Do not try to finish everything in one pass. Take the next unfinished area, do those four steps properly, write the journal, commit, and end the iteration. The loop will bring you back.

## When this is genuinely finished

Only when every area in the journal is ticked, the guard runs clean across every repository listed there, the guard is wired into every one of their commit hooks, every hook test suite passes, and a fresh full sweep from the top finds nothing new — then, and only then, write the exact line:

    <promise>PATH SWEEP COMPLETE</promise>

Do not write that line to escape the loop. If you are unsure, you are not finished.

---

## Journal template — copy this into `~/Dev/ai/ralph/path-sweep-journal.md` if it does not exist

```markdown
# Path sweep — journal

This file is the only memory the loop has. Each iteration reads it first and writes to it last.

## Areas

- [ ] 1. `~/Dev/ai` — the configuration repository: hooks, candidates, bin, skills, agents, memory, bootstrap, templates
- [ ] 2. `~/.claude` — the deployed configuration: settings.json, the symlinks, plugins, statusline, anything not a symlink into the repository above
- [ ] 3. `/Volumes/SSD/Dev/validite/validite-app` — the application repository: bin, .githooks, .claude, ai, kb
- [ ] 4. The other git repositories under `~/Dev` — enumerate them into this journal first, then take them one at a time
- [ ] 5. The business vault at `$VALIDITE_VAULT_ROOT`
- [ ] 6. Shell startup and environment: `~/.zshenv`, `~/.zshrc`, `~/.zprofile`, `~/.profile`, anything they source
- [ ] 7. Per-repository git configuration on this machine: `core.hooksPath`, merge drivers, worktree settings — an absolute value here stops every hook running while the commit still exits zero
- [ ] 8. Scheduled and background jobs: launchd plists under `~/Library/LaunchAgents`, cron entries, anything that runs unattended
- [ ] 9. Editor, tool and application configuration that names a checkout by path
- [ ] 10. A final full sweep from the top that must find nothing new

## Log

(One dated entry per iteration: which area, what was found, what was fixed, what was left alone and why, what was proved, what was committed.)
```
