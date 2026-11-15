"""Sixteen visible decision cards and their sealed sheets.

Numbers are chosen so the general scorecard rules, not card-id branches,
produce the behaviours locked in tests/test_engine.py.
"""

from __future__ import annotations

from risk_desk.schemas import (
    CreditLine,
    DecisionCardVisible,
    Limits,
    Mandate,
    MarketVisible,
    Position,
    SealedSheet,
)

AS_OF = "2026-01-15T10:00:00+00:00"
NEAR = "2026-02-01"
FAR = "2026-07-01"
LATER = "2026-10-01"


def _position(
    position_id: str,
    book_id: str,
    desk: str,
    commodity: str,
    instrument: str,
    quantity: float,
    price: float,
    counterparty: str,
    *,
    start: str = FAR,
    end: str = "2026-07-31",
    ratio: float | None = None,
) -> Position:
    return Position(
        position_id=position_id,
        book_id=book_id,
        desk=desk,  # type: ignore[arg-type]
        commodity=commodity,  # type: ignore[arg-type]
        instrument=instrument,  # type: ignore[arg-type]
        delivery_start=start,
        delivery_end=end,
        quantity=quantity,
        price_eur=price,
        counterparty_id=counterparty,
        physical_hedge_ratio=ratio,
    )


def _market(regime: str, liquidity: str, *, forecast_visible: bool = False) -> MarketVisible:
    prices = {"power": 80.0, "gas": 32.0, "carbon": 70.0}
    weather = {"summary": "mild" if regime == "ordinary" else regime}
    return MarketVisible(
        as_of=AS_OF,
        regime=regime,  # type: ignore[arg-type]
        prices=prices,
        volatility="low" if regime == "ordinary" else "high",
        liquidity=liquidity,  # type: ignore[arg-type]
        weather=weather,
        gas_power_correlation=0.6 if regime == "ordinary" else 0.2,
        forecast_visible=forecast_visible,
    )


def _mandate(
    actor: str,
    role: str,
    desk: str,
    books: list[str],
    appetite: str = "medium",
) -> Mandate:
    return Mandate(
        actor_id=actor,
        role=role,
        desk=desk,  # type: ignore[arg-type]
        may_trade_books=books,
        risk_appetite=appetite,  # type: ignore[arg-type]
    )


def _credit(counterparty: str, status: str = "known", limit: float | None = 5_000_000, used: float | None = 100_000) -> CreditLine:
    return CreditLine(
        counterparty_id=counterparty,
        status=status,  # type: ignore[arg-type]
        limit_eur=limit,
        utilisation_eur=used,
        collateral_eur=50_000,
    )


def _wide() -> Limits:
    return Limits(var_limit_eur=5_000_000, stress_limit_eur=5_000_000)


def _library() -> list[Position]:
    rows: list[Position] = []
    # B1 calm power book, tenors split so the near-month share stays under 0.70.
    for index, (start, qty) in enumerate((("2026-02-01", -32_000.0), ("2026-05-01", -32_000.0), ("2026-08-01", -32_000.0), ("2026-11-01", -24_000.0))):
        rows.append(_position(f"B1-{index}", "B1", "power_hedge", "power", "forward", qty, 80.0, "CP-POWER", start=start, end="2026-12-31"))
    for index, (start, qty) in enumerate((("2026-02-01", -12_000.0), ("2026-05-01", -12_000.0), ("2026-08-01", -12_000.0), ("2026-11-01", -9_000.0))):
        rows.append(_position(f"B12-{index}", "B12", "power_hedge", "power", "forward", qty, 80.0, "CP-POWER", start=start, end="2026-12-31"))
    # B2 gas procurement.
    for index, qty in enumerate((80.0, 70.0, 60.0, 50.0, 40.0)):
        rows.append(_position(f"B2-{index}", "B2", "gas_procurement", "gas", "forward", qty, 32.0, "CP-GAS", start=FAR))
    # B3 retail physical plus a financial hedge the actor can still change.
    rows.append(_position("B3-phys", "B3", "retail_supply", "power", "physical_supply_obligation", 200.0, 78.0, "CP-RETAIL", start=NEAR, end="2026-02-28", ratio=0.40))
    rows.append(_position("B3-fin", "B3", "retail_supply", "power", "forward", -80.0, 80.0, "CP-RETAIL", start=FAR))
    rows.append(_position("B3-fin-near", "B3", "retail_supply", "power", "forward", -20.0, 81.0, "CP-RETAIL", start=NEAR, end="2026-02-28"))
    # B4 proprietary carbon.
    for index, qty in enumerate((30.0, -10.0, 20.0, 15.0)):
        rows.append(_position(f"B4-{index}", "B4", "proprietary", "carbon", "swap", qty, 70.0, "CP-CARBON", start=FAR))
    # B5 large power book used when a hedge should win.
    rows.append(_position("B5-near", "B5", "power_hedge", "power", "forward", 1_500.0, 90.0, "CP-POWER", start=NEAR, end="2026-02-28"))
    rows.append(_position("B5-far", "B5", "power_hedge", "power", "forward", 1_500.0, 88.0, "CP-POWER", start=FAR))
    rows.append(_position("B13-near", "B13", "power_hedge", "power", "forward", 3_500.0, 89.0, "CP-POWER", start=NEAR, end="2026-02-28"))
    rows.append(_position("B13-far", "B13", "power_hedge", "power", "forward", 3_500.0, 89.0, "CP-POWER", start=FAR))
    # B6 retail exposure the prop actor must not touch. Five positions.
    for index in range(5):
        rows.append(_position(f"B6-{index}", "B6", "retail_supply", "power", "forward", -100.0, 82.0, "CP-RETAIL", start=FAR))
    # B7 flat book.
    for index in range(4):
        rows.append(_position(f"B7-{index}", "B7", "power_hedge", "power", "forward", 0.0, 80.0, "CP-POWER", start=FAR))
    # B8 correlation-break book across commodities.
    rows.append(_position("B8-p", "B8", "power_hedge", "power", "forward", -200.0, 85.0, "CP-POWER", start=FAR))
    rows.append(_position("B8-g", "B8", "gas_procurement", "gas", "forward", 180.0, 34.0, "CP-GAS", start=FAR))
    rows.append(_position("B8-c1", "B8", "proprietary", "carbon", "swap", 40.0, 72.0, "CP-CARBON", start=FAR))
    rows.append(_position("B8-c2", "B8", "proprietary", "carbon", "swap", -15.0, 71.0, "CP-CARBON", start=NEAR, end="2026-02-28"))
    rows.append(_position("B8-p2", "B8", "power_hedge", "power", "swap", -80.0, 86.0, "CP-POWER", start=FAR))
    for index in range(4):
        rows.append(_position(f"B11-{index}", "B11", "proprietary", "carbon", "swap", 0.0, 70.0, "CP-CARBON", start=FAR))
    # B9 concentrated near-month power, small enough that the tenor penalty dominates hedging.
    rows.append(_position("B9-near", "B9", "power_hedge", "power", "forward", 100.0, 50.0, "CP-POWER", start=NEAR, end="2026-02-28"))
    rows.append(_position("B9-far", "B9", "power_hedge", "power", "forward", 20.0, 50.0, "CP-POWER", start=FAR))
    # B10 modest power book for the near-tie and the headroom cases. Extra rows fill the library out.
    for index, qty in enumerate((60.0, 55.0, 50.0)):
        rows.append(_position(f"B10-{index}", "B10", "power_hedge", "power", "forward", -qty, 84.0, "CP-POWER", start=FAR if index else NEAR, end="2026-02-28" if index == 0 else "2026-07-31"))
    return rows


LIBRARY = _library()


def _pick(book_ids: set[str]) -> list[Position]:
    return [row for row in LIBRARY if row.book_id in book_ids]


def _card(
    card_id: str,
    mandate: Mandate,
    market: MarketVisible,
    positions: list[Position],
    credit: list[CreditLine],
    limits: Limits,
    logged: str | None = None,
) -> DecisionCardVisible:
    return DecisionCardVisible(
        card_id=card_id,
        mandate=mandate,
        market=market,
        positions=positions,
        credit=credit,
        limits=limits,
        logged_action=logged,  # type: ignore[arg-type]
    )


def _cards() -> dict[str, DecisionCardVisible]:
    power = _credit("CP-POWER")
    retail = _credit("CP-RETAIL")
    gas = _credit("CP-GAS")
    carbon = _credit("CP-CARBON")
    known = [power, retail, gas, carbon]
    return {
        "ordinary_inside": _card(
            "ordinary_inside",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B1"]),
            _market("ordinary", "normal"),
            _pick({"B1"}),
            known,
            _wide(),
            "hold",
        ),
        "var_headroom_tight": _card(
            "var_headroom_tight",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B5"]),
            _market("cold_spell_thin_liquidity", "normal"),
            _pick({"B5"}),
            known,
            Limits(var_limit_eur=18_500, stress_limit_eur=5_000_000),
            "hold",
        ),
        "stress_thin_hedge_capped": _card(
            "stress_thin_hedge_capped",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B13"]),
            _market("ordinary", "thin"),
            _pick({"B13"}),
            known,
            Limits(var_limit_eur=5_000_000, stress_limit_eur=2_000),
            "hold",
        ),
        "physical_obligation": _card(
            "physical_obligation",
            _mandate("A-RETAIL", "desk_trader", "retail_supply", ["B3"], "low"),
            _market("ordinary", "normal"),
            _pick({"B3"}),
            known,
            _wide(),
            "hold",
        ),
        "credit_missing": _card(
            "credit_missing",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B1"]),
            _market("ordinary", "normal"),
            _pick({"B1"}),
            [_credit("CP-POWER", "missing", None, None), retail, gas, carbon],
            _wide(),
            "hold",
        ),
        "credit_downgrade": _card(
            "credit_downgrade",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B5"]),
            _market("cold_spell_thin_liquidity", "normal"),
            _pick({"B5"}),
            [_credit("CP-POWER", "downgraded", 5_000_000, 4_000_000), retail, gas, carbon],
            _wide(),
            "hold",
        ),
        "mandate_prop_on_retail": _card(
            "mandate_prop_on_retail",
            _mandate("A-PROP", "desk_trader", "proprietary", ["B11"], "high"),
            _market("ordinary", "normal"),
            _pick({"B11", "B6"}),
            known,
            _wide(),
            "hedge_50",
        ),
        "near_tie": _card(
            "near_tie",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B12"]),
            _market("ordinary", "normal"),
            _pick({"B12"}),
            known,
            _wide(),
            "hold",
        ),
        "hindsight_trap": _card(
            "hindsight_trap",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B5"]),
            _market("cold_spell_thin_liquidity", "normal"),
            _pick({"B5"}),
            known,
            _wide(),
            "hold",
        ),
        "roll_tenor_breach": _card(
            "roll_tenor_breach",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B9"]),
            _market("ordinary", "normal"),
            _pick({"B9"}),
            known,
            _wide(),
            "hold",
        ),
        "exception_does_not_clear": _card(
            "exception_does_not_clear",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B5"]),
            _market("cold_spell_thin_liquidity", "normal"),
            _pick({"B5"}),
            known,
            Limits(var_limit_eur=1_000, stress_limit_eur=1_000),
            "request_limit_exception",
        ),
        "forecast_not_yet_issued": _card(
            "forecast_not_yet_issued",
            _mandate("A-GAS", "desk_trader", "gas_procurement", ["B2"], "low"),
            _market("ordinary", "normal", forecast_visible=False),
            _pick({"B2"}),
            known,
            _wide(),
            "hold",
        ),
        "zero_exposure": _card(
            "zero_exposure",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B7"]),
            _market("ordinary", "normal"),
            _pick({"B7"}),
            known,
            _wide(),
            "hold",
        ),
        "correlation_break_book": _card(
            "correlation_break_book",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B8"]),
            _market("correlation_break", "normal"),
            _pick({"B8"}),
            known,
            _wide(),
            "hold",
        ),
        "escalate_when_no_hedge": _card(
            "escalate_when_no_hedge",
            _mandate("A-RISK", "observer", "power_hedge", ["B5"], "low"),
            _market("cold_spell_thin_liquidity", "thin"),
            _pick({"B5"}),
            known,
            Limits(var_limit_eur=1_000, stress_limit_eur=1_000),
            "hold",
        ),
        "cold_spell_power": _card(
            "cold_spell_power",
            _mandate("A-POWER", "desk_trader", "power_hedge", ["B5"]),
            _market("cold_spell_thin_liquidity", "normal"),
            _pick({"B5"}),
            known,
            _wide(),
            "hold",
        ),
    }


CARDS = _cards()

SEALED: dict[str, SealedSheet] = {
    card_id: SealedSheet(
        card_id=card_id,
        realised_pnl_eur=25_000.0 if card_id == "hindsight_trap" else -2_000.0,
        latent_regime="cold_spell_unobserved" if card_id == "hindsight_trap" else "same_as_visible",
        hidden_forecast_value=120.0 if card_id == "forecast_not_yet_issued" else None,
    )
    for card_id in CARDS
}


def card_ids() -> list[str]:
    return list(CARDS)


def load_card(card_id: str) -> DecisionCardVisible:
    return CARDS[card_id]


def load_sealed(card_id: str) -> SealedSheet:
    return SEALED[card_id]


def all_positions() -> list[Position]:
    return list(LIBRARY)
