"""Self-improvement Loop v0 data models and artifact store.

This module intentionally uses only the Python standard library. v0 needs a
traceable, file-backed loop for one skill before adding adapters, cron, or
multi-skill rotation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any, Literal
from uuid import uuid4

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{uuid4().hex[:8]}"


def require_safe_id(value: str, field_name: str = "id") -> str:
    if not value or not SAFE_ID_RE.match(value):
        raise ValueError(f"unsafe {field_name}: {value!r}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"unsafe {field_name}: {value!r}")
    return value


@dataclass
class Observation:
    id: str
    ts: str
    source: str
    target_skill: str
    signal_type: str
    evidence_ref: str
    severity: str = "medium"
    note: str = ""


@dataclass
class Opportunity:
    id: str
    target_skill: str
    observation_ids: list[str]
    hypothesis: str
    priority: int = 5
    status: str = "open"
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class Experiment:
    id: str
    skill: str
    opportunity_id: str
    target: str
    baseline_ref: str
    dataset_ref: str
    budget_hint: dict[str, Any] = field(default_factory=dict)
    created_by: str = "hermes"
    status: str = "created"
    created_at: str = field(default_factory=utc_now_iso)
    legacy_run_dir: str | None = None


@dataclass
class Candidate:
    id: str
    experiment_id: str
    source: str
    artifact_path: str
    diff_summary: str = ""
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class EvalRun:
    id: str
    candidate_id: str
    dataset: str
    metric_name: str
    baseline_score: float
    candidate_score: float
    delta: float
    cost: float = 0.0
    passed: bool = False
    artifact_changed: bool = True
    generated_at: str = field(default_factory=utc_now_iso)


@dataclass
class Verdict:
    id: str
    candidate_id: str
    evalrun_id: str
    decision: Literal["promote", "reject", "revise", "hold"]
    reviewer: str
    rationale: str
    ts: str = field(default_factory=utc_now_iso)


@dataclass
class Promotion:
    id: str
    candidate_id: str
    verdict_id: str
    applied_via: str
    commit_ref: str
    status: str
    applied_at: str = field(default_factory=utc_now_iso)


@dataclass
class ImpactReport:
    id: str
    promotion_id: str
    window: str
    pre_metric: float
    post_metric: float
    delta: float
    regression_flag: bool
    recommendation: Literal["keep", "rollback", "inconclusive"]
    generated_at: str = field(default_factory=utc_now_iso)


class ExperimentStore:
    """File-backed store for Self-improvement Loop v0 artifacts."""

    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)

    @property
    def observations_root(self) -> Path:
        return self.output_root / "observations"

    @property
    def backlog_root(self) -> Path:
        return self.output_root / "backlog"

    @property
    def experiments_root(self) -> Path:
        return self.output_root / "experiments"

    @property
    def impact_root(self) -> Path:
        return self.output_root / "impact"

    @property
    def digest_root(self) -> Path:
        return self.output_root / "digest"

    def _experiment_dir(self, experiment_id: str) -> Path:
        return self.experiments_root / require_safe_id(experiment_id, "experiment_id")

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(payload, "__dataclass_fields__"):
            data = asdict(payload)
        else:
            data = payload
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def record_observation(
        self,
        *,
        source: str,
        target_skill: str,
        signal_type: str,
        evidence_ref: str,
        severity: str = "medium",
        note: str = "",
    ) -> Observation:
        observation = Observation(
            id=make_id("obs"),
            ts=utc_now_iso(),
            source=source,
            target_skill=target_skill,
            signal_type=signal_type,
            evidence_ref=evidence_ref,
            severity=severity,
            note=note,
        )
        day = observation.ts[:10]
        self._write_json(self.observations_root / day / f"{observation.id}.json", observation)
        return observation

    def record_opportunity(
        self,
        *,
        target_skill: str,
        observation_ids: list[str],
        hypothesis: str,
        priority: int = 5,
        status: str = "open",
    ) -> Opportunity:
        opportunity = Opportunity(
            id=make_id("opp"),
            target_skill=target_skill,
            observation_ids=observation_ids,
            hypothesis=hypothesis,
            priority=priority,
            status=status,
        )
        self.backlog_root.mkdir(parents=True, exist_ok=True)
        with (self.backlog_root / "opportunities.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(opportunity), sort_keys=True) + "\n")
        return opportunity

    def create_experiment(
        self,
        *,
        skill: str,
        opportunity_id: str,
        target: str,
        baseline_ref: str,
        dataset_ref: str,
        budget_hint: dict[str, Any] | None = None,
        created_by: str = "hermes",
        status: str = "created",
        legacy_run_dir: str | None = None,
    ) -> Experiment:
        experiment = Experiment(
            id=make_id("exp"),
            skill=skill,
            opportunity_id=opportunity_id,
            target=target,
            baseline_ref=baseline_ref,
            dataset_ref=dataset_ref,
            budget_hint=budget_hint or {},
            created_by=created_by,
            status=status,
            legacy_run_dir=legacy_run_dir,
        )
        exp_dir = self._experiment_dir(experiment.id)
        exp_dir.mkdir(parents=True, exist_ok=False)
        (exp_dir / "candidates").mkdir()
        (exp_dir / "eval").mkdir()
        self._write_json(exp_dir / "experiment.json", experiment)
        return experiment

    def load_experiment(self, experiment_id: str) -> Experiment:
        data = self._read_json(self._experiment_dir(experiment_id) / "experiment.json")
        return Experiment(**data)

    def find_experiment_by_legacy_run(self, legacy_run_dir: str) -> Experiment | None:
        """Return an existing imported experiment for a legacy run, if any.

        Report-only summaries may be re-run for the same legacy GEPA output.
        Importing must be idempotent so repeated dry-runs do not pollute the v0
        experiment backlog.
        """
        if not self.experiments_root.exists():
            return None
        for experiment_json in sorted(self.experiments_root.glob("*/experiment.json")):
            data = self._read_json(experiment_json)
            if data.get("legacy_run_dir") == legacy_run_dir:
                return Experiment(**data)
        return None

    def write_candidate(
        self,
        experiment_id: str,
        text: str,
        source: str = "manual",
        diff_summary: str = "",
    ) -> Candidate:
        exp_dir = self._experiment_dir(experiment_id)
        candidates_dir = exp_dir / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        index = len(sorted(candidates_dir.glob("candidate_*.md"))) + 1
        candidate_id = f"cand_{index:03d}"
        artifact = candidates_dir / f"candidate_{index:03d}.md"
        artifact.write_text(text, encoding="utf-8")
        candidate = Candidate(
            id=candidate_id,
            experiment_id=experiment_id,
            source=source,
            artifact_path=str(artifact),
            diff_summary=diff_summary,
        )
        self._write_json(candidates_dir / f"{candidate_id}.json", candidate)
        return candidate

    def write_eval_run(
        self,
        experiment_id: str,
        candidate_id: str,
        dataset: str,
        metric_name: str,
        baseline_score: float,
        candidate_score: float,
        cost: float = 0.0,
        artifact_changed: bool = True,
    ) -> EvalRun:
        delta = candidate_score - baseline_score
        eval_run = EvalRun(
            id=make_id("eval"),
            candidate_id=candidate_id,
            dataset=dataset,
            metric_name=metric_name,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            delta=delta,
            cost=cost,
            passed=delta > 0 and artifact_changed,
            artifact_changed=artifact_changed,
        )
        self._write_json(self._experiment_dir(experiment_id) / "eval" / f"{eval_run.id}.json", eval_run)
        return eval_run

    def write_verdict(
        self,
        experiment_id: str,
        candidate_id: str,
        evalrun_id: str,
        decision: Literal["promote", "reject", "revise", "hold"],
        reviewer: str,
        rationale: str,
    ) -> Verdict:
        if decision not in {"promote", "reject", "revise", "hold"}:
            raise ValueError(f"invalid verdict decision: {decision}")
        verdict = Verdict(
            id=make_id("verdict"),
            candidate_id=candidate_id,
            evalrun_id=evalrun_id,
            decision=decision,
            reviewer=reviewer,
            rationale=rationale,
        )
        self._write_json(self._experiment_dir(experiment_id) / "verdict.json", verdict)
        return verdict

    def write_promotion(
        self,
        experiment_id: str,
        candidate_id: str,
        verdict_id: str,
        applied_via: str,
        commit_ref: str,
        status: str,
    ) -> Promotion:
        verdict_path = self._experiment_dir(experiment_id) / "verdict.json"
        if verdict_path.exists():
            verdict = self._read_json(verdict_path)
            if verdict.get("decision") != "promote":
                raise ValueError("promotion requires a promote verdict")
            if verdict.get("id") != verdict_id:
                raise ValueError("promotion verdict_id does not match verdict.json")
        promotion = Promotion(
            id=make_id("promo"),
            candidate_id=candidate_id,
            verdict_id=verdict_id,
            applied_via=applied_via,
            commit_ref=commit_ref,
            status=status,
        )
        self._write_json(self._experiment_dir(experiment_id) / "promotion.json", promotion)
        return promotion

    def write_impact_report(
        self,
        promotion_id: str,
        *,
        pre_metric: float,
        post_metric: float,
        window: str,
    ) -> ImpactReport:
        require_safe_id(promotion_id, "promotion_id")
        delta = post_metric - pre_metric
        if delta > 0:
            recommendation: Literal["keep", "rollback", "inconclusive"] = "keep"
        elif delta < 0:
            recommendation = "rollback"
        else:
            recommendation = "inconclusive"
        impact = ImpactReport(
            id=make_id("impact"),
            promotion_id=promotion_id,
            window=window,
            pre_metric=pre_metric,
            post_metric=post_metric,
            delta=delta,
            regression_flag=delta < 0,
            recommendation=recommendation,
        )
        self._write_json(self.impact_root / promotion_id / "impact_report.json", impact)
        return impact

    def import_legacy_run(self, run_dir: Path) -> Experiment:
        run_dir = Path(run_dir)
        legacy_run_dir = str(run_dir)
        existing = self.find_experiment_by_legacy_run(legacy_run_dir)
        if existing is not None:
            return existing

        metrics = self._read_json(run_dir / "metrics.json")
        skill = metrics.get("skill_name") or run_dir.parent.name
        experiment = self.create_experiment(
            skill=skill,
            opportunity_id=f"legacy_{metrics.get('timestamp', run_dir.name)}",
            target=f"skill:{skill}",
            baseline_ref=str(run_dir / "baseline_skill.md"),
            dataset_ref=f"legacy:{run_dir}",
            budget_hint={
                "optimizer_model": metrics.get("optimizer_model"),
                "eval_model": metrics.get("eval_model"),
            },
            created_by="legacy-import",
            status="evaluated",
            legacy_run_dir=str(run_dir),
        )
        legacy_candidates = sorted((run_dir / "candidates").glob("candidate_*.md"))
        if legacy_candidates:
            for legacy_candidate in legacy_candidates:
                self.write_candidate(
                    experiment.id,
                    legacy_candidate.read_text(encoding="utf-8"),
                    source="gepa",
                    diff_summary=f"imported from {legacy_candidate}",
                )
            candidate_id = "cand_001"
        else:
            candidate_id = self.write_candidate(
                experiment.id,
                (run_dir / "evolved_skill.md").read_text(encoding="utf-8"),
                source="evolved_artifact",
                diff_summary="imported evolved artifact",
            ).id

        baseline_score = float(metrics.get("baseline_score", 0.0))
        evolved_score = float(metrics.get("evolved_score", baseline_score + float(metrics.get("improvement", 0.0))))
        self.write_eval_run(
            experiment.id,
            candidate_id,
            dataset=f"legacy:{run_dir.name}",
            metric_name="skill_fitness",
            baseline_score=baseline_score,
            candidate_score=evolved_score,
            cost=float(metrics.get("estimated_cost_usd", 0.0) or 0.0),
            artifact_changed=metrics.get("artifact_changed", True),
        )
        return experiment

    def write_digest(self, experiment_id: str) -> Path:
        exp_dir = self._experiment_dir(experiment_id)
        experiment = self._read_json(exp_dir / "experiment.json")
        eval_runs = sorted((exp_dir / "eval").glob("*.json"))
        latest_eval = self._read_json(eval_runs[-1]) if eval_runs else {}
        verdict = self._read_json(exp_dir / "verdict.json") if (exp_dir / "verdict.json").exists() else {}
        promotion = self._read_json(exp_dir / "promotion.json") if (exp_dir / "promotion.json").exists() else {}
        impact = {}
        if promotion.get("id"):
            impact_path = self.impact_root / promotion["id"] / "impact_report.json"
            if impact_path.exists():
                impact = self._read_json(impact_path)

        lines = [
            "# Self-improvement Experiment Digest",
            "",
            f"- Experiment: `{experiment_id}`",
            f"- Skill: `{experiment.get('skill')}`",
            f"- Status: `{experiment.get('status')}`",
            f"- Opportunity: `{experiment.get('opportunity_id')}`",
            "",
            "## Eval",
            f"- Eval delta: {latest_eval.get('delta', 'n/a')}",
            f"- Passed: {latest_eval.get('passed', 'n/a')}",
            "",
            "## Verdict",
            f"- Decision: {verdict.get('decision', 'none')}",
            f"- Rationale: {verdict.get('rationale', '')}",
            "",
            "## Promotion",
            f"- Status: {promotion.get('status', 'none')}",
            f"- Commit: {promotion.get('commit_ref', '')}",
            "",
            "## Impact",
            f"- Impact recommendation: {impact.get('recommendation', 'none')}",
            f"- Impact delta: {impact.get('delta', 'n/a')}",
            "",
        ]
        self.digest_root.mkdir(parents=True, exist_ok=True)
        path = self.digest_root / f"{experiment_id}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
