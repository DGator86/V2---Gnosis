from __future__ import annotations

"""
Hedge Engine v3.0 - Full Production Implementation.

This orchestrates all hedge processors to transform raw option-market
microstructure into a physics-style pressure field describing the energy
required to move price.

Architecture:
    Raw Inputs → Processors → Outputs
    
Processors:
    1. Dealer Sign Estimator
    2. Gamma Field Constructor
    3. Vanna Field Constructor
    4. Charm Field Constructor
    5. Elasticity Calculator (CORE THEORY)
    6. Movement Energy Calculator
    7. Regime Detector
    8. MTF Fusion Engine
"""

from datetime import datetime
from typing import Any, Dict, Optional

import polars as pl

from engines.base import Engine
from engines.hedge.models import GreekInputs, HedgeEngineOutput
from engines.hedge.processors import (
    build_charm_field,
    build_gamma_field,
    build_vanna_field,
    calculate_elasticity,
    calculate_movement_energy,
    detect_regime,
    estimate_dealer_sign,
    fuse_multi_timeframe,
)
from engines.inputs.options_chain_adapter import OptionsChainAdapter
from schemas.core_schemas import EngineOutput


class HedgeEngineV3(Engine):
    """
    Dealer hedge pressure engine with full Greek field analysis.
    
    Produces:
    - Pressure fields (up/down/net)
    - Elasticity (market stiffness)
    - Movement energy (cost to move price)
    - Multi-dimensional regime classification
    - MTF-fused outputs
    """

    def __init__(
        self,
        adapter: OptionsChainAdapter,
        config: Dict[str, Any],
        liquidity_adapter: Optional[Any] = None,
    ) -> None:
        """
        Initialize hedge engine with adapters and configuration.
        
        Args:
            adapter: Options chain data adapter
            config: Engine configuration parameters
            liquidity_adapter: Optional liquidity engine adapter for friction
        """
        self.adapter = adapter
        self.config = config
        self.liquidity_adapter = liquidity_adapter

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        """
        Execute full hedge engine pipeline.
        
        Args:
            symbol: Ticker symbol
            now: Current timestamp
            
        Returns:
            EngineOutput with complete hedge analysis
        """
        # ============================================================
        # FETCH RAW DATA
        # ============================================================
        chain = self.adapter.fetch_chain(symbol, now)
        
        # Degraded mode: no data
        if chain.is_empty():
            return self._degraded_output(symbol, now, "no_data")
        
        # Extract spot price
        if "underlying_price" not in chain.columns:
            return self._degraded_output(symbol, now, "missing_underlying_price")
        
        spot = float(chain["underlying_price"][0])
        
        # Extract VIX if available (for vol regime detection)
        vix = None
        if "vix" in chain.columns:
            vix = float(chain["vix"][0])
        
        # Extract vol-of-vol if available
        vol_of_vol = 0.0
        if "vol_of_vol" in chain.columns:
            vol_of_vol = float(chain["vol_of_vol"][0])
        
        # Get liquidity lambda (Amihud) if available
        liquidity_lambda = 0.0
        if self.liquidity_adapter:
            try:
                liquidity_data = self.liquidity_adapter.fetch_liquidity(symbol, now)
                liquidity_lambda = liquidity_data.get("amihud_lambda", 0.0)
            except Exception:
                pass
        
        # Build Greek inputs
        greek_inputs = GreekInputs(
            chain=chain,
            spot=spot,
            vix=vix,
            vol_of_vol=vol_of_vol,
            liquidity_lambda=liquidity_lambda,
            timestamp=now.timestamp(),
        )
        
        # ============================================================
        # RUN PROCESSOR PIPELINE
        # ============================================================
        try:
            hedge_output = self._run_processors(greek_inputs)
        except Exception as e:
            return self._degraded_output(symbol, now, f"processor_error: {str(e)}")
        
        # ============================================================
        # CONVERT TO STANDARD ENGINE OUTPUT
        # ============================================================
        features = {
            # Primary outputs
            "pressure_up": hedge_output.pressure_up,
            "pressure_down": hedge_output.pressure_down,
            "net_pressure": hedge_output.net_pressure,
            "elasticity": hedge_output.elasticity,
            "movement_energy": hedge_output.movement_energy,
            
            # Detailed breakdowns
            "elasticity_up": hedge_output.elasticity_up,
            "elasticity_down": hedge_output.elasticity_down,
            "movement_energy_up": hedge_output.movement_energy_up,
            "movement_energy_down": hedge_output.movement_energy_down,
            "energy_asymmetry": hedge_output.energy_asymmetry,
            
            # Greek components
            "gamma_pressure": hedge_output.gamma_pressure,
            "vanna_pressure": hedge_output.vanna_pressure,
            "charm_pressure": hedge_output.charm_pressure,
            "dealer_gamma_sign": hedge_output.dealer_gamma_sign,
            
            # Cross-asset
            "cross_asset_correlation": hedge_output.cross_asset_correlation,
        }
        
        metadata = {
            "potential_shape": hedge_output.potential_shape,
            "gamma_regime": hedge_output.gamma_regime,
            "vanna_regime": hedge_output.vanna_regime,
            "charm_regime": hedge_output.charm_regime,
            "jump_risk_regime": hedge_output.jump_risk_regime,
            "regime_stability": str(hedge_output.regime_stability),
        }
        
        # Add MTF weights if available
        if hedge_output.mtf_weights:
            metadata["mtf_weights"] = str(hedge_output.mtf_weights)
        
        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=now,
            features=features,
            confidence=hedge_output.confidence,
            regime=hedge_output.primary_regime,
            metadata=metadata,
        )
    
    def _run_processors(self, inputs: GreekInputs) -> HedgeEngineOutput:
        """
        Run the full processor pipeline.
        
        Pipeline:
            1. Dealer Sign Estimation
            2. Gamma Field Construction
            3. Vanna Field Construction
            4. Charm Field Construction
            5. Elasticity Calculation (CORE)
            6. Movement Energy Calculation
            7. Regime Detection
            8. (Optional) MTF Fusion
        
        Args:
            inputs: Greek inputs
            
        Returns:
            HedgeEngineOutput with all components
        """
        # ============================================================
        # PROCESSOR 1: DEALER SIGN
        # ============================================================
        dealer_sign = estimate_dealer_sign(inputs, self.config)
        
        # ============================================================
        # PROCESSOR 2: GAMMA FIELD
        # ============================================================
        gamma_field = build_gamma_field(inputs, dealer_sign, self.config)
        
        # ============================================================
        # PROCESSOR 3: VANNA FIELD
        # ============================================================
        vanna_field = build_vanna_field(inputs, dealer_sign, self.config)
        
        # ============================================================
        # PROCESSOR 4: CHARM FIELD
        # ============================================================
        charm_field = build_charm_field(inputs, dealer_sign, self.config)
        
        # ============================================================
        # PROCESSOR 5: ELASTICITY (CORE THEORY)
        # ============================================================
        elasticity = calculate_elasticity(
            inputs,
            gamma_field,
            vanna_field,
            charm_field,
            self.config,
        )
        
        # ============================================================
        # PROCESSOR 6: MOVEMENT ENERGY
        # ============================================================
        energy = calculate_movement_energy(
            gamma_field,
            vanna_field,
            charm_field,
            elasticity,
            self.config,
        )
        
        # ============================================================
        # PROCESSOR 7: REGIME DETECTION
        # ============================================================
        regime = detect_regime(
            inputs,
            gamma_field,
            vanna_field,
            charm_field,
            elasticity,
            energy,
            self.config,
        )
        
        # ============================================================
        # BUILD HEDGE ENGINE OUTPUT
        # ============================================================
        return HedgeEngineOutput(
            # Primary outputs
            pressure_up=gamma_field.gamma_pressure_up + vanna_field.vanna_pressure_up,
            pressure_down=gamma_field.gamma_pressure_down + vanna_field.vanna_pressure_down,
            net_pressure=(
                (gamma_field.gamma_pressure_up + vanna_field.vanna_pressure_up)
                - (gamma_field.gamma_pressure_down + vanna_field.vanna_pressure_down)
            ),
            elasticity=elasticity.elasticity,
            movement_energy=(energy.movement_energy_up + energy.movement_energy_down) / 2.0,
            
            # Detailed breakdowns
            elasticity_up=elasticity.elasticity_up,
            elasticity_down=elasticity.elasticity_down,
            movement_energy_up=energy.movement_energy_up,
            movement_energy_down=energy.movement_energy_down,
            energy_asymmetry=energy.energy_asymmetry,
            
            # Greek components
            gamma_pressure=gamma_field.gamma_exposure,
            vanna_pressure=vanna_field.vanna_exposure,
            charm_pressure=charm_field.charm_exposure,
            dealer_gamma_sign=dealer_sign.dealer_sign,
            
            # Regime classification
            primary_regime=regime.primary_regime,
            gamma_regime=regime.gamma_regime,
            vanna_regime=regime.vanna_regime,
            charm_regime=regime.charm_regime,
            jump_risk_regime=regime.jump_risk_regime,
            potential_shape=regime.potential_shape,
            
            # Confidence and quality
            confidence=min(dealer_sign.confidence, regime.regime_confidence),
            regime_stability=regime.regime_stability,
            
            # Cross-asset
            cross_asset_correlation=regime.cross_asset_correlation,
            mtf_weights={},  # Will be populated by MTF fusion if used
            
            # Metadata
            metadata={
                "acceleration_likelihood": energy.acceleration_likelihood,
                "barrier_strength": energy.barrier_strength,
            },
        )
    
    def _degraded_output(self, symbol: str, now: datetime, reason: str) -> EngineOutput:
        """Return degraded output when data is missing or processing fails."""
        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=now,
            features={
                "pressure_up": 0.0,
                "pressure_down": 0.0,
                "net_pressure": 0.0,
                "elasticity": 1.0,
                "movement_energy": 0.0,
            },
            confidence=0.0,
            regime="degraded",
            metadata={"degraded_reason": reason},
        )
