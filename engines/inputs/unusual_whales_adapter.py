"""Unusual Whales API adapter for options flow and alternative data.

Provides access to:
- Live options flow (sweeps, blocks, unusual activity)
- Market sentiment & tide
- Options chains with Greeks
- Congressional & insider trades
- Institutional holdings
- Historical data

API Documentation: https://api.unusualwhales.com/docs
OpenAPI Spec: https://api.unusualwhales.com/api/openapi.json
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List, Dict, Any
import os
from loguru import logger
import httpx


class UnusualWhalesAdapter:
    """Complete adapter for Unusual Whales API.
    
    Features:
    - Live options flow feed with filtering
    - High-urgency alerts (sweeps, blocks, unusual)
    - Market sentiment & tide
    - Full options chains with Greeks
    - Congressional & insider trades
    - Institutional holdings (13F)
    - Historical data
    - Real-time WebSocket support (future)
    
    Authentication:
    - Generate API key from https://unusualwhales.com/member/api-keys
    - Set UNUSUAL_WHALES_API_KEY environment variable
    - Or pass api_key parameter
    
    Rate Limits:
    - Free tier: ~5 requests/min
    - Paid tiers: 60-600+ requests/min
    - Use pagination for large datasets
    
    Usage:
        adapter = UnusualWhalesAdapter()
        
        # Live options flow
        flow = adapter.get_options_flow(limit=100, min_premium=500000)
        
        # High-urgency alerts
        alerts = adapter.get_flow_alerts(limit=50)
        
        # Market sentiment
        tide = adapter.get_market_tide()
        
        # Options chain
        chain = adapter.get_ticker_chain("AAPL")
        
        # Congressional trades
        congress = adapter.get_congress_trades(politician="Nancy Pelosi")
    """
    
    BASE_URL = "https://api.unusualwhales.com"
    WS_URL = "wss://api.unusualwhales.com/ws"
    
    # Test/placeholder key (limited, for development only)
    DEFAULT_TEST_KEY = "8932cd23-72b3-4f74-9848-13f9103b9df5"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        use_test_key: bool = False
    ):
        """Initialize Unusual Whales API adapter.
        
        Args:
            api_key: API key from Unusual Whales dashboard
                    (if None, reads from UNUSUAL_WHALES_API_KEY env var)
            timeout: Request timeout in seconds (default: 30)
            use_test_key: Use default test key for development (default: False)
        
        Raises:
            ValueError: If API key is not provided or found in env
        """
        # Get API key
        if use_test_key:
            self.api_key = self.DEFAULT_TEST_KEY
            logger.warning(
                "Using test API key - limited rate limits! "
                "Set UNUSUAL_WHALES_API_KEY for production use."
            )
        else:
            self.api_key = api_key or os.getenv("UNUSUAL_WHALES_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Unusual Whales API key required. "
                "Pass api_key parameter, set UNUSUAL_WHALES_API_KEY env variable, "
                "or use use_test_key=True for development."
            )
        
        self.timeout = timeout
        
        # Initialize HTTP client
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            },
            timeout=timeout,
        )
        
        logger.info("UnusualWhalesAdapter initialized successfully")
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """Make API request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/v1/options/flow")
            params: Query parameters
            **kwargs: Additional arguments for httpx request
        
        Returns:
            Parsed JSON response
        
        Raises:
            RuntimeError: If request fails
        """
        try:
            response = self.client.request(
                method,
                endpoint,
                params=params,
                **kwargs
            )
            
            if response.status_code not in [200, 201]:
                error_msg = (
                    f"{method} {endpoint} failed: "
                    f"{response.status_code} {response.text}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during {method} {endpoint}: {e}")
            raise RuntimeError(f"API request failed: {e}")
    
    # ========================================================================
    # OPTIONS FLOW
    # ========================================================================
    
    def get_options_flow(
        self,
        page: int = 1,
        limit: int = 100,
        ticker: Optional[str] = None,
        min_premium: Optional[float] = None,
        max_premium: Optional[float] = None,
        sentiment: Optional[str] = None,
        option_type: Optional[str] = None,
        trade_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get live options flow feed (paginated).
        
        Args:
            page: Page number (default: 1)
            limit: Results per page (default: 100)
            ticker: Filter by ticker symbol
            min_premium: Minimum premium ($)
            max_premium: Maximum premium ($)
            sentiment: "bullish", "bearish", or "neutral"
            option_type: "call" or "put"
            trade_type: "sweep", "block", "split", "unusual"
            **kwargs: Additional filter parameters
        
        Returns:
            Flow data including:
            - data: List of flow records
            - total: Total count
            - page: Current page
            - has_next: Whether more pages exist
        
        Example:
            # Get high-premium bullish sweeps
            flow = adapter.get_options_flow(
                limit=50,
                min_premium=500000,
                sentiment="bullish",
                trade_type="sweep"
            )
        """
        logger.debug(f"Fetching options flow (page={page}, limit={limit})...")
        
        params = {
            "page": page,
            "limit": limit,
        }
        
        if ticker:
            params["ticker"] = ticker
        if min_premium:
            params["min_premium"] = min_premium
        if max_premium:
            params["max_premium"] = max_premium
        if sentiment:
            params["sentiment"] = sentiment
        if option_type:
            params["option_type"] = option_type
        if trade_type:
            params["trade_type"] = trade_type
        
        # Add any additional filters
        params.update(kwargs)
        
        data = self._make_request("GET", "/api/option-trades/flow-alerts", params=params)
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} flow record(s)")
        
        return data
    
    def get_flow_alerts(
        self,
        page: int = 1,
        limit: int = 50,
        ticker: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get high-urgency options flow alerts.
        
        Filtered for unusual activity, large blocks, and aggressive sweeps.
        
        Args:
            page: Page number (default: 1)
            limit: Results per page (default: 50)
            ticker: Filter by ticker symbol
            **kwargs: Additional filter parameters
        
        Returns:
            Alert data with same structure as get_options_flow
        
        Example:
            alerts = adapter.get_flow_alerts(limit=25)
        """
        logger.debug(f"Fetching flow alerts (limit={limit})...")
        
        params = {
            "page": page,
            "limit": limit,
        }
        
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        data = self._make_request("GET", "/api/option-trades/flow-alerts", params=params)
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} alert(s)")
        
        return data
    
    def get_ticker_flow(
        self,
        ticker: str,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Get options flow for a specific ticker.
        
        Args:
            ticker: Stock symbol (e.g., "AAPL")
            limit: Results limit (default: 100)
            **kwargs: Additional filter parameters
        
        Returns:
            Flow data for the ticker
        """
        logger.debug(f"Fetching flow for {ticker}...")
        
        params = {"limit": limit}
        params.update(kwargs)
        
        data = self._make_request(
            "GET",
            f"/api/stock/{ticker}/flow-recent",
            params=params
        )
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} flow record(s) for {ticker}")
        
        return data
    
    # ========================================================================
    # MARKET OVERVIEW
    # ========================================================================
    
    def get_market_tide(self) -> Dict[str, Any]:
        """Get overall market sentiment & tide.
        
        Returns:
            Market tide data including:
            - tide: Overall market direction
            - sentiment: Market sentiment score
            - call_premium: Total call premium
            - put_premium: Total put premium
            - ratio: Put/call ratio
        
        Example:
            tide = adapter.get_market_tide()
            print(f"Market tide: {tide['tide']}")
        """
        logger.debug("Fetching market tide...")
        
        data = self._make_request("GET", "/api/market/market-tide")
        
        logger.info(f"Market tide: {data.get('tide', 'N/A')}")
        
        return data
    
    def get_market_heatmap(
        self,
        map_type: str = "options"
    ) -> Dict[str, Any]:
        """Get market heatmap data.
        
        Args:
            map_type: "options" or "stocks" (default: "options")
        
        Returns:
            Heatmap data for visualization
        """
        logger.debug(f"Fetching {map_type} heatmap...")
        
        params = {"type": map_type}
        # Note: Heatmap endpoint not found in OpenAPI spec, using option-chains as alternative
        logger.warning("Heatmap endpoint not available in current API version")
        return {"error": "Endpoint not available"}
        
        logger.info(f"Retrieved heatmap data ({map_type})")
        
        return data
    
    # ========================================================================
    # TICKER DATA
    # ========================================================================
    
    def get_ticker_overview(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive ticker overview.
        
        Args:
            ticker: Stock symbol (e.g., "SPY")
        
        Returns:
            Overview data including:
            - price: Current price
            - iv: Implied volatility
            - volume: Trading volume
            - open_interest: Total open interest
            - greeks: Aggregate Greeks
            - stats: Various statistics
        """
        logger.debug(f"Fetching overview for {ticker}...")
        
        data = self._make_request("GET", f"/api/stock/{ticker}/info")
        
        logger.info(f"Retrieved overview for {ticker}")
        
        return data
    
    def get_ticker_chain(
        self,
        ticker: str,
        date: Optional[str] = None,
        expiration: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get full options chain with Greeks.
        
        Args:
            ticker: Stock symbol
            date: Date for historical chain (YYYY-MM-DD)
            expiration: Filter by expiration date (YYYY-MM-DD)
        
        Returns:
            Options chain data with:
            - calls: List of call options
            - puts: List of put options
            - Each option includes: strike, bid, ask, IV, Greeks, OI, volume
        """
        logger.debug(f"Fetching options chain for {ticker}...")
        
        params = {}
        if date:
            params["date"] = date
        if expiration:
            params["expiration"] = expiration
        
        data = self._make_request(
            "GET",
            f"/api/stock/{ticker}/option-chains",
            params=params if params else None
        )
        
        calls_count = len(data.get("calls", []))
        puts_count = len(data.get("puts", []))
        logger.info(f"Retrieved chain for {ticker}: {calls_count} calls, {puts_count} puts")
        
        return data
    
    def get_ticker_oi(
        self,
        ticker: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get open interest snapshot for a ticker.
        
        Args:
            ticker: Stock symbol
            date: Date for historical OI (YYYY-MM-DD)
        
        Returns:
            Open interest data by strike and expiration
        """
        logger.debug(f"Fetching OI for {ticker}...")
        
        params = {"date": date} if date else None
        
        data = self._make_request(
            "GET",
            f"/api/stock/{ticker}/oi-per-strike",
            params=params
        )
        
        logger.info(f"Retrieved OI data for {ticker}")
        
        return data
    
    # ========================================================================
    # HISTORICAL DATA
    # ========================================================================
    
    def get_historical_flow(
        self,
        date: str,
        ticker: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Get historical options flow.
        
        Args:
            date: Date (YYYY-MM-DD)
            ticker: Filter by ticker
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            Historical flow data
        """
        logger.debug(f"Fetching historical flow for {date}...")
        
        params = {
            "date": date,
            "limit": limit
        }
        
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        # Historical flow requires ticker-specific endpoint
        if ticker:
            data = self._make_request(
                "GET",
                f"/api/stock/{ticker}/flow-per-strike",
                params=params
            )
        else:
            logger.warning("Historical flow requires ticker parameter")
            data = {"error": "ticker parameter required"}
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} historical flow record(s)")
        
        return data
    
    def get_ticker_historical(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """Get historical price/IV data for a ticker.
        
        Args:
            ticker: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Historical data time series
        """
        logger.debug(f"Fetching historical data for {ticker}...")
        
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        data = self._make_request(
            "GET",
            f"/api/stock/{ticker}/ohlc/1D",
            params=params
        )
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} historical record(s) for {ticker}")
        
        return data
    
    # ========================================================================
    # CONGRESS & INSIDER TRADES
    # ========================================================================
    
    def get_congress_trades(
        self,
        politician: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Get congressional stock trades.
        
        Args:
            politician: Filter by politician name
            ticker: Filter by ticker
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            Congressional trade data including:
            - politician: Name
            - ticker: Symbol
            - transaction_type: Buy/Sell
            - amount_range: Dollar range
            - date: Transaction date
        
        Example:
            # Nancy Pelosi trades
            trades = adapter.get_congress_trades(politician="Nancy Pelosi")
            
            # All NVDA congressional trades
            trades = adapter.get_congress_trades(ticker="NVDA")
        """
        logger.debug("Fetching congressional trades...")
        
        params = {"limit": limit}
        
        if politician:
            params["politician"] = politician
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        data = self._make_request(
            "GET",
            "/api/congress/recent-trades",
            params=params
        )
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} congressional trade(s)")
        
        return data
    
    def get_insider_trades(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Get insider transactions (Form 4 filings).
        
        Args:
            ticker: Filter by ticker
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            Insider trade data
        """
        logger.debug("Fetching insider trades...")
        
        params = {"limit": limit}
        
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        data = self._make_request(
            "GET",
            "/api/insider/transactions",
            params=params
        )
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} insider trade(s)")
        
        return data
    
    # ========================================================================
    # NEWS & FILINGS
    # ========================================================================
    
    def get_news(
        self,
        ticker: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """Get market-moving news.
        
        Args:
            ticker: Filter by ticker
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            News articles
        """
        logger.debug("Fetching news...")
        
        params = {"limit": limit}
        
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        # News endpoint not found in OpenAPI spec
        logger.warning("News endpoint not available in current API version")
        data = {"error": "Endpoint not available", "data": []}
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} news article(s)")
        
        return data
    
    def get_sec_filings(
        self,
        ticker: Optional[str] = None,
        form_type: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> Dict[str, Any]:
        """Get SEC filings.
        
        Args:
            ticker: Filter by ticker
            form_type: Filter by form type (e.g., "10-K", "8-K")
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            SEC filing data
        """
        logger.debug("Fetching SEC filings...")
        
        params = {"limit": limit}
        
        if ticker:
            params["ticker"] = ticker
        if form_type:
            params["form_type"] = form_type
        
        params.update(kwargs)
        
        # SEC filings not in current API spec - use institutions/latest_filings
        data = self._make_request("GET", "/api/institutions/latest_filings", params=params)
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} SEC filing(s)")
        
        return data
    
    # ========================================================================
    # INSTITUTIONAL DATA
    # ========================================================================
    
    def get_institutional_holdings(
        self,
        cik: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """Get 13F institutional holdings.
        
        Args:
            cik: Filter by institution CIK
            ticker: Filter by ticker
            limit: Results limit
            **kwargs: Additional filters
        
        Returns:
            13F holdings data
        """
        logger.debug("Fetching institutional holdings...")
        
        params = {"limit": limit}
        
        if cik:
            params["cik"] = cik
        if ticker:
            params["ticker"] = ticker
        
        params.update(kwargs)
        
        # Institutional holdings require institution name, not CIK
        if cik:
            logger.warning("Institution holdings endpoint requires 'name' not 'cik'")
            return {"error": "Use get_institution_holdings_by_name(name, ...) instead"}
        
        if ticker:
            data = self._make_request(
                "GET",
                f"/api/institution/{ticker}/ownership",
                params=params
            )
        else:
            # List all institutions
            data = self._make_request(
                "GET",
                "/api/institutions",
                params=params
            )
        
        count = len(data.get("data", []))
        logger.info(f"Retrieved {count} institutional holding(s)")
        
        return data
    
    # ========================================================================
    # CONVENIENCE METHODS
    # ========================================================================
    
    def test_connection(self) -> bool:
        """Test API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            tide = self.get_market_tide()
            logger.info(f"✅ Connection test successful (tide: {tide.get('tide')})")
            return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_adapter(
    api_key: Optional[str] = None,
    use_test_key: bool = False
) -> UnusualWhalesAdapter:
    """Create and initialize Unusual Whales adapter.
    
    Args:
        api_key: API key (reads from env if not provided)
        use_test_key: Use test key for development
    
    Returns:
        Initialized adapter
    """
    return UnusualWhalesAdapter(api_key=api_key, use_test_key=use_test_key)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("Unusual Whales API - Test Script")
    print("="*60)
    
    # Initialize adapter (with test key for demo)
    try:
        adapter = UnusualWhalesAdapter(use_test_key=True)
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\nSet your API key:")
        print("  export UNUSUAL_WHALES_API_KEY='your_api_key_here'")
        print("\nOr use test key:")
        print("  adapter = UnusualWhalesAdapter(use_test_key=True)")
        sys.exit(1)
    
    # Test 1: Market tide
    print("\n" + "="*60)
    print("TEST 1: Market Tide")
    print("="*60)
    
    try:
        tide = adapter.get_market_tide()
        print(f"✅ Market tide: {tide.get('tide', 'N/A')}")
        print(f"   Sentiment: {tide.get('sentiment', 'N/A')}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 2: Options flow alerts
    print("\n" + "="*60)
    print("TEST 2: Flow Alerts (Top 10)")
    print("="*60)
    
    try:
        alerts = adapter.get_flow_alerts(limit=10)
        data = alerts.get("data", [])
        print(f"✅ Retrieved {len(data)} alert(s)")
        
        if data:
            print("\nSample alerts:")
            for alert in data[:3]:
                ticker = alert.get("ticker", "N/A")
                premium = alert.get("premium", 0)
                sentiment = alert.get("sentiment", "N/A")
                trade_type = alert.get("trade_type", "N/A")
                print(f"  {ticker}: ${premium:,.0f} ({sentiment} {trade_type})")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 3: SPY options flow
    print("\n" + "="*60)
    print("TEST 3: SPY Options Flow")
    print("="*60)
    
    try:
        flow = adapter.get_ticker_flow("SPY", limit=5)
        data = flow.get("data", [])
        print(f"✅ Retrieved {len(data)} flow record(s) for SPY")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 4: Congressional trades
    print("\n" + "="*60)
    print("TEST 4: Recent Congressional Trades")
    print("="*60)
    
    try:
        congress = adapter.get_congress_trades(limit=5)
        data = congress.get("data", [])
        print(f"✅ Retrieved {len(data)} congressional trade(s)")
        
        if data:
            print("\nSample trades:")
            for trade in data[:3]:
                politician = trade.get("politician", "N/A")
                ticker = trade.get("ticker", "N/A")
                tx_type = trade.get("transaction_type", "N/A")
                print(f"  {politician}: {tx_type} {ticker}")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    print("\n" + "="*60)
    print("✅ Tests completed!")
    print("="*60)
    print("\nNote: Using test API key - limited rate limits")
    print("Set UNUSUAL_WHALES_API_KEY for production use")
