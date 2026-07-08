"""Tests for evolve_skill optimizer/model wiring."""


def test_build_gepa_optimizer_uses_optimizer_model_for_reflection(monkeypatch):
    """GEPA reflection must use the optimizer model, not the cheap eval model.

    This keeps the intended low-cost hybrid profile intact: GPT-5 Nano for
    eval/dataset calls, GPT-5 Mini for reflection/mutation.
    """
    from evolution.skills import evolve_skill

    lm_calls = []
    gepa_calls = []

    class FakeLM:
        def __init__(self, model):
            self.model = model
            lm_calls.append(model)

    class FakeGEPA:
        def __init__(self, **kwargs):
            self.reflection_lm = kwargs["reflection_lm"]
            gepa_calls.append(kwargs)

    monkeypatch.setattr(evolve_skill.dspy, "LM", FakeLM)
    monkeypatch.setattr(evolve_skill.dspy, "GEPA", FakeGEPA)

    optimizer = evolve_skill.build_gepa_optimizer(
        iterations=3,
        optimizer_model="openai/gpt-5-mini",
    )

    assert isinstance(optimizer, FakeGEPA)
    assert lm_calls == ["openai/gpt-5-mini"]
    assert gepa_calls == [
        {
            "metric": evolve_skill.gepa_skill_fitness_metric,
            "max_full_evals": 3,
            "reflection_lm": optimizer.reflection_lm,
        }
    ]


def test_gepa_metric_adapter_accepts_current_dspy_signature():
    """DSPy's current GEPA requires five metric args; the adapter preserves the
    existing skill_fitness_metric behavior while satisfying that signature."""
    from types import SimpleNamespace

    from evolution.skills.evolve_skill import gepa_skill_fitness_metric

    example = SimpleNamespace(expected_behavior="mention tests and risk", task_input="review this PR")
    prediction = SimpleNamespace(output="Check tests and call out risk.")

    score = gepa_skill_fitness_metric(example, prediction, None, "output", None)

    assert 0.0 <= score <= 1.0


def test_validate_skill_artifact_checks_full_frontmatter():
    """Constraint validation must inspect the full SKILL.md, not just body text.

    GEPA optimizes the body, but the structural skill constraint requires YAML
    frontmatter. A valid full skill should not be rejected as missing frontmatter.
    """
    from evolution.core.config import EvolutionConfig
    from evolution.core.constraints import ConstraintValidator
    from evolution.skills.evolve_skill import validate_skill_artifact

    validator = ConstraintValidator(EvolutionConfig())
    full_skill = "---\nname: demo\ndescription: Demo skill\n---\n\n# Demo\nDo the thing."
    body_only = "# Demo\nDo the thing."

    results = validate_skill_artifact(
        validator,
        artifact_full=full_skill,
        baseline_full=full_skill,
    )

    assert all(result.passed for result in results)
    assert not all(
        result.passed
        for result in validator.validate_all(body_only, "skill", baseline_text=body_only)
    )


def test_validate_evolved_skill_keeps_backwards_compatible_wrapper():
    from evolution.core.config import EvolutionConfig
    from evolution.core.constraints import ConstraintValidator
    from evolution.skills.evolve_skill import validate_evolved_skill

    validator = ConstraintValidator(EvolutionConfig())
    full_skill = "---\nname: demo\ndescription: Demo skill\n---\n\n# Demo\nDo the thing."

    results = validate_evolved_skill(
        validator,
        evolved_full=full_skill,
        baseline_raw=full_skill,
    )

    assert all(result.passed for result in results)


def test_select_holdout_examples_limits_only_when_requested():
    from evolution.skills.evolve_skill import select_holdout_examples

    examples = ["a", "b", "c"]

    assert select_holdout_examples(examples) == examples
    assert select_holdout_examples(examples, None) == examples
    assert select_holdout_examples(examples, 0) == examples
    assert select_holdout_examples(examples, 2) == ["a", "b"]


def test_extract_proposals_from_gepa_output():
    from evolution.skills.evolve_skill import extract_proposals

    sample = """\
Some debug output...
Proposed new text for predictor.predict:
## Code Review Skill
Review pull requests thoroughly.
Check for:
- Security issues
- Performance concerns
---
Score: 0.520 | Size: 3,200 chars

Evaluating iteration 2...
Proposed new text for predictor.predict:
## Code Review Skill
Review pull requests with a focus on correctness.
Always check the diff stat.
---
Score: 0.810 | Size: 3,350 chars

Final selection: baseline wins
"""

    proposals = extract_proposals(sample)
    assert len(proposals) == 2
    assert "Code Review Skill" in proposals[0]
    assert "focus on correctness" in proposals[1]
    assert "Score:" not in proposals[0]
    assert "---" not in proposals[0]


def test_extract_proposals_empty_when_no_headers():
    from evolution.skills.evolve_skill import extract_proposals

    assert extract_proposals("Just regular log output\nNo proposals here\n") == []


def test_extract_proposals_deduplicates():
    from evolution.skills.evolve_skill import extract_proposals

    repeated = """\
Proposed new text for predictor.predict:
## Same Text
---
Score: 0.5

Proposed new text for predictor.predict:
## Same Text
---
Score: 0.6
"""
    proposals = extract_proposals(repeated)
    assert len(proposals) == 1


def test_extract_proposals_respects_maximum():
    from evolution.skills.evolve_skill import extract_proposals, MAX_PROPOSAL_CAPTURE

    many = ""
    for i in range(MAX_PROPOSAL_CAPTURE + 5):
        many += f"""Proposed new text for predictor.predict:
## Proposal {i}
---
Score: 0.5

"""
    proposals = extract_proposals(many)
    assert len(proposals) <= MAX_PROPOSAL_CAPTURE


def test_tee_capture_proxies_to_original_and_captures(tmp_path):
    from evolution.skills.evolve_skill import _TeeCapture
    import io

    buf = io.StringIO()
    tee = _TeeCapture(buf)

    tee.write("hello ")
    tee.write("world\n")

    assert buf.getvalue() == "hello world\n"
    assert tee.getvalue() == "hello world\n"


def test_tee_capture_bounded_buffer():
    from evolution.skills.evolve_skill import _TeeCapture
    import io

    buf = io.StringIO()
    tee = _TeeCapture(buf)

    big = "x" * (tee.MAX_BYTES + 1000)
    tee.write(big)

    assert len(tee.getvalue()) <= tee.MAX_BYTES
    assert buf.getvalue() == big  # original stream gets everything
