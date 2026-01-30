#!/usr/bin/env python3
"""
CoinGecko API Client

Provides Python interface to CoinGecko API for cryptocurrency data:
- Token info (price, market cap, 24h change)
- Historical prices
- Trending tokens
- Paper trading mode (simulated trades, no real execution)

API Documentation: https://www.coingecko.com/en/api/documentation

DISCLAIMER: This is research synthesis, NOT financial advice.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
Cryptocurrency is highly volatile and speculative.
"""

import urllib.request
import urllib.parse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta


@dataclass
class TokenInfo:
    """Cryptocurrency token information."""
    id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float
    market_cap_rank: Optional[int]
    total_volume: float
    price_change_24h: float
    price_change_percentage_24h: float
    price_change_percentage_7d: Optional[float]
    price_change_percentage_30d: Optional[float]
    circulating_supply: float
    total_supply: Optional[float]
    max_supply: Optional[float]
    ath: float  # All-time high
    ath_change_percentage: float
    atl: float  # All-time low
    atl_change_percentage: float
    last_updated: str

    @property
    def disclaimer(self) -> str:
        return (
            "DISCLAIMER: This is research synthesis, NOT financial advice. "
            "Cryptocurrency is highly volatile and speculative. "
            "Past performance does not guarantee future results. "
            "Never invest more than you can afford to lose."
        )


@dataclass
class TokenDetail:
    """Detailed token information including description and links."""
    id: str
    symbol: str
    name: str
    description: str
    homepage: Optional[str]
    blockchain_site: Optional[str]
    github_repos: List[str]
    twitter_handle: Optional[str]
    subreddit: Optional[str]
    categories: List[str]
    genesis_date: Optional[str]
    sentiment_votes_up_percentage: Optional[float]
    sentiment_votes_down_percentage: Optional[float]
    market_data: Optional[TokenInfo]

    @property
    def disclaimer(self) -> str:
        return (
            "DISCLAIMER: This is research synthesis, NOT financial advice. "
            "Cryptocurrency is highly volatile and speculative. "
            "Past performance does not guarantee future results. "
            "Never invest more than you can afford to lose."
        )


@dataclass
class HistoricalPrice:
    """Single historical price point for crypto."""
    timestamp: str
    price: float
    market_cap: float
    volume: float


@dataclass
class TrendingToken:
    """Trending cryptocurrency token."""
    id: str
    symbol: str
    name: str
    market_cap_rank: Optional[int]
    thumb: str  # Thumbnail URL
    score: int  # Trending score


@dataclass
class CryptoPaperTrade:
    """Paper trading transaction record for crypto."""
    trade_id: str
    token_id: str
    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: str
    paper_mode: bool = True

    @property
    def total_value(self) -> float:
        return self.quantity * self.price


class CoinGeckoClient:
    """Client for CoinGecko cryptocurrency data with paper trading support."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        paper_trading: bool = True
    ):
        """
        Initialize CoinGecko client.

        Args:
            rate_limit_seconds: Minimum seconds between requests
            paper_trading: Enable paper trading mode (always True by default)
        """
        self.rate_limit_seconds = rate_limit_seconds
        self.paper_trading = paper_trading
        self.last_request_time = 0.0

        # Verify paper trading is enabled
        if not self.paper_trading:
            print(
                "WARNING: Paper trading mode disabled. "
                "This is for research only, NOT financial advice. "
                "Crypto is highly volatile.",
                file=sys.stderr
            )

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """Make HTTP request with error handling."""
        self._rate_limit()

        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "User-Agent": "Mozilla/5.0 (research-tool)",
            "Accept": "application/json"
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise CoinGeckoError("Rate limit exceeded. Please wait before retrying.")
            raise CoinGeckoError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise CoinGeckoError(f"URL error: {e.reason}")
        except json.JSONDecodeError as e:
            raise CoinGeckoError(f"Failed to parse response: {e}")

    def get_token_info(
        self,
        token_id: str,
        vs_currency: str = "usd"
    ) -> TokenInfo:
        """
        Get current token information.

        Args:
            token_id: CoinGecko token ID (e.g., 'bitcoin', 'ethereum')
            vs_currency: Target currency (default: usd)

        Returns:
            TokenInfo with current price and metrics

        Example:
            >>> client = CoinGeckoClient()
            >>> btc = client.get_token_info('bitcoin')
            >>> print(f"BTC: ${btc.current_price:,.2f}")
        """
        params = {
            "vs_currency": vs_currency,
            "ids": token_id,
            "order": "market_cap_desc",
            "per_page": 1,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d"
        }

        try:
            data = self._make_request("/coins/markets", params)

            if not data:
                raise CoinGeckoError(f"No data found for token: {token_id}")

            token = data[0]

            return TokenInfo(
                id=token.get("id", token_id),
                symbol=token.get("symbol", "").upper(),
                name=token.get("name", ""),
                current_price=token.get("current_price", 0.0),
                market_cap=token.get("market_cap", 0.0),
                market_cap_rank=token.get("market_cap_rank"),
                total_volume=token.get("total_volume", 0.0),
                price_change_24h=token.get("price_change_24h", 0.0),
                price_change_percentage_24h=token.get("price_change_percentage_24h", 0.0),
                price_change_percentage_7d=token.get("price_change_percentage_7d_in_currency"),
                price_change_percentage_30d=token.get("price_change_percentage_30d_in_currency"),
                circulating_supply=token.get("circulating_supply", 0.0),
                total_supply=token.get("total_supply"),
                max_supply=token.get("max_supply"),
                ath=token.get("ath", 0.0),
                ath_change_percentage=token.get("ath_change_percentage", 0.0),
                atl=token.get("atl", 0.0),
                atl_change_percentage=token.get("atl_change_percentage", 0.0),
                last_updated=token.get("last_updated", datetime.now().isoformat())
            )

        except Exception as e:
            if isinstance(e, CoinGeckoError):
                raise
            raise CoinGeckoError(f"Failed to get token info for {token_id}: {e}")

    def get_token_detail(self, token_id: str) -> TokenDetail:
        """
        Get detailed token information including description.

        Args:
            token_id: CoinGecko token ID

        Returns:
            TokenDetail with description, links, and categories
        """
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false"
        }

        try:
            data = self._make_request(f"/coins/{token_id}", params)

            links = data.get("links", {})
            community = data.get("community_data", {})
            market = data.get("market_data", {})

            # Extract market data into TokenInfo if available
            market_info = None
            if market:
                market_info = TokenInfo(
                    id=data.get("id", token_id),
                    symbol=data.get("symbol", "").upper(),
                    name=data.get("name", ""),
                    current_price=market.get("current_price", {}).get("usd", 0.0),
                    market_cap=market.get("market_cap", {}).get("usd", 0.0),
                    market_cap_rank=market.get("market_cap_rank"),
                    total_volume=market.get("total_volume", {}).get("usd", 0.0),
                    price_change_24h=market.get("price_change_24h", 0.0),
                    price_change_percentage_24h=market.get("price_change_percentage_24h", 0.0),
                    price_change_percentage_7d=market.get("price_change_percentage_7d"),
                    price_change_percentage_30d=market.get("price_change_percentage_30d"),
                    circulating_supply=market.get("circulating_supply", 0.0),
                    total_supply=market.get("total_supply"),
                    max_supply=market.get("max_supply"),
                    ath=market.get("ath", {}).get("usd", 0.0),
                    ath_change_percentage=market.get("ath_change_percentage", {}).get("usd", 0.0),
                    atl=market.get("atl", {}).get("usd", 0.0),
                    atl_change_percentage=market.get("atl_change_percentage", {}).get("usd", 0.0),
                    last_updated=market.get("last_updated", datetime.now().isoformat())
                )

            return TokenDetail(
                id=data.get("id", token_id),
                symbol=data.get("symbol", "").upper(),
                name=data.get("name", ""),
                description=data.get("description", {}).get("en", "")[:500],  # Truncate long descriptions
                homepage=links.get("homepage", [None])[0],
                blockchain_site=links.get("blockchain_site", [None])[0],
                github_repos=links.get("repos_url", {}).get("github", []),
                twitter_handle=links.get("twitter_screen_name"),
                subreddit=links.get("subreddit_url"),
                categories=data.get("categories", []),
                genesis_date=data.get("genesis_date"),
                sentiment_votes_up_percentage=data.get("sentiment_votes_up_percentage"),
                sentiment_votes_down_percentage=data.get("sentiment_votes_down_percentage"),
                market_data=market_info
            )

        except Exception as e:
            if isinstance(e, CoinGeckoError):
                raise
            raise CoinGeckoError(f"Failed to get token detail for {token_id}: {e}")

    def get_historical_prices(
        self,
        token_id: str,
        days: int = 30,
        vs_currency: str = "usd"
    ) -> List[HistoricalPrice]:
        """
        Get historical price data.

        Args:
            token_id: CoinGecko token ID
            days: Number of days of data (1, 7, 14, 30, 90, 180, 365, max)
            vs_currency: Target currency

        Returns:
            List of HistoricalPrice objects

        Example:
            >>> client = CoinGeckoClient()
            >>> history = client.get_historical_prices('bitcoin', days=30)
            >>> for day in history[-5:]:
            ...     print(f"{day.timestamp}: ${day.price:,.2f}")
        """
        params = {
            "vs_currency": vs_currency,
            "days": days
        }

        try:
            data = self._make_request(f"/coins/{token_id}/market_chart", params)

            prices = data.get("prices", [])
            market_caps = data.get("market_caps", [])
            volumes = data.get("total_volumes", [])

            history = []
            for i, (ts, price) in enumerate(prices):
                history.append(HistoricalPrice(
                    timestamp=datetime.fromtimestamp(ts / 1000).isoformat(),
                    price=price,
                    market_cap=market_caps[i][1] if i < len(market_caps) else 0.0,
                    volume=volumes[i][1] if i < len(volumes) else 0.0
                ))

            return history

        except Exception as e:
            if isinstance(e, CoinGeckoError):
                raise
            raise CoinGeckoError(f"Failed to get history for {token_id}: {e}")

    def get_trending(self) -> List[TrendingToken]:
        """
        Get trending tokens (top 7 on CoinGecko).

        Returns:
            List of TrendingToken objects

        Example:
            >>> client = CoinGeckoClient()
            >>> trending = client.get_trending()
            >>> for token in trending:
            ...     print(f"{token.name} ({token.symbol})")
        """
        try:
            data = self._make_request("/search/trending")
            coins = data.get("coins", [])

            trending = []
            for coin_wrapper in coins:
                coin = coin_wrapper.get("item", {})
                trending.append(TrendingToken(
                    id=coin.get("id", ""),
                    symbol=coin.get("symbol", "").upper(),
                    name=coin.get("name", ""),
                    market_cap_rank=coin.get("market_cap_rank"),
                    thumb=coin.get("thumb", ""),
                    score=coin.get("score", 0)
                ))

            return trending

        except Exception as e:
            if isinstance(e, CoinGeckoError):
                raise
            raise CoinGeckoError(f"Failed to get trending tokens: {e}")

    def search_tokens(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for tokens by name or symbol.

        Args:
            query: Search query

        Returns:
            List of matching token info dicts
        """
        params = {"query": query}

        try:
            data = self._make_request("/search", params)
            return data.get("coins", [])[:10]  # Return top 10 matches

        except Exception as e:
            if isinstance(e, CoinGeckoError):
                raise
            raise CoinGeckoError(f"Failed to search for '{query}': {e}")

    def paper_trade(
        self,
        token_id: str,
        action: str,
        quantity: float,
        price: Optional[float] = None
    ) -> CryptoPaperTrade:
        """
        Execute a paper trade (simulated, no real money).

        Args:
            token_id: CoinGecko token ID
            action: 'buy' or 'sell'
            quantity: Amount of tokens
            price: Price per token (uses current price if None)

        Returns:
            CryptoPaperTrade record

        Note:
            This is PAPER TRADING only - no real orders are placed.
            Crypto is highly volatile and speculative.
        """
        if not self.paper_trading:
            raise CoinGeckoError(
                "Paper trading is disabled. Enable paper_trading=True for simulated trades."
            )

        if action.lower() not in ('buy', 'sell'):
            raise CoinGeckoError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

        # Get current price if not specified
        if price is None:
            token = self.get_token_info(token_id)
            price = token.current_price
            symbol = token.symbol
        else:
            symbol = token_id.upper()

        trade = CryptoPaperTrade(
            trade_id=f"PAPER-CRYPTO-{token_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            token_id=token_id,
            symbol=symbol,
            action=action.lower(),
            quantity=quantity,
            price=price,
            timestamp=datetime.now().isoformat(),
            paper_mode=True
        )

        return trade


class CoinGeckoError(Exception):
    """Exception for CoinGecko client errors."""
    pass


def main():
    """CLI interface for CoinGecko client."""
    import argparse

    # Print disclaimer first
    print("=" * 70)
    print("DISCLAIMER: This is research synthesis, NOT financial advice.")
    print("Cryptocurrency is HIGHLY VOLATILE and SPECULATIVE.")
    print("Past performance does not guarantee future results.")
    print("Never invest more than you can afford to lose.")
    print("PAPER TRADING MODE - No real money involved.")
    print("=" * 70)
    print()

    parser = argparse.ArgumentParser(
        description="CoinGecko client for crypto research (PAPER TRADING ONLY)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Token info command
    info_parser = subparsers.add_parser("info", help="Get token info")
    info_parser.add_argument("token_id", help="CoinGecko token ID (e.g., bitcoin, ethereum)")
    info_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Token detail command
    detail_parser = subparsers.add_parser("detail", help="Get detailed token info")
    detail_parser.add_argument("token_id", help="CoinGecko token ID")
    detail_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # History command
    hist_parser = subparsers.add_parser("history", help="Get historical prices")
    hist_parser.add_argument("token_id", help="CoinGecko token ID")
    hist_parser.add_argument("--days", type=int, default=30, help="Number of days (1,7,14,30,90,180,365)")
    hist_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Trending command
    trend_parser = subparsers.add_parser("trending", help="Get trending tokens")
    trend_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for tokens")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Paper trade command
    trade_parser = subparsers.add_parser("paper-trade", help="Execute paper trade")
    trade_parser.add_argument("action", choices=["buy", "sell"], help="Trade action")
    trade_parser.add_argument("token_id", help="CoinGecko token ID")
    trade_parser.add_argument("quantity", type=float, help="Amount of tokens")
    trade_parser.add_argument("--price", type=float, help="Price per token (uses current if omitted)")
    trade_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    client = CoinGeckoClient(paper_trading=True)

    try:
        if args.command == "info":
            token = client.get_token_info(args.token_id)
            if args.json:
                print(json.dumps({
                    "id": token.id,
                    "symbol": token.symbol,
                    "name": token.name,
                    "current_price": token.current_price,
                    "market_cap": token.market_cap,
                    "market_cap_rank": token.market_cap_rank,
                    "total_volume": token.total_volume,
                    "price_change_24h": token.price_change_24h,
                    "price_change_percentage_24h": token.price_change_percentage_24h,
                    "circulating_supply": token.circulating_supply,
                    "ath": token.ath,
                    "atl": token.atl,
                    "last_updated": token.last_updated,
                    "disclaimer": token.disclaimer
                }, indent=2))
            else:
                print(f"\n{token.name} ({token.symbol})")
                print("-" * 50)
                print(f"Price:          ${token.current_price:,.6f}")
                print(f"24h Change:     ${token.price_change_24h:,.2f} ({token.price_change_percentage_24h:.2f}%)")
                print(f"Market Cap:     ${token.market_cap:,.0f}")
                print(f"Rank:           #{token.market_cap_rank}" if token.market_cap_rank else "Rank: N/A")
                print(f"24h Volume:     ${token.total_volume:,.0f}")
                print(f"Circulating:    {token.circulating_supply:,.0f}")
                print(f"All-Time High:  ${token.ath:,.2f} ({token.ath_change_percentage:.2f}% from ATH)")
                print(f"All-Time Low:   ${token.atl:,.6f}")
                print(f"\nLast Updated: {token.last_updated}")

        elif args.command == "detail":
            detail = client.get_token_detail(args.token_id)
            if args.json:
                print(json.dumps({
                    "id": detail.id,
                    "symbol": detail.symbol,
                    "name": detail.name,
                    "description": detail.description[:200] + "..." if len(detail.description) > 200 else detail.description,
                    "homepage": detail.homepage,
                    "categories": detail.categories,
                    "genesis_date": detail.genesis_date,
                    "sentiment_up": detail.sentiment_votes_up_percentage,
                    "sentiment_down": detail.sentiment_votes_down_percentage,
                    "disclaimer": detail.disclaimer
                }, indent=2))
            else:
                print(f"\n{detail.name} ({detail.symbol}) - Detail")
                print("-" * 50)
                if detail.description:
                    desc = detail.description[:300] + "..." if len(detail.description) > 300 else detail.description
                    print(f"Description: {desc}")
                print(f"Categories: {', '.join(detail.categories[:5])}" if detail.categories else "")
                print(f"Genesis: {detail.genesis_date}" if detail.genesis_date else "")
                print(f"Homepage: {detail.homepage}" if detail.homepage else "")
                if detail.sentiment_votes_up_percentage:
                    print(f"Sentiment: {detail.sentiment_votes_up_percentage:.0f}% up / {detail.sentiment_votes_down_percentage:.0f}% down")

        elif args.command == "history":
            history = client.get_historical_prices(args.token_id, days=args.days)
            if args.json:
                print(json.dumps([{
                    "timestamp": h.timestamp,
                    "price": h.price,
                    "market_cap": h.market_cap,
                    "volume": h.volume
                } for h in history], indent=2))
            else:
                print(f"\n{args.token_id} Price History ({args.days} days)")
                print("-" * 60)
                print(f"{'Timestamp':<25} {'Price':>15} {'Volume':>18}")
                print("-" * 60)
                # Show every nth entry to fit ~20 rows
                step = max(1, len(history) // 20)
                for h in history[::step]:
                    print(f"{h.timestamp:<25} ${h.price:>14,.2f} ${h.volume:>14,.0f}")

        elif args.command == "trending":
            trending = client.get_trending()
            if args.json:
                print(json.dumps([{
                    "id": t.id,
                    "symbol": t.symbol,
                    "name": t.name,
                    "market_cap_rank": t.market_cap_rank,
                    "score": t.score
                } for t in trending], indent=2))
            else:
                print("\nTrending Cryptocurrencies")
                print("-" * 50)
                for i, t in enumerate(trending, 1):
                    rank_str = f"#{t.market_cap_rank}" if t.market_cap_rank else "N/A"
                    print(f"{i}. {t.name} ({t.symbol}) - Rank: {rank_str}")

        elif args.command == "search":
            results = client.search_tokens(args.query)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"\nSearch Results for '{args.query}'")
                print("-" * 50)
                for r in results:
                    print(f"- {r.get('name', 'N/A')} ({r.get('symbol', 'N/A').upper()}) - ID: {r.get('id', 'N/A')}")

        elif args.command == "paper-trade":
            trade = client.paper_trade(
                args.token_id,
                args.action,
                args.quantity,
                args.price
            )
            if args.json:
                print(json.dumps({
                    "trade_id": trade.trade_id,
                    "token_id": trade.token_id,
                    "symbol": trade.symbol,
                    "action": trade.action,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "total_value": trade.total_value,
                    "timestamp": trade.timestamp,
                    "paper_mode": trade.paper_mode,
                    "disclaimer": "PAPER TRADE - No real money involved. Crypto is highly volatile."
                }, indent=2))
            else:
                print(f"\nPAPER TRADE EXECUTED")
                print("=" * 50)
                print(f"Trade ID:    {trade.trade_id}")
                print(f"Action:      {trade.action.upper()}")
                print(f"Token:       {trade.symbol} ({trade.token_id})")
                print(f"Quantity:    {trade.quantity}")
                print(f"Price:       ${trade.price:,.6f}")
                print(f"Total Value: ${trade.total_value:,.2f}")
                print(f"Timestamp:   {trade.timestamp}")
                print("=" * 50)
                print("*** PAPER TRADE - No real money involved ***")
                print("*** Crypto is HIGHLY VOLATILE ***")

        return 0

    except CoinGeckoError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
