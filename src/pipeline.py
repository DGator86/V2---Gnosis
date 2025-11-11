"""
Main pipeline orchestrator.
Runs the complete pipeline: engines -> agents -> trade ideas.
"""

from typing import List
from datetime import datetime

from .schemas.bars import Bar
from .schemas.options import OptionSnapshot
from .schemas.features import EngineSnapshot
from .schemas.trades import TradeIdea

from .engines import (
    compute_hedge_fields,
    compute_liquidity_fields,
    compute_sentiment_fields,
)

from .agents import (
    analyze_hedge,
    analyze_liquidity,
    analyze_sentiment,
    compose_thesis,
)

from .trade import construct_trade_ideas

from .utils.logging import log_pipeline_step, log_error


def run_pipeline(
    symbol: str,
    bars: List[Bar],
    options: List[OptionSnapshot],
    news_scores: List[float] = None,
    now: datetime = None
) -> List[TradeIdea]:
    """
    Run the complete pipeline for a single symbol.
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    bars : list[Bar]
        Recent price bars (at least 60-120 bars recommended)
    options : list[OptionSnapshot]
        Current options chain snapshot
    news_scores : list[float], optional
        News sentiment scores (-1..1)
    now : datetime, optional
        Current timestamp (defaults to last bar timestamp)
        
    Returns
    -------
    list[TradeIdea]
        Generated trade ideas
    """
    if now is None:
        now = bars[-1].ts if bars else datetime.now()
    
    try:
        # Step 1: Compute engine fields
        log_pipeline_step("ENGINE", symbol, "Computing hedge fields...")
        hedge_fields = compute_hedge_fields(symbol, options, bars)
        
        log_pipeline_step("ENGINE", symbol, "Computing liquidity fields...")
        liquidity_fields = compute_liquidity_fields(symbol, bars, dark_pool_df=None)
        
        log_pipeline_step("ENGINE", symbol, "Computing sentiment fields...")
        sentiment_fields = compute_sentiment_fields(symbol, bars, news_scores)
        
        # Step 2: Create engine snapshot
        snapshot = EngineSnapshot(
            ts=now,
            symbol=symbol,
            hedge=hedge_fields,
            liquidity=liquidity_fields,
            sentiment=sentiment_fields
        )
        
        # Step 3: Run agents
        log_pipeline_step("AGENT", symbol, "Analyzing hedge pressure...")
        hedge_finding = analyze_hedge(snapshot)
        
        log_pipeline_step("AGENT", symbol, "Analyzing liquidity...")
        liquidity_finding = analyze_liquidity(snapshot)
        
        log_pipeline_step("AGENT", symbol, "Analyzing sentiment...")
        sentiment_finding = analyze_sentiment(snapshot)
        
        findings = [hedge_finding, liquidity_finding, sentiment_finding]
        
        # Step 4: Compose thesis
        log_pipeline_step("COMPOSER", symbol, "Composing thesis...")
        thesis = compose_thesis(snapshot, findings)
        
        log_pipeline_step("COMPOSER", symbol, 
                         f"Thesis: {thesis.direction} with {thesis.conviction:.2f} conviction")
        
        # Step 5: Generate trade ideas
        log_pipeline_step("TRADE", symbol, "Constructing trade ideas...")
        trade_ideas = construct_trade_ideas(thesis, options, bars)
        
        log_pipeline_step("TRADE", symbol, f"Generated {len(trade_ideas)} trade idea(s)")
        
        return trade_ideas
    
    except Exception as e:
        log_error(e, f"Pipeline failed for {symbol}")
        return []


def run_pipeline_batch(
    symbols: List[str],
    bars_by_symbol: dict,
    options_by_symbol: dict,
    news_scores_by_symbol: dict = None
) -> dict:
    """
    Run pipeline for multiple symbols.
    
    Parameters
    ----------
    symbols : list[str]
        List of symbols
    bars_by_symbol : dict
        Dictionary mapping symbol -> list[Bar]
    options_by_symbol : dict
        Dictionary mapping symbol -> list[OptionSnapshot]
    news_scores_by_symbol : dict, optional
        Dictionary mapping symbol -> list[float]
        
    Returns
    -------
    dict
        Dictionary mapping symbol -> list[TradeIdea]
    """
    results = {}
    
    for symbol in symbols:
        bars = bars_by_symbol.get(symbol, [])
        options = options_by_symbol.get(symbol, [])
        news_scores = news_scores_by_symbol.get(symbol, None) if news_scores_by_symbol else None
        
        trade_ideas = run_pipeline(symbol, bars, options, news_scores)
        results[symbol] = trade_ideas
    
    return results
