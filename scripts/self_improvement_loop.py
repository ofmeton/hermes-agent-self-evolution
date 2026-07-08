#!/usr/bin/env python3
"""Self-improvement Loop v0 CLI.

This CLI is deliberately file-backed and local-only. It records the v0 loop
artifacts; it does not modify live skills, merge PRs, or run paid GEPA calls.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from evolution.core.self_improvement import ExperimentStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Self-improvement Loop v0 artifact CLI")
    parser.add_argument("--output-root", default="output", help="Root output directory for loop artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    observe = sub.add_parser("observe", help="Record one observation")
    observe.add_argument("--source", required=True)
    observe.add_argument("--skill", required=True)
    observe.add_argument("--signal-type", required=True)
    observe.add_argument("--evidence-ref", required=True)
    observe.add_argument("--severity", default="medium")
    observe.add_argument("--note", default="")

    opportunity = sub.add_parser("opportunity", help="Record one opportunity")
    opportunity.add_argument("--skill", required=True)
    opportunity.add_argument("--observation-id", action="append", default=[])
    opportunity.add_argument("--hypothesis", required=True)
    opportunity.add_argument("--priority", type=int, default=5)

    select = sub.add_parser("select", help="Create an experiment from a selected opportunity")
    select.add_argument("--skill", required=True)
    select.add_argument("--opportunity-id", required=True)
    select.add_argument("--target", required=True)
    select.add_argument("--baseline-ref", required=True)
    select.add_argument("--dataset-ref", required=True)
    select.add_argument("--created-by", default="human")

    add_candidate = sub.add_parser("add-candidate", help="Attach a candidate artifact to an experiment")
    add_candidate.add_argument("--experiment-id", required=True)
    text_group = add_candidate.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--artifact-file")
    add_candidate.add_argument("--source", default="manual")
    add_candidate.add_argument("--diff-summary", default="")

    eval_cmd = sub.add_parser("eval", help="Record an EvalRun for a candidate")
    eval_cmd.add_argument("--experiment-id", required=True)
    eval_cmd.add_argument("--candidate-id", required=True)
    eval_cmd.add_argument("--dataset", required=True)
    eval_cmd.add_argument("--metric-name", required=True)
    eval_cmd.add_argument("--baseline-score", type=float, required=True)
    eval_cmd.add_argument("--candidate-score", type=float, required=True)
    eval_cmd.add_argument("--cost", type=float, default=0.0)
    eval_cmd.add_argument("--artifact-changed", action=argparse.BooleanOptionalAction, default=True)

    review = sub.add_parser("review", help="Generate a digest for human review")
    review.add_argument("--experiment-id", required=True)

    verdict = sub.add_parser("verdict", help="Record a human verdict")
    verdict.add_argument("--experiment-id", required=True)
    verdict.add_argument("--candidate-id", required=True)
    verdict.add_argument("--evalrun-id", required=True)
    verdict.add_argument("--decision", choices=["promote", "reject", "revise", "hold"], required=True)
    verdict.add_argument("--reviewer", required=True)
    verdict.add_argument("--rationale", required=True)

    promote = sub.add_parser("promote", help="Record a human-approved promotion")
    promote.add_argument("--experiment-id", required=True)
    promote.add_argument("--candidate-id", required=True)
    promote.add_argument("--verdict-id", required=True)
    promote.add_argument("--applied-via", required=True)
    promote.add_argument("--commit-ref", required=True)
    promote.add_argument("--status", default="applied")

    measure = sub.add_parser("measure", help="Record an ImpactReport")
    measure.add_argument("--promotion-id", required=True)
    measure.add_argument("--pre-metric", type=float, required=True)
    measure.add_argument("--post-metric", type=float, required=True)
    measure.add_argument("--window", required=True)

    digest = sub.add_parser("digest", help="Generate a digest markdown")
    digest.add_argument("--experiment-id", required=True)

    import_run = sub.add_parser("import-run", help="Import a legacy output/<skill>/<timestamp> run")
    import_run.add_argument("--run-dir", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = ExperimentStore(Path(args.output_root))

    if args.command == "observe":
        observation = store.record_observation(
            source=args.source,
            target_skill=args.skill,
            signal_type=args.signal_type,
            evidence_ref=args.evidence_ref,
            severity=args.severity,
            note=args.note,
        )
        print(observation.id)
        return 0

    if args.command == "opportunity":
        opportunity = store.record_opportunity(
            target_skill=args.skill,
            observation_ids=args.observation_id,
            hypothesis=args.hypothesis,
            priority=args.priority,
        )
        print(opportunity.id)
        return 0

    if args.command == "select":
        experiment = store.create_experiment(
            skill=args.skill,
            opportunity_id=args.opportunity_id,
            target=args.target,
            baseline_ref=args.baseline_ref,
            dataset_ref=args.dataset_ref,
            created_by=args.created_by,
        )
        print(experiment.id)
        return 0

    if args.command == "add-candidate":
        text = args.text if args.text is not None else Path(args.artifact_file).read_text(encoding="utf-8")
        candidate = store.write_candidate(
            args.experiment_id,
            text=text,
            source=args.source,
            diff_summary=args.diff_summary,
        )
        print(candidate.id)
        return 0

    if args.command == "eval":
        eval_run = store.write_eval_run(
            args.experiment_id,
            args.candidate_id,
            dataset=args.dataset,
            metric_name=args.metric_name,
            baseline_score=args.baseline_score,
            candidate_score=args.candidate_score,
            cost=args.cost,
            artifact_changed=args.artifact_changed,
        )
        print(eval_run.id)
        return 0

    if args.command == "review" or args.command == "digest":
        path = store.write_digest(args.experiment_id)
        print(path)
        return 0

    if args.command == "verdict":
        verdict = store.write_verdict(
            args.experiment_id,
            args.candidate_id,
            args.evalrun_id,
            decision=args.decision,
            reviewer=args.reviewer,
            rationale=args.rationale,
        )
        print(verdict.id)
        return 0

    if args.command == "promote":
        promotion = store.write_promotion(
            args.experiment_id,
            args.candidate_id,
            args.verdict_id,
            applied_via=args.applied_via,
            commit_ref=args.commit_ref,
            status=args.status,
        )
        print(promotion.id)
        return 0

    if args.command == "measure":
        impact = store.write_impact_report(
            args.promotion_id,
            pre_metric=args.pre_metric,
            post_metric=args.post_metric,
            window=args.window,
        )
        print(impact.id)
        return 0

    if args.command == "import-run":
        experiment = store.import_legacy_run(Path(args.run_dir))
        print(experiment.id)
        return 0

    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
