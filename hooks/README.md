# hooks/

`~/.claude/hooks` is a symbolic link into this directory, so every file here is live: it
governs every tool call of every agent on this machine the moment it is saved, whether or
not it has been committed or tested.

A hook that gates every agent is never edited in place. It is built elsewhere, tested
there against its own `<name>.test.py` suite, and only then installed onto its live path
by `bin/hook-install <candidate-file> <hook-name>`, which refuses unless the candidate
parses and that test suite passes against it, and installs by renaming the candidate onto
the live path so no reader ever sees a partially written file.

`bin/hook-install --check` reports every file in this directory that differs from the
last commit or that fails to parse, and exits non-zero when it finds one.

`bin/hook-install -h` prints the full usage for both.
