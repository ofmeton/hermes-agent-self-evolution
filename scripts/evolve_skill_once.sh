#!/usr/bin/env bash
set -euo pipefail

SKILL="${1:?usage: scripts/evolve_skill_once.sh <skill> [iterations] [eval_source] [optimizer_model] [eval_model] [holdout_limit]}"
ITERATIONS="${2:-3}"
EVAL_SOURCE="${3:-synthetic}"
OPTIMIZER_MODEL="${4:-openai/gpt-5-mini}"
EVAL_MODEL="${5:-openai/gpt-5-nano}"
HOLDOUT_LIMIT="${6:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "ERROR: missing .venv. Run: /Users/rikukudo/.local/bin/uv venv --python 3.11 && /Users/rikukudo/.local/bin/uv pip install -e '.[dev]'" >&2
  exit 2
fi

load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0

  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    [[ "$line" == *=* ]] || continue

    key="${line%%=*}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

    # Do not overwrite an explicit environment variable from the caller.
    [[ -n "${!key+x}" ]] && continue

    value="${line#*=}"
    value="${value%$'\r'}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < "$env_file"
}

# Load local/project env first, then Hermes profile env. Existing exported
# values always win, so ad-hoc per-run overrides remain safe.
load_env_file "$ROOT/.env"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
load_env_file "$HERMES_HOME/.env"

# shellcheck source=/dev/null
source .venv/bin/activate

export HERMES_AGENT_REPO="${HERMES_AGENT_REPO:-/Users/rikukudo/.hermes/hermes-agent}"

ARGS=(
  --skill "$SKILL"
  --iterations "$ITERATIONS"
  --eval-source "$EVAL_SOURCE"
  --optimizer-model "$OPTIMIZER_MODEL"
  --eval-model "$EVAL_MODEL"
)

if [[ -n "$HOLDOUT_LIMIT" ]]; then
  ARGS+=(--holdout-limit "$HOLDOUT_LIMIT")
fi

python -m evolution.skills.evolve_skill "${ARGS[@]}"
