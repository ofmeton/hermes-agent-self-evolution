#!/usr/bin/env python3
"""Run one report-only Hermes GEPA improvement cycle."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from evolution.core.self_improvement import ExperimentStore


def select_target(config: dict[str, Any], skill: str | None = None) -> dict[str, Any]:
    targets = [t for t in config.get("targets", []) if t.get("enabled", False)]
    if skill:
        matches = [t for t in targets if t.get("skill") == skill]
        if not matches:
            raise ValueError(f"Skill is not enabled in config: {skill}")
        return matches[0]
    if not targets:
        raise ValueError("No enabled evolution targets")
    return sorted(targets, key=lambda t: int(t.get("priority", 0)), reverse=True)[0]


def report_path(root: Path, skill: str, date: str) -> Path:
    return root / "reports" / "evolution-runs" / date / skill / "summary.md"


def build_failed_variant_summary(root: Path, skill: str) -> str:
    failed_path = root / "output" / skill / "evolved_FAILED.md"
    if not failed_path.exists():
        raise FileNotFoundError(f"No completed run or failed variant for skill: {skill}")
    return f"""# Evolution Run Summary — {skill}

- Run dir: `output/{skill}`
- Status: **reject**
- Failed artifact: `{failed_path}`
- Reason: No completed `metrics.json` run directory was produced. The GEPA run saved an `evolved_FAILED.md` artifact instead.

## Next action

Do not apply this variant. Inspect the failed artifact only if debugging the evolution pipeline.
"""


def _load_summary_module(root: Path):
    summary_path = root / "scripts" / "summarize_latest_run.py"
    spec = importlib.util.spec_from_file_location("summarize_latest_run", summary_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_cycle(root: Path, skill: str | None = None, dry_run: bool = False) -> Path:
    config_path = root / "config" / "evolution_targets.yaml"
    config = yaml.safe_load(config_path.read_text())
    defaults = config.get("defaults", {})
    target = select_target(config, skill=skill)

    selected_skill = target["skill"]
    iterations = str(target.get("iterations", defaults.get("iterations", 3)))
    eval_source = str(target.get("eval_source", defaults.get("eval_source", "synthetic")))
    optimizer_model = str(target.get("optimizer_model", defaults.get("optimizer_model", "openai/gpt-5-mini")))
    eval_model = str(target.get("eval_model", defaults.get("eval_model", "openai/gpt-5-nano")))
    holdout_limit = target.get("holdout_limit", defaults.get("holdout_limit"))
    hermes_agent_repo = target.get("hermes_agent_repo", config.get("repo", {}).get("hermes_agent_repo"))

    command = [
        str(root / "scripts" / "evolve_skill_once.sh"),
        selected_skill,
        iterations,
        eval_source,
        optimizer_model,
        eval_model,
    ]
    if holdout_limit:
        command.append(str(holdout_limit))

    env = os.environ.copy()
    if hermes_agent_repo:
        env["HERMES_AGENT_REPO"] = str(hermes_agent_repo)

    if not dry_run:
        subprocess.run(command, cwd=root, env=env, check=True)

    summary_module = _load_summary_module(root)
    experiment_section = ""
    try:
        run_dir = summary_module.find_latest_run(root, selected_skill)
        markdown = summary_module.build_summary(run_dir, thresholds=defaults)["markdown"]
        try:
            experiment = ExperimentStore(root / "output").import_legacy_run(run_dir)
            experiment_section = (
                "\n## Self-improvement Loop v0\n\n"
                f"- Experiment: `{experiment.id}`\n"
                f"- Experiment dir: `{root / 'output' / 'experiments' / experiment.id}`\n"
                "- Imported from legacy GEPA run for Review → Verdict → Promotion → Measure tracking.\n"
            )
        except Exception as exc:
            experiment_section = (
                "\n## Self-improvement Loop v0 import skipped\n\n"
                f"- Reason: `{type(exc).__name__}: {exc}`\n"
                "- The report-only summary was still saved; inspect the import issue separately.\n"
            )
    except FileNotFoundError:
        markdown = build_failed_variant_summary(root, selected_skill)

    today = dt.date.today().isoformat()
    out_path = report_path(root, selected_skill, today)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown + experiment_section)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Only summarize latest existing run; do not run GEPA")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    path = run_cycle(root, skill=args.skill, dry_run=args.dry_run)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
