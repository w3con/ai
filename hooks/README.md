# Hooks

The installer exposes this directory at `~/.claude/hooks`. A hook edit can affect
active sessions as soon as it is installed, so prepare and test candidates away from
the installed path.

For an existing hook, run:

```text
bin/hook-install <candidate-file> <hook-name>
```

The installer checks syntax, requires the adjacent `<hook-name>.test.py` suite to pass
against the candidate, and replaces the installed file by atomic rename. It refuses a
new hook name for which no installed hook exists yet; new hook registration belongs in
the settings template and installer.

Run `bin/hook-install --check` to report hook files that differ from the committed
version or fail syntax validation. It makes no changes.
