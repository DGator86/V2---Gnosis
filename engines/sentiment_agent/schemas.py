# engines/sentiment_agent/schemas.py

from pydantic import BaseModel, Field


class SentimentAgentInput(BaseModel):
    """
    Canonical input to the Sentiment Agent.

    All values are pre-computed by the Sentiment Engine. The agent only
    interprets them into a normalized sentiment signal.
    """

    wyckoff_phase: str = Field(
        ...,
        description=(
            "Wyckoff phase label inferred by the Sentiment Engine, "
            "e.g. 'A', 'B', 'C', 'D', 'E'."
        ),
    )

    oscillator_score: float = Field(
        ...,
        description=(
            "Composite oscillator score (e.g., fused RSI/CCI/Stoch), "
            "normalized roughly to [-1, 1] where +1 = extremely overbought, "
            "-1 = extremely oversold."
        ),
    )

    volatility_regime: str = Field(
        ...,
        description=(
            "Volatility regime inferred by Sentiment Engine, "
            "e.g. 'compression', 'expansion', 'normal'."
        ),
    )

    vol_compression_score: float = Field(
        ...,
        description=(
            "Score in [0,1+] for volatility compression (squeeze). "
            "Higher implies more compressed / coiled state."
        ),
    )

    vol_expansion_score: float = Field(
        ...,
        description=(
            "Score in [0,1+] for volatility expansion. Higher implies "
            "active expansion / volatility shock sentiment."
        ),
    )

    breadth_score: float = Field(
        ...,
        description=(
            "Breadth indicator score, approximately [-1, 1], where "
            "+1 = strongly positive breadth (many names up), "
            "-1 = strongly negative breadth."
        ),
    )

    flow_bias: float = Field(
        ...,
        description=(
            "Signed flow bias score, e.g. options/ETF/futures/net flow "
            "bias; positive = bullish tilt, negative = bearish."
        ),
    )

    sentiment_energy: float = Field(
        ...,
        description=(
            "Sentiment 'energy' score inferred by the engine, capturing "
            "how intense or charged the current sentiment regime is."
        ),
    )

    regime: str = Field(
        ...,
        description=(
            "High-level sentiment regime label, e.g. 'accumulation', "
            "'distribution', 'markup', 'markdown', 'sideways', 'transition'."
        ),
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Engine-level confidence in these sentiment metrics.",
    )

    realized_sentiment_divergence: float = Field(
        ...,
        description=(
            "Score for divergence between sentiment signal and realized "
            "price action, e.g. [-1, 1]. Negative = sentiment was wrong."
        ),
    )


class SentimentAgentOutput(BaseModel):
    """
    Canonical output of Sentiment Agent, consumed by the Composer.
    """

    direction: str = Field(
        ...,
        description=(
            "Qualitative sentiment classification, e.g. 'bullish', "
            "'bearish', 'distribution top', 'accumulation bottom', "
            "'range-bound', 'chaotic'."
        ),
    )
    strength: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0–1 sentiment strength / intensity score.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0–1 confidence in this sentiment classification.",
    )
    regime: str = Field(
        ...,
        description="Echoed sentiment regime label for Composer context.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable annotations about sentiment conditions.",
    )
