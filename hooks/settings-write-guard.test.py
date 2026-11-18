#!/usr/bin/env python3
"""Test harness for hooks/settings-write-guard.sh.

Lives in a file rather than in a Bash command on purpose: the guard inspects the
whole command string, so a test suite written inline as shell would contain the
very patterns it is testing and block itself.
"""
import json
import os
import subprocess
import sys

_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOOKS = os.path.join(_AI_ROOT, "hooks")

HOOK = os.path.join(_HOOKS, "settings-write-guard.sh")
S = "settings.json"          # assembled at runtime, never as one literal below
LOCAL = "settings.local.json"
HOME = "~/.claude/"
REPO = _AI_ROOT + os.sep


def verdict(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    r = subprocess.run(["bash", HOOK], input=payload, capture_output=True, text=True, env=env)
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:60] + ")"


CASES = [
    # (expected, label, command)
    ("deny", "heredoc write", f"cat > {REPO}{S} << 'EOF'"),
    ("deny", "overwrite redirect", f"echo '{{}}' > {HOME}{S}"),
    ("deny", "append redirect", f"echo x >> {HOME}{S}"),
    ("deny", "tee", f"echo '{{}}' | tee {HOME}{S}"),
    ("deny", "move over settings", f"mv /tmp/new.json {HOME}{S}"),
    ("deny", "copy over settings", f"cp /tmp/new.json {HOME}{S}"),
    ("deny", "rm", f"rm {HOME}{S}"),
    ("deny", "sed -i", f"sed -i '' 's/opus/fable/' {S}"),
    ("deny", "local settings file is protected", f"echo x > {HOME}{LOCAL}"),
    ("deny", "Python write_text to settings",
     f"python3 -c \"import pathlib;pathlib.Path('{REPO}{S}').write_text('{{}}')\""),
    ("deny", "Python json.dump to settings",
     f"python3 -c \"import json;json.dump({{}}, open('{S}','w'))\""),

    # A script edits a plan whose text mentions settings only in a search string.
    ("allow", "Python edits a plan; settings is only in a search string",
     "python3 - <<'PY'\nimport pathlib\n"
      "p=pathlib.Path('plans/example-plan.md'); t=p.read_text()\n"
      f"t=t.replace('see setting {S}','updated')\n"
     "p.write_text(t)\nPY"),
    ("allow", "Python writes another file; settings mention is outside the write call",
     f"python3 -c \"print('{S} mentioned here, far away from the write call, "
     f"padded out so the window does not reach it: {'x' * 140}'); "
     "import pathlib; pathlib.Path('/tmp/x.md').write_text('hi')\""),

    # Read-only commands across lines must not combine into a false write.
    ("allow", "multiline read-only commands do not combine into a write",
     "git status --short | sed 's/^/  /'\n"
      f"git grep -i -e api_token -- {S} bin/websearch 2>/dev/null || echo none\n"
     "git check-ignore -v .env | sed 's/^/  /'"),
    ("allow", "git add path listing is not a settings write",
     f"git add -n bin/websearch {S} CLAUDE.md"),
    ("deny", "in-place sed remains blocked", f"sed -i.bak 's/a/b/' {HOME}{S}"),

    # A backup is not a live settings file: deleting one must be possible, while
    # deleting the real thing stays blocked.
    ("allow", "remove a settings backup", f"rm {HOME}{S}.bak-example"),
    ("allow", "remove an alternate settings backup", f"rm {HOME}{S}.pre-overlay-example"),
    ("deny", "removing the live settings file is blocked", f"rm {HOME}{S}"),

    ("allow", "cat", f"cat {HOME}{S}"),
    ("allow", "grep", f"grep model {HOME}{S}"),
    ("allow", "json.tool writes only to the null device", f"python3 -m json.tool {S} > /dev/null"),
    ("allow", "copy a backup", f"cp {HOME}{S} {HOME}{S}.bak-example"),
    ("allow", "move a backup aside", f"mv {HOME}{S} {HOME}{S}.pre-overlay-example"),
    ("allow", "unrelated directory listing", "ls -la ~/.claude"),
    ("allow", "unrelated write", "echo hi > /tmp/notes.txt"),
]

fails = 0
for expected, label, cmd in CASES:
    got = verdict(cmd)
    ok = got == expected
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (expected {expected}, got {got})"))

# fail-closed on empty stdin
r = subprocess.run(["bash", HOOK], input="", capture_output=True, text=True)
ok = '"deny"' in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  empty input fails closed")

# non-Bash tool is not gated
got = json.loads(subprocess.run(["bash", HOOK], input=json.dumps({"tool_name": "Read", "tool_input": {}}),
                                capture_output=True, text=True).stdout)["hookSpecificOutput"]["permissionDecision"]
ok = got == "allow"
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  non-Bash tools are not gated")

print(f"\n  result: {len(CASES) + 2 - fails}/{len(CASES) + 2} passed")
sys.exit(1 if fails else 0)
