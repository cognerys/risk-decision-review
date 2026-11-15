# Specialist-role pilot: results and recount

Run `20261114T104952Z-50766afe`. live; 16/16 jobs completed; 56 calls. No planned metric was changed after observing results.

The source snapshot and all recorded initial/final proposal metrics reproduce. Counts below use all four planned jobs per arm. Grounding is the specified structural/numeric contract; reference agreement is authored scorecard consistency.

| Arm | Grounded proposals / 4 | Grounded policy matches / 4 | Raw reference matches / 4 | Fallbacks | Calls | Input / output units | Job time (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| single | 3 | 3 | 4 | 1 | 4 | 39757 / 3177 | 27.1 |
| specialists | 4 | 4 | 4 | 0 | 12 | 125008 / 10121 | 85.3 |
| challenged | 4 | 4 | 4 | 0 | 20 | 217535 / 15511 | 139.8 |
| self_review | 4 | 4 | 4 | 0 | 20 | 208472 / 17297 | 144.5 |

Usage units are provider-reported tokens, including any reasoning output accounted for by the provider. Time is summed observed job latency, not a controlled speed benchmark. No monetary cost is inferred. Missing usage remains null in the analysis JSON.

## Case-level proposed actions

| Card | Reference | Single | Specialists | Challenged | Self-review |
| --- | --- | --- | --- | --- | --- |
| case_01 | hedge_25 | hedge_25 / highest_utility (contract pass) | hedge_25 / highest_utility (contract pass) | hedge_25 / highest_utility (contract pass) | hedge_25 / highest_utility (contract pass) |
| case_02 | abstain | abstain / missing_credit (contract pass) | abstain / missing_credit (contract pass) | abstain / missing_credit (contract pass) | abstain / missing_credit (contract pass) |
| case_03 | abstain | abstain / near_tie (contract pass) | abstain / near_tie (contract pass) | abstain / near_tie (contract pass) | abstain / near_tie (contract pass) |
| case_04 | hedge_25 | hedge_25 / highest_utility (contract fail) | hedge_25 / highest_utility (contract pass) | hedge_25 / highest_utility (contract pass) | hedge_25 / highest_utility (contract pass) |

## Paired results

| Comparison | Contract wins / losses / ties | Grounded-policy wins / losses / ties | Incomplete pairs |
| --- | --- | --- | --- |
| specialists-minus-single | 1 / 0 / 3 | 1 / 0 / 3 | 0 |
| challenged-minus-specialists | 0 / 0 / 4 | 0 / 0 / 4 | 0 |
| challenged-minus-self_review | 0 / 0 / 4 | 0 / 0 / 4 | 0 |

## Within-job challenger revisions

- `case_01`: hedge_25 → hedge_25; contract change +0; grounded-reference change +0. Usable critique: True.
- `case_02`: abstain → abstain; contract change +0; grounded-reference change +0. Usable critique: True.
- `case_03`: abstain → abstain; contract change +0; grounded-reference change +0. Usable critique: True.
- `case_04`: hedge_25 → hedge_25; contract change +0; grounded-reference change +0. Usable critique: True.

## Handoff outcomes

Usable reports: 16/16 planned; fully valid: 16/16. Accepted findings: 60/60 parsed emitted findings. Reports with unreliable finding counts: 0.

## Interpretation boundaries

One stochastic pass on four composed cases from two contrast pairs does not establish general benefit, statistical significance, explanation faithfulness or real-desk usefulness. The two five-call workflows differ in context, tokens and intermediate paths. The pilot compares configurations with full precomputed evidence; it is not a test of autonomous tool discovery or human approval. Structured numeric checks cover the emitted claim fields, not every factual statement in prose. Full traces retain the detail needed for separately labelled qualitative review.

EXP-007 and this follow-up change cases, evidence presentation, schema and handoff policy. Their scores do not isolate a causal repair effect; use matched arms within EXP-008.
