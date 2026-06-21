#!/usr/bin/env bash
# Claude Code statusline
# Reads JSON from stdin (Claude Code statusLine protocol)

input=$(cat)

cwd=$(echo "$input"         | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input"       | jq -r '.model.display_name // empty')
git_worktree=$(echo "$input"| jq -r '.workspace.git_worktree // empty')
ctx_used=$(echo "$input"    | jq -r '.context_window.used_percentage // empty')
ctx_total=$(echo "$input"   | jq -r '.context_window.context_window_size // empty')
ctx_tokens=$(echo "$input"  | jq -r '.context_window.total_input_tokens // empty')
five_pct=$(echo "$input"    | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input"  | jq -r '.rate_limits.five_hour.resets_at // empty')
week_pct=$(echo "$input"    | jq -r '.rate_limits.seven_day.used_percentage // empty')
week_reset=$(echo "$input"  | jq -r '.rate_limits.seven_day.resets_at // empty')

# ── ANSI 256-color helpers ──────────────────────────────────────────────────
C_RESET='\e[0m'
C_SEP='\e[38;5;031m'          # cyan — path separators
C_PATH='\e[1;38;5;039m'       # bold blue — full path
C_GIT_BR='\e[38;5;070m'       # green — git branch
C_GIT_DIRTY='\e[38;5;220m'    # yellow — dirty marker
C_MODEL='\e[38;5;066m'        # muted teal — model name
C_CTX='\e[38;5;245m'          # gray — context size
C_CTX_HI='\e[38;5;208m'       # orange — context warning (>75%)
C_RATE='\e[38;5;133m'         # purple — rate limit
C_RATE_HI='\e[38;5;160m'      # red — rate limit warning (>75%)

# ── Full path (no shortening) ────────────────────────────────────────────────
full_path() {
  local path="$1"
  [[ -z "$path" ]] && return
  # Replace home dir with ~
  local home_dir
  home_dir=$(cd /Users/tknff && pwd)
  if [[ "$path" == "$home_dir"* ]]; then
    path="~${path#$home_dir}"
  fi
  # Colorize separators
  local colored
  colored=$(printf '%s' "$path" | sed "s|/|$(printf '%b' "${C_SEP}")/$(printf '%b' "${C_PATH}")|g")
  printf '%b%b%b' "${C_PATH}" "${colored}" "${C_RESET}"
}

# ── Git status ───────────────────────────────────────────────────────────────
git_status() {
  local dir="$1"
  [[ -z "$dir" ]] && return

  local branch
  branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null) || \
  branch=$(git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null) || return

  local dirty=''
  if ! git -C "$dir" --no-optional-locks diff --quiet 2>/dev/null || \
     ! git -C "$dir" --no-optional-locks diff --cached --quiet 2>/dev/null; then
    dirty=" ${C_GIT_DIRTY}*${C_RESET}"
  fi

  local label="$branch"
  [[ -n "$git_worktree" ]] && label="${label} [${git_worktree}]"

  printf ' %b%b%b%b' "${C_GIT_BR}" "${label}" "${C_RESET}" "${dirty}"
}

# ── Model ────────────────────────────────────────────────────────────────────
model_segment() {
  local m="$1"
  [[ -z "$m" ]] && return
  printf ' %b%b%b' "${C_MODEL}" "${m}" "${C_RESET}"
}

# ── Context window ───────────────────────────────────────────────────────────
context_segment() {
  [[ -z "$ctx_used" ]] && return
  local color="$C_CTX"
  # Warn when context is more than 75% used
  (( $(echo "$ctx_used > 75" | bc -l 2>/dev/null) )) && color="$C_CTX_HI"
  local label
  label=$(printf 'ctx:%.0f%%' "$ctx_used")
  # Append token count if available (in thousands)
  if [[ -n "$ctx_tokens" && "$ctx_tokens" -gt 0 ]]; then
    local ktok
    ktok=$(printf '%.0fk' "$(echo "scale=1; $ctx_tokens / 1000" | bc 2>/dev/null)")
    label="${label} ${ktok}"
  fi
  printf ' %b%b%b' "${color}" "${label}" "${C_RESET}"
}

# ── Rate limits ──────────────────────────────────────────────────────────────
rate_segment() {
  local out=''
  if [[ -n "$five_pct" ]]; then
    local c="$C_RATE"
    (( $(echo "$five_pct > 75" | bc -l 2>/dev/null) )) && c="$C_RATE_HI"
    local reset_label=''
    if [[ -n "$five_reset" ]]; then
      local hhmm
      hhmm=$(date -r "$five_reset" '+%H:%M' 2>/dev/null)
      [[ -n "$hhmm" ]] && reset_label=$(printf ' %b↺%s%b' "${C_CTX}" "$hhmm" "${C_RESET}")
    fi
    out+=$(printf ' %b5h:%.0f%%%b%s' "${c}" "$five_pct" "${C_RESET}" "$reset_label")
  fi
  if [[ -n "$week_pct" ]]; then
    local c="$C_RATE"
    (( $(echo "$week_pct > 75" | bc -l 2>/dev/null) )) && c="$C_RATE_HI"
    local week_countdown=''
    if [[ -n "$week_reset" ]]; then
      local now secs_left
      now=$(date +%s 2>/dev/null)
      secs_left=$(( week_reset - now ))
      if (( secs_left > 0 )); then
        local days hours mins
        days=$(( secs_left / 86400 ))
        hours=$(( (secs_left % 86400) / 3600 ))
        mins=$(( (secs_left % 3600) / 60 ))
        local fmt
        if (( days >= 1 )); then
          fmt=$(printf '%dd%dh' "$days" "$hours")
        else
          fmt=$(printf '%dh%dm' "$hours" "$mins")
        fi
        week_countdown=$(printf ' %b↻%s%b' "${C_CTX}" "$fmt" "${C_RESET}")
      fi
    fi
    out+=$(printf ' %b7d:%.0f%%%b%s' "${c}" "$week_pct" "${C_RESET}" "$week_countdown")
  fi
  [[ -n "$out" ]] && printf '%s' "$out"
}

# ── Assemble ─────────────────────────────────────────────────────────────────
path_part=$(full_path "$cwd")
git_part=$(git_status "$cwd")
model_part=$(model_segment "$model")
ctx_part=$(context_segment)
rate_part=$(rate_segment)

printf '%b%b%b%b%b\n' "$path_part" "$git_part" "$model_part" "$ctx_part" "$rate_part"
