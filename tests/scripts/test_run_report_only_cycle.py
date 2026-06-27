import importlib.util
from pathlib import Path

import yaml


def load_cycle_module():
    path = Path(__file__).parents[2] / "scripts" / "run_report_only_cycle.py"
    spec = importlib.util.spec_from_file_location("run_report_only_cycle", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_selects_highest_priority_enabled_target():
    cycle = load_cycle_module()
    config = {
        "targets": [
            {"skill": "low", "enabled": True, "priority": 1},
            {"skill": "off", "enabled": False, "priority": 99},
            {"skill": "high", "enabled": True, "priority": 10},
        ]
    }
    assert cycle.select_target(config)["skill"] == "high"


def test_report_path_is_date_and_skill_scoped(tmp_path):
    cycle = load_cycle_module()
    path = cycle.report_path(tmp_path, "github-code-review", "2026-06-27")
    assert path == tmp_path / "reports" / "evolution-runs" / "2026-06-27" / "github-code-review" / "summary.md"


def test_build_failed_variant_summary_when_no_completed_run_exists(tmp_path):
    cycle = load_cycle_module()
    failed = tmp_path / "output" / "demo" / "evolved_FAILED.md"
    failed.parent.mkdir(parents=True)
    failed.write_text("---\nname: demo\ndescription: Demo\n---\n\n# Demo")

    markdown = cycle.build_failed_variant_summary(tmp_path, "demo")

    assert "Status: **reject**" in markdown
    assert "evolved_FAILED.md" in markdown
    assert "No completed `metrics.json` run directory was produced" in markdown


def test_run_cycle_passes_target_repo_and_holdout_limit(tmp_path, monkeypatch):
    cycle = load_cycle_module()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "evolution_targets.yaml").write_text(yaml.safe_dump({
        "defaults": {
            "optimizer_model": "openai/gpt-5-mini",
            "eval_model": "openai/gpt-5-nano",
            "eval_source": "synthetic",
            "iterations": 3,
        },
        "targets": [{
            "skill": "session-retrospective",
            "enabled": True,
            "priority": 10,
            "iterations": 1,
            "holdout_limit": 2,
            "hermes_agent_repo": "/tmp/custom/.claude",
        }],
    }))
    script = tmp_path / "scripts" / "evolve_skill_once.sh"
    script.parent.mkdir()
    script.write_text("#!/usr/bin/env bash\n")
    failed = tmp_path / "output" / "session-retrospective" / "evolved_FAILED.md"
    failed.parent.mkdir(parents=True)
    failed.write_text("---\nname: session-retrospective\ndescription: Demo\n---\n\n# Demo")

    calls = []

    def fake_run(command, cwd, env, check):
        calls.append({"command": command, "cwd": cwd, "env": env, "check": check})

    monkeypatch.setattr(cycle.subprocess, "run", fake_run)

    class FakeSummaryModule:
        @staticmethod
        def find_latest_run(root, skill):
            raise FileNotFoundError

    monkeypatch.setattr(cycle, "_load_summary_module", lambda root: FakeSummaryModule)

    cycle.run_cycle(tmp_path, skill="session-retrospective", dry_run=False)

    assert calls[0]["command"][-1] == "2"
    assert calls[0]["command"][1:6] == [
        "session-retrospective",
        "1",
        "synthetic",
        "openai/gpt-5-mini",
        "openai/gpt-5-nano",
    ]
    assert calls[0]["env"]["HERMES_AGENT_REPO"] == "/tmp/custom/.claude"
