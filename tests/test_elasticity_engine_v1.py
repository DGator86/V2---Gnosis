from __future__ import annotations

from datetime import datetime

from engines.elasticity.elasticity_engine_v1 import ElasticityEngineV1
from engines.inputs.stub_adapters import StaticMarketDataAdapter


def test_elasticity_engine_outputs_energy() -> None:
    engine = ElasticityEngineV1(StaticMarketDataAdapter(), {"baseline_move_cost": 1.0})
    output = engine.run("SPY", datetime.utcnow())
    assert output.kind == "elasticity"
    assert "energy_to_move_1pct_up" in output.features
    assert output.features["elasticity_up"] > 0
