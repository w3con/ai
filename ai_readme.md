# Skills and shared components

## Skills

A skill is stored in `skills/<name>/SKILL.md`; its directory name is the slash-command name in clients that support skill invocation. Skills should describe their inputs, workflow, tool dependencies, failure handling, and output contract.

| Skill | Path | Purpose |
|---|---|---|
| `grill-with-docs` | `skills/grill-with-docs/SKILL.md` | Stress-tests a plan against project terminology and existing decisions, then updates context and decision records when warranted. |
| `web-search` | `skills/web-search/SKILL.md` | Performs a web lookup using the toolkit's search command when available, and follows its documented result and failure contract. |

Project-specific skills belong in the project that owns them. Private or machine-specific skills should not be copied into the shared core.

## Agents

Reusable agent definitions live under `agents/`. Check each definition's frontmatter for its name, description, and supported tools. Their behavior must match the commands and workflows available in the current installation; a descriptive prompt does not create a missing command or tool.

The `executor-sonnet-4-6` name is retained for installations that configure it explicitly. This definition does not select or require a model; configure model selection in the host's supported agent configuration.

## Templates

Reusable project files live under `templates/`. `templates/kb-skeleton/` provides a local Markdown knowledge-base scaffold. `templates/plan-card.md` preserves the established task-card field and checkpoint layout, including compatibility with existing parsers.

## Commands and installation

`bin/` contains command-line utilities and `hooks/` contains integration hooks. Consult the root README and each command's own help or header for prerequisites and supported arguments. Install the toolkit with the repository's current installer; private integrations are optional and are supplied separately.
