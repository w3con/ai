#!/usr/bin/env python3
"""Test harness for hooks/settings-write-guard.sh.

Lives in a file rather than in a Bash command on purpose: the guard inspects the
whole command string, so a test suite written inline as shell would contain the
very patterns it is testing and block itself.
"""
import json
import subprocess
import sys

HOOK = "/Users/laptop/Dev/ai/hooks/settings-write-guard.sh"
S = "settings.json"          # assembled at runtime, never as one literal below
LOCAL = "settings.local.json"
HOME = "~/.claude/"
REPO = "/Users/laptop/Dev/ai/"


def verdict(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    r = subprocess.run(["bash", HOOK], input=payload, capture_output=True, text=True, env=env)
    try:
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "PARSE_FAIL(" + r.stdout[:60] + ")"


CASES = [
    # (expected, label, command)
    ("deny", "heredoc — приём, которым обошли запрет", f"cat > {REPO}{S} << 'EOF'"),
    ("deny", "перенаправление", f"echo '{{}}' > {HOME}{S}"),
    ("deny", "дозапись", f"echo x >> {HOME}{S}"),
    ("deny", "tee", f"echo '{{}}' | tee {HOME}{S}"),
    ("deny", "mv поверх", f"mv /tmp/new.json {HOME}{S}"),
    ("deny", "cp поверх", f"cp /tmp/new.json {HOME}{S}"),
    ("deny", "rm", f"rm {HOME}{S}"),
    ("deny", "sed -i", f"sed -i '' 's/opus/fable/' {S}"),
    ("deny", "settings.local.json тоже", f"echo x > {HOME}{LOCAL}"),
    ("deny", "python write_text В настройки",
     f"python3 -c \"import pathlib;pathlib.Path('{REPO}{S}').write_text('{{}}')\""),
    ("deny", "python json.dump в настройки",
     f"python3 -c \"import json;json.dump({{}}, open('{S}','w'))\""),

    # The false positive that forced the fix: a script editing the PLAN file, whose
    # text merely mentions the settings file inside a search string.
    ("allow", "python правит план; слово settings лишь в строке поиска",
     "python3 - <<'PY'\nimport pathlib\n"
     "p=pathlib.Path('plans/websearch-default.md'); t=p.read_text()\n"
     f"t=t.replace('см. Q1 ({S})','закрыт')\n"
     "p.write_text(t)\nPY"),
    ("allow", "python пишет в другой файл, настройки упомянуты далеко",
     f"python3 -c \"print('{S} mentioned here, far away from the write call, "
     f"padded out so the window does not reach it: {'x' * 140}'); "
     "import pathlib; pathlib.Path('/tmp/x.md').write_text('hi')\""),

    # Third false positive of 2026-07-10: the `sed -i` rule reached across newlines
    # and stitched `sed 's/^/  /'`, the `-i` of `git grep -i`, and the words
    # "settings.json" into a command nobody wrote.
    ("allow", "многострочный read-only скрипт: sed, git grep -i, слово settings",
     "git status --short | sed 's/^/  /'\n"
     f"git grep -i -e brave_api_key -- {S} bin/websearch 2>/dev/null || echo нет\n"
     "git check-ignore -v .env | sed 's/^/  /'"),
    ("allow", "git add перечисляет настройки среди путей (это не запись)",
     f"git add -n bin/websearch {S} CLAUDE.md"),
    ("deny", "настоящий sed -i всё ещё ловится", f"sed -i.bak 's/a/b/' {HOME}{S}"),

    # A backup is not a live settings file: deleting one must be possible, while
    # deleting the real thing stays blocked.
    ("allow", "rm бэкапа настроек", f"rm {HOME}{S}.bak-2026-07-10"),
    ("allow", "rm второго бэкапа", f"rm {HOME}{S}.pre-symlink-2026-07-10"),
    ("deny", "rm настоящего файла настроек всё ещё запрещён", f"rm {HOME}{S}"),

    ("allow", "cat", f"cat {HOME}{S}"),
    ("allow", "grep", f"grep model {HOME}{S}"),
    ("allow", "json.tool в /dev/null", f"python3 -m json.tool {S} > /dev/null"),
    ("allow", "бэкап в сторону", f"cp {HOME}{S} {HOME}{S}.bak-2026-07-10"),
    ("allow", "mv в сторону (нужно bootstrap.sh)", f"mv {HOME}{S} {HOME}{S}.pre-symlink"),
    ("allow", "посторонняя команда", "ls -la ~/.claude"),
    ("allow", "не упоминает настройки вовсе", "echo hi > /tmp/notes.txt"),
]

fails = 0
for expected, label, cmd in CASES:
    got = verdict(cmd)
    ok = got == expected
    fails += 0 if ok else 1
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (ожидал {expected}, получил {got})"))

# fail-closed on empty stdin
r = subprocess.run(["bash", HOOK], input="", capture_output=True, text=True)
ok = '"deny"' in r.stdout
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  пустой ввод -> deny (fail-closed)")

# non-Bash tool is not gated
got = json.loads(subprocess.run(["bash", HOOK], input=json.dumps({"tool_name": "Read", "tool_input": {}}),
                                capture_output=True, text=True).stdout)["hookSpecificOutput"]["permissionDecision"]
ok = got == "allow"
fails += 0 if ok else 1
print(f"  {'PASS' if ok else 'FAIL'}  не-Bash не гейтится")

print(f"\n  итог: {len(CASES) + 2 - fails}/{len(CASES) + 2} пройдено")
sys.exit(1 if fails else 0)
