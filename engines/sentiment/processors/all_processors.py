"""
Sentiment Engine v1.0 - Complete Processor Implementations

All sentiment processors following the canonical specification.
Pure functions, stateless, Polars/NumPy vectorized.
"""

from datetime import datetime
from typing import Literal, Optional

import numpy as np
import polars as pl

from engines.sentiment.models import (
    BollingerSignals,
    BreadthRegimeSignals,
    BreadthSignals,
    DarkPoolSignals,
    FlowBiasSignals,
    KeltnerSignals,
    MFISignals,
    MarketEnergySignals,
    OrderFlowSignals,
    OscillatorSignals,
    RSISignals,
    RiskRegimeSignals,
    SentimentSignal,
    StochasticSignals,
    TrendEnergySignals,
    VolatilitySignals,
    VolumeEnergySignals,
    WyckoffPhase,
    WyckoffSignals,
)


# ============================================================================
# WYCKOFF PROCESSOR
# ============================================================================

class WyckoffProcessor:
    """
    Analyzes market structure through Wyckoff methodology.
    
    Detects:
    - Accumulation/Distribution phases (A/B/C/D/E)
    - Springs and UTA Ds (signs of strength/weakness)
    - Demand vs Supply dominance
    - Composite operator bias
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.phase_sensitivity = config.get("phase_detection_sensitivity", 0.7)
        self.spring_threshold = config.get("spring_utad_threshold", 0.02)
        self.lookback = config.get("lookback_periods", 50)
    
    def process(self, df: pl.DataFrame) -> tuple[WyckoffSignals, SentimentSignal]:
        """
        Process OHLCV data and return Wyckoff analysis.
        
        Args:
            df: Polars DataFrame with columns [timestamp, open, high, low, close, volume]
        
        Returns:
            (WyckoffSignals, SentimentSignal) tuple
        """
        if df.is_empty() or len(df) < self.lookback:
            return self._default_output()
        
        # Phase detection
        phase = self._detect_phase(df)
        
        # Demand/Supply analysis
        demand_supply_ratio = self._calculate_demand_supply(df)
        
        # Spring/UTAD detection
        spring_detected = self._detect_spring(df)
        utad_detected = self._detect_utad(df)
        
        # Operator bias (composite)
        operator_bias = self._calculate_operator_bias(
            df, phase, demand_supply_ratio, spring_detected, utad_detected
        )
        
        # Overall strength
        strength_score = self._calculate_strength(
            phase, demand_supply_ratio, spring_detected, utad_detected
        )
        
        wyckoff_signals = WyckoffSignals(
            phase=phase,
            demand_supply_ratio=demand_supply_ratio,
            spring_detected=spring_detected,
            utad_detected=utad_detected,
            operator_bias=operator_bias,
            strength_score=strength_score,
        )
        
        # Convert to sentiment signal
        sentiment_signal = SentimentSignal(
            value=operator_bias,
            confidence=strength_score,
            weight=1.0,
            driver="wyckoff",
        )
        
        return wyckoff_signals, sentiment_signal
    
    def _detect_phase(self, df: pl.DataFrame) -> WyckoffPhase:
        """Detect current Wyckoff phase."""
        # Simplified phase detection based on price action and volume patterns
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        
        # Calculate price range and volume characteristics
        recent_range = np.ptp(closes[-20:])
        total_range = np.ptp(closes)
        avg_volume = np.mean(volumes)
        recent_volume = np.mean(volumes[-10:])
        
        # Price momentum
        momentum = (closes[-1] - closes[-20]) / closes[-20] if len(closes) >= 20 else 0.0
        
        # Phase logic
        if recent_range / (total_range + 1e-9) < 0.3 and recent_volume > avg_volume * 1.2:
            # Consolidation with high volume = Phase B (Accumulation)
            phase = "B"
            description = "Cause building - testing supply/demand"
            confidence = 0.7
        elif momentum > 0.05 and recent_volume > avg_volume:
            # Strong upward movement = Phase D or E (Markup)
            if np.std(closes[-10:]) > np.std(closes[-30:-10]):
                phase = "E"
                description = "Distribution or markup culmination"
                confidence = 0.6
            else:
                phase = "D"
                description = "Markup phase - trend in progress"
                confidence = 0.75
        elif momentum < -0.05 and recent_volume > avg_volume:
            # Strong downward movement = Phase D or E (Markdown)
            phase = "D"
            description = "Markdown phase - downtrend in progress"
            confidence = 0.75
        elif abs(momentum) < 0.02:
            # Low volatility, low momentum = Phase A or C
            if recent_volume < avg_volume * 0.8:
                phase = "A"
                description = "Preliminary support/resistance forming"
                confidence = 0.65
            else:
                phase = "C"
                description = "Testing - spring or upthrust likely"
                confidence = 0.7
        else:
            phase = "Unknown"
            description = "Phase unclear"
            confidence = 0.3
        
        return WyckoffPhase(phase=phase, confidence=confidence, description=description)
    
    def _calculate_demand_supply(self, df: pl.DataFrame) -> float:
        """Calculate demand/supply ratio. >1 = demand dominant, <1 = supply dominant."""
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        opens = df["open"].to_numpy()
        
        # Up bars (close > open) represent demand
        up_bars = closes > opens
        demand_volume = np.sum(volumes[up_bars])
        
        # Down bars represent supply
        down_bars = closes < opens
        supply_volume = np.sum(volumes[down_bars])
        
        if supply_volume == 0:
            return 2.0  # Cap at 2x for numerical stability
        
        ratio = demand_volume / supply_volume
        return float(np.clip(ratio, 0.0, 2.0))
    
    def _detect_spring(self, df: pl.DataFrame) -> bool:
        """
        Detect spring: Price breaks support but quickly recovers with low volume.
        Sign of accumulation.
        """
        if len(df) < 30:
            return False
        
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        
        # Recent support level
        support = np.min(lows[-30:-5])
        
        # Check if recent low broke support
        recent_low = np.min(lows[-5:])
        broke_support = recent_low < support * (1 - self.spring_threshold)
        
        # Check if recovered quickly
        current_close = closes[-1]
        recovered = current_close > support
        
        # Check if volume was relatively low during break
        avg_volume = np.mean(volumes[-30:-5])
        break_volume = np.mean(volumes[-5:])
        low_volume = break_volume < avg_volume * 1.1
        
        return bool(broke_support and recovered and low_volume)
    
    def _detect_utad(self, df: pl.DataFrame) -> bool:
        """
        Detect UTAD (Upthrust After Distribution): Price breaks resistance but fails.
        Sign of distribution.
        """
        if len(df) < 30:
            return False
        
        highs = df["high"].to_numpy()
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        
        # Recent resistance level
        resistance = np.max(highs[-30:-5])
        
        # Check if recent high broke resistance
        recent_high = np.max(highs[-5:])
        broke_resistance = recent_high > resistance * (1 + self.spring_threshold)
        
        # Check if failed to hold
        current_close = closes[-1]
        failed = current_close < resistance
        
        # Check if volume was high during break (distribution)
        avg_volume = np.mean(volumes[-30:-5])
        break_volume = np.mean(volumes[-5:])
        high_volume = break_volume > avg_volume * 1.2
        
        return bool(broke_resistance and failed and high_volume)
    
    def _calculate_operator_bias(
        self,
        df: pl.DataFrame,
        phase: WyckoffPhase,
        demand_supply: float,
        spring: bool,
        utad: bool,
    ) -> float:
        """Calculate composite operator positioning bias [-1, 1]."""
        bias = 0.0
        
        # Phase contribution
        phase_bias = {
            "A": 0.0,  # Neutral - preliminary
            "B": 0.2,  # Slightly bullish if accumulation
            "C": 0.0,  # Neutral - testing
            "D": 0.5,  # Strong bias in trend direction
            "E": 0.3,  # Moderate bias - nearing end
            "Unknown": 0.0,
        }
        
        # Determine if accumulation or distribution based on demand/supply
        if demand_supply > 1.1:
            bias += phase_bias[phase.phase]  # Accumulation
        elif demand_supply < 0.9:
            bias -= phase_bias[phase.phase]  # Distribution
        
        # Spring is bullish
        if spring:
            bias += 0.3
        
        # UTAD is bearish
        if utad:
            bias -= 0.3
        
        # Demand/supply contribution
        # Map [0.5, 2.0] to [-0.3, +0.3]
        ds_contribution = (demand_supply - 1.0) * 0.3
        bias += ds_contribution
        
        return float(np.clip(bias, -1.0, 1.0))
    
    def _calculate_strength(
        self,
        phase: WyckoffPhase,
        demand_supply: float,
        spring: bool,
        utad: bool,
    ) -> float:
        """Calculate overall Wyckoff signal strength [0, 1]."""
        strength = phase.confidence * 0.5
        
        # Strong demand/supply imbalance increases strength
        ds_strength = abs(demand_supply - 1.0) * 0.3
        strength += ds_strength
        
        # Spring/UTAD detection increases confidence
        if spring or utad:
            strength += 0.2
        
        return float(np.clip(strength, 0.0, 1.0))
    
    def _default_output(self) -> tuple[WyckoffSignals, SentimentSignal]:
        """Return default output when insufficient data."""
        phase = WyckoffPhase(phase="Unknown", confidence=0.0, description="Insufficient data")
        wyckoff = WyckoffSignals(
            phase=phase,
            demand_supply_ratio=1.0,
            spring_detected=False,
            utad_detected=False,
            operator_bias=0.0,
            strength_score=0.0,
        )
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="wyckoff")
        return wyckoff, signal


# ============================================================================
# OSCILLATOR PROCESSOR
# ============================================================================

class OscillatorProcessor:
    """
    Technical oscillators: RSI, MFI, Stochastic.
    
    Provides:
    - Overbought/oversold conditions
    - Momentum and energy decay
    - Divergence detection
    - Impulse/reversion signals
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.rsi_period = config.get("rsi_period", 14)
        self.mfi_period = config.get("mfi_period", 14)
        self.stoch_k = config.get("stoch_k_period", 14)
        self.stoch_d = config.get("stoch_d_period", 3)
        self.ob_threshold = config.get("overbought_threshold", 70.0)
        self.os_threshold = config.get("oversold_threshold", 30.0)
    
    def process(self, df: pl.DataFrame) -> tuple[OscillatorSignals, SentimentSignal]:
        """Process oscillator indicators."""
        if df.is_empty() or len(df) < max(self.rsi_period, self.mfi_period, self.stoch_k) + 5:
            return self._default_output()
        
        # Calculate RSI
        rsi_signals = self._calculate_rsi(df)
        
        # Calculate MFI
        mfi_signals = self._calculate_mfi(df)
        
        # Calculate Stochastic
        stoch_signals = self._calculate_stochastic(df)
        
        # Composite score
        composite = self._calculate_composite(rsi_signals, mfi_signals, stoch_signals)
        
        # Energy decay (rate of momentum loss)
        energy_decay = self._calculate_energy_decay(rsi_signals, df)
        
        oscillator_signals = OscillatorSignals(
            rsi=rsi_signals,
            mfi=mfi_signals,
            stochastic=stoch_signals,
            composite_score=composite,
            energy_decay=energy_decay,
        )
        
        # Convert to sentiment signal
        # Use composite score with confidence based on agreement
        confidence = self._calculate_confidence(rsi_signals, mfi_signals, stoch_signals)
        
        sentiment_signal = SentimentSignal(
            value=composite,
            confidence=confidence,
            weight=1.0,
            driver="oscillators",
        )
        
        return oscillator_signals, sentiment_signal
    
    def _calculate_rsi(self, df: pl.DataFrame) -> RSISignals:
        """Calculate RSI and derived signals."""
        closes = df["close"].to_numpy()
        
        # Calculate price changes
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate average gains and losses
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        # Handle edge case of no movement
        if avg_gain == 0 and avg_loss == 0:
            rsi_value = 50.0  # Neutral when no movement
        elif avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100.0 - (100.0 / (1.0 + rs))
        
        # Overbought/oversold
        overbought = rsi_value > self.ob_threshold
        oversold = rsi_value < self.os_threshold
        
        # Energy decay slope (RSI rate of change)
        if len(closes) >= self.rsi_period + 5:
            prev_rsi = self._calculate_rsi_value(closes[:-5])
            energy_slope = (rsi_value - prev_rsi) / 5.0
        else:
            energy_slope = 0.0
        
        # Simple divergence detection (price vs RSI)
        divergence = False
        if len(closes) >= 30:
            price_slope = (closes[-1] - closes[-20]) / closes[-20]
            rsi_current = rsi_value
            rsi_past = self._calculate_rsi_value(closes[:-20])
            rsi_slope = (rsi_current - rsi_past) / 100.0
            
            # Bearish divergence: price up, RSI down
            # Bullish divergence: price down, RSI up
            divergence = (price_slope > 0 and rsi_slope < -0.1) or (price_slope < 0 and rsi_slope > 0.1)
        
        return RSISignals(
            value=float(rsi_value),
            overbought=bool(overbought),
            oversold=bool(oversold),
            energy_decay_slope=float(energy_slope),
            divergence_detected=bool(divergence),
        )
    
    def _calculate_rsi_value(self, closes: np.ndarray) -> float:
        """Helper to calculate RSI value for given closes array."""
        if len(closes) < self.rsi_period + 1:
            return 50.0
        
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))
    
    def _calculate_mfi(self, df: pl.DataFrame) -> MFISignals:
        """Calculate Money Flow Index."""
        # Typical price
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        money_flow = typical_price * df["volume"]
        
        tp_array = typical_price.to_numpy()
        mf_array = money_flow.to_numpy()
        
        # Positive and negative money flow
        positive_flow = np.sum(mf_array[-self.mfi_period:][np.diff(tp_array[-self.mfi_period-1:]) > 0])
        negative_flow = np.sum(mf_array[-self.mfi_period:][np.diff(tp_array[-self.mfi_period-1:]) < 0])
        
        if negative_flow == 0:
            mfi_value = 100.0
        else:
            money_ratio = positive_flow / negative_flow
            mfi_value = 100.0 - (100.0 / (1.0 + money_ratio))
        
        # Buy/sell pressure (normalized)
        total_flow = positive_flow + negative_flow
        buy_pressure = positive_flow / total_flow if total_flow > 0 else 0.5
        sell_pressure = negative_flow / total_flow if total_flow > 0 else 0.5
        
        overbought = mfi_value > self.ob_threshold
        oversold = mfi_value < self.os_threshold
        
        return MFISignals(
            value=float(mfi_value),
            buy_pressure=float(buy_pressure),
            sell_pressure=float(sell_pressure),
            overbought=bool(overbought),
            oversold=bool(oversold),
        )
    
    def _calculate_stochastic(self, df: pl.DataFrame) -> StochasticSignals:
        """Calculate Stochastic oscillator."""
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        
        # %K calculation
        period_high = np.max(highs[-self.stoch_k:])
        period_low = np.min(lows[-self.stoch_k:])
        current_close = closes[-1]
        
        if period_high == period_low:
            k_value = 50.0
        else:
            k_value = 100.0 * (current_close - period_low) / (period_high - period_low)
        
        # %D calculation (SMA of %K) - simplified
        if len(closes) >= self.stoch_k + self.stoch_d:
            k_values = []
            for i in range(self.stoch_d):
                idx = -(i + 1)
                ph = np.max(highs[idx - self.stoch_k:idx])
                pl = np.min(lows[idx - self.stoch_k:idx])
                if ph == pl:
                    k_values.append(50.0)
                else:
                    k_values.append(100.0 * (closes[idx] - pl) / (ph - pl))
            d_value = np.mean(k_values)
        else:
            d_value = k_value
        
        # Crossovers
        if len(closes) >= self.stoch_k + self.stoch_d + 1:
            # Previous K and D
            prev_k = self._calculate_k_value(highs[:-1], lows[:-1], closes[:-1])
            prev_d = d_value  # Simplified - using same D
            impulse = k_value > d_value and prev_k <= prev_d
            reversion = k_value < d_value and prev_k >= prev_d
        else:
            impulse = False
            reversion = False
        
        overbought = k_value > self.ob_threshold
        oversold = k_value < self.os_threshold
        
        return StochasticSignals(
            k_value=float(k_value),
            d_value=float(d_value),
            impulse=bool(impulse),
            reversion=bool(reversion),
            overbought=bool(overbought),
            oversold=bool(oversold),
        )
    
    def _calculate_k_value(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Helper to calculate %K value."""
        period_high = np.max(highs[-self.stoch_k:])
        period_low = np.min(lows[-self.stoch_k:])
        current_close = closes[-1]
        
        if period_high == period_low:
            return 50.0
        
        return float(100.0 * (current_close - period_low) / (period_high - period_low))
    
    def _calculate_composite(
        self, rsi: RSISignals, mfi: MFISignals, stoch: StochasticSignals
    ) -> float:
        """Combine oscillators into composite score [-1, 1]."""
        # Map each oscillator to [-1, 1] range
        # 0-30 = oversold (negative), 70-100 = overbought (positive), 50 = neutral
        
        def map_to_sentiment(value: float) -> float:
            if value < 30:
                return (value - 30) / 30  # Maps [0,30] to [-1,0]
            elif value > 70:
                return (value - 70) / 30  # Maps [70,100] to [0,1]
            else:
                return (value - 50) / 20  # Maps [30,70] to [-1,1]
        
        rsi_sentiment = map_to_sentiment(rsi.value)
        mfi_sentiment = map_to_sentiment(mfi.value)
        stoch_sentiment = map_to_sentiment(stoch.k_value)
        
        # Weighted average
        composite = (rsi_sentiment * 0.4 + mfi_sentiment * 0.3 + stoch_sentiment * 0.3)
        
        return float(np.clip(composite, -1.0, 1.0))
    
    def _calculate_energy_decay(self, rsi: RSISignals, df: pl.DataFrame) -> float:
        """Calculate momentum energy decay rate."""
        # Use RSI slope as primary indicator
        # Negative slope = decaying momentum
        return float(rsi.energy_decay_slope)
    
    def _calculate_confidence(
        self, rsi: RSISignals, mfi: MFISignals, stoch: StochasticSignals
    ) -> float:
        """Calculate confidence based on oscillator agreement."""
        # Check if oscillators agree (all bullish, all bearish, or all neutral)
        signals = [
            1 if rsi.value > 60 else (-1 if rsi.value < 40 else 0),
            1 if mfi.value > 60 else (-1 if mfi.value < 40 else 0),
            1 if stoch.k_value > 60 else (-1 if stoch.k_value < 40 else 0),
        ]
        
        # Calculate agreement (all same sign = high confidence)
        agreement = len(set(signals)) == 1
        
        if agreement:
            return 0.8
        elif len([s for s in signals if s != 0]) >= 2:
            # At least 2 non-neutral signals
            return 0.6
        else:
            return 0.4
    
    def _default_output(self) -> tuple[OscillatorSignals, SentimentSignal]:
        """Return default output when insufficient data."""
        rsi = RSISignals(value=50.0, overbought=False, oversold=False, energy_decay_slope=0.0, divergence_detected=False)
        mfi = MFISignals(value=50.0, buy_pressure=0.5, sell_pressure=0.5, overbought=False, oversold=False)
        stoch = StochasticSignals(k_value=50.0, d_value=50.0, impulse=False, reversion=False, overbought=False, oversold=False)
        
        oscillator = OscillatorSignals(rsi=rsi, mfi=mfi, stochastic=stoch, composite_score=0.0, energy_decay=0.0)
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="oscillators")
        
        return oscillator, signal


# ============================================================================
# VOLATILITY PROCESSOR
# ============================================================================

class VolatilityProcessor:
    """
    Volatility envelope analysis: Bollinger Bands and Keltner Channels.
    
    Provides:
    - Mean reversion pressure (Bollinger)
    - Force boundaries (Keltner)
    - Squeeze detection (BB inside KC)
    - Compression/expansion energy
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.bb_period = config.get("bb_period", 20)
        self.bb_std = config.get("bb_std_dev", 2.0)
        self.kc_period = config.get("kc_period", 20)
        self.kc_mult = config.get("kc_atr_mult", 2.0)
    
    def process(self, df: pl.DataFrame) -> tuple[VolatilitySignals, SentimentSignal]:
        """Process volatility indicators."""
        if df.is_empty() or len(df) < max(self.bb_period, self.kc_period):
            return self._default_output()
        
        # Calculate Bollinger Bands
        bollinger = self._calculate_bollinger(df)
        
        # Calculate Keltner Channels
        keltner = self._calculate_keltner(df)
        
        # Squeeze detection
        squeeze = self._detect_squeeze(bollinger, keltner)
        
        # Compression/expansion energy
        compression_energy, expansion_energy = self._calculate_energies(bollinger, keltner, df)
        
        # Composite envelope score
        envelope_score = self._calculate_envelope_score(bollinger, keltner)
        
        volatility_signals = VolatilitySignals(
            bollinger=bollinger,
            keltner=keltner,
            squeeze_detected=squeeze,
            compression_energy=compression_energy,
            expansion_energy=expansion_energy,
            envelope_score=envelope_score,
        )
        
        # Convert to sentiment signal
        # Use envelope score with confidence based on volatility state
        confidence = self._calculate_confidence(bollinger, keltner, squeeze)
        
        sentiment_signal = SentimentSignal(
            value=envelope_score,
            confidence=confidence,
            weight=1.0,
            driver="volatility",
        )
        
        return volatility_signals, sentiment_signal
    
    def _calculate_bollinger(self, df: pl.DataFrame) -> BollingerSignals:
        """Calculate Bollinger Bands."""
        closes = df["close"].to_numpy()
        
        # Middle band (SMA)
        middle = np.mean(closes[-self.bb_period:])
        
        # Standard deviation
        std = np.std(closes[-self.bb_period:])
        
        # Upper and lower bands
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)
        
        # %B - position within bands
        current = closes[-1]
        if upper == lower:
            percent_b = 0.5
        else:
            percent_b = (current - lower) / (upper - lower)
        
        # Bandwidth - measure of volatility
        bandwidth = (upper - lower) / middle if middle != 0 else 0.0
        
        # Mean reversion pressure
        # High %B (>0.8) = strong overbought = negative pressure (expect reversion)
        # Low %B (<0.2) = strong oversold = positive pressure (expect bounce)
        if percent_b > 0.8:
            pressure = -(percent_b - 0.8) / 0.2  # Maps [0.8,1.0] to [0,-1]
        elif percent_b < 0.2:
            pressure = (0.2 - percent_b) / 0.2  # Maps [0,0.2] to [1,0]
        else:
            pressure = 0.0
        
        # Squeeze detection (low bandwidth)
        avg_bandwidth = np.mean([
            (np.max(closes[i-self.bb_period:i]) - np.min(closes[i-self.bb_period:i])) / np.mean(closes[i-self.bb_period:i])
            for i in range(self.bb_period, len(closes))
        ]) if len(closes) > self.bb_period else bandwidth
        
        squeeze_active = bandwidth < avg_bandwidth * 0.7
        
        return BollingerSignals(
            percent_b=float(percent_b),
            bandwidth=float(bandwidth),
            mean_reversion_pressure=float(np.clip(pressure, -1.0, 1.0)),
            squeeze_active=bool(squeeze_active),
        )
    
    def _calculate_keltner(self, df: pl.DataFrame) -> KeltnerSignals:
        """Calculate Keltner Channels."""
        closes = df["close"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        
        # Middle line (EMA of close) - simplified as SMA
        middle = np.mean(closes[-self.kc_period:])
        
        # ATR calculation
        tr_values = []
        for i in range(1, min(len(closes), self.kc_period + 1)):
            high_low = highs[-i] - lows[-i]
            high_close = abs(highs[-i] - closes[-i-1])
            low_close = abs(lows[-i] - closes[-i-1])
            tr_values.append(max(high_low, high_close, low_close))
        
        atr = np.mean(tr_values) if tr_values else 0.0
        
        # Upper and lower channels
        upper = middle + (self.kc_mult * atr)
        lower = middle - (self.kc_mult * atr)
        
        # Position relative to channel
        current = closes[-1]
        if upper == lower:
            position = 0.0
        else:
            position = (current - middle) / (upper - middle)
        
        # Expansion/compression detection
        # Compare current channel width to historical average
        if len(closes) > self.kc_period * 2:
            historical_widths = []
            for i in range(self.kc_period, len(closes) - self.kc_period):
                h_atr = np.mean([
                    max(highs[j] - lows[j], abs(highs[j] - closes[j-1]), abs(lows[j] - closes[j-1]))
                    for j in range(i - self.kc_period, i)
                ])
                historical_widths.append(h_atr)
            avg_width = np.mean(historical_widths)
        else:
            avg_width = atr
        
        expansion = atr > avg_width * 1.2
        compression = atr < avg_width * 0.8
        
        # Force boundary (elasticity measure)
        # Distance to nearest boundary as fraction of channel width
        if current > middle:
            distance_to_boundary = (upper - current) / (upper - middle) if upper != middle else 1.0
        else:
            distance_to_boundary = (current - lower) / (middle - lower) if middle != lower else 1.0
        
        force_boundary = float(distance_to_boundary)
        
        return KeltnerSignals(
            position=float(position),
            expansion=bool(expansion),
            compression=bool(compression),
            force_boundary=float(np.clip(force_boundary, 0.0, 2.0)),
        )
    
    def _detect_squeeze(self, bollinger: BollingerSignals, keltner: KeltnerSignals) -> bool:
        """Detect squeeze: Bollinger Bands inside Keltner Channels."""
        # True squeeze = BB bandwidth is narrowing AND KC is compressing
        return bool(bollinger.squeeze_active and keltner.compression)
    
    def _calculate_energies(
        self, bollinger: BollingerSignals, keltner: KeltnerSignals, df: pl.DataFrame
    ) -> tuple[float, float]:
        """Calculate compression and expansion energy."""
        # Compression energy: potential energy building during squeeze
        if bollinger.squeeze_active or keltner.compression:
            # Measure how long the squeeze has been active
            # For now, use bandwidth as proxy for compression energy
            compression = (1.0 - bollinger.bandwidth) * 2.0
        else:
            compression = 0.0
        
        # Expansion energy: kinetic energy during breakout
        if keltner.expansion:
            # Measure strength of expansion
            expansion = bollinger.bandwidth * 2.0
        else:
            expansion = 0.0
        
        return float(compression), float(expansion)
    
    def _calculate_envelope_score(
        self, bollinger: BollingerSignals, keltner: KeltnerSignals
    ) -> float:
        """Calculate composite envelope sentiment score [-1, 1]."""
        # Combine BB mean reversion pressure with KC position
        score = (bollinger.mean_reversion_pressure * 0.6 + keltner.position * 0.4)
        
        return float(np.clip(score, -1.0, 1.0))
    
    def _calculate_confidence(
        self, bollinger: BollingerSignals, keltner: KeltnerSignals, squeeze: bool
    ) -> float:
        """Calculate confidence in volatility signals."""
        confidence = 0.5
        
        # High confidence during squeeze (clear setup)
        if squeeze:
            confidence += 0.2
        
        # High confidence at extreme positions
        if abs(bollinger.percent_b - 0.5) > 0.3:
            confidence += 0.15
        
        if abs(keltner.position) > 0.5:
            confidence += 0.15
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def _default_output(self) -> tuple[VolatilitySignals, SentimentSignal]:
        """Return default output when insufficient data."""
        bollinger = BollingerSignals(
            percent_b=0.5, bandwidth=0.0, mean_reversion_pressure=0.0, squeeze_active=False
        )
        keltner = KeltnerSignals(position=0.0, expansion=False, compression=False, force_boundary=1.0)
        volatility = VolatilitySignals(
            bollinger=bollinger,
            keltner=keltner,
            squeeze_detected=False,
            compression_energy=0.0,
            expansion_energy=0.0,
            envelope_score=0.0,
        )
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="volatility")
        
        return volatility, signal


# ============================================================================
# FLOW/BIAS PROCESSOR
# ============================================================================

class FlowBiasProcessor:
    """
    Order flow and dark pool sentiment analysis.
    
    Provides:
    - Order flow imbalance (bid/ask dynamics)
    - Net aggressor pressure
    - Dark pool sentiment (DIX/GEX when available)
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.orderflow_window = config.get("orderflow_window", 10)
        self.darkpool_enabled = config.get("darkpool_enabled", True)
    
    def process(self, df: pl.DataFrame, darkpool_data: Optional[dict] = None) -> tuple[FlowBiasSignals, SentimentSignal]:
        """Process flow and bias indicators."""
        if df.is_empty() or len(df) < self.orderflow_window:
            return self._default_output()
        
        # Calculate order flow
        orderflow = self._calculate_orderflow(df)
        
        # Calculate dark pool sentiment
        darkpool = self._calculate_darkpool(darkpool_data) if self.darkpool_enabled else self._default_darkpool()
        
        # Composite flow bias
        composite_bias = self._calculate_composite(orderflow, darkpool)
        
        # Overall confidence
        confidence = self._calculate_confidence(orderflow, darkpool)
        
        flow_signals = FlowBiasSignals(
            order_flow=orderflow,
            dark_pool=darkpool,
            composite_flow_bias=composite_bias,
            flow_confidence=confidence,
        )
        
        # Convert to sentiment signal
        sentiment_signal = SentimentSignal(
            value=composite_bias,
            confidence=confidence,
            weight=1.0,
            driver="flow",
        )
        
        return flow_signals, sentiment_signal
    
    def _calculate_orderflow(self, df: pl.DataFrame) -> OrderFlowSignals:
        """Calculate order flow imbalance from price-volume action."""
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        opens = df["open"].to_numpy()
        
        # Bid/ask imbalance estimation
        # Up bars = aggressive buying, down bars = aggressive selling
        up_volume = np.sum(volumes[-self.orderflow_window:][closes[-self.orderflow_window:] > opens[-self.orderflow_window:]])
        down_volume = np.sum(volumes[-self.orderflow_window:][closes[-self.orderflow_window:] < opens[-self.orderflow_window:]])
        total_volume = up_volume + down_volume
        
        if total_volume == 0:
            imbalance = 0.0
            buy_ratio = 0.5
            sell_ratio = 0.5
        else:
            imbalance = (up_volume - down_volume) / total_volume
            buy_ratio = up_volume / total_volume
            sell_ratio = down_volume / total_volume
        
        # Net aggressor pressure (buyers - sellers)
        aggressor_pressure = imbalance
        
        return OrderFlowSignals(
            bid_ask_imbalance=float(np.clip(imbalance, -1.0, 1.0)),
            aggressive_buy_ratio=float(buy_ratio),
            aggressive_sell_ratio=float(sell_ratio),
            net_aggressor_pressure=float(np.clip(aggressor_pressure, -1.0, 1.0)),
        )
    
    def _calculate_darkpool(self, darkpool_data: Optional[dict]) -> DarkPoolSignals:
        """Calculate dark pool sentiment if data available."""
        if darkpool_data is None:
            return self._default_darkpool()
        
        # Extract DIX and GEX if available
        dix = darkpool_data.get("dix", None)
        gex = darkpool_data.get("gex", None)
        
        # Calculate sentiment score
        # DIX > 0.45 is bullish, < 0.40 is bearish
        # GEX positive = resistance, negative = acceleration
        sentiment = 0.0
        confidence = 0.0
        
        if dix is not None:
            dix_sentiment = (dix - 0.425) / 0.075  # Map [0.35, 0.50] to [-1, 1]
            sentiment += dix_sentiment * 0.6
            confidence += 0.5
        
        if gex is not None:
            # Normalize GEX (assuming billions)
            gex_sentiment = -np.tanh(gex / 5.0)  # Negative GEX is bullish (less resistance)
            sentiment += gex_sentiment * 0.4
            confidence += 0.5
        
        sentiment = float(np.clip(sentiment, -1.0, 1.0))
        
        return DarkPoolSignals(
            dix_value=dix,
            gex_value=gex,
            sentiment_score=sentiment,
            confidence=float(np.clip(confidence, 0.0, 1.0)),
        )
    
    def _default_darkpool(self) -> DarkPoolSignals:
        """Return default dark pool signals."""
        return DarkPoolSignals(
            dix_value=None,
            gex_value=None,
            sentiment_score=0.0,
            confidence=0.0,
        )
    
    def _calculate_composite(self, orderflow: OrderFlowSignals, darkpool: DarkPoolSignals) -> float:
        """Calculate composite flow bias."""
        # Weight order flow heavily, dark pool moderately
        if darkpool.confidence > 0:
            composite = (orderflow.net_aggressor_pressure * 0.7 + darkpool.sentiment_score * 0.3)
        else:
            composite = orderflow.net_aggressor_pressure
        
        return float(np.clip(composite, -1.0, 1.0))
    
    def _calculate_confidence(self, orderflow: OrderFlowSignals, darkpool: DarkPoolSignals) -> float:
        """Calculate overall flow confidence."""
        # Base confidence from order flow strength
        of_confidence = abs(orderflow.net_aggressor_pressure) * 0.5 + 0.3
        
        # Boost if dark pool agrees
        if darkpool.confidence > 0:
            agreement = np.sign(orderflow.net_aggressor_pressure) == np.sign(darkpool.sentiment_score)
            if agreement:
                confidence = min(1.0, of_confidence + darkpool.confidence * 0.3)
            else:
                confidence = of_confidence * 0.7
        else:
            confidence = of_confidence
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def _default_output(self) -> tuple[FlowBiasSignals, SentimentSignal]:
        """Return default output when insufficient data."""
        orderflow = OrderFlowSignals(
            bid_ask_imbalance=0.0,
            aggressive_buy_ratio=0.5,
            aggressive_sell_ratio=0.5,
            net_aggressor_pressure=0.0,
        )
        darkpool = self._default_darkpool()
        flow = FlowBiasSignals(
            order_flow=orderflow,
            dark_pool=darkpool,
            composite_flow_bias=0.0,
            flow_confidence=0.0,
        )
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="flow")
        
        return flow, signal


# ============================================================================
# BREADTH/REGIME PROCESSOR
# ============================================================================

class BreadthRegimeProcessor:
    """
    Market breadth and risk regime analysis.
    
    Provides:
    - Advance/decline dynamics
    - Percentage above moving averages
    - Risk-on/risk-off regime
    - Multi-period regime consensus
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.ma_periods = config.get("ma_periods", [50, 200])
        self.regime_window = config.get("regime_window", 20)
    
    def process(
        self, df: pl.DataFrame, breadth_data: Optional[dict] = None
    ) -> tuple[BreadthRegimeSignals, SentimentSignal]:
        """Process breadth and regime indicators."""
        if df.is_empty() or len(df) < max(self.ma_periods):
            return self._default_output()
        
        # Calculate breadth (if data available)
        breadth = self._calculate_breadth(df, breadth_data)
        
        # Calculate risk regime
        risk_regime = self._calculate_risk_regime(df)
        
        # Multi-period regime
        multi_period = self._calculate_multi_period_regime(df)
        
        # Composite score
        composite = self._calculate_composite(breadth, risk_regime)
        
        breadth_signals = BreadthRegimeSignals(
            breadth=breadth,
            risk_regime=risk_regime,
            multi_period_regime=multi_period,
            composite_score=composite,
        )
        
        # Convert to sentiment signal
        confidence = self._calculate_confidence(breadth, risk_regime)
        
        sentiment_signal = SentimentSignal(
            value=composite,
            confidence=confidence,
            weight=1.0,
            driver="breadth",
        )
        
        return breadth_signals, sentiment_signal
    
    def _calculate_breadth(self, df: pl.DataFrame, breadth_data: Optional[dict]) -> BreadthSignals:
        """Calculate market breadth indicators."""
        if breadth_data is not None:
            # Use actual breadth data if available
            advances = breadth_data.get("advances", 0)
            declines = breadth_data.get("declines", 0)
            total = advances + declines
            ad_ratio = advances / total if total > 0 else 1.0
            
            # Thrust detection (strong move in one direction)
            thrust = ad_ratio > 0.7 or ad_ratio < 0.3
        else:
            # Estimate from single symbol (limited utility)
            closes = df["close"].to_numpy()
            returns = np.diff(closes) / closes[:-1]
            positive_days = np.sum(returns[-20:] > 0)
            ad_ratio = positive_days / 20.0
            thrust = False
        
        # Calculate % above MA
        closes = df["close"].to_numpy()
        pct_above_ma = 0.0
        for period in self.ma_periods:
            if len(closes) >= period:
                ma = np.mean(closes[-period:])
                if closes[-1] > ma:
                    pct_above_ma += 1.0 / len(self.ma_periods)
        
        # Divergence detection (price vs breadth)
        divergence = False
        if breadth_data is not None and len(closes) >= 20:
            price_trend = (closes[-1] - closes[-20]) / closes[-20]
            breadth_trend = ad_ratio - 0.5  # Normalize around 0.5
            # Bearish divergence: price up but breadth weakening
            # Bullish divergence: price down but breadth improving
            divergence = (price_trend > 0.05 and breadth_trend < -0.1) or (price_trend < -0.05 and breadth_trend > 0.1)
        
        return BreadthSignals(
            advance_decline_ratio=float(ad_ratio),
            pct_above_ma=float(pct_above_ma),
            breadth_thrust=bool(thrust),
            divergence_detected=bool(divergence),
        )
    
    def _calculate_risk_regime(self, df: pl.DataFrame) -> RiskRegimeSignals:
        """Determine risk-on/risk-off regime."""
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        
        # Simple heuristic based on volatility and trend
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns[-self.regime_window:])
        avg_return = np.mean(returns[-self.regime_window:])
        
        # Risk-on: low volatility, positive returns
        # Risk-off: high volatility, negative returns
        
        # Historical volatility comparison
        if len(returns) > self.regime_window * 2:
            hist_vol = np.std(returns[:-self.regime_window])
        else:
            hist_vol = volatility
        
        vol_ratio = volatility / hist_vol if hist_vol > 0 else 1.0
        
        if avg_return > 0 and vol_ratio < 1.2:
            regime = "risk_on"
            rotation = 0.5
            confidence = 0.7
        elif avg_return < 0 and vol_ratio > 1.3:
            regime = "risk_off"
            rotation = -0.5
            confidence = 0.7
        else:
            regime = "neutral"
            rotation = 0.0
            confidence = 0.5
        
        return RiskRegimeSignals(
            regime=regime,
            rotation_score=float(rotation),
            confidence=float(confidence),
        )
    
    def _calculate_multi_period_regime(self, df: pl.DataFrame) -> str:
        """Calculate cross-timeframe regime consensus."""
        closes = df["close"].to_numpy()
        
        # Check multiple timeframes
        regimes = []
        
        for period in [10, 20, 50]:
            if len(closes) >= period:
                returns = (closes[-1] - closes[-period]) / closes[-period]
                if returns > 0.05:
                    regimes.append("bullish")
                elif returns < -0.05:
                    regimes.append("bearish")
                else:
                    regimes.append("neutral")
        
        if not regimes:
            return "unknown"
        
        # Consensus
        if regimes.count("bullish") >= 2:
            return "bullish_consensus"
        elif regimes.count("bearish") >= 2:
            return "bearish_consensus"
        else:
            return "mixed"
    
    def _calculate_composite(self, breadth: BreadthSignals, risk: RiskRegimeSignals) -> float:
        """Calculate composite breadth/regime score."""
        # Breadth contribution
        breadth_score = (breadth.advance_decline_ratio - 0.5) * 2.0  # Map [0,1] to [-1,1]
        pct_ma_score = (breadth.pct_above_ma - 0.5) * 2.0
        
        # Risk regime contribution
        risk_score = risk.rotation_score
        
        # Weighted composite
        composite = (breadth_score * 0.4 + pct_ma_score * 0.3 + risk_score * 0.3)
        
        return float(np.clip(composite, -1.0, 1.0))
    
    def _calculate_confidence(self, breadth: BreadthSignals, risk: RiskRegimeSignals) -> float:
        """Calculate confidence in breadth/regime signals."""
        confidence = 0.5
        
        # High confidence during thrust
        if breadth.breadth_thrust:
            confidence += 0.2
        
        # High confidence in clear risk regime
        confidence += risk.confidence * 0.3
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def _default_output(self) -> tuple[BreadthRegimeSignals, SentimentSignal]:
        """Return default output when insufficient data."""
        breadth = BreadthSignals(
            advance_decline_ratio=0.5,
            pct_above_ma=0.5,
            breadth_thrust=False,
            divergence_detected=False,
        )
        risk = RiskRegimeSignals(regime="neutral", rotation_score=0.0, confidence=0.0)
        breadth_regime = BreadthRegimeSignals(
            breadth=breadth,
            risk_regime=risk,
            multi_period_regime="unknown",
            composite_score=0.0,
        )
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="breadth")
        
        return breadth_regime, signal


# ============================================================================
# ENERGY PROCESSOR
# ============================================================================

class EnergyProcessor:
    """
    Market energy and momentum analysis.
    
    Provides:
    - Trend energy and coherence
    - Volume-energy correlation
    - Exhaustion vs continuation detection
    - Metabolic load measurement
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.momentum_window = config.get("momentum_window", 14)
        self.coherence_window = config.get("coherence_window", 20)
    
    def process(self, df: pl.DataFrame) -> tuple[MarketEnergySignals, SentimentSignal]:
        """Process energy indicators."""
        if df.is_empty() or len(df) < max(self.momentum_window, self.coherence_window):
            return self._default_output()
        
        # Calculate trend energy
        trend_energy = self._calculate_trend_energy(df)
        
        # Calculate volume energy
        volume_energy = self._calculate_volume_energy(df)
        
        # Exhaustion vs continuation
        exhaustion_continuation = self._calculate_exhaustion_continuation(df, trend_energy, volume_energy)
        
        # Metabolic load
        metabolic_load = self._calculate_metabolic_load(df)
        
        energy_signals = MarketEnergySignals(
            trend_energy=trend_energy,
            volume_energy=volume_energy,
            exhaustion_vs_continuation=exhaustion_continuation,
            metabolic_load=metabolic_load,
        )
        
        # Convert to sentiment signal
        confidence = self._calculate_confidence(trend_energy, volume_energy)
        
        sentiment_signal = SentimentSignal(
            value=exhaustion_continuation,
            confidence=confidence,
            weight=1.0,
            driver="energy",
        )
        
        return energy_signals, sentiment_signal
    
    def _calculate_trend_energy(self, df: pl.DataFrame) -> TrendEnergySignals:
        """Calculate trend momentum energy."""
        closes = df["close"].to_numpy()
        
        # Momentum calculation
        returns = np.diff(closes) / closes[:-1]
        momentum_energy = np.sum(np.abs(returns[-self.momentum_window:])) * 100
        
        # Trend coherence (consistency of direction)
        directional_moves = returns[-self.coherence_window:]
        positive_moves = np.sum(directional_moves > 0)
        coherence = abs(positive_moves / len(directional_moves) - 0.5) * 2.0  # [0, 1]
        
        # Exhaustion detection
        # High momentum with decreasing coherence = exhaustion
        if len(closes) >= self.momentum_window + 10:
            prev_momentum = np.sum(np.abs(returns[-self.momentum_window-10:-10])) * 100
            prev_coherence_moves = returns[-self.coherence_window-10:-10]
            prev_coherence = abs(np.sum(prev_coherence_moves > 0) / len(prev_coherence_moves) - 0.5) * 2.0
            
            exhaustion = momentum_energy > prev_momentum * 1.2 and coherence < prev_coherence * 0.8
            buildup = momentum_energy < prev_momentum * 0.8 and coherence > prev_coherence * 1.2
        else:
            exhaustion = False
            buildup = False
        
        return TrendEnergySignals(
            momentum_energy=float(momentum_energy),
            trend_coherence=float(coherence),
            exhaustion_detected=bool(exhaustion),
            buildup_detected=bool(buildup),
        )
    
    def _calculate_volume_energy(self, df: pl.DataFrame) -> VolumeEnergySignals:
        """Calculate volume-energy correlation."""
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        
        # Price returns
        returns = np.abs(np.diff(closes) / closes[:-1])
        
        # Volume trend
        vol_recent = volumes[-self.momentum_window:]
        
        # Correlation between volume and price movement
        if len(returns) >= self.momentum_window and len(vol_recent) >= self.momentum_window:
            # Align arrays - use same length for both
            ret_aligned = returns[-self.momentum_window:]
            vol_aligned = vol_recent[-self.momentum_window:]
            # Ensure same length
            min_len = min(len(ret_aligned), len(vol_aligned))
            if min_len > 1:
                correlation = np.corrcoef(ret_aligned[-min_len:], vol_aligned[-min_len:])[0, 1]
                correlation = 0.0 if np.isnan(correlation) else correlation
            else:
                correlation = 0.0
        else:
            correlation = 0.0
        
        # Energy per volume (efficiency)
        total_return = np.sum(returns[-self.momentum_window:])
        total_volume = np.sum(vol_recent)
        energy_per_volume = total_return / (total_volume + 1e-9)
        
        # Volume confirmation (high volume with price movement)
        avg_volume = np.mean(volumes)
        recent_volume = np.mean(vol_recent)
        volume_confirmation = recent_volume > avg_volume * 1.1
        
        return VolumeEnergySignals(
            volume_trend_correlation=float(np.clip(correlation, -1.0, 1.0)),
            energy_per_volume=float(energy_per_volume),
            volume_confirmation=bool(volume_confirmation),
        )
    
    def _calculate_exhaustion_continuation(
        self, df: pl.DataFrame, trend: TrendEnergySignals, volume: VolumeEnergySignals
    ) -> float:
        """Calculate exhaustion vs continuation score [-1, 1]."""
        # -1 = exhausted, +1 = building/continuing
        
        score = 0.0
        
        # Exhaustion signals
        if trend.exhaustion_detected:
            score -= 0.4
        
        # Buildup signals
        if trend.buildup_detected:
            score += 0.4
        
        # Low coherence = exhaustion
        if trend.trend_coherence < 0.3:
            score -= 0.2
        
        # High coherence = continuation
        if trend.trend_coherence > 0.7:
            score += 0.2
        
        # Volume confirmation
        if volume.volume_confirmation:
            score += 0.2
        elif not volume.volume_confirmation and trend.momentum_energy > 1.0:
            # High momentum without volume = exhaustion warning
            score -= 0.2
        
        return float(np.clip(score, -1.0, 1.0))
    
    def _calculate_metabolic_load(self, df: pl.DataFrame) -> float:
        """Calculate overall market energy expenditure."""
        closes = df["close"].to_numpy()
        volumes = df["volume"].to_numpy()
        
        # Combine price volatility and volume
        returns = np.diff(closes) / closes[:-1]
        volatility = np.std(returns[-self.momentum_window:])
        avg_volume = np.mean(volumes[-self.momentum_window:])
        
        # Metabolic load = volatility * volume (normalized)
        baseline_vol = np.std(returns) if len(returns) > self.momentum_window else volatility
        baseline_volume = np.mean(volumes) if len(volumes) > self.momentum_window else avg_volume
        
        load = (volatility / (baseline_vol + 1e-9)) * (avg_volume / (baseline_volume + 1e-9))
        
        return float(max(0.0, load))
    
    def _calculate_confidence(
        self, trend: TrendEnergySignals, volume: VolumeEnergySignals
    ) -> float:
        """Calculate confidence in energy signals."""
        confidence = 0.5
        
        # High coherence increases confidence
        confidence += trend.trend_coherence * 0.3
        
        # Volume confirmation increases confidence
        if volume.volume_confirmation:
            confidence += 0.2
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def _default_output(self) -> tuple[MarketEnergySignals, SentimentSignal]:
        """Return default output when insufficient data."""
        trend = TrendEnergySignals(
            momentum_energy=0.0,
            trend_coherence=0.0,
            exhaustion_detected=False,
            buildup_detected=False,
        )
        volume = VolumeEnergySignals(
            volume_trend_correlation=0.0,
            energy_per_volume=0.0,
            volume_confirmation=False,
        )
        energy = MarketEnergySignals(
            trend_energy=trend,
            volume_energy=volume,
            exhaustion_vs_continuation=0.0,
            metabolic_load=0.0,
        )
        signal = SentimentSignal(value=0.0, confidence=0.0, weight=1.0, driver="energy")
        
        return energy, signal
