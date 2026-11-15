"""Offline regressions for response decoding and attribution, not model skill."""
import importlib.util
import json
from pathlib import Path

from langchain_core.messages import AIMessage
import pytest

from risk_desk.graphs import workflows
from risk_desk.responses import decode_response
from risk_desk import tracing


def decision():
    return {"action_or_abstain": "hold", "reason": "fixture", "evidence_ids": ["ordinary_inside:utility"]}


@pytest.mark.parametrize("wrap", [lambda s: s, lambda s: [{"type": "text", "text": s}],
                                  lambda s: [{"type": "output_text", "text": s}],
                                  lambda s: "```json\n" + s + "\n```"])
def test_supported_text_shapes_preserve_the_actual_decision(wrap):
    raw = wrap(json.dumps(decision()))
    response = decode_response(raw)
    assert response["parse_status"] == "ok"
    assert response["proposal"] == decision()
    assert response["raw_content"] == raw


@pytest.mark.parametrize("raw,status", [
    ('{"type":"text","text":"hold"}', "invalid_shape"),
    ('{"action_or_abstain":[],"evidence_ids":[]}', "invalid_shape"),
    ('{"action_or_abstain":"hold","evidence_ids":[{}]}', "invalid_shape"),
    ('[1,2]', "invalid_shape"),
    ('Here is my answer: hold', "invalid_json"),
    ([{"type": "reasoning", "text": json.dumps(decision())}], "no_text"),
    ([{"type": "refusal", "refusal": "No"}], "no_text"),
])
def test_bad_shapes_are_recorded_instead_of_crashing_or_becoming_decisions(raw, status):
    response = decode_response(raw)
    assert response["parse_status"] == status
    assert response["proposal"] == {}


def test_embedded_secret_is_redacted_from_retained_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret-value")
    raw = json.dumps({**decision(), "reason": "Seen synthetic-secret-value and sk-fake-secret"})
    saved = json.dumps(decode_response(raw))
    assert "synthetic-secret-value" not in saved
    assert "sk-fake-secret" not in saved


def fake_agent(monkeypatch, content):
    class Agent:
        def invoke(self, *args, **kwargs):
            return {"messages": [AIMessage(content=content)]}
    monkeypatch.setattr(workflows, "create_agent", lambda *args, **kwargs: Agent())
    monkeypatch.setattr(workflows, "build_chat_model", lambda settings: object())


def test_valid_content_block_survives_verification_and_has_trace_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    fake_agent(monkeypatch, [{"type": "text", "text": json.dumps(decision())}])
    result = workflows.build_react_graph(checkpointer=None).invoke(
        {"card_id": "ordinary_inside", "arm": "react", "run_id": "run-a", "job_id": "B-ordinary"})
    assert result["recommendation"]["reason"] == "fixture"
    assert result["verification"]["fallback"] is False
    assert result["response"]["parse_status"] == "ok"
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert all(row["run_id"] == "run-a" and row["job_id"] == "B-ordinary" for row in events)
    assert {x["event"] for x in events} >= {"response", "proposal", "verification", "verify"}


def test_fallback_is_explicit_even_when_abstention_reason_is_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    fake_agent(monkeypatch, "malformed response")
    result = workflows.build_react_graph(checkpointer=None).invoke({"card_id": "credit_missing", "arm": "react"})
    assert result["recommendation"]["reason"] == "missing_credit"
    assert result["verification"]["fallback"] is True
    assert "response_parse_failed" in result["verification"]["rejection_reasons"]
    assert result["proposal"] == {}


def test_unknown_citations_remain_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    fake_agent(monkeypatch, json.dumps({**decision(), "evidence_ids": ["invented-id"]}))
    result = workflows.build_react_graph(checkpointer=None).invoke({"card_id": "ordinary_inside", "arm": "react"})
    assert result["response"]["parse_status"] == "ok"
    assert result["verification"]["fallback"] is True
    assert result["verification"]["citation_ids_valid"] is False


def load_runner():
    path = Path(__file__).resolve().parents[1] / "experiments/run_instrumented_study.py"
    spec = importlib.util.spec_from_file_location("instrumented_study", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_study_retains_each_stage_and_complete_probe_references(monkeypatch, tmp_path):
    runner = load_runner()
    monkeypatch.setenv("RISK_DESK_LIVE", "1")
    result = runner.run_study(tmp_path / "study", live=False)
    assert result["mode"] == "offline-scripted"
    assert result["model_calls"] == 0
    assert result["planned_jobs"] == result["completed_jobs"] == 42
    live_arms = [row for row in result["rows"] if row["arm"] != "scorecard"]
    assert len(live_arms) == 26
    assert all(row["verification"]["fallback"] for row in live_arms)
    assert all(row["response"]["raw_content"] for row in live_arms)
    assert len(result["comparisons"]) == 6
    assert all(row["evaluable_final_output"] for row in result["comparisons"])
    assert len({row["job_id"] for row in result["rows"]}) == 42
    assert os_environ_live() == "1"  # caller environment restored
    with pytest.raises(FileExistsError):
        runner.run_study(tmp_path / "study")


def os_environ_live():
    import os
    return os.environ.get("RISK_DESK_LIVE")


def test_global_call_cap_refuses_next_invocation():
    runner = load_runner()
    class Inner:
        def invoke(self, value):
            return value
    counter = {"calls": 0}
    model = runner.CountedModel(Inner(), counter, 1)
    assert model.invoke("first") == "first"
    with pytest.raises(runner.CallLimit):
        model.invoke("second")
    assert counter["calls"] == 1


def test_missing_or_failed_probe_reference_is_not_counted_as_agreement():
    runner = load_runner()
    result = runner.comparisons([{"job_id": "leak-x", "reference_job_id": "B-x", "status": "error"}])
    assert result[0]["final_action_equal"] is None
    assert result[0]["proposal_action_equal"] is None


@pytest.mark.parametrize("with_tools", [False, True])
def test_call_cap_is_preserved_by_real_agent_model_binding(with_tools):
    from langchain.agents import create_agent
    from risk_desk.llm import ScriptedChatModel
    from risk_desk.tools.desk_tools import make_tools
    runner = load_runner()
    counter = {"calls": 0}
    model = runner.CountedModel(ScriptedChatModel(), counter, 1)
    agent = create_agent(model, make_tools("ordinary_inside") if with_tools else [])
    agent.invoke({"messages": [("user", "review")]})
    assert counter["calls"] == 1
    with pytest.raises(runner.CallLimit):
        agent.invoke({"messages": [("user", "review again")]})


@pytest.mark.parametrize("override", [
    {"action_or_abstain": "invented_trade"},
    {"action_or_abstain": "hedge_75"},
    {"action_or_abstain": ["hedge_75"]},
])
def test_committee_cannot_bypass_action_and_evidence_checks(monkeypatch, tmp_path, override):
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    fake_agent(monkeypatch, "unparseable")
    graph = workflows.build_desk_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "committee-test"}}
    paused = graph.invoke({"card_id": "ordinary_inside", "arm": "desk", "auto_committee": False}, config)
    assert paused["__interrupt__"]
    result = graph.invoke(Command(resume=override), config)
    assert result["recommendation"]["action_or_abstain"] == "hold"
    assert result["committee_decision"]["status"] == "rejected"
    assert result["recommendation"]["escalation_pending"] is True


def test_committee_override_is_verified_and_has_its_own_explanation(monkeypatch, tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    fake_agent(monkeypatch, "unparseable")
    graph = workflows.build_desk_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "committee-valid"}}
    paused = graph.invoke({"card_id": "ordinary_inside", "arm": "desk", "auto_committee": False}, config)
    assert paused["__interrupt__"]
    result = graph.invoke(Command(resume={"action_or_abstain": "abstain", "reason": "review",
                         "evidence_ids": ["ordinary_inside:utility"], "economic": "Reviewer explanation"}), config)
    assert result["committee_decision"] == {"status": "accepted", "override": True, "requested_action": "abstain"}
    assert result["recommendation"]["action_or_abstain"] == "abstain"
    assert result["recommendation"]["economic"] == "Reviewer explanation"
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert len([x for x in events if x["event"] == "response"]) == 1


@pytest.mark.parametrize("builder", [workflows.build_supervisor_graph, workflows.build_desk_graph])
def test_empty_positions_fail_explicitly_instead_of_silently_ending_at_fanout(monkeypatch, builder):
    empty = workflows.load_card("ordinary_inside").model_copy(update={"positions": []})
    monkeypatch.setattr(workflows, "load_card", lambda card_id: empty)
    with pytest.raises(ValueError, match="at least one position"):
        builder(checkpointer=None).invoke({"card_id": "ordinary_inside", "arm": "desk"})


def test_repeated_cli_reviews_do_not_inherit_checkpoint_identity(monkeypatch, tmp_path, capsys):
    from risk_desk.cli import _run
    monkeypatch.setenv("RISK_DESK_LIVE", "0")
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    monkeypatch.chdir(tmp_path)
    assert _run("ordinary_inside", "desk") == _run("ordinary_inside", "desk") == 0
    capsys.readouterr()
    responses = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()
                 if json.loads(line)["event"] == "response"]
    assert len(responses) == 2
    assert responses[0]["run_id"] != responses[1]["run_id"]
    assert not (tmp_path / "runs/checkpoints.sqlite").exists()
