"""Turn a compiled arm into nodes and edges the viewer can draw."""

from __future__ import annotations

from typing import Any

from risk_desk.graphs.workflows import (
    build_desk_graph,
    build_react_graph,
    build_scorecard_graph,
    build_supervisor_graph,
)

ARMS = ("scorecard", "react", "supervisor", "desk")

BUILDERS = {
    "scorecard": build_scorecard_graph,
    "react": build_react_graph,
    "supervisor": build_supervisor_graph,
    "desk": build_desk_graph,
}

BLURBS = {
    "__start__": "Entry.",
    "__end__": "The recommendation is the output.",
    "score": "Ranks feasible actions with the declared utility. No model call.",
    "evidence": "Builds VaR, stress, and limit evidence from the visible card only.",
    "book": "Writes one snapshot per book. The edge into this node fans out.",
    "supervisor": "Opens credit, physical, or governance only when the flags say so.",
    "propose": "Tool-calling model. It may cite only ids the tools returned.",
    "challenger": "Marks dissent when the proposal leaves the scorecard action.",
    "verify": "Rejects a reply with no evidence ids and writes the scorecard action.",
    "committee": "Pauses for a person, or records that escalation leaves exposure unchanged.",
}


def describe(arm: str) -> dict[str, Any]:
    if arm not in BUILDERS:
        raise KeyError(arm)
    drawable = BUILDERS[arm](checkpointer=None).get_graph()
    nodes = []
    for node_id in drawable.nodes:
        nodes.append(
            {
                "id": node_id,
                "label": _label(node_id),
                "blurb": BLURBS.get(node_id, ""),
            }
        )
    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "conditional": bool(edge.conditional),
        }
        for edge in drawable.edges
    ]
    return {"arm": arm, "nodes": nodes, "edges": edges}


def _label(node_id: str) -> str:
    if node_id == "__start__":
        return "Start"
    if node_id == "__end__":
        return "End"
    return node_id.replace("_", " ")
