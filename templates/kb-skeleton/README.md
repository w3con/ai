# Local-first KB Skeleton

This directory is a portable template for setting up a local-first, Obsidian-based knowledge base on any project. It is the pattern extracted from Validité and intended to be reused for health, travel, or any other project where the same local-first KB discipline makes sense.

## Placeholders

Three placeholders must be substituted when scaffolding a new project:

| Placeholder | Meaning | Example |
|---|---|---|
| `{{PROJECT_NAME}}` | Short human name of the project | `HealthTrack` |
| `{{PROJECT_DESCRIPTION}}` | One-line description used by the semantic indexer | `a personal health tracking and research tool` |
| `{{MEMORY_DIR}}` | Absolute path to the Claude Code project-scoped memory directory | `/Users/alice/.claude/projects/-Users-alice-repos-healthtrack-/memory/` |

The `/new-kb` skill substitutes these automatically when it scaffolds from this skeleton.

## Contents

```
CLAUDE.md.template       → becomes CLAUDE.md after placeholder substitution
KB-CONVENTIONS.md        → frontmatter contract; already generic
bin/relation-build       → Builder v3: writes ai: frontmatter + Related footer
bin/kb-index             → generates kb/_index.md
.claude/
  agents/
    kb-retriever.md      → cross-domain retrieval agent
    kb-curator.md        → persistence agent (writes to kb/)
    vld.md               → proactive reviewer / quality-gate
    user-profiler.md     → maintains user memory store
  skills/
    deep/SKILL.md        → manual trigger for kb-retriever
    review/SKILL.md      → document quality-gate reviewer
    verify/SKILL.md      → factual claim verifier (web)
    web-search/SKILL.md  → enforced search tool priority
kb/
  _index.md              → generated map; placeholder until kb-index runs
  .gitkeep               → keeps the directory in git
.gitignore               → .env, .DS_Store, __pycache__, .obsidian/
README.md                → this file
```

## Sibling-path / cross-repo convention

If a code repository (e.g. `myproject-web`) needs to read the KB, document this in that repo's `CLAUDE.md`:

> KB lives at `../myproject-kb` (or the env var `MYPROJECT_KB`). Read it with Read/Grep/Glob from there. Do not edit the KB from this repo.

Optionally, add a gitignored symlink `.kb -> ../myproject-kb` in the code repo for a stable in-repo path. Graduate to a git submodule later if CI or a teammate needs versioned access.

## The `kb/` folder is the Obsidian vault

Open the `kb/` subdirectory (not the repo root) as your Obsidian vault. This keeps Obsidian away from `bin/`, `.ai/`, and other machine internals. Wikilinks use document slugs (the filename without `.md`); Obsidian auto-heals in-app renames.

## Getting started after scaffolding

1. Open `kb/` as an Obsidian vault.
2. Create your first collection folder under `kb/` (e.g. `kb/Strategy/`).
3. Add your first document with a YAML frontmatter block (see `KB-CONVENTIONS.md`).
4. Run `bin/kb-index` to generate `kb/_index.md`.
5. Run `bin/relation-build` to populate the `ai:` frontmatter blocks (requires `ANTHROPIC_API_KEY` in `.env`).
6. Ask Claude `/deep <query>` to test cross-domain retrieval.
