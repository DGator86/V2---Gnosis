"""
Sentiment Engine v1.0 - Complete Implementation

Multi-modal sentiment analysis combining:
- Wyckoff regime structure
- Oscillators (RSI, MFI, Stochastic)
- Volatility envelopes (Bollinger, Keltner)
- Order flow and dark pool bias
- Market breadth and risk regime
- Market energy and momentum

Outputs unified sentiment vector for Agent 3 (Sentiment Agent).
"""

from datetime import datetime
from typing import Dict, List, Optional

import polars as pl

from engines.inputs.market_data_adapter import MarketDataAdapter
from engines.sentiment.fusion import (
    apply_graceful_degradation,
    detect_conflicting_signals,
    fuse_signals,
)
from engines.sentiment.models import (
    SentimentEngineConfig,
    SentimentEnvelope,
    SentimentSignal,
)
from engines.sentiment.processors.all_processors import (
    BreadthRegimeProcessor,
    EnergyProcessor,
    FlowBiasProcessor,
    OscillatorProcessor,
    VolatilityProcessor,
    WyckoffProcessor,
)


class SentimentEngineV1:
    """
    Canonical Sentiment Engine v1.0.
    
    Orchestrates 6 processor categories to produce unified sentiment envelope.
    Pure interpretation - no forecasting, no ML.
    """
    
    def __init__(
        self,
        market_adapter: MarketDataAdapter,
        config: Optional[SentimentEngineConfig] = None,
    ):
        """
        Initialize Sentiment Engine with processors.
        
        Args:
            market_adapter: Source of OHLCV market data
            config: Engine configuration (uses defaults if None)
        """
        self.market_adapter = market_adapter
        self.config = config or SentimentEngineConfig()
        
        # Initialize all processors
        self.wyckoff_processor = WyckoffProcessor(
            config={
                "phase_detection_sensitivity": self.config.wyckoff.weight,
                "spring_utad_threshold": 0.02,
                "lookback_periods": self.config.wyckoff.lookback_periods,
            }
        )
        
        self.oscillator_processor = OscillatorProcessor(
            config={
                "rsi_period": self.config.oscillators.rsi_period,
                "mfi_period": self.config.oscillators.mfi_period,
                "stoch_k_period": self.config.oscillators.stoch_k_period,
                "stoch_d_period": self.config.oscillators.stoch_d_period,
                "overbought_threshold": self.config.oscillators.overbought_threshold,
                "oversold_threshold": self.config.oscillators.oversold_threshold,
            }
        )
        
        self.volatility_processor = VolatilityProcessor(
            config={
                "bb_period": self.config.volatility.bb_period,
                "bb_std_dev": self.config.volatility.bb_std_dev,
                "kc_period": self.config.volatility.kc_period,
                "kc_atr_mult": self.config.volatility.kc_atr_mult,
            }
        )
        
        self.flow_processor = FlowBiasProcessor(
            config={
                "orderflow_window": self.config.flow.orderflow_window,
                "darkpool_enabled": self.config.flow.darkpool_enabled,
            }
        )
        
        self.breadth_processor = BreadthRegimeProcessor(
            config={
                "ma_periods": self.config.breadth.ma_periods,
                "regime_window": self.config.breadth.regime_window,
            }
        )
        
        self.energy_processor = EnergyProcessor(
            config={
                "momentum_window": self.config.energy.momentum_window,
                "coherence_window": self.config.energy.coherence_window,
            }
        )
    
    def process(
        self,
        symbol: str,
        now: datetime,
        darkpool_data: Optional[Dict] = None,
        breadth_data: Optional[Dict] = None,
    ) -> SentimentEnvelope:
        """
        Process all sentiment signals and fuse into unified envelope.
        
        Args:
            symbol: Asset symbol to analyze
            now: Current timestamp
            darkpool_data: Optional dark pool data (DIX/GEX)
            breadth_data: Optional market breadth data (advances/declines)
        
        Returns:
            SentimentEnvelope with fused sentiment vector
        """
        # Fetch market data
        lookback = max(
            self.config.wyckoff.lookback_periods,
            self.config.oscillators.lookback_periods,
            self.config.volatility.lookback_periods,
            self.config.flow.lookback_periods,
            self.config.breadth.lookback_periods,
            self.config.energy.lookback_periods,
        ) + 10  # Extra buffer for calculations
        
        try:
            df = self.market_adapter.fetch_ohlcv(symbol, lookback, now)
        except Exception as e:
            # Graceful degradation - return neutral envelope
            return SentimentEnvelope(
                bias="neutral",
                strength=0.0,
                energy=0.0,
                confidence=0.0,
                drivers={"error": 0.0},
            )
        
        if df.is_empty():
            return SentimentEnvelope(
                bias="neutral",
                strength=0.0,
                energy=0.0,
                confidence=0.0,
                drivers={"no_data": 0.0},
            )
        
        # Process all sentiment signals
        signals: List[SentimentSignal] = []
        
        # Wyckoff analysis
        if self.config.wyckoff.enabled:
            try:
                wyckoff_signals, wyckoff_sentiment = self.wyckoff_processor.process(df)
                signals.append(wyckoff_sentiment)
            except Exception:
                pass  # Graceful degradation
        
        # Oscillator analysis
        if self.config.oscillators.enabled:
            try:
                osc_signals, osc_sentiment = self.oscillator_processor.process(df)
                signals.append(osc_sentiment)
            except Exception:
                pass
        
        # Volatility analysis
        if self.config.volatility.enabled:
            try:
                vol_signals, vol_sentiment = self.volatility_processor.process(df)
                signals.append(vol_sentiment)
            except Exception:
                pass
        
        # Flow bias analysis
        if self.config.flow.enabled:
            try:
                flow_signals, flow_sentiment = self.flow_processor.process(df, darkpool_data)
                signals.append(flow_sentiment)
            except Exception:
                pass
        
        # Breadth/regime analysis
        if self.config.breadth.enabled:
            try:
                breadth_signals, breadth_sentiment = self.breadth_processor.process(df, breadth_data)
                signals.append(breadth_sentiment)
            except Exception:
                pass
        
        # Energy analysis
        if self.config.energy.enabled:
            try:
                energy_signals, energy_sentiment = self.energy_processor.process(df)
                # Extract energy level for fusion
                energy_level = energy_signals.metabolic_load
                signals.append(energy_sentiment)
            except Exception:
                energy_level = 0.0
        else:
            energy_level = 0.0
        
        # Apply graceful degradation if needed
        signals = apply_graceful_degradation(signals, required_minimum=3)
        
        # Detect conflicts
        has_conflicts = detect_conflicting_signals(signals)
        
        # Determine regime for fusion (use breadth multi-period if available)
        regime = None
        if self.config.breadth.enabled:
            try:
                breadth_output, _ = self.breadth_processor.process(df, breadth_data)
                regime = breadth_output.multi_period_regime
            except Exception:
                pass
        
        # Fuse all signals
        envelope = fuse_signals(
            signals=signals,
            energy_level=energy_level,
            regime=regime,
            bias_threshold=self.config.bias_threshold,
        )
        
        # Add regime metadata
        if regime:
            envelope.liquidity_regime = regime
        
        # Add Wyckoff phase if available
        if self.config.wyckoff.enabled:
            try:
                wyckoff_output, _ = self.wyckoff_processor.process(df)
                envelope.wyckoff_phase = wyckoff_output.phase.phase
            except Exception:
                pass
        
        # Add volatility regime if available
        if self.config.volatility.enabled:
            try:
                vol_output, _ = self.volatility_processor.process(df)
                if vol_output.squeeze_detected:
                    envelope.volatility_regime = "squeeze"
                elif vol_output.keltner.expansion:
                    envelope.volatility_regime = "expansion"
                elif vol_output.keltner.compression:
                    envelope.volatility_regime = "compression"
                else:
                    envelope.volatility_regime = "normal"
            except Exception:
                pass
        
        # Add flow regime if available
        if self.config.flow.enabled:
            try:
                flow_output, _ = self.flow_processor.process(df, darkpool_data)
                if flow_output.composite_flow_bias > 0.3:
                    envelope.flow_regime = "bullish_flow"
                elif flow_output.composite_flow_bias < -0.3:
                    envelope.flow_regime = "bearish_flow"
                else:
                    envelope.flow_regime = "balanced_flow"
            except Exception:
                pass
        
        # Reduce confidence if conflicts detected
        if has_conflicts:
            envelope.confidence *= 0.7
        
        return envelope
    
    def get_detailed_analysis(
        self,
        symbol: str,
        now: datetime,
        darkpool_data: Optional[Dict] = None,
        breadth_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Get detailed breakdown of all processor outputs.
        
        Useful for debugging and deep analysis.
        
        Returns:
            Dict with all processor outputs plus final envelope
        """
        lookback = max(
            self.config.wyckoff.lookback_periods,
            self.config.oscillators.lookback_periods,
            self.config.volatility.lookback_periods,
        ) + 10
        
        try:
            df = self.market_adapter.fetch_ohlcv(symbol, lookback, now)
        except Exception:
            return {"error": "Failed to fetch data"}
        
        if df.is_empty():
            return {"error": "No data available"}
        
        results = {}
        
        # Process each component
        try:
            wyckoff_output, wyckoff_signal = self.wyckoff_processor.process(df)
            results["wyckoff"] = {
                "signals": wyckoff_output.model_dump(),
                "sentiment": wyckoff_signal.model_dump(),
            }
        except Exception as e:
            results["wyckoff"] = {"error": str(e)}

        try:
            osc_output, osc_signal = self.oscillator_processor.process(df)
            results["oscillators"] = {
                "signals": osc_output.model_dump(),
                "sentiment": osc_signal.model_dump(),
            }
        except Exception as e:
            results["oscillators"] = {"error": str(e)}

        try:
            vol_output, vol_signal = self.volatility_processor.process(df)
            results["volatility"] = {
                "signals": vol_output.model_dump(),
                "sentiment": vol_signal.model_dump(),
            }
        except Exception as e:
            results["volatility"] = {"error": str(e)}
        
        try:
            flow_output, flow_signal = self.flow_processor.process(df, darkpool_data)
            results["flow"] = {
                "signals": flow_output.model_dump(),
                "sentiment": flow_signal.model_dump(),
            }
        except Exception as e:
            results["flow"] = {"error": str(e)}
        
        try:
            breadth_output, breadth_signal = self.breadth_processor.process(df, breadth_data)
            results["breadth"] = {
                "signals": breadth_output.model_dump(),
                "sentiment": breadth_signal.model_dump(),
            }
        except Exception as e:
            results["breadth"] = {"error": str(e)}
        
        try:
            energy_output, energy_signal = self.energy_processor.process(df)
            results["energy"] = {
                "signals": energy_output.model_dump(),
                "sentiment": energy_signal.model_dump(),
            }
        except Exception as e:
            results["energy"] = {"error": str(e)}
        
        # Get final envelope
        envelope = self.process(symbol, now, darkpool_data, breadth_data)
        results["envelope"] = envelope.model_dump()
        
        return results
