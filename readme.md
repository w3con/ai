# AI Engineering Toolkit

A portable collection of shared agent instructions, skills, hooks, command-line utilities, settings support, and project templates. The public core is intended to install without access to private projects; optional machine- or project-specific configuration is supplied separately.

## Architecture

- `CLAUDE.md`, `STYLE.md`, and `agents/` provide shared instructions and agent definitions.
- `skills/` contains self-contained workflows.
- `bin/` contains command-line tools; `hooks/` contains client integrations.
- `bootstrap.sh`, settings templates, and the shared settings renderer install common files and configure optional local overlays.
- `templates/` contains reusable project structures, including `kb-skeleton/`.
- `.private/` is an optional ignored local layer for private rules and settings overrides. A separate private root may be used when configured by the installer. Do not commit private data.

The shared toolkit is maintained in this repository. Private overlays provide data and integration configuration, not duplicate copies of shared implementations.

## Requirements

Python 3.10 or newer, Bash, and Git are required for the relevant installation and command workflows on a Unix-like system. Individual tools may have additional dependencies; see their own documentation. The project knowledge-base scaffold may be used independently of the rest of the toolkit.

## Installation

Clone this repository to any local directory and run `./bootstrap.sh` from the checkout. Review the script's current help and behavior before using options. Installation targets are user-level configuration paths; use an isolated home directory to evaluate installation changes before applying them to an existing environment.

The installer works without private repositories or a private knowledge base. Optional private integrations are not required for core installation. For a clean installation, review generated settings and verify the reported exit status. The installer is the source of truth for exact supported targets and options.

## Optional settings overlay

An ignored `.private/settings.json` may supply local settings. The shared renderer recursively merges JSON objects; arrays and scalar values in the overlay replace the corresponding base values. Omit the overlay when it is not needed. Do not commit rendered machine settings, credentials, or private configuration. An external private root is supported only when explicitly configured by the installed implementation.

Claude's reviewed UI, model, and voice preferences are user-owned: valid installed preferences, including deletions, survive normal redeployment and override source defaults. Other nonhook settings and source-owned hook entries remain controlled by the shared template plus private overlay. Independently installed additional hooks are preserved; they are executable integrations trusted separately, not safety-validated by the harness. The gate checks required entries and a versioned source stamp. Bootstrap saves a private, stamp-bound `~/.claude/.harness-managed.json` baseline to update only its previous source-owned entries. The renderer's `--digest` still hashes exact output bytes. Use `bash ./bootstrap.sh --adopt --dry-run` to preview preference adoption, then `bash ./bootstrap.sh --adopt` for owner terminal confirmation. See [settings ownership and recovery](docs/settings.md) for ownership, updates, and repair.

## Compatibility

Existing consumers may depend on established file paths, arguments, output formats, exit statuses, hook event payloads, or generated input schemas. Those contracts are preserved or adapted where verified. Older task-card and knowledge-base inputs remain supported by the core parsers where implemented; documentation templates do not require publishing private historical examples.

The root overview is kept at the legacy `readme.md` path and remains the only tracked root README entry.

## Migration

Use the coordinator-supplied release-pinned command described in [the migration guide](docs/migration.md) to migrate an existing installation. It verifies the exact source revision and migrator digest before downloading or running the migration script. Never use an unpinned download command.

## Examples

The repository contains command-line utilities and a knowledge-base project scaffold. See `templates/kb-skeleton/README.md` for scaffold usage. Additional reproducible engineering examples are documented only after their scripts and checks are integrated; no example command is claimed as verified by this document.

## Checks

Install the declared Python dependency, install the checksum-pinned Gitleaks scanner, and run the tests and export-boundary checks:

```sh
python3 -m pip install -r bin/requirements.txt
python3 bin/public-check install-gitleaks
python3 -m unittest discover -s tests -v
python3 bin/public-check check --root . --tree
```

Use `python3 bin/public-check check --root . --staged` to validate the staged export. The checker scans tracked and non-ignored untracked files in tree mode; it does not read ignored private data. Gitleaks 8.24.3 is downloaded from its versioned release and checked against the pinned platform SHA-256 before installation. The continuous-integration workflow runs the test suite and tree check without private credentials. Migration on another computer is verified separately by the owner running the supplied release-pinned command.

## License and provenance

Owner-authored core components are released under the MIT License; see `LICENSE`. PyYAML 6.0.1 is a third-party dependency with its MIT license included at `lib/third_party/PyYAML-LICENSE.txt`; see `THIRD-PARTY-NOTICES.md`. The bounded provenance review did not identify other copied source or bundled assets in the reviewed core, but it does not establish authorship for every historical file. Private local tools with unresolved provenance are not part of this release.
