"""Deterministic scorecard. It never reads a sealed sheet."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np

from risk_desk.data.panel import SPREADS, load_panel
from risk_desk.policy import (
    ACTIONS,
    DESK_LAMBDAS,
    GOVERNANCE_PENALTY_BASE,
    NEAR_TIE_EUR,
    NEAR_TIE_FRACTION,
)
from risk_desk.schemas import DecisionCardVisible, Evidence, Position, Recommendation

METHOD = "empirical_pnl_quantile_v1"
MARKET_ACTIONS = {
    "hedge_25",
    "hedge_50",
    "hedge_75",
    "reduce_25",
    "reduce_50",
    "roll_near_to_far",
}
DELTA_MULTIPLIER = {
    "hedge_25": 0.75,
    "hedge_50": 0.50,
    "hedge_75": 0.25,
    "reduce_25": 0.75,
    "reduce_50": 0.50,
}
HEDGE_FRACTION = {"hedge_25": 0.25, "hedge_50": 0.50, "hedge_75": 0.75}
COMMODITY_ORDER = ("power", "gas", "carbon")
TENOR_SHARE = 0.70
TENOR_PENALTY_EUR = 10_000.0
NEAR_DAYS = 35


@dataclass
class Transition:
    action: str
    feasible: bool
    reason: str
    quantities: dict[str, float]
    hedge_ratios: dict[str, float]
    liquidity_cost: float
    escalation_pending: bool
    exception_pending: bool
    net_delta: dict[str, float]
    near_quantity: dict[str, float]
    var_95: float
    cvar_95: float
    stress_loss: float
    tenor_penalty: float
    governance_penalty: float
    utility: float | None
    breach: bool
    evidence: list[Evidence] = field(default_factory=list)


def visible_payload(card: DecisionCardVisible) -> str:
    return card.model_dump_json()


def evidence_for(card: DecisionCardVisible) -> list[Evidence]:
    base = apply_action(card, "hold")
    rows = list(base.evidence)
    rows.append(
        _evidence(
            card,
            "feasible_actions",
            feasible_actions(card),
            "list",
            "Action names that pass the mandate, physical, and credit checks.",
        )
    )
    return rows


def feasible_actions(card: DecisionCardVisible) -> list[str]:
    return [action for action in ACTIONS if apply_action(card, action).feasible]


def scorecard(card: DecisionCardVisible) -> Recommendation:
    """Rank feasible actions. Missing credit and near-ties abstain."""
    transitions = [apply_action(card, action) for action in ACTIONS]
    by_action = {item.action: item for item in transitions}
    evidence_ids = [row.evidence_id for row in by_action["hold"].evidence]

    if _missing_credit(card):
        return _recommendation(
            card,
            "abstain",
            "missing_credit",
            "Credit on a position the action would resize is missing, so exposure-changing actions are not scored.",
            "No economic ranking. Missing credit is unknown, not safe.",
            "The credit evidence row records status missing.",
            evidence_ids,
            escalation_pending=False,
        )

    feasible = [item for item in transitions if item.feasible]
    hold = by_action["hold"]
    reducers = [
        item
        for item in feasible
        if item.action in MARKET_ACTIONS
        and (item.var_95 < hold.var_95 - 1e-6 or item.stress_loss < hold.stress_loss - 1e-6)
    ]
    if hold.breach and not reducers:
        return _recommendation(
            card,
            "escalate",
            "breach_without_a_feasible_reducer",
            "A limit is breached and no feasible action reduces VaR or stress. Escalation is pending and exposure is unchanged.",
            "Exposure is unchanged. Escalation does not clear the breach.",
            "VaR and stress evidence are above a limit, and market actions are infeasible or do not reduce them.",
            evidence_ids,
            escalation_pending=True,
        )

    ranked = sorted(
        feasible,
        key=lambda item: (-(item.utility if item.utility is not None else -1e18), ACTIONS.index(item.action)),
    )
    best = ranked[0]
    # Actions with the same utility (hold versus escalate, hedge versus reduce on a
    # one-commodity book) are one economic result. The near-tie band applies to the
    # next distinct utility.
    second = next(
        (
            item
            for item in ranked[1:]
            if abs((item.utility or 0.0) - (best.utility or 0.0)) > 1.0
        ),
        None,
    )
    if second is not None and _near_tie(best.utility or 0.0, second.utility or 0.0):
        return _recommendation(
            card,
            "abstain",
            "near_tie",
            "The best and second distinct feasible utilities are inside the declared near-tie band.",
            f"Top actions {best.action} and {second.action} are not separated.",
            "Utilities use the declared formula and the visible evidence only.",
            evidence_ids,
            escalation_pending=False,
        )

    pending = best.action == "escalate"
    return _recommendation(
        card,
        best.action,
        best.reason or "highest_declared_utility",
        _procedural(best),
        f"Declared utility {best.utility:.2f} EUR is the best feasible value.",
        "Figures come from the empirical P&L panel and the named stress shock.",
        evidence_ids,
        escalation_pending=pending,
    )


def apply_action(card: DecisionCardVisible, action: str) -> Transition:
    measured = _measured_positions(card)
    quantities = {item.position_id: item.quantity for item in measured}
    ratios = {
        item.position_id: item.physical_hedge_ratio
        for item in measured
        if item.physical_hedge_ratio is not None
    }
    feasible, reason = _feasibility(card, action, measured)
    cost = 0.0
    escalation = action == "escalate"
    exception = action == "request_limit_exception"

    if feasible and action in DELTA_MULTIPLIER:
        quantities, ratios, cost = _scale(card, action, measured, quantities, ratios)
    elif feasible and action == "roll_near_to_far":
        quantities, cost = _roll(card, measured, quantities)

    post = _acted(card, _with_quantities(measured, quantities, ratios))
    var_95, cvar_95, pnl = _var_cvar(card, post)
    stress = _stress(card, post)
    tenor_penalty, _share = _tenor(card, post)
    breach, governance, excess = _governance(card, var_95, stress)
    utility = None
    if feasible:
        lam = DESK_LAMBDAS[card.mandate.desk]
        utility = -0.5 * stress - lam * cvar_95 - cost - governance - tenor_penalty

    evidence = [
        _evidence(card, "var_95", round(var_95, 6), "EUR", "Empirical 95% loss from the 60-day panel."),
        _evidence(card, "cvar_95", round(cvar_95, 6), "EUR", "Mean loss on the panel days at or below the 5% quantile."),
        _evidence(card, "stress_loss", round(stress, 6), "EUR", "Loss under the regime shock vector."),
        _evidence(card, "liquidity_cost", round(cost, 6), "EUR", "Notional moved times the regime spread."),
        _evidence(card, "governance_penalty", round(governance, 6), "EUR", "Zero inside both limits, else base plus excess."),
        _evidence(card, "tenor_penalty", round(tenor_penalty, 6), "EUR", "10,000 EUR when near-month share exceeds 0.70."),
        _evidence(card, "net_delta", {k: round(v, 6) for k, v in _net_delta(post).items()}, "quantity", "Financial delta by commodity."),
        _evidence(card, "breach", breach, "flag", f"excess_eur={excess:.2f}"),
    ]
    if utility is not None:
        evidence.append(_evidence(card, "utility", round(utility, 6), "EUR", "Declared utility of this action."))

    return Transition(
        action=action,
        feasible=feasible,
        reason=reason,
        quantities=quantities,
        hedge_ratios=ratios,
        liquidity_cost=cost,
        escalation_pending=escalation,
        exception_pending=exception,
        net_delta=_net_delta(post),
        near_quantity=_near_net(card, post),
        var_95=var_95,
        cvar_95=cvar_95,
        stress_loss=stress,
        tenor_penalty=tenor_penalty,
        governance_penalty=governance,
        utility=utility,
        breach=breach,
        evidence=evidence,
    )


def _recommendation(
    card: DecisionCardVisible,
    action: str,
    reason: str,
    procedural: str,
    economic: str,
    evidential: str,
    evidence_ids: list[str],
    *,
    escalation_pending: bool,
) -> Recommendation:
    return Recommendation(
        card_id=card.card_id,
        arm="scorecard",
        action_or_abstain=action,  # type: ignore[arg-type]
        reason=reason,
        procedural=procedural,
        economic=economic,
        evidential=evidential,
        evidence_ids=evidence_ids,
        escalation_pending=escalation_pending,
    )


def _procedural(item: Transition) -> str:
    if item.action == "escalate":
        return "Escalation is pending and exposure is unchanged. It is not approval."
    if item.action == "request_limit_exception":
        return "The exception request is pending and does not clear a breach."
    if item.breach:
        return "The action is feasible and a limit breach remains on the post-action book."
    return "The action is inside the mandate and leaves both limits."


def _near_tie(best: float, second: float) -> bool:
    gap = abs(best - second)
    return gap < NEAR_TIE_EUR or gap < NEAR_TIE_FRACTION * abs(best)


def _feasibility(card: DecisionCardVisible, action: str, measured: list[Position]) -> tuple[bool, str]:
    if action not in ACTIONS:
        return False, "unknown_action"
    if action not in MARKET_ACTIONS:
        return True, "no_exposure_change"
    if card.mandate.role == "observer":
        return False, "observer_mandate"
    acted = _acted(card, measured)
    financial = [item for item in acted if _financial(item) and abs(item.quantity) > 1e-9]
    outside = [
        item
        for item in measured
        if item.book_id not in set(card.mandate.may_trade_books) and _financial(item) and abs(item.quantity) > 1e-9
    ]
    if not financial and outside:
        return False, "mandate"
    if action.startswith("reduce") and any(item.instrument == "physical_supply_obligation" for item in acted):
        return False, "physical_obligation"
    if _resized_missing_credit(card, action, acted):
        return False, "missing_credit"
    current = {item.position_id: item.quantity for item in measured}
    ratios = {
        item.position_id: item.physical_hedge_ratio
        for item in measured
        if item.physical_hedge_ratio is not None
    }
    if action == "roll_near_to_far":
        post_quantities, _cost = _roll(card, measured, current)
        post_ratios = ratios
    else:
        post_quantities, post_ratios, _cost = _scale(card, action, measured, current, ratios)
    post = _with_quantities(measured, post_quantities, post_ratios)
    if _increases_breached_credit(card, measured, post):
        return False, "credit_limit"
    return True, "feasible"


def _missing_credit(card: DecisionCardVisible) -> bool:
    acted = _acted(card, card.positions)
    counterparties = {item.counterparty_id for item in acted if item.counterparty_id}
    return any(line.status == "missing" and line.counterparty_id in counterparties for line in card.credit)


def _resized_missing_credit(card: DecisionCardVisible, action: str, acted: list[Position]) -> bool:
    if action.startswith("hedge") or action == "roll_near_to_far":
        commodity = _dominant(acted)
        touched = [item for item in acted if _financial(item) and item.commodity == commodity]
    else:
        touched = [item for item in acted if _financial(item)]
    missing = {line.counterparty_id for line in card.credit if line.status == "missing"}
    return any(item.counterparty_id in missing for item in touched)


def _increases_breached_credit(card: DecisionCardVisible, before: list[Position], after: list[Position]) -> bool:
    breached = set()
    for line in card.credit:
        if line.status == "known" or line.status == "downgraded":
            if line.limit_eur is not None and line.utilisation_eur is not None and line.utilisation_eur > line.limit_eur:
                breached.add(line.counterparty_id)
    if not breached:
        return False
    return _gross(after, breached) > _gross(before, breached) + 1e-6


def _gross(positions: list[Position], counterparties: set[str]) -> float:
    return sum(
        abs(item.quantity) * item.price_eur
        for item in positions
        if item.counterparty_id in counterparties and _financial(item)
    )


def _scale(
    card: DecisionCardVisible,
    action: str,
    measured: list[Position],
    quantities: dict[str, float],
    ratios: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], float]:
    acted = _acted(card, measured)
    multiplier = DELTA_MULTIPLIER[action]
    updated = dict(quantities)
    updated_ratios = dict(ratios)
    if action.startswith("hedge"):
        commodity = _dominant(acted)
        touched = [item for item in acted if _financial(item) and item.commodity == commodity]
        old_delta = sum(item.quantity for item in touched)
        for item in touched:
            updated[item.position_id] = item.quantity * multiplier
        new_delta = old_delta * multiplier
        price = _vw_price(touched)
        cost = abs(old_delta - new_delta) * price * _spread(card)
        fraction = HEDGE_FRACTION[action]
        for item in acted:
            if item.instrument == "physical_supply_obligation" and item.commodity == commodity:
                old_ratio = item.physical_hedge_ratio or 0.0
                gap = max(0.0, 0.98 - old_ratio)
                updated_ratios[item.position_id] = min(0.98, old_ratio + fraction * gap)
        return updated, updated_ratios, cost

    touched = [item for item in acted if _financial(item)]
    cost = 0.0
    for item in touched:
        new_quantity = item.quantity * multiplier
        updated[item.position_id] = new_quantity
        cost += abs(item.quantity - new_quantity) * item.price_eur * _spread(card)
    return updated, updated_ratios, cost


def _roll(
    card: DecisionCardVisible,
    measured: list[Position],
    quantities: dict[str, float],
) -> tuple[dict[str, float], float]:
    acted = _acted(card, measured)
    commodity = _dominant(acted)
    as_of = _as_of(card)
    near = [
        item
        for item in acted
        if _financial(item) and item.commodity == commodity and _near(item, as_of)
    ]
    far = [
        item
        for item in acted
        if _financial(item) and item.commodity == commodity and not _near(item, as_of)
    ]
    updated = dict(quantities)
    near_net = sum(quantities[item.position_id] for item in near)
    moved = 0.5 * near_net
    if not near or not far or moved == 0.0:
        return updated, 0.0
    for item in near:
        weight = quantities[item.position_id] / near_net if near_net else 0.0
        updated[item.position_id] = quantities[item.position_id] - moved * weight
    far_abs = sum(abs(quantities[item.position_id]) for item in far) or 1.0
    for item in far:
        weight = abs(quantities[item.position_id]) / far_abs
        updated[item.position_id] = quantities[item.position_id] + moved * weight
    price = _vw_price(near)
    cost = abs(moved) * price * _spread(card) * 0.5
    return updated, cost


def _var_cvar(card: DecisionCardVisible, positions: list[Position]) -> tuple[float, float, np.ndarray]:
    panel = load_panel()
    rows = panel["regimes"][card.market.regime]
    pnl = np.array([_day_pnl(positions, row) for row in rows], dtype=float)
    quantile = float(np.quantile(pnl, 0.05))
    tail = pnl[pnl <= quantile + 1e-12]
    var_95 = max(0.0, -quantile)
    cvar_95 = max(0.0, -float(tail.mean()) if len(tail) else -quantile)
    return var_95, cvar_95, pnl


def _day_pnl(positions: list[Position], row: dict[str, float]) -> float:
    total = 0.0
    for item in positions:
        if _financial(item):
            total += item.quantity * item.price_eur * float(row[item.commodity])
    return total


def _stress(card: DecisionCardVisible, positions: list[Position]) -> float:
    panel = load_panel()
    shock = panel["shocks"][card.market.regime]
    marked = 0.0
    for item in positions:
        if _financial(item):
            marked += item.quantity * item.price_eur * float(shock[item.commodity])
    return max(0.0, -marked)


def _tenor(card: DecisionCardVisible, positions: list[Position]) -> tuple[float, float]:
    commodity = _dominant(positions)
    as_of = _as_of(card)
    financial = [item for item in positions if _financial(item) and item.commodity == commodity]
    total = sum(abs(item.quantity) for item in financial)
    near = sum(abs(item.quantity) for item in financial if _near(item, as_of))
    share = near / total if total > 1e-9 else 0.0
    penalty = TENOR_PENALTY_EUR if share > TENOR_SHARE else 0.0
    return penalty, share


def _governance(card: DecisionCardVisible, var_95: float, stress: float) -> tuple[bool, float, float]:
    excess = max(0.0, var_95 - card.limits.var_limit_eur) + max(0.0, stress - card.limits.stress_limit_eur)
    breach = excess > 0.0
    penalty = GOVERNANCE_PENALTY_BASE + excess if breach else 0.0
    return breach, penalty, excess


def _measured_positions(card: DecisionCardVisible) -> list[Position]:
    return list(card.positions)


def _acted(card: DecisionCardVisible, positions: list[Position]) -> list[Position]:
    allowed = set(card.mandate.may_trade_books)
    return [item for item in positions if item.book_id in allowed]


def _financial(position: Position) -> bool:
    return position.instrument != "physical_supply_obligation"


def _dominant(positions: list[Position]) -> str:
    totals = {name: 0.0 for name in COMMODITY_ORDER}
    for item in positions:
        if _financial(item):
            totals[item.commodity] += item.quantity
    return max(COMMODITY_ORDER, key=lambda name: (abs(totals[name]), -COMMODITY_ORDER.index(name)))


def _net_delta(positions: list[Position]) -> dict[str, float]:
    totals = {name: 0.0 for name in COMMODITY_ORDER}
    for item in positions:
        if _financial(item):
            totals[item.commodity] += item.quantity
    return totals


def _near_net(card: DecisionCardVisible, positions: list[Position]) -> dict[str, float]:
    as_of = _as_of(card)
    totals = {name: 0.0 for name in COMMODITY_ORDER}
    for item in positions:
        if _financial(item) and _near(item, as_of):
            totals[item.commodity] += item.quantity
    return totals


def _with_quantities(
    positions: list[Position],
    quantities: dict[str, float],
    ratios: dict[str, float],
) -> list[Position]:
    posted: list[Position] = []
    for item in positions:
        data = item.model_dump()
        data["quantity"] = quantities.get(item.position_id, item.quantity)
        if item.position_id in ratios:
            data["physical_hedge_ratio"] = ratios[item.position_id]
        posted.append(Position.model_validate(data))
    return posted


def _vw_price(positions: list[Position]) -> float:
    weight = sum(abs(item.quantity) for item in positions)
    if weight <= 1e-12:
        return 0.0
    return sum(abs(item.quantity) * item.price_eur for item in positions) / weight


def _spread(card: DecisionCardVisible) -> float:
    return SPREADS["thin"] if card.market.liquidity == "thin" else SPREADS["normal"]


def _as_of(card: DecisionCardVisible) -> date:
    text = card.market.as_of.replace("Z", "+00:00")
    return datetime.fromisoformat(text).date()


def _near(position: Position, as_of: date) -> bool:
    start = date.fromisoformat(position.delivery_start)
    return abs((start - as_of).days) <= NEAR_DAYS


def _evidence(card: DecisionCardVisible, kind: str, value: Any, units: str, method_note: str) -> Evidence:
    del method_note
    return Evidence(
        evidence_id=f"{card.card_id}:{kind}",
        kind=kind,
        method=METHOD,
        units=units,
        value=json.loads(json.dumps(value)),
        book_id=card.mandate.may_trade_books[0] if card.mandate.may_trade_books else None,
    )
