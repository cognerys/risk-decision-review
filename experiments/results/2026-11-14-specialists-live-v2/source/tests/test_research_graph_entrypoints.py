"""Offline checks for the opt-in CLI/Studio research entrypoints."""
import json
from pathlib import Path

import pytest

from risk_desk import tracing
from risk_desk.cli import main


@pytest.mark.parametrize("arm,expected_calls", [("single", 1), ("specialists", 3), ("challenged", 5), ("self_review", 5)])
def test_cli_research_arms_run_offline_with_expected_stages(arm, expected_calls, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("RISK_DESK_LIVE", "0")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr(tracing, "MIRROR_PATH", tmp_path / "trace.jsonl")
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--card", "ordinary_inside", "--arm", arm]) == 0
    recommendation = json.loads(capsys.readouterr().out)
    assert recommendation["arm"] == arm
    assert recommendation["action_or_abstain"] == "hold"
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert len([event for event in events if event["event"] == "model_stage"]) == expected_calls
    assert next(event for event in events if event["event"] == "verification")["payload"]["fallback"]
    assert not (tmp_path / "runs/checkpoints.sqlite").exists()


def test_studio_research_entrypoint_preserves_legacy_and_uses_studio_persistence():
    from risk_desk.graphs.research_desk import graph
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "langgraph.json").read_text())["graphs"]
    assert entries["desk"] == "./src/risk_desk/graphs/desk.py:graph"
    assert entries["research_desk"] == "./src/risk_desk/graphs/research_desk.py:graph"
    assert graph.checkpointer is None
    nodes = graph.get_graph().nodes
    assert {"market_physical", "credit_governance", "propose", "challenge", "revise", "verify"}.issubset(nodes)
