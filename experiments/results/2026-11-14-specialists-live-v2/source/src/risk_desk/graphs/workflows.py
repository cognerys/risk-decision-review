"""Four desk architectures sharing one tool surface and one visible card."""

from __future__ import annotations

import json
import operator
import sqlite3
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langchain.agents import create_agent
from langgraph.types import Command, Send, interrupt
from typing_extensions import TypedDict

from risk_desk.config import Settings
from risk_desk.data.cards import load_card
from risk_desk.engine.score import evidence_for, feasible_actions, scorecard
from risk_desk.llm import build_chat_model
from risk_desk.schemas import Recommendation
from risk_desk.tools.desk_tools import make_tools
from risk_desk.tracing import mirror_event
from risk_desk.responses import decode_response

_DEFAULT_CHECKPOINTER = object()
_CHECKPOINTER: SqliteSaver | None = None


def _default_checkpointer() -> SqliteSaver:
    global _CHECKPOINTER
    if _CHECKPOINTER is None:
        runs = Path("runs")
        runs.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(runs / "checkpoints.sqlite"), check_same_thread=False)
        _CHECKPOINTER = SqliteSaver(connection)
        _CHECKPOINTER.setup()
    return _CHECKPOINTER

PROMPT = (
    "You are reviewing one post-trade energy-risk decision. "
    "Use only tool results. Recommend one feasible action or abstain. "
    "Cite evidence ids. Do not invent risk numbers. Do not use realised profit. "
    "Escalation does not change exposure. Missing credit is unknown, not safe. "
    "Reply with one JSON object: action_or_abstain, reason, procedural, economic, "
    "evidential, evidence_ids."
)


class WorkflowState(TypedDict, total=False):
    card_id: str
    run_id: str
    job_id: str
    response: dict[str, Any]
    verification: dict[str, Any]
    committee_decision: dict[str, Any]
    arm: str
    book_id: str
    visible: dict[str, Any]
    evidence: list[Any]
    snapshots: Annotated[list[dict[str, Any]], operator.add]
    routes: list[str]
    proposal: dict[str, Any]
    dissent: bool
    recommendation: dict[str, Any]
    trace: list[Any]
    auto_committee: bool
    step_cap: int
    leak_realised_pnl: float


def _compile(builder: StateGraph, checkpointer: Any) -> Any:
    if checkpointer is _DEFAULT_CHECKPOINTER:
        checkpointer = _default_checkpointer()
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)


def build_scorecard_graph(checkpointer: Any = _DEFAULT_CHECKPOINTER) -> Any:
    builder = StateGraph(WorkflowState)
    builder.add_node("score", _score_node)
    builder.add_edge(START, "score")
    builder.add_edge("score", END)
    return _compile(builder, checkpointer)


def build_react_graph(checkpointer: Any = _DEFAULT_CHECKPOINTER) -> Any:
    builder = StateGraph(WorkflowState)
    builder.add_node("propose", _react_node)
    builder.add_node("verify", _verify_node)
    builder.add_edge(START, "propose")
    builder.add_edge("propose", "verify")
    builder.add_edge("verify", END)
    return _compile(builder, checkpointer)


def build_supervisor_graph(checkpointer: Any = _DEFAULT_CHECKPOINTER) -> Any:
    builder = StateGraph(WorkflowState)
    builder.add_node("evidence", _evidence_node)
    builder.add_node("book", _book_node)
    builder.add_node("supervisor", _supervisor_node)
    builder.add_node("propose", _react_node)
    builder.add_node("verify", _verify_node)
    builder.add_edge(START, "evidence")
    builder.add_conditional_edges("evidence", _fanout, ["book"])
    builder.add_edge("book", "supervisor")
    builder.add_edge("supervisor", "propose")
    builder.add_edge("propose", "verify")
    builder.add_edge("verify", END)
    return _compile(builder, checkpointer)


def build_desk_graph(checkpointer: Any = _DEFAULT_CHECKPOINTER) -> Any:
    """Supervisor, challenger, verifier, and a committee interrupt."""
    builder = StateGraph(WorkflowState)
    builder.add_node("evidence", _evidence_node)
    builder.add_node("book", _book_node)
    builder.add_node("supervisor", _supervisor_node)
    builder.add_node("propose", _react_node)
    builder.add_node("challenger", _challenger_node)
    builder.add_node("verify", _verify_node)
    builder.add_node("committee", _committee_node)
    builder.add_edge(START, "evidence")
    builder.add_conditional_edges("evidence", _fanout, ["book"])
    builder.add_edge("book", "supervisor")
    builder.add_edge("supervisor", "propose")
    builder.add_edge("propose", "challenger")
    builder.add_edge("challenger", "verify")
    builder.add_edge("verify", "committee")
    builder.add_edge("committee", END)
    return _compile(builder, checkpointer)


def _score_node(state: WorkflowState) -> dict[str, Any]:
    state = _with_ids(state)
    card = load_card(state["card_id"])
    recommendation = scorecard(card).model_copy(update={"arm": "scorecard"})
    _mirror(state, "scorecard", recommendation.model_dump())
    return {"run_id": state["run_id"], "job_id": state["job_id"], "recommendation": recommendation.model_dump(), "evidence": [row.model_dump() for row in evidence_for(card)]}


def _evidence_node(state: WorkflowState) -> dict[str, Any]:
    state = _with_ids(state)
    card = load_card(state["card_id"])
    if not card.positions:
        raise ValueError("Supervisor and desk workflows require at least one position; use a flat-position card for zero exposure")
    rows = [row.model_dump() for row in evidence_for(card)]
    _mirror(state, "evidence", {"n": len(rows)})
    return {"run_id": state["run_id"], "job_id": state["job_id"], "evidence": rows, "visible": json.loads(card.model_dump_json())}


def _fanout(state: WorkflowState) -> list[Send]:
    card = load_card(state["card_id"])
    books = sorted({row.book_id for row in card.positions})
    return [Send("book", {"card_id": state["card_id"], "arm": state.get("arm", ""), "book_id": book}) for book in books]


def _book_node(state: WorkflowState) -> dict[str, Any]:
    card = load_card(state["card_id"])
    book_id = state["book_id"]
    quantity = sum(row.quantity for row in card.positions if row.book_id == book_id)
    return {"snapshots": [{"book_id": book_id, "quantity": quantity}]}


def _supervisor_node(state: WorkflowState) -> dict[str, Any]:
    card = load_card(state["card_id"])
    routes = ["market_risk"]
    credit_status = {line.status for line in card.credit}
    if "missing" in credit_status or "downgraded" in credit_status:
        routes.append("credit")
    if any(row.instrument == "physical_supply_obligation" for row in card.positions):
        routes.append("physical")
    hold = next(row for row in state.get("evidence", []) if row.get("kind") == "breach")
    if hold and hold.get("value") is True:
        routes.append("governance")
    if card.mandate.role == "observer":
        routes.append("governance")
    _mirror(state, "routes", {"routes": routes})
    return {"routes": routes}


def _react_node(state: WorkflowState) -> dict[str, Any]:
    state = _with_ids(state)
    card_id = state["card_id"]
    model = build_chat_model(Settings.from_env())
    agent = create_agent(model, make_tools(card_id), system_prompt=PROMPT)
    user = f"Review card {card_id}. Routes already selected: {state.get('routes', ['market_risk'])}."
    leaked = state.get("leak_realised_pnl")
    if leaked is not None:
        user += f" Realised P&L over the horizon was {leaked} EUR."
    result = agent.invoke(
        {"messages": [("user", user)]},
        config={"recursion_limit": int(state.get("step_cap") or 12)},
    )
    message = result["messages"][-1]
    response = decode_response(message.content)
    proposal = response["proposal"]
    _mirror(state, "response", response)
    _mirror(state, "proposal", proposal)
    return {"run_id": state["run_id"], "job_id": state["job_id"],
            "response": response, "proposal": proposal}


def _challenger_node(state: WorkflowState) -> dict[str, Any]:
    proposal = state.get("proposal") or {}
    baseline = scorecard(load_card(state["card_id"]))
    dissent = proposal.get("action_or_abstain") not in {baseline.action_or_abstain, "abstain"}
    if proposal.get("reason") == "foundation_stub":
        dissent = baseline.action_or_abstain not in {"abstain", "hold"}
    _mirror(state, "challenger", {"dissent": dissent})
    return {"dissent": dissent}


def _verify_node(state: WorkflowState) -> dict[str, Any]:
    card = load_card(state["card_id"])
    baseline = scorecard(card)
    proposal = dict(state.get("proposal") or {})
    evidence_ids = {row.evidence_id for row in evidence_for(card)}
    cited = proposal.get("evidence_ids") or []
    action = proposal.get("action_or_abstain")
    feasible = set(feasible_actions(card)) | {"abstain"}
    supported = (isinstance(cited, list) and bool(cited)
                 and all(isinstance(item, str) for item in cited)
                 and set(cited).issubset(evidence_ids))
    legal = isinstance(action, str) and action in feasible
    reasons = []
    if state.get("response", {}).get("parse_status", "ok") != "ok":
        reasons.append("response_parse_failed")
    if not legal:
        reasons.append("invalid_or_infeasible_action")
    if not supported:
        reasons.append("missing_or_unknown_evidence_ids")
    if proposal.get("reason") == "foundation_stub":
        reasons.append("scripted_stub")
    verification = {"fallback": bool(reasons), "proposal_legal": legal,
                    "citation_ids_valid": supported, "rejection_reasons": reasons}
    if reasons:
        recommendation = baseline.model_copy(update={"arm": state.get("arm", "desk"), "reason": "verifier_rejected"})
        if baseline.reason in {"missing_credit", "near_tie"}:
            recommendation = baseline.model_copy(update={"arm": state.get("arm", "desk")})
    else:
        recommendation = Recommendation(
            card_id=card.card_id,
            arm=state.get("arm", "desk"),
            action_or_abstain=action,
            reason=str(proposal.get("reason") or "model"),
            procedural=str(proposal.get("procedural") or ""),
            economic=str(proposal.get("economic") or ""),
            evidential=str(proposal.get("evidential") or ""),
            evidence_ids=list(cited),
            escalation_pending=action == "escalate",
        )
    _mirror(state, "verification", verification)
    _mirror(state, "verify", recommendation.model_dump())
    return {"recommendation": recommendation.model_dump(), "verification": verification}


def _committee_node(state: WorkflowState) -> dict[str, Any]:
    recommendation = dict(state.get("recommendation") or {})
    needs_pause = bool(state.get("dissent")) or recommendation.get("action_or_abstain") == "escalate"
    auto = bool(state.get("auto_committee"))
    if needs_pause and not auto:
        decision = interrupt(
            {
                "card_id": state.get("card_id"),
                "recommendation": recommendation,
                "note": "escalation pending, exposure unchanged",
            }
        )
        outcome = {"status": "rejected", "override": False}
        candidate = decode_response(json.dumps(decision)) if isinstance(decision, dict) else {"proposal": {}}
        action = decision.get("action_or_abstain") if isinstance(decision, dict) else None
        if isinstance(action, str) and action == recommendation.get("action_or_abstain"):
            outcome = {"status": "accepted", "override": False}
        else:
            proposal = candidate["proposal"]
            card = load_card(state["card_id"])
            feasible = set(feasible_actions(card)) | {"abstain"}
            known_ids = {row.evidence_id for row in evidence_for(card)}
            cited = proposal.get("evidence_ids") or []
            legal = isinstance(action, str) and action in feasible
            supported = bool(cited) and set(cited).issubset(known_ids)
            if candidate.get("parse_status") == "ok" and legal and supported:
                recommendation = Recommendation(
                    card_id=card.card_id, arm=state.get("arm", "desk"),
                    action_or_abstain=action, reason="committee",
                    procedural=proposal.get("procedural", ""),
                    economic=proposal.get("economic", ""),
                    evidential=proposal.get("evidential", ""),
                    evidence_ids=cited, escalation_pending=action == "escalate",
                ).model_dump()
                outcome = {"status": "accepted", "override": True}
            else:
                outcome["reason"] = "override_requires_feasible_action_and_valid_evidence_ids"
                recommendation["escalation_pending"] = True
        outcome["requested_action"] = action
    elif needs_pause:
        recommendation["escalation_pending"] = True
        recommendation["procedural"] = "escalation pending, exposure unchanged"
        outcome = {"status": "auto_pending", "override": False}
    else:
        outcome = {"status": "not_required", "override": False}
    _mirror(state, "committee_decision", outcome)
    _mirror(state, "committee", recommendation)
    return {"recommendation": recommendation, "committee_decision": outcome}


def _parse_proposal(content: Any) -> dict[str, Any]:
    return decode_response(content)["proposal"]


def _with_ids(state: WorkflowState) -> WorkflowState:
    return {**state, "run_id": state.get("run_id") or uuid4().hex,
            "job_id": state.get("job_id") or f"{state.get('arm', 'desk')}-{state['card_id']}"}


def _mirror(state: WorkflowState, event: str, payload: dict[str, Any]) -> None:
    mirror_event({"event": event, "run_id": state.get("run_id"), "job_id": state.get("job_id"),
                  "card_id": state.get("card_id"), "arm": state.get("arm"), "payload": payload})


def resume_committee(graph: Any, thread_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    return graph.invoke(Command(resume=decision), config={"configurable": {"thread_id": thread_id}})
