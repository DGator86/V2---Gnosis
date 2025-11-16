# agents/composer/resolution/conflict_resolver.py

from ..schemas import EngineDirective


def summarize_conflicts(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> str:
    """
    Return a short human-readable description of inter-engine conflicts.

    This is appended into the rationale string.
    """
    msgs = []

    if hedge.direction * liquidity.direction < 0:
        msgs.append("Hedge and Liquidity disagree on direction.")
    if hedge.direction * sentiment.direction < 0:
        msgs.append("Hedge and Sentiment disagree on direction.")
    if liquidity.direction * sentiment.direction < 0:
        msgs.append("Liquidity and Sentiment disagree on direction.")

    if not msgs:
        return "Engines are broadly aligned on direction."

    return " | ".join(msgs)
