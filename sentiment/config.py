"""Configuration settings for the sentiment engine."""

# Source reliability weights for different news sources
SOURCE_WEIGHTS = {
    "bloomberg": 1.0,
    "reuters": 1.0,
    "wsj": 0.95,
    "ft": 0.95,
    "cnbc": 0.93,
    "marketwatch": 0.90,
    "ap": 0.90,
    "yahoo": 0.85,
    "seekingalpha": 0.75,
    "benzinga": 0.70,
    "reddit": 0.60,
    "blog": 0.60,
    "unknown": 0.70,
    "pr": 0.50,  # Press releases
    "twitter": 0.50,
}

# Recency decay constants (seconds) per time window
DECAY_TAU = {
    "5m": 90 * 60,      # 90 minutes
    "30m": 6 * 3600,    # 6 hours
    "1h": 12 * 3600,    # 12 hours
    "1d": 36 * 3600,    # 36 hours
}

# Lookback length for surprise baseline calculation
SURPRISE_LOOKBACK = 120  # Number of data points

# Thresholds for contrarian/trend/shock detection
CONTRARIAN_THRESH = {
    "market": -0.25,        # Correlation to market below this = contrarian
    "sector": -0.25,        # Correlation to sector below this = contrarian
    "trend_momentum": 0.02, # Minimum momentum for trending
    "trend_sharpe": 0.5,    # Minimum sharpe-like ratio for clean trend
    "shock_surprise": 1.0,  # Z-score threshold for information shock
}

# Sentiment model configuration
MODEL_CONFIG = {
    "model_id": "ProsusAI/finbert",
    "max_length": 512,
    "batch_size": 16,
    "cache_dir": None,  # Set to specific path for model caching
}

# Novelty detection parameters
NOVELTY_CONFIG = {
    "threshold_bits": 6,    # Hamming distance threshold for duplicates
    "cache_size": 10000,    # Max items in novelty cache
}

# Rolling statistics configuration
ROLLING_STATS_CONFIG = {
    "max_buffer": 5000,     # Max items per window
    "ema_span": 20,         # EMA span for momentum
    "corr_min_points": 20,  # Minimum points for correlation
}