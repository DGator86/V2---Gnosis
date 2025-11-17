"""
StockTwits API Adapter for retail sentiment data.

Fetches real-time retail sentiment from StockTwits social feed.
Provides sentiment scores, message volume, and trending indicators.

Uses StockTwits API: https://api.stocktwits.com/developers/docs
Rate limits: 200 requests per hour (free tier)

Alternative libraries:
- https://github.com/lukasz-madon/stocktwits
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import polars as pl
from pydantic import BaseModel, Field

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not installed. Install with: pip install httpx")


class StockTwitsMessage(BaseModel):
    """Single StockTwits message."""
    
    id: int
    body: str
    created_at: str
    user_id: int
    username: str
    sentiment: Optional[str] = None  # "bullish", "bearish", or None
    likes: int = 0
    reshares: int = 0
    symbols: List[str] = Field(default_factory=list)


class StockTwitsSentiment(BaseModel):
    """Aggregated sentiment data for a symbol."""
    
    symbol: str
    timestamp: str
    
    # Message counts
    total_messages: int = 0
    bullish_messages: int = 0
    bearish_messages: int = 0
    neutral_messages: int = 0
    
    # Sentiment scores
    sentiment_score: float = 0.0  # -1 (bearish) to +1 (bullish)
    sentiment_ratio: float = 0.0  # bullish / (bullish + bearish)
    confidence: float = 0.0  # Based on message volume
    
    # Engagement metrics
    total_likes: int = 0
    total_reshares: int = 0
    avg_likes_per_message: float = 0.0
    avg_reshares_per_message: float = 0.0
    
    # Trending indicators
    message_velocity: float = 0.0  # Messages per hour
    is_trending: bool = False
    trending_score: float = 0.0


class StockTwitsAdapter:
    """
    Adapter for StockTwits API to fetch retail sentiment data.
    
    Provides:
    - Real-time sentiment scores
    - Message volume tracking
    - Trending indicators
    - Social engagement metrics
    """
    
    BASE_URL = "https://api.stocktwits.com/api/2"
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        use_cache: bool = True,
        cache_ttl_minutes: int = 5
    ):
        """
        Initialize StockTwits adapter.
        
        Args:
            access_token: Optional API access token (not required for public endpoints)
            use_cache: Whether to cache results
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required. Install with: pip install httpx")
        
        self.access_token = access_token
        self.use_cache = use_cache
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache = {}
        
        # Initialize HTTP client
        headers = {"Accept": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        
        self.client = httpx.Client(headers=headers, timeout=10.0)
        
        logger.info(f"✅ StockTwits adapter initialized (cache={use_cache})")
    
    def _get_cache_key(self, endpoint: str, params: dict) -> str:
        """Generate cache key from endpoint and params."""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{endpoint}?{param_str}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[dict]:
        """Get data from cache if still valid."""
        if not self.use_cache:
            return None
        
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return data
        
        return None
    
    def _put_in_cache(self, cache_key: str, data: dict):
        """Store data in cache."""
        if self.use_cache:
            self._cache[cache_key] = (data, datetime.now())
    
    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make API request with caching.
        
        Args:
            endpoint: API endpoint (e.g., "/streams/symbol/SPY.json")
            params: Query parameters
        
        Returns:
            Response JSON
        """
        params = params or {}
        cache_key = self._get_cache_key(endpoint, params)
        
        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit: {endpoint}")
            return cached
        
        # Make request
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Cache result
            self._put_in_cache(cache_key, data)
            
            return data
        
        except httpx.HTTPStatusError as e:
            logger.error(f"StockTwits API error: {e.response.status_code} - {e.response.text}")
            return {}
        except Exception as e:
            logger.error(f"Failed to fetch from StockTwits: {e}")
            return {}
    
    def fetch_stream(
        self,
        symbol: str,
        limit: int = 30,
        since: Optional[int] = None,
        max_id: Optional[int] = None,
        filter_type: str = "all"
    ) -> List[StockTwitsMessage]:
        """
        Fetch message stream for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
            limit: Number of messages to fetch (max 30)
            since: Return messages with ID greater than this
            max_id: Return messages with ID less than or equal to this
            filter_type: "all", "charts", "videos", "links", or "top"
        
        Returns:
            List of StockTwitsMessage objects
        """
        endpoint = f"/streams/symbol/{symbol.upper()}.json"
        params = {"limit": min(limit, 30), "filter": filter_type}
        
        if since:
            params["since"] = since
        if max_id:
            params["max"] = max_id
        
        data = self._request(endpoint, params)
        
        if not data or "messages" not in data:
            logger.warning(f"No messages found for {symbol}")
            return []
        
        messages = []
        for msg_data in data["messages"]:
            # Extract sentiment
            sentiment_data = msg_data.get("entities", {}).get("sentiment")
            sentiment = sentiment_data.get("basic") if sentiment_data else None
            
            # Extract symbols
            symbols = [
                s["symbol"] for s in msg_data.get("symbols", [])
            ]
            
            # Extract user
            user_data = msg_data.get("user", {})
            
            message = StockTwitsMessage(
                id=msg_data["id"],
                body=msg_data["body"],
                created_at=msg_data["created_at"],
                user_id=user_data.get("id", 0),
                username=user_data.get("username", "unknown"),
                sentiment=sentiment,
                likes=msg_data.get("likes", {}).get("total", 0),
                reshares=msg_data.get("reshares", {}).get("reshared_count", 0),
                symbols=symbols
            )
            messages.append(message)
        
        logger.info(f"✅ Fetched {len(messages)} messages for {symbol}")
        return messages
    
    def calculate_sentiment(
        self,
        messages: List[StockTwitsMessage],
        symbol: str,
        lookback_hours: int = 24
    ) -> StockTwitsSentiment:
        """
        Calculate aggregated sentiment from messages.
        
        Args:
            messages: List of StockTwitsMessage objects
            symbol: Symbol these messages are for
            lookback_hours: Time window for velocity calculation
        
        Returns:
            StockTwitsSentiment with aggregated metrics
        """
        if not messages:
            return StockTwitsSentiment(
                symbol=symbol,
                timestamp=datetime.now().isoformat()
            )
        
        # Count sentiment
        bullish = sum(1 for m in messages if m.sentiment == "Bullish")
        bearish = sum(1 for m in messages if m.sentiment == "Bearish")
        neutral = len(messages) - bullish - bearish
        
        # Calculate sentiment score (-1 to +1)
        if bullish + bearish > 0:
            sentiment_score = (bullish - bearish) / (bullish + bearish)
            sentiment_ratio = bullish / (bullish + bearish)
        else:
            sentiment_score = 0.0
            sentiment_ratio = 0.5
        
        # Engagement metrics
        total_likes = sum(m.likes for m in messages)
        total_reshares = sum(m.reshares for m in messages)
        avg_likes = total_likes / len(messages) if messages else 0.0
        avg_reshares = total_reshares / len(messages) if messages else 0.0
        
        # Message velocity (messages per hour)
        message_velocity = len(messages) / lookback_hours if lookback_hours > 0 else 0.0
        
        # Trending detection
        # Consider trending if:
        # 1. High message velocity (>10/hour)
        # 2. High engagement (avg likes > 5)
        # 3. Strong sentiment (abs(score) > 0.3)
        is_trending = (
            message_velocity > 10 and
            avg_likes > 5 and
            abs(sentiment_score) > 0.3
        )
        
        trending_score = (
            (message_velocity / 20) * 0.4 +  # Normalize to 20 msg/hr
            (avg_likes / 10) * 0.3 +          # Normalize to 10 likes
            abs(sentiment_score) * 0.3        # Already -1 to 1
        )
        
        # Confidence based on message volume
        confidence = min(1.0, len(messages) / 30.0)  # Max at 30 messages
        
        return StockTwitsSentiment(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            total_messages=len(messages),
            bullish_messages=bullish,
            bearish_messages=bearish,
            neutral_messages=neutral,
            sentiment_score=sentiment_score,
            sentiment_ratio=sentiment_ratio,
            confidence=confidence,
            total_likes=total_likes,
            total_reshares=total_reshares,
            avg_likes_per_message=avg_likes,
            avg_reshares_per_message=avg_reshares,
            message_velocity=message_velocity,
            is_trending=is_trending,
            trending_score=min(1.0, trending_score)
        )
    
    def fetch_sentiment(
        self,
        symbol: str,
        limit: int = 30,
        lookback_hours: int = 24
    ) -> StockTwitsSentiment:
        """
        Fetch and calculate sentiment in one call.
        
        Args:
            symbol: Stock symbol
            limit: Number of messages to fetch
            lookback_hours: Time window for metrics
        
        Returns:
            StockTwitsSentiment object
        """
        messages = self.fetch_stream(symbol=symbol, limit=limit)
        return self.calculate_sentiment(
            messages=messages,
            symbol=symbol,
            lookback_hours=lookback_hours
        )
    
    def fetch_multi_symbol_sentiment(
        self,
        symbols: List[str],
        limit_per_symbol: int = 30
    ) -> pl.DataFrame:
        """
        Fetch sentiment for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            limit_per_symbol: Messages to fetch per symbol
        
        Returns:
            Polars DataFrame with sentiment for all symbols
        """
        logger.info(f"Fetching sentiment for {len(symbols)} symbols")
        
        results = []
        for symbol in symbols:
            try:
                sentiment = self.fetch_sentiment(
                    symbol=symbol,
                    limit=limit_per_symbol
                )
                results.append(sentiment.model_dump())
            except Exception as e:
                logger.error(f"Failed to fetch sentiment for {symbol}: {e}")
                continue
        
        if not results:
            logger.warning("No sentiment data fetched")
            return pl.DataFrame()
        
        df = pl.DataFrame(results)
        logger.info(f"✅ Fetched sentiment for {len(df)} symbols")
        
        return df
    
    def close(self):
        """Close HTTP client."""
        self.client.close()


# Example usage
if __name__ == "__main__":
    # Initialize adapter
    adapter = StockTwitsAdapter(use_cache=True, cache_ttl_minutes=5)
    
    try:
        # Example 1: Fetch sentiment for single symbol
        print("\n" + "="*60)
        print("EXAMPLE 1: Fetch Sentiment for SPY")
        print("="*60)
        
        sentiment = adapter.fetch_sentiment(symbol="SPY", limit=30)
        
        print(f"\n{sentiment.symbol} Sentiment:")
        print(f"  Total Messages: {sentiment.total_messages}")
        print(f"  Bullish: {sentiment.bullish_messages}")
        print(f"  Bearish: {sentiment.bearish_messages}")
        print(f"  Neutral: {sentiment.neutral_messages}")
        print(f"  Sentiment Score: {sentiment.sentiment_score:+.3f} (-1 to +1)")
        print(f"  Sentiment Ratio: {sentiment.sentiment_ratio:.3f}")
        print(f"  Confidence: {sentiment.confidence:.3f}")
        print(f"  Message Velocity: {sentiment.message_velocity:.1f} msg/hr")
        print(f"  Trending: {sentiment.is_trending}")
        print(f"  Trending Score: {sentiment.trending_score:.3f}")
        print(f"  Avg Likes: {sentiment.avg_likes_per_message:.1f}")
        
        # Example 2: Fetch messages
        print("\n" + "="*60)
        print("EXAMPLE 2: Fetch Recent Messages")
        print("="*60)
        
        messages = adapter.fetch_stream(symbol="TSLA", limit=10)
        
        print(f"\nLatest 10 messages for TSLA:")
        for i, msg in enumerate(messages[:5], 1):
            sentiment_emoji = {
                "Bullish": "🟢",
                "Bearish": "🔴",
                None: "⚪"
            }.get(msg.sentiment, "⚪")
            
            print(f"\n{i}. {sentiment_emoji} @{msg.username}")
            print(f"   {msg.body[:100]}...")
            print(f"   ❤️ {msg.likes} likes | 🔄 {msg.reshares} reshares")
        
        # Example 3: Multi-symbol sentiment
        print("\n" + "="*60)
        print("EXAMPLE 3: Multi-Symbol Sentiment")
        print("="*60)
        
        symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]
        df_sentiment = adapter.fetch_multi_symbol_sentiment(symbols, limit_per_symbol=20)
        
        print(f"\nSentiment for {len(df_sentiment)} symbols:")
        print(df_sentiment.select([
            "symbol",
            "sentiment_score",
            "total_messages",
            "is_trending",
            "message_velocity"
        ]))
        
    finally:
        adapter.close()
