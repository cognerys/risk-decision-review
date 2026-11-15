"""Offline foundation checks. No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest

from risk_desk.cli import main
from risk_desk.config import Settings, live_enabled
from risk_desk.llm import STUB_CONTENT, build_chat_model
from risk_desk.policy import (
    ACTIONS,
    DESK_LAMBDAS,
    DESKS,
    GOVERNANCE_PENALTY_BASE,
    NEAR_TIE_BAND,
    NEAR_TIE_EUR,
    NEAR_TIE_FRACTION,
)
from risk_desk.schemas import (
    Action,
    CreditLine,
    DecisionCardVisible,
    Desk,
    Evidence,
    Limits,
    Mandate,
    MarketVisible,
    Position,
    Recommendation,
    SealedSheet,
)
from risk_desk.tracing import MIRROR_PATH, langsmith_env, mirror_event


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("RISK_DESK_LIVE", raising=False)


def _card() -> DecisionCardVisible:
    return DecisionCardVisible(
        card_id="card-1",
        mandate=Mandate(
            actor_id="actor-1",
            role="trader",
            desk="power_hedge",
            may_trade_books=["book-power"],
            risk_appetite="medium",
        ),
        market=MarketVisible(
            as_of="2026-01-15T10:00:00Z",
            regime="ordinary",
            prices={"power": 80.0, "gas": 30.0, "carbon": 70.0},
            volatility="medium",
            liquidity="normal",
            weather={"summary": "mild"},
            gas_power_correlation=0.4,
            forecast_visible=False,
        ),
        positions=[
            Position(
                position_id="pos-1",
                book_id="book-power",
                desk="power_hedge",
                commodity="power",
                instrument="forward",
                delivery_start="2026-02-01",
                delivery_end="2026-02-28",
                quantity=-125.0,
                price_eur=82.5,
                counterparty_id="cp-1",
                physical_hedge_ratio=0.98,
            )
        ],
        credit=[
            CreditLine(
                counterparty_id="cp-1",
                status="known",
                limit_eur=1_000_000.0,
                utilisation_eur=100_000.0,
                collateral_eur=50_000.0,
            )
        ],
        limits=Limits(var_limit_eur=250_000.0, stress_limit_eur=500_000.0),
        logged_action="hold",
    )


def _mirror_text() -> str:
    if not MIRROR_PATH.exists():
        return ""
    return MIRROR_PATH.read_text(encoding="utf-8")


def test_schema_round_trip() -> None:
    card = _card()
    assert DecisionCardVisible.model_validate(card.model_dump()) == card
    assert set(ACTIONS) == set(get_args(Action))
    assert set(DESKS) == set(get_args(Desk))

    missing = CreditLine(
        counterparty_id="cp-2",
        status="missing",
        limit_eur=None,
        utilisation_eur=None,
        collateral_eur=0.0,
    )
    assert CreditLine.model_validate(missing.model_dump()) == missing
    with pytest.raises(ValueError):
        CreditLine(
            counterparty_id="cp-3",
            status="known",
            limit_eur=None,
            utilisation_eur=None,
            collateral_eur=0.0,
        )

    sealed = SealedSheet(
        card_id="card-1",
        realised_pnl_eur=-15.5,
        latent_regime="cold_spell_thin_liquidity",
        hidden_forecast_value=1.25,
    )
    assert SealedSheet.model_validate(sealed.model_dump()) == sealed

    evidence = Evidence(
        evidence_id="ev-1",
        kind="var",
        method="empirical_pnl_quantile_v1",
        units="EUR",
        value={"var_95": 10.0},
        book_id="book-power",
    )
    assert Evidence.model_validate(evidence.model_dump()) == evidence
    with pytest.raises(ValueError):
        Evidence(
            evidence_id="ev-2",
            kind="var",
            method="empirical_pnl_quantile_v1",
            units="EUR",
            value={1, 2},
        )

    recommendation = Recommendation(
        card_id="card-1",
        arm="desk",
        action_or_abstain="abstain",
        reason="foundation_stub",
        procedural="p",
        economic="e",
        evidential="v",
        evidence_ids=["ev-1"],
        escalation_pending=False,
    )
    assert Recommendation.model_validate(recommendation.model_dump()) == recommendation


def test_visible_card_has_no_realised_pnl() -> None:
    forbidden = ("pnl", "realised", "realized", "latent")
    for model in (DecisionCardVisible, MarketVisible, Position, Mandate, Limits, CreditLine):
        for name in model.model_fields:
            lowered = name.lower()
            assert not any(part in lowered for part in forbidden)
    assert "realised_pnl_eur" in SealedSheet.model_fields
    payload = _card().model_dump()
    payload["realised_pnl_eur"] = 10.0
    with pytest.raises(ValueError):
        DecisionCardVisible.model_validate(payload)


def test_policy_constants() -> None:
    assert isinstance(ACTIONS, tuple)
    assert ACTIONS == (
        "hold",
        "hedge_25",
        "hedge_50",
        "hedge_75",
        "reduce_25",
        "reduce_50",
        "roll_near_to_far",
        "escalate",
        "request_limit_exception",
    )
    assert DESK_LAMBDAS == {
        "power_hedge": 0.35,
        "gas_procurement": 0.45,
        "retail_supply": 0.55,
        "proprietary": 0.15,
    }
    assert NEAR_TIE_FRACTION == 0.05
    assert NEAR_TIE_EUR == 2000
    assert NEAR_TIE_BAND == (0.05, 2000)
    assert GOVERNANCE_PENALTY_BASE == 50_000


def test_live_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RISK_DESK_LIVE", "1")
    assert live_enabled() is True
    monkeypatch.setenv("RISK_DESK_LIVE", "true")
    assert live_enabled() is True
    monkeypatch.setenv("RISK_DESK_LIVE", "TRUE")
    assert live_enabled() is True
    for raw in ("0", "false", "yes", "on", ""):
        monkeypatch.setenv("RISK_DESK_LIVE", raw)
        assert live_enabled() is False


def test_scripted_model_abstains_offline() -> None:
    settings = Settings(live=False)
    model = build_chat_model(settings)
    message = model.invoke("hello")
    bound = model.bind_tools([{"name": "noop"}]).invoke("hello")
    for result in (message, bound):
        assert result.content == STUB_CONTENT
        assert not result.tool_calls


def test_mirror_redacts_secret_values() -> None:
    before = _mirror_text()
    mirror_event(
        {
            "api_key": "not-a-real-secret",
            "detail": "sk-fake-value",
            "status": "recorded",
            "nested": {"client_secret": "hidden", "fine": 1},
        }
    )
    added = _mirror_text()[len(before) :]
    assert "sk-" not in added
    assert "api_key" not in added
    assert "not-a-real-secret" not in added
    assert "client_secret" not in added
    parsed = json.loads(added.strip().splitlines()[-1])
    assert parsed["status"] == "recorded"
    assert parsed["nested"] == {"fine": 1}


def test_show_config_omits_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "sk-foundation-do-not-print-9f3a"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("RISK_DESK_MODEL", "gpt-6-luna")
    monkeypatch.setenv("RISK_DESK_LIVE", "0")
    assert main(["show-config"]) == 0
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert "gpt-6-luna" in captured.out
    assert "live=false" in captured.out
    assert "reasoning_note=" in captured.out


def test_langsmith_env_hides_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "sk-langsmith-secret")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_PROJECT", "risk-desk-function")
    info = langsmith_env()
    blob = json.dumps(info)
    assert "sk-langsmith-secret" not in blob
    assert info["project"] == "risk-desk-function"
    assert info["langsmith_tracing_present"] is True
    assert info["langsmith_api_key_present"] is True


def test_mirror_path_is_runs_file() -> None:
    assert Path("runs/mirror.jsonl") == MIRROR_PATH
