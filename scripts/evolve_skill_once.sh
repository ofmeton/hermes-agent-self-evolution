#!/usr/bin/env bash
set -euo pipefail

SKILL="${1:?usage: scripts/evolve_skill_once.sh <skill> [iterations] [eval_source] [optimizer_model] [eval_model]}"
ITERATIONS="${2:-3}"
EVAL_SOURCE="${3:-synthetic}"
OPTIMIZER_MODEL="${4:-openai/gpt-5-mini}"
EVAL_MODEL="${5:-openai/gpt-5-nano}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "ERROR: missing .venv. Run: /Users/rikukudo/.local/bin/uv venv --python 3.11 && /Users/rikukudo/.local/bin/uv pip install -e '.[dev]'" >&2
  exit 2
fi

# shellcheck source=/dev/null
source .venv/bin/activate

export HERMES_AGENT_REPO="${HERMES_AGENT_REPO:-/Users/rikukudo/.hermes/hermes-agent}"

python -m evolution.skills.evolve_skill \
  --skill "$SKILL" \
  --iterations "$ITERATIONS" \
  --eval-source "$EVAL_SOURCE" \
  --optimizer-model "$OPTIMIZER_MODEL" \
  --eval-model "$EVAL_MODEL"
