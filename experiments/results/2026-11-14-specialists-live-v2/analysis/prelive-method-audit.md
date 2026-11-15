# EXP-008 pre-live method audit

14 November 2026. Inspected `run_specialist_followup.py`, `specialists_v2.py`, `followup_cases.py` and the newly saved canonical `experiments/specialist-study-v2/protocol.md`. No live model calls or implementation edits were made by this audit.

## Findings

No blocking protocol/implementation mismatch identified before execution.

- The runner schedules four fixed cases under four arms, rotating arm order by case index. Planned calls are 1/3/5/5 per case, total56, with cap60.
- Model setup retains maximum1,800 completion tokens, timeout60seconds and zero SDK retries. Model/effort are recorded from the existing configuration; the run manifest must be checked for the prescribed `gpt-6-luna`/`low` values.
- Exact output schemas are included in each role's request. There are no extra model calls to repair an invalid output.
- The graph keeps the private evaluation/reference bundles in closures used by verification. Model nodes consume the visible bundle and admissible workflow evidence. Reference basis is used by runner metrics, not supplied to model nodes.
- `primary_contract_pass` includes numeric correctness and `derivation_citations_valid`. Every emitted computed utility claim must cite all of its declared component IDs. `grounded_policy_match` additionally requires reference action and reference basis; mechanically grounded but incorrectly justified abstention does not pass that endpoint.
- Report validation admits findings independently and records per-finding failures. Only the first four may survive. Partial summaries are omitted, while usable finding bodies and status records are passed downstream. The canonical protocol records this policy rather than treating it as an unreported repair.
- The challenger receives workflow status evidence, enabling it to inspect process statements without receiving the specialists' substantive findings as trusted conclusions.
- The runner retains planned denominators of four per arm, incomplete pairs as null, all errors and unattempted jobs. Two consecutive job exceptions or the call cap stop execution.
- Per-request, response, stage and job UTC timestamps are now recorded in addition to monotonic durations.

## Deterministic input checks

`prelive-input-audit.json` records an independent arithmetic and visibility check over all four packages. All26 feasible action utilities reconstruct from the supplied rounded components and desk weight within tolerance. The maximum difference from private rounded utility is approximately EUR0.0000006, far below the EUR0.01 absolute tolerance.

No numeric utility values were found under utility fields/IDs in the recursively inspected visible bundles. Those fields instead contain explicit derived definitions; aggregate action records contain no utility values. This verifies the constructed input bundles, not future model compliance. Actual request records should still be checked after execution.

The four deterministic references are hedge25/highest-utility, abstain/missing-credit, abstain/near-tie, and hedge25/highest-utility. Their values were inspected only after recipes were fixed and before live execution. The audit did not select or modify recipes based on these outcomes.

## Analysis requirements

The runner stores all data needed for the planned process measures, but does not aggregate every endpoint itself. Retained analysis must compute planned report acceptance (16total,8per specialist arm,8per role), parsed finding acceptance with unknown counts disclosed, zero/one/two-report delivery by job, and conditional synthetic regret from private values. These analysis steps are specified in the protocol before live results, not added after choosing a favourable outcome.

This remains a single pass over two constructed contrast pairs. It does not establish that the new task is empirically harder, isolate a causal effect of repairs versus EXP-007, validate all explanation prose, or prove general specialist benefit. The next review should compare the executed frozen snapshot and retained outcomes with this protocol without rewriting either.
