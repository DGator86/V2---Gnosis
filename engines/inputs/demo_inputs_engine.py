"""
Demo inputs engine
Provides sample market data for testing
Replace with real data adapters (IBKR, Polygon, etc.)
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import random
from schemas import RawInputs
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class DemoInputsEngine:
    """Engine for demo market data generation"""
    
    def __init__(self):
        logger.info("Demo inputs engine initialized")
    
    def get_options_chain(self, symbol: str, spot_price: float = 450.0) -> List[Dict[str, Any]]:
        """Generate demo options chain"""
        options = []
        
        # Generate strikes around spot
        strikes = [spot_price + i * 5 for i in range(-10, 11)]
        
        for strike in strikes:
            # Call option
            options.append({
                "type": "call",
                "strike": strike,
                "expiry": (datetime.now() + timedelta(days=7)).timestamp(),
                "gamma": random.uniform(0.01, 0.5) if abs(strike - spot_price) < 15 else random.uniform(0.001, 0.05),
                "delta": max(0, min(1, (spot_price - strike + 25) / 50)),
                "vega": random.uniform(0.1, 0.3),
                "open_interest": random.randint(100, 10000),
                "volume": random.randint(10, 1000),
                "iv": random.uniform(0.15, 0.40)
            })
            
            # Put option
            options.append({
                "type": "put",
                "strike": strike,
                "expiry": (datetime.now() + timedelta(days=7)).timestamp(),
                "gamma": random.uniform(0.01, 0.5) if abs(strike - spot_price) < 15 else random.uniform(0.001, 0.05),
                "delta": max(-1, min(0, (spot_price - strike - 25) / 50)),
                "vega": random.uniform(0.1, 0.3),
                "open_interest": random.randint(100, 10000),
                "volume": random.randint(10, 1000),
                "iv": random.uniform(0.15, 0.40)
            })
        
        return options
    
    def get_trade_tape(self, symbol: str, num_trades: int = 100) -> List[Dict[str, Any]]:
        """Generate demo trade tape"""
        trades = []
        base_price = 450.0
        
        for i in range(num_trades):
            price = base_price + random.uniform(-2, 2)
            size = random.randint(100, 10000)
            
            trades.append({
                "timestamp": (datetime.now() - timedelta(seconds=num_trades - i)).timestamp(),
                "price": price,
                "size": size,
                "side": random.choice(["buy", "sell"]),
                "venue": random.choice(["NYSE", "ARCA", "BATS", "EDGX"])
            })
        
        return trades
    
    def get_news_feed(self, symbol: str, num_items: int = 20) -> List[Dict[str, Any]]:
        """Generate demo news feed"""
        news_templates = [
            ("Fed announces interest rate decision", 0.1),
            ("{symbol} beats earnings expectations", 0.7),
            ("Market volatility increases amid uncertainty", -0.3),
            ("{symbol} announces new product launch", 0.5),
            ("Analyst upgrades {symbol} to buy", 0.6),
            ("Economic data shows strong growth", 0.4),
            ("{symbol} reports weak guidance", -0.5),
            ("Geopolitical tensions rise", -0.4),
            ("Tech sector rallies on AI optimism", 0.6),
            ("{symbol} CEO interview bullish", 0.5)
        ]
        
        news = []
        for i in range(num_items):
            template, base_score = random.choice(news_templates)
            title = template.format(symbol=symbol)
            score = base_score + random.uniform(-0.1, 0.1)
            
            news.append({
                "timestamp": (datetime.now() - timedelta(hours=num_items - i)).timestamp(),
                "title": title,
                "source": random.choice(["Bloomberg", "Reuters", "CNBC", "WSJ", "FT"]),
                "sentiment_score": score,
                "confidence": random.uniform(0.6, 0.95),
                "url": f"https://example.com/news/{i}"
            })
        
        return news
    
    def get_orderbook(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        """Generate demo orderbook"""
        mid_price = 450.0
        spread = 0.02
        
        bids = []
        asks = []
        
        for i in range(levels):
            bid_price = mid_price - spread/2 - i * 0.01
            ask_price = mid_price + spread/2 + i * 0.01
            
            bids.append({
                "price": round(bid_price, 2),
                "size": random.randint(100, 5000)
            })
            
            asks.append({
                "price": round(ask_price, 2),
                "size": random.randint(100, 5000)
            })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "bids": bids,
            "asks": asks,
            "spread": spread,
            "mid": mid_price
        }
    
    def get_raw_inputs(self, symbol: str = "SPY") -> RawInputs:
        """
        Get complete raw inputs for a symbol
        This is the main entry point
        """
        logger.info(f"Generating demo inputs for {symbol}")

        return RawInputs(
            symbol=symbol,
            timestamp=datetime.now(),
            options=self.get_options_chain(symbol),
            trades=self.get_trade_tape(symbol),
            news=self.get_news_feed(symbol),
            orderbook=self.get_orderbook(symbol),
            fundamentals={
                "pe_ratio": random.uniform(15, 30),
                "market_cap": random.uniform(1e10, 1e12),
                "avg_volume": random.uniform(5e7, 2e8)
            }
        )
