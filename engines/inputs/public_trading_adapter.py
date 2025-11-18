"""Public.com Individual Trading API adapter.

Complete integration with Public.com's Individual Trading API for:
- Account management (accounts, portfolio, history)
- Market data (real-time quotes for equity/option/index)
- Order execution (future implementation)

API Documentation: https://public.com/api/docs
Individual API Program: https://public.com/api
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import os
from loguru import logger
import httpx


class PublicTradingAdapter:
    """Complete adapter for Public.com Individual Trading API.
    
    Features:
    - OAuth token management with automatic refresh
    - Account management (get accounts, portfolio, history)
    - Real-time market data (quotes for stocks, options, indices)
    - Transaction history with pagination
    - Full error handling and logging
    
    Authentication:
    1. Generate secret key from Public.com dashboard
    2. Exchange secret for access token (60-minute validity)
    3. Use access token for all API calls
    
    Usage:
        adapter = PublicTradingAdapter(secret_key="YOUR_SECRET_KEY")
        accounts = adapter.get_accounts()
        account_id = accounts[0]["accountId"]
        portfolio = adapter.get_portfolio(account_id)
        quotes = adapter.get_quotes(account_id, [
            {"symbol": "SPY", "type": "EQUITY"},
            {"symbol": "AAPL", "type": "EQUITY"}
        ])
    """
    
    BASE_URL = "https://api.public.com"
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        timeout: int = 30,
        auto_refresh: bool = True
    ):
        """Initialize Public.com Trading API adapter.
        
        Args:
            secret_key: API secret key from Public.com dashboard
                       (if None, reads from PUBLIC_SECRET_KEY env var)
            timeout: Request timeout in seconds (default: 30)
            auto_refresh: Automatically refresh expired tokens (default: True)
        
        Raises:
            ValueError: If secret key is not provided or found in env
        """
        # Get secret key from parameter or environment
        self.secret_key = secret_key or os.getenv("PUBLIC_SECRET_KEY")
        
        if not self.secret_key:
            raise ValueError(
                "Public.com secret key required. "
                "Pass secret_key parameter or set PUBLIC_SECRET_KEY env variable."
            )
        
        self.timeout = timeout
        self.auto_refresh = auto_refresh
        self.access_token = None
        self.token_expires_at = None
        
        # Initialize HTTP client
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        
        # Get initial access token
        self._refresh_access_token()
        
        logger.info("PublicTradingAdapter initialized successfully")
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def _refresh_access_token(self, validity_minutes: int = 60) -> str:
        """Exchange secret key for access token.
        
        Args:
            validity_minutes: Token validity in minutes (default: 60)
        
        Returns:
            Access token string
        
        Raises:
            RuntimeError: If token exchange fails
        """
        try:
            logger.debug("Refreshing access token...")
            
            response = self.client.post(
                "/userapiauthservice/personal/access-tokens",
                json={
                    "secret": self.secret_key,
                    "validityInMinutes": validity_minutes
                }
            )
            
            if response.status_code != 200:
                error_msg = f"Token exchange failed: {response.status_code} {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            data = response.json()
            self.access_token = data.get("accessToken")
            
            if not self.access_token:
                raise RuntimeError(f"No accessToken in response: {data}")
            
            # Calculate expiration (with 5-minute buffer)
            self.token_expires_at = datetime.now() + timedelta(minutes=validity_minutes - 5)
            
            # Update client headers
            self.client.headers["Authorization"] = f"Bearer {self.access_token}"
            
            logger.info(f"Access token refreshed (expires at {self.token_expires_at})")
            return self.access_token
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token exchange: {e}")
            raise RuntimeError(f"Failed to exchange secret for access token: {e}")
    
    def _ensure_authenticated(self):
        """Ensure we have a valid access token, refresh if needed."""
        if not self.access_token or not self.token_expires_at:
            self._refresh_access_token()
            return
        
        if datetime.now() >= self.token_expires_at:
            if self.auto_refresh:
                logger.debug("Token expired, refreshing...")
                self._refresh_access_token()
            else:
                raise RuntimeError("Access token expired and auto_refresh is disabled")
    
    def _make_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Any:
        """Make authenticated API request with error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            **kwargs: Additional arguments for httpx request
        
        Returns:
            Parsed JSON response
        
        Raises:
            RuntimeError: If request fails
        """
        self._ensure_authenticated()
        
        try:
            response = self.client.request(method, path, **kwargs)
            
            if response.status_code not in [200, 201]:
                error_msg = f"{method} {path} failed: {response.status_code} {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during {method} {path}: {e}")
            raise RuntimeError(f"API request failed: {e}")
    
    # ========================================================================
    # ACCOUNT MANAGEMENT
    # ========================================================================
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Get list of financial accounts for the authenticated user.
        
        Returns:
            List of account objects with fields:
            - accountId: Unique account identifier
            - accountType: "BROKERAGE", etc.
            - optionsLevel: Options trading level
            - brokerageAccountType: "CASH" or "MARGIN"
            - tradePermissions: Trading permissions
        
        Example:
            accounts = adapter.get_accounts()
            account_id = accounts[0]["accountId"]
        """
        logger.debug("Fetching accounts...")
        
        data = self._make_request("GET", "/userapigateway/trading/account")
        accounts = data.get("accounts", [])
        
        logger.info(f"Retrieved {len(accounts)} account(s)")
        return accounts
    
    def get_primary_account_id(self) -> str:
        """Get the primary account ID (first account in list).
        
        Returns:
            Account ID string
        
        Raises:
            RuntimeError: If no accounts found
        """
        accounts = self.get_accounts()
        
        if not accounts:
            raise RuntimeError("No accounts found for this user")
        
        account_id = accounts[0]["accountId"]
        logger.debug(f"Primary account ID: {account_id}")
        
        return account_id
    
    def get_portfolio(self, account_id: str) -> Dict[str, Any]:
        """Get portfolio snapshot for an account.
        
        Args:
            account_id: Target account ID
        
        Returns:
            Portfolio data including:
            - positions: List of open positions
            - equity: Account equity breakdown
            - buyingPower: Available buying power
            - openOrders: List of open orders
        
        Example:
            portfolio = adapter.get_portfolio(account_id)
            positions = portfolio.get("positions", [])
            buying_power = portfolio.get("buyingPower", {})
        """
        logger.debug(f"Fetching portfolio for account {account_id}...")
        
        data = self._make_request(
            "GET",
            f"/userapigateway/trading/{account_id}/portfolio/v2"
        )
        
        positions_count = len(data.get("positions", []))
        logger.info(f"Retrieved portfolio with {positions_count} position(s)")
        
        return data
    
    def get_history(
        self,
        account_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        page_size: Optional[int] = None,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get account history (transactions, trades, deposits, etc.).
        
        Args:
            account_id: Target account ID
            start: Start timestamp (UTC or with timezone)
            end: End timestamp
            page_size: Maximum number of records (default: API default)
            next_token: Pagination token for next page
        
        Returns:
            History data including:
            - transactions: List of transaction records
            - nextToken: Pagination token (if more pages available)
        
        Example:
            # Last 30 days
            end = datetime.utcnow()
            start = end - timedelta(days=30)
            history = adapter.get_history(account_id, start=start, end=end, page_size=100)
            
            # Pagination
            while history.get("nextToken"):
                history = adapter.get_history(
                    account_id, 
                    next_token=history["nextToken"]
                )
        """
        logger.debug(f"Fetching history for account {account_id}...")
        
        params = {}
        if start:
            # Public.com expects RFC 3339 format with timezone
            if start.tzinfo is None:
                start = start.replace(tzinfo=datetime.now().astimezone().tzinfo)
            params["start"] = start.isoformat()
        if end:
            if end.tzinfo is None:
                end = end.replace(tzinfo=datetime.now().astimezone().tzinfo)
            params["end"] = end.isoformat()
        if page_size:
            params["pageSize"] = page_size
        if next_token:
            params["nextToken"] = next_token
        
        data = self._make_request(
            "GET",
            f"/userapigateway/trading/{account_id}/history",
            params=params
        )
        
        transactions_count = len(data.get("transactions", []))
        has_more = "nextToken" in data
        logger.info(
            f"Retrieved {transactions_count} transaction(s)"
            f"{' (more pages available)' if has_more else ''}"
        )
        
        return data
    
    # ========================================================================
    # MARKET DATA
    # ========================================================================
    
    def get_quotes(
        self,
        account_id: str,
        instruments: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Get real-time quotes for multiple instruments.
        
        Args:
            account_id: Target account ID (for scoping/permissions)
            instruments: List of instrument descriptors, each with:
                - symbol: Ticker symbol (e.g., "SPY", "AAPL")
                - type: "EQUITY", "OPTION", or "INDEX"
        
        Returns:
            Quotes data including:
            - quotes: List of quote objects with:
                - instrument: Symbol and type
                - outcome: "SUCCESS" or error
                - last: Last trade price
                - lastTimestamp: Last trade timestamp
                - bid/ask: Bid/ask prices
                - bidSize/askSize: Bid/ask sizes
                - volume: Trading volume
                - openInterest: Open interest (options only)
        
        Example:
            quotes = adapter.get_quotes(account_id, [
                {"symbol": "SPY", "type": "EQUITY"},
                {"symbol": "QQQ", "type": "EQUITY"},
                {"symbol": "^VIX", "type": "INDEX"}
            ])
            
            for quote in quotes["quotes"]:
                if quote["outcome"] == "SUCCESS":
                    print(f"{quote['instrument']['symbol']}: ${quote['last']}")
        """
        logger.debug(f"Fetching quotes for {len(instruments)} instrument(s)...")
        
        data = self._make_request(
            "POST",
            f"/userapigateway/marketdata/{account_id}/quotes",
            json={"instruments": instruments}
        )
        
        quotes = data.get("quotes", [])
        success_count = sum(1 for q in quotes if q.get("outcome") == "SUCCESS")
        
        logger.info(f"Retrieved {success_count}/{len(quotes)} successful quote(s)")
        
        return data
    
    def get_quote(
        self,
        account_id: str,
        symbol: str,
        instrument_type: str = "EQUITY"
    ) -> Optional[Dict[str, Any]]:
        """Get quote for a single instrument (convenience method).
        
        Args:
            account_id: Target account ID
            symbol: Ticker symbol
            instrument_type: "EQUITY", "OPTION", or "INDEX" (default: "EQUITY")
        
        Returns:
            Quote object if successful, None if failed
        
        Example:
            quote = adapter.get_quote(account_id, "SPY")
            if quote:
                print(f"SPY: ${quote['last']}")
        """
        response = self.get_quotes(account_id, [
            {"symbol": symbol, "type": instrument_type}
        ])
        
        quotes = response.get("quotes", [])
        if not quotes:
            return None
        
        quote = quotes[0]
        if quote.get("outcome") != "SUCCESS":
            logger.warning(f"Quote for {symbol} failed: {quote.get('outcome')}")
            return None
        
        return quote
    
    # ========================================================================
    # CONVENIENCE METHODS
    # ========================================================================
    
    def get_vix(self, account_id: str) -> Optional[float]:
        """Get current VIX value.
        
        Args:
            account_id: Target account ID
        
        Returns:
            VIX value as float, or None if failed
        
        Note:
            Public.com may not support VIX directly. Try VXX (VIX ETF) as alternative.
        """
        # Try VIX index first, fall back to VXX ETF
        quote = self.get_quote(account_id, "VIX", "INDEX")
        if quote:
            return float(quote["last"])
        
        # Try VXX as alternative
        quote = self.get_quote(account_id, "VXX", "EQUITY")
        if quote:
            return float(quote["last"])
        
        return None
    
    def get_spx(self, account_id: str, use_etf: bool = True) -> Optional[float]:
        """Get current SPX value.
        
        Args:
            account_id: Target account ID
            use_etf: Use SPY ETF instead of SPX index (default: True)
        
        Returns:
            SPX value as float, or None if failed
        """
        symbol = "SPY" if use_etf else "SPX"
        instrument_type = "EQUITY" if use_etf else "INDEX"
        
        quote = self.get_quote(account_id, symbol, instrument_type)
        if quote:
            return float(quote["last"])
        return None
    
    def test_connection(self) -> bool:
        """Test API connection by fetching accounts.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            accounts = self.get_accounts()
            logger.info(f"✅ Connection test successful ({len(accounts)} account(s))")
            return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_adapter(secret_key: Optional[str] = None) -> PublicTradingAdapter:
    """Create and initialize a Public.com Trading API adapter.
    
    Args:
        secret_key: API secret key (reads from env if not provided)
    
    Returns:
        Initialized adapter
    """
    return PublicTradingAdapter(secret_key=secret_key)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("Public.com Individual Trading API - Test Script")
    print("="*60)
    
    # Initialize adapter (reads from PUBLIC_SECRET_KEY env var)
    try:
        adapter = PublicTradingAdapter()
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\nSet your secret key:")
        print("  export PUBLIC_SECRET_KEY='your_secret_key_here'")
        print("\nOr pass it directly:")
        print("  adapter = PublicTradingAdapter(secret_key='your_key')")
        sys.exit(1)
    
    # Test 1: Get accounts
    print("\n" + "="*60)
    print("TEST 1: Get Accounts")
    print("="*60)
    
    try:
        accounts = adapter.get_accounts()
        print(f"✅ Found {len(accounts)} account(s)")
        
        if accounts:
            account = accounts[0]
            print(f"\nPrimary Account:")
            print(f"  ID: {account.get('accountId')}")
            print(f"  Type: {account.get('accountType')}")
            print(f"  Options Level: {account.get('optionsLevel')}")
            print(f"  Account Type: {account.get('brokerageAccountType')}")
            
            account_id = account["accountId"]
        else:
            print("❌ No accounts found")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)
    
    # Test 2: Get portfolio
    print("\n" + "="*60)
    print("TEST 2: Get Portfolio")
    print("="*60)
    
    try:
        portfolio = adapter.get_portfolio(account_id)
        
        positions = portfolio.get("positions", [])
        print(f"✅ Portfolio fetched")
        print(f"  Positions: {len(positions)}")
        
        if positions:
            print(f"\nSample position:")
            pos = positions[0]
            print(f"  Symbol: {pos.get('instrument', {}).get('symbol')}")
            print(f"  Quantity: {pos.get('quantity')}")
            print(f"  Market Value: ${pos.get('marketValue', 0):.2f}")
        
        equity = portfolio.get("equity", {})
        if equity:
            print(f"\nEquity:")
            print(f"  Total: ${equity.get('total', 0):.2f}")
            print(f"  Cash: ${equity.get('cash', 0):.2f}")
        
        buying_power = portfolio.get("buyingPower", {})
        if buying_power:
            print(f"\nBuying Power:")
            print(f"  Cash: ${buying_power.get('cash', 0):.2f}")
            print(f"  Stock: ${buying_power.get('stock', 0):.2f}")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 3: Get quotes
    print("\n" + "="*60)
    print("TEST 3: Get Quotes")
    print("="*60)
    
    try:
        quotes_response = adapter.get_quotes(account_id, [
            {"symbol": "SPY", "type": "EQUITY"},
            {"symbol": "AAPL", "type": "EQUITY"},
            {"symbol": "MSFT", "type": "EQUITY"}
        ])
        
        print(f"✅ Quotes fetched")
        
        for quote in quotes_response.get("quotes", []):
            if quote.get("outcome") == "SUCCESS":
                symbol = quote["instrument"]["symbol"]
                last = quote["last"]
                bid = quote.get("bid", "N/A")
                ask = quote.get("ask", "N/A")
                volume = quote.get("volume", 0)
                
                print(f"\n{symbol}:")
                print(f"  Last: ${last}")
                print(f"  Bid/Ask: ${bid} / ${ask}")
                print(f"  Volume: {volume:,}")
            else:
                symbol = quote["instrument"]["symbol"]
                outcome = quote.get("outcome")
                print(f"\n{symbol}: {outcome}")
                
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    # Test 4: Get history (last 7 days)
    print("\n" + "="*60)
    print("TEST 4: Get History (Last 7 Days)")
    print("="*60)
    
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        
        history = adapter.get_history(
            account_id,
            start=start,
            end=end,
            page_size=10
        )
        
        transactions = history.get("transactions", [])
        print(f"✅ History fetched: {len(transactions)} transaction(s)")
        
        if transactions:
            print(f"\nRecent transactions:")
            for tx in transactions[:3]:  # Show first 3
                tx_type = tx.get("type", "Unknown")
                amount = tx.get("amount", 0)
                symbol = tx.get("instrument", {}).get("symbol", "N/A")
                timestamp = tx.get("timestamp", "N/A")
                print(f"  {tx_type}: {symbol} ${amount:.2f} at {timestamp}")
        
        if history.get("nextToken"):
            print(f"\n  (More pages available)")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
