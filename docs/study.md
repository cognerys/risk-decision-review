# The study

Do extra model roles improve a review of a risk decision, when every configuration is given the same evidence?

## Design

Four review configurations (`single`, `specialists`, `challenged`, `self_review`; see [design.md](design.md)) each review the same four cases once. That is 16 jobs and 56 model calls for a run.

The four cases are two contrast pairs, written before their reference answers were computed:

- **Authority.** Two cases with the same positions, one counterparty with missing credit, and a mandate that either does or does not cover the book holding that counterparty. The reference is to hedge in the first and to abstain for missing credit in the second.
- **Threshold.** Two cases built the same way with position sizes scaled by 0.91 or 1.07, which puts the two best actions either inside or outside the declared near-tie band. The reference is to abstain as a near-tie in the first and to hedge in the second.

Every configuration receives the same evidence. The final utility of each action is withheld: models are given the formula, the desk's weight and the components, and must calculate it. The reference answers and the computed utilities never enter a model request. This has been checked against the retained requests of both runs: all 112 carry the frozen visible bundle and no reference field or true utility value. The retained text has had secret-shaped strings redacted, so it is not byte-exact, and what the provider did with a request cannot be observed.

**Primary endpoint.** A job passes when the model's final proposal clears the form check and also has the reference action and the reference reason. The form check requires a well-formed reply, a feasible action or an abstention, only registered evidence identifiers, numbers within tolerance (EUR 0.01 or one part in a million, whichever is larger) and citations to all five components of the utility it calculated.

**Fallback.** A proposal that fails the form check is replaced by the deterministic reference action, and the record says so. The fallback does not consult the reference: a well-formed proposal with a different action would fail the endpoint but would not be replaced. That did not happen in either run.

**The reference rule for these cases.** Abstain if credit is missing for a counterparty on a position in a book the actor may trade. Otherwise rank feasible actions by utility, breaking exact ties by a fixed action order. Then find the next distinct utility, more than EUR 1 below the best, and abstain as a near-tie if it is within EUR 2,000 or 5% of the best. This differs from the scorecard's simpler near-tie rule for the sixteen standard cards, described in the [datasheet](datasheet.md).

The full [protocol](../experiments/protocol.md) was fixed before the first live response. A [note](../experiments/replication.md) fixed how the second run would be reported. It was written shortly before that run started; it is not hashed in the run's manifest, so that ordering rests on the file's time and this statement.

## Results

| Configuration | Calls | Run 1 passed | Run 2 passed | Run 1 input / output tokens | Run 2 input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `single` | 4 | 3 of 4 | 4 of 4 | 39,757 / 3,177 | 39,757 / 3,378 |
| `specialists` | 12 | 4 of 4 | 4 of 4 | 125,008 / 10,121 | 123,801 / 9,774 |
| `challenged` | 20 | 4 of 4 | 2 of 4 | 217,535 / 15,511 | 218,334 / 16,371 |
| `self_review` | 20 | 4 of 4 | 4 of 4 | 208,472 / 17,297 | 209,851 / 19,185 |

Run 1 is `experiments/results/2026-11-14-specialists-live-v2/` (14 November 2026), made from the private research repository before this one was separated from it. Run 2 is `experiments/results/2026-11-15-replication-live/` (15 November 2026), made from the cleaned code that became this repository. The run's manifest records a working commit that was later squashed into this repository's single commit, so its recorded head cannot be resolved here; the source snapshot inside the run is the authority, and the files on the study path match the current ones by hash. The review graph module is byte-identical to run 1's. The prompts, schemas, cases and checks are the same; module names differ, the runner gained a label argument, and three `langgraph` packages moved by a patch version between the runs. Both used `gpt-6-luna` at low reasoning effort with an output allowance of 1,800 tokens per call.

The model's own final proposal matched the reference action and reason in 16 of 16 jobs in run 1 and 15 of 16 in run 2. After fallback (one job in run 1, two in run 2), all 16 jobs in each run ended on the reference action. The two runs are reported side by side and not pooled, because they share the same four cases.

### The failures

| Run | Job | What failed |
| --- | --- | --- |
| 1 | `single`, case 4 | Correct action, reason and utility. Cited an escalation-status field under an identifier the evidence dictionary does not register. |
| 2 | `challenged`, case 4 | The same kind of unregistered citation, to the pending-status fields of two actions. It was in the first proposal; the challenger asked for no revision, and the revision kept it. |
| 2 | `challenged`, case 1 | The first proposal passed every check. The challenger raised two issues: it asked the proposer to withdraw a statement about specialist findings (which the challenger cannot see but the proposer can), and to give utility evidence for every feasible action or qualify the ranking. The revision that followed spent its whole 1,800-token allowance on reasoning and returned no text. |
| 2 | `specialists`, case 2 | The credit and governance report was valid JSON followed by a full stop, so the strict parser rejected it. The proposer, without that report, still passed. This was a handoff failure, not a failed job. |

Three jobs failed the endpoint across the two runs. The fourth row is a failed handoff inside a job that passed: 15 of 16 specialist reports were admitted in run 2, against 16 of 16 in run 1.

### What the challenger did

In run 1, on case 4, the challenger asked for fuller evidence behind the claim that the chosen action had the highest utility. The revision expanded its numeric claims from two actions to all seven feasible ones, correctly. The proposal had already passed, so the endpoint did not move.

In run 2, on case 1, a challenge that included a request of the same kind was followed by the empty revision described above, which replaced a passing proposal with a failure. The record shows the order of events, not the cause. Long replies sat close to the 1,800-token allowance in both runs.

In run 1 a challenger found a real arithmetic discrepancy of one thousandth of a euro, and the reviser wrongly rejected the correction. Both values were inside the tolerance, so the endpoint did not move. In run 2, on case 3, a challenger raised a discrepancy of the same size; it was right and the revision adopted it. A second error of the same size in the same proposal was not raised and remains in the final answer. In run 2, on case 4, the challenger did not raise the unregistered citations, although citations are among the things it is asked to check.

In run 1 the self-review configuration introduced a utility error of about half a euro on its second pass and corrected it on a later one. Only the intermediate records show that. Run 2's self-review passes all passed.

Run 1 also has a [qualitative review](../experiments/results/2026-11-14-specialists-live-v2/analysis/qualitative-review.md) of the traces. Run 2 has had only a bounded reading of its challenger episodes and self-review numbers, not a review of the prose.

## What this supports

- With the same evidence, the configurations reached the same action. Extra roles changed how much was written and how much it cost, not what was decided.
- Run-to-run variation was as large as the variation between configurations: the largest change between runs was two jobs, and the largest gap between configurations was one job in run 1 and two in run 2. Each run alone gives a different ordering.
- No failure was a wrong action. They were a citation vocabulary the models occasionally stepped outside, an output allowance and a strict parser. Those are properties of the harness as much as of the models, and a review system will have its own. The empty revision leaves nothing to judge either way.
- A challenge is not free. One was followed by a better answer and one by an empty one.
- Fallback makes every job look right at the end. A review that keeps only final answers cannot tell a model's answer from a substituted one.

## What it does not support

- Any ranking of the configurations. Two runs of four cases are far too few, and the two runs share the same cases, so they are repeated observations and not eight independent ones.
- Any claim about real desks. The cases, the policy and the data are invented, and the reference is a declared rule, not validated judgement.
- Any claim that an explanation is faithful or useful. The checks cover structure, identifiers and stated numbers. No person assessed the explanations.
- Any claim about models in general. One model, one setting, one output allowance.

## What a larger study would need

More and independent cases; several runs of each, reported with their spread; a primary outcome chosen in advance; an output allowance that does not decide results; a separate measure of whether a challenge was justified and whether a valid correction was adopted; and a reviewer study if usefulness is to be claimed.
