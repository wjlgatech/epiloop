#!/usr/bin/env python3
"""
Yahoo Finance API Client

Provides Python interface to Yahoo Finance for stock data including:
- Real-time quotes (price, volume, market cap)
- Financials (revenue, earnings, PE ratio)
- Historical prices
- Paper trading mode (simulated trades, no real execution)

DISCLAIMER: This is research synthesis, NOT financial advice.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
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
class StockQuote:
    """Real-time stock quote data."""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    avg_volume: int
    market_cap: float
    pe_ratio: Optional[float]
    eps: Optional[float]
    dividend_yield: Optional[float]
    fifty_two_week_high: float
    fifty_two_week_low: float
    timestamp: str
    exchange: str
    currency: str

    @property
    def disclaimer(self) -> str:
        return (
            "DISCLAIMER: This is research synthesis, NOT financial advice. "
            "Past performance does not guarantee future results. "
            "Never invest more than you can afford to lose."
        )


@dataclass
class StockFinancials:
    """Company financial data."""
    symbol: str
    revenue: Optional[float]
    revenue_growth: Optional[float]
    gross_profit: Optional[float]
    operating_income: Optional[float]
    net_income: Optional[float]
    eps: Optional[float]
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    price_to_book: Optional[float]
    price_to_sales: Optional[float]
    debt_to_equity: Optional[float]
    current_ratio: Optional[float]
    return_on_equity: Optional[float]
    profit_margin: Optional[float]
    fiscal_year_end: Optional[str]
    most_recent_quarter: Optional[str]

    @property
    def disclaimer(self) -> str:
        return (
            "DISCLAIMER: This is research synthesis, NOT financial advice. "
            "Past performance does not guarantee future results. "
            "Never invest more than you can afford to lose."
        )


@dataclass
class HistoricalPrice:
    """Single historical price point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


@dataclass
class PaperTrade:
    """Paper trading transaction record."""
    trade_id: str
    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: int
    price: float
    timestamp: str
    paper_mode: bool = True

    @property
    def total_value(self) -> float:
        return self.quantity * self.price


class YahooFinanceClient:
    """Client for Yahoo Finance data with paper trading support."""

    # Using yfinance-style endpoints (unofficial)
    BASE_URL = "https://query1.finance.yahoo.com"

    def __init__(
        self,
        rate_limit_seconds: float = 0.5,
        paper_trading: bool = True
    ):
        """
        Initialize Yahoo Finance client.

        Args:
            rate_limit_seconds: Minimum seconds between requests
            paper_trading: Enable paper trading mode (always True by default)
        """
        self.rate_limit_seconds = rate_limit_seconds
        self.paper_trading = paper_trading  # ALWAYS paper trading by default
        self.last_request_time = 0.0

        # Verify paper trading is enabled
        if not self.paper_trading:
            print(
                "WARNING: Paper trading mode disabled. "
                "This is for research only, NOT financial advice.",
                file=sys.stderr
            )

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        self._rate_limit()

        headers = {
            "User-Agent": "Mozilla/5.0 (research-tool)"
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise YahooFinanceError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise YahooFinanceError(f"URL error: {e.reason}")
        except json.JSONDecodeError as e:
            raise YahooFinanceError(f"Failed to parse response: {e}")

    def get_quote(self, symbol: str) -> StockQuote:
        """
        Get real-time quote for a stock.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

        Returns:
            StockQuote with current price and metrics

        Example:
            >>> client = YahooFinanceClient()
            >>> quote = client.get_quote('AAPL')
            >>> print(f"{quote.symbol}: ${quote.price}")
        """
        url = f"{self.BASE_URL}/v6/finance/quote?symbols={symbol.upper()}"

        try:
            data = self._make_request(url)
            result = data.get("quoteResponse", {}).get("result", [])

            if not result:
                raise YahooFinanceError(f"No data found for symbol: {symbol}")

            q = result[0]

            return StockQuote(
                symbol=q.get("symbol", symbol.upper()),
                price=q.get("regularMarketPrice", 0.0),
                change=q.get("regularMarketChange", 0.0),
                change_percent=q.get("regularMarketChangePercent", 0.0),
                volume=q.get("regularMarketVolume", 0),
                avg_volume=q.get("averageDailyVolume3Month", 0),
                market_cap=q.get("marketCap", 0.0),
                pe_ratio=q.get("trailingPE"),
                eps=q.get("epsTrailingTwelveMonths"),
                dividend_yield=q.get("dividendYield"),
                fifty_two_week_high=q.get("fiftyTwoWeekHigh", 0.0),
                fifty_two_week_low=q.get("fiftyTwoWeekLow", 0.0),
                timestamp=datetime.now().isoformat(),
                exchange=q.get("exchange", ""),
                currency=q.get("currency", "USD")
            )

        except Exception as e:
            raise YahooFinanceError(f"Failed to get quote for {symbol}: {e}")

    def get_financials(self, symbol: str) -> StockFinancials:
        """
        Get financial data for a stock.

        Args:
            symbol: Stock ticker symbol

        Returns:
            StockFinancials with revenue, earnings, ratios

        Example:
            >>> client = YahooFinanceClient()
            >>> fin = client.get_financials('AAPL')
            >>> print(f"PE Ratio: {fin.pe_ratio}")
        """
        modules = "financialData,defaultKeyStatistics,incomeStatementHistory"
        url = f"{self.BASE_URL}/v10/finance/quoteSummary/{symbol.upper()}?modules={modules}"

        try:
            data = self._make_request(url)
            result = data.get("quoteSummary", {}).get("result", [])

            if not result:
                raise YahooFinanceError(f"No financial data for symbol: {symbol}")

            info = result[0]
            fin_data = info.get("financialData", {})
            key_stats = info.get("defaultKeyStatistics", {})

            def get_raw(d: Dict, key: str) -> Optional[float]:
                """Extract raw value from nested dict."""
                val = d.get(key, {})
                if isinstance(val, dict):
                    return val.get("raw")
                return val

            return StockFinancials(
                symbol=symbol.upper(),
                revenue=get_raw(fin_data, "totalRevenue"),
                revenue_growth=get_raw(fin_data, "revenueGrowth"),
                gross_profit=get_raw(fin_data, "grossProfits"),
                operating_income=get_raw(fin_data, "operatingCashflow"),
                net_income=get_raw(key_stats, "netIncomeToCommon"),
                eps=get_raw(key_stats, "trailingEps"),
                pe_ratio=get_raw(key_stats, "trailingPE"),
                forward_pe=get_raw(key_stats, "forwardPE"),
                price_to_book=get_raw(key_stats, "priceToBook"),
                price_to_sales=get_raw(key_stats, "priceToSalesTrailing12Months"),
                debt_to_equity=get_raw(fin_data, "debtToEquity"),
                current_ratio=get_raw(fin_data, "currentRatio"),
                return_on_equity=get_raw(fin_data, "returnOnEquity"),
                profit_margin=get_raw(fin_data, "profitMargins"),
                fiscal_year_end=key_stats.get("lastFiscalYearEnd", {}).get("fmt"),
                most_recent_quarter=key_stats.get("mostRecentQuarter", {}).get("fmt")
            )

        except Exception as e:
            raise YahooFinanceError(f"Failed to get financials for {symbol}: {e}")

    def get_historical_prices(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d"
    ) -> List[HistoricalPrice]:
        """
        Get historical price data.

        Args:
            symbol: Stock ticker symbol
            period: Time period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            interval: Data interval ('1m', '5m', '15m', '1h', '1d', '1wk', '1mo')

        Returns:
            List of HistoricalPrice objects

        Example:
            >>> client = YahooFinanceClient()
            >>> history = client.get_historical_prices('AAPL', period='3mo')
            >>> for day in history[-5:]:
            ...     print(f"{day.date}: ${day.close}")
        """
        url = (
            f"{self.BASE_URL}/v8/finance/chart/{symbol.upper()}"
            f"?range={period}&interval={interval}"
        )

        try:
            data = self._make_request(url)
            chart = data.get("chart", {}).get("result", [])

            if not chart:
                raise YahooFinanceError(f"No historical data for symbol: {symbol}")

            result = chart[0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {})
            quote = indicators.get("quote", [{}])[0]
            adjclose = indicators.get("adjclose", [{}])[0]

            prices = []
            for i, ts in enumerate(timestamps):
                prices.append(HistoricalPrice(
                    date=datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                    open=quote.get("open", [0])[i] or 0,
                    high=quote.get("high", [0])[i] or 0,
                    low=quote.get("low", [0])[i] or 0,
                    close=quote.get("close", [0])[i] or 0,
                    adj_close=adjclose.get("adjclose", [0])[i] or 0 if adjclose else 0,
                    volume=quote.get("volume", [0])[i] or 0
                ))

            return prices

        except Exception as e:
            raise YahooFinanceError(f"Failed to get history for {symbol}: {e}")

    def paper_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        price: Optional[float] = None
    ) -> PaperTrade:
        """
        Execute a paper trade (simulated, no real money).

        Args:
            symbol: Stock ticker symbol
            action: 'buy' or 'sell'
            quantity: Number of shares
            price: Price per share (uses current price if None)

        Returns:
            PaperTrade record

        Note:
            This is PAPER TRADING only - no real orders are placed.
            For research and learning purposes only.
        """
        if not self.paper_trading:
            raise YahooFinanceError(
                "Paper trading is disabled. Enable paper_trading=True for simulated trades."
            )

        if action.lower() not in ('buy', 'sell'):
            raise YahooFinanceError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

        # Get current price if not specified
        if price is None:
            quote = self.get_quote(symbol)
            price = quote.price

        trade = PaperTrade(
            trade_id=f"PAPER-{symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            symbol=symbol.upper(),
            action=action.lower(),
            quantity=quantity,
            price=price,
            timestamp=datetime.now().isoformat(),
            paper_mode=True
        )

        return trade


class YahooFinanceError(Exception):
    """Exception for Yahoo Finance client errors."""
    pass


def main():
    """CLI interface for Yahoo Finance client."""
    import argparse

    # Print disclaimer first
    print("=" * 70)
    print("DISCLAIMER: This is research synthesis, NOT financial advice.")
    print("Past performance does not guarantee future results.")
    print("Never invest more than you can afford to lose.")
    print("PAPER TRADING MODE - No real money involved.")
    print("=" * 70)
    print()

    parser = argparse.ArgumentParser(
        description="Yahoo Finance client for stock research (PAPER TRADING ONLY)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Quote command
    quote_parser = subparsers.add_parser("quote", help="Get stock quote")
    quote_parser.add_argument("symbol", help="Stock ticker symbol")
    quote_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Financials command
    fin_parser = subparsers.add_parser("financials", help="Get financial data")
    fin_parser.add_argument("symbol", help="Stock ticker symbol")
    fin_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # History command
    hist_parser = subparsers.add_parser("history", help="Get historical prices")
    hist_parser.add_argument("symbol", help="Stock ticker symbol")
    hist_parser.add_argument("--period", default="1mo", help="Time period (1d,5d,1mo,3mo,6mo,1y)")
    hist_parser.add_argument("--interval", default="1d", help="Data interval (1d,1wk,1mo)")
    hist_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Paper trade command
    trade_parser = subparsers.add_parser("paper-trade", help="Execute paper trade")
    trade_parser.add_argument("action", choices=["buy", "sell"], help="Trade action")
    trade_parser.add_argument("symbol", help="Stock ticker symbol")
    trade_parser.add_argument("quantity", type=int, help="Number of shares")
    trade_parser.add_argument("--price", type=float, help="Price per share (uses current if omitted)")
    trade_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    client = YahooFinanceClient(paper_trading=True)

    try:
        if args.command == "quote":
            quote = client.get_quote(args.symbol)
            if args.json:
                print(json.dumps({
                    "symbol": quote.symbol,
                    "price": quote.price,
                    "change": quote.change,
                    "change_percent": quote.change_percent,
                    "volume": quote.volume,
                    "market_cap": quote.market_cap,
                    "pe_ratio": quote.pe_ratio,
                    "eps": quote.eps,
                    "52_week_high": quote.fifty_two_week_high,
                    "52_week_low": quote.fifty_two_week_low,
                    "timestamp": quote.timestamp,
                    "disclaimer": quote.disclaimer
                }, indent=2))
            else:
                print(f"\n{quote.symbol} Stock Quote")
                print("-" * 40)
                print(f"Price:          ${quote.price:.2f}")
                print(f"Change:         ${quote.change:.2f} ({quote.change_percent:.2f}%)")
                print(f"Volume:         {quote.volume:,}")
                print(f"Avg Volume:     {quote.avg_volume:,}")
                print(f"Market Cap:     ${quote.market_cap:,.0f}")
                print(f"PE Ratio:       {quote.pe_ratio or 'N/A'}")
                print(f"EPS:            ${quote.eps or 'N/A'}")
                print(f"52-Week High:   ${quote.fifty_two_week_high:.2f}")
                print(f"52-Week Low:    ${quote.fifty_two_week_low:.2f}")
                print(f"\nTimestamp: {quote.timestamp}")

        elif args.command == "financials":
            fin = client.get_financials(args.symbol)
            if args.json:
                print(json.dumps({
                    "symbol": fin.symbol,
                    "revenue": fin.revenue,
                    "revenue_growth": fin.revenue_growth,
                    "net_income": fin.net_income,
                    "eps": fin.eps,
                    "pe_ratio": fin.pe_ratio,
                    "forward_pe": fin.forward_pe,
                    "price_to_book": fin.price_to_book,
                    "debt_to_equity": fin.debt_to_equity,
                    "return_on_equity": fin.return_on_equity,
                    "profit_margin": fin.profit_margin,
                    "disclaimer": fin.disclaimer
                }, indent=2))
            else:
                print(f"\n{fin.symbol} Financial Data")
                print("-" * 40)
                print(f"Revenue:        ${fin.revenue:,.0f}" if fin.revenue else "Revenue: N/A")
                print(f"Revenue Growth: {fin.revenue_growth:.2%}" if fin.revenue_growth else "Revenue Growth: N/A")
                print(f"Net Income:     ${fin.net_income:,.0f}" if fin.net_income else "Net Income: N/A")
                print(f"EPS:            ${fin.eps:.2f}" if fin.eps else "EPS: N/A")
                print(f"PE Ratio:       {fin.pe_ratio:.2f}" if fin.pe_ratio else "PE Ratio: N/A")
                print(f"Forward PE:     {fin.forward_pe:.2f}" if fin.forward_pe else "Forward PE: N/A")
                print(f"Price/Book:     {fin.price_to_book:.2f}" if fin.price_to_book else "Price/Book: N/A")
                print(f"Debt/Equity:    {fin.debt_to_equity:.2f}" if fin.debt_to_equity else "Debt/Equity: N/A")
                print(f"ROE:            {fin.return_on_equity:.2%}" if fin.return_on_equity else "ROE: N/A")
                print(f"Profit Margin:  {fin.profit_margin:.2%}" if fin.profit_margin else "Profit Margin: N/A")

        elif args.command == "history":
            history = client.get_historical_prices(
                args.symbol,
                period=args.period,
                interval=args.interval
            )
            if args.json:
                print(json.dumps([{
                    "date": h.date,
                    "open": h.open,
                    "high": h.high,
                    "low": h.low,
                    "close": h.close,
                    "volume": h.volume
                } for h in history], indent=2))
            else:
                print(f"\n{args.symbol} Historical Prices ({args.period}, {args.interval})")
                print("-" * 60)
                print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
                print("-" * 60)
                for h in history[-20:]:  # Last 20 entries
                    print(f"{h.date:<12} {h.open:>10.2f} {h.high:>10.2f} {h.low:>10.2f} {h.close:>10.2f} {h.volume:>12,}")

        elif args.command == "paper-trade":
            trade = client.paper_trade(
                args.symbol,
                args.action,
                args.quantity,
                args.price
            )
            if args.json:
                print(json.dumps({
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "action": trade.action,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "total_value": trade.total_value,
                    "timestamp": trade.timestamp,
                    "paper_mode": trade.paper_mode,
                    "disclaimer": "PAPER TRADE - No real money involved"
                }, indent=2))
            else:
                print(f"\nPAPER TRADE EXECUTED")
                print("=" * 40)
                print(f"Trade ID:    {trade.trade_id}")
                print(f"Action:      {trade.action.upper()}")
                print(f"Symbol:      {trade.symbol}")
                print(f"Quantity:    {trade.quantity}")
                print(f"Price:       ${trade.price:.2f}")
                print(f"Total Value: ${trade.total_value:.2f}")
                print(f"Timestamp:   {trade.timestamp}")
                print("=" * 40)
                print("*** PAPER TRADE - No real money involved ***")

        return 0

    except YahooFinanceError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
