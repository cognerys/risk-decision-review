"""Turn a compiled review configuration into nodes and edges the viewer can draw."""

from __future__ import annotations

from typing import Any

from risk_desk.graphs.review import ARMS, build_research_graph

BLURBS = {
    "__start__": "Entry.",
    "__end__": "The recommendation is the output.",
    "evidence": "Builds the evidence bundle from the visible card: positions, limits, credit and the consequences of each action. No model call.",
    "market_physical": "Specialist model. Reports on stress, tail risk, liquidity cost and physical obligations. Its report is checked before it is passed on.",
    "credit_governance": "Specialist model. Reports on credit, mandate and escalation. Its report is checked before it is passed on.",
    "propose": "Model proposes an action with cited evidence and numeric claims.",
    "challenge": "A separate model reviews the proposal against the original evidence.",
    "revise": "The proposer revises or confirms once, in the light of the challenge.",
    "self_review": "The same model re-reads its own proposal, four times, with no outside advice.",
    "verify": "Code checks the schema, feasibility, cited identifiers and numeric claims. A failed check falls back to the deterministic scorecard.",
}


def describe(arm: str) -> dict[str, Any]:
    if arm not in ARMS:
        raise KeyError(arm)
    drawable = build_research_graph(arm, checkpointer=None).get_graph()
    nodes = [{"id": node_id, "label": _label(node_id), "blurb": BLURBS.get(node_id, "")} for node_id in drawable.nodes]
    edges = [{"source": edge.source, "target": edge.target, "conditional": bool(edge.conditional)} for edge in drawable.edges]
    return {"arm": arm, "nodes": nodes, "edges": edges}


def _label(node_id: str) -> str:
    if node_id == "__start__":
        return "Start"
    if node_id == "__end__":
        return "End"
    return node_id.replace("_", " ")
