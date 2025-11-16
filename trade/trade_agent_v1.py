"""Trade Agent v1.0 implementation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence
from uuid import uuid4

import polars as pl

from agents.base import TradeAgent
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from schemas.core_schemas import Suggestion, TradeIdea, TradeLeg

_CONTRACT_SIZE = 100


@dataclass
class _OptionContract:
    strike: float
    expiry: str
    option_type: str
    mid: float

    @property
    def is_call(self) -> bool:
        return self.option_type.lower() == "call"

    @property
    def is_put(self) -> bool:
        return self.option_type.lower() == "put"


class TradeAgentV1(TradeAgent):
    """Map composer suggestions into concrete trade ideas."""

    def __init__(self, adapter: OptionsChainAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def generate_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        if suggestion.confidence < self.config.get("min_confidence", 0.5):
            return []

        now = datetime.now(timezone.utc)
        chain = self.adapter.fetch_chain(suggestion.symbol, now)
        if isinstance(chain, pl.DataFrame) and chain.is_empty():
            return [self._stock_trade(suggestion)]

        contracts = self._extract_contracts(chain)
        if not contracts:
            return [self._stock_trade(suggestion)]

        ideas: List[TradeIdea] = []
        if suggestion.action == "long":
            ideas.append(self._stock_trade(suggestion))
            ideas.append(self._call_debit_spread(suggestion, contracts))
            ideas.append(self._calendar_spread(suggestion, contracts))
        elif suggestion.action == "short":
            ideas.append(self._short_stock_trade(suggestion))
            ideas.append(self._put_debit_spread(suggestion, contracts))
        elif suggestion.action == "spread":
            ideas.append(self._call_debit_spread(suggestion, contracts))
            ideas.append(self._put_debit_spread(suggestion, contracts))
        elif suggestion.action in {"flat", "complex"}:
            ideas.append(self._iron_condor(suggestion, contracts))
            ideas.append(self._calendar_spread(suggestion, contracts))

        filtered = [idea for idea in ideas if idea is not None]
        max_legs = self.config.get("max_legs", 4)
        return [idea for idea in filtered if len(idea.legs) <= max_legs]

    def _extract_contracts(self, chain: pl.DataFrame) -> List[_OptionContract]:
        records: List[_OptionContract] = []
        if not isinstance(chain, pl.DataFrame):
            return records
        for row in chain.iter_rows(named=True):
            if {"strike", "expiry", "option_type", "mid"}.issubset(row):
                records.append(
                    _OptionContract(
                        strike=float(row["strike"]),
                        expiry=str(row["expiry"]),
                        option_type=str(row["option_type"]),
                        mid=float(row.get("mid", 0.0)),
                    )
                )
        return sorted(records, key=lambda c: (c.expiry, c.strike))

    def _stock_trade(self, suggestion: Suggestion) -> TradeIdea:
        return self._build_stock_trade(suggestion, direction="buy", strategy="long_stock", side="long")

    def _short_stock_trade(self, suggestion: Suggestion) -> TradeIdea:
        return self._build_stock_trade(suggestion, direction="sell", strategy="short_stock", side="short")

    def _build_stock_trade(self, suggestion: Suggestion, direction: str, strategy: str, side: str) -> TradeIdea:
        price = self.config.get("reference_price", 100.0)
        leg = TradeLeg(instrument_type="STOCK", direction=direction, qty=1)
        return TradeIdea(
            id=f"trade-{uuid4()}",
            symbol=suggestion.symbol,
            strategy_type=strategy,
            side=side,
            legs=[leg],
            cost_per_unit=price if side == "long" else 0.0,
            max_loss=price if side == "long" else 0.0,
            max_profit=None if side == "long" else price,
            breakeven_levels=[price],
            target_exit_price=None,
            stop_loss_price=None,
            recommended_units=self._recommended_units(price),
            confidence=suggestion.confidence,
            rationale=suggestion.reasoning,
            tags=[*suggestion.tags, strategy],
        )

    def _call_debit_spread(self, suggestion: Suggestion, contracts: Sequence[_OptionContract]) -> TradeIdea:
        calls = [c for c in contracts if c.is_call]
        if len(calls) < 2:
            return self._stock_trade(suggestion)
        lower = calls[0]
        upper = calls[min(1, len(calls) - 1)]
        cost = (lower.mid - upper.mid) * _CONTRACT_SIZE
        max_profit = ((upper.strike - lower.strike) * _CONTRACT_SIZE) - cost
        breakeven = lower.strike + cost / _CONTRACT_SIZE
        legs = [
            TradeLeg(instrument_type="C", direction="buy", qty=1, strike=lower.strike, expiry=lower.expiry),
            TradeLeg(instrument_type="C", direction="sell", qty=1, strike=upper.strike, expiry=upper.expiry),
        ]
        return self._build_option_trade(
            suggestion,
            strategy="call_debit_spread",
            side="long",
            cost=cost,
            max_loss=cost,
            max_profit=max_profit,
            breakevens=[breakeven],
            legs=legs,
        )

    def _put_debit_spread(self, suggestion: Suggestion, contracts: Sequence[_OptionContract]) -> TradeIdea:
        puts = [c for c in contracts if c.is_put]
        if len(puts) < 2:
            return self._short_stock_trade(suggestion)
        lower = puts[0]
        upper = puts[min(1, len(puts) - 1)]
        cost = (upper.mid - lower.mid) * _CONTRACT_SIZE
        max_profit = ((upper.strike - lower.strike) * _CONTRACT_SIZE) - cost
        breakeven = upper.strike - cost / _CONTRACT_SIZE
        legs = [
            TradeLeg(instrument_type="P", direction="buy", qty=1, strike=upper.strike, expiry=upper.expiry),
            TradeLeg(instrument_type="P", direction="sell", qty=1, strike=lower.strike, expiry=lower.expiry),
        ]
        return self._build_option_trade(
            suggestion,
            strategy="put_debit_spread",
            side="short",
            cost=cost,
            max_loss=cost,
            max_profit=max_profit,
            breakevens=[breakeven],
            legs=legs,
        )

    def _iron_condor(self, suggestion: Suggestion, contracts: Sequence[_OptionContract]) -> TradeIdea:
        calls = [c for c in contracts if c.is_call]
        puts = [c for c in contracts if c.is_put]
        if len(calls) < 2 or len(puts) < 2:
            return self._call_debit_spread(suggestion, contracts)
        call_lower, call_upper = calls[0], calls[min(1, len(calls) - 1)]
        put_lower, put_upper = puts[0], puts[min(1, len(puts) - 1)]
        credit = (call_upper.mid - call_lower.mid + put_upper.mid - put_lower.mid) * _CONTRACT_SIZE
        max_loss = ((call_upper.strike - call_lower.strike) * _CONTRACT_SIZE) - credit
        legs = [
            TradeLeg(instrument_type="C", direction="sell", qty=1, strike=call_upper.strike, expiry=call_upper.expiry),
            TradeLeg(instrument_type="C", direction="buy", qty=1, strike=call_lower.strike, expiry=call_lower.expiry),
            TradeLeg(instrument_type="P", direction="sell", qty=1, strike=put_lower.strike, expiry=put_lower.expiry),
            TradeLeg(instrument_type="P", direction="buy", qty=1, strike=put_upper.strike, expiry=put_upper.expiry),
        ]
        breakevens = [call_upper.strike + credit / _CONTRACT_SIZE, put_lower.strike - credit / _CONTRACT_SIZE]
        return self._build_option_trade(
            suggestion,
            strategy="iron_condor",
            side="neutral",
            cost=-credit,
            max_loss=max_loss,
            max_profit=credit,
            breakevens=breakevens,
            legs=legs,
        )

    def _calendar_spread(self, suggestion: Suggestion, contracts: Sequence[_OptionContract]) -> TradeIdea:
        if len(contracts) < 2:
            return self._stock_trade(suggestion)
        near = contracts[0]
        far = contracts[-1]
        cost = (far.mid - near.mid) * _CONTRACT_SIZE
        legs = [
            TradeLeg(
                instrument_type="C" if near.is_call else "P",
                direction="sell",
                qty=1,
                strike=near.strike,
                expiry=near.expiry,
            ),
            TradeLeg(
                instrument_type="C" if far.is_call else "P",
                direction="buy",
                qty=1,
                strike=far.strike,
                expiry=far.expiry,
            ),
        ]
        breakevens = [near.strike]
        return self._build_option_trade(
            suggestion,
            strategy="calendar_spread",
            side="neutral",
            cost=cost,
            max_loss=cost,
            max_profit=None,
            breakevens=breakevens,
            legs=legs,
        )

    def _build_option_trade(
        self,
        suggestion: Suggestion,
        strategy: str,
        side: str,
        cost: float,
        max_loss: float,
        max_profit: float | None,
        breakevens: Sequence[float],
        legs: Sequence[TradeLeg],
    ) -> TradeIdea:
        units = self._recommended_units(abs(cost) if cost else self.config.get("risk_per_unit", 500.0))
        return TradeIdea(
            id=f"trade-{uuid4()}",
            symbol=suggestion.symbol,
            strategy_type=strategy,
            side=side,
            legs=list(legs),
            cost_per_unit=cost,
            max_loss=max_loss,
            max_profit=max_profit,
            breakeven_levels=list(breakevens),
            target_exit_price=None,
            stop_loss_price=None,
            recommended_units=units,
            confidence=suggestion.confidence,
            rationale=suggestion.reasoning,
            tags=[*suggestion.tags, strategy],
        )

    def _recommended_units(self, cost: float) -> int:
        capital = self.config.get("max_capital_per_trade", 10000.0)
        if cost <= 0:
            return int(capital / max(self.config.get("risk_per_unit", 500.0), 1.0))
        return max(1, int(capital / cost))
