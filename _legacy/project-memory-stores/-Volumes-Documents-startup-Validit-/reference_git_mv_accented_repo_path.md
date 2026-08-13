---
name: reference_git_mv_accented_repo_path
description: "git mv with absolute paths fails in this repo because the path contains \"Validité\" (NFD/NFC) — use relative paths"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 66cbb497-4a74-41cf-b47d-dbcdafd498d9
---

The repository root path contains an accented character — `/Volumes/Documents/startup/Validité`. macOS stores that filename in Unicode NFD (decomposed `e` + combining acute), while Python/git often produce NFC. Because of the mismatch, passing **absolute** paths to `git mv` (or other git path operations) fails with `fatal: '...' is outside repository`, since git can't match the normalized worktree prefix.

**Fix:** run git from the repo root (`cwd = git rev-parse --show-toplevel`) and pass **relative** paths to `git mv` / git commands. Relative paths sidestep the absolute-prefix comparison entirely. This bit a bulk 71-file folder-note migration (commit 18250a4, 2026-06-15) where all moves failed on the first attempt with absolute paths and succeeded immediately with relative ones.

Applies to any future bulk file operation in this repo. Many KB filenames also contain Cyrillic and `&`, so drive such operations from Python with an argument list rather than a shell string.
