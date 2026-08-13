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

## What the guard understands today

This section is here so that no iteration has to read `bin/path-check` from top to bottom
merely to find out how far it has been widened. Whoever widens it updates this section in
the same commit.

The guard is `~/Dev/ai/bin/path-check`, a Python program with no dependencies beyond the
standard library. As of the founding of this journal it recognises exactly one shape of
fault: an absolute path of the form `/Users/<name>` where `<name>` is not one of the
documented placeholders. It does not yet recognise a checkout location that exists on only
one of the two machines — `/Volumes/SSD/...`, `/Volumes/Documents/...`, or a hard-coded
`~/Dev/app` pointing at a repository that actually lives elsewhere. Widening it to those
shapes is part of the work still ahead, and the prompt requires that each new rule first be
proved to fire on a deliberately broken scratch fixture and to stay quiet on the cases that
are meant to be exempt.

It decides which files matter by calling them *load-bearing*. A file is load-bearing when it
carries one of the extensions `.sh`, `.bash`, `.zsh`, `.py`, `.json`, `.yaml`, `.yml`,
`.toml`, `.template`, `.conf`, `.cfg` or `.ini`; when it has no extension at all and sits
directly under `bin/` or `hooks/`, where such a file is a command; or when it is Markdown
sitting under `memory/`, `skills/`, `agents/` or `commands/`, all four of which an agent
reads as a standing instruction about what to do now rather than as a record of the past.

It deliberately passes over four things. A comment line, because a comment cannot be
executed and several comments in this repository exist precisely to record the literal that
was removed. Anything under `decisions/` or `plans/`, because those are the historical
record and rewriting evidence to satisfy a checker destroys the only thing those documents
are for. The placeholder names `__HOME__`, `alice`, `youruser`, `username` and `user`. And
any single line carrying the marker `path-check: allow`, which is the visible, searchable
escape for a case nobody foresaw.

It is invoked either with no arguments, in which case it checks every tracked file in its
own repository; with `--root DIR` to check a different repository; with `--staged` to check
only what is staged, which is the form a commit hook wants; or with explicit file paths. It
exits zero when it found nothing, one when it found at least one violation, and two when it
was invoked wrongly or pointed at something that is not a git repository.

## Log

### 2026-08-13 — founding the journal

**Area worked:** none of the ten. This iteration did the thing the prompt reserves as a
complete iteration's work on its own, which is to bring this journal into existence, because
without it every later iteration would start from nothing and repeat the same searching.

**What was found.** The directory `~/Dev/ai/ralph/` already existed, holding the prompt
itself as `path-sweep.md` and a `logs/` directory, but it held no journal, so this loop had
no memory at all. The guard `~/Dev/ai/bin/path-check` does already exist, is executable, and
is written clearly enough that its behaviour could be summarised without running it; that
summary is the section above, recorded so that the next iteration is not obliged to re-read
the program merely to learn its current reach.

**What was fixed.** Nothing was fixed, because finding and fixing faults is the work of the
numbered areas and this iteration deliberately did not begin one. No file outside this
journal was modified.

**What was deliberately left alone, and why.** Every one of the ten areas, untouched. The
prompt is explicit that founding the journal is where this iteration stops, and the reason is
sound: an iteration that both founded the journal and swept an area would be writing its
record of the sweep into a file whose own shape it was still deciding, and the risk is that
the sweep gets recorded badly or not at all. The guard was also left exactly as it is,
including its known gap around `/Volumes/...` paths, because the prompt requires each
widening to be proved against a deliberately broken fixture first and that proof is real
work that deserves its own iteration.

**What was proved.** That the journal did not previously exist, by attempting to read it and
receiving a plain "no such file" from the filesystem. That the guard exists and is
executable, from a directory listing showing the executable bit set on all three of user,
group and other. Nothing else was claimed and nothing else was run.

**What comes next.** Area 1, the configuration repository `~/Dev/ai` itself. It is first for
a reason worth writing down: it contains the guard, the hooks, the skills and the agents, so
a fault living there is a fault that reaches every project on both machines, and it is also
the repository whose commit hook must eventually run the guard for every other repository's
sweep to stay honest.

**What was committed.** This journal file alone, staged by name.
