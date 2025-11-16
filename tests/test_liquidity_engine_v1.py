from __future__ import annotations

from datetime import datetime

from engines.inputs.stub_adapters import StaticMarketDataAdapter
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1


def test_liquidity_engine_metrics() -> None:
    engine = LiquidityEngineV1(StaticMarketDataAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    assert output.kind == "liquidity"
    assert "amihud_illiquidity" in output.features
    assert "liquidity_score" in output.features
    assert "volume_strength" in output.features
    assert "polr_direction" in output.features
