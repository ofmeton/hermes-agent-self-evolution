# Hermes GEPA Continuous Improvement Runbook

## Default mode

Report-only. Never apply evolved artifacts automatically.

## Manual pilot

```bash
cd /Users/rikukudo/Projects/hermes-agent-self-evolution
source .venv/bin/activate
export HERMES_AGENT_REPO=/Users/rikukudo/.hermes/hermes-agent

python -m evolution.skills.evolve_skill \
  --skill github-code-review \
  --eval-source synthetic
```

## Summarize latest run

```bash
python scripts/summarize_latest_run.py github-code-review
```

## Run report-only cycle

```bash
python scripts/run_report_only_cycle.py --skill github-code-review
```

## Decision rules

- `candidate`: review diff manually. Do not merge automatically.
- `review`: inspect if the skill is important; otherwise leave as audit data.
- `reject`: keep metrics only; do not apply.

## Review diff

```bash
diff -u \
  output/<skill>/<timestamp>/baseline_skill.md \
  output/<skill>/<timestamp>/evolved_skill.md
```

## Cost policy

Default run target is approximately <$0.25 for small skills. Any benchmark run, Opus/GPT-5.5 Pro run, or multi-skill run requires explicit approval.

## Cron policy

Cron may run report-only jobs. TUI sessions do not receive cron delivery. If live notifications are required, configure Telegram/gateway delivery explicitly.
