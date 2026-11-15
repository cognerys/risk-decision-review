# The study

Do extra model roles improve a review of a risk decision, when every configuration is given the same evidence?

## Design

Four review configurations (`single`, `specialists`, `challenged`, `self_review`; see [design.md](design.md)) each review the same four cases once. That is 16 jobs and 56 model calls for a run.

The four cases are two contrast pairs, written before their reference answers were computed:

- **Authority.** Two cases with the same positions, one counterparty with missing credit, and a mandate that either does or does not cover the book holding that counterparty. The reference is to hedge in the first and to abstain for missing credit in the second.
- **Threshold.** Two cases built the same way with position sizes scaled by 0.91 or 1.07, which puts the two best actions either inside or outside the declared near-tie band. The reference is to abstain as a near-tie in the first and to hedge in the second.

Every configuration receives the same evidence. The final utility of each action is withheld: models are given the formula, the desk's weight and the components, and must calculate it. The reference answers and the computed utilities never enter a model request. This is checked from the retained requests.

**Primary endpoint.** A job passes when the model's final proposal has the reference action and the reference reason, cites only registered evidence identifiers, states numbers within tolerance, and cites all five components of the utility it calculated. A proposal that fails is replaced by the deterministic reference action ("fallback"), and the record says so.

The full [protocol](../experiments/protocol.md) was fixed before the first live response. A [note](../experiments/replication.md) written before the second run fixed how it would be reported.

## Results

| Configuration | Calls | Run 1 passed | Run 2 passed | Run 1 input / output tokens | Run 2 input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `single` | 4 | 3 of 4 | 4 of 4 | 39,757 / 3,177 | 39,757 / 3,378 |
| `specialists` | 12 | 4 of 4 | 4 of 4 | 125,008 / 10,121 | 123,801 / 9,774 |
| `challenged` | 20 | 4 of 4 | 2 of 4 | 217,535 / 15,511 | 218,334 / 16,371 |
| `self_review` | 20 | 4 of 4 | 4 of 4 | 208,472 / 17,297 | 209,851 / 19,185 |

Run 1 is `experiments/results/2026-11-14-specialists-live-v2/` (14 November 2026), made from the private research repository before this one was separated from it. Run 2 is `experiments/results/2026-11-15-replication-live/` (15 November 2026), made from this repository's code. The prompts, schemas, cases and checks are the same; module names differ. Both used `gpt-6-luna` at low reasoning effort with an output allowance of 1,800 tokens per call.

The model's own final proposal matched the reference action and reason in 31 of 32 jobs. After fallback, all 32 jobs ended on the reference action.

### The failures

| Run | Job | What failed |
| --- | --- | --- |
| 1 | `single`, case 4 | Correct action, reason and utility. Cited an escalation-status field under an identifier the evidence dictionary does not register. |
| 2 | `challenged`, case 4 | The same kind of unregistered citation, to the pending-status fields of two actions. It was in the first proposal; the challenger asked for no revision, and the revision kept it. |
| 2 | `challenged`, case 1 | The first proposal passed every check. The challenger asked for utility evidence on every feasible action. The revision spent its whole 1,800-token allowance on reasoning and returned no text. |
| 2 | `specialists`, case 2 | The credit and governance report was valid JSON followed by a full stop, so the strict parser rejected it. The proposer, without that report, still passed. This was a handoff failure, not a failed job. |

Three jobs failed the endpoint across the two runs. The fourth row is a failed handoff inside a job that passed: 15 of 16 specialist reports were admitted in run 2, against 16 of 16 in run 1.

### What the challenger did

In run 1, on case 4, the challenger asked for fuller evidence behind the claim that the chosen action had the highest utility. The revision expanded its numeric claims from two actions to all seven feasible ones, correctly. The proposal had already passed, so the endpoint did not move.

In run 2, on case 1, a request of the same kind ended in the empty revision described above, replacing a passing proposal with a failure.

In run 1 a challenger found a real arithmetic discrepancy of one thousandth of a euro, and the reviser wrongly rejected the correction. Both values were inside the tolerance, so the endpoint did not move. A challenger raised a discrepancy of the same size in run 2; whether that correction was right and whether it was adopted has not been reviewed.

In run 1 the self-review configuration introduced a utility error of about half a euro on its second pass and corrected it on a later one. Only the intermediate records show that.

Run 1 also has a [qualitative review](../experiments/results/2026-11-14-specialists-live-v2/analysis/qualitative-review.md) of the traces. Run 2 has not had one.

## What this supports

- With the same evidence, the configurations reached the same action. Extra roles changed how much was written and how much it cost, not what was decided.
- Run-to-run variation was larger than the variation between configurations. A single run of this study would have given a misleading ordering either way round.
- The failures were of form: a citation vocabulary the models occasionally stepped outside, an output allowance, a strict parser. Those are properties of the harness as much as of the models, and a review system will have its own.
- A challenge is not free. It can prompt a better answer and it can prompt a longer one that fails.
- Fallback makes every job look right at the end. A review that keeps only final answers cannot tell a model's answer from a substituted one.

## What it does not support

- Any ranking of the configurations. Two runs of four cases are far too few, and the two runs share the same cases, so they are repeated observations and not eight independent ones.
- Any claim about real desks. The cases, the policy and the data are invented, and the reference is a declared rule, not validated judgement.
- Any claim that an explanation is faithful or useful. The checks cover structure, identifiers and stated numbers. No person assessed the explanations.
- Any claim about models in general. One model, one setting, one output allowance.

## What a larger study would need

More and independent cases; several runs of each, reported with their spread; a primary outcome chosen in advance; an output allowance that does not decide results; a separate measure of whether a challenge was justified and whether a valid correction was adopted; and a reviewer study if usefulness is to be claimed.
