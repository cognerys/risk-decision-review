"""Offline checks for the four arms. No network."""

from __future__ import annotations

import json

from risk_desk.graphs.workflows import (
    build_desk_graph,
    build_react_graph,
    build_scorecard_graph,
    build_supervisor_graph,
)
from risk_desk.tools.desk_tools import make_tools


def _invoke(graph, card_id: str, arm: str, **extra):
    state = {
        "card_id": card_id,
        "arm": arm,
        "visible": {},
        "evidence": [],
        "snapshots": [],
        "routes": [],
        "proposal": {},
        "dissent": False,
        "recommendation": {},
        "trace": [],
        "auto_committee": True,
    }
    state.update(extra)
    return graph.invoke(state, config={"configurable": {"thread_id": f"test-{arm}-{card_id}"}})


def test_scorecard_arm_matches_hold() -> None:
    result = _invoke(build_scorecard_graph(), "ordinary_inside", "scorecard")
    assert result["recommendation"]["action_or_abstain"] == "hold"
    assert result["recommendation"]["arm"] == "scorecard"


def test_react_and_desk_fall_back_when_the_stub_has_no_evidence() -> None:
    react = _invoke(build_react_graph(), "cold_spell_power", "react")
    desk = _invoke(build_desk_graph(), "cold_spell_power", "desk")
    assert react["recommendation"]["action_or_abstain"] == "hedge_75"
    assert desk["recommendation"]["action_or_abstain"] == "hedge_75"
    assert desk["recommendation"]["reason"] == "verifier_rejected"


def test_missing_credit_reason_is_kept() -> None:
    result = _invoke(build_desk_graph(), "credit_missing", "desk")
    assert result["recommendation"]["action_or_abstain"] == "abstain"
    assert result["recommendation"]["reason"] == "missing_credit"


def test_supervisor_routes_a_physical_book() -> None:
    result = _invoke(build_supervisor_graph(), "physical_obligation", "supervisor")
    assert "physical" in result["routes"]
    assert "market_risk" in result["routes"]
    assert len(result["snapshots"]) >= 1


def test_committee_pauses_without_auto_policy() -> None:
    graph = build_desk_graph()
    result = graph.invoke(
        {
            "card_id": "escalate_when_no_hedge",
            "arm": "desk",
            "snapshots": [],
            "evidence": [],
            "auto_committee": False,
        },
        config={"configurable": {"thread_id": "pause-escalate"}},
    )
    assert result["__interrupt__"]
    assert "exposure unchanged" in json.dumps(result["__interrupt__"][0].value)


def test_tools_do_not_return_realised_pnl() -> None:
    tools = {tool.name: tool for tool in make_tools("hindsight_trap")}
    for name in ("visible_card", "risk_evidence", "scorecard_rank"):
        payload = tools[name].invoke({})
        assert "realised_pnl" not in payload
        assert "latent_regime" not in payload
    scored = tools["score_action"].invoke({"action": "hedge_50"})
    assert "realised_pnl" not in scored
