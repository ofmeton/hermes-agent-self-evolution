import importlib.util
from pathlib import Path


def load_gate_module():
    path = Path(__file__).parents[2] / "scripts" / "check_candidate_gate.py"
    spec = importlib.util.spec_from_file_location("check_candidate_gate", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_candidate_when_improved_constraints_pass_and_size_ok():
    gate = load_gate_module()
    result = gate.classify_candidate(
        metrics={
            "baseline_score": 0.50,
            "evolved_score": 0.57,
            "improvement": 0.07,
            "baseline_size": 10000,
            "evolved_size": 10500,
            "constraints_passed": True,
        },
        thresholds={"min_improvement": 0.03, "max_size_growth_chars": 1500},
    )
    assert result["status"] == "candidate"


def test_reject_when_constraints_failed():
    gate = load_gate_module()
    result = gate.classify_candidate(
        metrics={
            "improvement": 0.20,
            "baseline_size": 10000,
            "evolved_size": 10100,
            "constraints_passed": False,
        },
        thresholds={"min_improvement": 0.03, "max_size_growth_chars": 1500},
    )
    assert result["status"] == "reject"
    assert any("constraints" in reason for reason in result["reasons"])


def test_review_when_small_positive_improvement():
    gate = load_gate_module()
    result = gate.classify_candidate(
        metrics={
            "improvement": 0.01,
            "baseline_size": 10000,
            "evolved_size": 10100,
            "constraints_passed": True,
        },
        thresholds={"min_improvement": 0.03, "max_size_growth_chars": 1500},
    )
    assert result["status"] == "review"
