#!/usr/bin/env python3
"""
Example usage of the Gnosis DHPE engine system.
Demonstrates how to integrate all three engines.
"""

import numpy as np
import pandas as pd
from engines import dhpe, liquidity, orderflow
from config import get_dhpe_config


def create_sample_data():
    """Create sample market data for demonstration."""
    # Sample price bars
    dates = pd.date_range('2024-01-01', periods=100, freq='1h')
    np.random.seed(42)
    
    # Generate synthetic price data with trend and noise
    price = 100 + np.cumsum(np.random.randn(100) * 0.5)
    volume = np.random.randint(1000000, 5000000, 100)
    
    bars_df = pd.DataFrame({
        'timestamp': dates,
        'close': price,
        'volume': volume
    })
    
    # Sample options data (placeholder structure)
    options_df = pd.DataFrame({
        'strike': np.linspace(95, 105, 20),
        'tau': np.random.uniform(0.1, 0.5, 20),
        'gamma': np.random.uniform(0.01, 0.1, 20),
        'vanna': np.random.uniform(-0.05, 0.05, 20),
        'charm': np.random.uniform(-0.02, 0.02, 20),
        'oi': np.random.randint(100, 1000, 20),
        'mid_iv': np.random.uniform(0.15, 0.35, 20)
    })
    
    return bars_df, options_df


def main():
    """Main demonstration workflow."""
    print("=" * 60)
    print("Gnosis DHPE Engine - Example Usage")
    print("=" * 60)
    print()
    
    # Load configuration
    config = get_dhpe_config()
    print(f"Configuration loaded:")
    print(f"  - Kernel kappa: {config['kernel']['kappa']}")
    print(f"  - Gamma weight: {config['weights']['alpha_G']}")
    print(f"  - Vanna weight: {config['weights']['alpha_V']}")
    print(f"  - Charm weight: {config['weights']['alpha_C']}")
    print(f"  - Liquidity span: {config['liquidity']['span']}")
    print()
    
    # Create sample data
    print("Generating sample market data...")
    bars_df, options_df = create_sample_data()
    print(f"  - Price bars: {len(bars_df)} periods")
    print(f"  - Options chain: {len(options_df)} contracts")
    print(f"  - Current price: ${bars_df['close'].iloc[-1]:.2f}")
    print()
    
    # Step 1: Compute liquidity
    print("[1/5] Computing Amihud liquidity metric...")
    lam = liquidity.estimate_amihud(bars_df, span=config['liquidity']['span'])
    print(f"  - Liquidity lambda (latest): {lam[-1]:.6e}")
    print(f"  - Mean lambda: {lam.mean():.6e}")
    print()
    
    # Step 2: Compute DHPE sources
    print("[2/5] Computing DHPE source densities (Gamma, Vanna, Charm)...")
    G, Vn, Ch = dhpe.sources(options_df, projector=config['projector'])
    print(f"  - Gamma shape: {G.shape}")
    print(f"  - Vanna shape: {Vn.shape}")
    print(f"  - Charm shape: {Ch.shape}")
    print("  - Note: Using placeholder implementation")
    print()
    
    # Step 3: Build Green's kernel
    print("[3/5] Building Green's kernel...")
    K = dhpe.greens_kernel(lam, kappa=config['kernel']['kappa'])
    print(f"  - Kernel shape: {K.shape}")
    print("  - Note: Using placeholder implementation")
    print()
    
    # Step 4: Compute pressure potential
    print("[4/5] Computing pressure potential...")
    Pi = dhpe.potential(G, Vn, Ch, K, weights=config['weights'])
    print(f"  - Potential shape: {Pi.shape}")
    print(f"  - Potential (latest): {Pi[-1]:.6f}")
    
    # Compute gradients
    grad = dhpe.gradient(Pi)
    dPi = dhpe.dPi_dt(Pi)
    print(f"  - Spatial gradient (latest): {grad[-1]:.6f}")
    print(f"  - Temporal derivative: {dPi:.6f}")
    print()
    
    # Step 5: Compute order flow
    print("[5/5] Computing order flow metrics...")
    dV, cvd = orderflow.compute(bars_df)
    print(f"  - Signed volume (latest): {dV[-1]:,.0f}")
    print(f"  - Cumulative volume delta: {cvd[-1]:,.0f}")
    print(f"  - CVD trend: {'Bullish' if cvd[-1] > cvd[-10] else 'Bearish'}")
    print()
    
    # Summary
    print("=" * 60)
    print("Analysis Complete")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Implement full sticky-delta projector in dhpe.sources()")
    print("  2. Complete Green's function computation in dhpe.greens_kernel()")
    print("  3. Add FFT-based convolution in dhpe.potential()")
    print("  4. Integrate real-time data feeds from Alpaca API")
    print("  5. Build signal generation and backtesting framework")
    print()
    print("For more information, see README.md")
    print()


if __name__ == "__main__":
    main()
