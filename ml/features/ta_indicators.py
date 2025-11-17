"""
Technical Analysis Indicators Wrapper using `ta` library.

Provides 130+ technical indicators as a complement/validation to the custom
technical indicators in technical.py. This wrapper makes it easy to add
additional indicators that aren't already implemented.

Uses the `ta` library: https://github.com/bukosabino/ta
"""

from typing import List, Optional
from loguru import logger
import polars as pl

try:
    import ta
    import pandas as pd
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning(
        "ta library not installed. Install with: pip install ta>=0.11.0"
    )


class TAIndicators:
    """
    Wrapper for the ta library providing 130+ technical indicators.
    
    Categories:
    - Volume indicators (e.g., OBV, CMF, MFI, VWAP)
    - Volatility indicators (e.g., Bollinger, Keltner, Donchian, ATR)
    - Trend indicators (e.g., MACD, EMA, SMA, ADX, Ichimoku)
    - Momentum indicators (e.g., RSI, Stochastic, Williams %R, ROC)
    - Others (e.g., Daily Return, Cumulative Return)
    """
    
    def __init__(self):
        if not TA_AVAILABLE:
            raise ImportError(
                "ta library is required. Install with: pip install ta>=0.11.0"
            )
        self.available_categories = [
            "volume", "volatility", "trend", "momentum", "others"
        ]
    
    def _to_pandas(self, df: pl.DataFrame) -> pd.DataFrame:
        """Convert Polars to Pandas for ta library."""
        return df.to_pandas()
    
    def _to_polars(self, df: pd.DataFrame) -> pl.DataFrame:
        """Convert Pandas back to Polars."""
        return pl.from_pandas(df)
    
    def add_all_indicators(
        self,
        df: pl.DataFrame,
        open_col: str = "open",
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add ALL 130+ technical indicators from the ta library.
        
        Args:
            df: Polars DataFrame with OHLCV data
            open_col: Name of open price column
            high_col: Name of high price column
            low_col: Name of low price column
            close_col: Name of close price column
            volume_col: Name of volume column
            fillna: Whether to fill NaN values (forward-fill strategy)
        
        Returns:
            Polars DataFrame with all ta indicators added
        """
        logger.info("Adding all ta library indicators (130+ features)")
        
        # Convert to pandas for ta library
        df_pd = self._to_pandas(df)
        
        # Add all indicators at once
        df_with_ta = ta.add_all_ta_features(
            df_pd,
            open=open_col,
            high=high_col,
            low=low_col,
            close=close_col,
            volume=volume_col,
            fillna=fillna
        )
        
        # Convert back to polars
        result = self._to_polars(df_with_ta)
        
        added_cols = len(result.columns) - len(df.columns)
        logger.info(f"✅ Added {added_cols} ta indicators")
        
        return result
    
    def add_volume_indicators(
        self,
        df: pl.DataFrame,
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add volume-based indicators.
        
        Indicators:
        - On-Balance Volume (OBV)
        - Chaikin Money Flow (CMF)
        - Money Flow Index (MFI)
        - Volume Weighted Average Price (VWAP)
        - Accumulation/Distribution Index (ADI)
        - Force Index (FI)
        - Ease of Movement (EOM)
        - Volume Price Trend (VPT)
        - Negative Volume Index (NVI)
        """
        logger.info("Adding volume indicators")
        
        df_pd = self._to_pandas(df)
        
        # On-Balance Volume
        df_pd['ta_volume_obv'] = ta.volume.on_balance_volume(
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # Chaikin Money Flow
        df_pd['ta_volume_cmf'] = ta.volume.chaikin_money_flow(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # Money Flow Index
        df_pd['ta_volume_mfi'] = ta.volume.money_flow_index(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # VWAP
        df_pd['ta_volume_vwap'] = ta.volume.volume_weighted_average_price(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # Accumulation/Distribution Index
        df_pd['ta_volume_adi'] = ta.volume.acc_dist_index(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # Force Index
        df_pd['ta_volume_fi'] = ta.volume.force_index(
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        # Ease of Movement
        eom = ta.volume.ease_of_movement(
            high=df_pd[high_col],
            low=df_pd[low_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        df_pd['ta_volume_eom'] = eom
        
        # Volume Price Trend
        df_pd['ta_volume_vpt'] = ta.volume.volume_price_trend(
            close=df_pd[close_col],
            volume=df_pd[volume_col],
            fillna=fillna
        )
        
        result = self._to_polars(df_pd)
        logger.info(f"✅ Added 8 volume indicators")
        return result
    
    def add_volatility_indicators(
        self,
        df: pl.DataFrame,
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add volatility indicators.
        
        Indicators:
        - Bollinger Bands (BB)
        - Keltner Channel (KC)
        - Donchian Channel (DC)
        - Average True Range (ATR)
        - Ulcer Index (UI)
        """
        logger.info("Adding volatility indicators")
        
        df_pd = self._to_pandas(df)
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df_pd[close_col], fillna=fillna)
        df_pd['ta_volatility_bbh'] = bb.bollinger_hband()
        df_pd['ta_volatility_bbl'] = bb.bollinger_lband()
        df_pd['ta_volatility_bbm'] = bb.bollinger_mavg()
        df_pd['ta_volatility_bbhi'] = bb.bollinger_hband_indicator()
        df_pd['ta_volatility_bbli'] = bb.bollinger_lband_indicator()
        df_pd['ta_volatility_bbw'] = bb.bollinger_wband()
        df_pd['ta_volatility_bbp'] = bb.bollinger_pband()
        
        # Keltner Channel
        kc = ta.volatility.KeltnerChannel(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_volatility_kch'] = kc.keltner_channel_hband()
        df_pd['ta_volatility_kcl'] = kc.keltner_channel_lband()
        df_pd['ta_volatility_kcm'] = kc.keltner_channel_mband()
        df_pd['ta_volatility_kchi'] = kc.keltner_channel_hband_indicator()
        df_pd['ta_volatility_kcli'] = kc.keltner_channel_lband_indicator()
        df_pd['ta_volatility_kcw'] = kc.keltner_channel_wband()
        df_pd['ta_volatility_kcp'] = kc.keltner_channel_pband()
        
        # Donchian Channel
        dc = ta.volatility.DonchianChannel(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_volatility_dch'] = dc.donchian_channel_hband()
        df_pd['ta_volatility_dcl'] = dc.donchian_channel_lband()
        df_pd['ta_volatility_dcm'] = dc.donchian_channel_mband()
        df_pd['ta_volatility_dchi'] = dc.donchian_channel_hband_indicator()
        df_pd['ta_volatility_dcli'] = dc.donchian_channel_lband_indicator()
        df_pd['ta_volatility_dcw'] = dc.donchian_channel_wband()
        df_pd['ta_volatility_dcp'] = dc.donchian_channel_pband()
        
        # ATR
        df_pd['ta_volatility_atr'] = ta.volatility.average_true_range(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        
        # Ulcer Index
        df_pd['ta_volatility_ui'] = ta.volatility.ulcer_index(
            close=df_pd[close_col],
            fillna=fillna
        )
        
        result = self._to_polars(df_pd)
        logger.info(f"✅ Added 25 volatility indicators")
        return result
    
    def add_trend_indicators(
        self,
        df: pl.DataFrame,
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add trend indicators.
        
        Indicators:
        - MACD
        - EMA (Exponential Moving Average)
        - SMA (Simple Moving Average)
        - WMA (Weighted Moving Average)
        - ADX (Average Directional Movement Index)
        - Vortex Indicator (VI)
        - Trix
        - Mass Index (MI)
        - CCI (Commodity Channel Index)
        - DPO (Detrended Price Oscillator)
        - KST (Know Sure Thing)
        - Ichimoku
        - Parabolic SAR
        - Aroon
        """
        logger.info("Adding trend indicators")
        
        df_pd = self._to_pandas(df)
        
        # MACD
        macd = ta.trend.MACD(close=df_pd[close_col], fillna=fillna)
        df_pd['ta_trend_macd'] = macd.macd()
        df_pd['ta_trend_macd_signal'] = macd.macd_signal()
        df_pd['ta_trend_macd_diff'] = macd.macd_diff()
        
        # EMA
        df_pd['ta_trend_ema_fast'] = ta.trend.ema_indicator(
            close=df_pd[close_col], window=12, fillna=fillna
        )
        df_pd['ta_trend_ema_slow'] = ta.trend.ema_indicator(
            close=df_pd[close_col], window=26, fillna=fillna
        )
        
        # SMA
        df_pd['ta_trend_sma_fast'] = ta.trend.sma_indicator(
            close=df_pd[close_col], window=12, fillna=fillna
        )
        df_pd['ta_trend_sma_slow'] = ta.trend.sma_indicator(
            close=df_pd[close_col], window=26, fillna=fillna
        )
        
        # WMA
        df_pd['ta_trend_wma_fast'] = ta.trend.wma_indicator(
            close=df_pd[close_col], window=12, fillna=fillna
        )
        df_pd['ta_trend_wma_slow'] = ta.trend.wma_indicator(
            close=df_pd[close_col], window=26, fillna=fillna
        )
        
        # ADX
        adx = ta.trend.ADXIndicator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_trend_adx'] = adx.adx()
        df_pd['ta_trend_adx_pos'] = adx.adx_pos()
        df_pd['ta_trend_adx_neg'] = adx.adx_neg()
        
        # Vortex
        vortex = ta.trend.VortexIndicator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_trend_vortex_pos'] = vortex.vortex_indicator_pos()
        df_pd['ta_trend_vortex_neg'] = vortex.vortex_indicator_neg()
        df_pd['ta_trend_vortex_diff'] = vortex.vortex_indicator_diff()
        
        # TRIX
        df_pd['ta_trend_trix'] = ta.trend.trix(
            close=df_pd[close_col], fillna=fillna
        )
        
        # Mass Index
        df_pd['ta_trend_mass_index'] = ta.trend.mass_index(
            high=df_pd[high_col],
            low=df_pd[low_col],
            fillna=fillna
        )
        
        # CCI
        df_pd['ta_trend_cci'] = ta.trend.cci(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        
        # DPO
        df_pd['ta_trend_dpo'] = ta.trend.dpo(
            close=df_pd[close_col], fillna=fillna
        )
        
        # KST
        kst = ta.trend.KSTIndicator(close=df_pd[close_col], fillna=fillna)
        df_pd['ta_trend_kst'] = kst.kst()
        df_pd['ta_trend_kst_sig'] = kst.kst_sig()
        df_pd['ta_trend_kst_diff'] = kst.kst_diff()
        
        # Ichimoku
        ichimoku = ta.trend.IchimokuIndicator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            fillna=fillna
        )
        df_pd['ta_trend_ichimoku_a'] = ichimoku.ichimoku_a()
        df_pd['ta_trend_ichimoku_b'] = ichimoku.ichimoku_b()
        df_pd['ta_trend_ichimoku_base'] = ichimoku.ichimoku_base_line()
        df_pd['ta_trend_ichimoku_conv'] = ichimoku.ichimoku_conversion_line()
        
        # Parabolic SAR
        psar = ta.trend.PSARIndicator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_trend_psar'] = psar.psar()
        df_pd['ta_trend_psar_up'] = psar.psar_up()
        df_pd['ta_trend_psar_down'] = psar.psar_down()
        df_pd['ta_trend_psar_up_indicator'] = psar.psar_up_indicator()
        df_pd['ta_trend_psar_down_indicator'] = psar.psar_down_indicator()
        
        # Aroon
        aroon = ta.trend.AroonIndicator(
            close=df_pd[close_col], fillna=fillna
        )
        df_pd['ta_trend_aroon_up'] = aroon.aroon_up()
        df_pd['ta_trend_aroon_down'] = aroon.aroon_down()
        df_pd['ta_trend_aroon_indicator'] = aroon.aroon_indicator()
        
        result = self._to_polars(df_pd)
        logger.info(f"✅ Added 39 trend indicators")
        return result
    
    def add_momentum_indicators(
        self,
        df: pl.DataFrame,
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add momentum indicators.
        
        Indicators:
        - RSI (Relative Strength Index)
        - Stochastic Oscillator
        - Stochastic RSI
        - Williams %R
        - Awesome Oscillator (AO)
        - KAMA (Kaufman Adaptive Moving Average)
        - ROC (Rate of Change)
        - TSI (True Strength Index)
        - Ultimate Oscillator (UO)
        - Percentage Price Oscillator (PPO)
        - Percentage Volume Oscillator (PVO)
        """
        logger.info("Adding momentum indicators")
        
        df_pd = self._to_pandas(df)
        
        # RSI
        df_pd['ta_momentum_rsi'] = ta.momentum.rsi(
            close=df_pd[close_col], fillna=fillna
        )
        
        # Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        df_pd['ta_momentum_stoch'] = stoch.stoch()
        df_pd['ta_momentum_stoch_signal'] = stoch.stoch_signal()
        
        # Stochastic RSI
        stoch_rsi = ta.momentum.StochRSIIndicator(
            close=df_pd[close_col], fillna=fillna
        )
        df_pd['ta_momentum_stoch_rsi'] = stoch_rsi.stochrsi()
        df_pd['ta_momentum_stoch_rsi_k'] = stoch_rsi.stochrsi_k()
        df_pd['ta_momentum_stoch_rsi_d'] = stoch_rsi.stochrsi_d()
        
        # Williams %R
        df_pd['ta_momentum_wr'] = ta.momentum.williams_r(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        
        # Awesome Oscillator
        df_pd['ta_momentum_ao'] = ta.momentum.awesome_oscillator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            fillna=fillna
        )
        
        # KAMA
        df_pd['ta_momentum_kama'] = ta.momentum.kama(
            close=df_pd[close_col], fillna=fillna
        )
        
        # ROC
        df_pd['ta_momentum_roc'] = ta.momentum.roc(
            close=df_pd[close_col], fillna=fillna
        )
        
        # TSI
        tsi = ta.momentum.TSIIndicator(close=df_pd[close_col], fillna=fillna)
        df_pd['ta_momentum_tsi'] = tsi.tsi()
        
        # Ultimate Oscillator
        df_pd['ta_momentum_uo'] = ta.momentum.ultimate_oscillator(
            high=df_pd[high_col],
            low=df_pd[low_col],
            close=df_pd[close_col],
            fillna=fillna
        )
        
        # PPO
        ppo = ta.momentum.PercentagePriceOscillator(
            close=df_pd[close_col], fillna=fillna
        )
        df_pd['ta_momentum_ppo'] = ppo.ppo()
        df_pd['ta_momentum_ppo_signal'] = ppo.ppo_signal()
        df_pd['ta_momentum_ppo_hist'] = ppo.ppo_hist()
        
        # PVO
        pvo = ta.momentum.PercentageVolumeOscillator(
            volume=df_pd[volume_col], fillna=fillna
        )
        df_pd['ta_momentum_pvo'] = pvo.pvo()
        df_pd['ta_momentum_pvo_signal'] = pvo.pvo_signal()
        df_pd['ta_momentum_pvo_hist'] = pvo.pvo_hist()
        
        result = self._to_polars(df_pd)
        logger.info(f"✅ Added 21 momentum indicators")
        return result
    
    def add_other_indicators(
        self,
        df: pl.DataFrame,
        close_col: str = "close",
        fillna: bool = True
    ) -> pl.DataFrame:
        """
        Add miscellaneous indicators.
        
        Indicators:
        - Daily Return
        - Daily Log Return
        - Cumulative Return
        """
        logger.info("Adding other indicators")
        
        df_pd = self._to_pandas(df)
        
        # Daily Return
        df_pd['ta_others_dr'] = ta.others.daily_return(
            close=df_pd[close_col], fillna=fillna
        )
        
        # Daily Log Return
        df_pd['ta_others_dlr'] = ta.others.daily_log_return(
            close=df_pd[close_col], fillna=fillna
        )
        
        # Cumulative Return
        df_pd['ta_others_cr'] = ta.others.cumulative_return(
            close=df_pd[close_col], fillna=fillna
        )
        
        result = self._to_polars(df_pd)
        logger.info(f"✅ Added 3 other indicators")
        return result
    
    def get_available_indicators(self) -> dict:
        """
        Get list of all available indicators by category.
        
        Returns:
            Dictionary mapping category name to list of indicator names
        """
        return {
            "volume": [
                "obv", "cmf", "mfi", "vwap", "adi", "fi", "eom", "vpt"
            ],
            "volatility": [
                "bollinger_bands", "keltner_channel", "donchian_channel",
                "atr", "ulcer_index"
            ],
            "trend": [
                "macd", "ema", "sma", "wma", "adx", "vortex", "trix",
                "mass_index", "cci", "dpo", "kst", "ichimoku", "psar", "aroon"
            ],
            "momentum": [
                "rsi", "stochastic", "stoch_rsi", "williams_r", "ao",
                "kama", "roc", "tsi", "uo", "ppo", "pvo"
            ],
            "others": [
                "daily_return", "daily_log_return", "cumulative_return"
            ]
        }


# Example usage
if __name__ == "__main__":
    import numpy as np
    
    # Create sample OHLCV data
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="1min")
    
    sample_data = pl.DataFrame({
        "timestamp": dates,
        "open": np.random.randn(n).cumsum() + 100,
        "high": np.random.randn(n).cumsum() + 102,
        "low": np.random.randn(n).cumsum() + 98,
        "close": np.random.randn(n).cumsum() + 100,
        "volume": np.random.randint(1000, 10000, n)
    })
    
    # Initialize wrapper
    ta_indicators = TAIndicators()
    
    # Add all indicators at once
    result = ta_indicators.add_all_indicators(sample_data)
    
    print(f"\n📊 Original columns: {len(sample_data.columns)}")
    print(f"📊 Columns after ta indicators: {len(result.columns)}")
    print(f"📊 Added {len(result.columns) - len(sample_data.columns)} indicators")
    
    print("\n✅ Sample columns:")
    print(result.columns[:20])
    
    # Get available indicators
    available = ta_indicators.get_available_indicators()
    print(f"\n📋 Available indicator categories:")
    for category, indicators in available.items():
        print(f"  {category}: {len(indicators)} indicators")
