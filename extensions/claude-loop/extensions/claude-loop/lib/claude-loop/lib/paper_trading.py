#!/usr/bin/env python3
"""
Paper Trading System

Simulated trading system for educational purposes.
Tracks paper positions, records entry/exit prices, calculates P&L.
Stores all data in data/paper_trades.json.

DISCLAIMER: This is for educational purposes only, NOT financial advice.
Paper trading mode - no real money involved.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# Default data directory and file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
TRADES_FILE = os.path.join(DATA_DIR, 'paper_trades.json')


class TradeAction(str, Enum):
    """Trade action types."""
    BUY = "buy"
    SELL = "sell"


class AssetType(str, Enum):
    """Asset type classification."""
    STOCK = "stock"
    CRYPTO = "crypto"
    OPTION = "option"
    ETF = "etf"


@dataclass
class PaperTrade:
    """Individual paper trade record."""
    trade_id: str
    symbol: str
    asset_type: str
    action: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: str
    notes: str = ""

    @property
    def total_value(self) -> float:
        return self.quantity * self.price


@dataclass
class Position:
    """Current position in an asset."""
    symbol: str
    asset_type: str
    quantity: float
    avg_cost: float
    total_cost: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    def update_price(self, price: float):
        """Update position with current price."""
        self.current_price = price
        if self.quantity > 0:
            current_value = self.quantity * price
            self.unrealized_pnl = current_value - self.total_cost
            self.unrealized_pnl_pct = (self.unrealized_pnl / self.total_cost) * 100 if self.total_cost > 0 else 0


@dataclass
class Portfolio:
    """Paper trading portfolio."""
    initial_balance: float = 100000.0
    cash_balance: float = 100000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[PaperTrade] = field(default_factory=list)
    realized_pnl: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    @property
    def total_invested(self) -> float:
        return sum(p.total_cost for p in self.positions.values())

    @property
    def total_value(self) -> float:
        positions_value = sum(
            p.quantity * p.current_price
            for p in self.positions.values()
        )
        return self.cash_balance + positions_value

    @property
    def total_pnl(self) -> float:
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.realized_pnl + unrealized

    @property
    def total_pnl_pct(self) -> float:
        if self.initial_balance > 0:
            return (self.total_pnl / self.initial_balance) * 100
        return 0.0


class PaperTradingSystem:
    """Paper trading system with persistence."""

    DISCLAIMER = (
        "DISCLAIMER: This is paper trading for educational purposes only. "
        "NOT financial advice. No real money involved. "
        "Past performance does not guarantee future results. "
        "Never invest more than you can afford to lose."
    )

    def __init__(self, data_file: str = TRADES_FILE, initial_balance: float = 100000.0):
        """
        Initialize paper trading system.

        Args:
            data_file: Path to JSON file for persistence
            initial_balance: Starting paper money balance
        """
        self.data_file = data_file
        self.initial_balance = initial_balance
        self.portfolio = self._load_or_create_portfolio()

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        data_dir = os.path.dirname(self.data_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _load_or_create_portfolio(self) -> Portfolio:
        """Load existing portfolio or create new one."""
        self._ensure_data_dir()

        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)

                # Reconstruct portfolio
                portfolio = Portfolio(
                    initial_balance=data.get('initial_balance', self.initial_balance),
                    cash_balance=data.get('cash_balance', self.initial_balance),
                    realized_pnl=data.get('realized_pnl', 0.0),
                    created_at=data.get('created_at', ''),
                    updated_at=data.get('updated_at', '')
                )

                # Reconstruct positions
                for symbol, pos_data in data.get('positions', {}).items():
                    portfolio.positions[symbol] = Position(**pos_data)

                # Reconstruct trades
                for trade_data in data.get('trades', []):
                    portfolio.trades.append(PaperTrade(**trade_data))

                return portfolio

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load portfolio, creating new one: {e}", file=sys.stderr)

        return Portfolio(initial_balance=self.initial_balance, cash_balance=self.initial_balance)

    def _save_portfolio(self):
        """Save portfolio to JSON file."""
        self._ensure_data_dir()
        self.portfolio.updated_at = datetime.now().isoformat()

        data = {
            'initial_balance': self.portfolio.initial_balance,
            'cash_balance': self.portfolio.cash_balance,
            'realized_pnl': self.portfolio.realized_pnl,
            'created_at': self.portfolio.created_at,
            'updated_at': self.portfolio.updated_at,
            'positions': {
                symbol: asdict(pos)
                for symbol, pos in self.portfolio.positions.items()
            },
            'trades': [asdict(trade) for trade in self.portfolio.trades],
            'disclaimer': self.DISCLAIMER
        }

        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        asset_type: str = "stock",
        notes: str = ""
    ) -> PaperTrade:
        """
        Execute a paper buy order.

        Args:
            symbol: Asset symbol
            quantity: Number of units to buy
            price: Price per unit
            asset_type: Type of asset (stock, crypto, etc.)
            notes: Optional trade notes

        Returns:
            PaperTrade record

        Raises:
            ValueError: If insufficient funds
        """
        total_cost = quantity * price

        if total_cost > self.portfolio.cash_balance:
            raise ValueError(
                f"Insufficient funds. Required: ${total_cost:.2f}, "
                f"Available: ${self.portfolio.cash_balance:.2f}"
            )

        # Create trade record
        trade = PaperTrade(
            trade_id=f"PAPER-{uuid.uuid4().hex[:8].upper()}",
            symbol=symbol.upper(),
            asset_type=asset_type,
            action=TradeAction.BUY.value,
            quantity=quantity,
            price=price,
            timestamp=datetime.now().isoformat(),
            notes=notes
        )

        # Update cash
        self.portfolio.cash_balance -= total_cost

        # Update or create position
        if symbol.upper() in self.portfolio.positions:
            pos = self.portfolio.positions[symbol.upper()]
            new_quantity = pos.quantity + quantity
            new_total_cost = pos.total_cost + total_cost
            pos.quantity = new_quantity
            pos.total_cost = new_total_cost
            pos.avg_cost = new_total_cost / new_quantity
            pos.current_price = price
        else:
            self.portfolio.positions[symbol.upper()] = Position(
                symbol=symbol.upper(),
                asset_type=asset_type,
                quantity=quantity,
                avg_cost=price,
                total_cost=total_cost,
                current_price=price
            )

        # Record trade
        self.portfolio.trades.append(trade)

        # Save
        self._save_portfolio()

        return trade

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        notes: str = ""
    ) -> PaperTrade:
        """
        Execute a paper sell order.

        Args:
            symbol: Asset symbol
            quantity: Number of units to sell
            price: Price per unit
            notes: Optional trade notes

        Returns:
            PaperTrade record

        Raises:
            ValueError: If insufficient position
        """
        symbol = symbol.upper()

        if symbol not in self.portfolio.positions:
            raise ValueError(f"No position in {symbol}")

        pos = self.portfolio.positions[symbol]

        if quantity > pos.quantity:
            raise ValueError(
                f"Insufficient position. Requested: {quantity}, "
                f"Available: {pos.quantity}"
            )

        # Calculate realized P&L
        cost_basis = pos.avg_cost * quantity
        sale_proceeds = quantity * price
        realized_gain = sale_proceeds - cost_basis

        # Create trade record
        trade = PaperTrade(
            trade_id=f"PAPER-{uuid.uuid4().hex[:8].upper()}",
            symbol=symbol,
            asset_type=pos.asset_type,
            action=TradeAction.SELL.value,
            quantity=quantity,
            price=price,
            timestamp=datetime.now().isoformat(),
            notes=notes
        )

        # Update cash
        self.portfolio.cash_balance += sale_proceeds

        # Update realized P&L
        self.portfolio.realized_pnl += realized_gain

        # Update position
        pos.quantity -= quantity
        pos.total_cost -= cost_basis

        if pos.quantity <= 0:
            del self.portfolio.positions[symbol]
        else:
            pos.current_price = price
            pos.update_price(price)

        # Record trade
        self.portfolio.trades.append(trade)

        # Save
        self._save_portfolio()

        return trade

    def update_prices(self, prices: Dict[str, float]):
        """
        Update position prices.

        Args:
            prices: Dict of symbol -> current price
        """
        for symbol, price in prices.items():
            if symbol.upper() in self.portfolio.positions:
                self.portfolio.positions[symbol.upper()].update_price(price)

        self._save_portfolio()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        return {
            'initial_balance': self.portfolio.initial_balance,
            'cash_balance': self.portfolio.cash_balance,
            'total_invested': self.portfolio.total_invested,
            'total_value': self.portfolio.total_value,
            'realized_pnl': self.portfolio.realized_pnl,
            'unrealized_pnl': sum(p.unrealized_pnl for p in self.portfolio.positions.values()),
            'total_pnl': self.portfolio.total_pnl,
            'total_pnl_pct': self.portfolio.total_pnl_pct,
            'positions_count': len(self.portfolio.positions),
            'trades_count': len(self.portfolio.trades),
            'created_at': self.portfolio.created_at,
            'updated_at': self.portfolio.updated_at,
            'disclaimer': self.DISCLAIMER
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions."""
        return [
            {
                'symbol': p.symbol,
                'asset_type': p.asset_type,
                'quantity': p.quantity,
                'avg_cost': p.avg_cost,
                'total_cost': p.total_cost,
                'current_price': p.current_price,
                'current_value': p.quantity * p.current_price,
                'unrealized_pnl': p.unrealized_pnl,
                'unrealized_pnl_pct': p.unrealized_pnl_pct
            }
            for p in self.portfolio.positions.values()
        ]

    def get_trades(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trade history."""
        trades = self.portfolio.trades

        if symbol:
            trades = [t for t in trades if t.symbol == symbol.upper()]

        # Return most recent first
        trades = sorted(trades, key=lambda t: t.timestamp, reverse=True)[:limit]

        return [asdict(t) for t in trades]

    def reset_portfolio(self, initial_balance: float = 100000.0):
        """Reset portfolio to initial state."""
        self.portfolio = Portfolio(
            initial_balance=initial_balance,
            cash_balance=initial_balance
        )
        self._save_portfolio()

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate portfolio metrics."""
        trades = self.portfolio.trades

        if not trades:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'win_rate': 0.0,
                'disclaimer': self.DISCLAIMER
            }

        buy_trades = [t for t in trades if t.action == TradeAction.BUY.value]
        sell_trades = [t for t in trades if t.action == TradeAction.SELL.value]

        # Calculate win rate from closed positions (simplified)
        # In real implementation, would track each trade's outcome
        winning_trades = 0
        losing_trades = 0

        # Simple heuristic: if we have realized gains, count as wins
        if self.portfolio.realized_pnl > 0:
            winning_trades = len(sell_trades)
        else:
            losing_trades = len(sell_trades)

        total_closed = winning_trades + losing_trades
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0

        return {
            'total_trades': len(trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_buy_value': sum(t.total_value for t in buy_trades),
            'total_sell_value': sum(t.total_value for t in sell_trades),
            'realized_pnl': self.portfolio.realized_pnl,
            'win_rate': win_rate,
            'disclaimer': self.DISCLAIMER
        }


def main():
    """CLI interface for paper trading system."""
    import argparse

    # Print disclaimer first
    print("=" * 70)
    print("PAPER TRADING SYSTEM - EDUCATIONAL USE ONLY")
    print("=" * 70)
    print("DISCLAIMER: This is for educational purposes only, NOT financial advice.")
    print("No real money is involved. Past performance does not guarantee future results.")
    print("Never invest more than you can afford to lose.")
    print("=" * 70)
    print()

    parser = argparse.ArgumentParser(
        description="Paper Trading System (Educational Only)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Buy command
    buy_parser = subparsers.add_parser("buy", help="Execute paper buy")
    buy_parser.add_argument("symbol", help="Asset symbol")
    buy_parser.add_argument("quantity", type=float, help="Quantity to buy")
    buy_parser.add_argument("price", type=float, help="Price per unit")
    buy_parser.add_argument("--type", default="stock", help="Asset type (stock, crypto, etf)")
    buy_parser.add_argument("--notes", default="", help="Trade notes")

    # Sell command
    sell_parser = subparsers.add_parser("sell", help="Execute paper sell")
    sell_parser.add_argument("symbol", help="Asset symbol")
    sell_parser.add_argument("quantity", type=float, help="Quantity to sell")
    sell_parser.add_argument("price", type=float, help="Price per unit")
    sell_parser.add_argument("--notes", default="", help="Trade notes")

    # Portfolio command
    portfolio_parser = subparsers.add_parser("portfolio", help="View portfolio")
    portfolio_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Positions command
    positions_parser = subparsers.add_parser("positions", help="View positions")
    positions_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Trades command
    trades_parser = subparsers.add_parser("trades", help="View trade history")
    trades_parser.add_argument("--symbol", help="Filter by symbol")
    trades_parser.add_argument("--limit", type=int, default=20, help="Number of trades")
    trades_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="View portfolio metrics")
    metrics_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset portfolio")
    reset_parser.add_argument("--balance", type=float, default=100000, help="Initial balance")
    reset_parser.add_argument("--confirm", action="store_true", help="Confirm reset")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    system = PaperTradingSystem()

    try:
        if args.command == "buy":
            trade = system.buy(
                args.symbol,
                args.quantity,
                args.price,
                asset_type=args.type,
                notes=args.notes
            )
            print(f"\nPAPER BUY EXECUTED")
            print("=" * 40)
            print(f"Trade ID:    {trade.trade_id}")
            print(f"Symbol:      {trade.symbol}")
            print(f"Quantity:    {trade.quantity}")
            print(f"Price:       ${trade.price:.4f}")
            print(f"Total:       ${trade.total_value:.2f}")
            print(f"Timestamp:   {trade.timestamp}")
            print("=" * 40)
            print(f"Cash Balance: ${system.portfolio.cash_balance:.2f}")
            print("*** PAPER TRADE - No real money ***")

        elif args.command == "sell":
            trade = system.sell(
                args.symbol,
                args.quantity,
                args.price,
                notes=args.notes
            )
            print(f"\nPAPER SELL EXECUTED")
            print("=" * 40)
            print(f"Trade ID:    {trade.trade_id}")
            print(f"Symbol:      {trade.symbol}")
            print(f"Quantity:    {trade.quantity}")
            print(f"Price:       ${trade.price:.4f}")
            print(f"Total:       ${trade.total_value:.2f}")
            print(f"Timestamp:   {trade.timestamp}")
            print("=" * 40)
            print(f"Cash Balance: ${system.portfolio.cash_balance:.2f}")
            print(f"Realized P&L: ${system.portfolio.realized_pnl:.2f}")
            print("*** PAPER TRADE - No real money ***")

        elif args.command == "portfolio":
            summary = system.get_portfolio_summary()
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                print("\nPAPER TRADING PORTFOLIO")
                print("=" * 50)
                print(f"Initial Balance:   ${summary['initial_balance']:,.2f}")
                print(f"Cash Balance:      ${summary['cash_balance']:,.2f}")
                print(f"Total Invested:    ${summary['total_invested']:,.2f}")
                print(f"Portfolio Value:   ${summary['total_value']:,.2f}")
                print("-" * 50)
                print(f"Realized P&L:      ${summary['realized_pnl']:,.2f}")
                print(f"Unrealized P&L:    ${summary['unrealized_pnl']:,.2f}")
                print(f"Total P&L:         ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")
                print("-" * 50)
                print(f"Open Positions:    {summary['positions_count']}")
                print(f"Total Trades:      {summary['trades_count']}")
                print(f"Created:           {summary['created_at'][:10]}")
                print("=" * 50)
                print("*** PAPER TRADING - No real money ***")

        elif args.command == "positions":
            positions = system.get_positions()
            if args.json:
                print(json.dumps(positions, indent=2))
            else:
                print("\nOPEN POSITIONS")
                print("=" * 80)
                if not positions:
                    print("No open positions.")
                else:
                    print(f"{'Symbol':<10} {'Type':<8} {'Qty':>10} {'Avg Cost':>12} {'Curr Price':>12} {'P&L':>12} {'P&L %':>8}")
                    print("-" * 80)
                    for p in positions:
                        print(f"{p['symbol']:<10} {p['asset_type']:<8} {p['quantity']:>10.4f} ${p['avg_cost']:>10.2f} ${p['current_price']:>10.2f} ${p['unrealized_pnl']:>10.2f} {p['unrealized_pnl_pct']:>7.2f}%")
                print("=" * 80)
                print("*** PAPER TRADING - No real money ***")

        elif args.command == "trades":
            trades = system.get_trades(symbol=args.symbol, limit=args.limit)
            if args.json:
                print(json.dumps(trades, indent=2))
            else:
                print("\nTRADE HISTORY")
                print("=" * 90)
                if not trades:
                    print("No trades recorded.")
                else:
                    print(f"{'Trade ID':<20} {'Action':<6} {'Symbol':<8} {'Qty':>10} {'Price':>12} {'Total':>14}")
                    print("-" * 90)
                    for t in trades:
                        print(f"{t['trade_id']:<20} {t['action'].upper():<6} {t['symbol']:<8} {t['quantity']:>10.4f} ${t['price']:>10.4f} ${t['quantity']*t['price']:>12.2f}")
                print("=" * 90)
                print("*** PAPER TRADING - No real money ***")

        elif args.command == "metrics":
            metrics = system.calculate_metrics()
            if args.json:
                print(json.dumps(metrics, indent=2))
            else:
                print("\nPORTFOLIO METRICS")
                print("=" * 40)
                print(f"Total Trades:     {metrics['total_trades']}")
                print(f"Buy Trades:       {metrics['buy_trades']}")
                print(f"Sell Trades:      {metrics['sell_trades']}")
                if 'total_buy_value' in metrics:
                    print(f"Total Bought:     ${metrics['total_buy_value']:,.2f}")
                    print(f"Total Sold:       ${metrics['total_sell_value']:,.2f}")
                print(f"Realized P&L:     ${metrics['realized_pnl']:,.2f}")
                print(f"Win Rate:         {metrics['win_rate']:.1f}%")
                print("=" * 40)
                print("*** PAPER TRADING - No real money ***")

        elif args.command == "reset":
            if not args.confirm:
                print("WARNING: This will delete all paper trades and positions!")
                print("Use --confirm to proceed.")
                return 1
            system.reset_portfolio(args.balance)
            print(f"\nPortfolio reset to ${args.balance:,.2f}")
            print("*** PAPER TRADING - No real money ***")

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
