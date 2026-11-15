"""The local graph page is drawn from the compiled arms."""

from risk_desk.viewer.graph_view import describe
from risk_desk.viewer.server import run_arm


def test_desk_graph_lists_the_committee_path() -> None:
    payload = describe("desk")
    ids = [node["id"] for node in payload["nodes"]]
    assert ids == [
        "__start__",
        "evidence",
        "book",
        "supervisor",
        "propose",
        "challenger",
        "verify",
        "committee",
        "__end__",
    ]
    fanout = [edge for edge in payload["edges"] if edge["conditional"]]
    assert fanout == [{"source": "evidence", "target": "book", "conditional": True}]


def test_viewer_run_puts_the_figures_on_the_node() -> None:
    result = run_arm("scorecard", "ordinary_inside", live=False)
    assert result["visited"] == ["score"]
    assert result["recommendation"]["action_or_abstain"] == "hold"
    text = " ".join(result["outputs"]["score"])
    assert "var 95" in text
    assert "hold" in text
    assert result["recommendation"]["procedural"]


def test_desk_run_shows_each_node_output() -> None:
    result = run_arm("desk", "cold_spell_power", live=False)
    assert "var 95" in " ".join(result["outputs"]["evidence"])
    assert result["outputs"]["supervisor"]
    assert result["outputs"]["propose"]
    assert result["outputs"]["verify"]
    assert result["recommendation"]["economic"]
