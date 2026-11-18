# Local-first knowledge-base scaffold

This directory is a reusable starting point for a project-local Markdown knowledge base. It does not require access to any other project or private service.

## Placeholders

Replace `{{PROJECT_NAME}}` and `{{PROJECT_DESCRIPTION}}` in `CLAUDE.md.template` when creating a project from this scaffold. Preserve their exact spelling for any generator that substitutes them. The optional `{{MEMORY_DIR}}` placeholder is retained only for compatibility with older scaffold consumers; this public template does not require or create a memory integration.

## Contents

`CLAUDE.md.template` is the project instruction template. `KB-CONVENTIONS.md` defines the Markdown metadata contract. `.claude/settings.json` registers a local index hook. The `.claude/agents/` and `.claude/skills/` directories contain optional workflows. `kb/_index.md` is an initial placeholder for the generated knowledge-base index.

The executable files under `bin/` are part of this scaffold. Consult the checked-out commands and their help before relying on their options.

## Getting started

1. Create a project repository from this directory while preserving the scaffold's relative paths.
2. Replace the required project placeholders using the generator or process that created the project.
3. Review the conventions and generated settings for the tools installed in that project.
4. Add project-owned Markdown documents under `kb/` and keep generated files under their documented ownership.

No search provider, external credential, memory store, or network service is required by this template.
