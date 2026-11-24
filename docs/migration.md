# Migrating an existing installation

`bin/migrate-public-release` replaces an existing checkout with an exact public commit while preserving the target machine's local recovery data. The script uses Python's standard library and Git. Run it from a terminal on the machine being migrated, not from the live toolkit session or by pulling into the old checkout.

The Python 3 interpreter used for migration and its preflight suite must have the declared `PyYAML==6.0.1` dependency available; the knowledge-index tests import it. If it is absent, install the declared dependency before migration with `python3 -m pip install 'PyYAML==6.0.1'`. The migrator resolves Gitleaks 8.24.3 from an explicitly configured binary or the invoking home’s versioned cache; otherwise it installs the checksum-pinned scanner into its restricted preflight home and passes that verified absolute path to the test suite. No global Gitleaks setup is required.

## Before running

1. Choose the immutable full commit SHA for the accepted release and its public repository URL.
2. Compute the SHA-256 digest of the exact `bin/migrate-public-release` file in that commit. The release coordinator supplies both values after acceptance; do not substitute a branch name, tag, or unverified digest.
3. Review local private mappings in `.private/migration-map.json`. The file is optional and ignored by Git; a legacy `memory/` directory is mapped automatically when found. Add every private tool, skill, or adapter that must stay active. An unmapped file remains in the recovery checkout without being reactivated.
4. Close other sessions that may change the checkout. The migrator disables the installed SessionStart synchronization hook, waits for active updater processes to finish, and uses a sibling pause marker honored by the new hook. If it cannot establish a safe pause, it stops before moving the checkout and restores the previous settings.

## Private mapping format

The map has a `mappings` array. Each entry names a source path in the old checkout (or an explicitly named external local path), a relative historical destination, and `file` or `directory` kind:

```json
{
  "mappings": [
    {"source": "memory", "destination": "memory", "kind": "directory"},
    {"source": "bin/local-tool", "destination": "bin/local-tool", "kind": "file"},
    {"source": "skills/local-workflow", "destination": "skills/local-workflow", "kind": "directory"}
  ]
}
```

The migrator copies each explicitly mapped source into its restricted sibling recovery area and creates a symlink at the requested historical path. It refuses to replace a path tracked by the pinned public release. The generated aliases are recorded in the new checkout's local Git exclude file. Private mappings under `hooks/` are also registered with the installer as local extensions. Unmapped and unknown old files stay in the preserved old checkout; they are not reactivated automatically.

An old root `.env` is copied to the new ignored `.env` on that same machine. Machine-specific settings are derived from the installed settings file, excluding old toolkit hooks, and stored in ignored `.private/settings.json`. An explicitly configured external `AI_TOOLKIT_CONFIG` file is updated with the migrated private roots and extensions; its exact original bytes are kept in recovery and restored on rollback. The settings renderer recursively merges JSON objects; arrays and scalar values replace their corresponding base values. Shell profiles and environment exports are not edited.

Old operational instructions from `CLAUDE.md` and an existing `.private/rules.md` are kept in the new ignored `.private/rules.md` after removing the old style imports and style-owned sections. The public `STYLE.md` remains the only style-guidance file. If the sanitized private rules still trigger the toolkit's style-rule scanner, migration stops before switching so the original rules remain available in recovery for manual review.

## Dry run

Dry-run validates local arguments and reports the intended target and number of mappings. It does not create state, locks, staging files, settings changes, or network requests:

```sh
python3 bin/migrate-public-release \
  --target "$HOME/path/to/checkout" \
  --repository https://github.com/OWNER/REPOSITORY.git \
  --revision FULL_COMMIT_SHA \
  --dry-run
```

The old checkout may be reached through an outer symlink. The script resolves and replaces the physical checkout directory while leaving that outer symlink itself in place.

## Release-pinned launch command

The old checkout does not need to fetch history first. After acceptance, the coordinator runs this generator against the release candidate and supplies its output as the one-command launcher for the target machine:

```sh
python3 bin/migrate-public-release \
  --target '$HOME/path/to/checkout' \
  --repository https://github.com/OWNER/REPOSITORY.git \
  --revision FULL_COMMIT_SHA \
  --migrator-sha256 FULL_64_CHARACTER_SHA256 \
  --print-launcher
```

This generator command is run from the accepted candidate, not from the old machine. The coordinator-supplied output downloads the migrator from the revision-pinned raw source URL, checks the exact SHA-256 in memory, and only then writes and runs it. The placeholders above are inputs to the generator, not a launch command. Do not use an unpinned download, branch, tag, or `curl | sh` pipeline.

The migrator clones the supplied repository into fresh sibling staging, checks out only the requested full commit, verifies that checkout, and rejects any commit reachable from the old private checkout's refs. It then runs `python3 -m unittest discover -s tests -v` in an isolated home and performs a preflight bootstrap there. It does not copy the old Git object database. When upgrading an already migrated clean public release, its accepted public ancestry may naturally appear in the new clone; private old-history commits remain only in the restricted recovery archive. Only after those checks succeed does it pause synchronization and switch the physical checkout.

## Recovery, retry, and rollback

State and staging are held beside the checkout in a hidden, mode-restricted migration directory. The old checkout, including its Git history, tracked modifications, untracked files, ignored files, and `.env`, remains there as recovery data. State is written between rename steps so rerunning the same pinned command resumes safely after interruption. Repeating it after success is a no-op. After a completed rollback, a later migration starts a new run and archives the prior run's recovery record rather than overwriting it.

The migration runs the pinned installer against the actual home only after preserving local settings and project memory entries. If deployment or its final checks fail, the script moves the failed new checkout into recovery and restores the old checkout, installed settings, and links. Project-scoped memory directories are temporarily moved aside during bootstrap and restored unchanged afterward.

The installed `.harness-managed.json` source baseline is preserved with exact bytes, existence, and mode in restricted recovery alongside settings and stamp. Fresh bootstrap and interrupted-bootstrap retries remove the prior/generated baseline together with settings, so the installer can establish a new source/stamp pair. Rollback restores the prior baseline or its recorded absence. Baseline symlinks and nonregular files are refused; `installed-managed.original` is private recovery data, never a public export. Older recovery states without `baseline_existed` do not authorize deleting or replacing an unknown baseline; a retry encountering one stops for owner recovery.

To explicitly roll back a completed migration, run:

```sh
python3 bin/migrate-public-release --target "$HOME/path/to/checkout" --rollback
```

Rollback restores the old checkout and the saved installation settings; the failed public checkout remains in the recovery directory. Neither success nor rollback deletes recovery data. Keep it until the migrated installation and required local consumers have been verified.

## Verification limits

Automated fixtures use local bare repositories and synthetic private data. They cover dry-run, outer symlinks, local modifications, ignored files, private mappings, custom settings, failure rollback, interruption resumption, repeat execution, synchronization pausing, and launcher integrity ordering. They do not prove that another computer or an external consumer has been migrated; report that separately after an owner-run execution.
