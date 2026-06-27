#!/usr/bin/env python3
"""Summarize the latest GEPA skill evolution run."""

from __future__ import annotations

import difflib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _load_gate_module():
    gate_path = Path(__file__).with_name("check_candidate_gate.py")
    spec = importlib.util.spec_from_file_location("check_candidate_gate", gate_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def find_latest_run(root: Path, skill: str) -> Path:
    base = root / "output" / skill
    if not base.exists():
        raise FileNotFoundError(f"No output directory for skill: {skill}")
    candidates = [p for p in base.iterdir() if p.is_dir() and (p / "metrics.json").exists()]
    if not candidates:
        raise FileNotFoundError(f"No completed runs for skill: {skill}")
    return sorted(candidates, key=lambda p: p.name)[-1]


def _diff_stats(run_dir: Path) -> dict[str, int]:
    baseline = (run_dir / "baseline_skill.md").read_text().splitlines()
    evolved = (run_dir / "evolved_skill.md").read_text().splitlines()
    diff = list(difflib.unified_diff(baseline, evolved, lineterm=""))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    return {"added_lines": added, "removed_lines": removed, "diff_lines": len(diff)}


def build_summary(run_dir: Path, thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = json.loads((run_dir / "metrics.json").read_text())
    gate = _load_gate_module().classify_candidate(metrics, thresholds)
    diff_stats = _diff_stats(run_dir)

    markdown = f"""# Evolution Run Summary — {metrics.get('skill_name')}

- Run dir: `{run_dir}`
- Timestamp: `{metrics.get('timestamp')}`
- Status: **{gate['status']}**
- Reasons: {', '.join(gate['reasons'])}
- Optimizer model: `{metrics.get('optimizer_model')}`
- Eval/dataset model: `{metrics.get('eval_model')}`
- Iterations: {metrics.get('iterations')}
- Baseline score: {metrics.get('baseline_score'):.3f}
- Evolved score: {metrics.get('evolved_score'):.3f}
- Improvement: {metrics.get('improvement'):+.3f}
- Baseline size: {metrics.get('baseline_size')} chars
- Evolved size: {metrics.get('evolved_size')} chars
- Size growth: {gate['size_growth']} chars
- Constraints passed: {metrics.get('constraints_passed')}
- Diff lines: +{diff_stats['added_lines']} / -{diff_stats['removed_lines']}

## Next action

"""
    if gate["status"] == "candidate":
        markdown += "Review the diff manually. If it reads well, run the PR candidate command.\n"
    elif gate["status"] == "review":
        markdown += "Small improvement. Review manually, but do not auto-promote.\n"
    else:
        markdown += "Reject this run. Keep it as audit data only.\n"

    return {"metrics": metrics, "gate": gate, "diff_stats": diff_stats, "markdown": markdown}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: summarize_latest_run.py <skill> [repo_root]", file=sys.stderr)
        return 2
    skill = argv[0]
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    run_dir = find_latest_run(root, skill)
    summary = build_summary(run_dir)
    print(summary["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
