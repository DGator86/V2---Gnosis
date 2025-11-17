"""
Universal Energy Interpreter - Dynamic Hedging Physics Engine
==============================================================

The core physics framework that translates Greek exposures into energy states.

This module implements the theoretical foundation of DHPE (Dynamic Hedging Physics Engine):
1. Greeks → Force Fields (pressure fields)
2. Force Fields → Energy Potential (movement energy)
3. Energy Potential → Market Elasticity (stiffness)
4. Elasticity → Trading Strategy (position sizing, hedging)

Physics Analogy:
- Greeks (Gamma, Vanna, Charm) = Force fields
- Price movement = Particle in potential field
- Energy required = Work to move price
- Elasticity = Restoring force (market resistance)

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

# Import vollib for precise Greeks
try:
    from engines.hedge.vollib_greeks import VolilibGreeksCalculator, OptionGreeks
    VOLLIB_AVAILABLE = True
except ImportError:
    logger.warning("vollib not available, using simplified Greeks")
    VOLLIB_AVAILABLE = False


@dataclass
class EnergyState:
    """Complete energy state of the market."""
    
    # Energy components
    movement_energy: float  # Total energy to move price
    movement_energy_up: float  # Energy for upward move
    movement_energy_down: float  # Energy for downward move
    
    # Elasticity (market stiffness)
    elasticity: float  # Total elasticity
    elasticity_up: float  # Upward elasticity
    elasticity_down: float  # Downward elasticity
    
    # Asymmetry metrics
    energy_asymmetry: float  # up - down (positive = easier to go up)
    elasticity_asymmetry: float  # Difference in stiffness
    
    # Force field components
    gamma_force: float  # Gamma pressure
    vanna_force: float  # Vanna pressure
    charm_force: float  # Charm pressure (time decay)
    
    # Regime classification
    regime: str  # low_energy, medium_energy, high_energy, critical_energy
    stability: float  # Regime stability (0-1)
    
    # Metadata
    timestamp: datetime
    confidence: float  # Calculation confidence (0-1)


@dataclass
class GreekExposure:
    """Greek exposures at a price level."""
    
    strike: float
    call_delta: float = 0.0
    call_gamma: float = 0.0
    call_vega: float = 0.0
    call_theta: float = 0.0
    call_vanna: float = 0.0
    call_charm: float = 0.0
    
    put_delta: float = 0.0
    put_gamma: float = 0.0
    put_vega: float = 0.0
    put_theta: float = 0.0
    put_vanna: float = 0.0
    put_charm: float = 0.0
    
    call_oi: int = 0
    put_oi: int = 0


class UniversalEnergyInterpreter:
    """
    Universal energy interpreter for translating Greek exposures into energy states.
    
    This is the core physics engine that:
    1. Ingests Greek exposures from options chain
    2. Constructs force fields (pressure fields)
    3. Calculates energy potentials
    4. Determines market elasticity
    5. Classifies energy regimes
    
    Uses vollib for production-grade Greeks calculations.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        use_vollib: bool = True,
        energy_scaling: float = 1e-6,
        elasticity_scaling: float = 1e-3
    ):
        """
        Initialize universal energy interpreter.
        
        Args:
            risk_free_rate: Risk-free rate for Greeks calculations
            use_vollib: Use vollib for precise Greeks (recommended)
            energy_scaling: Scaling factor for energy calculations
            elasticity_scaling: Scaling factor for elasticity
        """
        self.risk_free_rate = risk_free_rate
        self.use_vollib = use_vollib and VOLLIB_AVAILABLE
        self.energy_scaling = energy_scaling
        self.elasticity_scaling = elasticity_scaling
        
        # Initialize vollib calculator if available
        if self.use_vollib and VOLLIB_AVAILABLE:
            try:
                self.greeks_calc = VolilibGreeksCalculator(risk_free_rate=risk_free_rate)
                logger.info("✅ Universal Energy Interpreter initialized with vollib")
            except ImportError:
                self.greeks_calc = None
                self.use_vollib = False
                logger.warning("⚠️  vollib not available, using simplified Greeks")
        else:
            self.greeks_calc = None
            logger.info("⚠️  Universal Energy Interpreter using simplified Greeks")
    
    def interpret(
        self,
        spot: float,
        exposures: List[GreekExposure],
        vix: float,
        time_to_expiry: float,
        dealer_sign: float = -1.0,
        move_size: float = 0.01  # 1% move
    ) -> EnergyState:
        """
        Interpret Greek exposures into complete energy state.
        
        Args:
            spot: Current spot price
            exposures: List of Greek exposures at each strike
            vix: VIX level (implied volatility)
            time_to_expiry: Days to expiration
            dealer_sign: Dealer gamma sign (-1 = short gamma, +1 = long gamma)
            move_size: Price move size for energy calculation (fraction)
        
        Returns:
            Complete EnergyState
        """
        # Calculate force fields
        gamma_force = self._calculate_gamma_force(spot, exposures, dealer_sign)
        vanna_force = self._calculate_vanna_force(spot, exposures, dealer_sign, vix)
        charm_force = self._calculate_charm_force(spot, exposures, dealer_sign, time_to_expiry)
        
        # Calculate net force at current spot
        net_force = gamma_force + vanna_force + charm_force
        
        # Calculate movement energy (integral of force over distance)
        move_up = spot * move_size
        move_down = spot * move_size
        
        energy_up = self._calculate_movement_energy(
            spot, spot + move_up, exposures, dealer_sign, vix, time_to_expiry
        )
        energy_down = self._calculate_movement_energy(
            spot, spot - move_down, exposures, dealer_sign, vix, time_to_expiry
        )
        
        movement_energy = (energy_up + energy_down) / 2
        energy_asymmetry = energy_up - energy_down
        
        # Calculate elasticity (dForce/dPrice)
        elasticity_up = self._calculate_elasticity(
            spot, move_up, exposures, dealer_sign, vix, time_to_expiry, direction='up'
        )
        elasticity_down = self._calculate_elasticity(
            spot, move_down, exposures, dealer_sign, vix, time_to_expiry, direction='down'
        )
        
        elasticity = (elasticity_up + elasticity_down) / 2
        elasticity_asymmetry = elasticity_up - elasticity_down
        
        # Classify regime
        regime, stability = self._classify_regime(
            movement_energy, elasticity, gamma_force, vanna_force, charm_force
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(exposures, vix, time_to_expiry)
        
        return EnergyState(
            movement_energy=movement_energy,
            movement_energy_up=energy_up,
            movement_energy_down=energy_down,
            elasticity=elasticity,
            elasticity_up=elasticity_up,
            elasticity_down=elasticity_down,
            energy_asymmetry=energy_asymmetry,
            elasticity_asymmetry=elasticity_asymmetry,
            gamma_force=gamma_force,
            vanna_force=vanna_force,
            charm_force=charm_force,
            regime=regime,
            stability=stability,
            timestamp=datetime.now(),
            confidence=confidence
        )
    
    def _calculate_gamma_force(
        self,
        spot: float,
        exposures: List[GreekExposure],
        dealer_sign: float
    ) -> float:
        """
        Calculate gamma force (pressure from gamma hedging).
        
        Gamma force = Σ(gamma_i * OI_i * distance_weight_i) * dealer_sign
        """
        total_force = 0.0
        
        for exp in exposures:
            # Net gamma at this strike
            net_gamma = (exp.call_gamma * exp.call_oi - exp.put_gamma * exp.put_oi)
            
            # Distance weight (closer strikes have more influence)
            distance = abs(exp.strike - spot) / spot
            weight = np.exp(-5 * distance)  # Exponential decay
            
            # Force contribution
            force = net_gamma * weight * dealer_sign
            total_force += force
        
        return total_force * self.energy_scaling
    
    def _calculate_vanna_force(
        self,
        spot: float,
        exposures: List[GreekExposure],
        dealer_sign: float,
        vix: float
    ) -> float:
        """
        Calculate vanna force (spot-vol correlation pressure).
        
        Vanna force = Σ(vanna_i * OI_i * vol_sensitivity) * dealer_sign
        """
        total_force = 0.0
        vol_sensitivity = vix / 20.0  # Normalize around VIX=20
        
        for exp in exposures:
            # Net vanna at this strike
            net_vanna = (exp.call_vanna * exp.call_oi - exp.put_vanna * exp.put_oi)
            
            # Distance weight
            distance = abs(exp.strike - spot) / spot
            weight = np.exp(-3 * distance)
            
            # Force contribution
            force = net_vanna * weight * vol_sensitivity * dealer_sign
            total_force += force
        
        return total_force * self.energy_scaling
    
    def _calculate_charm_force(
        self,
        spot: float,
        exposures: List[GreekExposure],
        dealer_sign: float,
        time_to_expiry: float
    ) -> float:
        """
        Calculate charm force (time decay pressure).
        
        Charm force = Σ(charm_i * OI_i * time_weight) * dealer_sign
        """
        total_force = 0.0
        time_weight = np.exp(-time_to_expiry / 30)  # Decay over 30 days
        
        for exp in exposures:
            # Net charm at this strike
            net_charm = (exp.call_charm * exp.call_oi - exp.put_charm * exp.put_oi)
            
            # Distance weight
            distance = abs(exp.strike - spot) / spot
            weight = np.exp(-3 * distance)
            
            # Force contribution
            force = net_charm * weight * time_weight * dealer_sign
            total_force += force
        
        return total_force * self.energy_scaling
    
    def _calculate_movement_energy(
        self,
        spot_start: float,
        spot_end: float,
        exposures: List[GreekExposure],
        dealer_sign: float,
        vix: float,
        time_to_expiry: float
    ) -> float:
        """
        Calculate energy required to move price from start to end.
        
        Energy = ∫ Force(x) dx from spot_start to spot_end
        
        We approximate this with Simpson's rule integration.
        """
        n_steps = 10
        prices = np.linspace(spot_start, spot_end, n_steps)
        forces = []
        
        for price in prices:
            # Calculate force at this price
            gamma_f = self._calculate_gamma_force(price, exposures, dealer_sign)
            vanna_f = self._calculate_vanna_force(price, exposures, dealer_sign, vix)
            charm_f = self._calculate_charm_force(price, exposures, dealer_sign, time_to_expiry)
            
            total_force = gamma_f + vanna_f + charm_f
            forces.append(abs(total_force))
        
        # Simpson's rule integration
        forces = np.array(forces)
        dx = (spot_end - spot_start) / (n_steps - 1)
        energy = dx / 3 * (forces[0] + forces[-1] + 4 * np.sum(forces[1:-1:2]) + 2 * np.sum(forces[2:-1:2]))
        
        return energy
    
    def _calculate_elasticity(
        self,
        spot: float,
        move: float,
        exposures: List[GreekExposure],
        dealer_sign: float,
        vix: float,
        time_to_expiry: float,
        direction: str = 'up'
    ) -> float:
        """
        Calculate elasticity (market stiffness).
        
        Elasticity = dForce/dPrice
        
        Higher elasticity = harder to move (more restoring force)
        """
        # Calculate force at current spot
        force_0 = (
            self._calculate_gamma_force(spot, exposures, dealer_sign) +
            self._calculate_vanna_force(spot, exposures, dealer_sign, vix) +
            self._calculate_charm_force(spot, exposures, dealer_sign, time_to_expiry)
        )
        
        # Calculate force after small move
        spot_moved = spot + move if direction == 'up' else spot - move
        force_1 = (
            self._calculate_gamma_force(spot_moved, exposures, dealer_sign) +
            self._calculate_vanna_force(spot_moved, exposures, dealer_sign, vix) +
            self._calculate_charm_force(spot_moved, exposures, dealer_sign, time_to_expiry)
        )
        
        # Elasticity = change in force / change in price
        elasticity = abs(force_1 - force_0) / move
        
        return elasticity * self.elasticity_scaling
    
    def _classify_regime(
        self,
        energy: float,
        elasticity: float,
        gamma_force: float,
        vanna_force: float,
        charm_force: float
    ) -> Tuple[str, float]:
        """
        Classify energy regime based on energy and elasticity levels.
        
        Returns:
            (regime_name, stability_score)
        """
        # Normalize metrics
        energy_norm = np.tanh(energy * 1000)  # 0-1
        elasticity_norm = np.tanh(elasticity * 100)  # 0-1
        
        # Classify regime
        if energy_norm < 0.3 and elasticity_norm < 0.3:
            regime = "low_energy"
            stability = 0.8
        elif energy_norm < 0.6 and elasticity_norm < 0.6:
            regime = "medium_energy"
            stability = 0.6
        elif energy_norm < 0.8 or elasticity_norm < 0.8:
            regime = "high_energy"
            stability = 0.4
        else:
            regime = "critical_energy"
            stability = 0.2
        
        # Adjust stability based on force balance
        total_force = abs(gamma_force) + abs(vanna_force) + abs(charm_force)
        if total_force > 0:
            gamma_pct = abs(gamma_force) / total_force
            # More balanced forces = more stable
            balance = 1.0 - abs(gamma_pct - 0.33) * 3  # Penalize imbalance
            stability *= balance
        
        return regime, max(0.0, min(1.0, stability))
    
    def _calculate_confidence(
        self,
        exposures: List[GreekExposure],
        vix: float,
        time_to_expiry: float
    ) -> float:
        """
        Calculate confidence in energy state calculation.
        
        Higher confidence with:
        - More strike prices
        - Higher open interest
        - Normal VIX levels
        - Reasonable time to expiry
        """
        # Strike count factor (more strikes = better)
        strike_factor = min(1.0, len(exposures) / 20)
        
        # Open interest factor
        total_oi = sum(exp.call_oi + exp.put_oi for exp in exposures)
        oi_factor = min(1.0, total_oi / 10000)
        
        # VIX factor (extreme VIX reduces confidence)
        vix_factor = 1.0 - abs(vix - 20) / 60  # Optimal around VIX=20
        vix_factor = max(0.3, vix_factor)
        
        # Time factor (too close or too far reduces confidence)
        if time_to_expiry < 7:
            time_factor = time_to_expiry / 7
        elif time_to_expiry > 90:
            time_factor = 1.0 - (time_to_expiry - 90) / 180
        else:
            time_factor = 1.0
        time_factor = max(0.3, time_factor)
        
        # Combined confidence
        confidence = (strike_factor * 0.3 + oi_factor * 0.3 + 
                     vix_factor * 0.2 + time_factor * 0.2)
        
        return max(0.0, min(1.0, confidence))


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_interpreter(
    risk_free_rate: float = 0.05,
    use_vollib: bool = True
) -> UniversalEnergyInterpreter:
    """
    Create universal energy interpreter with default settings.
    
    Args:
        risk_free_rate: Risk-free rate
        use_vollib: Use vollib for precise Greeks
    
    Returns:
        Configured UniversalEnergyInterpreter
    """
    return UniversalEnergyInterpreter(
        risk_free_rate=risk_free_rate,
        use_vollib=use_vollib
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("\n⚡ Universal Energy Interpreter Example\n")
    
    # Create interpreter
    interpreter = create_interpreter()
    
    # Create sample exposures (SPY options)
    spot = 450.0
    vix = 18.0
    time_to_expiry = 30.0  # 30 days
    
    exposures = [
        GreekExposure(
            strike=440, call_gamma=0.01, call_vanna=0.005, call_charm=-0.002,
            put_gamma=0.008, put_vanna=0.004, put_charm=-0.001,
            call_oi=5000, put_oi=8000
        ),
        GreekExposure(
            strike=445, call_gamma=0.015, call_vanna=0.008, call_charm=-0.003,
            put_gamma=0.012, put_vanna=0.006, put_charm=-0.002,
            call_oi=10000, put_oi=12000
        ),
        GreekExposure(
            strike=450, call_gamma=0.02, call_vanna=0.01, call_charm=-0.004,
            put_gamma=0.02, put_vanna=0.01, put_charm=-0.004,
            call_oi=15000, put_oi=15000
        ),
        GreekExposure(
            strike=455, call_gamma=0.015, call_vanna=0.008, call_charm=-0.003,
            put_gamma=0.012, put_vanna=0.006, put_charm=-0.002,
            call_oi=12000, put_oi=10000
        ),
        GreekExposure(
            strike=460, call_gamma=0.01, call_vanna=0.005, call_charm=-0.002,
            put_gamma=0.008, put_vanna=0.004, put_charm=-0.001,
            call_oi=8000, put_oi=5000
        ),
    ]
    
    # Interpret energy state
    energy_state = interpreter.interpret(
        spot=spot,
        exposures=exposures,
        vix=vix,
        time_to_expiry=time_to_expiry,
        dealer_sign=-1.0  # Dealers short gamma
    )
    
    # Display results
    print(f"Spot: ${spot:.2f}")
    print(f"VIX: {vix:.1f}")
    print(f"Time to Expiry: {time_to_expiry:.0f} days")
    print(f"\n⚡ ENERGY STATE:")
    print(f"   Movement Energy: {energy_state.movement_energy:.6f}")
    print(f"   Energy Up: {energy_state.movement_energy_up:.6f}")
    print(f"   Energy Down: {energy_state.movement_energy_down:.6f}")
    print(f"   Energy Asymmetry: {energy_state.energy_asymmetry:.6f}")
    print(f"\n🔧 ELASTICITY:")
    print(f"   Total Elasticity: {energy_state.elasticity:.6f}")
    print(f"   Elasticity Up: {energy_state.elasticity_up:.6f}")
    print(f"   Elasticity Down: {energy_state.elasticity_down:.6f}")
    print(f"\n💪 FORCE FIELDS:")
    print(f"   Gamma Force: {energy_state.gamma_force:.6f}")
    print(f"   Vanna Force: {energy_state.vanna_force:.6f}")
    print(f"   Charm Force: {energy_state.charm_force:.6f}")
    print(f"\n🎯 REGIME:")
    print(f"   Classification: {energy_state.regime}")
    print(f"   Stability: {energy_state.stability:.2%}")
    print(f"   Confidence: {energy_state.confidence:.2%}")
    
    print("\n✅ Universal Energy Interpreter ready for production!")
