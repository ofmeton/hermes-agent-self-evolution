import importlib.util
from pathlib import Path


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
