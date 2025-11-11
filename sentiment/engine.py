"""Main sentiment engine orchestrator."""

from __future__ import annotations
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional, Set
import math
import time
import numpy as np
import logging
from pydantic import TypeAdapter

from .schemas import NewsDoc, ScoredNews, SentimentSpan, TickerSentimentSnapshot, SentimentLabel
from .config import (
    SOURCE_WEIGHTS, DECAY_TAU, SURPRISE_LOOKBACK, CONTRARIAN_THRESH as CT,
    MODEL_CONFIG, NOVELTY_CONFIG, ROLLING_STATS_CONFIG
)
from .nlp.finbert import FinBERT
from .nlp.entity_map import SymbolLexicon
from .dedupe.simhash import simhash_64, NoveltyIndex
from .features.rollup import RollingStats
from .references.reference_builder import ReferenceBuilder

logger = logging.getLogger(__name__)

# Type adapter for serialization
TA_ScoredNews = TypeAdapter(ScoredNews)


def _now_ts() -> float:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).timestamp()


def _source_weight(source: str, is_pr: bool) -> float:
    """Get weight for a news source.
    
    Args:
        source: Source name
        is_pr: Whether it's a press release
        
    Returns:
        Weight value
    """
    if is_pr:
        return SOURCE_WEIGHTS.get("pr", 0.5)
    return SOURCE_WEIGHTS.get(source.lower(), SOURCE_WEIGHTS.get("unknown", 0.7))


class SentimentEngine:
    """Production-ready sentiment analysis engine with FinBERT.
    
    Features:
    - FinBERT-based financial sentiment analysis
    - Entity extraction and per-ticker scoring
    - Near-duplicate detection with SimHash
    - Time-decayed weighted statistics
    - Multiple feature computations (mean, std, momentum, entropy, etc.)
    - Dual correlation tracking (market & sector)
    - Convenience flags for trading decisions
    """
    
    def __init__(
        self,
        symbol_aliases: Optional[Dict[str, Set[str]]] = None,
        decay_windows: Optional[List[str]] = None,
        model_config: Optional[dict] = None,
        enable_caching: bool = True
    ):
        """Initialize sentiment engine.
        
        Args:
            symbol_aliases: Ticker to aliases mapping
            decay_windows: Time windows for analysis
            model_config: Model configuration overrides
            enable_caching: Whether to enable result caching
        """
        # Model configuration
        config = {**MODEL_CONFIG, **(model_config or {})}
        
        # Initialize components
        logger.info("Initializing SentimentEngine components...")
        
        # NLP model
        self.model = FinBERT(
            model_id=config["model_id"],
            cache_dir=config.get("cache_dir"),
            batch_size=config.get("batch_size", 16)
        )
        
        # Entity extractor
        self.lexicon = SymbolLexicon(symbol_aliases)
        
        # Time windows
        self.decay_windows = decay_windows or ["5m", "30m", "1h", "1d"]
        
        # Per-ticker rolling statistics
        self.stats: Dict[str, Dict[str, RollingStats]] = defaultdict(
            lambda: {
                w: RollingStats(maxlen=ROLLING_STATS_CONFIG["max_buffer"])
                for w in self.decay_windows
            }
        )
        
        # Novelty detection
        self.novelty = NoveltyIndex(
            threshold_bits=NOVELTY_CONFIG["threshold_bits"],
            max_size=NOVELTY_CONFIG["cache_size"]
        )
        
        # Historical baselines for surprise calculation
        self.baselines: Dict[Tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=SURPRISE_LOOKBACK)
        )
        
        # Mean series for correlations
        self.mean_series: Dict[Tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=600)
        )
        
        # Market-wide reference (average of all tickers)
        self.market_ref: Dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=600)
        )
        
        # Specific reference series
        self.ref_series: Dict[Tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=600)
        )
        self.ticker_ref: Dict[str, str] = {}  # ticker -> reference name
        
        # Optional reference builder (for ETF-based refs)
        self._ref_builder: Optional[ReferenceBuilder] = None
        
        # Correlation settings
        self._corr_min_points = ROLLING_STATS_CONFIG["corr_min_points"]
        
        # Caching
        self.enable_caching = enable_caching
        self._cache = {} if enable_caching else None
        
        # Statistics
        self.stats_counter = {
            "docs_processed": 0,
            "spans_created": 0,
            "duplicates_found": 0,
        }
        
        logger.info("SentimentEngine initialized successfully")
    
    # ============= Reference Management =============
    
    def attach_reference_builder(self, rb: ReferenceBuilder):
        """Attach a reference builder for ETF-based correlations.
        
        Args:
            rb: ReferenceBuilder instance
        """
        self._ref_builder = rb
        logger.info("Reference builder attached")
    
    def set_ticker_reference(self, ticker: str, ref_name: str):
        """Map a ticker to a specific reference series.
        
        Args:
            ticker: Ticker symbol
            ref_name: Reference name (e.g., "XLK" for tech sector)
        """
        self.ticker_ref[ticker] = ref_name
        logger.debug(f"Mapped {ticker} to reference {ref_name}")
    
    def push_reference_point(
        self,
        ref_name: str,
        window: str,
        value: float
    ):
        """Manually push a reference series value.
        
        Args:
            ref_name: Reference name
            window: Time window
            value: Value to push
        """
        self.ref_series[(ref_name, window)].append(float(value))
    
    # ============= Core Processing =============
    
    def score_docs(self, docs: List[NewsDoc]) -> List[ScoredNews]:
        """Score news documents for sentiment.
        
        Args:
            docs: List of news documents
            
        Returns:
            List of scored news with sentiment spans
        """
        if not docs:
            return []
        
        logger.info(f"Scoring {len(docs)} documents")
        start_time = time.time()
        
        results: List[ScoredNews] = []
        
        for doc in docs:
            # Skip non-English
            if doc.lang != "en":
                logger.debug(f"Skipping non-English doc: {doc.id}")
                continue
            
            # Extract tickers
            if not doc.tickers:
                text_for_extraction = doc.title + " " + (doc.body or "")
                doc.tickers = self.lexicon.extract(text_for_extraction)
            
            if not doc.tickers:
                logger.debug(f"No tickers found in doc: {doc.id}")
                continue
            
            # Prepare text for sentiment analysis
            text = doc.title if doc.body is None else (doc.title + " \n " + doc.body)
            
            # Get sentiment scores
            if self.enable_caching and text in self._cache:
                probs = self._cache[text]
            else:
                probs = self.model.score(text)
                if self.enable_caching:
                    self._cache[text] = probs
            
            # Determine label
            if probs["pos"] > max(probs["neu"], probs["neg"]):
                label = SentimentLabel.POSITIVE
            elif probs["neg"] > max(probs["neu"], probs["pos"]):
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL
            
            # Create spans for each ticker
            spans: List[SentimentSpan] = []
            for ticker in doc.tickers:
                span = SentimentSpan(
                    ticker=ticker,
                    label=label,
                    score=probs["signed"],
                    probs={"pos": probs["pos"], "neu": probs["neu"], "neg": probs["neg"]},
                    confidence=max(probs["pos"], probs["neg"], probs["neu"])
                )
                spans.append(span)
                self.stats_counter["spans_created"] += 1
            
            # Compute novelty hash
            hash_text = (doc.title or "") + "||" + (doc.body or "") + "||" + (doc.source or "")
            hash_value = simhash_64(hash_text)
            is_novel = self.novelty.mark_and_is_novel(hash_value)
            
            if not is_novel:
                self.stats_counter["duplicates_found"] += 1
            
            doc.novelty_hash = hex(hash_value)
            
            # Create scored news
            processing_time = (time.time() - start_time) * 1000
            scored = ScoredNews(
                doc=doc,
                spans=spans,
                processing_time_ms=processing_time
            )
            results.append(scored)
            self.stats_counter["docs_processed"] += 1
        
        logger.info(
            f"Scored {len(results)} docs with {self.stats_counter['spans_created']} spans "
            f"in {time.time() - start_time:.2f}s"
        )
        
        return results
    
    def ingest(self, scored_docs: List[ScoredNews]):
        """Ingest scored documents into rolling statistics.
        
        Args:
            scored_docs: List of scored news documents
        """
        if not scored_docs:
            return
        
        logger.info(f"Ingesting {len(scored_docs)} scored documents")
        now_ts = _now_ts()
        
        for scored in scored_docs:
            doc = scored.doc
            if not scored.spans:
                continue
            
            # Calculate weights
            src_weight = _source_weight(doc.source, doc.is_pr)
            doc_ts = doc.ts_utc.timestamp()
            
            # Check if novel (already computed during scoring)
            is_unique = doc.novelty_hash is not None
            
            # Process each span
            for span in scored.spans:
                ticker = span.ticker
                
                # Update stats for each window
                for window in self.decay_windows:
                    # Calculate time-decayed weight
                    recency_weight = self._recency_weight(now_ts, doc_ts, window)
                    
                    # Additional weight factors
                    length_weight = 1.0 if doc.body else 0.9
                    pr_weight = 0.5 if doc.is_pr else 1.0
                    
                    # Combined weight
                    total_weight = src_weight * recency_weight * length_weight * pr_weight
                    
                    # Add to rolling stats
                    self.stats[ticker][window].add(
                        ts=doc_ts,
                        score=span.score,
                        weight=total_weight,
                        is_unique=is_unique,
                        source_weight=src_weight
                    )
    
    # ============= Snapshot Generation =============
    
    def snapshot(self, ticker: str, window: str) -> TickerSentimentSnapshot:
        """Generate sentiment snapshot for a ticker at a specific window.
        
        Args:
            ticker: Ticker symbol
            window: Time window
            
        Returns:
            Complete sentiment snapshot
        """
        # Get rolling stats
        rs = self.stats[ticker][window]
        
        # Compute basic statistics
        mean, std, skew = rs.weighted_mean_std_skew()
        
        # Compute advanced metrics
        disagreement = rs.disagreement()
        momentum = rs.momentum(span=ROLLING_STATS_CONFIG["ema_span"])
        novelty = rs.novelty_ratio()
        src_mean = rs.source_weighted_mean()
        entropy = rs.entropy()
        sharpe = rs.sharpe_like(drift_span=ROLLING_STATS_CONFIG["ema_span"])
        
        # Update mean series
        key = (ticker, window)
        self.mean_series[key].append(mean)
        
        # Update market reference
        self._update_market_ref(window)
        
        # Calculate surprise
        surprise = self._calculate_surprise(ticker, window, mean)
        
        # Calculate correlations
        corr_market = self._calculate_correlation(
            self.mean_series[key],
            self.market_ref[window]
        )
        
        # Sector/reference correlation
        ref_name = self.ticker_ref.get(ticker)
        corr_ref = None
        if ref_name is not None:
            corr_ref = self._calculate_ref_correlation(ticker, window, ref_name)
        
        # Determine convenience flags
        flags = self._determine_flags(
            corr_market, corr_ref, momentum, sharpe, surprise
        )
        
        # Build snapshot
        return TickerSentimentSnapshot(
            ticker=ticker,
            window=window,
            n_docs=len(rs.buf),
            mean=mean,
            std=std,
            skew=skew,
            disagreement=disagreement,
            momentum=momentum,
            surprise=surprise,
            novelty=novelty,
            source_weighted_mean=src_mean,
            entropy=entropy,
            sharpe_like=sharpe,
            corr_to_market=corr_market,
            corr_to_ref=corr_ref,
            ref_name=ref_name,
            is_contrarian_market=flags["is_contrarian_market"],
            is_contrarian_sector=flags["is_contrarian_sector"],
            is_strong_contrarian=flags["is_strong_contrarian"],
            is_trending_sentiment=flags["is_trending_sentiment"],
            is_information_shock=flags["is_information_shock"],
            updated_at=datetime.now(timezone.utc)
        )
    
    def snapshots_for(self, ticker: str) -> Dict[str, TickerSentimentSnapshot]:
        """Get all snapshots for a ticker across all windows.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary mapping window to snapshot
        """
        return {w: self.snapshot(ticker, w) for w in self.decay_windows}
    
    # ============= Helper Methods =============
    
    def _recency_weight(self, now_ts: float, doc_ts: float, window: str) -> float:
        """Calculate time decay weight."""
        tau = DECAY_TAU[window]
        dt = max(0.0, now_ts - doc_ts)
        return math.exp(-dt / tau)
    
    def _update_market_ref(self, window: str):
        """Update market-wide reference series."""
        # Collect latest means from all tickers
        latest_means = []
        for (t, w), series in self.mean_series.items():
            if w == window and series:
                latest_means.append(series[-1])
        
        # Add average to market reference
        if latest_means:
            market_mean = float(np.mean(latest_means))
            self.market_ref[window].append(market_mean)
    
    def _calculate_surprise(
        self,
        ticker: str,
        window: str,
        current_mean: float
    ) -> float:
        """Calculate surprise metric."""
        key = (ticker, window)
        baseline = self.baselines[key]
        
        # Update baseline
        baseline.append(current_mean)
        
        # Need enough history
        if len(baseline) < 2:
            return 0.0
        
        # Calculate z-score
        hist_mean = np.mean(baseline)
        hist_std = np.std(baseline)
        
        if hist_std < 1e-9:
            return 0.0
        
        return float((current_mean - hist_mean) / hist_std)
    
    def _calculate_correlation(
        self,
        series_a: deque[float],
        series_b: deque[float]
    ) -> Optional[float]:
        """Calculate correlation between two series."""
        if not series_a or not series_b:
            return None
        
        n = min(len(series_a), len(series_b))
        if n < self._corr_min_points:
            return None
        
        a = np.array(list(series_a)[-n:], dtype=float)
        b = np.array(list(series_b)[-n:], dtype=float)
        
        if a.std() < 1e-9 or b.std() < 1e-9:
            return None
        
        return float(np.corrcoef(a, b)[0, 1])
    
    def _calculate_ref_correlation(
        self,
        ticker: str,
        window: str,
        ref_name: str
    ) -> Optional[float]:
        """Calculate correlation to reference series."""
        ticker_series = self.mean_series[(ticker, window)]
        
        # Try reference builder first
        if self._ref_builder is not None:
            ref_series = self._ref_builder.series(ref_name, window)
            return self._calculate_correlation(ticker_series, ref_series)
        
        # Fall back to manual reference series
        ref_series = self.ref_series[(ref_name, window)]
        return self._calculate_correlation(ticker_series, ref_series)
    
    def _determine_flags(
        self,
        corr_market: Optional[float],
        corr_ref: Optional[float],
        momentum: float,
        sharpe: float,
        surprise: float
    ) -> dict:
        """Determine convenience flags for trading decisions."""
        # Contrarian flags
        is_cm = (corr_market is not None) and (corr_market <= CT["market"])
        is_cs = (corr_ref is not None) and (corr_ref <= CT["sector"])
        
        # Trend flag
        is_trend = (
            abs(momentum) >= CT["trend_momentum"] and
            sharpe >= CT["trend_sharpe"]
        )
        
        # Shock flag
        is_shock = surprise >= CT["shock_surprise"]
        
        # Strong contrarian (both market and sector contrarian + trending + shock)
        is_strong = (
            (is_cm or False) and
            (is_cs or False) and
            is_trend and
            is_shock
        )
        
        # Handle None values
        strong_contrarian = (
            is_strong if (corr_market is not None and corr_ref is not None)
            else None
        )
        
        return {
            "is_contrarian_market": is_cm if corr_market is not None else None,
            "is_contrarian_sector": is_cs if corr_ref is not None else None,
            "is_strong_contrarian": strong_contrarian,
            "is_trending_sentiment": is_trend,
            "is_information_shock": is_shock,
        }
    
    # ============= Utility Methods =============
    
    def get_statistics(self) -> dict:
        """Get engine statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self.stats_counter,
            "novelty_rate": self.novelty.get_novelty_rate(),
            "cached_items": len(self._cache) if self._cache else 0,
            "tracked_tickers": len(self.stats),
        }
    
    def clear_cache(self):
        """Clear sentiment score cache."""
        if self._cache:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def reset_statistics(self):
        """Reset engine statistics."""
        self.stats_counter = {
            "docs_processed": 0,
            "spans_created": 0,
            "duplicates_found": 0,
        }
        logger.info("Statistics reset")