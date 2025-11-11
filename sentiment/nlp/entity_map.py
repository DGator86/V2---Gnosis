"""Entity extraction and symbol mapping for ticker identification."""

from __future__ import annotations
from typing import List, Set, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)


class SymbolLexicon:
    """Extract ticker symbols from text using aliases and patterns."""
    
    def __init__(
        self,
        aliases: Optional[Dict[str, Set[str]]] = None,
        use_pattern_matching: bool = True
    ):
        """Initialize symbol lexicon.
        
        Args:
            aliases: Dictionary mapping tickers to alias sets
                    e.g., {"AAPL": {"apple", "apple inc", "aapl"}}
            use_pattern_matching: Whether to use regex patterns for ticker extraction
        """
        # Normalize aliases to lowercase
        if aliases:
            self.aliases = {
                ticker: {alias.lower() for alias in alias_set} | {ticker.lower()}
                for ticker, alias_set in aliases.items()
            }
        else:
            self.aliases = self._default_aliases()
        
        self.use_pattern_matching = use_pattern_matching
        
        # Compile regex patterns for efficiency
        self._ticker_pattern = re.compile(r'\b([A-Z]{1,5})\b')
        self._exchange_pattern = re.compile(
            r'\b(NYSE|NASDAQ|AMEX|OTC):\s*([A-Z]{1,5})\b',
            re.IGNORECASE
        )
    
    @staticmethod
    def _default_aliases() -> Dict[str, Set[str]]:
        """Provide default ticker aliases for common stocks."""
        return {
            # Tech giants
            "AAPL": {"apple", "apple inc", "apple inc.", "aapl"},
            "MSFT": {"microsoft", "microsoft corp", "microsoft corporation", "msft"},
            "GOOGL": {"google", "alphabet", "alphabet inc", "googl", "goog"},
            "AMZN": {"amazon", "amazon.com", "amazon inc", "amzn"},
            "META": {"meta", "facebook", "meta platforms", "fb"},
            "TSLA": {"tesla", "tesla inc", "tesla motors", "tsla"},
            "NVDA": {"nvidia", "nvidia corp", "nvidia corporation", "nvda"},
            
            # Financial
            "JPM": {"jpmorgan", "jp morgan", "jpmorgan chase", "jpm"},
            "BAC": {"bank of america", "bofa", "boa", "bac"},
            "GS": {"goldman sachs", "goldman", "gs"},
            "MS": {"morgan stanley", "ms"},
            "WFC": {"wells fargo", "wfc"},
            
            # Energy
            "XOM": {"exxon", "exxonmobil", "exxon mobil", "xom"},
            "CVX": {"chevron", "chevron corp", "cvx"},
            
            # Healthcare
            "JNJ": {"johnson & johnson", "j&j", "jnj"},
            "PFE": {"pfizer", "pfizer inc", "pfe"},
            "UNH": {"unitedhealth", "united health", "unitedhealth group", "unh"},
            
            # Consumer
            "WMT": {"walmart", "wal-mart", "wmt"},
            "PG": {"procter & gamble", "p&g", "pg"},
            "KO": {"coca-cola", "coca cola", "coke", "ko"},
            "DIS": {"disney", "walt disney", "dis"},
            
            # ETFs
            "SPY": {"s&p 500", "spdr s&p 500", "spy"},
            "QQQ": {"nasdaq 100", "invesco qqq", "qqq"},
            "DIA": {"dow jones", "spdr dow", "dia"},
            "IWM": {"russell 2000", "iwm"},
            "VTI": {"total market", "vanguard total", "vti"},
            
            # Sectors
            "XLK": {"technology sector", "tech etf", "xlk"},
            "XLF": {"financial sector", "financials etf", "xlf"},
            "XLE": {"energy sector", "energy etf", "xle"},
            "XLV": {"healthcare sector", "health etf", "xlv"},
            "XLY": {"consumer discretionary", "consumer etf", "xly"},
        }
    
    def extract(self, text: str) -> List[str]:
        """Extract ticker symbols from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of unique ticker symbols found
        """
        if not text:
            return []
        
        found_tickers = set()
        text_lower = text.lower()
        
        # 1. Check aliases
        for ticker, alias_set in self.aliases.items():
            for alias in alias_set:
                # Use word boundaries for exact matches
                if re.search(rf'\b{re.escape(alias)}\b', text_lower):
                    found_tickers.add(ticker)
                    break
        
        # 2. Pattern matching for explicit tickers
        if self.use_pattern_matching:
            # Look for exchange:ticker patterns
            for match in self._exchange_pattern.finditer(text):
                ticker = match.group(2).upper()
                if self._is_valid_ticker(ticker):
                    found_tickers.add(ticker)
            
            # Look for standalone uppercase ticker patterns
            # (but be conservative to avoid false positives)
            for match in self._ticker_pattern.finditer(text):
                ticker = match.group(1)
                # Check if it's preceded by $ or in specific contexts
                start = match.start()
                if start > 0 and text[start - 1] == '$':
                    if self._is_valid_ticker(ticker):
                        found_tickers.add(ticker)
        
        return sorted(list(found_tickers))
    
    def _is_valid_ticker(self, ticker: str) -> bool:
        """Check if a string is likely a valid ticker.
        
        Args:
            ticker: Potential ticker symbol
            
        Returns:
            True if likely valid
        """
        # Basic validation rules
        if len(ticker) < 1 or len(ticker) > 5:
            return False
        
        # Avoid common non-ticker abbreviations
        common_words = {
            'I', 'A', 'THE', 'AND', 'OR', 'NOT', 'FOR', 'TO', 'IN',
            'OF', 'ON', 'AT', 'BY', 'UP', 'SO', 'NO', 'IF', 'US',
            'UK', 'EU', 'AI', 'IT', 'CEO', 'CFO', 'IPO', 'ETF'
        }
        
        if ticker in common_words:
            return False
        
        # Could add more sophisticated checks here
        # (e.g., checking against a known ticker database)
        
        return True
    
    def add_aliases(self, ticker: str, aliases: Set[str]):
        """Add or update aliases for a ticker.
        
        Args:
            ticker: Ticker symbol
            aliases: Set of aliases to add
        """
        ticker = ticker.upper()
        if ticker not in self.aliases:
            self.aliases[ticker] = set()
        
        self.aliases[ticker].update({alias.lower() for alias in aliases})
        self.aliases[ticker].add(ticker.lower())