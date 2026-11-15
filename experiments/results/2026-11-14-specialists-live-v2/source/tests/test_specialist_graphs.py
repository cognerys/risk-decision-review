"""Offline graph tests use scripted role outputs; they establish no model skill."""
import json

from langchain_core.messages import AIMessage
import pytest

from risk_desk import tracing
from risk_desk.graphs.specialists import (
    ARMS, Proposal, _decode, assess_proposal, build_evidence_bundle, build_research_graph,
)


def proposal(card="ordinary_inside", action="hold"):
    bundle = build_evidence_bundle(card)
    ids = [f"{card}:action:hold:stress_loss", f"{card}:action:{'hold' if action == 'abstain' else action}:utility"]
    return {"action_or_abstain": action, "reason": "fixture", "procedural": "Synthetic fixture",
            "economic": "Synthetic numeric claims", "evidential": "Supplied values only",
            "evidence_ids": ids, "numeric_claims": [{"evidence_id": i, "value": bundle["evidence"][i]} for i in ids]}


def report(label="fixture"):
    return {"summary": label, "findings": [{"issue": label, "evidence_ids": ["ordinary_inside:credit"],
                                           "implication": "Consider credit", "uncertainty": "No new evidence"}]}


class ScriptedRoles:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, settings):
        return self

    def invoke(self, messages):
        self.requests.append(messages)
        reply = self.replies.pop(0)
        return AIMessage(content=reply if isinstance(reply, str) else json.dumps(reply),
                         usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150})


@pytest.fixture(autouse=True)
def isolated_trace(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")


def invoke(arm, replies):
    factory = ScriptedRoles(replies)
    result = build_research_graph(arm, model_factory=factory).invoke(
        {"card_id": "ordinary_inside", "run_id": "test-run", "job_id": f"test-{arm}"})
    return result, factory


def test_bundle_has_action_scoped_numbers_and_no_reference_answer_or_hindsight():
    bundle = build_evidence_bundle("ordinary_inside")
    assert "ordinary_inside:action:hold:stress_loss" in bundle["evidence"]
    assert "ordinary_inside:action:hedge_75:stress_loss" in bundle["evidence"]
    encoded = json.dumps(bundle)
    assert "scorecard" not in encoded and "realised_pnl" not in encoded
    assert "logged_action" not in bundle["card"]
    assert len(bundle["actions"]) == 9


def test_valid_structured_proposal_passes_primary_and_preserves_usage():
    result, factory = invoke("single", [proposal()])
    assert len(factory.requests) == 1
    assert result["verification"]["primary_contract_pass"]
    assert not result["verification"]["fallback"]
    assert result["stages"][0]["usage"]["total_units"] == 150
    assert result["initial_proposal"] == result["proposal"]


@pytest.mark.parametrize("mutate", [
    lambda p: p["numeric_claims"][0].update(value=True),
    lambda p: p["numeric_claims"][0].update(value=float("nan")),
    lambda p: p["numeric_claims"][0].update(value=99999999.0),
    lambda p: p["numeric_claims"].pop(),
    lambda p: p["evidence_ids"].pop(),
    lambda p: p.update(action_or_abstain="invented_action"),
    lambda p: p["evidence_ids"].append("invented-id"),
])
def test_primary_rejects_bad_claims_missing_coverage_and_invalid_decisions(mutate):
    p = proposal()
    mutate(p)
    assert not assess_proposal(p, build_evidence_bundle("ordinary_inside"))["primary_contract_pass"]


def test_numeric_tolerance_and_abstention_requirement():
    p = proposal("credit_missing", "abstain")
    assert assess_proposal(p, build_evidence_bundle("credit_missing"))["primary_contract_pass"]
    p["numeric_claims"][0]["value"] += .001
    assert assess_proposal(p, build_evidence_bundle("credit_missing"))["primary_contract_pass"]


def test_specialists_are_independent_and_their_findings_reach_proposer():
    result, factory = invoke("specialists", [report("market observation"), report("credit observation"), proposal()])
    assert len(factory.requests) == 3
    second_request = json.loads(factory.requests[1][1][1])
    assert "specialist_reports" not in second_request
    proposer_payload = json.loads(factory.requests[2][1][1])
    assert [r["report"]["summary"] for r in proposer_payload["specialist_reports"]] == ["market observation", "credit observation"]
    assert [s["role"] for s in result["stages"]] == ["market_physical", "credit_governance", "proposer"]


def test_invalid_specialist_citations_are_retained_but_not_used_as_advice():
    bad = report()
    bad["findings"][0]["evidence_ids"] = ["invented"]
    result, factory = invoke("specialists", [bad, report(), proposal()])
    assert result["specialist_reports"][0]["usable"] is False
    assert result["specialist_reports"][0]["report"] == {}
    assert result["stages"][0]["parsed"] == bad
    assert "invented" not in factory.requests[2][1][1]


def test_challenge_causes_one_revision_preserving_both_proposals():
    bad = proposal()
    bad["numeric_claims"][0]["value"] += 123
    challenge = {"requires_revision": True, "assessment": "Wrong stress value",
                 "issues": [{"issue": "Incorrect stress", "evidence_ids": ["ordinary_inside:action:hold:stress_loss"],
                             "requested_change": "Use supplied stress loss"}]}
    result, factory = invoke("challenged", [report(), report(), bad, challenge, proposal()])
    assert len(factory.requests) == 5 and result["revision_count"] == 1
    assert result["initial_proposal"] == bad and result["proposal"] == proposal()
    assert not assess_proposal(result["initial_proposal"], result["evidence_bundle"])["primary_contract_pass"]
    assert result["verification"]["primary_contract_pass"]
    challenger_payload = json.loads(factory.requests[3][1][1])
    assert "specialist_reports" not in challenger_payload
    assert json.loads(factory.requests[4][1][1])["challenge"] == challenge


@pytest.mark.parametrize("challenge", [
    {"requires_revision": False, "assessment": "No problem", "issues": []},
    {"requires_revision": True, "assessment": "Unsupported", "issues": []},
    {"requires_revision": True, "assessment": "Unsupported", "issues": [{"issue": "Invented", "evidence_ids": ["fake"], "requested_change": "Change"}]},
    "malformed",
])
def test_clear_or_unusable_challenge_still_gets_one_confirmation_pass(challenge):
    result, factory = invoke("challenged", [report(), report(), proposal(), challenge, proposal()])
    assert len(factory.requests) == 5
    assert result["revision_count"] == 1
    assert result["proposal"] == result["initial_proposal"]
    final_payload = json.loads(factory.requests[4][1][1])
    if not result["challenge"]["usable"]:
        assert final_payload["challenge"] == {}
        assert not final_payload["challenge_usable"]


def test_generic_self_review_is_five_calls_with_every_intermediate_retained():
    replies = [proposal() for _ in range(5)]
    for i, item in enumerate(replies):
        item["reason"] = f"pass-{i}"
    result, factory = invoke("self_review", replies)
    assert len(factory.requests) == 5 and result["revision_count"] == 4
    assert result["initial_proposal"]["reason"] == "pass-0"
    assert [s["parsed"]["reason"] for s in result["stages"]] == [f"pass-{i}" for i in range(5)]
    assert not result["specialist_reports"]


def test_fallback_is_separate_and_never_changes_retained_bad_proposal():
    bad = proposal()
    bad["numeric_claims"][0]["value"] += 123
    result, _ = invoke("single", [bad])
    assert result["proposal"] == bad
    assert result["verification"]["fallback"]
    assert result["verification"]["fallback_source"] == "deterministic_scorecard"
    assert result["recommendation"]["action_or_abstain"] == "hold"


def test_parser_handles_text_blocks_and_rejects_reasoning_content():
    p = proposal()
    assert _decode([{"type": "text", "text": json.dumps(p)}], Proposal)["parsed"] == p
    assert _decode([{"type": "reasoning", "text": json.dumps(p)}], Proposal)["parse_status"] == "no_text"


def test_every_arm_gets_identical_original_information():
    bundles = []
    for arm in ARMS:
        replies = {
            "single": [proposal()],
            "specialists": [report(), report(), proposal()],
            "challenged": [report(), report(), proposal(), {"requires_revision": False, "assessment": "No issues", "issues": []}, proposal()],
            "self_review": [proposal() for _ in range(5)],
        }[arm]
        result, _ = invoke(arm, replies)
        bundles.append(result["evidence_bundle"])
    assert all(bundle == bundles[0] for bundle in bundles)
