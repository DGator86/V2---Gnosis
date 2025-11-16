# scripts/run_composer_backtest_spy.py

from datetime import datetime
import pandas as pd

from backtesting.composer_backtest import BacktestConfig, run_composer_backtest


def load_spy_prices_from_csv(path: str) -> pd.Series:
    """
    Example loader. Expects a CSV with columns:
    timestamp, close

    Adjust to your actual historical data store.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp")
    return df.set_index("timestamp")["close"].astype(float)


def make_price_getter(prices: pd.Series):
    def price_getter(symbol: str, t: pd.Timestamp) -> float:
        # Nearest previous price; assumes prices index is sorted
        try:
            return float(prices.loc[:t].iloc[-1])
        except IndexError:
            return float("nan")
    return price_getter


def hedge_engine_runner(symbol: str, t: pd.Timestamp):
    """
    Stub runner – replace with real historical hedge engine execution
    or precomputed snapshots.
    
    NOTE: Must return EngineOutput with kind="hedge"
    """
    from schemas.core_schemas import EngineOutput
    
    return EngineOutput(
        kind="hedge",
        symbol=symbol,
        timestamp=t,
        features={
            "net_pressure": 1e6,
            "movement_energy": 0.5,
            "elasticity": 1.0,
        },
        confidence=0.8,
        regime="normal",
    )


def liquidity_engine_runner(symbol: str, t: pd.Timestamp):
    """
    NOTE: Must return EngineOutput with kind="liquidity"
    """
    from schemas.core_schemas import EngineOutput
    
    return EngineOutput(
        kind="liquidity",
        symbol=symbol,
        timestamp=t,
        features={
            "polr_direction": 0.2,
            "polr_strength": 0.5,
            "liquidity_score": 0.9,
            "friction_cost": 0.3,
            "amihud_illiquidity": 1e-6,
        },
        confidence=0.7,
        regime="normal",
    )


def sentiment_engine_runner(symbol: str, t: pd.Timestamp):
    """
    NOTE: Must return SentimentEnvelope
    """
    from engines.sentiment.models import SentimentEnvelope
    
    return SentimentEnvelope(
        bias="bullish",
        strength=0.6,
        energy=0.4,
        confidence=0.7,
        drivers={"wyckoff": 0.5, "flow": 0.3},
        timestamp=t,
        wyckoff_phase="markup",
    )


if __name__ == "__main__":
    symbol = "SPY"
    prices = load_spy_prices_from_csv("data/spy_daily.csv")
    timestamps = prices.index.to_list()

    cfg = BacktestConfig(
        symbol=symbol,
        horizon_steps=1,  # next bar / next day
        notional=1.0,
    )

    price_getter = make_price_getter(prices)

    result = run_composer_backtest(
        config=cfg,
        timestamps=timestamps,
        price_getter=price_getter,
        hedge_engine_runner=hedge_engine_runner,
        liquidity_engine_runner=liquidity_engine_runner,
        sentiment_engine_runner=sentiment_engine_runner,
    )

    print("=== Composer Backtest Result ===")
    print(f"Symbol: {cfg.symbol}")
    print(f"Directional Accuracy: {result.directional_accuracy:.3f}")
    print(f"Naive PnL (notional={cfg.notional}): {result.naive_pnl:.6f}")
    print(f"Sharpe: {result.sharpe:.3f}")
    print("Accuracy by energy bucket:")
    for bucket, acc in result.energy_bucket_accuracy.items():
        print(f"  {bucket}: {acc:.3f}")

    # Save full log for further analysis
    result.log.to_csv("composer_backtest_log_spy.csv")
