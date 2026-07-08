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
    diff_stats = _diff_stats(run_dir)
    enriched_metrics = {
        **metrics,
        "artifact_changed": bool(diff_stats["added_lines"] or diff_stats["removed_lines"]),
    }
    gate = _load_gate_module().classify_candidate(enriched_metrics, thresholds)

    # Check for captured non-selected proposals
    candidates_dir = run_dir / "candidates"
    candidate_files = sorted(candidates_dir.glob("candidate_*.md")) if candidates_dir.exists() else []
    candidate_count = len(candidate_files)

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
- Candidate proposals captured: {candidate_count}
"""

    # Add proposal discard notice if proposals exist but artifact didn't change
    if candidate_count > 0 and not enriched_metrics.get("artifact_changed"):
        first_candidate = candidate_files[0].name if candidate_files else ""
        candidates_path = candidates_dir.relative_to(run_dir.parents[1]) if candidates_dir.exists() else ""
        markdown += (
            f"\n## ⚠ Non-selected proposals discarded ({candidate_count})\n\n"
            f"GEPA generated {candidate_count} instruction proposals internally, but "
            "the optimizer selected the baseline artifact. These proposals were **not lost** — "
            f"they are saved in `{candidates_dir}/` for human review.\n\n"
        )
        if candidate_count >= 1:
            markdown += (
                f"- Review the first candidate: `{candidates_dir / candidate_files[0].name}`\n"
                f"- All {candidate_count} candidates available for manual inspection at `{candidates_dir}/`\n"
                f"- To apply a candidate: copy its content into the skill's `body` section.\n"
            )

    markdown += "\n## Next action\n\n"
    if gate["status"] == "candidate":
        markdown += "Review the diff manually. If it reads well, run the PR candidate command.\n"
    elif gate["status"] == "review":
        markdown += "Small improvement. Review manually, but do not auto-promote.\n"
    else:
        markdown += "Reject this run. Keep it as audit data only.\n"

    return {
        "metrics": metrics,
        "gate": gate,
        "diff_stats": diff_stats,
        "markdown": markdown,
        "candidate_count": candidate_count,
    }


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
