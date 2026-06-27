#!/usr/bin/env python3
"""Classify a GEPA evolution run as reject/review/candidate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def classify_candidate(metrics: dict[str, Any], thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    thresholds = thresholds or {}
    min_improvement = float(thresholds.get("min_improvement", 0.03))
    max_size_growth = int(thresholds.get("max_size_growth_chars", 1500))

    improvement = float(metrics.get("improvement", 0.0))
    baseline_size = int(metrics.get("baseline_size", 0))
    evolved_size = int(metrics.get("evolved_size", 0))
    size_growth = evolved_size - baseline_size
    constraints_passed = bool(metrics.get("constraints_passed", False))

    reasons: list[str] = []

    if not constraints_passed:
        reasons.append("constraints_failed")
    if size_growth > max_size_growth:
        reasons.append(f"size_growth_too_large:{size_growth}>{max_size_growth}")
    if improvement <= 0:
        reasons.append(f"no_positive_improvement:{improvement:.4f}")

    if reasons:
        status = "reject"
    elif improvement >= min_improvement:
        status = "candidate"
        reasons.append(f"improvement_above_threshold:{improvement:.4f}>={min_improvement:.4f}")
    else:
        status = "review"
        reasons.append(f"small_positive_improvement:{improvement:.4f}<{min_improvement:.4f}")

    return {
        "status": status,
        "reasons": reasons,
        "improvement": improvement,
        "size_growth": size_growth,
        "constraints_passed": constraints_passed,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: check_candidate_gate.py <metrics.json>", file=sys.stderr)
        return 2
    metrics = json.loads(Path(argv[0]).read_text())
    result = classify_candidate(metrics)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] != "reject" else 1


if __name__ == "__main__":
    raise SystemExit(main())
