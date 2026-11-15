# Datasheet — Northfold synthetic decision cards

This fixture is synthetic research data for a risk-desk rehearsal. It is not a price history, not an order book, and not a judgement of whether a real person was negligent.

## Purpose

Each row is one post-trade decision situation at a fictional merchant, Northfold Energy. The visible sheet is everything an agent may see. The sealed sheet holds a realised P&L and, where relevant, a forecast that had not been issued at `as_of`. The scorecard compares feasible actions with a declared utility. Agreement with that scorecard is not actor-information defensibility.

## Generation

`src/risk_desk/data/panel.py` draws 60 daily simple returns per regime with numpy Generator seed 42 and writes `src/risk_desk/data/fixtures/returns.json`. Scoring reads the file. It does not draw again.

Ordinary daily vols are 0.004, 0.0035, and 0.003 for power, gas, and carbon, with correlations 0.60, 0.30, and 0.20. The cold-spell regime is 0.045, 0.040, and 0.020 with correlations 0.85, 0.40, and 0.25. The correlation-break regime is 0.030, 0.030, and 0.025 with correlations 0.05, −0.20, and 0.00.

Named stress shocks, as simple returns: ordinary −0.004 / −0.003 / −0.002; cold spell −0.12 / −0.10 / −0.04; correlation break −0.08 / +0.06 / −0.05. A down shock hurts a long position. Spreads are 0.004 in normal liquidity and 0.018 when liquidity is thin. A roll pays half the spread.

The ordinary regime is calm so that hedge transaction cost can exceed the tail benefit. That is a property of these parameters, not a market fact.

## Utility

For desk lambda λ:

```
U = -0.5 * stress_loss - λ * cvar_95 - liquidity_cost - governance_penalty - tenor_penalty
```

Lambdas: power hedge 0.35, gas procurement 0.45, retail supply 0.55, proprietary 0.15.

`governance_penalty` is 0 when post-action VaR and stress are inside both limits. Otherwise it is 50,000 EUR plus the summed positive excess.

`tenor_penalty` is 10,000 EUR when more than 70% of the dominant commodity's absolute financial quantity delivers within 35 days of `as_of`. A hedge scales near and far together, so it does not remove this penalty. `roll_near_to_far` moves half the near-month net quantity into the far bucket and leaves total delta unchanged.

VaR is the positive part of the empirical 5% loss on the 60-day panel (`empirical_pnl_quantile_v1`). CVaR is the positive part of the mean loss on that tail. This is not a commercial ETRM VaR.

## Actions and abstention

The action names are: `hold`, `hedge_25`, `hedge_50`, `hedge_75`, `reduce_25`, `reduce_50`, `roll_near_to_far`, `escalate`, `request_limit_exception`.

`reduce_*` is illegal on a book that contains a physical supply obligation. A hedge in the obligation's commodity lifts `physical_hedge_ratio` toward 0.98 by that hedge's fraction of the remaining gap, and never above 0.98. `escalate` and `request_limit_exception` do not change exposure and do not clear a breach.

An observer role can be shown the book and cannot send a market action. A trader cannot hedge a book outside `may_trade_books`. Missing credit on a counterparty the action would resize blocks those market actions, and the scorecard abstains with `missing_credit`. Missing credit is unknown, not safe. A near-tie (gap under 5% of the best absolute utility, or under 2,000 EUR) abstains with `near_tie`. If a breach remains and no feasible action reduces VaR or stress, the scorecard recommends `escalate` and says exposure is unchanged.

## What a row is not

There are no options, no real venue prices, no JEPA embeddings, and no human ratings. Sixteen cards reuse eight books and about forty positions. Repeating a book across cards is not sixteen independent market days. The sealed realised P&L on `hindsight_trap` is planted so that a later profit can disagree with the ex ante score. It is never shown to a model.
