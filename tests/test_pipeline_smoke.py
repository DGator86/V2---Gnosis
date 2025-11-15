from __future__ import annotations

"""Smoke test for the pipeline runner."""

from datetime import datetime
from pathlib import Path
from typing import Dict

from agents.base import PrimaryAgent, ComposerAgent, TradeAgent
from engines.base import Engine
from engines.orchestration.pipeline_runner import PipelineRunner
from ledger.ledger_store import LedgerStore
from schemas.core_schemas import EngineOutput, StandardSnapshot, Suggestion


class DummyEngine(Engine):
    def run(self, symbol: str, now: datetime) -> EngineOutput:
        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=now,
            features={"gamma": 1.0},
            confidence=1.0,
        )


class DummyPrimaryAgent(PrimaryAgent):
    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        return Suggestion(
            id="agent",
            layer="primary_hedge",
            symbol=snapshot.symbol,
            action="flat",
            confidence=0.5,
            forecast={},
            reasoning="test",
            tags=[],
        )


class DummyComposer(ComposerAgent):
    def compose(self, snapshot: StandardSnapshot, suggestions):
        return Suggestion(
            id="composer",
            layer="composer",
            symbol=snapshot.symbol,
            action="flat",
            confidence=0.5,
            forecast={},
            reasoning="test",
            tags=[],
        )


class DummyTradeAgent(TradeAgent):
    def generate_trades(self, suggestion: Suggestion):
        return []


def test_pipeline_smoke(tmp_path: Path) -> None:
    engines: Dict[str, Engine] = {"hedge": DummyEngine()}
    primary_agents: Dict[str, PrimaryAgent] = {"primary_hedge": DummyPrimaryAgent()}
    composer: ComposerAgent = DummyComposer()
    trade_agent: TradeAgent = DummyTradeAgent()
    ledger_store = LedgerStore(tmp_path / "ledger.jsonl")

    runner = PipelineRunner(
        symbol="SPY",
        engines=engines,
        primary_agents=primary_agents,
        composer=composer,
        trade_agent=trade_agent,
        ledger_store=ledger_store,
        config={},
    )

    now = datetime.utcnow()
    result = runner.run_once(now)
    assert result["snapshot"].symbol == "SPY"
