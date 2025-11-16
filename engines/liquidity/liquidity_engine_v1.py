from __future__ import annotations

"""
Liquidity Engine v1.0 - Full Production Implementation.

Orchestrates 8 processors to transform raw market data into comprehensive
liquidity analysis covering:
- Volume dynamics
- Order flow
- Microstructure
- Impact costs
- Dark pool activity  
- Structural liquidity (HVN/LVN)
- Wyckoff phases
- Volatility-liquidity interaction
"""

from datetime import datetime
from typing import Any, Dict

import polars as pl

from engines.base import Engine
from engines.liquidity.models import *
from engines.liquidity.processors.all_processors import *
from engines.inputs.market_data_adapter import MarketDataAdapter
from schemas.core_schemas import EngineOutput


class LiquidityEngineV1(Engine):
    """
    Dealer liquidity and market microstructure engine.
    
    Produces:
    - Liquidity score and friction costs
    - Structural zones (absorption/displacement/voids)
    - Order flow imbalances
    - Impact metrics (Amihud, Kyle lambda)
    - Wyckoff phase classification
    - Compression/expansion energy
    """

    def __init__(
        self,
        adapter: MarketDataAdapter,
        config: Dict[str, Any],
    ) -> None:
        self.adapter = adapter
        self.config = config
        
        # Initialize processors
        self.volume_proc = VolumeProcessor(lookback=config.get("volume_lookback", 20))
        self.orderflow_proc = OrderFlowProcessor()
        self.micro_proc = MicrostructureProcessor()
        self.impact_proc = ImpactProcessor()
        self.darkpool_proc = DarkPoolProcessor()
        self.structure_proc = StructureProcessor()
        self.wyckoff_proc = WyckoffLiquidityProcessor()
        self.vol_liq_proc = VolatilityLiquidityProcessor(
            bb_period=config.get("bb_period", 20),
            kc_period=config.get("kc_period", 20)
        )

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        """
        Execute full liquidity engine pipeline.
        
        Args:
            symbol: Ticker symbol
            now: Current timestamp
            
        Returns:
            EngineOutput with complete liquidity analysis
        """
        # Fetch market data
        lookback = self.config.get("lookback_bars", 100)
        data = self.adapter.fetch_ohlcv(symbol, lookback, now)
        
        if data.is_empty():
            return self._degraded_output(symbol, now, "no_data")
        
        # Run all processors
        try:
            volume_result = self.volume_proc.process(data, self.config)
            orderflow_result = self.orderflow_proc.process(data, self.config)
            micro_result = self.micro_proc.process(data, self.config)
            impact_result = self.impact_proc.process(data, self.config)
            darkpool_result = self.darkpool_proc.process(data, self.config)
            structure_result = self.structure_proc.process(data, self.config)
            wyckoff_result = self.wyckoff_proc.process(data, self.config)
            vol_liq_result = self.vol_liq_proc.process(data, self.config)
        except Exception as e:
            return self._degraded_output(symbol, now, f"processor_error: {str(e)}")
        
        # Fuse results
        liquidity_output = self._fuse_results(
            volume_result,
            orderflow_result,
            micro_result,
            impact_result,
            darkpool_result,
            structure_result,
            wyckoff_result,
            vol_liq_result,
        )
        
        # Convert to standard EngineOutput
        return self._to_engine_output(symbol, now, liquidity_output)
    
    def _fuse_results(
        self,
        volume: VolumeProcessorResult,
        orderflow: OrderFlowProcessorResult,
        micro: MicrostructureProcessorResult,
        impact: ImpactProcessorResult,
        darkpool: DarkPoolProcessorResult,
        structure: StructureProcessorResult,
        wyckoff: WyckoffLiquidityProcessorResult,
        vol_liq: VolatilityLiquidityProcessorResult,
    ) -> LiquidityEngineOutput:
        """
        Fuse all processor results with regime-aware weighting.
        
        Fusion logic:
        - Low impact + high volume = high liquidity
        - High compression energy + low volume = potential breakout
        - Strong absorption zones = resistance to movement
        - High OFI + sweeps = directional pressure
        """
        
        # ============================================================
        # COMPOSITE LIQUIDITY SCORE
        # ============================================================
        # Factors:
        # - Low Amihud = more liquid
        # - High volume strength = more liquid
        # - Low spread cost = more liquid
        # - High structure confidence = more reliable
        
        amihud_score = 1.0 / (1.0 + impact.amihud * 1e6)  # Normalize
        volume_score = volume.volume_strength
        spread_score = 1.0 / (1.0 + micro.spread_cost * 100)
        structure_score = structure.confidence
        
        liquidity_score = (
            amihud_score * 0.3 +
            volume_score * 0.3 +
            spread_score * 0.2 +
            structure_score * 0.2
        )
        
        # ============================================================
        # FRICTION COST
        # ============================================================
        # Combines spread, impact, and slippage
        friction_cost = (
            micro.spread_cost +
            impact.slippage_per_1pct_move +
            impact.lambda_kyle * 1000
        )
        
        # ============================================================
        # REGIME CLASSIFICATION
        # ============================================================
        if liquidity_score > 0.8:
            regime = "Abundant"
        elif liquidity_score > 0.6:
            regime = "Normal"
        elif liquidity_score > 0.4:
            regime = "Thin"
        elif liquidity_score > 0.2:
            regime = "Stressed"
        else:
            regime = "Crisis"
        
        # Adjust regime based on additional factors
        if vol_liq.squeeze_flag and volume.exhaustion_flag:
            regime = "Stressed"  # Pre-breakout stress
        
        # ============================================================
        # PATH OF LEAST RESISTANCE (POLR)
        # ============================================================
        # Combines OFI, Wyckoff bias, and displacement zones
        
        polr_direction = (
            orderflow.ofi * 0.4 +
            wyckoff.absorption_vs_displacement_bias * 0.3 +
            micro.microprice_direction * 0.3
        )
        
        # POLR strength from conviction alignment
        alignment_score = abs(orderflow.ofi) * abs(wyckoff.absorption_vs_displacement_bias)
        polr_strength = min(1.0, alignment_score + orderflow.liquidity_taker_intensity * 0.5)
        
        # ============================================================
        # CONFIDENCE
        # ============================================================
        confidences = [
            volume.confidence,
            orderflow.confidence,
            micro.confidence,
            impact.confidence,
            structure.confidence,
            wyckoff.confidence,
            vol_liq.confidence,
        ]
        overall_confidence = float(np.mean(confidences))
        
        regime_confidence = overall_confidence * liquidity_score
        
        # ============================================================
        # BUILD OUTPUT
        # ============================================================
        return LiquidityEngineOutput(
            # Core metrics
            liquidity_score=liquidity_score,
            friction_cost=friction_cost,
            kyle_lambda=impact.lambda_kyle,
            amihud=impact.amihud,
            
            # Structure
            absorption_zones=structure.absorption_zones,
            displacement_zones=structure.displacement_zones,
            voids=structure.voids,
            hvn_lvn_structure=structure.profile_nodes,
            
            # Order flow
            orderbook_imbalance=orderflow.ofi,
            sweep_alerts=orderflow.sweep_flag,
            iceberg_alerts=orderflow.iceberg_flag,
            
            # Volatility-liquidity
            compression_energy=vol_liq.compression_energy,
            expansion_energy=vol_liq.expansion_energy,
            
            # Volume
            volume_strength=volume.volume_strength,
            buying_effort=volume.buying_effort,
            selling_effort=volume.selling_effort,
            
            # Dark pool
            off_exchange_ratio=darkpool.off_exchange_ratio,
            hidden_accumulation=darkpool.dp_accumulation,
            
            # Wyckoff
            wyckoff_phase=wyckoff.wyckoff_phase,
            wyckoff_energy=wyckoff.wyckoff_energy,
            
            # Regime
            liquidity_regime=regime,
            regime_confidence=regime_confidence,
            
            # POLR
            polr_direction=polr_direction,
            polr_strength=polr_strength,
            
            # Meta
            confidence=overall_confidence,
            metadata={
                "rvol": volume.rvol,
                "taker_intensity": orderflow.liquidity_taker_intensity,
                "impact_energy": impact.impact_energy,
                "squeeze_flag": float(vol_liq.squeeze_flag),
                "sos_detected": float(wyckoff.sos_detected),
                "sow_detected": float(wyckoff.sow_detected),
            },
        )
    
    def _to_engine_output(
        self,
        symbol: str,
        now: datetime,
        liq_output: LiquidityEngineOutput,
    ) -> EngineOutput:
        """Convert LiquidityEngineOutput to standard EngineOutput."""
        
        features = {
            # Core liquidity
            "liquidity_score": liq_output.liquidity_score,
            "friction_cost": liq_output.friction_cost,
            "amihud_illiquidity": liq_output.amihud,
            "kyle_lambda": liq_output.kyle_lambda,
            
            # Order flow
            "orderbook_imbalance": liq_output.orderbook_imbalance,
            "sweep_detected": float(liq_output.sweep_alerts),
            "iceberg_detected": float(liq_output.iceberg_alerts),
            
            # Volume
            "volume_strength": liq_output.volume_strength,
            "buying_effort": liq_output.buying_effort,
            "selling_effort": liq_output.selling_effort,
            
            # Structure counts
            "num_absorption_zones": float(len(liq_output.absorption_zones)),
            "num_displacement_zones": float(len(liq_output.displacement_zones)),
            "num_voids": float(len(liq_output.voids)),
            "num_hvn_nodes": float(len([n for n in liq_output.hvn_lvn_structure if n.node_type == "HVN"])),
            
            # Volatility-liquidity
            "compression_energy": liq_output.compression_energy,
            "expansion_energy": liq_output.expansion_energy,
            
            # Wyckoff
            "wyckoff_energy": liq_output.wyckoff_energy,
            
            # POLR
            "polr_direction": liq_output.polr_direction,
            "polr_strength": liq_output.polr_strength,
            
            # Dark pool
            "off_exchange_ratio": liq_output.off_exchange_ratio,
        }
        
        metadata = {
            "liquidity_regime": liq_output.liquidity_regime,
            "wyckoff_phase": liq_output.wyckoff_phase,
            "regime_confidence": str(liq_output.regime_confidence),
        }
        
        # Add processor metadata
        metadata.update({k: str(v) for k, v in liq_output.metadata.items()})
        
        return EngineOutput(
            kind="liquidity",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=liq_output.confidence,
            regime=liq_output.liquidity_regime,
            metadata=metadata,
        )
    
    def _degraded_output(self, symbol: str, now: datetime, reason: str) -> EngineOutput:
        """Return degraded output when data is missing or processing fails."""
        return EngineOutput(
            kind="liquidity",
            symbol=symbol,
            timestamp=now,
            features={
                "liquidity_score": 0.5,
                "friction_cost": 0.0,
                "amihud_illiquidity": 0.0,
                "kyle_lambda": 0.0,
            },
            confidence=0.0,
            regime="degraded",
            metadata={"degraded_reason": reason},
        )
