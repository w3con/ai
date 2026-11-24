# Settings ownership and recovery

## Ownership and precedence

`bin/settings-render` recursively merges `settings.json.template` with the
optional ignored private overlay, then expands `__HOME__`. Objects merge;
arrays and scalars replace. The overlay defaults to `.private/settings.json`.
`settings_overlay` in the optional private configuration can select another
root-relative or absolute path; `AI_TOOLKIT_CONFIG` selects that configuration.

On a fresh installation, the merged source supplies initial preferences. On
redeployment, **all valid installed user preferences win**, including absent
fields: deleting a preference does not cause an overlay default to return.
Normal deployment does not write those preferences back into the overlay.
Controlled settings come from the merged source. Bootstrap validates the last
managed source before updating its entries; independently installed hook additions
are preserved as described below.

The exact allowlist and validators live in
[`lib/settings_policy.py`](../lib/settings_policy.py):

- `theme`, `model`, `effortLevel`, `alwaysThinkingEnabled`, `language`
- `preferredNotifChannel`, `agentPushNotifEnabled`, `inputNeededNotifEnabled`
- `editorMode`, `verbose`, `viewMode`, `showTurnDuration`, `showThinkingSummaries`
- `spinnerTipsEnabled`, `prefersReducedMotion`, `terminalProgressBarEnabled`,
  `syntaxHighlightingDisabled`, `tui`
- `voiceEnabled`, `voice`, `modelSettings`
- `skipDangerousModePermissionPrompt` (Boolean confirmation-dialog preference)

`voice` accepts only `enabled` and `autoSubmit` booleans, and `mode` equal to
`hold` or `tap`. `modelSettings` maps model names to objects containing only
`effortLevel`/`maxEffortLevel` (`low`, `medium`, `high`, `xhigh`) and
`autoCompactWindow` (a number at least 100000, or `auto`). Invalid shapes or
unknown nested fields fail closed, naming only the top-level key.

Other nonhook settings are controlled, including unknown keys, permissions,
environment variables, sandbox settings, plugins/marketplaces, MCP servers,
credential helpers and command fields. `disableAllHooks` and
`skipAutoPermissionPrompt` remain controlled. There are no `voice*` or `skip*`
wildcard exemptions.

`skipDangerousModePermissionPrompt` only suppresses the confirmation dialog when
entering bypass-permissions mode; it does not select that mode or change tool
permission rules. Adding, changing or removing this Boolean does not stale the
stamp or stop other projects. Normal redeployment preserves its installed value
or absence. Permission modes, bypass-mode restrictions and source-owned hooks
remain controlled independently.

## Hook entry ownership

Every hook entry in the merged template/private source is required. Within each
event, the policy flattens groups into ordered entries containing the complete
group metadata (all fields except `hooks`) and the complete hook object. These
entries must occur intact and in order in installed settings. Matcher, execution
options, command/type changes, removals, or reordering of required entries fail.
Empty groups retain their metadata as required entries too.

Additional entries may occur at new events, in separate groups, or between required
hooks within a group. Ordinary redeployment preserves installed hooks exactly,
including those additions. Structural validation requires event/group arrays and
typed hook objects, with execution payloads for known hook types. It does not
reimplement Claude's complete hook schema or certify the behavior of arbitrary
options or future hook types.

**Additional hooks are independently trusted executable integrations, outside the
harness's integrity assurance.** They can execute commands, consume event data,
affect tool handling or permission responses, and are not classified as harmless
presentation preferences. There are no application-name or command-marker
exemptions. `--adopt` remains preference-only and does not import these hooks into
the private source.

Source duplicates retain their required multiplicity. An additional entry
identical to a source-owned entry is rejected as ambiguous ownership: the installer
cannot reliably choose which copy to replace later. A source update that collides
with an identical independent entry also requires owner reconciliation.

## Last deployed source baseline and updates

Bootstrap atomically writes `~/.claude/.harness-managed.json` with mode `0600`:
an object with exactly `version: 1` and `controlled`, the last rendered source
JSON excluding valid preferences. It contains source-owned hooks, not independent
additions. This generated file may contain private commands/configuration; keep
it outside the public repository and protect backups as private data.

The baseline must be a regular file, have a supported structure, and hash to the
saved `managed-v1:` stamp. If it exists but is malformed, unsupported, symlinked,
or unbound, bootstrap fails before mutation, even when current source entries
appear to match. The gate checks the current source and stamp directly; it does
not use the baseline as an alternative authorization for stale sources.

An older baseline may contain the formerly controlled
`skipDangerousModePermissionPrompt` Boolean. Bootstrap validates the original
stored controlled JSON against its saved stamp before excluding this key from
previous ownership. Redeployment writes a current baseline/stamp and preserves
the installed preference. Invalid shapes, unbound records and other preference
keys in the baseline remain rejected.

Before a source update, all previous baseline-owned entries and nonhook controlled
values must still match installed settings. Missing old entries cannot be disguised
by removing them from the new source. For each changed hook event, bootstrap removes
only the old owned entries and inserts the new source groups as a block at the
first old owned group. If the event had no owned entries, the new block is appended.
Residual independent hooks keep their original group metadata; independent groups
and hooks retain their content and mutual order. Their order relative to newly
replaced managed hooks can change. Unchanged event arrays remain exact.

On an older installation without a baseline, current required source entries and
nonhook controls may match even with additional hooks; normal bootstrap then
preserves them and establishes the baseline. A prior versioned full-controlled
hash can also establish an old baseline only if installed controlled JSON still
hashes exactly to that saved stamp (no subsequent external additions). With extras
and a pending source change, a missing baseline cannot prove previous ownership;
restore a trusted baseline/stamp pair, or establish the baseline using the reviewed
last-deployed source before applying the update. An arbitrary legacy byte hash is
never previous-ownership evidence.

## Semantic stamps

Bootstrap writes `.harness-stamp` as `managed-v1:<sha256>`, hashing canonical
controlled **source** JSON with valid preferences excluded. The algorithm is
unchanged; independent hooks do not enter this hash. Object order and whitespace
are irrelevant; array order and the distinction between booleans and numbers
matter. Preference-default changes do not stale this stamp. Controlled or
unknown source changes do, until redeployment.

For compatibility, `bin/settings-render --digest` continues to print the SHA-256
of **exact rendered bytes**, including formatting and the final newline. This
byte digest is not the new managed stamp. A legacy 64-hex stamp is accepted by
the gate only when it equals the current renderer byte digest **and** installed
nonhook controls and required hook entries match the source. Bootstrap writes the versioned stamp on
the next deployment. An arbitrary legacy hash cannot prove an older controlled
baseline for a source update.

Malformed JSON, duplicate object keys, and non-finite numbers are rejected.
The gate also rejects missing, malformed, or symlinked installed settings and
stamps. Read-only tools and the existing bootstrap repair allowance remain
available during a denial.

## Adopt preferences into the private source

From the checkout, preview keys/categories without writing anything:

```sh
bash ./bootstrap.sh --adopt --dry-run
```

Then, as the owner in a terminal:

```sh
bash ./bootstrap.sh --adopt
```

Adoption prints preference keys, never values, and asks the owner to type
`adopt` through the controlling terminal (`/dev/tty`, checked with `isatty`).
Unattended invocation is refused; there is no automatic confirmation flag.
Adoption only updates allowlisted top-level preference fields, removes deleted
preferences from the overlay, and preserves unrelated private keys. Shared
template defaults still apply to a future fresh installation; adoption does
not add deletion markers to the renderer's merge contract.

An overlay inside the checkout must be Git-ignored. An explicitly configured
external regular file is supported. Adoption refuses an overlay symlink rather
than replacing it; deliberately configure its regular target to adopt there.
Normal deployment may read an existing valid overlay symlink. Settings, overlay,
baseline, and source inputs are checked again after confirmation and immediately
before replacement. A detected independent install/edit aborts deployment without
overwriting that edit; retry from a new preflight. These checks are not a shared
lock or atomic compare-and-swap with other installers. Adoption and baseline writes
participate in the installer's rollback transaction, including `after-settings`
failure recovery.

## Controlled drift recovery

Start with a read-only diagnosis from the checkout:

```sh
bash ./bootstrap.sh --dry-run
```

Diagnostics show added, removed, and changed nonhook keys, and affected hook event
and one-based source-entry index, without commands/arguments or values. Additional
entries are reported as preserved counts/events, not safety-validated. Adoption
never authorizes controlled drift. For an intended source change, restore any
unexpected drift from the last managed source first, deliberately review/edit the
private source (or shared template), then rerun diagnosis and deployment.

For owner recovery, back up installed settings, stamp and any baseline using unused
private backup names. Render the reviewed source to a separate file for comparison.
This example assumes the default overlay; substitute its configured path if different:

```sh
cp -p "$HOME/.claude/settings.json" "$HOME/.claude/settings.json.owner-backup"
python3 ./bin/settings-render --template ./settings.json.template \
  --overlay ./.private/settings.json --home "$HOME" \
  --output "$HOME/.claude/settings.json.source-review"
```

Compare locally and reconcile only the intended managed fields/entries, retaining
independent hooks and preferences. Do not replace installed settings wholesale with
the rendered review file when additions are present. Then run `bash ./bootstrap.sh
--dry-run` and normal bootstrap. The renderer itself does not preserve independent
hooks or installed preferences; it still renders only its supplied sources.

For baseline corruption or loss, restore a trusted baseline and its matching stamp
as a pair. If no trusted pair exists, the owner must first review/reconcile installed
required entries and nonhook controls against the current reviewed source before
moving an unusable baseline/stamp aside and letting bootstrap establish new state.
Do not fabricate a baseline to authorize missing/changed managed entries. Symlinked
installed settings, stamps or baselines require deliberate repair to regular files.

The hook is a consistency aid, **not a security boundary**: removing/disabling
the hook can prevent it from running. Its denials guide owner repair, and do not
make hook configuration tamper-proof.
