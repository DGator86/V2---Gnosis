"""Label generation for ML training.

Generates multiple label types:
- Forward returns (5m, 15m, 1h horizons)
- Direction labels (±1)
- Magnitude labels (small/medium/large moves)
- Volatility estimates (forward realized volatility)
"""

from ml.labels.generator import LabelGenerator, LabelConfig, LabelSet

__all__ = ["LabelGenerator", "LabelConfig", "LabelSet"]
