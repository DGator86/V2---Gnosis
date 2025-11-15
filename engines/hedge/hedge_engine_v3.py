from __future__ import annotations

"""Hedge Engine v3.0 implementation skeleton."""

from datetime import datetime
from typing import Any, Dict

import polars as pl

from engines.base import Engine
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from schemas.core_schemas import EngineOutput


class HedgeEngineV3(Engine):
    """Dealer hedge pressure engine producing normalized features."""

    def __init__(self, adapter: OptionsChainAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        chain = self.adapter.fetch_chain(symbol, now)
        if chain.is_empty():
            return EngineOutput(
                kind="hedge",
                symbol=symbol,
                timestamp=now,
                features={},
                confidence=0.0,
                regime="illiquid_gamma",
                metadata={"degraded": "no_data"},
            )

        features = self._compute_features(chain)
        regime = self._determine_regime(features)
        confidence = self._compute_confidence(chain, features)

        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=confidence,
            regime=regime,
        )

    def _compute_features(self, chain: pl.DataFrame) -> Dict[str, float]:
        required_cols = {"gamma", "vanna", "charm", "open_interest", "underlying_price"}
        if not required_cols.issubset(set(chain.columns)):
            return {}

        gamma_pressure = (chain["gamma"] * chain["open_interest"] * chain["underlying_price"]).sum()
        vanna_pressure = (chain["vanna"] * chain["open_interest"]).sum()
        charm_pressure = (chain["charm"] * chain["open_interest"]).sum()

        features: Dict[str, float] = {
            "gamma_pressure": float(gamma_pressure),
            "vanna_pressure": float(vanna_pressure),
            "charm_pressure": float(charm_pressure),
        }

        features["gamma_sign"] = 1.0 if gamma_pressure >= 0 else -1.0
        features["vanna_sign"] = 1.0 if vanna_pressure >= 0 else -1.0
        features["hedge_regime_energy"] = float(abs(gamma_pressure) + abs(vanna_pressure))
        features["vix_friction_factor"] = 0.0

        return features

    def _determine_regime(self, features: Dict[str, float]) -> str:
        if not features:
            return "illiquid_gamma"

        gamma_pressure = features.get("gamma_pressure", 0.0)
        vanna_pressure = features.get("vanna_pressure", 0.0)

        if abs(gamma_pressure) > self.config.get("gamma_squeeze_threshold", 1e6):
            return "gamma_squeeze"
        if abs(vanna_pressure) > self.config.get("vanna_flow_threshold", 1e6):
            return "vanna_flow"
        if abs(gamma_pressure) < self.config.get("pin_threshold", 1e5):
            return "pin"
        return "neutral"

    def _compute_confidence(self, chain: pl.DataFrame, features: Dict[str, float]) -> float:
        if not features:
            return 0.0
        coverage = len(chain)
        max_coverage = self.config.get("max_chain_size", 5000)
        return float(min(1.0, coverage / max_coverage))
