# EXP-008 independent recount and qualitative review

14 November 2026. This review reads the retained frozen source, requests, responses, stage records and evaluation packages. It does not change source, rerun a model, repair responses or alter endpoints. `independent-recount.json` recomputes the mechanical outcomes directly from JSON without importing the study evaluators. Qualitative observations below are targeted post-run interpretation, not additional prespecified success measures or a blinded human assessment.

## Recount and information boundary

All16 jobs completed in56 calls. Independent calculation agrees with every stored final-proposal contract, reference-action, decision-basis, component-citation and grounded-policy result. Frozen source hashes match. Every retained request contains the same prescribed base visible bundle for its case; role-specific workflow status is separate. No evaluator-only reference, basis or numeric final utility was supplied in those bundles or top-level request fields. Utility entries remain derived definitions, with their source components available. This checks recorded inputs, not unobservable properties of the provider or model training.

| Arm | Grounded policy matches | Correct raw action | Correct basis | Calls | Total tokens |
| --- | --- | --- | --- | --- | --- |
| Single | 3/4 | 4/4 | 4/4 | 4 | 42,934 |
| Specialists | 4/4 | 4/4 | 4/4 | 12 | 135,129 |
| Challenged | 4/4 | 4/4 | 4/4 | 20 | 233,046 |
| Self-review | 4/4 | 4/4 | 4/4 | 20 | 225,769 |

All final proposals have correct structured numeric claims within the prespecified tolerance and complete component citations. The single-arm loss is an additional unregistered citation, not an incorrect action, policy basis or calculated required utility. Specialists versus single has one grounded-policy win and three ties; challenged versus specialists and challenged versus self-review each have four ties. All pairs are complete. These are four cases in two authored contrast pairs, not four independent scenario families.

All16 planned specialist reports were observed, mechanically usable and fully valid. All60 parsed findings were admitted, with zero rejected findings and no unknown finding count. Each specialist-enabled job received both reports. This describes schema/citation admissibility; it does not mean that every admitted implication or summary is true. The previous7/24 result and this16/16 result concern different tasks and source versions, so they do not isolate the causal effect of repairs.

## The single-arm contract failure

**Locator:** `results.json`, row `case_04--single`, `proposal.evidence_ids`, `proposal_metrics`; the corresponding proposer stage/request in `stages` and request records.

The proposal correctly selects `hedge_25` with basis `highest_utility`, reports hold stress EUR2,666.44 and computes hedge utility as approximately −EUR4,999.06000055. It cites all five required utility components. One additional identifier is absent from the registry:

`case_04:action:escalate:escalation_pending`

The registered aggregate `case_04:action:escalate` does contain `escalation_pending`; no separate leaf identifier with the above name exists. The extra alias therefore invalidates the citation contract. Verification falls back to the same reference action. This is a concrete distinction between a reference-consistent decision and a strictly admissible evidence record.

Do not describe this result as an arithmetic error, a failed component citation, a wrong policy judgement or a critic repairing the single proposal. The other arms ran independently; their passing records are a case-level comparison, not a repair of this response.

## Challenger episodes

### Case01: confirmation with correct actor scope, but an admitted specialist-summary error

**Locator:** row `case_01--challenged`, `specialist_reports[credit_governance].report.summary`, its first finding, `initial_proposal`, `challenge.report`, and final `proposal.evidential`.

The critic requests no revision and correctly confirms hedge25 and the near-tie comparison. The initial and final proposals correctly distinguish missing CP-RETAIL credit in unauthorised B3 from known credit on authorised B13. No endpoint changes.

The mechanically admitted credit/governance report nevertheless contains a summary asserting a binding missing-credit issue for the authorised book. Its own detailed findings and the mandate say the relevant missing-credit positions are outside B13 authority. The final proposer explicitly rejects that summary-level implication. This is evidence that usable status does not certify semantic consistency; the proposer succeeds while treating advice as fallible. The critic did not identify or fix this issue because it received status metadata rather than the specialist body.

### Case02: a reporting requirement is confused with a decision rule

**Locator:** row `case_02--challenged`, initial `procedural`, `challenge.report.issues[0:2]`, final `economic`/`evidential`; challenger and revision request payloads in the same row's stages.

The initial proposer correctly abstains for relevant missing credit and supplies hold utility. The critic challenges the phrase that hold utility is used “as required for abstention”. The **decision rule** does not require an economic ranking before missing-credit abstention, but the **proposal output contract** explicitly requires a hold-utility claim for abstaining proposals. The statement is ambiguous; this is not evidence that the required numerical reporting was wrong. The critic is given its own output schema, the proposal and domain rules, not a separate copy of the full proposer reporting contract.

The critic also asks the proposer to qualify a statement about absent stress-scenario/model-validation detail because accepted report statuses do not reveal report contents. Status evidence is now present, so the EXP-007 missing-status mechanism has been repaired. However, the revision repeats a broader statement that specialist substantive findings are withheld. The revision request actually includes both accepted report bodies under `specialist_reports`, containing four and three findings. “This bundle” could narrowly mean the `evidence_bundle` subobject, but the wording is misleading if read as describing what the revision role received. It carries a critic-specific visibility limit into the author's account of its own available information.

The action, basis, numeric values and primary endpoint remain unchanged. This episode supports clearer separation of domain policy, reporting requirements and role-specific information availability; it does not establish useful correction of the decision.

### Case03: the critic identifies a real but sub-tolerance arithmetic discrepancy

**Locator:** row `case_03--challenged`, initial and final hold-utility numeric claim, `challenge.report.issues[0]`; private/visible hold component entries in `evaluation-packages.json`.

Direct calculation from the supplied components gives:

`−0.5 × 2267.72 − 0.35 × 3237.931466 − 0 − 50447.72 − 0 = −52714.8560131`

The initial proposer reports −52714.8550131, a EUR0.001 discrepancy. The critic's suggested value is **arithmetically correct**. The revision wrongly calls that correction incorrect and retains its initial value.

Both values fall within the prespecified numerical tolerance, so both initial and final proposals pass the same endpoint. There is no action or basis change. This is a correct critic observation that was not adopted, alongside an inaccurate narrative justification for rejecting it. Do not describe the critic as making a mistaken correction, or claim that the revision improves exact arithmetic. The tiny discrepancy's practical significance is not evaluated here.

### Case04: a broader documented comparison, with no endpoint improvement

**Locator:** row `case_04--challenged`, `challenge.report.issues[0]`, initial/final `numeric_claims` and `evidence_ids`.

The critic requests evidence for feasible alternatives omitted from the displayed ranking comparison. The initial proposal already selects the reference action with the correct basis and passes the minimum output contract. It explicitly reports utility values for hold and hedge25. The revision adds accurate utility values and their component citations for all seven feasible actions: hold, hedge25, hedge50, hedge75, roll, escalation and exception request.

This is an observable expansion of documented alternative coverage. It is a useful candidate example for the article, provided it is labelled as a targeted qualitative change. Exhaustive alternative coverage was not the prespecified primary contract; no action, basis or endpoint changes. Additional detail has not been tested for human usefulness, readability or general explanation quality.

## Self-review is not monotonically improving

**Locator:** row `case_04--self_review`, proposer and the four `self_review` stages; `proposal_stage_metrics`.

The initial proposal and first self-review pass satisfy the endpoint. The second review changes hedge25 utility from approximately −4999.06000055 to −4999.55900055, an error of about EUR0.499. That intermediate proposal fails numeric grounding. The third review restores the correct value and the fourth retains it. The selected action and basis do not change.

The other three self-review jobs retain passing measured outcomes throughout. This stage sequence should remain visible: a final4/4 result does not mean every additional review improved the proposal. It also shows why comparing only final outputs misses intermediate regressions.

## What the evidence supports for writing

The follow-up demonstrates that the repaired evidence handoff delivered all planned reports under the mechanical contract and that the configurations could compute policy-consistent decisions on these two contrast pairs. The specialist, challenged and self-review arms each avoid one citation-contract failure observed in the independent single-arm run. They do not improve raw action or policy-basis accuracy, which is16/16 across final proposals.

The critic's value is mixed at the trace level: one confirmation, one reporting/context confusion, one correct arithmetic challenge rejected by the reviser, and one expansion of explicit alternatives. The new context fields remove the earlier missing-status condition, but do not establish complete semantic understanding of role visibility or reporting obligations. All admitted findings and all primary passes must retain those limitations.

A defensible research contribution is the separation of component correctness, policy-basis accuracy, citation-contract compliance, handoff admissibility and narrative/process interpretation. The result does not demonstrate general multi-agent superiority, broad semantic faithfulness, a benefit from repairs alone, or that the new diagnostics were empirically harder at the decision-selection level. It does justify a more precise next evaluation of explanation coverage and the handling of valid challenges.
