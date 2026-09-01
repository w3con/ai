#!/usr/bin/env bash
# work-gate.sh — PreToolUse hook: the enforcement backbone of the new work-management
# system (HRN-2, ai/harness/system/project.md, "Хук на вызов инструмента", in the
# validite-app repository). A rule that used to live only in prose becomes a rule nobody can
# break by accident, because the tool call itself is refused.
#
# This file currently builds phases HRN-2.A (the fitness guard and caller identity),
# HRN-2.B (one-file-one-author and the log-write ceiling), HRN-2.D/F (the phase boundary,
# judged against the run's own named phase), HRN-2.C (the context/spend/pace ceilings, read
# from the run's own transcript, plus the file-edit brake), and HRN-63.B, which replaced the
# phase boundary's own log.md-header counting (HRN-2.E's, in turn, own rewrite of that
# counting to a step's permanent name) with running the phase's own gate-<фаза>.sh, found in
# the card's own linked working copy, on every bin/work-note call, and reading the boundary
# off the <фаза>.closed marker that gate leaves rather than off log.md at all.
#
# WHAT THIS FILE DOES, IN THE ORDER IT DOES IT
#
#  1. Bypass: CLAUDE_GATE_BYPASS=1 disables every rule below, the same escape hatch the
#     other hooks in this directory share (memory-store-guard.sh, plan-gate.sh,
#     card-touch-gate.sh).
#
#  2. NO SANCTION, NO EXECUTOR SPAWN (HRN-48.B): judged only against a Task/Agent call that
#     carries no agent_id yet — this hook sees the SPAWN call itself, before the subagent it
#     would create exists — whose own subagent_type is "executor". `bin/work-handover` and
#     `bin/work-resume` are the only two writers of a sanction file, and each writes one only
#     once every refusal it checks has already passed and the executor's own brief has been
#     printed — one file per card this conversation was ever handed over to,
#     sanctions/<key>/<card id>.json, sibling of briefs/<session_id>.json, `<key>` the
#     sanitized session_id this hook's own payload already carries (proved identical to
#     CLAUDE_CODE_SESSION_ID on a live call, HRN-48.B.1). Reshaped per-card by HRN-52.A.1: a
#     second handover in the same conversation, for a different card, used to overwrite the
#     first card's own sanction — the exact hole that made two short cards handed over back
#     to back never both stay sanctioned — and now leaves both on disk instead. This rule
#     allows when at least one of this conversation's own sanction files names a card the
#     spawn's own prompt or description actually contains AND that card's own folder carries
#     none of `done.md`, `cancelled.md`, `rejected.md` or `question.md` — a sanction written
#     before a card was returned to the orchestrator for one of those four reasons must never
#     let a later spawn resurrect it past `bin/work-handover`'s own fourth refusal. Refused
#     with the same text either way — no sanction names the spawned card at all, or the one
#     that does belongs to a card in one of those four states. The refusal names exactly one
#     exit: bin/work-handover <ID> for a fresh phase, bin/work-resume <ID> for an interrupted
#     one. A reading role's own spawn (critic, mapper, tracer, acceptor) is never judged by
#     this rule — only subagent_type "executor" is.
#
#  2b. ONE CONVERSATION RUNS ONE TASK (HRN-48.C, carried over from the retired
#     hooks/plan-gate.sh's own HRN-203 — read as the model, never rebuilt from memory): runs
#     only once rule 2 above has already decided to allow this exact spawn, on the very same
#     call, and it can only turn that decided allow into a deny — it never grants an allow of
#     its own. Short work is exempt from this rule outright (HRN-52.A.2; threshold raised from
#     1 to 2 by HRN-53.A.1, owner's own word 2026-08-30): the sanction rule 2 matched this
#     spawn against carries its own card's estimate (written by bin/work-handover /
#     bin/work-resume, read straight from `description.md`'s own "Оценка" field), and when
#     that estimate reads the integer 1 or 2 — bin/work-short's own signature at 1, and, since
#     HRN-53, the most common size of a small fix at 2 — this rule neither denies the spawn
#     nor records that card as occupying the conversation, so any number of these cards pass
#     at once, before, after or alongside whatever else the conversation is already doing. A
#     card estimated 2 goes through the whole conveyor and may carry more than one step or
#     more than one phase, so "nothing to lose on a rollback" is no longer a structural
#     guarantee of its shape the way it is for a one-step estimate-1 card — for a 2 it is only
#     the plan author's own judgement (HRN-53's own "Причина"). A sanction carrying no
#     estimate field, or one that is not readable as the integer 1 or 2, is judged as an
#     ordinary card exactly as before this exemption existed — giving a missing or unreadable
#     estimate the same pass as a proven 1 or 2 would lift a denial this rule used to make,
#     not merely withhold a denial it was never going to make on its own account. For every
#     card this exemption does not cover: on the first ordinary executor spawn a conversation
#     sanctions,
#     the card named in that spawn's own sanction is written into a small per-conversation
#     state file, keyed on a sanitized transcript_path (the same value
#     hooks/card-touch-gate.sh's own COORD rule already keyed its per-session ceiling on). A
#     later spawn in the SAME conversation whose own sanction names a DIFFERENT ordinary card
#     is refused, naming both cards and both ways out — finish the current task and close the
#     conversation with /clear, or open a separate session with /parallel when both are
#     genuinely needed at once — UNLESS the remembered card's own folder has since gained a
#     done.md or a cancelled.md (HRN-51): a card closed this way no longer occupies the
#     conversation, the new spawn passes, and its own card takes the closed one's place in the
#     state file. A later spawn whose sanction names the SAME card passes every time, without
#     limit — an ordinary relay after a pace stop, not a second task. This rule keeps its own
#     try/except and never denies on an error of its own — a transcript_path it cannot read, a
#     state file it cannot write or parse, or a remembered card's own folder it cannot find
#     while checking for done.md/cancelled.md, all fall through to an allow, since rule 2 has
#     already decided this exact spawn is fine and a bug in this rule must never widen into a
#     refusal that rule did not itself make.
#
#  3. CALLER IDENTITY: a call carrying no agent_id in its payload is the session's own — the
#     orchestrator — and passes past rules 2 and 2b above. Rules 4 onward judge only a
#     subagent's own call — none of them can read anything a session-only call carries.
#
#  3a. COORDINATOR COUNTS (HRN-48.D): the session's own call, judged by rule 3 above, is never
#     refused by anything from here on, but it is watched on two separate rubrics, both
#     ceilings carried over unchanged from the retired hooks/card-touch-gate.sh's own COORD
#     and SEARCH-AGENT rules (HRN-123). Every one of the session's own calls, keyed on a
#     sanitized transcript_path, bumps a running total against a ceiling of 761; a Task/Agent
#     spawn whose own subagent_type is a reading role (Explore, Plan, trace-audit — the same
#     three hooks/plan-gate.sh once allowlisted) bumps a second, separate running total, same
#     key, against a ceiling of 28. Crossing either ceiling changes nothing about the call's
#     own outcome — it still allows — and only adds the count to that allow's own
#     permissionDecisionReason, so a long coordinator session can see its own pace without a
#     refusal ever breaking the single-conversation pipeline rule 65 of this project's own
#     CLAUDE.md requires.
#
#  4. NO BRIEF, NO LAUNCH: a subagent is known to this hook only because something told it —
#     a small caller-brief file naming its role and the card it works, {"role": ...,
#     "card": ...}. bin/work-agent-brief is the script that writes one, called by a
#     subagent as its own first action, naming its own role and card
#     (`bin/work-agent-brief --role executor --card HRN-6`). Two things write a brief, for
#     two different reasons:
#       - THIS HOOK, the moment it sees that very Bash call go by, parses --role/--card
#         straight out of the command string and writes briefs/agent-<agent_id>.json, keyed
#         on the agent_id carried by that SAME call's own payload — the only identifier
#         available at that moment that is guaranteed fresh and stable for this subagent's
#         whole life, established already for exactly this reason by HRN-46 and reused
#         unchanged by card-touch-gate.sh in this same directory ("agent_id values are
#         treated as unique on their own, with no session_id folded in"). agent_id cannot be
#         known before the subagent exists, so no launcher script run by the orchestrator
#         could ever write this file itself — only this hook, watching the subagent's own
#         first call, can.
#       - bin/work-agent-brief ITSELF, once the hook has allowed that same call through and
#         the real script runs a moment later, separately writes
#         briefs/session-<CLAUDE_CODE_SESSION_ID>.json — a second, independently useful path
#         (the script is a real, standalone command, testable on its own, and the one that
#         honours this card's own plan wording of a brief "named by the agent's session
#         identifier"), kept as a fallback this hook reads only when no agent_id-keyed brief
#         exists yet.
#     A subagent with neither file has every call refused, with one exemption: the Bash call
#     that runs bin/work-agent-brief itself, since that is how the very first brief gets
#     written at all.
#
#  4a. READING ROLE IS READ-ONLY: a subagent whose brief names one of the four reading roles
#     — critic, mapper, tracer, acceptor — is refused every Bash call. The one call that
#     would be legitimate, bin/work-agent-brief itself, never reaches this rule: rule 4 above
#     allows and exits on it long before. When one of bin/work-critic, bin/work-map,
#     bin/work-trace or bin/work-accept raises its own reading agent, it hands
#     `--allowedTools "Bash(bin/work-agent-brief *)" Read Grep Glob` and the reading really is
#     read-only. When rules.md's own `agents-always-foreground` sends that same raise back to
#     the live session instead, the session raises the agent definition agents/work-reader.md,
#     whose `tools:` line cannot express that scope: a parenthesised specifier there grants the
#     whole Bash tool rather than the one command it names, and dropping Bash altogether would
#     strand the agent before its own mandatory first call. So the scope is enforced here,
#     where it holds for both paths, and an acceptor that runs the very checks it is told it
#     never runs is refused instead of believed.
#
#  5. PHASE BOUNDARY (HRN-2.D, rewritten by HRN-2.F): applies only to a subagent whose brief
#     names role "executor" — every other role is never judged by this rule at all. HRN-2.D's
#     own reading — "the current phase is the first phase in plan.md's own order that still
#     has an open step" — silently required every phase of the whole plan to close before the
#     boundary ever fired, so an executor that finished its own phase walked straight into
#     the next one (found live, on this very card, by HRN-2.B's own executor). HRN-2.F
#     replaces that scan: the boundary is judged only against the ONE phase this run's own
#     caller-brief names (bin/work-agent-brief's own --phase), never against the plan as a
#     whole.
#       - No phase named in the brief at all: refused, every call except a Write/Edit of the
#         card's own log.md — the same shape as "no caller-brief file", because an unnamed
#         phase would leave this rule nothing to judge and the run would never be stopped
#         (owner's own correction, 2026-08-28: «неназванная фаза не освобождает от границы,
#         а запрещает работу»).
#       - Phase named: read plan.md's own "## Шаги" section, split into phases by its
#         "### <ID>.<letter> — …" subheadings (a plan not split into phases at all is one
#         implicit phase named by the bare card id); each phase's steps are its own "- "
#         bullet lines, in order, numbered 1..N. Read log.md's own headings of the shape
#         "## <ID>.<letter>, шаг <N>" or "…, шаг <N>–<M>" (en dash), the convention HRN-2.A's
#         own executor established — the numbers named there are that phase's closed steps.
#         A phase that does not appear in plan.md at all is not a state this rule can judge,
#         so the call is skipped rather than denied. Once every one of the named phase's own
#         steps is closed, the boundary is reached for THAT phase — every further call is
#         refused except a Write/Edit of the card's own log.md, with the words «допиши
#         передачу и остановись», regardless of what any other phase in the plan looks like
#         (closed, open, or never started at all). While the named phase still has an open
#         step, every call passes with no inspection at all.
#     A card whose plan.md cannot be read is not yet in a state this rule can judge, so it is
#     skipped rather than denied — the same fail-open choice bin/work-agent-brief's own
#     malformed-command case already makes in rule 4 above.
#
#  6. FILE AUTHORSHIP (HRN-2.B): "one file, one author" (ai/harness/system/project.md,
#     "Правка чужого файла") — applies only to a Write/Edit whose target actually sits inside
#     the run's own card folder. An executor may not write description.md, attention.md or
#     done.md, each belonging to a different role (the owner via the orchestrator, the
#     critic, the acceptor); an executor targeting plan.md is refused the same way, but the
#     refusal names question.md instead ("Проблема в плане") — the plan itself is never the
#     executor's own to edit, so it records the proposed change there and keeps working. An
#     acceptor may not write log.md — that file is the executor's own.
#
#  6a. WORKING COPY BOUNDARY (HRN-70): applies only to role "executor", judged the same way
#     rule 6 above is — only once card_dir is known, and only for a Write/Edit whose target
#     does NOT sit inside the run's own card folder (every file that folder holds is written
#     by whichever command owns it, in the shared checkout, by rules.md's own rule 51 — this
#     rule is never about those, question.md included). The target's own realpath is compared
#     against two other paths: the shared checkout's own root (os.path.dirname of the work
#     root rule 5 already resolves) and this card's own linked working copy, found the same
#     way bin/work-session cuts one and bin/work-commit already finds one by name — the `git
#     worktree list --porcelain` entry whose own branch is refs/heads/work/<card id,
#     lowercased> (rules.md rule 53). A target inside the shared checkout but NOT inside that
#     working copy is refused, naming both the wrong path it actually named and the right
#     one — the same path, rewritten under the working copy's own root — so the fix is
#     repeating the same edit at the right address, never guessing what that address is. A
#     target already inside the card's own working copy, or outside the shared checkout
#     entirely, is never judged by this rule at all; nor is a call whose own working copy
#     this rule cannot resolve — the same fail-open posture every other rule in this file
#     already takes on an unresolvable state of its own.
#
#  6b. GIT COMMAND (HRN-70): applies only to role "executor", judged against every Bash call.
#     A `git …` invocation is read-only by default — status, diff, log, show, rev-parse,
#     ls-files, worktree list — and every other subcommand is refused, naming the reference
#     command that does the same thing correctly instead of a bare git call: bin/work-commit
#     for saving or discarding work (stash, add, commit, checkout, switch, restore, reset,
#     branch, clean — each one of these can lose uncommitted work exactly the way a bare
#     `git stash` already has, HRN-63 2026-09-01), acceptance for landing this card's own
#     branch (merge, rebase, push), and the same generic pointer for a subcommand this rule
#     does not recognise at all. `npm install` is refused the same way, in favour of `npm
#     ci`, as its own separate check inside this rule. Only a git call that actually targets
#     one of THIS project's own repositories is judged: a bare `git …` (no `-C`) always
#     targets cwd, which every Bash call's own cwd is reset to — the shared checkout — so it
#     is always in scope; a `git -C <path> …` is judged only when <path> resolves inside one
#     of the paths `git worktree list --porcelain` reports for that same repository. A git
#     call targeting a repository outside this project entirely — the separate ~/Dev/ai
#     configuration repository this rule itself was built and committed in, by this same
#     kind of executor, being the load-bearing example — is never judged by this rule at
#     all. A command carrying a heredoc (`<<marker`) is judged only on the part before the
#     heredoc operator, never inside the heredoc's own body — that body is stdin content,
#     most often a check's own verbatim output pasted into a bin/work-note call, and a line
#     inside it that happens to read "git status" or "$ git commit -m x" as PROSE is never
#     mistaken for a real invocation.
#
#  7. LOG-WRITE CEILING (HRN-2.B, extended by HRN-21.B, narrowed 2026-09-01): applies only
#     to role "executor", once card_dir is known. Twenty calls in a row without a Write/Edit
#     of this card's own log.md refuse the next call — "Двадцать вызовов без записи в
#     log.md". Two kinds of call still get through, and only one of them resets the count.
#     A Write/Edit of log.md itself, or a single, unchained Bash call running bin/work-note
#     WITH A STEP NAME, resets the count to zero: that call records a closed step, so the
#     run has actually moved. A bin/work-note --handoff call passes the ceiling too — a run
#     that has hit it must always be able to record its own state — but resets nothing,
#     because a handoff records that the run is stopping, not that work was done.
#     A Bash call running bin/work-commit passes on the same terms, and for the same reason
#     (HRN-76, 2026-09-01): bin/work-note --handoff refuses outright on a working copy
#     carrying uncommitted changes, naming bin/work-commit as the one command to run first,
#     so with that command refused by this ceiling a run that hit the ceiling with dirty
#     code could neither commit nor record a handoff and lost its whole phase — measured
#     that day on HRN-76, whose first executor was cut off exactly this way. It resets
#     nothing either: landing code is not closing a step.
#     Before this narrowing --handoff reset the count like any other bin/work-note call, so
#     an executor that hit the ceiling bought itself twenty more calls with a call that
#     built nothing. Measured 2026-09-01 on HRN-63.C: six consecutive --handoff calls did
#     exactly that, the first of them saying "investigation phase, no code changed yet" in
#     its own text. The reset is decided before the command runs, so a bin/work-note that
#     goes on to refuse itself still resets — narrowing the reset to the step-naming form
#     is what keeps that harmless, since closing a step is the thing the run is for.
#
#  8. CONTEXT SIZE CEILING (HRN-2.C): applies to every subagent call carrying a brief, any
#     role — "агента", not "исполнителя", is the word project.md's own paragraph uses. The
#     size of the context the agent's own most recent turn actually held (input_tokens +
#     cache_creation_input_tokens + cache_read_input_tokens of the LAST assistant record in
#     this run's own transcript, resolved from the call's own agent_id — see "WHICH
#     TRANSCRIPT RULES 8-10 JUDGE" below — what that one generation was actually given to
#     read, not a sum across the run) is compared
#     against CONTEXT_SIZE_CEILING (300,000 tokens). Past it, every call is refused except a
#     Write/Edit of this card's own log.md, with the words «запиши состояние в лог и
#     остановись» the plan itself quotes. A transcript that cannot be read, or carries no
#     assistant record with a usage field at all, is not a state this rule can judge, so the
#     call is skipped rather than denied — the same fail-open choice rule 5 already makes for
#     an unreadable plan.md.
#
#  9. SPEND CEILING (HRN-2.C): applies only to role "executor" — project.md's own wording
#     names it explicitly ("Потолок по расходу считается на прогон исполнителя"), unlike
#     rule 8 above. The run's cumulative spend (cache_read_input_tokens + output_tokens,
#     summed across every assistant record in this run's own transcript — the same
#     definition bin/agent-spend's own emit_spend() already uses for a card's `spend:`
#     field, reused here rather than invented fresh) is compared against SPEND_CEILING
#     (90,000,000 tokens). Counted per run, from that run's own transcript alone, never
#     accumulated across a card: there is no state file behind this number at all, so a
#     fresh executor's own fresh transcript starts this same count at zero by construction
#     — "свежий исполнитель приходит на карточку с нулём".
#
# 10. PACE CEILING (HRN-2.C): applies only to role "executor", the same scope as rule 9. The
#     run's own spend (rule 9's own count) divided by the number of tool calls it has made
#     (one per tool_use content block across the transcript) is compared against a threshold
#     read from a machine file, PACE_THRESHOLD_FILE (default hooks/work-gate-pace-threshold.txt,
#     next to this file — 460,000 as of HRN-2.C, per project.md's own "Потолок по темпу").
#     That file's absence, or content that does not parse as a bare integer, refuses every
#     call for this executor except a Write/Edit of this card's own log.md, regardless of
#     call count — this check runs before the call-count gate below, not behind it. Once a
#     threshold is read, the ceiling itself is judged only once this run has made more than
#     PACE_CALL_ALLOWANCE (120) tool calls — "темп не проверяется первые сто двадцать
#     вызовов" — every call up to and including the 120th passes with no inspection.
#
# 11. FILE-EDIT BRAKE (HRN-2.C, extended by HRN-21.C.1, softened 2026-08-31): past the Nth
#     Edit/Write of one and the same file inside one run, a point edit (Edit) of that file
#     refuses and a whole-file rewrite (Write of the same path) is allowed instead. The rule
#     exists to stop an agent hammering one place with a long series of small edits, not to
#     forbid finishing the file, so the refusal names the rewrite as the way through rather
#     than leaving the run with nothing to do but abandon the file
#     — mirrors hooks/card-touch-gate.sh's own BRAKE rule
#     and its measured threshold (BRAKE_THRESHOLD = 9, HRN-123.1's own p90 of the per-path
#     edit-count distribution across archived executor runs) rather than deriving a fresh
#     number for the same fact, matching the number this card's own plan names directly
#     ("девятая правка"). Applies to every role — the plan states this ceiling "в одном
#     прогоне", not "у исполнителя" the way it names rules 9 and 10 above. A Write/Edit
#     inside this card's own folder is never counted at all ("не считая записей в файлы
#     карточки"); a Bash call re-running the same command however many times is never
#     counted either, since this rule only ever inspects Write/Edit ("не ограничивать
#     повторный запуск одной и той же команды"). HRN-21.C.1: the very first Write that
#     brings a file into existence — one that does not yet exist on disk at the moment this
#     hook runs — is not a "правка" of anything and is never counted either, whatever count
#     already sits on file for that path; and since the brake exists to catch hammering of
#     code that was already on disk when the run began, that creation also takes the path
#     out of the count for the rest of the run, marker file and all ("тормоз ловит долбёжку по одному
#     месту, а не написание нового файла").
#
# 12. REPEATED REFUSAL → GLOBAL BREAKAGE (HRN-13.C): every call to deny_and_exit(reason,
#     rule) below, for a call that carries an agent_id (a subagent's own call — rule 3
#     already let the session's own call through before this could ever run), counts against
#     a per-agent, per-rule streak. Three denials in a row by the SAME rule write one line to
#     the global-breakage journal (ai/harness/journals/global.md, via `bin/work-journal
#     --breakage-once`, deduplicated so the same agent+rule pair never earns a second line
#     the same day) and reset the streak to zero; a denial by a DIFFERENT rule resets the
#     streak to one without writing anything; a call this hook ALLOWS never reaches
#     deny_and_exit at all, so it neither increments nor resets the streak — an executor
#     denied by the same rule, forced to write log.md (itself always allowed) in between,
#     still hits three in a row on its next matching denial ("разрешённый вызов между
#     отказами счёт не сбрасывает").
#
# Rule 6a keeps no state of its own either — it re-reads `git worktree list --porcelain`
# fresh on every call, exactly like rule 5's own resolution of the work root. Rule 6b keeps
# no state of its own for the same reason.
#
# STATE. Everything this hook remembers between calls lives under WORK_GATE_STATE_DIR
# (default "${TMPDIR:-/tmp}/claude-work-gate", the convention hooks/card-touch-gate.sh
# already uses for its own per-agent state): sanctions/<key>/<card id>.json (rule 2, one file
# per card this conversation was ever handed over to, written by bin/work-handover /
# bin/work-resume, never by this hook itself — reshaped per-card by HRN-52.A.1),
# one-task/<sanitized-transcript-path>.json (rule 2b, the one ordinary card this conversation
# has already sanctioned an executor spawn for — cards estimated 1 or 2 never occupy this
# file — written by this hook itself, the only writer),
# briefs/agent-<agent_id>.json
# / briefs/session-<session_id>.json (rule 4), log-call-counts/agent-<agent_id>.txt (rule 7),
# file-edit-counts/agent-<agent_id>/<sanitized-path>.txt (rule 11) and
# consecutive-refusals/agent-<agent_id>.txt (rule 12: the last rule that denied this agent,
# and how many times in a row). Rule 5 keeps no state of its own — it re-reads plan.md and
# log.md fresh on every call, and rules 8-10 keep no state of their own either — each
# re-reads this run's own transcript fresh on every call.
#
# TEST OVERRIDES, read only by bin/work-refusals, never present in a real deployed session:
#   WORK_GATE_STATE_DIR            overrides the whole state tree above.
#   WORK_GATE_WORK_ROOT            overrides the work root rule 5 resolves a card id
#                                   against (the directory holding the "harness" and
#                                   "timeline" kind folders, normally found via `git
#                                   worktree list --porcelain`'s own first entry — the
#                                   shared checkout's path, since a card's folder always
#                                   lives there and never inside a linked worktree's own
#                                   copy).
#   WORK_GATE_PACE_THRESHOLD_FILE  overrides the path rule 10 reads its threshold from
#                                   (default hooks/work-gate-pace-threshold.txt, next to
#                                   this file).
#   WORK_GATE_CARD_WORKTREE_ROOT   overrides the working copy path rule 6a resolves for the
#                                   run's own card (normally found via `git worktree list
#                                   --porcelain`'s own branch line, refs/heads/work/<card
#                                   id, lowercased>).
#
# Fail-closed: unparseable stdin denies.

STDIN_DATA="$(cat)"
# Passed to Python as-is; Python resolves it to the real underlying file with
# os.path.realpath() — see the comment on self_path below for why plain string handling
# here is not enough (~/.claude/hooks/ is itself a symlinked directory, and neither `cd
# "$(dirname ...)" && pwd` nor a hand-rolled `[ -L ]` loop over just the final path
# component follows a symlinked *directory* component, only a symlinked final file).
SELF_PATH="${BASH_SOURCE[0]}"

exec python3 - "$SELF_PATH" "$STDIN_DATA" <<'PYEOF'
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

# realpath(), not just the literal argv value: ~/.claude/hooks/ is itself a symlinked
# directory (bin/bootstrap.sh points it at this file's real repository path), and Claude
# Code always invokes this hook through that deployed, symlinked path — never through the
# real repository path directly. Without resolving through the directory symlink here, the
# self-edit exemption below (which compares this value against the file_path an Edit/Write
# call names, always the real repository path) would never match a live invocation, only
# bin/work-refusals's own synthetic cases, which run bash directly against the real path
# and so never exercised the symlink at all (found and fixed in HRN-2.D).
self_path  = os.path.realpath(sys.argv[1])
stdin_data = sys.argv[2]

ALLOW_JSON = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'

def deny_json(reason):
    return ('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
            '"permissionDecision":"deny",'
            '"permissionDecisionReason":' + json.dumps(reason) + '}}')

def allow_and_exit(reason=None):
    # HRN-48.D: an "allow" decision can still carry a permissionDecisionReason — used by rule
    # 3a's two coordinator-count rubrics to warn without ever refusing. reason=None (every
    # call site before HRN-48.D) reproduces the exact ALLOW_JSON string this function always
    # printed, so no other allow point in this file changes shape.
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            }
        }))
    else:
        print(ALLOW_JSON)
    sys.exit(0)

def _journal_shared_checkout_root():
    """The root bin/work-journal is found under and the journal files themselves resolve
    against, the same WORK_JOURNAL_DIR override bin/work_journal.py's own _checkout_root()
    honours first — this hook cannot import that module across the repository boundary, so
    it re-derives the same resolution here, never raising. Without the override: `git
    worktree list --porcelain`'s own first entry, the shared checkout's own path."""
    override = os.environ.get("WORK_JOURNAL_DIR")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):].strip()
    return None

def _write_refusal_journal(rule, input_text):
    """Best-effort call to bin/work-journal --refusal in the separate validite-app
    repository (HRN-13.B.4, HRN-13.A.4's own bin/work-journal) — never raises and never
    changes deny_and_exit's own return value or exit code, exactly like every other rule in
    this file that already fails open on an unreadable input rather than denying for a
    reason of its own making."""
    try:
        root = _journal_shared_checkout_root()
        if root is None:
            return
        journal_cmd = os.path.join(root, "bin", "work-journal")
        who = "hooks/work-gate.sh:" + str(globals().get("agent_id") or "session")
        subprocess.run([journal_cmd, "--refusal", who, rule, input_text],
                        capture_output=True, timeout=5)
    except Exception:
        pass

def consecutive_refusal_state_path(state_dir, aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(state_dir, "consecutive-refusals", "agent-" + safe + ".txt")

def read_consecutive_refusal_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            rule, count = f.read().strip().split("\t", 1)
        return rule, int(count)
    except (OSError, ValueError):
        return None, 0

def write_consecutive_refusal_state(path, rule, count):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(rule + "\t" + str(count))

CONSECUTIVE_REFUSAL_CEILING = 3

def _record_repeated_refusal(rule):
    """HRN-13.C.1: bump this agent's own consecutive-refusal streak for `rule`; on the third
    in a row, write one line to the global-breakage journal (deduplicated per agent+rule+day
    by bin/work-journal --breakage-once itself) and reset the streak to zero. A denial by a
    DIFFERENT rule resets the streak to one instead of writing anything. Skipped entirely for
    the session's own call (no agent_id) and for the narrow window before STATE_DIR itself
    is assigned — the same defensive globals().get(...) pattern _write_refusal_journal
    already uses above. Never raises."""
    aid = globals().get("agent_id")
    state_dir = globals().get("STATE_DIR")
    if not aid or not state_dir:
        return
    try:
        path = consecutive_refusal_state_path(state_dir, aid)
        last_rule, count = read_consecutive_refusal_state(path)
        count = count + 1 if last_rule == rule else 1
        if count >= CONSECUTIVE_REFUSAL_CEILING:
            root = _journal_shared_checkout_root()
            if root is not None:
                journal_cmd = os.path.join(root, "bin", "work-journal")
                key = "work-gate.repeated-refusal:%s:%s" % (aid, rule)
                text = ("hooks/work-gate.sh: агента %s правило %s отказало три раза "
                        "подряд." % (aid, rule))
                subprocess.run([journal_cmd, "--breakage-once", key, text],
                                capture_output=True, timeout=5)
            count = 0
        write_consecutive_refusal_state(path, rule, count)
    except Exception:
        pass

def deny_and_exit(reason, rule):
    _write_refusal_journal(rule, reason)
    _record_repeated_refusal(rule)
    print(deny_json(reason))
    sys.exit(0)

# --- 1. bypass -----------------------------------------------------------------------
if os.environ.get("CLAUDE_GATE_BYPASS") == "1":
    allow_and_exit()

# --- parse stdin (fail closed) --------------------------------------------------------
try:
    if not stdin_data.strip():
        raise ValueError("empty stdin")
    data = json.loads(stdin_data)
except Exception:
    deny_and_exit("Blocked by work-gate: gate error (unreadable hook payload), failing closed.", "work-gate.unreadable-payload")

tool_name  = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
agent_id   = data.get("agent_id")
session_id = data.get("session_id") or ""

STATE_DIR = os.environ.get("WORK_GATE_STATE_DIR") or \
    os.path.join(os.environ.get("TMPDIR", "/tmp"), "claude-work-gate")
BRIEFS_DIR = os.path.join(STATE_DIR, "briefs")
SANCTIONS_DIR = os.path.join(STATE_DIR, "sanctions")

# A card's own log.md, under the new folder shape ai/<kind>/<epic>/<ID>_<slug>/log.md, kind
# being "harness" or "timeline" (ai/harness/system/project.md, "Эпик"). Only log.md is
# matched here — the other card files, and the "one file, one author" rule that names them,
# belong to HRN-2.B, not to this file yet.
LOG_FILE_RE = re.compile(r'/ai/(?:harness|timeline)/[^/]+/[^/]+/log\.md$')

def file_path_of(ti):
    fp = ti.get("file_path")
    return fp if isinstance(fp, str) and fp else None

def command_of(ti):
    cmd = ti.get("command")
    return cmd if isinstance(cmd, str) else ""

def bash_names(command, script_basename):
    """True when a Bash command invokes a script by this basename — matched on any
    occurrence of the basename in the command line, the same coarse-but-safe matching
    harness-stamp-gate.sh already uses for 'bootstrap.sh' in its own command."""
    return script_basename in command

# The two kinds of work a card can belong to, each its own folder directly under the work
# root — identical to bin/work-plan's own KINDS, kept as its own small copy here rather
# than imported, the same way this repository's other git-plumbing helpers each carry their
# own copy (bin/session-start's own repo_root()/primary_worktree_path() comments name the
# same convention). Moved above rule 2b (HRN-51), which is the first rule below that needs
# to resolve a card's own folder — rule 5 further down still uses these same four names.
CARD_KINDS = ("harness", "timeline")

def find_work_root():
    """The directory holding the "harness" and "timeline" kind folders. A card's own folder
    always lives in the shared checkout, never inside a linked worktree's own copy
    (ai/harness/system/project.md, "Папка карточки всегда живёт в общем каталоге, а не в
    копии"), so this is resolved from the shared checkout's own path — `git worktree
    list --porcelain`'s first entry, readable from inside any linked worktree too — not
    from whatever repository copy this call's own cwd happens to sit in. Returns None when
    that cannot be resolved (cwd is not inside a git working tree at all, or git itself is
    unavailable), in which case the phase-boundary rule and rule 2b's own card-closure check
    are both skipped rather than denied."""
    override = os.environ.get("WORK_GATE_WORK_ROOT")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return os.path.join(line[len("worktree "):].strip(), "ai")
    return None

def epic_dirs(work_root):
    found = []
    for kind in CARD_KINDS:
        base = os.path.join(work_root, kind)
        if not os.path.isdir(base):
            continue
        for epic_name in sorted(os.listdir(base)):
            epic_dir = os.path.join(base, epic_name)
            if os.path.isdir(epic_dir):
                found.append(epic_dir)
    return found

def find_card_dir(work_root, card_id):
    for epic_dir in epic_dirs(work_root):
        for card_name in sorted(os.listdir(epic_dir)):
            if card_name == card_id or card_name.startswith(card_id + "_"):
                card_dir = os.path.join(epic_dir, card_name)
                if os.path.isdir(card_dir):
                    return card_dir
    return None

# Moved up from next to rule 6a (HRN-70) by HRN-63.B.1, which now needs this to find a
# phase's own gate script before rule 5 runs; rule 6a still uses the same function unchanged.
def find_card_worktree_root(card_id):
    """The path of card_id's own linked working copy, resolved the same way bin/work-session
    cuts one and bin/work-commit already finds it by name (rules.md rule 53): the entry in
    `git worktree list --porcelain` whose own branch is refs/heads/work/<card id, lowercased>.
    WORK_GATE_CARD_WORKTREE_ROOT overrides this outright, the same test-only escape every
    other git-plumbing lookup in this file already carries. None when no such branch is found
    at all — an ordinary case for a role other than executor, and for an executor whose
    brief names a card this session never actually ran bin/work-session for; the caller then
    skips this rule, since it has nothing to judge a boundary against."""
    override = os.environ.get("WORK_GATE_CARD_WORKTREE_ROOT")
    if override:
        return override
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    target_branch = "refs/heads/work/" + card_id.lower()
    current_path = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            if line[len("branch "):].strip() == target_branch and current_path:
                return current_path
    return None

# --- 2. no sanction, no executor spawn (HRN-48.B, reshaped per-card by HRN-52.A.1) -----
def sanctions_dir(sid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
    return os.path.join(SANCTIONS_DIR, safe)

def read_sanctions(sid):
    """Every sanction this conversation has ever written, each as a dict, read from every
    *.json file under sanctions/<key>/ — one file per card that conversation was handed
    over to (HRN-52.A.1). Best-effort throughout: a directory that does not exist yet, or a
    single file that will not parse, is simply skipped rather than denying the whole call —
    the same fail-open posture rule 2b already takes on a reading error of its own."""
    d = sanctions_dir(sid)
    result = []
    try:
        names = sorted(os.listdir(d))
    except Exception:
        return result
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if isinstance(obj, dict):
            result.append(obj)
    return result

TERMINAL_STATE_FILES = ("done.md", "cancelled.md", "rejected.md", "question.md")

def sanction_card_is_terminal(card_id):
    """True when card_id's own folder already carries one of the four terminal-state files
    bin/work-handover itself refuses a handover on — a sanction written before the card
    reached one of these states must never let a later spawn resurrect it past that
    refusal. False when the folder is found and carries none of the four. None on any
    reading error of this check's own (no work root, no matching folder, a listing that
    raises) — read as "not terminal" by the caller, since a bug here must never manufacture
    a denial out of a card name rule 2 already found sanctioned and matched in the prompt."""
    try:
        root = find_work_root()
        if root is None:
            return None
        card_dir = find_card_dir(root, card_id)
        if card_dir is None:
            return None
        return any(os.path.isfile(os.path.join(card_dir, fname))
                    for fname in TERMINAL_STATE_FILES)
    except Exception:
        return None

DENY_NO_SANCTION = (
    "Blocked by work-gate: no sanction on file for this session raising an executor "
    "subagent — call bin/work-handover <ID> for a fresh phase, or bin/work-resume <ID> "
    "for an interrupted one, and let it print the executor's own brief before spawning "
    "the executor with it."
)

# --- 2b. one conversation runs one task (HRN-48.C, carried from the retired
# hooks/plan-gate.sh's own second_task_deny_reason(), HRN-203) -------------------------
ONE_TASK_STATE_DIR = os.path.join(STATE_DIR, "one-task")

def one_task_state_path(transcript_path):
    """None when there is no transcript_path to key state on — this rule then has nothing
    to judge and falls through to an allow, the same fail-open posture card-touch-gate.sh's
    own COORD rule already takes when it cannot establish a session identifier."""
    if not transcript_path:
        return None
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))
    return os.path.join(ONE_TASK_STATE_DIR, safe + ".json")

SECOND_TASK_TEMPLATE = (
    "Blocked by work-gate: this conversation already sanctioned an executor on {owned}, and "
    "this spawn's own sanction names a different card, {attempted}. One conversation runs "
    "one task: finish the current task and close this conversation with /clear before "
    "starting the next one, or, when the two pieces of work genuinely must run at the same "
    "time, open a separate session with /parallel instead of spawning a second executor here."
)

def owned_card_is_closed(card_id):
    """HRN-51: True only when card_id's own folder can be found and it carries a done.md or
    cancelled.md file — the two terminal markers rules.md's own rule 51 names ("A folder
    carrying none of these three is still in progress" — the third, rejected.md, is never
    checked here, since a rejected card is sent back for a plan fix and still occupies the
    conversation). False when the folder is found but carries neither file — the ordinary,
    still-open case. None when the card's own folder cannot be established at all (no work
    root, no matching folder, or a listing that raises) — this function's own reading error,
    which second_task_deny_reason below must treat as a permission, never as grounds to
    deny, exactly like every other reading error this rule already tolerates."""
    try:
        root = find_work_root()
        if root is None:
            return None
        card_dir = find_card_dir(root, card_id)
        if card_dir is None:
            return None
        return os.path.isfile(os.path.join(card_dir, "done.md")) or \
            os.path.isfile(os.path.join(card_dir, "cancelled.md"))
    except Exception:
        return None

def second_task_deny_reason(card, transcript_path):
    """None to allow (recording the card as needed); the deny reason string otherwise. This
    rule never creates a permission of its own — it only ever turns an allow rule 2 has
    already decided into a deny — and it never raises: every failure of its own (an
    unwritable state directory, a corrupt state file, an unresolvable card folder) falls
    through to None, an allow, because a bug in this rule must never widen into a refusal
    rule 2 did not itself make.

    HRN-51: a remembered card stops occupying the conversation the moment its own folder
    carries done.md or cancelled.md — a later spawn naming a different card then passes,
    and that card takes the remembered one's place in the state file, the same write the
    fresh-start branch below already performs. While neither marker is on disk, the denial
    is unchanged, naming both exits below. owned_card_is_closed()'s own reading error (its
    own None) is answered with an allow that leaves the state file untouched, never with a
    denial — this rule can turn an already-decided allow into a deny, never manufacture one
    of its own out of a failure to read."""
    try:
        state_path = one_task_state_path(transcript_path)
        if not state_path:
            return None
        owned = None
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    owned = loaded.get("card")
            except Exception:
                owned = None  # a corrupt state file is a fresh start, not an error to deny on
        if owned is None:
            os.makedirs(ONE_TASK_STATE_DIR, exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"card": card}, f)
            return None
        if owned == card:
            return None
        closed = owned_card_is_closed(owned)
        if closed is None:
            return None  # a reading error of this check's own — never a reason to deny
        if closed:
            os.makedirs(ONE_TASK_STATE_DIR, exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"card": card}, f)
            return None
        return SECOND_TASK_TEMPLATE.format(owned=owned, attempted=card)
    except Exception:
        return None
# --- end 2b -----------------------------------------------------------------------------

if not agent_id and tool_name in ("Task", "Agent") and \
        (tool_input.get("subagent_type") or "").strip() == "executor":
    prompt_text = ((tool_input.get("prompt") or "") + " " +
                   (tool_input.get("description") or ""))
    # HRN-52.A.1: this conversation may have handed over more than one card — walk every
    # sanction it ever wrote and take the first whose own card name shows up in this spawn's
    # own prompt/description, exactly the same substring test the single-sanction form used.
    # Newest sanction first, and a card that has already reached a terminal state is skipped
    # rather than being taken as the match: read in file-name order, an older, finished card
    # masked the live one whenever the executor's own brief merely mentioned it, and the
    # spawn was refused for having no sanction at all. Measured 2026-09-01 — a HRN-68 spawn
    # refused because its brief named HRN-63, accepted minutes earlier, whose own sanction
    # file sorts first. A sanction whose card cannot be read at all still counts as live,
    # exactly as sanction_card_is_terminal's own None already means to every caller.
    matched_sanction = None
    for candidate in sorted(read_sanctions(session_id),
                            key=lambda c: c.get("time") or 0, reverse=True):
        card = candidate.get("card")
        if card and card in prompt_text and not sanction_card_is_terminal(card):
            matched_sanction = candidate
            break
    if matched_sanction is None:
        deny_and_exit(DENY_NO_SANCTION, "work-gate.no-sanction-executor-spawn")
    matched_card = matched_sanction.get("card")
    matched_estimate = matched_sanction.get("estimate")
    matched_short = bool(matched_sanction.get("short"))
    # HRN-52.A.2, threshold raised from 1 to 2 by HRN-53.A.1: a sanction proven to carry the
    # integer 1 or 2 as its own estimate skips rule 2b entirely — never denied by it, never
    # recorded as occupying the conversation. HRN-54.B.3: a sanction carrying the short-card
    # flag skips it the same way regardless of its own estimate — the structural fact
    # work_journal.is_short_card already named on the bin/work-handover side, so a short
    # card's own estimate (always 1 per rule 66) never has to be the thing this rule reads.
    # Anything else (no estimate field, one that is not exactly 1 or 2, and no short flag) is
    # judged by rule 2b exactly as before either exemption existed.
    if not (matched_short or (isinstance(matched_estimate, int) and matched_estimate in (1, 2))):
        second_reason = second_task_deny_reason(matched_card, data.get("transcript_path"))
        if second_reason is not None:
            deny_and_exit(second_reason, "work-gate.second-task-in-conversation")

# --- 3. / 3a. the session's own call passes, but is watched by two warn-only rubrics
# (HRN-48.D) whose ceilings are carried over unchanged from the retired
# hooks/card-touch-gate.sh's own COORD and SEARCH-AGENT rules -----------------------------
COORD_CALL_CEILING = 761  # card-touch-gate.sh's own COORD_CEILING
SEARCH_AGENT_RAISE_CEILING = 28  # card-touch-gate.sh's own SEARCH_AGENT_CEILING
SEARCH_AGENT_ROLE_TYPES = {"Explore", "Plan", "trace-audit"}  # plan-gate.sh's own
                                                               # ALLOWLISTED_SUBTYPES

COORD_CALLS_DIR = os.path.join(STATE_DIR, "coord-calls")
SEARCH_AGENT_RAISES_DIR = os.path.join(STATE_DIR, "search-agent-raises")

COORD_COUNT_WARN_TEMPLATE = (
    "work-gate's COORD count: this coordinator session has made {count} tool calls, past its "
    "own watched ceiling of {ceiling} (carried over from the retired card-touch-gate.sh's own "
    "COORD rule). This is a count, not a refusal — the call still passes."
)

SEARCH_AGENT_RAISE_WARN_TEMPLATE = (
    "work-gate's SEARCH-AGENT count: this session has raised {count} reading agents "
    "(subagent_type={agent_type} included), past its own watched ceiling of {ceiling} "
    "(carried over from the retired card-touch-gate.sh's own SEARCH-AGENT rule). This is a "
    "count, not a refusal — the spawn still passes."
)

def _sanitized_transcript_token(transcript_path):
    if not transcript_path:
        return None
    return re.sub(r'[^A-Za-z0-9_-]', '_', os.path.basename(str(transcript_path)))

def _bump_counter(dir_path, token, field):
    """Best-effort increment-and-read of a per-token counter file; never raises — returns the
    new count (starting at 1) on success, None when the count cannot be established at all,
    the same fail-open posture every other rule in this file already takes."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, token + ".json")
        count = 0
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    count = loaded.get(field, 0)
            except Exception:
                count = 0
        count += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump({field: count}, f)
        return count
    except Exception:
        return None

if not agent_id:
    warn_reason = None
    token = _sanitized_transcript_token(data.get("transcript_path"))
    if token:
        coord_count = _bump_counter(COORD_CALLS_DIR, token, "coord_count")
        if coord_count is not None and coord_count > COORD_CALL_CEILING:
            warn_reason = COORD_COUNT_WARN_TEMPLATE.format(
                count=coord_count, ceiling=COORD_CALL_CEILING)
        subagent_type = (tool_input.get("subagent_type") or "").strip()
        if tool_name in ("Task", "Agent") and subagent_type in SEARCH_AGENT_ROLE_TYPES:
            raise_count = _bump_counter(SEARCH_AGENT_RAISES_DIR, token, "raise_count")
            if raise_count is not None and raise_count > SEARCH_AGENT_RAISE_CEILING:
                search_warn = SEARCH_AGENT_RAISE_WARN_TEMPLATE.format(
                    agent_type=subagent_type, count=raise_count,
                    ceiling=SEARCH_AGENT_RAISE_CEILING)
                warn_reason = (warn_reason + " " + search_warn) if warn_reason else search_warn
    allow_and_exit(warn_reason)

# --- 4. no brief, no launch (one exemption: writing the very first brief) -------------
KNOWN_ROLES = {"critic", "mapper", "executor", "tracer", "acceptor"}

def agent_brief_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(BRIEFS_DIR, "agent-" + safe + ".json")

def session_brief_path(sid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(sid)) if sid else "_no_session_id_"
    return os.path.join(BRIEFS_DIR, "session-" + safe + ".json")

is_brief_self_write = tool_name == "Bash" and bash_names(command_of(tool_input), "work-agent-brief")
if is_brief_self_write:
    # The one moment this hook writes state of its own accord rather than only reading it:
    # agent_id is the sole identifier proven stable for a subagent's whole life (HRN-46), and
    # it is never visible to the subagent's own shell as an environment variable — only to
    # this hook's own payload — so this hook is the only thing that can ever correctly key a
    # brief on it. Parsed straight out of the command string about to run; a command that
    # does not parse (a malformed invocation) is still allowed through unconditionally,
    # since the real script's own argument validation is what should report that failure,
    # not this hook.
    command = command_of(tool_input)
    m_role = re.search(r'--role[= ]+(\S+)', command)
    m_card = re.search(r'--card[= ]+(\S+)', command)
    m_phase = re.search(r'--phase[= ]+(\S+)', command)
    if m_role and m_card and m_role.group(1) in KNOWN_ROLES and agent_id:
        os.makedirs(BRIEFS_DIR, exist_ok=True)
        brief_obj = {"role": m_role.group(1), "card": m_card.group(1)}
        if m_phase:
            brief_obj["phase"] = m_phase.group(1)
        try:
            with open(agent_brief_path(agent_id), "w", encoding="utf-8") as f:
                json.dump(brief_obj, f)
        except OSError:
            pass
    allow_and_exit()

def read_brief(aid, sid):
    for path in (agent_brief_path(aid) if aid else None, session_brief_path(sid)):
        if not path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                b = json.load(f)
        except Exception:
            continue
        if not isinstance(b, dict):
            continue
        role, card = b.get("role"), b.get("card")
        if role and card:
            # "phase" (HRN-2.F): the plan phase this run is working, named only by whoever
            # launched it — bin/work-agent-brief's own --phase — and never derivable from the
            # card's own files. None when the brief carries no such key at all (an older
            # brief, or any role other than executor, which the phase boundary rule below
            # never requires it from).
            return {"role": role, "card": card, "phase": b.get("phase")}
    return None

brief = read_brief(agent_id, session_id)
if brief is None:
    deny_and_exit(
        "Blocked by work-gate: this subagent carries no caller-brief file. The step that "
        "launches an agent must run bin/work-agent-brief first, naming this agent's own "
        "role and the card it is working — this hook writes %s the moment it sees that "
        "call, and the script itself separately writes %s; neither exists yet (or neither "
        "is valid JSON naming a role and a card). «Нет файла — нет запуска.»" %
        (agent_brief_path(agent_id), session_brief_path(session_id)),
        "work-gate.no-brief-no-launch"
    )

# --- 4a. READING ROLE IS READ-ONLY: the four reading roles get no Bash call at all -------
# The brief call itself never arrives here — rule 4's own is_brief_self_write branch allows
# and exits on it above — so every Bash call that reaches this line is a second one, and a
# reading agent has no second one. Enforced here rather than in the agent's own `tools:`
# line, which cannot hold a scoped Bash specifier: see rule 4a's own paragraph in the header.
READING_ROLES = ("critic", "mapper", "tracer", "acceptor")

if brief.get("role") in READING_ROLES and tool_name == "Bash":
    deny_and_exit(
        "Blocked by work-gate's READING ROLE IS READ-ONLY rule: role \"%s\" reads and never "
        "runs anything. The one Bash call this role is allowed, bin/work-agent-brief, has "
        "already happened — every later one is refused, this one included: %s. Read the "
        "sources with Read, Glob and Grep and answer the question you were raised for; you "
        "never run a check yourself, and you never see a check's output. Whatever raised "
        "you runs every check with its own hand, after reading your answer." %
        (brief.get("role"), command_of(tool_input)),
        "work-gate.reading-role-read-only"
    )

# --- 5. PHASE BOUNDARY: an executor whose current phase has no open steps left is refused
# every call except a Write/Edit of its own card's log.md, and a Bash call that does nothing
# but `git add` or `git commit` (HRN-2.D, extended by HRN-21.A) -----------------------

# HRN-21.A: the boundary exists to stop an executor from STARTING new work once its own
# phase is closed, not to stop it from SAVING work already done — writing the log entry that
# closes the phase is worthless if the very next call, the commit that lands it, is refused.
# This list is closed and literal, per this card's own plan ("Решения, принятые при
# написании плана", "Защёлка ничего не толкует и ничего не угадывает"): no rule here
# recognises a call by resemblance to a save. `git merge`, `git push` and `git rebase` are
# refused at the boundary exactly as before, because the executor may not run them at all,
# boundary or not — they are not in this list and never will be. A harmless `git status`, or
# any command not in this list, is refused exactly like any other call.
#
# HRN-21.C.3: the same closed list also exempts a Bash call running bin/work-note, one more
# entry added the same deliberate way — the boundary must not strand an executor holding the
# one command this system requires it to close its own last step with. That call gets its
# own recognising function, is_phase_boundary_log_call() below, rather than joining this
# git-only one: a real bin/work-note invocation always carries a heredoc body (its own
# stdin — the check's own verbatim output), which legitimately spans many lines, so the bare
# "no newline anywhere" test below cannot apply to it.
PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS = ("add", "commit")

# Every quoted span of a shell command — single-quoted, or double-quoted with backslash
# escapes honoured. Blanking these out before looking for chaining is what keeps an
# argument's own contents from being read as shell syntax.
QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)
CHAINING_RE = re.compile(r'(&&|;|\||\n)')

def chains(command):
    """True when the command runs more than one statement. Judged against the command with
    every quoted span blanked out, because a `;`, `|`, `&&` or newline inside an argument is
    ordinary prose — a handoff entry's own text carries all four — and reading it as shell
    syntax refused exactly the calls this boundary is supposed to let through (found live
    closing HRN-6.C)."""
    return CHAINING_RE.search(QUOTED_SPAN_RE.sub("", command)) is not None

# `-C <path>` and `-c <key>=<value>` before the subcommand: git's own two options that take
# a value and change nothing about which subcommand runs. `-C` in particular is the only way
# to name another working copy without a `cd`, and a `cd` is chaining and refused here — so
# refusing `git -C <copy> add` while promising that `git add` gets through left an executor
# standing in the shared checkout with no way at all to stage its own copy's work, which is
# exactly the wall HRN-59's own executor hit some twenty times (2026-08-31).
GIT_PRE_SUBCOMMAND_VALUE_OPTS = ("-C", "-c")

def git_subcommand(command):
    """The subcommand of a `git …` invocation, skipping the options that legitimately come
    before it, or None when the command is not a git invocation at all."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GIT_PRE_SUBCOMMAND_VALUE_OPTS:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None

def is_phase_boundary_save_call():
    """True only for a Bash call whose entire command is a single `git add` or `git commit`
    invocation — never a substring or resemblance match. A command that chains more than one
    statement is never exempt, even when one of its parts is itself a bare `git add` or
    `git commit`, since the exemption names one specific action, not a shell script that
    happens to contain it somewhere. `git -C <copy> add` counts as `git add`: the option
    names which working copy is written and changes nothing about what the call does."""
    if tool_name != "Bash":
        return False
    command = command_of(tool_input)
    if chains(command):
        return False
    return git_subcommand(command) in PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS

# A command invoking one of the three commands that record and land a closed phase, by the
# bare relative path or by any path ending in that same bin/<name> component — never by
# basename alone, so that a path such as ~/elsewhere/work-note is not exempt while
# /abs/path/to/bin/work-note is.
PHASE_BOUNDARY_LOG_CALL_RE = re.compile(r'^\s*(\S*/)?bin/work-(log|note|commit)\b')

def matched_log_call_kind():
    """Which of bin/work-note / bin/work-commit / bin/work-log this Bash call actually
    invokes — "note", "commit" or "log" — matched the same rigorous, heredoc-aware,
    chain-aware way is_phase_boundary_log_call() always has; None when the call is not a
    single, genuine invocation of any of the three. The one shared parser behind two
    different callers: is_phase_boundary_log_call() below (any of the three, unchanged
    behaviour) and is_work_note_invocation() (HRN-63.B.1's own trigger for a phase's own
    gate — "note" only, never "commit" or "log").

    A real invocation always carries a heredoc body (bin/work-note's own stdin, the check's
    own verbatim output) — legitimately spanning many lines and containing any character at
    all, including `&&`/`;`/`|` — so the plain "no newline anywhere" test
    is_phase_boundary_save_call() applies to git cannot apply here. Chaining is instead
    judged only against the text OUTSIDE the heredoc body: the first line, up to its own
    heredoc marker, carries none of `&&`/`;`/`|` and starts with one of the three script
    names; and when a heredoc marker is present, the command's own last line is exactly that
    marker and nothing follows it. A command naming no heredoc marker at all still may not
    chain, exactly like git add/commit.

    The command may name the script by an absolute path as well as by the bare relative one
    (found live closing HRN-6.B): an executor works in its own linked working copy while
    this environment resets every Bash call's own working directory to the shared checkout,
    so the relative form reaches the wrong copy — or no file at all, when the command being
    called is one the card itself is still building — and the only other way of reaching it,
    a `cd` in front, is chaining and refused. Matching is on the path's own trailing
    component, never on the basename alone, so a command merely mentioning the name
    somewhere is still not exempt."""
    if tool_name != "Bash":
        return None
    command = command_of(tool_input)
    lines = command.rstrip("\n").split("\n")
    first_line = lines[0]
    heredoc_m = re.search(r'<<-?\s*([\'"]?)(\w+)\1\s*$', first_line)
    if heredoc_m:
        head = first_line[:heredoc_m.start()]
        if CHAINING_RE.search(QUOTED_SPAN_RE.sub("", head)):
            return None
        m = PHASE_BOUNDARY_LOG_CALL_RE.match(head)
        if m is None:
            return None
        if lines[-1].strip() != heredoc_m.group(2):
            return None
        return m.group(2)
    if chains(command):
        return None
    m = PHASE_BOUNDARY_LOG_CALL_RE.match(command)
    return m.group(2) if m else None

def is_phase_boundary_log_call():
    """True only for a Bash call that is a single invocation of bin/work-note or
    bin/work-commit — exempted at the boundary for the same reason git add/commit already
    are (HRN-21.A.1), added by HRN-21.C.3: writing the log entry that closes a phase is
    worthless if the very next call, the one command this system requires to record it, is
    itself refused.

    `bin/work-commit` is exempt alongside `bin/work-note`, for the same reason and found the
    same way (closing HRN-6.C): it is what this system puts in place of the bare `git
    add`/`git commit` already exempt here, and an executor that cannot call it at the
    boundary cannot land the work whose closure it has just recorded — as happened, one
    phase after the absolute-path defect above, leaving a finished phase's code stranded
    uncommitted in its own working copy."""
    return matched_log_call_kind() in ("note", "commit")

def is_work_note_invocation():
    """True only for a Bash call that is a single, genuine invocation of bin/work-note —
    matched_log_call_kind() narrowed to that one script (HRN-63.B.1): the trigger for
    running the run's own named phase's gate-<фаза>.sh, never fired by bin/work-commit or
    bin/work-log, which record or land a phase but never close one on their own."""
    return matched_log_call_kind() == "note"

# CARD_KINDS, find_work_root(), epic_dirs(), find_card_dir() and find_card_worktree_root()
# moved up next to rule 2b (HRN-51 / HRN-63.B.1), which now need them to resolve a card's
# own folder, and its own working copy, before rule 5 below runs; rule 5 still uses the
# same names, unchanged.

# HRN-63.B: the phase boundary no longer counts closed-step headings in log.md at all — it
# reads one fact, whether <phase_id>.closed already sits in the card's own folder in the
# shared checkout, laid only by that phase's own gate-<phase_id>.sh returning zero
# (run_phase_gate_if_due() below). parse_plan_phases(), short_card_total_steps(),
# closed_steps_for_phase() and total_steps_for_phase() — the whole log.md-header-counting
# machinery HRN-2.E and HRN-54.B.3 built — are gone with them; plan.md and description.md
# are no longer read by this rule at all.
PHASE_GATE_RUNNING_ENV = "WORK_GATE_PHASE_GATE_RUNNING"
PHASE_GATE_TIMEOUT = 900  # seconds — generous for a real check, bounded against a hang

def phase_closed_marker_path(card_dir, phase_id):
    return os.path.join(card_dir, phase_id + ".closed")

def phase_closed(card_dir, phase_id):
    return os.path.isfile(phase_closed_marker_path(card_dir, phase_id))

def run_phase_gate_if_due(card_dir, phase_id):
    """HRN-63.B.1/B.2: on a genuine bin/work-note invocation (is_work_note_invocation()
    above), while phase_id is not yet closed, run that phase's own gate-<phase_id>.sh — the
    one copy that lives in the card's own linked working copy (find_card_worktree_root()
    above), with that working copy as the script's own working directory — and, on a zero
    return, lay and commit the boundary marker <phase_id>.closed in the card's folder in the
    shared checkout, the same way bin/work_journal.py's own record_breakage() commits a
    single file directly by path, except that a brand-new marker is untracked the first time
    and needs its own `git add` first — a bare `git commit -- <path>` refuses an untracked
    path outright, proved live writing this same step. Never raises and never denies on its
    own account: every failure to resolve, run or commit falls through silently, leaving the
    phase open exactly as it was.

    Guarded by PHASE_GATE_RUNNING_ENV against recursing into itself: a phase's own gate
    script may itself drive this very hook through synthetic bin/work-note calls of its own
    (gate-HRN-63.B.sh does exactly this, on this very card), and since
    find_card_worktree_root() always resolves to the one real working copy a card's branch
    actually has, whatever state directory the outer run used, that nested run would
    otherwise ask this same function to run the very gate that is already running, without
    ever returning. Set once, in the environment the gate script's own subprocess (and every
    `sh work-gate.sh` call it makes in turn) inherits, so at most one nested real run
    happens and stops there."""
    if not is_work_note_invocation():
        return
    if phase_closed(card_dir, phase_id):
        return
    if os.environ.get(PHASE_GATE_RUNNING_ENV) == "1":
        return
    own_root = find_card_worktree_root(brief["card"])
    if not own_root:
        return
    working_copy_card_dir = find_card_dir(os.path.join(own_root, "ai"), brief["card"])
    if not working_copy_card_dir:
        return
    gate_path = os.path.join(working_copy_card_dir, "gate-" + phase_id + ".sh")
    if not (os.path.isfile(gate_path) and os.access(gate_path, os.X_OK)):
        return
    try:
        env = dict(os.environ)
        env[PHASE_GATE_RUNNING_ENV] = "1"
        result = subprocess.run([gate_path], cwd=own_root, env=env,
                                 capture_output=True, timeout=PHASE_GATE_TIMEOUT)
    except Exception:
        return
    if result.returncode != 0:
        return
    marker = phase_closed_marker_path(card_dir, phase_id)
    try:
        with open(marker, "w", encoding="utf-8"):
            pass
        add = subprocess.run(["git", "add", "--", marker], cwd=card_dir,
                              capture_output=True, timeout=30)
        if add.returncode != 0:
            return
        subprocess.run(
            ["git", "commit", "--no-verify", "-m",
             "chore(%s): mark phase %s closed by its own gate" % (brief["card"], phase_id),
             "--", marker],
            cwd=card_dir, capture_output=True, timeout=30,
        )
    except Exception:
        pass

work_root = find_work_root()
card_dir = find_card_dir(work_root, brief["card"]) if work_root else None

# A brief naming a card whose folder cannot be found is refused rather than let through.
# card_dir being None used to fail open everywhere it is read, which is right for the one
# case it was written for — git unavailable, so work_root itself is None and nothing about
# this repository can be resolved at all. It is wrong for the other case: work_root resolved
# fine and the brief simply names something that is not a card. Every rule scoped to a card —
# the phase boundary, the run of that phase's own gate, the file-authorship rule — then
# vanishes silently, and the run continues with no boundary over it while every party
# believes there is one. Measured live 2026-09-01 on HRN-63: an executor re-ran
# bin/work-agent-brief with its own card folder's absolute path in place of the identifier,
# and worked the rest of its run ungoverned, laying no phase marker and never once being
# stopped. bin/work-agent-brief now refuses that value at the source; this refuses whatever
# still reaches here by another road.
if work_root and card_dir is None:
    deny_and_exit(
        "Blocked by work-gate: this run's own caller-brief names %r as its card, and no "
        "card folder of that name exists under %s. A card is named by its identifier — "
        "HRN-6, MAT-7 — never by a path to its own folder. Every rule this gate scopes to "
        "a card is off while the brief says this, so the run is stopped here rather than "
        "allowed to continue ungoverned. Re-write the brief with the identifier: "
        "bin/work-agent-brief --role %s --card <ID>%s" %
        (brief["card"], work_root, brief.get("role") or "executor",
         (" --phase " + brief["phase"]) if brief.get("phase") else ""),
        "work-gate.brief-names-no-card"
    )

if brief.get("role") == "executor" and card_dir is not None:
    fp = file_path_of(tool_input)

    def is_this_cards_log_write():
        # "Read" is exempted alongside "Write"/"Edit" (found live closing HRN-34.B): the
        # Edit tool's own client-side staleness check refuses to edit a file that changed
        # on disk since this session last read it, and log.md is dirtied outside Claude's
        # own file tracking by every bin/work-note call — so with Read still refused at the
        # boundary, Edit could never satisfy its own precondition and the boundary's one
        # designated escape (a Write/Edit of this file) became unreachable via Edit.
        return (tool_name in ("Read", "Write", "Edit") and fp is not None and
                os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md")))

    phase_id = brief.get("phase")
    if not phase_id:
        if is_this_cards_log_write():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's PHASE BOUNDARY rule: this executor's caller-brief "
            "names no phase — an unnamed phase does not exempt a run from the boundary, it "
            "blocks it, exactly like a subagent that carries no caller-brief file at all "
            "(rule 4). Re-launch with bin/work-agent-brief --role executor --card %s "
            "--phase <ID>, naming the phase this run is actually working. The only call "
            "that still gets through is a Write/Edit of this card's own log.md: «допиши "
            "передачу и остановись»." % brief["card"],
            "work-gate.phase-boundary-blocks-unnamed-phase"
        )
    else:
        run_phase_gate_if_due(card_dir, phase_id)
        if phase_closed(card_dir, phase_id):
            if is_this_cards_log_write() or is_phase_boundary_save_call() or \
                    is_phase_boundary_log_call():
                allow_and_exit()
            deny_and_exit(
                "Blocked by work-gate's PHASE BOUNDARY rule: phase %s — the phase this "
                "run's own caller-brief names — is already closed: its own gate-%s.sh has "
                "already returned zero, and %s.closed sits in this card's own folder, "
                "regardless of what any other phase in the plan looks like. A fresh "
                "executor takes the next phase, not this one. Save what is already built "
                "and stop — «допиши передачу и остановись».\n"
                "These four calls, and nothing else, still get through. Each is a "
                "single command: no `cd` in front, no `&&`, no `;`, no `|` — every "
                "chained command is refused here, whatever it chains.\n"
                "  1. Commit this phase's own code (this command finds the card's own "
                "working copy itself, from the step name — you do not have to be "
                "standing in it, and there is no path to pass):\n"
                "         bin/work-commit %s.<N> \"<что сделал шаг>\"\n"
                "  2. Write the phase's own handoff entry:\n"
                "         bin/work-note %s --handoff %s \"<состояние, находки, что "
                "дальше>\"\n"
                "  3. A bare `git add` or `git commit`, including the `git -C <путь "
                "копии> …` form, when you need git directly rather than the two "
                "commands above.\n"
                "  4. A Read, Write or Edit of this card's own log.md, and of no "
                "other file." % (phase_id, phase_id, phase_id, phase_id, brief["card"],
                                  phase_id),
                "work-gate.phase-boundary-own-phase-closed-later-untouched"
            )

# --- 6. FILE AUTHORSHIP (HRN-2.B): "one file, one author" ------------------------------
# ai/harness/system/project.md, "Правка чужого файла": the executor may not write
# description.md, attention.md or done.md — each belongs to a different role (the owner via
# the orchestrator, the critic, the acceptor) — and may not write plan.md either, but that
# refusal names question.md instead, per this same document's "Проблема в плане": the
# executor records a proposed change there and keeps working, rather than touching the plan
# itself. The acceptor may not write log.md — that file is the executor's own. Only a call
# that targets a file actually inside THIS card's own folder is judged; card_dir is None
# (skip, fail open) exactly when rule 5 above already treats it as unresolvable.
EXECUTOR_LOCKED_FILES = ("description.md", "attention.md", "done.md")

if tool_name in ("Write", "Edit") and card_dir is not None:
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        real_card_dir = os.path.realpath(card_dir)
        if os.path.dirname(real_fp) == real_card_dir:
            fname = os.path.basename(real_fp)
            role = brief.get("role")
            if role == "executor" and fname == "plan.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: plan.md is not the "
                    "executor's file to write — the orchestrator alone edits the plan. "
                    "Write the proposed change to question.md in this card's own folder "
                    "instead and keep working; the orchestrator watches for that file and "
                    "answers it. «Один файл, один автор.»",
                    "work-gate.file-authorship-plan"
                )
            if role == "executor" and fname in EXECUTOR_LOCKED_FILES:
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: %s is not the executor's "
                    "file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\"." % fname,
                    "work-gate.file-authorship-executor-locked"
                )
            if role == "acceptor" and fname == "log.md":
                deny_and_exit(
                    "Blocked by work-gate's FILE AUTHORSHIP rule: log.md is not the "
                    "acceptor's file to write — «Один файл, один автор». See "
                    "ai/harness/system/project.md, \"Правка чужого файла\".",
                    "work-gate.file-authorship-acceptor-log"
                )

# --- 6a. WORKING COPY BOUNDARY (HRN-70): an executor's own Write/Edit lands inside its
# card's own linked working copy, never inside the shared checkout every other session on
# this machine shares. Judged only for role "executor", and only once card_dir is known —
# the same fail-open posture rule 6 above already takes when card_dir cannot be resolved. A
# target inside the card's own folder is never judged here at all: description.md, plan.md,
# log.md, question.md and every other file that folder holds are written by whichever
# command owns each one, in the shared checkout, by design (rules.md rule 51) — this rule
# exists for the executor's own product-code edits, not for those.
def resolve_shared_checkout_root():
    """The shared checkout's own path — os.path.dirname(work_root), since find_work_root()
    above always returns that path with "ai" appended, by construction or by its own test
    override. None when work_root itself is None."""
    if not work_root:
        return None
    return os.path.dirname(work_root)

WORKING_COPY_BOUNDARY_TEMPLATE = (
    "Blocked by work-gate's WORKING COPY BOUNDARY rule: this call would edit %s, inside the "
    "shared checkout — not this card's own working copy, %s. Repeat the same edit at the "
    "right address instead: %s."
)

if brief.get("role") == "executor" and tool_name in ("Write", "Edit") and card_dir is not None:
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        real_card_dir = os.path.realpath(card_dir)
        if os.path.dirname(real_fp) != real_card_dir:
            shared_root = resolve_shared_checkout_root()
            own_root = find_card_worktree_root(brief["card"])
            if shared_root and own_root:
                real_shared_root = os.path.realpath(shared_root)
                real_own_root = os.path.realpath(own_root)
                inside_shared = (real_fp == real_shared_root or
                                  real_fp.startswith(real_shared_root + os.sep))
                inside_own = (real_fp == real_own_root or
                              real_fp.startswith(real_own_root + os.sep))
                if inside_shared and not inside_own:
                    rel = os.path.relpath(real_fp, real_shared_root)
                    right_path = os.path.join(real_own_root, rel)
                    deny_and_exit(
                        WORKING_COPY_BOUNDARY_TEMPLATE % (real_fp, real_own_root, right_path),
                        "work-gate.working-copy-boundary"
                    )

# --- 6b. GIT COMMAND (HRN-70): an executor's own `git` invocation is read-only by default —
# status, diff, log, show, rev-parse, ls-files, worktree list — and anything else is refused,
# naming the reference command that does the same thing correctly instead of a bare git call:
# bin/work-commit for saving or discarding work (stash, add, commit, checkout, switch,
# restore, reset, branch, clean — every one of these can lose uncommitted work exactly the
# way a bare `git stash` already has, HRN-63 2026-09-01), acceptance for landing this card's
# own branch (merge, rebase, push), and the same generic pointer for anything this rule does
# not recognise at all. `npm install` is refused the same way in favour of `npm ci`, as its
# own separate check inside this rule. Judged only for role "executor" — every other role
# passes through untouched, since none of them carries a card whose own working copy this
# rule could even resolve a scope from.
#
# SCOPE: only a git call that actually targets one of THIS project's own repositories — the
# shared checkout every Bash call's own cwd is reset to, or one of its own linked working
# copies (…-hrnNN) — is judged at all. A bare `git …` (no `-C`) always targets cwd, which is
# always the shared checkout, so it is always in scope; a `git -C <path> …` is judged only
# when <path> resolves inside one of the paths `git worktree list --porcelain` reports for
# that same repository. This is deliberate and load-bearing, not an incidental gap: this
# card's own fix lives in the separate ~/Dev/ai configuration repository (ai/harness/system/
# project.md, "правка живёт в файле hooks/work-gate.sh репозитория конфигурации"), committed
# there by a direct `git -C /Users/tknff/Dev/ai commit …`, by the same executor this very
# rule governs — a rule that refused that call would refuse its own fix's own delivery.
GIT_PRE_SUBCOMMAND_VALUE_OPTS_6B = GIT_PRE_SUBCOMMAND_VALUE_OPTS  # same two options, same skip

def git_subcommand_and_arg(command):
    """(subcommand, the token right after it) of a `git …` invocation, walking past the same
    pre-subcommand options git_subcommand() above already walks past. The second element is
    used only to tell `git worktree list` apart from `git worktree add`/`remove`/… — None
    when there is no further token. (None, None) when `command` is not a git invocation."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None, None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GIT_PRE_SUBCOMMAND_VALUE_OPTS_6B:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token, (tokens[i + 1] if i + 1 < len(tokens) else None)
    return None, None

def git_dash_c_path(command):
    """The path argument of this `git …` invocation's own `-C <path>` option, or None when
    it carries none — used only to resolve which repository a git call actually targets."""
    tokens = command.split()
    if not tokens or tokens[0] != "git":
        return None
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token == "-C":
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if token == "-c":
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return None
    return None

def command_head_before_heredoc(command):
    """The part of `command` that actually runs — everything up to the start of a heredoc
    operator (`<<marker`, `<<-marker`, `<<'marker'`, `<<"marker"`), or the whole command when
    it carries none. A heredoc's own BODY is never scanned by this rule: it is stdin content,
    most often a check's own verbatim output pasted into a bin/work-note call, and a line
    inside it that happens to read "git status" or "$ git commit -m x" as PROSE must never be
    mistaken for a real invocation — found while writing this very rule's own card, HRN-70,
    whose own log entries quote exactly that kind of line."""
    m = re.search(r'<<-?\s*([\'"]?)(\w+)\1', command)
    return command[:m.start()] if m else command

def git_statements(command):
    """Every top-level statement of `command`'s own head (command_head_before_heredoc above)
    — split on `&&`, `;`, `|` or a newline outside any quoted span, the same quote-aware rule
    chains() already uses to decide whether a command chains at all, kept position-aligned
    with the original text (padded, not stripped) so the split points land in the same place
    in both strings."""
    head = command_head_before_heredoc(command)
    blanked = QUOTED_SPAN_RE.sub(lambda m: "x" * len(m.group(0)), head)
    parts, last = [], 0
    for m in CHAINING_RE.finditer(blanked):
        parts.append(head[last:m.start()])
        last = m.end()
    parts.append(head[last:])
    return [p.strip() for p in parts if p.strip()]

def project_worktree_roots():
    """Every worktree path `git worktree list --porcelain` reports for the repository
    reachable from this hook's own default working directory — the shared checkout every
    Bash call's own cwd is always reset to — covering both that shared checkout itself and
    every card's own linked working copy cut alongside it. None on any failure to run git at
    all, in which case a `-C <path>` git call is treated as unresolvable and not judged, the
    same fail-open posture every other rule in this file already takes on a reading error of
    its own."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    roots = [line[len("worktree "):].strip()
             for line in result.stdout.splitlines() if line.startswith("worktree ")]
    return roots or None

def path_is_in_project(path, roots):
    if not path or not roots:
        return False
    try:
        real = os.path.realpath(path)
    except Exception:
        return False
    for root in roots:
        real_root = os.path.realpath(root)
        if real == real_root or real.startswith(real_root + os.sep):
            return True
    return False

GIT_READ_ONLY_SUBCOMMANDS = {"status", "diff", "log", "show", "rev-parse", "ls-files"}
GIT_COMMAND_SAVE_SUBCOMMANDS = {"stash", "add", "commit", "checkout", "switch",
                                 "restore", "reset", "branch", "clean"}
GIT_COMMAND_LAND_SUBCOMMANDS = {"merge", "rebase", "push"}

GIT_COMMAND_SAVE_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` is not the executor's own way to "
    "save or discard work — call bin/work-commit <шаг> \"<итог>\" instead, which stages and "
    "commits everything this step changed through the project's own pre-commit checks, "
    "after recording the same step's own state with bin/work-note %s <шаг> \"<состояние>\". "
    "Reading commands stay open without limit: git status, diff, log, show, rev-parse, "
    "ls-files, worktree list."
)
GIT_COMMAND_LAND_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` lands or moves this card's own "
    "branch, and that is never the executor's own move — acceptance (bin/work-accept, run "
    "by the coordinator once the card's work is done) is what folds the branch in. Reading "
    "commands stay open without limit: git status, diff, log, show, rev-parse, ls-files, "
    "worktree list."
)
GIT_COMMAND_UNKNOWN_TEMPLATE = (
    "Blocked by work-gate's GIT COMMAND rule: `git %s` is not one of the reading commands an "
    "executor may run directly — status, diff, log, show, rev-parse, ls-files, worktree "
    "list. Save or discard work with bin/work-commit <шаг> \"<итог>\", record it with "
    "bin/work-note %s <шаг> \"<состояние>\", and leave landing the branch to acceptance."
)

def git_command_denial(subcommand_label, card_id):
    if subcommand_label in GIT_COMMAND_SAVE_SUBCOMMANDS:
        return GIT_COMMAND_SAVE_TEMPLATE % (subcommand_label, card_id)
    if subcommand_label in GIT_COMMAND_LAND_SUBCOMMANDS:
        return GIT_COMMAND_LAND_TEMPLATE % subcommand_label
    return GIT_COMMAND_UNKNOWN_TEMPLATE % (subcommand_label, card_id)

NPM_INSTALL_RE = re.compile(r'(?:^|[\s;&|])npm\s+install\b')

if brief.get("role") == "executor" and tool_name == "Bash":
    command = command_of(tool_input)
    head_blanked = QUOTED_SPAN_RE.sub(lambda m: "x" * len(m.group(0)),
                                       command_head_before_heredoc(command))
    if NPM_INSTALL_RE.search(head_blanked):
        deny_and_exit(
            "Blocked by work-gate's GIT COMMAND rule: `npm install` rewrites the lock file "
            "— call `npm ci` instead, which installs exactly what the lock file already "
            "records.",
            "work-gate.npm-install"
        )

    project_roots = None
    for statement in git_statements(command):
        subcommand, nxt = git_subcommand_and_arg(statement)
        if subcommand is None:
            continue
        dash_c = git_dash_c_path(statement)
        if dash_c is not None:
            if project_roots is None:
                project_roots = project_worktree_roots()
            if not path_is_in_project(dash_c, project_roots):
                continue  # a repository outside this project (e.g. ~/Dev/ai) — not judged
        if subcommand == "worktree":
            if nxt == "list":
                continue
            deny_and_exit(git_command_denial("worktree " + (nxt or ""), brief["card"]),
                          "work-gate.git-command")
        if subcommand in GIT_READ_ONLY_SUBCOMMANDS:
            continue
        deny_and_exit(git_command_denial(subcommand, brief["card"]), "work-gate.git-command")

# --- 7. LOG-WRITE CEILING (HRN-2.B, extended by HRN-21.B): twenty calls without a log.md
# write ------------------------------------------------------------------------------------
# ai/harness/system/project.md, "Двадцать вызовов без записи в log.md": applies only to the
# executor, and only once card_dir is known (fail open otherwise, same reasoning as rule 6 —
# without a resolved log.md path this rule could never recognise the one write meant to
# reset it, and would end up denying that write itself). agent_id is guaranteed present here
# — rule 3 above already exited for any call carrying none, so every call that reaches this
# point is a real subagent's own. The count lives in its own state file, one per agent_id,
# keyed the same way the brief files already are; a call denied by an earlier rule (no-brief,
# phase boundary, file authorship) never reaches here and so neither increments
# nor resets it.
#
# HRN-21.B: the system requires the executor to write log.md only through `bin/work-note`,
# never by hand (ai/harness/system/project.md, "log.md — пишет исполнитель"), and that
# command runs through Bash — so a bare Bash call naming it is exempted: a closed, literal
# match on the script's own basename appearing anywhere in the command line, never a
# chain-aware parse. Exempting it is not enough on its own — a call that merely passes the
# ceiling but still counts toward it would still eventually starve the executor of the one
# command it needs — so this same call also resets the counter to zero, exactly like a
# direct Write/Edit of log.md, because a `bin/work-note` invocation IS that write, only
# spelled through a command rather than through the tool directly.
LOG_CALL_CEILING = 20

def log_call_count_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    return os.path.join(STATE_DIR, "log-call-counts", "agent-" + safe + ".txt")

def read_log_call_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0

def write_log_call_count(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n))

if brief.get("role") == "executor" and card_dir is not None:
    fp = file_path_of(tool_input)
    is_this_cards_log_write_now = (
        tool_name in ("Write", "Edit") and fp is not None and
        os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md"))
    )
    log_command = command_of(tool_input)
    is_work_log_call = tool_name == "Bash" and (
        bash_names(log_command, "work-log") or
        bash_names(log_command, "work-note"))
    # A --handoff call passes this ceiling but resets nothing: it records that the run is
    # stopping, not that a step closed. Only a step-naming bin/work-note call — or a direct
    # Write/Edit of log.md — says the run actually moved, and only that resets the count.
    is_handoff_call = is_work_log_call and "--handoff" in (log_command or "")
    # HRN-76: bin/work-commit passes on the same terms, resetting nothing. Without this a
    # run that hit the ceiling with uncommitted code was stuck for good: --handoff refuses
    # on a dirty working copy and names bin/work-commit as the way out, and this ceiling
    # refused that command in turn.
    is_work_commit_call = tool_name == "Bash" and bash_names(log_command or "", "work-commit")
    count_path = log_call_count_path(agent_id)
    if is_this_cards_log_write_now or (is_work_log_call and not is_handoff_call):
        write_log_call_count(count_path, 0)
    elif is_handoff_call or is_work_commit_call:
        pass
    else:
        n = read_log_call_count(count_path) + 1
        write_log_call_count(count_path, n)
        if n >= LOG_CALL_CEILING:
            deny_and_exit(
                "Blocked by work-gate's LOG CEILING rule: %d calls have passed since this "
                "executor last closed a step in this card's own log.md. Two calls still get "
                "through. A Write/Edit of log.md, or a Bash call running bin/work-note with "
                "a step name, records a closed step and resets this count to zero — write "
                "one and go straight on with the work. A bin/work-note --handoff call also "
                "gets through but resets nothing: it says the run is stopping, not that work "
                "was done, so after writing one, end the run. «Закрой шаг записью в лог и "
                "работай дальше — или запиши передачу и остановись.»" % n,
                "work-gate.log-ceiling"
            )

# --- shared by rules 8-11 below: "is this call a Write/Edit of THIS run's own card's
# log.md" — the same test rules 5 and 7 above each already define locally for their own
# narrower scopes, repeated here as its own top-level helper rather than factored out of
# that already-built code, since this phase's own brief is to add HRN-2.C's five steps and
# nothing beyond them. -------------------------------------------------------------------
def is_this_cards_log_write_call():
    fp = file_path_of(tool_input)
    return (tool_name in ("Write", "Edit") and fp is not None and card_dir is not None and
            os.path.realpath(fp) == os.path.realpath(os.path.join(card_dir, "log.md")))

# --- shared by rules 8-10: one walk of this run's own transcript ----------------------
def transcript_line_records(path):
    """Yield each JSON object from a transcript file, one per line, skipping a blank or
    unparseable one — the same tolerant walk bin/agent-spend's own measure()/load_calls()
    already use for the identical file format (a Claude Code session transcript), repeated
    here rather than imported: this hook has no import path to bin/, which lives in a
    different repository."""
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record

def run_transcript_stats(path):
    """One walk of this run's own transcript, answering everything rules 8-10 below need:
    last_context — the context size the agent's own MOST RECENT turn actually held
    (input_tokens + cache_creation_input_tokens + cache_read_input_tokens of the last
    assistant record alone, never summed across the run — rule 8's own number); spend —
    the run's cumulative spend so far (cache_read_input_tokens + output_tokens, summed
    across every assistant record — the same definition bin/agent-spend's own emit_spend()
    already uses for a card's `spend:` field, reused here rather than invented fresh —
    rule 9's own number); calls — the number of tool calls the run has made (one per
    tool_use content block, the same count bin/agent-spend's own measure() already uses —
    rule 10's own denominator). None when path is missing, unreadable, or carries not one
    assistant record with a usage field at all — rules 8-10 then have nothing to judge and
    skip rather than deny, the same fail-open choice every earlier rule in this file
    already makes for a missing or unreadable input."""
    if not path:
        return None
    last_context = None
    spend = 0
    calls = 0
    seen_usage = False
    for record in transcript_line_records(path):
        if record.get("type") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        if usage:
            seen_usage = True
        u_input = usage.get("input_tokens", 0) or 0
        u_cwrite = usage.get("cache_creation_input_tokens", 0) or 0
        u_cread = usage.get("cache_read_input_tokens", 0) or 0
        u_output = usage.get("output_tokens", 0) or 0
        last_context = u_input + u_cwrite + u_cread
        spend += u_cread + u_output
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls += 1
    if not seen_usage:
        return None
    return {"last_context": last_context, "spend": spend, "calls": calls}

# --- WHICH TRANSCRIPT RULES 8-10 JUDGE (2026-08-31) ------------------------------------
# The payload's own `transcript_path` names the SESSION's transcript and never a subagent's
# own: a subagent's turns are written to `<...>/tasks/<agent_id>.output` instead. Reading
# that field for a subagent call therefore measured the coordinator's own run, and all
# three of the ceilings below — context size, spend, pace — judged the wrong numbers and
# never fired once for any subagent. Measured on HRN-59's own executor, 2026-08-31: its
# last turn held 385,246 tokens of context, 59 of its turns sat above the 300,000 ceiling,
# no refusal was ever issued, while the coordinator's own transcript peaked at 202,592 and
# so passed every check. The rules themselves were sound — fed that executor's real
# transcript by hand, rule 8 refused exactly as written.
#
# So a call carrying an agent_id resolves that agent's own transcript, by the same two
# globs bin/agent-spend's own TRANSCRIPT_GLOBS already use (the durable per-session file
# first, the temporary subagent mirror second). Not finding it leaves these rules nothing
# to judge and they skip — the same fail-open choice they already make for an unreadable
# transcript — rather than falling back to the payload's path, since measuring the wrong
# run is exactly the defect this replaces. A call carrying no agent_id is the session's
# own, and there the payload's path names the right file.
AGENT_TRANSCRIPT_GLOBS = [
    os.path.expanduser("~/.claude/projects/*/%s.jsonl"),
    "/private/tmp/claude-*/*/*/tasks/%s.output",
]

def agent_transcript_path(aid):
    """The newest transcript file on disk for one agent id, or None when there is none."""
    if not aid or not re.fullmatch(r'[A-Za-z0-9_-]+', str(aid)):
        return None
    for pattern in AGENT_TRANSCRIPT_GLOBS:
        hits = glob.glob(pattern % aid)
        if not hits:
            continue
        try:
            return max(hits, key=os.path.getmtime)
        except OSError:
            return hits[0]
    return None

if agent_id:
    transcript_path = agent_transcript_path(agent_id)
else:
    transcript_path = data.get("transcript_path")
run_stats = run_transcript_stats(transcript_path)

# --- 8. CONTEXT SIZE CEILING (HRN-2.C): every role -------------------------------------
CONTEXT_SIZE_CEILING = 300_000

if run_stats is not None and run_stats["last_context"] is not None and \
        run_stats["last_context"] > CONTEXT_SIZE_CEILING:
    if is_this_cards_log_write_call():
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's CONTEXT SIZE rule: this agent's own most recent turn held "
        "%d tokens of context, past the %d ceiling. «Запиши состояние в лог и остановись.» "
        "A fresh executor picks the card up from there with an empty context. The only "
        "call that still gets through is a Write/Edit of this card's own log.md." %
        (run_stats["last_context"], CONTEXT_SIZE_CEILING),
        "work-gate.context-size"
    )

# --- 9. SPEND CEILING (HRN-2.C): role "executor" only, counted on this run's own
# transcript alone, never accumulated across the card ------------------------------------
SPEND_CEILING = 90_000_000

if brief.get("role") == "executor" and run_stats is not None and \
        run_stats["spend"] > SPEND_CEILING:
    if is_this_cards_log_write_call():
        allow_and_exit()
    deny_and_exit(
        "Blocked by work-gate's SPEND CEILING rule: this executor's own run has spent %d "
        "tokens (cache-read plus output, summed from its own transcript), past the %d "
        "ceiling counted for this run alone, never accumulated across the whole card — a "
        "fresh executor's own transcript starts this same count at zero. «Запиши "
        "состояние в лог и остановись.» The only call that still gets through is a "
        "Write/Edit of this card's own log.md." % (run_stats["spend"], SPEND_CEILING),
        "work-gate.spend-ceiling"
    )

# --- 10. PACE CEILING (HRN-2.C): role "executor" only, tokens spent per tool call this
# run has made, threshold read from a machine file, not checked before call 120 ----------
PACE_CALL_ALLOWANCE = 120

def pace_threshold_file():
    return os.environ.get("WORK_GATE_PACE_THRESHOLD_FILE") or \
        os.path.join(os.path.dirname(self_path), "work-gate-pace-threshold.txt")

def read_pace_threshold():
    try:
        with open(pace_threshold_file(), "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None

if brief.get("role") == "executor":
    pace_threshold = read_pace_threshold()
    if pace_threshold is None:
        if is_this_cards_log_write_call():
            allow_and_exit()
        deny_and_exit(
            "Blocked by work-gate's PACE rule: no number was found at %s — the pace "
            "threshold this rule judges every call against must live there as a bare "
            "integer, and its absence refuses every call for this executor rather than "
            "silently skipping the check. The only call that still gets through is a "
            "Write/Edit of this card's own log.md." % pace_threshold_file(),
            "work-gate.pace-threshold-missing"
        )
    elif run_stats is not None and run_stats["calls"] > PACE_CALL_ALLOWANCE:
        pace = run_stats["spend"] / run_stats["calls"]
        if pace > pace_threshold:
            if is_this_cards_log_write_call():
                allow_and_exit()
            deny_and_exit(
                "Blocked by work-gate's PACE rule: this run has spent %.0f tokens per "
                "tool call (%d tokens over %d calls), past the %d threshold read from %s. "
                "«Запиши состояние в лог и остановись.» The only call that still gets "
                "through is a Write/Edit of this card's own log.md." %
                (pace, run_stats["spend"], run_stats["calls"], pace_threshold,
                 pace_threshold_file()),
                "work-gate.pace-ceiling"
            )

# --- 11. FILE-EDIT BRAKE (HRN-2.C): the Nth Edit/Write of one file inside one run -------
FILE_EDIT_BRAKE_THRESHOLD = 9

def file_edit_count_path(aid, real_fp):
    safe_agent = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    safe_file = re.sub(r'[^A-Za-z0-9_-]', '_', real_fp)
    return os.path.join(STATE_DIR, "file-edit-counts", "agent-" + safe_agent,
                         safe_file + ".txt")

def read_file_edit_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0

def write_file_edit_count(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n))

def file_created_marker_path(aid, real_fp):
    return file_edit_count_path(aid, real_fp) + ".created"

def mark_file_created_this_run(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("1")

if tool_name in ("Write", "Edit"):
    fp = file_path_of(tool_input)
    if fp is not None:
        real_fp = os.path.realpath(fp)
        is_card_file = card_dir is not None and \
            os.path.dirname(real_fp) == os.path.realpath(card_dir)
        # HRN-21.C.1: a Write that brings a file into existence — one that does not yet
        # exist on disk at the moment this hook runs, before the tool call itself executes
        # — is a creation, not a "правка" (edit) of anything, and is never counted at all.
        # Checked fresh against the filesystem on every call, never remembered as a flag of
        # its own: the next Write/Edit of this same path finds the file now on disk (this
        # call's own effect, once it actually runs) and counts normally from there.
        is_fresh_creation = tool_name == "Write" and not os.path.exists(real_fp)
        # The brake exists to catch an agent hammering code that was already on disk when
        # its run began. A file this same run brought into existence is not that: an agent
        # authoring a new script honestly edits it a dozen times, and refusing that stops
        # real work while catching nothing. So the creation lays down a marker for this
        # (run, path) pair, and every later Write/Edit of that path inside the same run is
        # left uncounted. The run stays bounded either way — the spend, context and pace
        # ceilings all still apply to it.
        created_marker = file_created_marker_path(agent_id, real_fp)
        if is_fresh_creation:
            mark_file_created_this_run(created_marker)
        was_created_this_run = os.path.exists(created_marker)
        if not is_card_file and not is_fresh_creation and not was_created_this_run:
            count_path = file_edit_count_path(agent_id, real_fp)
            n = read_file_edit_count(count_path) + 1
            write_file_edit_count(count_path, n)
            if n >= FILE_EDIT_BRAKE_THRESHOLD:
                # Past the threshold the brake stops point edits, never the file's remaining
                # work: a whole-file Write is the way through, and it is allowed here.
                if tool_name == "Write":
                    allow_and_exit()
                deny_and_exit(
                    "Blocked by work-gate's FILE-EDIT BRAKE rule: this run has now touched "
                    "%s %d times, past the %d threshold, so point edits of this file are "
                    "refused from here on. This is not a ban on finishing the file. The way "
                    "through is one whole-file rewrite: read the file, work out every "
                    "remaining change at once, and write the complete new content back in a "
                    "single Write call of this same path — a Write is allowed past the "
                    "threshold, an Edit is not. If the remaining work is too large to hold in "
                    "one rewrite, record the state with bin/work-note and hand the rest to a "
                    "fresh run. This count is per file path and per run; it never counts a "
                    "write to one of this card's own files, and a Bash call re-running the "
                    "same command however many times is never limited at all." %
                    (fp, n, FILE_EDIT_BRAKE_THRESHOLD),
                    "work-gate.file-edit-brake"
                )

# --- 13. COMMAND REFERENCE ON THE FIRST SAVE-SHAPED CALL (owner's word, 2026-08-31) ----
# The brief carries the command reference, and a run that needs it does so long after it
# read the brief — HRN-59's own executor spent twelve refused calls guessing a form its
# brief had already given it forty turns earlier. A skill cannot fix that: the model chooses
# a skill by reading its description, which is the same memory that just failed. This hook
# is the only thing that fires without asking the model anything, so it is what carries the
# reference back to the moment of need.
#
# Never refuses, and never fires twice in one run: the first Bash call this run makes that
# looks like saving work — bin/work-note, bin/work-commit, `git add`, `git commit` — is
# allowed with the reference attached to it, and a marker for that run means every later
# call goes through silently. The text is not written here: it is sliced out of the one
# template the brief itself is built from, so the two can never drift apart. Every failure
# along the way (no template, no card, an unreadable file) falls through to a plain allow.
REFERENCE_MARKER_DIR = os.path.join(STATE_DIR, "reference-shown")

def reference_marker_path(aid):
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid)) if aid else "_no_agent_"
    return os.path.join(REFERENCE_MARKER_DIR, "agent-" + safe + ".txt")

def looks_like_save_call(command):
    """True for the shapes an executor saves finished work with — the two commands of this
    system, and the two bare git subcommands the phase boundary already exempts."""
    if re.search(r'(^|\s)(\S*/)?bin/work-(note|commit)\b', command):
        return True
    return git_subcommand(command) in PHASE_BOUNDARY_SAVE_GIT_SUBCOMMANDS

def command_reference_text(card_id, phase, card_dir_path):
    """The brief's own command reference, read out of bin/templates/executor-brief.md —
    from its 'Справочник команд:' heading up to the standing-behaviour heading that follows
    it — with the same three placeholders the brief itself fills. None when anything at all
    cannot be resolved, so this rule can only ever add text to an allow, never withhold
    one."""
    if not work_root or not card_id:
        return None
    template = os.path.join(os.path.dirname(work_root.rstrip("/")), "bin", "templates",
                            "executor-brief.md")
    try:
        with open(template, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    start = text.find("Справочник команд:")
    if start < 0:
        return None
    end = text.find("Постоянное поведение исполнителя", start)
    section = text[start:end] if end > start else text[start:]
    section = section.replace("{{CARD_ID}}", card_id)
    section = section.replace("{{PHASE}}", phase or "<фаза>")
    section = section.replace("{{CARD_DIR}}", card_dir_path or "<папка карточки>")
    return section.strip()

if brief.get("role") == "executor" and tool_name == "Bash":
    marker = reference_marker_path(agent_id)
    if not os.path.exists(marker) and looks_like_save_call(command_of(tool_input)):
        reference = command_reference_text(brief.get("card"), brief.get("phase"), card_dir)
        if reference is not None:
            try:
                os.makedirs(os.path.dirname(marker), exist_ok=True)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write("shown\n")
            except OSError:
                pass
            allow_and_exit(
                "Справочник команд этой системы, приложен один раз за прогон, к первому "
                "вызову, похожему на сохранение работы. Он же стоит в начале твоего "
                "брифа.\n\n" + reference
            )

# --- 14. REPEATED SEARCH → THE MAP (owner's word, 2026-09-01) --------------------------
# Measured on HRN-63.C: six consecutive greps of one 765-line file, and ten reads plus eight
# edits of another. Searching one file over and over is how a run rediscovers, one match at
# a time, what the card's own map.md already states outright — and that map was read once, at
# the very start of the run, a hundred thousand tokens before the moment it was needed. So
# the second search of one file hands the map back at the moment of need, and the third and
# every later one is refused. No work is taken away, only the method: a whole-file Read of
# that same path is never refused by this rule, and it zeroes the count, so an honest read
# followed by a targeted search starts from nothing again. Executor only — a reading role's
# whole job is searching, and it carries no map of its own to be handed.
SEARCH_REPEAT_MAP_AT = 2      # this search is allowed, with the map attached to it
SEARCH_REPEAT_DENY_AT = 3     # this search, and every later one, is refused

SEARCH_TOOL_RE = re.compile(r'(^|[|;&]\s*)(\S*/)?(grep|egrep|fgrep|rg|ag|ack|awk|sed)\b')

def search_count_path(aid, real_fp):
    safe_agent = re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))
    safe_file = re.sub(r'[^A-Za-z0-9_-]', '_', real_fp)
    return os.path.join(STATE_DIR, "search-counts", "agent-" + safe_agent,
                        safe_file + ".txt")

def searched_files(tname, ti):
    """Every existing regular file this one call searches inside. A Grep call names its path
    outright. A Bash call is read by taking every token of a grep/rg/sed/awk command line and
    keeping the ones that turn out to be real files on disk — which drops flags, patterns and
    directories without having to parse a shell command properly. A directory-wide search is
    therefore never counted at all: this rule is about pecking at one known file."""
    raw = []
    if tname == "Grep":
        p = ti.get("path")
        if isinstance(p, str) and p:
            raw.append(p)
    elif tname == "Bash":
        cmd = command_of(ti)
        if SEARCH_TOOL_RE.search(cmd):
            raw = re.findall(r'[^\s\'"|;&<>()]+', cmd)
    out = []
    for t in raw:
        try:
            rp = os.path.realpath(t)
        except (OSError, ValueError):
            continue
        if os.path.isfile(rp) and rp not in out:
            out.append(rp)
    return out

def map_material(real_fp):
    """What the run is handed instead of another search: how long the file actually is, and
    what the card's own map.md already says about it — the paragraphs naming that file when
    there are any, the whole map otherwise. A card with no map still gets the line count and
    the advice, so this never withholds the answer, only shortens it."""
    try:
        with open(real_fp, "r", encoding="utf-8", errors="replace") as f:
            line_count = sum(1 for _ in f)
    except OSError:
        line_count = None
    text = None
    if card_dir:
        try:
            with open(os.path.join(card_dir, "map.md"), "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = None
    excerpt = None
    if text and text.strip():
        base = os.path.basename(real_fp)
        paragraphs = [p for p in re.split(r'\n\s*\n', text) if base in p]
        excerpt = "\n\n".join(paragraphs).strip() if paragraphs else text.strip()
        if len(excerpt) > 3000:
            excerpt = excerpt[:3000] + "\n…"
    return line_count, excerpt

def search_advice(line_count, excerpt):
    length = ("%d строк" % line_count) if line_count is not None else "неизвестной длины"
    body = ("Read этого файла не ограничен ничем, читает его целиком (%s) и обнуляет этот "
            "счёт, после чего поиск снова разрешён." % length)
    if excerpt:
        return body + "\n\nЧто про этот файл уже написано в map.md карточки:\n\n" + excerpt
    return body + "\n\nmap.md карточки про этот файл ничего не говорит — тем более читай сам файл."

if brief.get("role") == "executor":
    # A whole-file Read — no offset, no limit — is the thing this rule wants to happen, so it
    # wipes the count for that path rather than merely passing.
    if tool_name == "Read" and tool_input.get("offset") is None and \
            tool_input.get("limit") is None:
        read_fp = file_path_of(tool_input)
        if read_fp:
            try:
                stale = search_count_path(agent_id, os.path.realpath(read_fp))
                if os.path.exists(stale):
                    os.remove(stale)
            except OSError:
                pass
    # Counted with the same two integer helpers rule 11 counts edits with, over their own
    # directory. Every file this one call searches is counted before any of them is judged,
    # so a command naming two files leaves neither count behind.
    searched = []
    for searched_fp in searched_files(tool_name, tool_input):
        search_path = search_count_path(agent_id, searched_fp)
        searched.append((read_file_edit_count(search_path) + 1, searched_fp))
        write_file_edit_count(search_path, searched[-1][0])
    for n, searched_fp in searched:
        if n >= SEARCH_REPEAT_DENY_AT:
            line_count, excerpt = map_material(searched_fp)
            deny_and_exit(
                "Blocked by work-gate's REPEATED SEARCH rule: поиск по %s в этом прогоне "
                "уже %d-й, и он отказан. Работа не отнята, отнят способ. %s" %
                (searched_fp, n, search_advice(line_count, excerpt)),
                "work-gate.repeated-search"
            )
    for n, searched_fp in searched:
        if n >= SEARCH_REPEAT_MAP_AT:
            line_count, excerpt = map_material(searched_fp)
            allow_and_exit(
                "Ты ищешь в %s второй раз за прогон. Следующий поиск по этому файлу будет "
                "отказан. %s" % (searched_fp, search_advice(line_count, excerpt))
            )

allow_and_exit()
PYEOF
