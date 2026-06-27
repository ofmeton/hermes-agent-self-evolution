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
