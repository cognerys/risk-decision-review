"""The local graph page is drawn from the compiled review configurations."""

from risk_desk.viewer.graph_view import describe
from risk_desk.viewer.server import run_arm


def test_challenged_graph_lists_every_step() -> None:
    payload = describe("challenged")
    ids = [node["id"] for node in payload["nodes"]]
    assert ids == ["__start__", "evidence", "propose", "verify", "market_physical", "credit_governance",
                   "challenge", "revise", "__end__"] or set(ids) == {
        "__start__", "evidence", "market_physical", "credit_governance", "propose", "challenge", "revise", "verify", "__end__"}
    assert {"source": "challenge", "target": "revise", "conditional": False} in payload["edges"]


def test_single_graph_has_no_specialists() -> None:
    ids = {node["id"] for node in describe("single")["nodes"]}
    assert ids == {"__start__", "evidence", "propose", "verify", "__end__"}


def test_offline_run_shows_each_step_and_the_fallback() -> None:
    result = run_arm("challenged", "ordinary_inside", live=False)
    assert result["visited"] == ["evidence", "market_physical", "credit_governance", "propose", "challenge", "revise", "verify"]
    for step in result["visited"]:
        assert result["outputs"][step]
    # The scripted offline model does not satisfy the proposal contract, so code falls back and says so.
    assert result["fallback"] is True
    assert result["recommendation"]["action_or_abstain"] == "hold"
    assert result["evidence"]
