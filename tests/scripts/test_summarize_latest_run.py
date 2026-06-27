import importlib.util
import json
from pathlib import Path


def load_summary_module():
    path = Path(__file__).parents[2] / "scripts" / "summarize_latest_run.py"
    spec = importlib.util.spec_from_file_location("summarize_latest_run", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_run(root: Path, skill: str, timestamp: str, improvement: float, changed: bool = True):
    run_dir = root / "output" / skill / timestamp
    run_dir.mkdir(parents=True)
    (run_dir / "baseline_skill.md").write_text("# Base\nOld text\n")
    evolved_text = "# Base\nNew text\n" if changed else "# Base\nOld text\n"
    (run_dir / "evolved_skill.md").write_text(evolved_text)
    (run_dir / "metrics.json").write_text(json.dumps({
        "skill_name": skill,
        "timestamp": timestamp,
        "iterations": 3,
        "optimizer_model": "openai/gpt-5-mini",
        "eval_model": "openai/gpt-5-nano",
        "baseline_score": 0.50,
        "evolved_score": 0.50 + improvement,
        "improvement": improvement,
        "baseline_size": 100,
        "evolved_size": 110,
        "constraints_passed": True,
    }))
    return run_dir


def test_find_latest_run_uses_newest_timestamp(tmp_path):
    summary = load_summary_module()
    write_run(tmp_path, "demo", "20260101_000000", 0.01)
    latest = write_run(tmp_path, "demo", "20260201_000000", 0.05)
    assert summary.find_latest_run(tmp_path, "demo") == latest


def test_build_summary_contains_models_and_recommendation(tmp_path):
    summary = load_summary_module()
    run_dir = write_run(tmp_path, "demo", "20260201_000000", 0.05)
    result = summary.build_summary(run_dir)
    assert "openai/gpt-5-mini" in result["markdown"]
    assert "openai/gpt-5-nano" in result["markdown"]
    assert result["gate"]["status"] == "candidate"


def test_build_summary_rejects_score_gain_without_artifact_change(tmp_path):
    summary = load_summary_module()
    run_dir = write_run(tmp_path, "demo", "20260201_000000", 0.13, changed=False)
    result = summary.build_summary(run_dir)
    assert result["gate"]["status"] == "reject"
    assert "artifact_unchanged" in result["markdown"]
