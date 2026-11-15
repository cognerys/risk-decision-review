"""Scorecard behaviour on the sixteen synthetic cards. No network."""

from __future__ import annotations

import json

import pytest

from risk_desk.data.cards import all_positions, card_ids, load_card, load_sealed
from risk_desk.engine.score import apply_action, feasible_actions, scorecard, visible_payload
from risk_desk.schemas import DecisionCardVisible

HEDGES = {"hedge_25", "hedge_50", "hedge_75"}


def test_sixteen_cards_and_library_size() -> None:
    assert len(card_ids()) == 16
    assert 35 <= len(all_positions()) <= 50


@pytest.mark.parametrize("card_id", card_ids())
def test_visible_payload_has_no_sealed_keys(card_id: str) -> None:
    payload = visible_payload(load_card(card_id))
    for banned in ("realised_pnl", "latent_regime", "hidden_forecast"):
        assert banned not in payload


def test_forecast_not_yet_issued_is_hidden() -> None:
    card = load_card("forecast_not_yet_issued")
    assert card.market.forecast_visible is False
    sealed = load_sealed("forecast_not_yet_issued")
    assert sealed.hidden_forecast_value == 120.0


def test_physical_obligation_rules() -> None:
    card = load_card("physical_obligation")
    feasible = set(feasible_actions(card))
    assert "reduce_25" not in feasible
    assert "reduce_50" not in feasible
    before = next(row for row in card.positions if row.instrument == "physical_supply_obligation")
    hedge = apply_action(card, "hedge_50")
    assert hedge.feasible
    assert hedge.hedge_ratios[before.position_id] > (before.physical_hedge_ratio or 0)
    assert hedge.hedge_ratios[before.position_id] <= 0.98
    held = apply_action(card, "hold")
    escalated = apply_action(card, "escalate")
    assert escalated.net_delta == held.net_delta
    assert escalated.escalation_pending


def test_credit_missing_abstains() -> None:
    recommendation = scorecard(load_card("credit_missing"))
    assert recommendation.action_or_abstain == "abstain"
    assert recommendation.reason == "missing_credit"
    feasible = set(feasible_actions(load_card("credit_missing")))
    assert feasible == {"hold", "escalate", "request_limit_exception"}


def test_mandate_blocks_the_retail_book() -> None:
    feasible = set(feasible_actions(load_card("mandate_prop_on_retail")))
    assert not feasible & (HEDGES | {"reduce_25", "reduce_50", "roll_near_to_far"})


def test_exception_does_not_clear_a_breach() -> None:
    card = load_card("exception_does_not_clear")
    after = apply_action(card, "request_limit_exception")
    assert after.exception_pending
    assert after.breach


def test_zero_exposure_has_no_var_and_no_hedge_cost() -> None:
    card = load_card("zero_exposure")
    assert apply_action(card, "hold").var_95 == 0
    assert apply_action(card, "hedge_50").liquidity_cost == 0


def test_hindsight_trap_disagrees_with_realised_profit() -> None:
    card = load_card("hindsight_trap")
    sealed = load_sealed("hindsight_trap")
    assert sealed.realised_pnl_eur > 0
    assert scorecard(card).action_or_abstain != "hold"
    payload = card.model_dump()
    payload["realised_pnl_eur"] = sealed.realised_pnl_eur
    with pytest.raises(ValueError):
        DecisionCardVisible.model_validate(payload)


def test_near_tie_abstains() -> None:
    recommendation = scorecard(load_card("near_tie"))
    assert recommendation.action_or_abstain == "abstain"
    assert recommendation.reason == "near_tie"


def test_roll_moves_tenor_without_changing_delta() -> None:
    card = load_card("roll_tenor_breach")
    before = apply_action(card, "hold")
    rolled = apply_action(card, "roll_near_to_far")
    assert rolled.net_delta["power"] == pytest.approx(before.net_delta["power"])
    assert abs(rolled.near_quantity["power"]) < abs(before.near_quantity["power"])
    assert scorecard(card).action_or_abstain == "roll_near_to_far"


def test_escalate_when_nothing_reduces_the_breach() -> None:
    card = load_card("escalate_when_no_hedge")
    before = apply_action(card, "hold")
    recommendation = scorecard(card)
    assert recommendation.action_or_abstain == "escalate"
    assert recommendation.escalation_pending
    after = apply_action(card, "escalate")
    assert after.net_delta == before.net_delta
    assert "unchanged" in recommendation.procedural


def test_hedges_win_when_the_tail_is_expensive() -> None:
    assert scorecard(load_card("var_headroom_tight")).action_or_abstain in HEDGES
    assert scorecard(load_card("cold_spell_power")).action_or_abstain in HEDGES


def test_ordinary_hold() -> None:
    assert scorecard(load_card("ordinary_inside")).action_or_abstain == "hold"


def test_thin_book_does_not_buy_the_largest_hedge() -> None:
    action = scorecard(load_card("stress_thin_hedge_capped")).action_or_abstain
    assert action != "hedge_75"
    assert action in HEDGES | {"roll_near_to_far"}


def test_downgrade_still_allows_a_reducing_hedge() -> None:
    assert "hedge_50" in feasible_actions(load_card("credit_downgrade"))


def test_correlation_break_var_is_finite() -> None:
    var_95 = apply_action(load_card("correlation_break_book"), "hold").var_95
    assert var_95 >= 0
    assert var_95 < 1e12


def test_scorecard_evidence_ids_exist() -> None:
    card = load_card("ordinary_inside")
    recommendation = scorecard(card)
    assert recommendation.evidence_ids
    blob = json.dumps([row.model_dump() for row in apply_action(card, "hold").evidence])
    for evidence_id in recommendation.evidence_ids:
        assert evidence_id in blob
