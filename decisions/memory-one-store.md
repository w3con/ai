# Decision log — one memory store, and the boundary that defines it

## 2026-07-10 — Project-level memory is abolished; there is one store for every project

**Decided by:** Alexander, verbatim: «Я хочу, чтобы не было больше никаких возможностей сохранять
что-то в проектный [стор]. Всё должно сохраняться в общее хранилище касательно искусственного
интеллекта, чтобы все проекты всегда это видели», with the refinement that plans stay in their
project («конкретно планы… пусть лежат в самом проекте») and «согласен, делай так».

**What.** Memory now lives in exactly one place, `~/Dev/ai/memory/`, under version control, reaching
every project and both machines. Each `~/.claude/projects/<slug>/memory` is a symlink to it, so
writing "to a project's memory" writes to the one store. A `PreToolUse` hook,
`hooks/memory-store-guard.sh`, refuses any `Write`/`Edit` whose real path lands in a project memory
directory that is not the shared store, and `bootstrap.sh` creates the symlinks on any machine,
repairing a wrong or broken one and refusing to touch a non-empty real directory. Ten entries were
consolidated from four scattered directories; one pair of near-duplicates was merged; broken
`[[links]]` to rules that had been promoted into `CLAUDE.md` were repaired to point there.

**The boundary — this is the part worth keeping.** The line is *not* between "shared memory" and
"project memory"; that split is gone entirely. The line is between **memory** and **a project's own
documents**:
- **Memory** answers "how does Claude work" — what Alex requires, where he corrected me, which tool
  to use for what. By nature this is not owned by any project, so it lives in one store and follows
  us everywhere.
- **A project's documents** answer "what did this project decide" — its architecture, its
  trade-offs. Those belong in that project's `ai/decisions/` and `ai/arch/`, versioned with the
  code and readable by a human, not only by me. Plans likewise describe work *on a project* and
  stay in it.

This boundary was already latent in the project `CLAUDE.md` ("repo docs, not personal memory, are
the home for project decisions"); it had simply never been said out loud, so personal memory had
been accumulating things that were not its to hold.

**Why this was not the sacrifice it first looked like.** I initially framed it as a trade —
"one store means a note about one project becomes visible in all of them" — and said so with more
confidence than the facts warranted. Reading the ten existing entries settled it: nine are about
method, not about any project. There was almost nothing to divide. For the rare entry that is about
method yet only true inside one project, a `scope: <project>` field in the frontmatter carries that
fact (two entries now use it: `design-reproduce-not-improvise` → `validite-web`, `kb-entry-via-index`
→ `validite-kb`). One field, no second store.

**Alternatives considered.**
1. **Two stores kept in sync** — the status quo, one shared and one per project. Rejected: it is the
   exact failure this session kept hitting. Earlier today I wrote three lessons into the `Dev/app`
   project store; on the second machine they would simply not exist. A store that a second machine
   cannot see is not memory, it is a local note.
2. **One store by convention, enforced only by a rule in `CLAUDE.md`.** Rejected by Alex in as many
   words: he asked that there be *no possibility* of writing to a project store, not a discouragement.
   A rule that depends on my remembering it is exactly what a hook is for — and today proved that a
   safeguard which can be sidestepped (the settings classifier, defeated by switching from `Write`
   to a Bash heredoc) is not a safeguard. Hence `memory-store-guard.sh`.
3. **Copy the shared store into each project** instead of symlinking. Rejected: N copies drift, which
   is the disease, not the cure. The symlink means there is only ever one file.
4. **Path matching by string** in the guard, as the first settings guard did. Rejected: string rules
   gave three false positives in one hour today, including one that stitched a dangerous command out
   of three innocent lines across newlines. The memory guard compares `os.path.realpath`, so a write
   through a project symlink resolves into the shared store and is allowed, while a write to a real
   project directory is denied — decided by where the path actually leads, not how it reads.

**Consequences and the cost, stated plainly.** A note genuinely specific to one project is now
visible in all of them unless it carries `scope:`; that is the accepted price, and it is small
because almost nothing is that specific. A brand-new project still creates a fresh real `memory/`
directory the first time the harness touches it — the hook cannot create a symlink, only refuse the
write, so the first write there is denied with an instruction to run `bootstrap.sh`. Automating that
away is a separate task if it ever grates. The store, like `settings.json`, now depends on `~/Dev/ai`
existing. And `~/.claude/projects/<slug>` is derived from the project's path, so renaming a project
directory mints a new store; the same hook and `bootstrap.sh` catch it.
