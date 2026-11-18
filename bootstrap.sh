#!/usr/bin/env bash
# Preserve the historical installer entry point while keeping install behavior in Python.
set -euo pipefail
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$REPO_DIR/bin/bootstrap.py" --root "$REPO_DIR" "$@"
