# EXP-008: fixed composition and computed-utility protocol v2

Protocol fixed on 14 November 2026 before live follow-up responses. The run manifest must hash this protocol and copy source, prompts and serialized input packages before the first live request. It follows EXP-007's observed ceiling and report-handoff problems while preserving that run unchanged. Changes after observing responses require a new protocol/run.

## Question and interpretation

With repaired specialist evidence delivery and critic context, do the same four role configurations differ when they must calculate utility from supplied components and apply policy to composed, actor-scoped situations?

This is a **composition and synthesis challenge**, not an established harder benchmark. The manipulations increase explicit task requirements, but no empirical difficulty claim is made before observing outcomes. Results compare configurations within EXP-008. Differences from EXP-007 cannot be attributed to repairs alone: cards, information presentation, output schema and endpoint requirements also change.

Four fixed cards form **two controlled contrast pairs**, not four independent scenario families or a representative market sample. One pass of every card under each of `single`, `specialists`, `challenged` and `self_review` produces 16 jobs and at most 56 calls. No new card or mutation is chosen after seeing a live response. Preserve all recipes and serialized cards, including an unexpected deterministic reference.

## Frozen recipes

The parent selected these recipes before computing their reference outcomes. A single deterministic inspection subsequently established the targets below; no recipe was changed in response to those targets. Implementation is `src/risk_desk/data/study_cases.py`. Save its bytes and all serialized packages in the run's frozen source/input snapshot.

| Pair | Case ID | Recipe | Reference from deterministic inspection |
| --- | --- | --- | --- |
| Actor scope | `case_01` | Start with `stress_thin_hedge_capped` (B13). Append the three B3 positions from `physical_obligation`, multiplying their quantities by 30. Set CP-RETAIL to missing with null credit limit/utilisation. Keep the actor authorised for B13 only. | `hedge_25`; `highest_utility` |
| Actor scope | `case_02` | Identical state to case_01 except the mandate also permits B3. | `abstain`; `missing_credit` |
| Numerical/policy threshold | `case_03` | Start with `stress_thin_hedge_capped`. Multiply its existing financial position quantities and stress limit by 0.91. Add the existing B3 physical-obligation template as `B13-physical`, book B13, desk `power_hedge`, quantity 6,000 and counterparty CP-POWER. Retain template price EUR78, dates and physical hedge ratio 0.40. Credit remains known. | `abstain`; `near_tie` |
| Numerical/policy threshold | `case_04` | Same construction as case_03, using 1.07 instead of 0.91. The added physical quantity stays 6,000. | `hedge_25`; `highest_utility` |

Every card receives its opaque case ID and no logged action. The actor-scope pair changes one mandate field; that change affects the relevant credit/physical scope and the acted portfolio together. It is not an isolated intervention on credit alone. The scaling pair changes financial quantities and the stress limit, leaving the physical obligation fixed. Both pairs remain authored diagnostics with inherited modelling assumptions.

Expected references are evaluator-only and must not appear in model messages, case labels or the visible bundle. In particular, the two abstentions have different required mechanisms: missing credit versus near-tie. Matching `abstain` alone must not count as identifying the correct policy basis.

## Uniform information and bounded roles

All four arms receive the same visible card, action consequences, feasibility, declared policy, component values and utility formula. Final utility values are withheld from every role. The allowed formula is:

`utility = -0.5 * stress_loss - desk_lambda * cvar_95 - liquidity_cost - governance_penalty - tenor_penalty`

Supply `desk_lambda` explicitly from the actor's desk. Scalar components use EUR, matching the engine. A declared derived-quantity entry explains the formula and lists the component IDs; it is not a null measured value. Utility is undefined for infeasible actions. This distinction prevents deliberate withholding of a calculation from being conflated with genuinely missing credit information.

Retain a full evaluation-only bundle containing the actual utilities. Verify that final utility values are absent from all model-visible aliases, including aggregate action records. No scorecard answer, reference policy basis or evaluator-only bundle can reach a proposer, specialist or challenger. Model requests must be retained so this can be checked after execution.

Keep the same role counts and division of labour:

- `single`: one proposer call.
- `specialists`: market/physical and credit/governance calls, then a proposer consuming admissible findings; three calls.
- `challenged`: the specialist sequence, an independent challenge and exactly one revision/confirmation; five calls.
- `self_review`: a proposer and four generic review/revision passes; five calls.

The challenge receives original visible evidence, the proposal and the provenance/status metadata needed to assess any workflow claims. It need not receive a trusted specialist conclusion. Additional roles must not gain access to private evaluator information or extra domain observations. Same-call controls still differ in context, token use and intermediate processing.

## Prespecified outcomes

The exact v2 output schemas are included in every role request and retained with source. No additional schema-repair calls are allowed. The proposal adds `decision_basis` with the allowed values `missing_credit`, `unreducible_breach`, `near_tie`, `highest_utility`. The evaluator derives basis using the engine's actual precedence: relevant missing credit; then breached state without a feasible risk reducer; then utility ranking and distinct-outcome near-tie; otherwise highest utility.

### Primary decision endpoint

`grounded_policy_match` requires all of:

1. The strict proposal/numeric-grounding contract passes.
2. The proposed action equals the evaluator-only reference.
3. `decision_basis` equals the evaluator-only required basis.
4. The computed utility claim cites its derived ID and **all five source-component IDs** for that action. For abstention, the specified claim uses hold utility and hold's five components.

The source-component requirement must be an explicit scored predicate, not only a prompt request. Retain its pass/fail value independently of the aggregate outcome. Reject nonfinite values and booleans as numeric claims. Check all emitted structured numeric claims against the private deterministic bundle, with the same stated EUR0.01 or relative1e-6 tolerance. A derived definition itself is not a numeric observation to copy.

Report primary successes out of **four planned jobs per arm**. Provider errors, unattempted jobs after stopping and invalid final proposals do not count as successes. Report completed counts and failure categories separately. There are four case-level pairs per arm comparison, clustered into the two designed contrast pairs.

### Primary handoff/process endpoints

There are **16 planned specialist reports**: four cases × two specialist-enabled arms × two roles. Report usable reports/16 overall, by arm /8 and by role /8; keep absent/error outputs in the planned-report denominator. This measures admissible delivery under the declared contract, not narrative truth.

Report finding acceptance separately using all parsed emitted findings as its explicit denominator. Record malformed JSON/schema reports for which a reliable finding count is unavailable; do not silently omit them and call the resulting proportion a complete delivery rate. The v2 handoff policy validates findings individually: a well-formed finding with nonempty registered evidence IDs is retained even when another finding or the report envelope fails. Only the first four findings may be admitted. Missing required fields, unknown IDs and over-limit findings receive explicit rejection reasons. A fully valid report retains its summary; a partially admitted report omits the summary so it cannot restate rejected material. A report is usable if at least one finding survives. Retain redacted raw content, all validation records and downstream-visible survivors so auditors can reconstruct this policy. Schema-valid or mechanically admitted findings are not automatically factually true.

Also report how many specialist-enabled jobs receive zero, one or two usable reports. For challenges, retain usable status, requested revision/confirmation, cited evidence, reviewer-visible process context and actual proposal changes. Accepted identifiers alone do not establish the truth of a challenge.

### Secondary outcomes

Report contract satisfaction, action agreement, policy-basis accuracy, computed-utility accuracy, component-citation completeness, unnecessary abstention, verifier fallback and case-level changes in challenged and self-review proposals. Keep final recommendation metrics distinct from proposal metrics. Synthetic regret is calculated during the retained analysis from the private evaluation bundle and is conditional on both proposed and reference actions having defined non-abstaining feasible utility; do not impute zero to abstentions. The runner retains the necessary values even where its summary does not calculate this secondary statistic.

For `specialists`−`single`, `challenged`−`specialists` and `challenged`−`self_review`, report wins/losses/ties, missing pairs, and the actual case outcomes. The two contrast-pair patterns are especially relevant: handling irrelevant versus relevant missing credit and distinguishing the numerical near-tie threshold. Do not treat four rows as four independent replications or claim significance.

## Execution and provenance

Maximum planned calls: `4 × (1 + 3 + 5 + 5) = 56`. Hard cap: **60**, including all roles. The difference between plan and ceiling does not permit adaptive reruns. Retain existing model `gpt-6-luna` and reasoning effort `low` with no silent substitution. Use 1,800 maximum completion tokens, a 60-second request timeout and zero SDK retries.

Use fresh state for every job and rotate the same four-arm order by case index. Keep all errors and unattempted jobs; stop at the cap or after two consecutive job exceptions. No replacement prompt, extra case, retry-until-success or hidden repair of live outputs is permitted. A malformed role output remains evidence of the executed contract.

Freeze before live: protocol, recipe source, serialized cases, visible and private evaluation bundles, references/bases, source and prompt snapshots, dependency versions, exact schedule and output contract. Add per-call/stage UTC timestamps and explicit stage identity. Retain usage and monotonic latency, and do not turn token counts into an invented financial charge. Separate post-run analysis code and exploratory observations from the frozen method.

## Writing and PhD connection

EXP-007 remains a null measured comparison with 7/24 admissible specialist reports. EXP-008 tests the repaired configuration under newly specified composition and calculation requirements. Do not claim that a higher handoff rate or a better decision count isolates the causal effect of the repair; the protocol changed in several respects.

The research note should compare arms within EXP-008 and explain the two paired mechanisms, including different bases for the two abstentions. The article can follow one trace from evidence through specialist finding, challenge, revision and verification, identifying what changed and whether it improved the prespecified endpoint. A second ceiling or a regression remains reportable.

The PhD contribution is bounded evidence-contract and structured-synthesis evaluation for RQ4/RQ6, grounded in RQ1/RQ3's information, feasibility and utility assumptions. It does not establish semantic faithfulness of all prose, human usefulness, general multi-agent superiority, JEPA/hybrid performance or real-desk validity. These cases are newly composed diagnostics, not an independent externally validated test set.
