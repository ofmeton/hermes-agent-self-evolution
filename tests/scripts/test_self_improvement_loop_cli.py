"""CLI tests for Self-improvement Loop v0."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_cli_module():
    path = Path(__file__).parents[2] / "scripts" / "self_improvement_loop.py"
    spec = importlib.util.spec_from_file_location("self_improvement_loop", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cli_select_eval_verdict_promote_measure_digest(tmp_path, capsys):
    cli = load_cli_module()
    output = tmp_path / "output"

    assert cli.main([
        "--output-root", str(output),
        "select",
        "--skill", "stop-slop",
        "--opportunity-id", "opp_manual",
        "--target", "skill:stop-slop",
        "--baseline-ref", "baseline.md",
        "--dataset-ref", "holdout.jsonl",
    ]) == 0
    exp_id = capsys.readouterr().out.strip()
    assert exp_id.startswith("exp_")

    assert cli.main([
        "--output-root", str(output),
        "add-candidate",
        "--experiment-id", exp_id,
        "--text", "candidate body",
        "--source", "manual",
    ]) == 0
    cand_id = capsys.readouterr().out.strip()
    assert cand_id == "cand_001"

    assert cli.main([
        "--output-root", str(output),
        "eval",
        "--experiment-id", exp_id,
        "--candidate-id", cand_id,
        "--dataset", "holdout:2",
        "--metric-name", "skill_fitness",
        "--baseline-score", "0.4",
        "--candidate-score", "0.6",
    ]) == 0
    eval_id = capsys.readouterr().out.strip()
    assert eval_id.startswith("eval_")

    assert cli.main([
        "--output-root", str(output),
        "verdict",
        "--experiment-id", exp_id,
        "--candidate-id", cand_id,
        "--evalrun-id", eval_id,
        "--decision", "promote",
        "--reviewer", "human",
        "--rationale", "Clear improvement",
    ]) == 0
    verdict_id = capsys.readouterr().out.strip()
    assert verdict_id.startswith("verdict_")

    assert cli.main([
        "--output-root", str(output),
        "promote",
        "--experiment-id", exp_id,
        "--candidate-id", cand_id,
        "--verdict-id", verdict_id,
        "--applied-via", "manual",
        "--commit-ref", "abc123",
        "--status", "applied",
    ]) == 0
    promotion_id = capsys.readouterr().out.strip()
    assert promotion_id.startswith("promo_")

    assert cli.main([
        "--output-root", str(output),
        "measure",
        "--promotion-id", promotion_id,
        "--pre-metric", "0.4",
        "--post-metric", "0.5",
        "--window", "7d",
    ]) == 0
    impact_id = capsys.readouterr().out.strip()
    assert impact_id.startswith("impact_")

    assert cli.main([
        "--output-root", str(output),
        "digest",
        "--experiment-id", exp_id,
    ]) == 0
    digest_path = Path(capsys.readouterr().out.strip())
    assert digest_path.exists()
    assert "Impact recommendation" in digest_path.read_text()


def test_cli_import_run_outputs_experiment_id(tmp_path, capsys):
    cli = load_cli_module()
    output = tmp_path / "output"
    run_dir = output / "stop-slop" / "20260628_233149"
    run_dir.mkdir(parents=True)
    (run_dir / "baseline_skill.md").write_text("base")
    (run_dir / "evolved_skill.md").write_text("evolved")
    (run_dir / "metrics.json").write_text(json.dumps({
        "skill_name": "stop-slop",
        "timestamp": "20260628_233149",
        "baseline_score": 0.4,
        "evolved_score": 0.45,
    }))

    assert cli.main([
        "--output-root", str(output),
        "import-run",
        "--run-dir", str(run_dir),
    ]) == 0

    exp_id = capsys.readouterr().out.strip()
    assert exp_id.startswith("exp_")
    assert (output / "experiments" / exp_id / "experiment.json").exists()
