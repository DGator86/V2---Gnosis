"""
WallStreetBets (WSB) Sentiment Adapter.

Scrapes and analyzes sentiment from Reddit's r/wallstreetbets.
Provides meme stock pressure, retail mania indicators, and sentiment scores.

Uses Reddit API (PRAW): https://praw.readthedocs.io/
Alternative: https://github.com/ngurnani/WSB_Sentiment

Note: Requires Reddit API credentials (free).
Sign up at: https://www.reddit.com/prefs/apps
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from collections import Counter
from loguru import logger
import polars as pl
from pydantic import BaseModel, Field
import re

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning(
        "praw not installed. Install with: pip install praw"
    )


class WSBPost(BaseModel):
    """Single WSB post."""
    
    id: str
    title: str
    body: str
    author: str
    created_utc: float
    score: int  # Upvotes - downvotes
    upvote_ratio: float
    num_comments: int
    flair: Optional[str] = None
    url: str
    
    # Extracted data
    symbols: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None  # "bullish", "bearish", "neutral"


class WSBSentiment(BaseModel):
    """Aggregated WSB sentiment for a symbol."""
    
    symbol: str
    timestamp: str
    
    # Mention metrics
    total_mentions: int = 0
    post_mentions: int = 0
    comment_mentions: int = 0
    
    # Sentiment scores
    sentiment_score: float = 0.0  # -1 (bearish) to +1 (bullish)
    bullish_ratio: float = 0.0
    
    # Engagement metrics
    total_score: int = 0  # Sum of upvotes
    avg_score: float = 0.0
    avg_upvote_ratio: float = 0.0
    total_comments: int = 0
    
    # Mania indicators
    is_meme_stock: bool = False
    meme_pressure: float = 0.0  # 0 to 1 scale
    mania_score: float = 0.0  # Contrarian indicator
    
    # Rank
    mention_rank: int = 0  # Rank by mentions


class WSBSentimentAdapter:
    """
    Adapter for Reddit WallStreetBets sentiment analysis.
    
    Provides:
    - Symbol mention tracking
    - Sentiment analysis
    - Meme stock pressure indicators
    - Retail mania signals (contrarian indicators)
    """
    
    # Bullish keywords
    BULLISH_KEYWORDS = {
        "moon", "rocket", "calls", "long", "buy", "bull", "bullish",
        "up", "gains", "tendies", "lambos", "yolo", "diamond hands",
        "hold", "hodl", "squeeze", "breakout", "rally"
    }
    
    # Bearish keywords
    BEARISH_KEYWORDS = {
        "puts", "short", "bear", "bearish", "down", "crash", "dump",
        "sell", "losses", "rekt", "bagholding", "trap", "overvalued"
    }
    
    # Ticker pattern (e.g., $SPY, $TSLA)
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize WSB sentiment adapter.
        
        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string (e.g., "WSBSentiment/1.0")
            username: Reddit username (optional, for read-write access)
            password: Reddit password (optional)
        """
        if not PRAW_AVAILABLE:
            raise ImportError("praw is required. Install with: pip install praw")
        
        # Initialize Reddit client
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
        
        # Set read-only mode
        self.reddit.read_only = True
        
        logger.info("✅ WSB sentiment adapter initialized")
    
    def _extract_tickers(self, text: str) -> List[str]:
        """
        Extract stock tickers from text.
        
        Args:
            text: Text to search for tickers (e.g., "$SPY to the moon!")
        
        Returns:
            List of ticker symbols found
        """
        # Find all $TICKER patterns
        tickers = self.TICKER_PATTERN.findall(text)
        
        # Filter out common false positives
        filtered = [
            t for t in tickers
            if t not in {"A", "I", "DD", "YOLO", "WSB", "CEO", "IPO", "ATH"}
        ]
        
        return filtered
    
    def _analyze_sentiment(self, text: str) -> str:
        """
        Simple sentiment analysis based on keywords.
        
        Args:
            text: Text to analyze
        
        Returns:
            "bullish", "bearish", or "neutral"
        """
        text_lower = text.lower()
        
        # Count keyword matches
        bullish_count = sum(
            1 for keyword in self.BULLISH_KEYWORDS
            if keyword in text_lower
        )
        bearish_count = sum(
            1 for keyword in self.BEARISH_KEYWORDS
            if keyword in text_lower
        )
        
        # Determine sentiment
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"
    
    def fetch_posts(
        self,
        limit: int = 100,
        time_filter: str = "day",
        sort_by: str = "hot"
    ) -> List[WSBPost]:
        """
        Fetch posts from r/wallstreetbets.
        
        Args:
            limit: Number of posts to fetch (max 1000)
            time_filter: "hour", "day", "week", "month", "year", "all"
            sort_by: "hot", "new", "top", "rising"
        
        Returns:
            List of WSBPost objects
        """
        logger.info(f"Fetching {limit} {sort_by} posts from WSB")
        
        subreddit = self.reddit.subreddit("wallstreetbets")
        
        # Get posts based on sort method
        if sort_by == "hot":
            submissions = subreddit.hot(limit=limit)
        elif sort_by == "new":
            submissions = subreddit.new(limit=limit)
        elif sort_by == "top":
            submissions = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort_by == "rising":
            submissions = subreddit.rising(limit=limit)
        else:
            raise ValueError(f"Invalid sort_by: {sort_by}")
        
        posts = []
        for submission in submissions:
            # Extract tickers
            title_text = f"{submission.title} {submission.selftext}"
            tickers = self._extract_tickers(title_text)
            
            # Analyze sentiment
            sentiment = self._analyze_sentiment(title_text)
            
            post = WSBPost(
                id=submission.id,
                title=submission.title,
                body=submission.selftext[:500],  # Truncate long posts
                author=str(submission.author) if submission.author else "[deleted]",
                created_utc=submission.created_utc,
                score=submission.score,
                upvote_ratio=submission.upvote_ratio,
                num_comments=submission.num_comments,
                flair=submission.link_flair_text,
                url=f"https://reddit.com{submission.permalink}",
                symbols=tickers,
                sentiment=sentiment
            )
            posts.append(post)
        
        logger.info(f"✅ Fetched {len(posts)} posts")
        return posts
    
    def calculate_symbol_sentiment(
        self,
        posts: List[WSBPost],
        min_mentions: int = 3
    ) -> List[WSBSentiment]:
        """
        Calculate sentiment for all mentioned symbols.
        
        Args:
            posts: List of WSBPost objects
            min_mentions: Minimum mentions required to include symbol
        
        Returns:
            List of WSBSentiment objects, sorted by mention count
        """
        # Count mentions and aggregate metrics per symbol
        symbol_data = {}
        
        for post in posts:
            for symbol in post.symbols:
                if symbol not in symbol_data:
                    symbol_data[symbol] = {
                        "mentions": 0,
                        "scores": [],
                        "upvote_ratios": [],
                        "comments": [],
                        "sentiments": []
                    }
                
                data = symbol_data[symbol]
                data["mentions"] += 1
                data["scores"].append(post.score)
                data["upvote_ratios"].append(post.upvote_ratio)
                data["comments"].append(post.num_comments)
                data["sentiments"].append(post.sentiment)
        
        # Filter by min mentions
        symbol_data = {
            symbol: data
            for symbol, data in symbol_data.items()
            if data["mentions"] >= min_mentions
        }
        
        if not symbol_data:
            logger.warning(f"No symbols with >={min_mentions} mentions")
            return []
        
        # Sort by mentions
        sorted_symbols = sorted(
            symbol_data.items(),
            key=lambda x: x[1]["mentions"],
            reverse=True
        )
        
        # Calculate sentiment for each symbol
        results = []
        for rank, (symbol, data) in enumerate(sorted_symbols, 1):
            # Sentiment score
            bullish_count = sum(1 for s in data["sentiments"] if s == "bullish")
            bearish_count = sum(1 for s in data["sentiments"] if s == "bearish")
            
            if bullish_count + bearish_count > 0:
                sentiment_score = (bullish_count - bearish_count) / (bullish_count + bearish_count)
                bullish_ratio = bullish_count / (bullish_count + bearish_count)
            else:
                sentiment_score = 0.0
                bullish_ratio = 0.5
            
            # Engagement metrics
            total_score = sum(data["scores"])
            avg_score = total_score / len(data["scores"]) if data["scores"] else 0
            avg_upvote_ratio = sum(data["upvote_ratios"]) / len(data["upvote_ratios"]) if data["upvote_ratios"] else 0
            total_comments = sum(data["comments"])
            
            # Meme stock detection
            # High mentions + high engagement = meme stock
            mention_threshold = 10
            score_threshold = 1000
            
            is_meme_stock = (
                data["mentions"] >= mention_threshold and
                avg_score >= score_threshold
            )
            
            # Meme pressure (0 to 1 scale)
            meme_pressure = min(1.0, (
                (data["mentions"] / 50) * 0.5 +  # Normalize to 50 mentions
                (avg_score / 5000) * 0.3 +       # Normalize to 5000 score
                (total_comments / 1000) * 0.2    # Normalize to 1000 comments
            ))
            
            # Mania score (contrarian indicator)
            # High when extreme bullish sentiment + high mentions
            mania_score = min(1.0, (
                bullish_ratio * 0.5 +            # Weight bullish ratio
                (data["mentions"] / 100) * 0.3 + # Weight popularity
                meme_pressure * 0.2              # Weight meme status
            ))
            
            sentiment = WSBSentiment(
                symbol=symbol,
                timestamp=datetime.now().isoformat(),
                total_mentions=data["mentions"],
                post_mentions=data["mentions"],  # All from posts in this implementation
                comment_mentions=0,  # Would need to fetch comments separately
                sentiment_score=sentiment_score,
                bullish_ratio=bullish_ratio,
                total_score=total_score,
                avg_score=avg_score,
                avg_upvote_ratio=avg_upvote_ratio,
                total_comments=total_comments,
                is_meme_stock=is_meme_stock,
                meme_pressure=meme_pressure,
                mania_score=mania_score,
                mention_rank=rank
            )
            results.append(sentiment)
        
        logger.info(f"✅ Calculated sentiment for {len(results)} symbols")
        return results
    
    def fetch_sentiment(
        self,
        limit: int = 100,
        time_filter: str = "day",
        sort_by: str = "hot",
        min_mentions: int = 3
    ) -> pl.DataFrame:
        """
        Fetch posts and calculate sentiment in one call.
        
        Args:
            limit: Number of posts to fetch
            time_filter: Time filter for posts
            sort_by: Sort method
            min_mentions: Minimum mentions to include symbol
        
        Returns:
            Polars DataFrame with sentiment for all symbols
        """
        # Fetch posts
        posts = self.fetch_posts(
            limit=limit,
            time_filter=time_filter,
            sort_by=sort_by
        )
        
        # Calculate sentiment
        sentiments = self.calculate_symbol_sentiment(
            posts=posts,
            min_mentions=min_mentions
        )
        
        if not sentiments:
            return pl.DataFrame()
        
        # Convert to DataFrame
        df = pl.DataFrame([s.model_dump() for s in sentiments])
        
        return df
    
    def get_top_mentions(
        self,
        limit: int = 100,
        top_n: int = 10
    ) -> pl.DataFrame:
        """
        Get top N most mentioned symbols.
        
        Args:
            limit: Number of posts to analyze
            top_n: Number of top symbols to return
        
        Returns:
            DataFrame with top symbols by mention count
        """
        df = self.fetch_sentiment(limit=limit)
        
        if df.is_empty():
            return df
        
        return df.head(top_n)


# Example usage
if __name__ == "__main__":
    import os
    
    # Note: You need to set these environment variables
    # Get credentials from: https://www.reddit.com/prefs/apps
    client_id = os.getenv("REDDIT_CLIENT_ID", "YOUR_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
    user_agent = "WSBSentiment/1.0 by YourUsername"
    
    if client_id == "YOUR_CLIENT_ID":
        print("\n⚠️  WARNING: Reddit API credentials not configured!")
        print("\n📝 To use this adapter:")
        print("1. Go to: https://www.reddit.com/prefs/apps")
        print("2. Create a new app (select 'script')")
        print("3. Set environment variables:")
        print("   export REDDIT_CLIENT_ID='your_client_id'")
        print("   export REDDIT_CLIENT_SECRET='your_client_secret'")
        print("\nSkipping examples...\n")
    else:
        # Initialize adapter
        adapter = WSBSentimentAdapter(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        # Example 1: Get top mentions
        print("\n" + "="*60)
        print("EXAMPLE 1: Top 10 Most Mentioned Symbols")
        print("="*60)
        
        df_top = adapter.get_top_mentions(limit=100, top_n=10)
        
        print(f"\nTop mentions from last 100 hot posts:")
        print(df_top.select([
            "mention_rank",
            "symbol",
            "total_mentions",
            "sentiment_score",
            "is_meme_stock",
            "mania_score"
        ]))
        
        # Example 2: Full sentiment analysis
        print("\n" + "="*60)
        print("EXAMPLE 2: Full Sentiment Analysis")
        print("="*60)
        
        df_sentiment = adapter.fetch_sentiment(
            limit=50,
            time_filter="day",
            sort_by="hot",
            min_mentions=2
        )
        
        print(f"\nSentiment for {len(df_sentiment)} symbols:")
        print(df_sentiment.select([
            "symbol",
            "sentiment_score",
            "total_mentions",
            "avg_score",
            "meme_pressure"
        ]).head(10))
        
        # Example 3: Meme stocks only
        print("\n" + "="*60)
        print("EXAMPLE 3: Meme Stocks Detection")
        print("="*60)
        
        df_meme = df_sentiment.filter(pl.col("is_meme_stock"))
        
        if len(df_meme) > 0:
            print(f"\n🚀 Detected {len(df_meme)} meme stocks:")
            print(df_meme.select([
                "symbol",
                "total_mentions",
                "meme_pressure",
                "mania_score",
                "sentiment_score"
            ]))
        else:
            print("\n📊 No meme stocks detected in current sample")
        
        # Example 4: Contrarian indicators
        print("\n" + "="*60)
        print("EXAMPLE 4: Contrarian Indicators (High Mania)")
        print("="*60)
        
        df_mania = df_sentiment.filter(pl.col("mania_score") > 0.7)
        
        if len(df_mania) > 0:
            print(f"\n⚠️  High mania symbols (potential contrarian signals):")
            print(df_mania.select([
                "symbol",
                "mania_score",
                "bullish_ratio",
                "total_mentions"
            ]))
        else:
            print("\n✅ No extreme mania detected")
