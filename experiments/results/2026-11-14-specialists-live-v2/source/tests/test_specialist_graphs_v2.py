"""Prospective V2 handoff and private-evaluation tests; no live calls."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from langchain_core.messages import AIMessage
import pytest

from risk_desk import tracing
from risk_desk.data.cards import load_card
from risk_desk.engine.score import scorecard
from risk_desk.graphs.specialists_v2 import (
    Proposal, assess_proposal, build_evidence_bundle, build_research_graph,
    evaluation_bundle_for, validate_specialist_report,
)


def finding(label="valid finding", ids=None):
    return {"issue": label, "evidence_ids": ids or ["ordinary_inside:credit"],
            "implication": "Check the supplied credit snapshot", "uncertainty": ""}


def report(findings=None):
    return {"summary": "SUMMARY MAY REPEAT REJECTED CLAIMS", "findings": findings or [finding()]}


def proposal(bundle=None, action="hold"):
    bundle = bundle or build_evidence_bundle("ordinary_inside")
    card = bundle["card"]["card_id"]
    ids = [f"{card}:action:hold:stress_loss", f"{card}:action:{'hold' if action == 'abstain' else action}:utility"]
    return {"action_or_abstain": action, "decision_basis": "highest_utility",
            "reason": "fixture", "procedural": "fixture", "economic": "fixture", "evidential": "fixture",
            "evidence_ids": ids,
            "numeric_claims": [{"evidence_id": key, "value": bundle["evidence"][key]} for key in ids]}


class Replies:
    def __init__(self, values):
        self.values = list(values)
        self.requests = []

    def __call__(self, settings):
        return self

    def invoke(self, messages):
        self.requests.append(messages)
        value = self.values.pop(0)
        return AIMessage(content=value if isinstance(value, str) else json.dumps(value))


@pytest.fixture(autouse=True)
def trace(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")


def test_visible_sections_and_action_metadata_are_citable_with_qualified_position_ids():
    bundle = build_evidence_bundle("ordinary_inside")
    evidence = bundle["evidence"]
    for suffix in ("market", "positions", "decision_rules", "action:hold", "action:escalate"):
        assert f"ordinary_inside:{suffix}" in evidence
    position = bundle["card"]["positions"][0]
    assert evidence[f"ordinary_inside:position:{position['position_id']}"] == position
    assert position["position_id"] not in evidence
    assert evidence["ordinary_inside:action:escalate"]["escalation_pending"] is True
    assert "exact utility equality" in bundle["decision_rules"]["ranking"]
    assert "MORE THAN EUR 1" in bundle["decision_rules"]["near_tie"]


@pytest.mark.parametrize("damage,expected_code", [
    (lambda f: f.update(evidence_ids=["invented-id"]), "unknown_evidence_ids"),
    (lambda f: f.pop("uncertainty"), "missing"),
    (lambda f: f.update(implication=123), "string_type"),
    (lambda f: f.update(unexpected="untrusted extra"), "extra_forbidden"),
    (lambda f: f.update(evidence_ids=[]), "empty_evidence_ids"),
])
def test_one_invalid_finding_does_not_discard_valid_sibling_or_pass_unsafe_summary(damage, expected_code):
    bad = finding("REJECTED SUBSTANTIVE CLAIM")
    damage(bad)
    candidate = report([finding(), bad])
    result = validate_specialist_report(candidate, build_evidence_bundle("ordinary_inside"))
    assert result["status"] == "partial" and result["usable"]
    assert result["report"] == {"findings": [finding()]}
    assert result["summary_omitted"]
    assert result["validation"]["accepted_finding_count"] == 1
    assert result["validation"]["rejected_finding_count"] == 1
    assert expected_code in {r["code"] for r in result["validation"]["findings"][1]["rejection_reasons"]}
    assert candidate["summary"] == "SUMMARY MAY REPEAT REJECTED CLAIMS"  # raw input preserved


def test_invalid_top_level_fields_are_rejected_but_valid_findings_can_be_salvaged():
    candidate = {**report(), "unsupported_field": "DO NOT FORWARD"}
    result = validate_specialist_report(candidate, build_evidence_bundle("ordinary_inside"))
    assert result["status"] == "partial"
    assert result["validation"]["envelope_errors"][0]["code"] == "extra_fields"
    assert "summary" not in result["report"] and "unsupported_field" not in result["report"]


def test_excess_findings_have_explicit_rejection_and_are_not_forwarded():
    result = validate_specialist_report(report([finding(str(i)) for i in range(5)]), build_evidence_bundle("ordinary_inside"))
    assert len(result["report"]["findings"]) == 4
    assert result["validation"]["findings"][4]["rejection_reasons"][0]["code"] == "exceeds_finding_limit"
    assert result["summary_omitted"]


def test_empty_or_invalid_report_does_not_become_advice():
    result = validate_specialist_report({"summary": "unsafe", "findings": [finding(ids=["unknown"])]}, build_evidence_bundle("ordinary_inside"))
    assert result["status"] == "rejected" and not result["usable"]
    assert result["report"] == {}


def test_handoff_exposes_citable_status_to_critic_without_substantive_specialist_advice():
    bad = finding("REJECTED SUBSTANTIVE CLAIM", ["invented-id"])
    partial = report([finding("PRIVATE SPECIALIST ADVICE"), bad])
    status_id = "ordinary_inside:workflow:specialist:market_physical"
    initial = proposal()
    initial["evidence_ids"].append(status_id)
    challenge = {"requires_revision": True, "assessment": "Report partially usable",
                 "issues": [{"issue": "A valid finding remains available", "evidence_ids": [status_id],
                             "requested_change": "Distinguish partial rejection from no report"}]}
    replies = Replies([partial, report(), initial, challenge, initial])
    result = build_research_graph("challenged", model_factory=replies).invoke({"card_id": "ordinary_inside"})
    assert len(replies.requests) == 5
    second_specialist = json.loads(replies.requests[1][1][1])
    assert second_specialist["evidence_bundle"]["workflow_evidence"] == {}
    proposer_input = json.loads(replies.requests[2][1][1])
    retained = proposer_input["specialist_reports"][0]
    assert retained["report"] == {"findings": [finding("PRIVATE SPECIALIST ADVICE")]}
    assert "REJECTED SUBSTANTIVE CLAIM" not in replies.requests[2][1][1]
    critic_input = json.loads(replies.requests[3][1][1])
    assert "specialist_reports" not in critic_input
    assert "PRIVATE SPECIALIST ADVICE" not in replies.requests[3][1][1]
    status = critic_input["evidence_bundle"]["workflow_evidence"][status_id]
    assert status["status"] == "partial" and status["accepted_finding_count"] == 1
    assert result["challenge"]["usable"]
    assert result["verification"]["primary_contract_pass"]
    assert result["specialist_reports"][0]["validation"]["rejected_finding_count"] == 1


def test_every_role_receives_schema_and_records_utc_stage_times():
    replies = Replies([report(), report(), proposal(), {"requires_revision": False, "assessment": "Clear", "issues": []}, proposal()])
    result = build_research_graph("challenged", model_factory=replies).invoke({"card_id": "ordinary_inside"})
    for request, stage in zip(replies.requests, result["stages"]):
        schema = json.loads(request[1][1])["output_schema"]
        assert schema["additionalProperties"] is False
        assert schema["required"]
        start, finish = datetime.fromisoformat(stage["started_utc"]), datetime.fromisoformat(stage["finished_utc"])
        assert start.utcoffset() == finish.utcoffset() == timezone.utc.utcoffset(start)
        assert finish >= start
    proposal_schema = json.loads(replies.requests[2][1][1])["output_schema"]
    assert proposal_schema["properties"]["decision_basis"]["enum"] == ["missing_credit", "unreducible_breach", "near_tie", "highest_utility"]


def test_error_stage_retains_utc_timestamps_before_propagating(tmp_path):
    class Fails:
        def invoke(self, messages):
            raise RuntimeError("offline failure")
    with pytest.raises(RuntimeError, match="offline failure"):
        build_research_graph(model_factory=lambda settings: Fails()).invoke({"card_id": "ordinary_inside"})
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    error = next(e["payload"] for e in events if e["event"] == "model_stage_error")
    assert error["started_utc"] and error["finished_utc"]


def test_custom_case_private_reference_and_numeric_values_never_reach_models():
    card = load_card("ordinary_inside").model_copy(update={"card_id": "custom_case"})
    evaluation = build_evidence_bundle(card)
    visible = deepcopy(evaluation)
    utility_id = "custom_case:action:hold:utility"
    definition = {"derived": True, "formula": "fixture formula", "components": {"stress_loss": "custom_case:action:hold:stress_loss"}}
    visible["evidence"][utility_id] = definition
    visible["derived_quantities"] = {utility_id: definition}
    reference = scorecard(card).model_copy(update={"reason": "PRIVATE REFERENCE MARKER"}).model_dump()
    p = proposal(evaluation)
    replies = Replies([p])
    graph = build_research_graph("single", model_factory=replies, bundle_override=visible,
                                 reference_override=reference, evaluation_bundle_override=evaluation)
    result = graph.invoke({"card_id": "custom_case"})
    model_bundle = json.loads(replies.requests[0][1][1])["evidence_bundle"]
    assert model_bundle["evidence"][utility_id] == definition
    assert "PRIVATE REFERENCE MARKER" not in replies.requests[0][1][1]
    assert result["evidence_bundle"]["evidence"][utility_id] == definition
    assert result["verification"]["primary_contract_pass"]
    assert not result["verification"]["fallback"]
    assert visible["workflow_evidence"] == {}


def test_derived_utility_requires_citations_for_each_component():
    evaluation = build_evidence_bundle("ordinary_inside")
    visible = deepcopy(evaluation)
    uid = "ordinary_inside:action:hold:utility"
    visible["derived_quantities"] = {uid: {"derived": True, "components": {"stress_loss": "ordinary_inside:action:hold:stress_loss", "cvar_95": "ordinary_inside:action:hold:cvar_95"}}}
    p = proposal(evaluation)
    merged = evaluation_bundle_for(visible, evaluation)
    result = assess_proposal(p, merged)
    assert result["numeric_claims_valid"]
    assert not result["derivation_citations_valid"] and not result["primary_contract_pass"]
    p["evidence_ids"].append("ordinary_inside:action:hold:cvar_95")
    assert assess_proposal(p, merged)["primary_contract_pass"]
    assert "derived_quantities" not in evaluation


def test_custom_case_requires_matching_private_reference_and_evaluation_for_derived_values():
    bundle = build_evidence_bundle("ordinary_inside")
    with pytest.raises(ValueError, match="reference_override"):
        build_research_graph(bundle_override=bundle)
    reference = scorecard(load_card("ordinary_inside")).model_dump()
    other = {**reference, "card_id": "other"}
    with pytest.raises(ValueError, match="card IDs differ"):
        build_research_graph(bundle_override=bundle, reference_override=other)
    bundle["evidence"]["ordinary_inside:action:hold:utility"] = {"derived": True}
    with pytest.raises(ValueError, match="evaluation_bundle_override"):
        build_research_graph(bundle_override=bundle, reference_override=reference)


@pytest.mark.parametrize("arm,count", [("single", 1), ("specialists", 3), ("challenged", 5), ("self_review", 5)])
def test_v2_keeps_bounded_calls_and_original_evidence_identical(arm, count):
    replies = {
        "single": [proposal()], "specialists": [report(), report(), proposal()],
        "challenged": [report(), report(), proposal(), {"requires_revision": False, "assessment": "Clear", "issues": []}, proposal()],
        "self_review": [proposal() for _ in range(5)],
    }[arm]
    factory = Replies(replies)
    result = build_research_graph(arm, model_factory=factory).invoke({"card_id": "ordinary_inside"})
    assert len(factory.requests) == count
    assert result["evidence_bundle"]["evidence"] == build_evidence_bundle("ordinary_inside")["evidence"]
    assert result["verification"]["primary_contract_pass"]


def test_missing_or_unknown_decision_basis_fails_schema_contract():
    p = proposal()
    p.pop("decision_basis")
    assert not assess_proposal(p, build_evidence_bundle("ordinary_inside"))["primary_contract_pass"]
    p["decision_basis"] = "profit_hindsight"
    assert not assess_proposal(p, build_evidence_bundle("ordinary_inside"))["primary_contract_pass"]


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), 10 ** 400])
def test_invalid_numeric_types_fail_contract_without_crashing(value):
    p = proposal()
    p["numeric_claims"][0]["value"] = value
    result = assess_proposal(p, build_evidence_bundle("ordinary_inside"))
    assert not result["primary_contract_pass"] and not result["numeric_claims_valid"]
