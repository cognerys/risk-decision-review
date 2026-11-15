"""Action set, desk lambdas, near-tie band, and governance penalty base.

See docs/design.md. Scoring is not implemented here.
"""

from __future__ import annotations

ACTIONS = (
    "hold",
    "hedge_25",
    "hedge_50",
    "hedge_75",
    "reduce_25",
    "reduce_50",
    "roll_near_to_far",
    "escalate",
    "request_limit_exception",
)

DESKS = (
    "power_hedge",
    "gas_procurement",
    "retail_supply",
    "proprietary",
)

# U = -0.5 * remaining_stress_loss - lambda * cvar_95 - liquidity_cost - governance_penalty
DESK_LAMBDAS = {
    "power_hedge": 0.35,
    "gas_procurement": 0.45,
    "retail_supply": 0.55,
    "proprietary": 0.15,
}

# Abstain when best and second feasible utilities differ by less than 5% of
# abs(best), or by less than 2000 EUR.
NEAR_TIE_FRACTION = 0.05
NEAR_TIE_EUR = 2_000
NEAR_TIE_BAND = (NEAR_TIE_FRACTION, NEAR_TIE_EUR)

# Base only. A remaining VaR or stress breach adds the excess on top.
GOVERNANCE_PENALTY_BASE = 50_000
