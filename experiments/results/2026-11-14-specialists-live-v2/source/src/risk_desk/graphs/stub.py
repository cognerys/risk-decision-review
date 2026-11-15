"""Offline foundation graph kept for the package smoke test."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from risk_desk.schemas import Recommendation
from risk_desk.state import DeskState
from risk_desk.tracing import mirror_event

_RUNS = Path("runs")
_RUNS.mkdir(parents=True, exist_ok=True)
_CHECKPOINT_CONNECTION = sqlite3.connect(str(_RUNS / "checkpoints.sqlite"), check_same_thread=False)
_CHECKPOINTER = SqliteSaver(_CHECKPOINT_CONNECTION)
_CHECKPOINTER.setup()


def foundation_node(state: DeskState) -> dict[str, Any]:
    recommendation = Recommendation(
        card_id=state["card_id"],
        arm=state["arm"],
        action_or_abstain="abstain",
        reason="foundation_stub",
        procedural="no procedural finding; foundation graph only",
        economic="no economic finding; foundation graph only",
        evidential="no evidential finding; foundation graph only",
        evidence_ids=[],
        escalation_pending=False,
    )
    event = {
        "event": "foundation_recommendation",
        "card_id": state["card_id"],
        "arm": state["arm"],
        "action_or_abstain": "abstain",
        "reason": "foundation_stub",
    }
    mirror_event(dict(event))
    trace = list(state.get("trace") or [])
    trace.append(dict(event))
    return {"recommendation": recommendation.model_dump(), "trace": trace}


def _compile() -> Any:
    builder = StateGraph(DeskState)
    builder.add_node("foundation", foundation_node)
    builder.add_edge(START, "foundation")
    builder.add_edge("foundation", END)
    return builder.compile(checkpointer=_CHECKPOINTER)


stub_graph = _compile()
