from __future__ import annotations

"""Liquidity Agent v1.0 implementation skeleton."""

from typing import Any, Dict
from uuid import uuid4

from agents.base import PrimaryAgent
from schemas.core_schemas import StandardSnapshot, Suggestion


class LiquidityAgentV1(PrimaryAgent):
    """Interpret liquidity features to determine market stance."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        liquidity = snapshot.liquidity
        action = "flat"
        confidence = 0.4
        reasoning = "Normal liquidity"
        tags = []

        amihud = liquidity.get("amihud_illiquidity", 0.0)
        ofi = liquidity.get("ofi", 0.0)

        if amihud > self.config.get("thin_threshold", 0.001):
            action = "spread"
            confidence = 0.6
            tags.append("thin_liquidity")
            reasoning = "Thin liquidity suggests spreads"
        if ofi > self.config.get("one_sided_threshold", 0.6):
            action = "long"
            confidence = 0.7
            tags.append("one_sided_flow")
            reasoning = "Strong buy-side flow"
        elif ofi < -self.config.get("one_sided_threshold", 0.6):
            action = "short"
            confidence = 0.7
            tags.append("one_sided_flow")
            reasoning = "Strong sell-side flow"

        return Suggestion(
            id=f"liq-{uuid4()}",
            layer="primary_liquidity",
            symbol=snapshot.symbol,
            action=action,
            confidence=confidence,
            forecast={},
            reasoning=reasoning,
            tags=tags,
        )
