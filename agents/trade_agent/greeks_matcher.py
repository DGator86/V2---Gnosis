# agents/trade_agent/greeks_matcher.py

from __future__ import annotations

from .schemas import ComposerTradeContext, TradeIdea


def annotate_with_greeks_context(
    idea: TradeIdea,
    ctx: ComposerTradeContext,
) -> TradeIdea:
    """
    Enriches the idea.notes with context from gamma/vanna/charm/elasticity.
    Does not change economics – strictly interpretive.
    """
    notes = []

    if ctx.gamma_exposure > 0:
        notes.append("Positive dealer gamma: mean-reversion / pinned behavior more likely.")
    elif ctx.gamma_exposure < 0:
        notes.append("Negative dealer gamma: larger directional swings more likely.")

    if ctx.vanna_exposure > 0:
        notes.append("Positive vanna: rising spot likely to reduce implied vol.")
    elif ctx.vanna_exposure < 0:
        notes.append("Negative vanna: rising spot may increase implied vol.")

    if ctx.charm_exposure < 0:
        notes.append("Negative charm: delta likely to decay intraday (watch intraday drift).")

    if ctx.elastic_energy > 0:
        notes.append(
            f"Elastic energy={ctx.elastic_energy:.2f}: higher values imply more 'cost' "
            "to push price through key levels."
        )

    if ctx.liquidity_score < 0.4:
        notes.append("Low liquidity: expect wider spreads and slippage.")
    elif ctx.liquidity_score > 0.8:
        notes.append("High liquidity: execution quality likely good.")

    combined = (idea.notes or "") + (" " if idea.notes else "") + " ".join(notes)
    idea.notes = combined.strip()

    return idea
