from datetime import datetime

from schemas import EngineOutput
from engines.standardization.standardizer_engine import StandardizerEngine


def _engine_output(kind: str, features: dict, confidence: float = 0.8) -> EngineOutput:
    return EngineOutput(
        kind=kind,
        features=features,
        metadata={"source": "unit-test"},
        timestamp=datetime.now().timestamp(),
        confidence=confidence,
    )


def test_gamma_pressure_triggers_gamma_squeeze_regime():
    engine = StandardizerEngine()
    snapshot = engine.standardize(
        "SPY",
        hedge=_engine_output("hedge", {"gamma_pressure": 12.0, "vanna_pressure": 0.1, "charm_pressure": 0.05}),
        volume=_engine_output(
            "volume",
            {"flow_volume": 2e6, "vwap": 449.5, "trade_imbalance": 0.1},
        ),
        sentiment=_engine_output("sentiment", {"sentiment_score": 0.1}),
    )

    assert snapshot.regime == "gamma_squeeze"


def test_trending_regime_requires_alignment():
    engine = StandardizerEngine()
    snapshot = engine.standardize(
        "SPY",
        hedge=_engine_output("hedge", {"gamma_pressure": 1.0, "vanna_pressure": 0.1, "charm_pressure": 0.05}),
        volume=_engine_output(
            "volume",
            {"flow_volume": 5e6, "vwap": 451.0, "trade_imbalance": 0.5},
        ),
        sentiment=_engine_output("sentiment", {"sentiment_score": 0.6}),
    )

    assert snapshot.regime == "trending"


def test_validation_flags_missing_features_and_low_confidence():
    engine = StandardizerEngine()
    snapshot = engine.standardize(
        "SPY",
        hedge=_engine_output("hedge", {"gamma_pressure": 0.0, "vanna_pressure": 0.1}),
        volume=_engine_output(
            "volume",
            {"flow_volume": 5e5, "vwap": 451.0},
            confidence=0.2,
        ),
        sentiment=_engine_output("sentiment", {"sentiment_score": 0.1}, confidence=0.1),
    )

    report = engine.validate_snapshot(snapshot)

    assert not report["valid"]
    assert any("Missing hedge feature" in issue for issue in report["issues"])
    assert any("Low volume confidence" in issue for issue in report["issues"])
    assert any("Low sentiment confidence" in issue for issue in report["issues"])
