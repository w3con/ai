#!/usr/bin/env bash
# Status line: model | ctx+tokens | rate limits | dir/branch
input=$(cat)

cwd=$(echo "$input" | jq -r '.cwd // .workspace.current_dir // empty')
[ -z "$cwd" ] && cwd="$(pwd)"
dir=$(basename "$cwd")

git_branch=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  git_branch=$(git -C "$cwd" -c core.fsmonitor=false symbolic-ref --short HEAD 2>/dev/null \
               || git -C "$cwd" -c core.fsmonitor=false rev-parse --short HEAD 2>/dev/null)
fi

model=$(echo "$input"      | jq -r '.model.display_name // empty')
ctx_pct=$(echo "$input"    | jq -r '.context_window.used_percentage // empty')
ctx_tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')
cost_usd=$(echo "$input"   | jq -r '.cost.total_cost_usd // empty')
thinking=$(echo "$input"   | jq -r '.thinking.enabled // false')
fh_pct=$(echo "$input"     | jq -r '.rate_limits.five_hour.used_percentage // empty')
fh_reset=$(echo "$input"   | jq -r '.rate_limits.five_hour.resets_at       // empty')
sd_pct=$(echo "$input"     | jq -r '.rate_limits.seven_day.used_percentage // empty')
sd_reset=$(echo "$input"   | jq -r '.rate_limits.seven_day.resets_at       // empty')

DIM=$'\033[90m'
RESET=$'\033[0m'
WHITE=$'\033[37m'

pct_color() {
  local n=$(printf '%.0f' "${1:-0}")
  if   [ "$n" -ge 80 ]; then printf $'\033[35m'
  elif [ "$n" -ge 60 ]; then printf $'\033[31m'
  elif [ "$n" -ge 40 ]; then printf $'\033[38;5;208m'
  elif [ "$n" -ge 20 ]; then printf $'\033[33m'
  else printf $'\033[90m'
  fi
}

vis_len() {
  local stripped
  stripped=$(printf '%s' "$1" | sed $'s/\033\[[0-9;]*m//g')
  local chars wide
  chars=$(printf '%s' "$stripped" | wc -m | tr -d ' \t\n')
  wide=$(printf '%s' "$stripped" | grep -o '⌚' | wc -l | tr -d ' \t\n')
  echo $(( chars + wide ))
}

# ── S1: model (color by tier) + thinking indicator ────────────────────────────
case "$model" in
  *Haiku*)  model_col=$'\033[90m'         ;;
  *Opus*)   model_col=$'\033[38;5;135m'   ;;
  *)        model_col="${WHITE}"           ;;
esac
s1="${model_col}${model}${RESET}"
[ "$thinking" = "true" ] && s1+=" ${DIM}⚡${RESET}"

# ── S2: context (current session) ─────────────────────────────────────────────
s2=""
if [ -n "$ctx_pct" ]; then
  col=$(pct_color "$ctx_pct")
  s2+="${col}ctx:$(printf '%.0f' "$ctx_pct")%${RESET}"
  if [ -n "$ctx_tokens" ] && [ "$ctx_tokens" != "null" ]; then
    tok_k=$(echo "$ctx_tokens" | awk '{printf "%.0fk", $1/1000}')
    s2+=" ${DIM}(${tok_k})${RESET}"
  fi
fi
if [ -n "$cost_usd" ] && [ "$cost_usd" != "null" ] && [ "$cost_usd" != "0" ]; then
  cost_fmt=$(echo "$cost_usd" | awk '{printf "$%.2f", $1}')
  s2+=" ${DIM}${cost_fmt}${RESET}"
fi

# ── S3: rate limits ────────────────────────────────────────────────────────────
s3=""
if [ -n "$fh_pct" ]; then
  col=$(pct_color "$fh_pct")
  s3+="${col}5h:$(printf '%.0f' "$fh_pct")%${RESET}"
  if [ -n "$fh_reset" ]; then
    rt=$(date -r "$fh_reset" '+%H:%M' 2>/dev/null || date -d "@$fh_reset" '+%H:%M' 2>/dev/null)
    s3+=" ${DIM}⌚${rt}${RESET}"
  fi
fi
if [ -n "$sd_pct" ]; then
  col=$(pct_color "$sd_pct")
  [ -n "$s3" ] && s3+="  "
  s3+="${col}7d:$(printf '%.0f' "$sd_pct")%${RESET}"
  if [ -n "$sd_reset" ]; then
    rl=$(date -r "$sd_reset" '+%a %H:%M' 2>/dev/null || date -d "@$sd_reset" '+%a %H:%M' 2>/dev/null)
    s3+=" ${DIM}⌚${rl}${RESET}"
  fi
fi

# ── S4: dir + branch (color = git state) ─────────────────────────────────────
s4="${WHITE}${dir}${RESET}"
if [ -n "$git_branch" ]; then
  dirty=$(git -C "$cwd" status --porcelain 2>/dev/null)
  unpushed=$(git -C "$cwd" log '@{u}..HEAD' --oneline 2>/dev/null)
  if [ -n "$dirty" ] && [ -n "$unpushed" ]; then
    branch_col=$'\033[31m'       # red: uncommitted + unpushed
  elif [ -n "$unpushed" ]; then
    branch_col=$'\033[32m'       # green: clean but unpushed commits
  elif [ -n "$dirty" ]; then
    branch_col=$'\033[33m'       # yellow: uncommitted changes
  else
    branch_col="${DIM}"          # gray: all clean
  fi
  s4+=" ${branch_col}$(printf '\xef\xb1\x8b') ${git_branch}${RESET}"
fi

# ── Layout: evenly spaced at 0%, 33%, 66%, 100% ───────────────────────────────
width=$(( $(tput cols 2>/dev/null || echo 120) - 4 ))

l1=$(vis_len "$s1")
l2=$(vis_len "$s2")
l3=$(vis_len "$s3")
l4=$(vis_len "$s4")

# Target anchor positions (left edge of each section)
a1=0
a2=$(( width / 3 - l2 / 2 ))
a3=$(( width * 2 / 3 - l3 / 2 ))
a4=$(( width - l4 ))

# Ensure no overlaps
[ "$a2" -lt $(( a1 + l1 + 2 )) ] && a2=$(( a1 + l1 + 2 ))
[ "$a3" -lt $(( a2 + l2 + 2 )) ] && a3=$(( a2 + l2 + 2 ))
[ "$a4" -lt $(( a3 + l3 + 2 )) ] && a4=$(( a3 + l3 + 2 ))

printf '%s' "$s1"
printf '%*s' $(( a2 - a1 - l1 )) ""
printf '%s' "$s2"
printf '%*s' $(( a3 - a2 - l2 )) ""
printf '%s' "$s3"
printf '%*s' $(( a4 - a3 - l3 )) ""
printf '%s' "$s4"
