# Risk decision review

Research software for reviewing post-trade energy risk decisions, and for testing what extra model roles add to such a review.

It comes from Gary Morris's doctoral research at the University of Bath, which asks: given a decision log like one an energy trading and risk management system would hold, can we evaluate whether a risk action was defensible at the time, compare it with plausible alternatives, and explain the assessment faithfully? This repository covers one small, inspectable part of that question. It is maintained by [Cognerys](https://cognerys.com).

Everything here is synthetic. The merchant, books, prices and decision policy are invented. It is not investment advice, it sends no orders, and it says nothing about a real desk.

## What it does

A fictional merchant, Northfold Energy, has eight books of power, gas and carbon positions. A **decision card** describes one situation an actor on a desk faces: the positions, the limits, the credit status of counterparties and what that actor is allowed to trade.

1. **Code works out the consequences.** For each of nine possible actions (hold, three sizes of hedge, two sizes of reduction, a roll, an escalation, a limit-exception request) a deterministic engine calculates the risk, the cost and whether the action is allowed. A declared utility ranks them. This ranking is the reference; it is a stated assumption, not a validated view of good trading.
2. **Models propose and explain.** A language model reads the same evidence and proposes an action, citing the evidence it relied on.
3. **Code checks the proposal.** The cited identifiers must exist, the action must be feasible and each stated number must match the value code holds. A proposal that fails this check is replaced by the reference action, and the record says that happened. The check never looks at whether the action agrees with the reference; that comparison is made separately when a study is scored.

The same card can be run through four **review configurations**:

| Configuration | What runs | Model calls |
| --- | --- | ---: |
| `single` | One proposer | 1 |
| `specialists` | A market and physical-risk specialist and a credit and governance specialist report, then the proposer | 3 |
| `challenged` | `specialists`, then a separate reviewer challenges the proposal and the proposer revises once | 5 |
| `self_review` | The proposer re-reads its own proposal four times, with no outside advice | 5 |

`self_review` is the control for `challenged`: the same number of calls without the extra roles.

## What the study found

Two live runs of the same frozen [protocol](experiments/protocol.md): four authored cases, each run once through all four configurations. A job passes when the model's final proposal clears that check (valid citations, correct numbers) and also has the reference action and reason.

| Configuration | Model calls per run | Passed, run 1 (14 Nov 2026) | Passed, run 2 (15 Nov 2026) |
| --- | ---: | ---: | ---: |
| `single` | 4 | 3 of 4 | 4 of 4 |
| `specialists` | 12 | 4 of 4 | 4 of 4 |
| `challenged` | 20 | 4 of 4 | 2 of 4 |
| `self_review` | 20 | 4 of 4 | 4 of 4 |

- **The extra roles did not change the decision.** The model's own final proposal chose the reference action for the reference reason in 16 of 16 jobs in run 1 and 15 of 16 in run 2. The one exception returned no usable reply at all.
- **The difference between two runs was as large as the difference between configurations.** In run 1 the single proposer was the only configuration whose final proposal failed a check. In run 2 it passed everything and the most elaborate configuration failed twice. Either run alone gives a different ordering.
- **No failure was a wrong action.** Two were a citation to a field the evidence dictionary does not register. One was a revision that used its whole output allowance on reasoning and returned no text; it came after a challenge that raised two issues, one of them a request to cover every alternative or qualify the ranking, and it replaced a proposal that had already passed. One specialist report was rejected because a full stop followed otherwise valid JSON.
- **A challenge did not reliably help.** In run 1 a request of the same kind was followed by a fuller, correct answer. In run 2 it was followed by an empty one, and the challenger did not raise the bad citation in the other failing case.
- **The final answer hides all of this.** Code replaced each proposal that failed the check with the reference action (one in run 1, two in run 2), so all 16 jobs in each run ended on the reference action. Only the intermediate records show which answers came from a model.

Two runs of four cases cannot rank the configurations. What they do show is that a single run of a small study is not enough to claim an extra role helps, and that a review needs its intermediate records kept. [docs/study.md](docs/study.md) has the detail, and both runs are in `experiments/results/` with every request and response.

## Three judgements that stay separate

- **Realised profit or loss** is a later outcome. It is sealed away from every model and is not the verdict.
- **Agreement with the reference** means a proposal matched the declared utility ranking on the information visible at the time.
- **Whether the decision was defensible** given what the actor knew is the doctoral question. This software does not establish it.

## Try it

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The tests run offline and never call a model.

```bash
risk-desk scorecard cold_spell_power        # the deterministic reference for one card
risk-desk run --card credit_missing         # one card through the challenged configuration, offline
risk-desk view                              # draw the configurations at http://127.0.0.1:8765
```

Offline runs use a scripted model whose reply deliberately fails the checks, so they show the fallback path. To use a real model, set `OPENAI_API_KEY` and `RISK_DESK_LIVE=1`; that makes paid API calls. [docs/usage.md](docs/usage.md) covers the command line, the viewer, LangGraph Studio and running the study.

## Reproduce the study

```bash
python experiments/run_study.py            # offline dry run, no cost
python experiments/run_study.py --live --experiment MY-RUN --output-dir experiments/results/my-run
```

A live run makes at most 56 model calls. Read the [protocol](experiments/protocol.md) first. Model output is not deterministic, so your counts may differ from ours; that is itself worth knowing.

## Where things are

| Path | What it holds |
| --- | --- |
| `src/risk_desk/engine/` | The deterministic scorecard: risk figures, action consequences, the reference ranking |
| `src/risk_desk/graphs/review.py` | The four review configurations, the handoff checks and the proposal checks |
| `src/risk_desk/data/` | The sixteen decision cards, the four study cases and the fixed return panel |
| `src/risk_desk/viewer/` | The local graph page |
| `experiments/` | The study protocol, runner, analysis and retained runs |
| `docs/study.md` | The study, its results and what they do and do not support |
| `docs/design.md` | The contracts: actions, information, engine, configurations |
| `docs/datasheet.md` | How the synthetic data was made and what it is not |

## Limits

- Four authored cases in two contrast pairs. They are not a benchmark, a sample of a market or evidence about real desks.
- The checks cover structure, feasibility, cited identifiers and stated numbers. They do not establish that every sentence a model wrote is true or useful.
- No person reviewed the explanations. Whether they help a reviewer is untested.
- This repository holds the current study only. Earlier generations of the graph and their pilot runs are kept in the private research record.

## Licence and citation

Code and documentation are under the [MIT licence](LICENSE). To cite the software or its results, see [CITATION.cff](CITATION.cff).
