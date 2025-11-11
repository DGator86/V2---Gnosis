# Production Sentiment Engine 📊

A production-ready financial sentiment analysis engine powered by FinBERT, designed for real-time market sentiment tracking and trading signal generation.

## 🌟 Key Features

### Core Capabilities
- **FinBERT Integration**: State-of-the-art financial sentiment analysis
- **Entity Recognition**: Automatic ticker extraction with customizable aliases
- **Duplicate Detection**: SimHash-based near-duplicate filtering
- **Time-Decayed Statistics**: Weighted rolling statistics across multiple time windows
- **Advanced Metrics**: 15+ sentiment indicators including entropy, momentum, surprise
- **Dual Correlation Tracking**: Market-wide and sector-specific correlations
- **Trading Signals**: Built-in flags for contrarian, trend, and shock detection

### Performance Features
- Batch processing support
- Result caching
- Asynchronous news fetching
- Optimized numpy operations
- Configurable buffer sizes

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from sentiment import SentimentEngine, NewsDoc
from datetime import datetime, timezone

# Initialize engine
engine = SentimentEngine()

# Create a news document
doc = NewsDoc(
    id="1",
    ts_utc=datetime.now(timezone.utc),
    title="Apple reports record iPhone sales, raises guidance",
    url="https://example.com/article",
    source="reuters",
    tickers=["AAPL"]
)

# Score the document
scored = engine.score_docs([doc])

# Ingest into statistics
engine.ingest(scored)

# Get sentiment snapshot
snapshot = engine.snapshot("AAPL", "1h")
print(f"AAPL Sentiment: {snapshot.mean:.3f}")
print(f"Trending: {snapshot.is_trending_sentiment}")
print(f"Information Shock: {snapshot.is_information_shock}")
```

## 📦 Architecture

### Component Overview

```
sentiment/
├── engine.py          # Main orchestrator
├── schemas.py         # Data models
├── config.py          # Configuration
├── nlp/
│   ├── finbert.py     # FinBERT wrapper
│   └── entity_map.py  # Ticker extraction
├── dedupe/
│   └── simhash.py     # Duplicate detection
├── features/
│   └── rollup.py      # Rolling statistics
├── references/
│   └── reference_builder.py  # ETF correlations
└── fetchers/
    └── google_rss.py  # News fetching
```

### Data Flow

1. **News Ingestion** → Fetchers retrieve articles
2. **Entity Extraction** → Tickers identified
3. **Sentiment Scoring** → FinBERT analysis
4. **Deduplication** → SimHash filtering
5. **Statistical Rollup** → Time-weighted metrics
6. **Snapshot Generation** → Trading signals

## 📊 Metrics Explained

### Core Statistics
- **mean**: Time-decayed weighted average sentiment [-1, 1]
- **std**: Weighted standard deviation of sentiment
- **skew**: Asymmetry of sentiment distribution

### Advanced Metrics
- **disagreement**: Spread between positive/negative sentiment [0, 1]
- **momentum**: EWMA trend of sentiment change
- **surprise**: Z-score vs historical baseline
- **novelty**: Ratio of unique vs duplicate content
- **entropy**: Uncertainty in sentiment mix [0, 1]
- **sharpe_like**: Signal-to-noise ratio

### Correlations
- **corr_to_market**: Correlation with market-wide sentiment
- **corr_to_ref**: Correlation with sector/reference series

### Trading Flags
- **is_contrarian_market**: Negative correlation with market
- **is_contrarian_sector**: Negative correlation with sector
- **is_strong_contrarian**: Both contrarian + trending + shock
- **is_trending_sentiment**: Clear directional trend
- **is_information_shock**: Significant surprise detected

## ⚙️ Configuration

### Source Weights
Configure reliability weights for different news sources:

```python
SOURCE_WEIGHTS = {
    "bloomberg": 1.0,
    "reuters": 1.0,
    "wsj": 0.95,
    "seekingalpha": 0.75,
    "reddit": 0.60,
    "pr": 0.50,
}
```

### Time Windows
Analyze sentiment across multiple time horizons:

```python
windows = ["5m", "30m", "1h", "1d"]
```

### Thresholds
Adjust detection thresholds:

```python
CONTRARIAN_THRESH = {
    "market": -0.25,      # Correlation threshold
    "trend_momentum": 0.02,
    "shock_surprise": 1.0,  # Z-score threshold
}
```

## 🔗 Integration Examples

### With Trading Agents

```python
# Agent 3: Sentiment Interpreter
class SentimentAgent:
    def interpret(self, snapshot: TickerSentimentSnapshot):
        if snapshot.is_strong_contrarian and snapshot.mean > 0:
            return "CONTRARIAN_BULLISH"
        elif snapshot.is_information_shock:
            return "NEWS_CATALYST"
        elif snapshot.entropy > 0.7:
            return "HIGH_UNCERTAINTY"
        return "NEUTRAL"

# Agent 4: Strategy Composer
class StrategyAgent:
    def compose(self, sentiment_signal, market_regime):
        if sentiment_signal == "CONTRARIAN_BULLISH":
            if market_regime == "FRAGILE":
                return "DIRECTIONAL_DEBIT_SPREAD"
        # ... more logic
```

### With Reference Data

```python
from sentiment.references import ReferenceBuilder

# Setup ETF references
ref_builder = ReferenceBuilder()
engine.attach_reference_builder(ref_builder)

# Map tickers to sectors
engine.set_ticker_reference("AAPL", "XLK")  # Tech sector
engine.set_ticker_reference("JPM", "XLF")   # Financial sector

# Feed price data
ref_builder.update_price("XLK", datetime.now(), 200.50)
```

## 🎯 Performance Optimization

### Batch Processing
```python
# Process multiple documents efficiently
docs = [doc1, doc2, doc3, ...]  # List of NewsDoc
scored = engine.score_docs(docs)  # Batch scoring
engine.ingest(scored)             # Batch ingestion
```

### Caching
```python
# Enable caching for repeated content
engine = SentimentEngine(enable_caching=True)
```

### Async Fetching
```python
import asyncio
from sentiment.fetchers import GoogleRSSFetcher

async def fetch_news():
    fetcher = GoogleRSSFetcher()
    docs = await fetcher.fetch("AAPL stock", max_articles=20)
    return docs

docs = asyncio.run(fetch_news())
```

## 📊 Production Deployment

### Docker Setup
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download FinBERT model during build
RUN python -c "from transformers import AutoModel, AutoTokenizer; \
               AutoModel.from_pretrained('ProsusAI/finbert'); \
               AutoTokenizer.from_pretrained('ProsusAI/finbert')"

COPY . .
CMD ["python", "main.py"]
```

### Monitoring
```python
# Get engine statistics
stats = engine.get_statistics()
print(f"Documents processed: {stats['docs_processed']}")
print(f"Duplicates found: {stats['duplicates_found']}")
print(f"Novelty rate: {stats['novelty_rate']:.2%}")
```

## 🛠️ Advanced Usage

### Custom Symbol Aliases
```python
alias_dict = {
    "AAPL": {"apple", "apple inc", "tim cook's company"},
    "TSLA": {"tesla", "elon's car company", "model s maker"},
}
engine = SentimentEngine(symbol_aliases=alias_dict)
```

### Multi-Window Analysis
```python
# Analyze across all time windows
snapshots = engine.snapshots_for("AAPL")

for window, snap in snapshots.items():
    print(f"{window}: mean={snap.mean:.3f}, momentum={snap.momentum:.3f}")
```

### Custom Decay Windows
```python
# Define custom time windows
custom_windows = ["1m", "15m", "4h", "1w"]
engine = SentimentEngine(decay_windows=custom_windows)
```

## 🔧 Troubleshooting

### Common Issues

1. **Model Download**: First run downloads ~420MB FinBERT model
2. **Memory Usage**: Reduce buffer sizes in config if needed
3. **Correlation NaN**: Need minimum 20 data points

## 📈 Benchmarks

- **Throughput**: ~100 documents/second on CPU
- **Latency**: <50ms per document (cached)
- **Memory**: ~1GB with default buffers
- **Accuracy**: 85%+ on financial headlines

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md

## 🙏 Acknowledgments

- ProsusAI for FinBERT model
- Hugging Face for transformers library
- Original NewsSentimentScanner for inspiration