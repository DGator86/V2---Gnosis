from __future__ import annotations

"""Pipeline orchestration for Super Gnosis."""

from datetime import datetime
from typing import Any, Dict, List

from agents.base import ComposerAgent, PrimaryAgent, TradeAgent
from engines.base import Engine
from ledger.ledger_store import LedgerStore
from schemas.core_schemas import EngineOutput, LedgerRecord, StandardSnapshot, Suggestion, TradeIdea


class PipelineRunner:
    """Coordinate a single pipeline pass."""

    def __init__(
        self,
        symbol: str,
        engines: Dict[str, Engine],
        primary_agents: Dict[str, PrimaryAgent],
        composer: ComposerAgent,
        trade_agent: TradeAgent,
        ledger_store: LedgerStore,
        config: Dict[str, Any],
    ) -> None:
        self.symbol = symbol
        self.engines = engines
        self.primary_agents = primary_agents
        self.composer = composer
        self.trade_agent = trade_agent
        self.ledger_store = ledger_store
        self.config = config

    def run_once(self, now: datetime) -> Dict[str, object]:
        engine_outputs: Dict[str, EngineOutput] = {
            name: engine.run(self.symbol, now) for name, engine in self.engines.items()
        }

        snapshot = self._build_snapshot(engine_outputs)
        primary_suggestions: List[Suggestion] = [
            agent.step(snapshot) for agent in self.primary_agents.values()
        ]
        composite_suggestion = self.composer.compose(snapshot, primary_suggestions)
        trade_ideas = self.trade_agent.generate_trades(composite_suggestion)

        record = LedgerRecord(
            timestamp=now,
            symbol=self.symbol,
            snapshot=snapshot,
            primary_suggestions=primary_suggestions,
            composite_suggestion=composite_suggestion,
            trade_ideas=trade_ideas,
        )
        self.ledger_store.append(record)

        return {
            "snapshot": snapshot,
            "engine_outputs": engine_outputs,
            "primary_suggestions": primary_suggestions,
            "composite_suggestion": composite_suggestion,
            "trade_ideas": trade_ideas,
        }

    def _build_snapshot(self, engine_outputs: Dict[str, EngineOutput]) -> StandardSnapshot:
        def features(kind: str) -> Dict[str, float]:
            output = engine_outputs.get(kind)
            return output.features if output else {}

        timestamp = next(iter(engine_outputs.values())).timestamp if engine_outputs else datetime.utcnow()

        return StandardSnapshot(
            symbol=self.symbol,
            timestamp=timestamp,
            hedge=features("hedge"),
            liquidity=features("liquidity"),
            sentiment=features("sentiment"),
            elasticity=features("elasticity"),
        )
