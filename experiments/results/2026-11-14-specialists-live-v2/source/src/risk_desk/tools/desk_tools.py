"""Tools an agent may call. They never load a sealed sheet."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from risk_desk.data.cards import load_card
from risk_desk.engine.score import apply_action, evidence_for, feasible_actions, scorecard, visible_payload
from risk_desk.policy import ACTIONS


def make_tools(card_id: str) -> list:
    """Bind every tool to one visible card."""

    @tool
    def visible_card() -> str:
        """Return the visible decision card as JSON. Realised P&L is not included."""
        return visible_payload(load_card(card_id))

    @tool
    def book_snapshot(book_id: str) -> str:
        """Return quantities and instruments for one book on this card."""
        card = load_card(card_id)
        rows = [
            {
                "position_id": row.position_id,
                "commodity": row.commodity,
                "instrument": row.instrument,
                "quantity": row.quantity,
                "delivery_start": row.delivery_start,
            }
            for row in card.positions
            if row.book_id == book_id
        ]
        return json.dumps({"book_id": book_id, "positions": rows})

    @tool
    def risk_evidence() -> str:
        """Return evidence rows computed from the visible card. Each row has an evidence id."""
        rows = [row.model_dump() for row in evidence_for(load_card(card_id))]
        return json.dumps(rows)

    @tool
    def list_feasible_actions() -> str:
        """Return the feasible action names for this card."""
        return json.dumps(feasible_actions(load_card(card_id)))

    @tool
    def score_action(action: str) -> str:
        """Score one action. Refuses names outside the action set. Does not return realised P&L."""
        if action not in ACTIONS and action != "abstain":
            return json.dumps({"error": "unknown_action", "action": action})
        if action == "abstain":
            return json.dumps({"action": "abstain", "utility": None})
        result = apply_action(load_card(card_id), action)
        return json.dumps(
            {
                "action": result.action,
                "feasible": result.feasible,
                "reason": result.reason,
                "utility": result.utility,
                "var_95": result.var_95,
                "cvar_95": result.cvar_95,
                "stress_loss": result.stress_loss,
                "liquidity_cost": result.liquidity_cost,
                "tenor_penalty": result.tenor_penalty,
                "governance_penalty": result.governance_penalty,
                "breach": result.breach,
                "escalation_pending": result.escalation_pending,
                "exception_pending": result.exception_pending,
                "net_delta": result.net_delta,
            }
        )

    @tool
    def scorecard_rank() -> str:
        """Return the deterministic scorecard recommendation as JSON."""
        return scorecard(load_card(card_id)).model_dump_json()

    return [visible_card, book_snapshot, risk_evidence, list_feasible_actions, score_action, scorecard_rank]
