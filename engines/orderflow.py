"""
Order-Flow Engine
Derives simple directional flow metrics (ΔV, CVD) for integration into the pressure system.
Implements M3 extensions (order-flow awareness).
"""

import numpy as np
import pandas as pd


def compute(bars_df: pd.DataFrame):
    """
    Compute signed volume (ΔV) and cumulative volume delta (CVD)
    using price-change direction as a proxy for trade aggressor.

    Parameters
    ----------
    bars_df : DataFrame with ['close','volume']

    Returns
    -------
    tuple (dV, cvd)
        dV : np.ndarray, signed volume per bar
        cvd: np.ndarray, cumulative delta
    """
    ret = bars_df["close"].diff().fillna(0.0)
    sign = np.sign(ret.values)
    dV = sign * bars_df["volume"].values
    cvd = dV.cumsum()
    return dV, cvd
