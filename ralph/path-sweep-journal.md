# Path sweep — journal

This file is the only memory the loop has. Each iteration reads it first and writes to it last.

## Areas

- [x] 1. `~/Dev/ai` — the configuration repository: hooks, candidates, bin, skills, agents, memory, bootstrap, templates
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
standard library. It now recognises **two** shapes of fault.

The first, which it has understood since it was written, is an absolute path of the form
`/Users/<name>` where `<name>` is not one of the documented placeholders — one machine's
own home directory.

The second was added on 2026-08-13 and is an absolute path of the form `/Volumes/<name>` —
a location on a mounted disk. The rule is deliberately broad: it refuses *every* volume
name rather than only the two currently in use, so that the next external disk to be
plugged in is caught on the day it is first written down instead of after it has broken
something. The matching character class excludes the shell glob character on purpose, so a
test such as `[[ "$dir" == /Volumes/* ]]` — which asks whether a path happens to sit on a
volume and names no particular one — is not mistaken for a hard-coded location.

The shape it still does **not** recognise is a hard-coded `~/Dev/app`, or any other
`$HOME`-relative path naming a repository that does not sit at the same place on both
machines. This one is genuinely harder than the other two, because `~/Dev/ai` is correct
everywhere while `~/Dev/app` is correct on only one machine, and nothing in the text of
either path distinguishes them — the guard would need a list of which repository names are
machine-specific. Widening it to that shape is the next piece of guard work, and the three
occurrences that existed when this was written have already been fixed by hand (see the
2026-08-13 entry below), so the widening is prevention against recurrence rather than a
backlog of live faults.

It decides which files matter by calling them *load-bearing*. A file is load-bearing when it
carries one of the extensions `.sh`, `.bash`, `.zsh`, `.py`, `.json`, `.yaml`, `.yml`,
`.toml`, `.template`, `.conf`, `.cfg` or `.ini`; when it has no extension at all and sits
directly under `bin/` or `hooks/`, where such a file is a command; or when it is Markdown
sitting under `memory/`, `skills/`, `agents/` or `commands/`, all four of which an agent
reads as a standing instruction about what to do now rather than as a record of the past.

Two behaviours added on 2026-08-13 are worth knowing before trusting a quiet run. Both
sides of the path arithmetic are now resolved through every symbolic link before they are
compared; they used to be merely made absolute, and that silently disabled the entire check
whenever the two sides disagreed about a link. The failure was not hypothetical — it was
found within minutes of first use, because macOS makes `/var` a link to `/private/var`, so
naming a file in a temporary directory produced a relative path that resolved to nothing,
the file was skipped, and the run reported success. And a file named explicitly on the
command line that cannot be read is now reported and exits `2`, instead of being passed
over in silence; a file listed by git but missing from disk is still an ordinary deletion
and says nothing.

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
was invoked wrongly, pointed at something that is not a git repository, or handed a named
file it could not read.

## Where the guard is already wired in

`~/Dev/ai` runs it on every commit, from `.githooks/pre-commit`, in its `--staged` form;
`core.hooksPath` there is the relative value `.githooks`, which is the only form that works
on both machines. No other repository runs it yet, and wiring each one in is part of that
repository's own area below.

## Log

### 2026-08-13 — area 1, the configuration repository `~/Dev/ai`

**Area worked:** area 1, and it is now ticked. The guard was also widened by one step, and
one live fault was found and corrected that the sweep was not looking for.

**What was found.** The guard, in the form it had at the start of this iteration, was
already quiet across the whole repository — every `/Users/<name>` occurrence left in it is
a comment recording a literal that was removed, a document under `decisions/` or `plans/`,
the guard's own explanatory text, or the documented `alice` placeholder in the
knowledge-base skeleton. Searching by hand for the shapes the guard did not yet understand
turned up twenty-seven `/Volumes/SSD` occurrences and thirteen `/Volumes/Documents` ones,
of which the great majority are the historical record and correctly stay. After the
widening, nine lines in six files were reported, and they divide into two groups.

Five of the nine are correct as written and were made explicit rather than rewritten. Four
are in `bootstrap.sh`, where the business vault is found by trying a list of candidate
locations and taking the first that actually exists, plus the error message that tells the
reader which places were tried; one is in `hooks/git-sync-notice.sh`, which resolves the
application checkout the same way. Naming a location that may not exist is only a fault
when something depends on it existing, and in a first-that-exists-wins list nothing does.
Each of those lines now carries the marker `path-check: allow` with a short reason beside
it, so the exception is visible where a reader will meet it.

Two more of the nine are the two frontmatter fields of `memory/machine-ssd-python-path.md`,
a note whose entire subject is that one of the two machines needs a particular Python
interpreter. Its body already carried the marker; the two fields did not, and they now do,
written as YAML comments so that the values themselves are untouched — this was checked by
parsing the frontmatter afterwards and confirming every field reads exactly as before.

The remaining occurrences were genuine faults. `memory/feedback_pilier_private_kb.md` is a
standing instruction telling an agent where the two Pilier repositories are, and it named
them by this machine's own volume, so on the other machine it would send the reader
somewhere that does not exist. A second fault the guard cannot yet see was found by hand:
`memory/project_app_no_real_data_yet.md` and the index line for it in `memory/MEMORY.md`
both located the application repository at `~/Dev/app`, which is the *other* machine's
path — there is no such directory here. And `candidates/git-sync-notice.sh` had fallen out
of step with the hook installed from it, still carrying the pre-fix line that assumed the
application repository sits at `$HOME/Dev/app`; every other candidate in that directory is
byte-identical with its installed hook, so this one was a loaded gun aimed at the next
person to install from it.

**The live fault nobody was looking for.** Writing the first test suite `hooks/inbox-stop.py`
has ever had exposed something worse than any of the above, and it was failing on this
machine right now. That hook decides whether the current turn belongs to the application
repository by comparing the session's working directory against the repository path. It
built its own side with `os.path.realpath`, which follows symbolic links, and the session's
side with `os.path.abspath`, which does not. On this machine `~/Dev` is a symbolic link
onto an external volume, so its own side came out as `/Volumes/SSD/Dev/validite/validite-app`
while a session working in that very checkout reports `~/Dev/validite/validite-app`, and the
two never matched. The hook therefore delivered nothing, ever — and nothing was visible from
outside, because a `Stop` hook that decides it has nothing to say is indistinguishable from
one that is working. This is the same disease in a subtler dress: not a literal path written
down, but two ways of resolving one. Both sides are resolved identically now.

**What was fixed, in order.** The guard learned the mounted-volume shape, and separately
stopped being able to skip a file in silence. `bin/hook-install` learned to install a Python
hook. `hooks/inbox-stop.test.py` was founded. `hooks/inbox-stop.py` had its comparison
corrected and its marker added. `hooks/git-sync-notice.sh` had its marker added and its
candidate brought back into step. `bootstrap.sh` and `memory/machine-ssd-python-path.md`
gained their markers. `memory/feedback_pilier_private_kb.md`,
`memory/project_app_no_real_data_yet.md` and `memory/MEMORY.md` had their machine-specific
locations replaced by machine-neutral descriptions.

**The obstacle that was cleared rather than walked around.** Both hooks touched here are
live files that may only be changed by assembling a candidate and installing it with
`bin/hook-install`, which refuses unless that hook's own test suite passes. For
`hooks/inbox-stop.py` that route did not exist at all: the installer's live path was
spelled with a hard-coded `.sh` suffix, so it could install a shell hook and nothing else,
and on top of that this hook had no test suite, which the installer's fifth refusal
requires. The tempting move was to edit the live file by hand "just this once", and that is
exactly how a rule stops being a rule. Instead the installer was taught both languages —
its `--check` half already knew about Python and only its installing half did not — and the
missing suite was written. The route is now open for every hook in the directory.

**What was deliberately left alone, and why.** Everything under `decisions/`, `plans/`,
`_legacy/`, `session/` and `readme.md`, all of which record what actually happened on a
given day; rewriting evidence to satisfy a checker destroys the only thing those documents
are for. The `~/Dev/app` inside `memory/feedback-commit-by-naming-paths.md`, because that
sentence narrates an incident on 2026-08-07 and the path is part of the account, not an
instruction about where to go now. The comment lines in `bin/hook-install`,
`candidates/plan-gate.sh`, `candidates/card-touch-gate.sh`, `hooks/plan-gate.sh` and
`hooks/card-touch-gate.sh` that quote the literal `/Users/laptop/Dev/ai/hooks` they were
written to replace, which exist precisely so a later reader understands what the code
around them is defending against. The `alice` placeholder in `templates/kb-skeleton/`. And
`settings.json.template`, which was already correct — it uses the `__HOME__` placeholder
throughout — and was therefore not touched, so no redeploy is owed and the harness stamp
still matches, which was checked.

**What was proved, and how.** The widened rule was proved on a scratch fixture built for
the purpose, holding twelve files. Five had to fire and did: a `/Volumes/SSD` path in a
shell script, a `/Volumes/Documents` one, a `/Volumes/BigDisk` one using a volume name
never seen in this configuration, an old-style `/Users/laptop` one proving the original
rule still bites, and a `/Volumes` path inside a Markdown file under `memory/`. Seven had
to stay silent and did: the same literal inside a comment, the same literal on a line
carrying `path-check: allow`, the same literal in a file under `decisions/`, the glob
`/Volumes/*` that names no particular volume, the `alice` and `__HOME__` placeholders, a
Markdown file outside the instruction directories, and a plain `.txt` file. A thirteenth
case proved the silent-skip repair: a file named on the command line that does not exist
is now reported and exits `2`.

The widened `bin/hook-install` was proved against a scratch hooks directory through its
`HOOK_INSTALL_HOOKS_DIR` override, which exists for exactly this. Seven checks, all
passing: a Python hook installs when its suite passes; a bare name with no suffix finds the
live Python file; a Python candidate that does not parse is refused, and the refusal names
the Python parser rather than bash; a Python candidate whose suite fails is refused and the
live file is left untouched; a shell hook still installs, unchanged; a broken shell
candidate is still refused by bash; and a hook with no suite is still refused.

The new `hooks/inbox-stop.test.py` holds eighteen checks. Nine of them failed against the
installed hook and all eighteen pass against the corrected one, which is the proof that the
symbolic-link fault was real and that the suite would have caught it. Then all eight hook
suites in the directory were run together and all eight passed — eight rather than the
previous seven, because `inbox-stop` now has one. Every shell file was checked with
`bash -n` and every Python file with `python3 -m py_compile`. `bootstrap.sh --dry-run`
confirmed the vault is still found after the markers were added to its candidate list.
`bin/hook-install --help` still answers without doing anything. And the guard was run over
the whole repository and is quiet.

**What was committed.** The twelve files this iteration changed, staged by name: the guard
and the installer under `bin/`, `bootstrap.sh`, the two hooks and the new suite under
`hooks/`, the two candidates, the four memory files, and this journal.

**What comes next.** Area 2, the deployed configuration under `~/.claude` — the parts of it
that are not symbolic links back into this repository. Two smaller pieces of work are also
now on the record and should not be forgotten: teaching the guard the `~/Dev/app` shape,
and considering whether the fact that the application checkout sits at a different path on
each machine deserves a memory of its own, since several files now depend on that
convention and none of them states it.

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
