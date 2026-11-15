"""Visible card, sealed sheet, and recommendation models.

The sealed sheet is not a field of ``DecisionCardVisible``.
See docs/design.md.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Action = Literal[
    "hold",
    "hedge_25",
    "hedge_50",
    "hedge_75",
    "reduce_25",
    "reduce_50",
    "roll_near_to_far",
    "escalate",
    "request_limit_exception",
]
Desk = Literal["power_hedge", "gas_procurement", "retail_supply", "proprietary"]
Commodity = Literal["power", "gas", "carbon"]
Instrument = Literal["forward", "swap", "physical_supply_obligation"]
CreditStatus = Literal["known", "missing", "downgraded"]
Regime = Literal["ordinary", "cold_spell_thin_liquidity", "correlation_break"]
Volatility = Literal["low", "medium", "high"]
Liquidity = Literal["normal", "thin"]
RiskAppetite = Literal["low", "medium", "high"]
ActionOrAbstain = Action | Literal["abstain"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(_Strict):
    position_id: str
    book_id: str
    desk: Desk
    commodity: Commodity
    instrument: Instrument
    delivery_start: str
    delivery_end: str
    quantity: float
    price_eur: float
    counterparty_id: str | None = None
    physical_hedge_ratio: float | None = Field(default=None, ge=0, le=0.98)


class CreditLine(_Strict):
    counterparty_id: str
    status: CreditStatus
    limit_eur: float | None = None
    utilisation_eur: float | None = None
    collateral_eur: float

    @model_validator(mode="after")
    def _limits_null_only_when_missing(self) -> CreditLine:
        if self.status != "missing" and (
            self.limit_eur is None or self.utilisation_eur is None
        ):
            raise ValueError(
                "limit_eur and utilisation_eur may be null only when status is missing"
            )
        return self


class MarketVisible(_Strict):
    as_of: str
    regime: Regime
    prices: dict[str, float]
    volatility: Volatility
    liquidity: Liquidity
    weather: dict[str, Any]
    gas_power_correlation: float
    forecast_visible: bool


class Mandate(_Strict):
    actor_id: str
    role: str
    desk: Desk
    may_trade_books: list[str]
    risk_appetite: RiskAppetite


class Limits(_Strict):
    var_limit_eur: float
    stress_limit_eur: float


class DecisionCardVisible(_Strict):
    card_id: str
    mandate: Mandate
    market: MarketVisible
    positions: list[Position]
    credit: list[CreditLine]
    limits: Limits
    logged_action: Action | None = None


class SealedSheet(_Strict):
    card_id: str
    realised_pnl_eur: float
    latent_regime: str
    hidden_forecast_value: float | None = None


class Evidence(_Strict):
    evidence_id: str
    kind: str
    method: str
    units: str
    value: Any
    book_id: str | None = None

    @field_validator("value")
    @classmethod
    def _value_is_json_safe(cls, value: Any) -> Any:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON-safe") from exc
        return value


class Recommendation(_Strict):
    card_id: str
    arm: str
    action_or_abstain: ActionOrAbstain
    reason: str
    procedural: str
    economic: str
    evidential: str
    evidence_ids: list[str]
    escalation_pending: bool
