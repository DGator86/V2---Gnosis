from __future__ import annotations

from datetime import datetime

from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.inputs.stub_adapters import StaticOptionsAdapter


def test_hedge_engine_outputs_features() -> None:
    engine = HedgeEngineV3(StaticOptionsAdapter(), {})
    output = engine.run("SPY", datetime.utcnow())
    assert output.kind == "hedge"
    assert "gamma_pressure" in output.features
    assert "dealer_gamma_sign" in output.features
    assert "potential_shape" in output.metadata
