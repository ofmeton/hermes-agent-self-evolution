#!/usr/bin/env python3
"""Run one report-only Hermes GEPA improvement cycle."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


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

    if not dry_run:
        subprocess.run(
            [
                str(root / "scripts" / "evolve_skill_once.sh"),
                selected_skill,
                iterations,
                eval_source,
                optimizer_model,
                eval_model,
            ],
            cwd=root,
            check=True,
        )

    summary_module = _load_summary_module(root)
    run_dir = summary_module.find_latest_run(root, selected_skill)
    summary = summary_module.build_summary(run_dir, thresholds=defaults)

    today = dt.date.today().isoformat()
    out_path = report_path(root, selected_skill, today)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary["markdown"])
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
