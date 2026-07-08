"""Tests for the Self-improvement Loop v0 data model and artifact store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_experiment_store_creates_traceable_v0_artifacts(tmp_path):
    from evolution.core.self_improvement import ExperimentStore

    store = ExperimentStore(tmp_path / "output")

    observation = store.record_observation(
        source="session",
        target_skill="stop-slop",
        signal_type="correction",
        evidence_ref="session://abc#msg-1",
        severity="medium",
        note="User corrected AI slop wording.",
    )
    opportunity = store.record_opportunity(
        target_skill="stop-slop",
        observation_ids=[observation.id],
        hypothesis="Stop-slop should better remove generic AI phrasing.",
        priority=10,
    )
    experiment = store.create_experiment(
        skill="stop-slop",
        opportunity_id=opportunity.id,
        target="skill:stop-slop",
        baseline_ref="output/stop-slop/20260628_233149/baseline_skill.md",
        dataset_ref="datasets/skills/stop-slop/holdout.jsonl",
        budget_hint={"cost_usd": 0.2},
        created_by="test",
    )
    candidate = store.write_candidate(
        experiment.id,
        text="Rewrite instruction candidate",
        source="gepa",
        diff_summary="candidate captured from GEPA proposal",
    )
    eval_run = store.write_eval_run(
        experiment.id,
        candidate.id,
        dataset="holdout:2",
        metric_name="skill_fitness",
        baseline_score=0.40,
        candidate_score=0.55,
        cost=0.01,
        artifact_changed=True,
    )
    verdict = store.write_verdict(
        experiment.id,
        candidate.id,
        eval_run.id,
        decision="promote",
        reviewer="human",
        rationale="Better and still concise.",
    )
    promotion = store.write_promotion(
        experiment.id,
        candidate.id,
        verdict.id,
        applied_via="manual",
        commit_ref="abc123",
        status="applied",
    )
    impact = store.write_impact_report(
        promotion.id,
        pre_metric=0.40,
        post_metric=0.50,
        window="7d",
    )

    exp_dir = tmp_path / "output" / "experiments" / experiment.id
    assert (exp_dir / "experiment.json").exists()
    assert (exp_dir / "candidates" / "candidate_001.md").read_text() == "Rewrite instruction candidate"
    assert json.loads((exp_dir / "eval" / f"{eval_run.id}.json").read_text())["delta"] == pytest.approx(0.15)
    assert json.loads((exp_dir / "verdict.json").read_text())["decision"] == "promote"
    assert json.loads((exp_dir / "promotion.json").read_text())["commit_ref"] == "abc123"
    assert json.loads((tmp_path / "output" / "impact" / promotion.id / "impact_report.json").read_text())["recommendation"] == "keep"
    assert impact.delta == pytest.approx(0.10)
    assert impact.regression_flag is False


def test_store_rejects_path_traversal_experiment_ids(tmp_path):
    from evolution.core.self_improvement import ExperimentStore

    store = ExperimentStore(tmp_path / "output")

    with pytest.raises(ValueError, match="unsafe"):
        store.write_candidate("../escape", text="bad")


def test_import_legacy_run_creates_experiment_with_candidates_and_eval(tmp_path):
    from evolution.core.self_improvement import ExperimentStore

    root = tmp_path
    run_dir = root / "output" / "stop-slop" / "20260628_233149"
    run_dir.mkdir(parents=True)
    (run_dir / "baseline_skill.md").write_text("base")
    (run_dir / "evolved_skill.md").write_text("evolved")
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir()
    (candidates_dir / "candidate_001.md").write_text("proposal one")
    (run_dir / "metrics.json").write_text(json.dumps({
        "skill_name": "stop-slop",
        "timestamp": "20260628_233149",
        "baseline_score": 0.4,
        "evolved_score": 0.35,
        "improvement": -0.05,
        "optimizer_model": "openai/gpt-5-mini",
        "eval_model": "openai/gpt-5-nano",
        "candidate_count": 1,
    }))

    store = ExperimentStore(root / "output")
    experiment = store.import_legacy_run(run_dir)
    again = store.import_legacy_run(run_dir)

    exp_dir = root / "output" / "experiments" / experiment.id
    assert again.id == experiment.id
    assert experiment.skill == "stop-slop"
    assert json.loads((exp_dir / "experiment.json").read_text())["legacy_run_dir"].endswith("output/stop-slop/20260628_233149")
    assert (exp_dir / "candidates" / "candidate_001.md").read_text() == "proposal one"
    eval_files = list((exp_dir / "eval").glob("*.json"))
    assert len(eval_files) == 1
    assert json.loads(eval_files[0].read_text())["delta"] == pytest.approx(-0.05)


def test_digest_includes_full_loop_state(tmp_path):
    from evolution.core.self_improvement import ExperimentStore

    store = ExperimentStore(tmp_path / "output")
    experiment = store.create_experiment(
        skill="stop-slop",
        opportunity_id="opp_manual",
        target="skill:stop-slop",
        baseline_ref="baseline.md",
        dataset_ref="holdout.jsonl",
    )
    candidate = store.write_candidate(experiment.id, "candidate", source="manual")
    eval_run = store.write_eval_run(experiment.id, candidate.id, "holdout", "fitness", 0.4, 0.5, 0.0)
    verdict = store.write_verdict(experiment.id, candidate.id, eval_run.id, "promote", "human", "Looks good")
    promotion = store.write_promotion(experiment.id, candidate.id, verdict.id, "manual", "abc", "applied")
    store.write_impact_report(promotion.id, pre_metric=0.4, post_metric=0.45, window="7d")

    digest = store.write_digest(experiment.id)
    text = digest.read_text()

    assert "# Self-improvement Experiment Digest" in text
    assert "stop-slop" in text
    assert "Eval delta" in text
    assert "promote" in text
    assert "Impact recommendation" in text
