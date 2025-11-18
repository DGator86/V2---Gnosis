"""
Opportunity Scanner - Identifies top trading opportunities across multiple symbols.

Scans a universe of stocks and ranks them based on:
1. DHPE energy states (high asymmetry = directional opportunities)
2. Liquidity quality (high liquidity = tradeable)
3. Volatility regime (expansion = opportunities, compression = range-bound)
4. Sentiment strength (strong directional bias)
5. Options activity (high OI/volume = liquid options)

Returns top N symbols ranked by opportunity score.
"""

from __future__ import annotations

import polars as pl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class OpportunityScore:
    """Score for a single symbol's trading opportunity."""
    symbol: str
    score: float
    rank: int
    
    # Component scores (0-1 scale)
    energy_score: float
    liquidity_score: float
    volatility_score: float
    sentiment_score: float
    options_score: float
    
    # Key metrics
    energy_asymmetry: float
    movement_energy: float
    liquidity_quality: float
    iv_rank: Optional[float]
    option_volume: Optional[int]
    
    # Directional bias
    direction: str  # 'bullish', 'bearish', 'neutral'
    confidence: float
    
    # Reasoning
    opportunity_type: str  # 'directional', 'volatility', 'range_bound', 'gamma_squeeze'
    reasoning: str
    
    timestamp: datetime


@dataclass
class ScanResult:
    """Complete scan result with ranked opportunities."""
    opportunities: List[OpportunityScore]
    scan_timestamp: datetime
    symbols_scanned: int
    universe: List[str]
    scan_duration_seconds: float


class OpportunityScanner:
    """
    Scans multiple symbols and ranks them by trading opportunity quality.
    
    Uses DHPE physics to identify:
    - High energy asymmetry (directional moves)
    - Liquidity conditions (easy to trade)
    - Volatility expansion (breakout potential)
    - Strong sentiment (conviction)
    - Active options (liquid derivatives)
    """
    
    def __init__(
        self,
        hedge_engine,
        liquidity_engine,
        sentiment_engine,
        elasticity_engine,
        options_adapter,
        market_adapter,
    ):
        """
        Initialize scanner with engine dependencies.
        
        Args:
            hedge_engine: HedgeEngineV3 for options flow analysis
            liquidity_engine: LiquidityEngineV1 for orderflow
            sentiment_engine: SentimentEngineV1 for sentiment
            elasticity_engine: ElasticityEngineV1 for price elasticity
            options_adapter: For fetching options chains
            market_adapter: For fetching market data
        """
        self.hedge_engine = hedge_engine
        self.liquidity_engine = liquidity_engine
        self.sentiment_engine = sentiment_engine
        self.elasticity_engine = elasticity_engine
        self.options_adapter = options_adapter
        self.market_adapter = market_adapter
    
    def scan(
        self,
        universe: List[str],
        top_n: int = 25,
        min_price: float = 10.0,
        max_price: float = 1000.0,
        min_volume: int = 1_000_000,
    ) -> ScanResult:
        """
        Scan universe of symbols and return top N opportunities.
        
        Args:
            universe: List of symbols to scan
            top_n: Number of top opportunities to return
            min_price: Minimum stock price (avoid penny stocks)
            max_price: Maximum stock price (avoid expensive stocks)
            min_volume: Minimum daily volume (liquidity filter)
        
        Returns:
            ScanResult with ranked opportunities
        """
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting opportunity scan of {len(universe)} symbols")
        
        opportunities = []
        
        for symbol in universe:
            try:
                # Quick pre-filter: price and volume
                if not self._passes_prefilter(symbol, min_price, max_price, min_volume):
                    continue
                
                # Calculate opportunity score
                opp_score = self._score_symbol(symbol)
                
                if opp_score:
                    opportunities.append(opp_score)
                    logger.debug(f"{symbol}: score={opp_score.score:.3f}, type={opp_score.opportunity_type}")
                
            except Exception as e:
                logger.warning(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by score descending
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        # Assign ranks
        for i, opp in enumerate(opportunities[:top_n], 1):
            opp.rank = i
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        result = ScanResult(
            opportunities=opportunities[:top_n],
            scan_timestamp=start_time,
            symbols_scanned=len(universe),
            universe=universe,
            scan_duration_seconds=duration,
        )
        
        logger.info(f"Scan complete: {len(result.opportunities)} opportunities found in {duration:.1f}s")
        
        return result
    
    def _passes_prefilter(
        self,
        symbol: str,
        min_price: float,
        max_price: float,
        min_volume: int,
    ) -> bool:
        """Quick filter to avoid scanning obviously unsuitable symbols."""
        try:
            # Get basic quote
            quote = self.market_adapter.get_quote(symbol)
            
            if not quote:
                logger.debug(f"❌ {symbol}: No quote data returned")
                return False
            
            price = quote.get('close', quote.get('last', 0))
            volume = quote.get('volume', 0)
            
            logger.debug(f"📊 {symbol}: price=${price:.2f}, volume={volume:,}")
            
            # Apply filters
            if price < min_price:
                logger.debug(f"   ❌ Price ${price:.2f} below minimum ${min_price:.2f}")
                return False
            
            if price > max_price:
                logger.debug(f"   ❌ Price ${price:.2f} above maximum ${max_price:.2f}")
                return False
            
            if volume < min_volume:
                logger.debug(f"   ❌ Volume {volume:,} below minimum {min_volume:,}")
                return False
            
            logger.debug(f"   ✓ {symbol} passed prefilter")
            return True
            
        except Exception as e:
            logger.debug(f"❌ Prefilter failed for {symbol}: {e}")
            return False
    
    def _score_symbol(self, symbol: str) -> Optional[OpportunityScore]:
        """
        Calculate comprehensive opportunity score for a symbol.
        
        Returns:
            OpportunityScore or None if analysis fails
        """
        try:
            # Run all engines
            now = datetime.now(timezone.utc)
            
            # 1. Hedge Engine (options flow, gamma, vanna)
            hedge_output = self.hedge_engine.run(symbol, now)
            
            # 2. Liquidity Engine (orderflow, absorption)
            liquidity_output = self.liquidity_engine.run(symbol, now)
            
            # 3. Sentiment Engine (news, flow, technical)
            sentiment_output = self.sentiment_engine.run(symbol, now)
            
            # 4. Elasticity Engine (price resistance)
            elasticity_output = self.elasticity_engine.run(symbol, now)
            
            # Extract key metrics
            energy_asymmetry = hedge_output.features.get('energy_asymmetry', 0.0)
            movement_energy = hedge_output.features.get('movement_energy', 0.0)
            liquidity_quality = liquidity_output.features.get('liquidity_score', 0.0)
            sentiment_score = sentiment_output.features.get('sentiment_score', 0.0)
            
            # 5. Score components (0-1 scale)
            energy_score = self._score_energy(hedge_output.features)
            liquidity_score = self._score_liquidity(liquidity_output.features)
            volatility_score = self._score_volatility(hedge_output.features, elasticity_output.features)
            sentiment_component = self._score_sentiment(sentiment_output.features)
            options_score = self._score_options(symbol)
            
            # Weighted composite score
            weights = {
                'energy': 0.30,      # Energy asymmetry most important
                'liquidity': 0.25,   # Must be tradeable
                'volatility': 0.20,  # Volatility creates opportunity
                'sentiment': 0.15,   # Directional conviction
                'options': 0.10,     # Options liquidity bonus
            }
            
            composite_score = (
                weights['energy'] * energy_score +
                weights['liquidity'] * liquidity_score +
                weights['volatility'] * volatility_score +
                weights['sentiment'] * sentiment_component +
                weights['options'] * options_score
            )
            
            logger.debug(f"   🎯 {symbol} Component Scores:")
            logger.debug(f"      Energy: {energy_score:.3f} (asymmetry={energy_asymmetry:.2f})")
            logger.debug(f"      Liquidity: {liquidity_score:.3f}")
            logger.debug(f"      Volatility: {volatility_score:.3f}")
            logger.debug(f"      Sentiment: {sentiment_component:.3f}")
            logger.debug(f"      Options: {options_score:.3f}")
            logger.debug(f"      COMPOSITE: {composite_score:.3f}")
            
            # Determine direction and opportunity type
            direction, confidence = self._determine_direction(
                sentiment_score,
                energy_asymmetry,
                hedge_output.features
            )
            
            opportunity_type = self._classify_opportunity(
                energy_asymmetry,
                movement_energy,
                liquidity_output.regime,
                hedge_output.regime,
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                opportunity_type,
                energy_asymmetry,
                movement_energy,
                liquidity_quality,
                sentiment_score,
            )
            
            return OpportunityScore(
                symbol=symbol,
                score=composite_score,
                rank=0,  # Set during sorting
                energy_score=energy_score,
                liquidity_score=liquidity_score,
                volatility_score=volatility_score,
                sentiment_score=sentiment_component,
                options_score=options_score,
                energy_asymmetry=energy_asymmetry,
                movement_energy=movement_energy,
                liquidity_quality=liquidity_quality,
                iv_rank=None,  # TODO: Add IV rank calculation
                option_volume=None,  # TODO: Add option volume
                direction=direction,
                confidence=confidence,
                opportunity_type=opportunity_type,
                reasoning=reasoning,
                timestamp=now,
            )
            
        except Exception as e:
            logger.warning(f"Failed to score {symbol}: {e}")
            return None
    
    def _score_energy(self, hedge_features: Dict) -> float:
        """Score based on energy asymmetry and movement potential."""
        asymmetry = abs(hedge_features.get('energy_asymmetry', 0.0))
        movement_energy = hedge_features.get('movement_energy', 0.0)
        
        # High asymmetry = directional opportunity
        # Normalize asymmetry (>10 is very high)
        asymmetry_score = min(asymmetry / 10.0, 1.0)
        
        # High movement energy = active opportunity
        # Normalize energy (>1000 is very high)
        energy_norm = min(movement_energy / 1000.0, 1.0)
        
        # Combined: 70% asymmetry, 30% energy
        return 0.7 * asymmetry_score + 0.3 * energy_norm
    
    def _score_liquidity(self, liquidity_features: Dict) -> float:
        """Score based on liquidity quality."""
        liquidity_score = liquidity_features.get('liquidity_score', 0.0)
        
        # Liquidity score is already 0-1
        return liquidity_score
    
    def _score_volatility(self, hedge_features: Dict, elasticity_features: Dict) -> float:
        """Score based on volatility regime and expansion potential."""
        # Check for gamma regime (low gamma = expansion potential)
        gamma_regime = hedge_features.get('dealer_gamma_sign', 0.0)
        
        # Negative gamma = high volatility potential
        gamma_score = 0.5 if gamma_regime < 0 else 0.2
        
        # Elasticity (low elasticity = easier to move)
        elasticity = elasticity_features.get('elasticity_up', 1.0)
        elasticity_score = max(0.0, 1.0 - elasticity)  # Lower elasticity = higher score
        
        # Combined
        return 0.6 * gamma_score + 0.4 * elasticity_score
    
    def _score_sentiment(self, sentiment_features: Dict) -> float:
        """Score based on sentiment strength."""
        sentiment_score = sentiment_features.get('sentiment_score', 0.0)
        sentiment_confidence = sentiment_features.get('sentiment_confidence', 0.0)
        
        # Strong sentiment (positive or negative) + high confidence
        strength = abs(sentiment_score)
        
        return strength * sentiment_confidence
    
    def _score_options(self, symbol: str) -> float:
        """Score based on options activity and liquidity."""
        try:
            # Fetch recent options chain
            chain = self.options_adapter.get_chain(symbol, days_to_expiry=30)
            
            if chain is None or len(chain) == 0:
                return 0.0
            
            # Calculate average OI and volume
            avg_oi = chain['open_interest'].mean() if 'open_interest' in chain.columns else 0
            avg_volume = chain['volume'].mean() if 'volume' in chain.columns else 0
            
            # Normalize (>500 OI is good, >200 volume is good)
            oi_score = min(avg_oi / 500.0, 1.0)
            volume_score = min(avg_volume / 200.0, 1.0)
            
            return 0.6 * oi_score + 0.4 * volume_score
            
        except Exception as e:
            logger.debug(f"Options scoring failed for {symbol}: {e}")
            return 0.0
    
    def _determine_direction(
        self,
        sentiment_score: float,
        energy_asymmetry: float,
        hedge_features: Dict,
    ) -> Tuple[str, float]:
        """Determine directional bias and confidence."""
        # Sentiment provides primary direction
        if sentiment_score > 0.2:
            direction = 'bullish'
        elif sentiment_score < -0.2:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        # Energy asymmetry provides confidence
        asymmetry = abs(energy_asymmetry)
        confidence = min(asymmetry / 15.0, 1.0)  # >15 = very confident
        
        # Boost confidence if sentiment agrees with energy
        sentiment_strength = abs(sentiment_score)
        if sentiment_strength > 0.3:
            confidence = min(confidence * 1.2, 1.0)
        
        return direction, confidence
    
    def _classify_opportunity(
        self,
        energy_asymmetry: float,
        movement_energy: float,
        liquidity_regime: str,
        hedge_regime: str,
    ) -> str:
        """Classify type of opportunity."""
        asymmetry = abs(energy_asymmetry)
        
        # Strong directional bias
        if asymmetry > 10.0:
            return 'directional'
        
        # High energy with low asymmetry = volatility expansion
        if movement_energy > 800 and asymmetry < 5.0:
            return 'volatility'
        
        # Low energy + normal liquidity = range bound
        if movement_energy < 300:
            return 'range_bound'
        
        # Gamma squeeze indicators
        if hedge_regime and 'squeeze' in hedge_regime.lower():
            return 'gamma_squeeze'
        
        # Default
        return 'mixed'
    
    def _generate_reasoning(
        self,
        opportunity_type: str,
        energy_asymmetry: float,
        movement_energy: float,
        liquidity_quality: float,
        sentiment_score: float,
    ) -> str:
        """Generate human-readable reasoning for the opportunity."""
        parts = []
        
        # Opportunity type
        type_descriptions = {
            'directional': 'Strong directional bias detected',
            'volatility': 'Volatility expansion opportunity',
            'range_bound': 'Range-bound, premium selling opportunity',
            'gamma_squeeze': 'Gamma squeeze potential',
            'mixed': 'Mixed signals',
        }
        parts.append(type_descriptions.get(opportunity_type, 'Trading opportunity'))
        
        # Energy
        if abs(energy_asymmetry) > 10:
            direction = 'bullish' if energy_asymmetry > 0 else 'bearish'
            parts.append(f"High energy asymmetry ({direction})")
        
        # Liquidity
        if liquidity_quality > 0.7:
            parts.append("Excellent liquidity")
        elif liquidity_quality < 0.4:
            parts.append("Lower liquidity (caution)")
        
        # Sentiment
        if sentiment_score > 0.3:
            parts.append("Strong bullish sentiment")
        elif sentiment_score < -0.3:
            parts.append("Strong bearish sentiment")
        
        return " | ".join(parts)


# Default universe of liquid, optionable stocks
DEFAULT_UNIVERSE = [
    # Major Indices & ETFs
    'SPY', 'QQQ', 'IWM', 'DIA', 'EEM', 'EFA', 'GLD', 'SLV', 'TLT', 'HYG',
    
    # Mega Cap Tech
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
    
    # Large Cap Tech
    'NFLX', 'CRM', 'ADBE', 'ORCL', 'INTC', 'CSCO', 'AVGO',
    
    # Finance
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'AXP',
    
    # Healthcare
    'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'CVS',
    
    # Consumer
    'WMT', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'COST', 'DIS',
    
    # Industrial
    'BA', 'CAT', 'GE', 'MMM', 'HON', 'UPS', 'RTX',
    
    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD',
    
    # Volatility & Meme
    'AMC', 'GME', 'COIN', 'RIOT', 'MARA',
]
