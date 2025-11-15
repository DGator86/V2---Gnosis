from __future__ import annotations

"""Unit tests for core schemas."""

from datetime import datetime

from schemas.core_schemas import EngineOutput, LedgerRecord, StandardSnapshot, Suggestion, TradeIdea, TradeLeg


def test_engine_output_roundtrip() -> None:
    output = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.utcnow(),
        features={"gamma": 1.0},
        confidence=0.9,
        regime="gamma_squeeze",
    )
    assert output.kind == "hedge"
    assert output.features["gamma"] == 1.0


def test_trade_idea_structure() -> None:
    leg = TradeLeg(instrument_type="C", direction="buy", qty=1, strike=400.0, expiry="2024-12-20")
    idea = TradeIdea(
        id="idea",
        symbol="SPY",
        strategy_type="call_debit_spread",
        side="long",
        legs=[leg],
        cost_per_unit=1.0,
        max_loss=1.0,
        max_profit=2.0,
        breakeven_levels=[401.0],
        target_exit_price=405.0,
        stop_loss_price=395.0,
        recommended_units=1,
        confidence=0.8,
        rationale="Test",
        tags=["test"],
    )
    assert idea.legs[0].instrument_type == "C"


def test_ledger_record_structure() -> None:
    snapshot = StandardSnapshot(
        symbol="SPY",
        timestamp=datetime.utcnow(),
        hedge={},
        liquidity={},
        sentiment={},
        elasticity={},
    )
    suggestion = Suggestion(
        id="sug",
        layer="primary_hedge",
        symbol="SPY",
        action="flat",
        confidence=0.5,
        forecast={},
        reasoning="Neutral",
        tags=[],
    )
    record = LedgerRecord(
        timestamp=datetime.utcnow(),
        symbol="SPY",
        snapshot=snapshot,
        primary_suggestions=[suggestion],
        composite_suggestion=suggestion,
        trade_ideas=[],
    )
    assert record.symbol == "SPY"
