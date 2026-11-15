# Risk desk design contract

Synthetic research software. It reviews post-trade energy-risk actions. It does not send orders, and it is not evidence about a real desk.

The scientific target is the doctoral question this software serves: given a decision log like one an energy trading and risk management system would hold, can we evaluate whether a risk action was defensible at the time, compare it with plausible alternatives, and explain the assessment faithfully? This repository addresses a small part of that question. The action names below follow the contract used across the wider research project.

Three judgements stay separate in every schema, prompt, and report:

1. Realised P&L. A later outcome. Never an input to a tool or a default prompt.
2. Simulator-relative regret. Utility of the chosen feasible action versus the best feasible action, under the declared weights and the visible information.
3. Actor-information defensibility. Not established by this app. Do not use that phrase as a label the model emits.

Procedural, economic, and evidential findings are separate fields. A pending escalation is not approval and does not change exposure. Missing credit is unknown, not safe.

## Action contract

The action names:

`hold`, `hedge_25`, `hedge_50`, `hedge_75`, `reduce_25`, `reduce_50`, `roll_near_to_far`, `escalate`, `request_limit_exception`.

Effects, applied to the book the actor is allowed to touch:

| Action | Exposure | Other |
|---|---|---|
| `hold` | unchanged | |
| `hedge_25/50/75` | multiplies the dominant financial commodity delta by 0.75 / 0.50 / 0.25 | pays liquidity cost on the hedged notional; if a physical obligation in that commodity is present, also lifts `physical_hedge_ratio` toward 0.98 by the same fraction of the unhedged gap |
| `reduce_25/50` | multiplies absolute net financial delta by 0.75 / 0.50, sign preserved | illegal when the book contains a `physical_supply_obligation` |
| `roll_near_to_far` | total commodity delta unchanged; moves half of the nearest-month net quantity into the next season bucket | smaller liquidity cost |
| `escalate` | unchanged | sets `escalation_pending`; does not clear a breach |
| `request_limit_exception` | unchanged | sets `exception_pending`; does not clear a breach |

Dominant commodity is the one with the largest absolute net financial delta. Physical obligations do not count as financial delta.

## Information contract

A decision card has a visible sheet and a sealed sheet. Tools and prompts accept only the visible sheet plus engine evidence built from it. The sealed sheet holds `realised_pnl_eur`, any latent regime name, and forecast values whose issue time is after `as_of`. The generator strips those forecast values from the visible market context and sets `forecast_visible` false.

Evidence records carry `evidence_id`, `kind`, `method`, `units`, and `value`. Model prose may cite those ids. It may not introduce a numeric risk figure that is absent from the evidence bundle.

## Desk and books

Fictional merchant `Northfold Energy`. Desks: `power_hedge`, `gas_procurement`, `retail_supply`, `proprietary`. Commodities: `power`, `gas`, `carbon`. Instruments: `forward`, `swap`, `physical_supply_obligation`. Currency EUR. Power and gas quantities are MWh. Carbon is tonnes. Eight books, about forty positions, three market regimes: `ordinary`, `cold_spell_thin_liquidity`, `correlation_break`. Sixteen decision cards.

Mandates: an actor may change only books in `may_trade_books`. The proprietary actor cannot hedge the retail book.

## Engine

Deterministic. No network. A fixed return panel of 60 business days per regime lives in the fixture, with columns for power, gas, and carbon simple returns. Portfolio P&L for a day is the sum over financial positions of `quantity * price * return`. Empirical 95% VaR is the negative of the 5% quantile of that P&L (a loss is positive). CVaR is the negative of the mean of the P&L values at or below that quantile. Stress is P&L under a named shock vector stored beside the panel. Document the method string on every evidence row: `empirical_pnl_quantile_v1`.

This is a transparent proxy. It is not a commercial ETRM VaR.

Liquidity cost = hedged or reduced notional times the regime spread (thin liquidity is wider). Roll cost is half the hedge spread.

Utility, stated as an assumption:

```
U = -0.5 * remaining_stress_loss - lambda * cvar_95 - liquidity_cost - governance_penalty - tenor_penalty
```

Lambdas: power_hedge 0.35, gas_procurement 0.45, retail_supply 0.55, proprietary 0.15.

`governance_penalty` is 0 when the post-action book is inside both limits. It is `50_000 + excess` when a VaR or stress breach remains. Escalation and exception requests do not remove the penalty.

Hard infeasibility is applied before scoring: unknown action, book outside the mandate, `reduce_*` on a physical obligation, hedge or reduce that would increase exposure to a counterparty whose credit is missing, credit utilisation already above the limit when the action increases that exposure. If credit status is `missing` and the action changes financial exposure, the scorecard abstains instead of treating the name as safe. `hold` and `escalate` remain available in that case. The economic recommendation is `abstain` with reason `missing_credit`.

Near-tie: if the best and second feasible utilities differ by less than 5% of the absolute value of the best utility, or by less than 2_000 EUR, the scorecard abstains with reason `near_tie`.

Zero net exposure has zero incremental hedge cost and zero VaR contribution from that book.

## Review configurations

Every configuration receives the same evidence bundle, built by code from the visible sheet: positions, limits, credit, mandate, and the consequences of each action. No model can call a tool, see the scorecard's answer or see the reference used to score it.

- `single`: one proposing model. One call.
- `specialists`: a market and physical-risk specialist and a credit and governance specialist each report; code checks each report before passing it on; then the proposer. Three calls.
- `challenged`: `specialists`, then a separate reviewer challenges the proposal against the original evidence, then the proposer revises or confirms once. Five calls.
- `self_review`: the proposer re-reads its own proposal four times with no outside advice. Five calls. It is the control for `challenged`: the same number of calls without the extra roles.

Code then verifies the final proposal: schema, feasibility, that every cited identifier exists, and that stated numbers match the evidence. A proposal that fails falls back to the deterministic scorecard's action, and the record says so.

Model id: `RISK_DESK_MODEL`, default `gpt-6-luna`. `OPENAI_API_KEY` comes from the environment. Live calls run only when `RISK_DESK_LIVE=1`. Tests use a scripted model and never call a network.

Tracing: a JSONL mirror is appended under `runs/`. LangSmith tracing is used only when `LANGSMITH_TRACING` and `LANGSMITH_API_KEY` are set. The API key is never logged.

## Repository layout

Package `risk_desk` under `src/`. Tests in `tests/`. The study protocol, runner and analysis in `experiments/`; retained runs in `experiments/results/`. The data is described in `docs/datasheet.md`.
