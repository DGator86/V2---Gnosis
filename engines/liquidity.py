"""
Liquidity Engine
Computes Amihud λ and optional extensions (Kyle’s λ) to measure market resistance.
Implements M3 of the Gnosis / DHPE build guide.
"""

import numpy as np
import pandas as pd


def estimate_amihud(bars_df: pd.DataFrame, span: int = 20):
    """
    Estimate Amihud illiquidity λ_t = E[ |r_t| / Vol_t ], EWMA-smoothed.

    Parameters
    ----------
    bars_df : DataFrame with columns ['close','volume']
    span : int, smoothing window (default 20)

    Returns
    -------
    np.ndarray of λ values (positive, NaN-safe)
    """
    r = bars_df["close"].pct_change().abs().fillna(0.0)
    vol = bars_df["volume"].replace(0, np.nan).fillna(method="ffill")
    amihud = (r / vol).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    lam = amihud.ewm(span=span, adjust=False).mean().values
    if (lam <= 0).any():
        lam[lam <= 0] = np.nanmin(lam[lam > 0]) if (lam > 0).any() else 1e-8
    return lam
