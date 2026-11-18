# Shared AI engineering configuration

This repository provides reusable instructions, agents, skills, hooks, commands, settings templates, and project scaffolds. Use only interfaces and scripts present in the checked-out version.

## Writing guidance

@STYLE.md

@.private/rules.md

The installer creates an empty `.private/rules.md` when no private rules are configured, so this optional import remains harmless in a public-only installation.

## Working in a project

Before changing files, identify the repository root and read its local instructions, task description, relevant implementation, and tests. Preserve established paths and interfaces unless the task explicitly changes them. Keep changes within the authorized scope and verify the affected behavior with available checks. Do not claim a check passed unless it was run.

When requirements are ambiguous in a way that changes the result, clarify them before implementation. For implementation details within an agreed scope, use the simplest approach consistent with existing interfaces and record material trade-offs with the work.

## Configuration and privacy

The repository is the shared toolkit. Machine-specific settings and project-specific integrations belong in ignored `.private/` configuration or another explicitly configured private root, not in shared defaults. The installer and settings renderer are authoritative for supported configuration fields; consult their current help and behavior before invoking them.

Do not store credentials, private project records, generated settings, or local execution logs in the public repository. Keep local changes outside release staging unless they are explicitly reviewed.

## Project knowledge-base scaffold

Projects created from `templates/kb-skeleton/` may use a Markdown knowledge base with the documented frontmatter contract. The generated skeleton's local `CLAUDE.md` is project-specific and supplements these shared instructions.
