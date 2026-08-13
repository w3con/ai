---
name: machine-ssd-python-path
description: On the /Volumes/SSD machine the project scripts need anaconda's python3; putting Homebrew ahead of it in PATH breaks them with a misleading "PyYAML required"  # path-check: allow — the volume name identifies which machine this note is about
metadata:
  type: reference
scope: validite-app
machine: the /Volumes/SSD machine only  # path-check: allow — a machine name, not a path anything opens
---

This note is deliberately about one machine, so it is the one place in this store where an absolute home directory is the fact itself rather than a mistake; the marker at the end of the next paragraph is what tells `bin/path-check` so.

On this machine the checkout at `/Volumes/SSD/Dev/validite/validite-app` runs its `bin/` scripts under `/Users/tknff/anaconda3/bin/python3`, which is the interpreter that actually has PyYAML installed. Homebrew's own `/opt/homebrew/bin/python3` does not have it. Homebrew is already on the PATH, so nothing needs adding — but prepending `/opt/homebrew/bin` to PATH reorders the two interpreters and every script that reads YAML then dies with `PyYAML required: pip install pyyaml` or `ModuleNotFoundError: No module named 'yaml'`. <!-- path-check: allow — a machine-specific interpreter path is this note's whole subject -->

**Why this matters:** on 2026-08-13 that reordering made `bin/checks all` report all thirty refusal-test rules as failing, immediately after a real change to `bin/refusal-tests` — which read exactly like a regression caused by the change and was not one. Worse, one failing rule (`card-launch.live-worktree`) runs `bin/card-launch` for real, relying on its worktree refusal firing first; when the refusal did not fire, the script spawned an actual `card-critic` agent, so a PATH mistake spent tokens.

**How to apply:** never prepend `/opt/homebrew/bin` to PATH when running this project's scripts — run them in the shell's own environment. If a project script suddenly cannot find `yaml`, suspect the interpreter before suspecting the change you just made: check `command -v python3` and `python3 -c "import yaml"` before reading the failure as a regression. Related: [[feedback_reusable_tooling]].
