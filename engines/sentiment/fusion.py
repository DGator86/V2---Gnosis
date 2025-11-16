"""
Sentiment Engine v1.0 - Fusion Core

Multi-modal sentiment signal fusion with:
- Energy-aware dynamic weighting
- Graceful degradation
- Nonlinear confidence calculation
- Regime-based weight adjustment
"""

from typing import Dict, List, Literal, Optional

import numpy as np

from engines.sentiment.models import SentimentEnvelope, SentimentSignal


def fuse_signals(
    signals: List[SentimentSignal],
    energy_level: float = 0.0,
    regime: Optional[str] = None,
    bias_threshold: float = 0.15,
) -> SentimentEnvelope:
    """
    Fuse multiple sentiment signals into unified envelope.
    
    Args:
        signals: List of SentimentSignal from various processors
        energy_level: Market energy level for energy-aware weighting
        regime: Current market regime for regime-aware weighting
        bias_threshold: Threshold for neutral classification [0, 1]
    
    Returns:
        SentimentEnvelope with fused sentiment vector
    """
    if not signals:
        return _empty_envelope()
    
    # Apply regime-aware weighting
    weighted_signals = _apply_regime_weights(signals, regime, energy_level)
    
    # Apply energy-aware rescaling
    rescaled_signals = _apply_energy_rescaling(weighted_signals, energy_level)
    
    # Calculate weighted sentiment value
    total_weight = sum(s.weight * s.confidence for s in rescaled_signals)
    
    if total_weight == 0:
        return _empty_envelope()
    
    # Weighted fusion
    weighted_values = np.array([s.value * s.weight * s.confidence for s in rescaled_signals])
    combined_value = float(np.sum(weighted_values) / total_weight)
    
    # Determine bias
    bias = _determine_bias(combined_value, bias_threshold)
    
    # Calculate strength (conviction)
    strength = float(abs(combined_value))
    
    # Calculate meta-confidence
    confidence = _calculate_meta_confidence(rescaled_signals, combined_value)
    
    # Extract top drivers
    drivers = _extract_drivers(rescaled_signals)
    
    # Market energy (aggregate metabolic expenditure)
    energy = _calculate_aggregate_energy(rescaled_signals, energy_level)
    
    return SentimentEnvelope(
        bias=bias,
        strength=min(1.0, strength),
        energy=energy,
        confidence=confidence,
        drivers=drivers,
    )


def _apply_regime_weights(
    signals: List[SentimentSignal],
    regime: Optional[str],
    energy_level: float,
) -> List[SentimentSignal]:
    """
    Apply regime-aware weight adjustments.
    
    Weights vary by regime:
    - Trending regime: Boost Wyckoff, Energy processors
    - Mean-revert regime: Boost Oscillators, Volatility
    - High-energy regime: Reduce oscillator weight
    - Low-energy regime: Increase oscillator weight
    """
    adjusted = []
    
    for signal in signals:
        adjusted_weight = signal.weight
        
        # Regime-based adjustments
        if regime in ["bullish_consensus", "bearish_consensus", "risk_on", "risk_off"]:
            # Trending regime
            if signal.driver in ["wyckoff", "energy"]:
                adjusted_weight *= 1.3
            elif signal.driver == "oscillators":
                adjusted_weight *= 0.8
        
        elif regime in ["mixed", "neutral", "choppy"]:
            # Mean-reversion regime
            if signal.driver in ["oscillators", "volatility"]:
                adjusted_weight *= 1.3
            elif signal.driver == "wyckoff":
                adjusted_weight *= 0.8
        
        # Energy-based adjustments
        if energy_level > 1.5:
            # High energy market
            if signal.driver == "oscillators":
                adjusted_weight *= 0.7  # Oscillators less reliable in high energy
            elif signal.driver == "flow":
                adjusted_weight *= 1.2  # Flow more important
        
        elif energy_level < 0.5:
            # Low energy market
            if signal.driver == "oscillators":
                adjusted_weight *= 1.2  # Mean reversion more likely
            elif signal.driver == "energy":
                adjusted_weight *= 0.8
        
        # Create new signal with adjusted weight
        adjusted.append(
            SentimentSignal(
                value=signal.value,
                confidence=signal.confidence,
                weight=adjusted_weight,
                driver=signal.driver,
            )
        )
    
    return adjusted


def _apply_energy_rescaling(
    signals: List[SentimentSignal],
    energy_level: float,
) -> List[SentimentSignal]:
    """
    Apply energy-aware rescaling to prevent extreme swings.
    
    High energy = more volatile signals, apply damping
    Low energy = more stable signals, allow higher sensitivity
    """
    rescaled = []
    
    # Damping factor based on energy
    # High energy (>2.0) = apply 20% damping
    # Low energy (<0.5) = no damping
    damping = min(0.2, max(0.0, (energy_level - 0.5) / 7.5))
    
    for signal in signals:
        # Apply nonlinear damping to extreme values
        rescaled_value = signal.value
        
        if abs(signal.value) > 0.7:
            # Damp extreme values
            sign = np.sign(signal.value)
            magnitude = abs(signal.value)
            damped_magnitude = magnitude * (1.0 - damping)
            rescaled_value = sign * damped_magnitude
        
        rescaled.append(
            SentimentSignal(
                value=float(rescaled_value),
                confidence=signal.confidence,
                weight=signal.weight,
                driver=signal.driver,
            )
        )
    
    return rescaled


def _determine_bias(
    combined_value: float,
    threshold: float,
) -> Literal["bullish", "bearish", "neutral"]:
    """Determine sentiment bias based on combined value and threshold."""
    if combined_value > threshold:
        return "bullish"
    elif combined_value < -threshold:
        return "bearish"
    else:
        return "neutral"


def _calculate_meta_confidence(
    signals: List[SentimentSignal],
    combined_value: float,
) -> float:
    """
    Calculate meta-confidence based on:
    - Signal agreement/disagreement
    - Data completeness
    - Individual signal confidences
    """
    if not signals:
        return 0.0
    
    # Base confidence from individual signal confidences
    avg_confidence = float(np.mean([s.confidence for s in signals]))
    
    # Agreement factor
    # Check how many signals agree with the combined direction
    combined_direction = np.sign(combined_value)
    agreements = sum(1 for s in signals if np.sign(s.value) == combined_direction)
    agreement_ratio = agreements / len(signals)
    
    # Variance penalty (high variance = lower confidence)
    values = np.array([s.value for s in signals])
    variance = float(np.var(values))
    variance_penalty = min(0.3, variance * 0.5)
    
    # Completeness factor
    # Assume 6 processors total (wyckoff, oscillators, volatility, flow, breadth, energy)
    completeness = min(1.0, len(signals) / 6.0)
    
    # Combine factors
    meta_confidence = (
        avg_confidence * 0.4 +
        agreement_ratio * 0.3 +
        completeness * 0.2 +
        (1.0 - variance_penalty) * 0.1
    )
    
    return float(np.clip(meta_confidence, 0.0, 1.0))


def _extract_drivers(signals: List[SentimentSignal]) -> Dict[str, float]:
    """
    Extract top contributing drivers with their weighted values.
    
    Returns dict of {driver_name: weighted_contribution}
    """
    drivers = {}
    
    for signal in signals:
        # Weighted contribution = value * weight * confidence
        contribution = signal.value * signal.weight * signal.confidence
        drivers[signal.driver] = float(contribution)
    
    # Sort by absolute contribution
    sorted_drivers = dict(
        sorted(drivers.items(), key=lambda x: abs(x[1]), reverse=True)
    )
    
    return sorted_drivers


def _calculate_aggregate_energy(
    signals: List[SentimentSignal],
    energy_level: float,
) -> float:
    """
    Calculate aggregate market energy (metabolic expenditure).
    
    Combines:
    - Signal strength (absolute values)
    - Energy level from energy processor
    - Volatility implied by signal variance
    """
    if not signals:
        return 0.0
    
    # Average absolute signal strength
    avg_strength = float(np.mean([abs(s.value) for s in signals]))
    
    # Signal variance (volatility proxy)
    variance = float(np.var([s.value for s in signals]))
    
    # Aggregate energy
    aggregate = (
        avg_strength * 0.4 +
        energy_level * 0.4 +
        variance * 0.2
    )
    
    return float(max(0.0, aggregate))


def _empty_envelope() -> SentimentEnvelope:
    """Return neutral sentiment envelope when no signals available."""
    return SentimentEnvelope(
        bias="neutral",
        strength=0.0,
        energy=0.0,
        confidence=0.0,
        drivers={},
    )


def apply_graceful_degradation(
    signals: List[SentimentSignal],
    required_minimum: int = 3,
) -> List[SentimentSignal]:
    """
    Handle missing processors through graceful degradation.
    
    Redistributes weights when some processors unavailable.
    
    Args:
        signals: Available signals
        required_minimum: Minimum signals needed for reliable fusion
    
    Returns:
        Adjusted signals with redistributed weights
    """
    if len(signals) < required_minimum:
        # Boost confidence of available signals to compensate
        boost_factor = required_minimum / max(1, len(signals))
        
        return [
            SentimentSignal(
                value=s.value,
                confidence=min(1.0, s.confidence * boost_factor),
                weight=s.weight * boost_factor,
                driver=s.driver,
            )
            for s in signals
        ]
    
    return signals


def detect_conflicting_signals(
    signals: List[SentimentSignal],
    conflict_threshold: float = 0.7,
) -> bool:
    """
    Detect if signals are highly conflicting.
    
    Args:
        signals: List of sentiment signals
        conflict_threshold: Threshold for considering signals conflicting
    
    Returns:
        True if strong conflicts detected
    """
    if len(signals) < 2:
        return False
    
    # Check for strong opposing signals
    positive_signals = [s for s in signals if s.value > conflict_threshold]
    negative_signals = [s for s in signals if s.value < -conflict_threshold]
    
    # Conflict if both strong positive and strong negative exist
    # AND they have similar confidence/weight
    if positive_signals and negative_signals:
        pos_strength = sum(s.weight * s.confidence for s in positive_signals)
        neg_strength = sum(s.weight * s.confidence for s in negative_signals)
        
        # Balanced conflict
        if min(pos_strength, neg_strength) / max(pos_strength, neg_strength) > 0.7:
            return True
    
    return False
