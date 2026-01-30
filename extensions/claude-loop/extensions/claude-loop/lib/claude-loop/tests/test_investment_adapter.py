#!/usr/bin/env python3
"""
Tests for Investment Research Adapter (US-009)

Tests the complete investment research adapter including:
- Yahoo Finance client
- CoinGecko client
- Paper trading system
- Investment agents
- Quality gates
- End-to-end investment research queries

DISCLAIMER: This is for testing purposes only, NOT financial advice.
Paper trading mode - no real money involved.
"""

import pytest
import sys
import os
import yaml
import json
import tempfile
from datetime import datetime, timedelta

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Import using importlib for modules
import importlib.util


def load_module(name, path):
    """Load a module from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load modules
lib_path = os.path.join(os.path.dirname(__file__), '..', 'lib')

yahoo_module = load_module(
    "yahoo_finance_client",
    os.path.join(lib_path, 'yahoo_finance_client.py')
)
YahooFinanceClient = yahoo_module.YahooFinanceClient
StockQuote = yahoo_module.StockQuote
StockFinancials = yahoo_module.StockFinancials
HistoricalPrice = yahoo_module.HistoricalPrice
PaperTrade = yahoo_module.PaperTrade
YahooFinanceError = yahoo_module.YahooFinanceError

coingecko_module = load_module(
    "coingecko_client",
    os.path.join(lib_path, 'coingecko_client.py')
)
CoinGeckoClient = coingecko_module.CoinGeckoClient
TokenInfo = coingecko_module.TokenInfo
TokenDetail = coingecko_module.TokenDetail
TrendingToken = coingecko_module.TrendingToken
CryptoPaperTrade = coingecko_module.CryptoPaperTrade
CoinGeckoError = coingecko_module.CoinGeckoError

paper_trading_module = load_module(
    "paper_trading",
    os.path.join(lib_path, 'paper_trading.py')
)
PaperTradingSystem = paper_trading_module.PaperTradingSystem
Portfolio = paper_trading_module.Portfolio
Position = paper_trading_module.Position


class TestYahooFinanceClient:
    """Test Yahoo Finance API client."""

    def test_client_initialization(self):
        """Test client initializes with paper trading enabled by default."""
        client = YahooFinanceClient()
        assert client.paper_trading is True
        assert client.rate_limit_seconds == 0.5

    def test_client_paper_trading_default(self):
        """Test that paper trading is on by default."""
        client = YahooFinanceClient()
        assert client.paper_trading is True

    def test_stock_quote_dataclass(self):
        """Test StockQuote dataclass structure."""
        quote = StockQuote(
            symbol="AAPL",
            price=175.50,
            change=2.50,
            change_percent=1.45,
            volume=50000000,
            avg_volume=60000000,
            market_cap=2800000000000,
            pe_ratio=28.5,
            eps=6.15,
            dividend_yield=0.5,
            fifty_two_week_high=199.62,
            fifty_two_week_low=124.17,
            timestamp="2024-01-15T10:00:00",
            exchange="NASDAQ",
            currency="USD"
        )

        assert quote.symbol == "AAPL"
        assert quote.price == 175.50
        assert quote.pe_ratio == 28.5
        assert "NOT financial advice" in quote.disclaimer

    def test_stock_financials_dataclass(self):
        """Test StockFinancials dataclass structure."""
        financials = StockFinancials(
            symbol="AAPL",
            revenue=383285000000,
            revenue_growth=0.08,
            gross_profit=170782000000,
            operating_income=114301000000,
            net_income=96995000000,
            eps=6.15,
            pe_ratio=28.5,
            forward_pe=26.2,
            price_to_book=47.5,
            price_to_sales=7.8,
            debt_to_equity=1.81,
            current_ratio=0.99,
            return_on_equity=1.47,
            profit_margin=0.25,
            fiscal_year_end="2023-09-30",
            most_recent_quarter="2023-12-30"
        )

        assert financials.symbol == "AAPL"
        assert financials.revenue > 0
        assert financials.pe_ratio == 28.5
        assert "NOT financial advice" in financials.disclaimer

    def test_historical_price_dataclass(self):
        """Test HistoricalPrice dataclass structure."""
        price = HistoricalPrice(
            date="2024-01-15",
            open=174.50,
            high=176.25,
            low=173.80,
            close=175.50,
            adj_close=175.50,
            volume=50000000
        )

        assert price.date == "2024-01-15"
        assert price.close == 175.50

    def test_paper_trade_dataclass(self):
        """Test PaperTrade dataclass structure."""
        trade = PaperTrade(
            trade_id="PAPER-AAPL-20240115",
            symbol="AAPL",
            action="buy",
            quantity=100,
            price=175.50,
            timestamp="2024-01-15T10:00:00",
            paper_mode=True
        )

        assert trade.symbol == "AAPL"
        assert trade.action == "buy"
        assert trade.quantity == 100
        assert trade.paper_mode is True
        assert trade.total_value == 17550.0

    def test_paper_trade_requires_paper_mode(self):
        """Test that paper trading is enforced."""
        client = YahooFinanceClient(paper_trading=True)

        # Should work in paper trading mode
        trade = client.paper_trade("AAPL", "buy", 100, price=175.50)
        assert trade.paper_mode is True

    def test_paper_trade_invalid_action(self):
        """Test that invalid trade actions are rejected."""
        client = YahooFinanceClient(paper_trading=True)

        with pytest.raises(YahooFinanceError):
            client.paper_trade("AAPL", "invalid", 100, price=175.50)


class TestCoinGeckoClient:
    """Test CoinGecko API client."""

    def test_client_initialization(self):
        """Test client initializes with paper trading enabled."""
        client = CoinGeckoClient()
        assert client.paper_trading is True
        assert client.rate_limit_seconds == 1.0

    def test_client_paper_trading_default(self):
        """Test that paper trading is on by default."""
        client = CoinGeckoClient()
        assert client.paper_trading is True

    def test_token_info_dataclass(self):
        """Test TokenInfo dataclass structure."""
        token = TokenInfo(
            id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            current_price=45000.0,
            market_cap=880000000000,
            market_cap_rank=1,
            total_volume=25000000000,
            price_change_24h=500.0,
            price_change_percentage_24h=1.12,
            price_change_percentage_7d=5.5,
            price_change_percentage_30d=-2.3,
            circulating_supply=19500000,
            total_supply=21000000,
            max_supply=21000000,
            ath=69000.0,
            ath_change_percentage=-34.8,
            atl=67.81,
            atl_change_percentage=66300.0,
            last_updated="2024-01-15T10:00:00Z"
        )

        assert token.id == "bitcoin"
        assert token.symbol == "BTC"
        assert token.current_price == 45000.0
        assert token.market_cap_rank == 1
        assert "highly volatile" in token.disclaimer

    def test_trending_token_dataclass(self):
        """Test TrendingToken dataclass structure."""
        trending = TrendingToken(
            id="bonk",
            symbol="BONK",
            name="Bonk",
            market_cap_rank=100,
            thumb="https://example.com/thumb.png",
            score=0
        )

        assert trending.id == "bonk"
        assert trending.symbol == "BONK"

    def test_crypto_paper_trade_dataclass(self):
        """Test CryptoPaperTrade dataclass structure."""
        trade = CryptoPaperTrade(
            trade_id="PAPER-CRYPTO-bitcoin-20240115",
            token_id="bitcoin",
            symbol="BTC",
            action="buy",
            quantity=0.5,
            price=45000.0,
            timestamp="2024-01-15T10:00:00",
            paper_mode=True
        )

        assert trade.token_id == "bitcoin"
        assert trade.symbol == "BTC"
        assert trade.quantity == 0.5
        assert trade.paper_mode is True
        assert trade.total_value == 22500.0

    def test_paper_trade_requires_paper_mode(self):
        """Test that paper trading is enforced."""
        client = CoinGeckoClient(paper_trading=True)

        trade = client.paper_trade("bitcoin", "buy", 0.5, price=45000.0)
        assert trade.paper_mode is True

    def test_paper_trade_invalid_action(self):
        """Test that invalid trade actions are rejected."""
        client = CoinGeckoClient(paper_trading=True)

        with pytest.raises(CoinGeckoError):
            client.paper_trade("bitcoin", "invalid", 0.5, price=45000.0)


class TestPaperTradingSystem:
    """Test paper trading system."""

    @pytest.fixture
    def temp_data_file(self):
        """Create a temporary data file for testing."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_system_initialization(self, temp_data_file):
        """Test paper trading system initializes correctly."""
        system = PaperTradingSystem(data_file=temp_data_file)

        assert system.portfolio.initial_balance == 100000.0
        assert system.portfolio.cash_balance == 100000.0
        assert len(system.portfolio.positions) == 0
        assert len(system.portfolio.trades) == 0

    def test_system_custom_balance(self, temp_data_file):
        """Test initialization with custom balance."""
        system = PaperTradingSystem(data_file=temp_data_file, initial_balance=50000.0)

        assert system.portfolio.initial_balance == 50000.0
        assert system.portfolio.cash_balance == 50000.0

    def test_buy_order(self, temp_data_file):
        """Test executing a paper buy order."""
        system = PaperTradingSystem(data_file=temp_data_file)

        trade = system.buy("AAPL", 100, 175.50, asset_type="stock")

        assert trade.symbol == "AAPL"
        assert trade.action == "buy"
        assert trade.quantity == 100
        assert trade.price == 175.50

        # Check portfolio updated
        assert system.portfolio.cash_balance == 100000.0 - (100 * 175.50)
        assert "AAPL" in system.portfolio.positions
        assert system.portfolio.positions["AAPL"].quantity == 100

    def test_buy_insufficient_funds(self, temp_data_file):
        """Test buy order with insufficient funds."""
        system = PaperTradingSystem(data_file=temp_data_file)

        with pytest.raises(ValueError, match="Insufficient funds"):
            system.buy("AAPL", 1000, 175.50)  # Would cost $175,500

    def test_sell_order(self, temp_data_file):
        """Test executing a paper sell order."""
        system = PaperTradingSystem(data_file=temp_data_file)

        # First buy
        system.buy("AAPL", 100, 175.50)

        # Then sell at profit
        trade = system.sell("AAPL", 50, 180.00)

        assert trade.symbol == "AAPL"
        assert trade.action == "sell"
        assert trade.quantity == 50

        # Check position reduced
        assert system.portfolio.positions["AAPL"].quantity == 50

        # Check realized P&L
        expected_pnl = 50 * (180.00 - 175.50)  # $225 profit
        assert system.portfolio.realized_pnl == expected_pnl

    def test_sell_insufficient_position(self, temp_data_file):
        """Test sell order with insufficient position."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.50)

        with pytest.raises(ValueError, match="Insufficient position"):
            system.sell("AAPL", 200, 180.00)

    def test_sell_no_position(self, temp_data_file):
        """Test sell order with no position."""
        system = PaperTradingSystem(data_file=temp_data_file)

        with pytest.raises(ValueError, match="No position"):
            system.sell("AAPL", 100, 180.00)

    def test_position_closed_on_full_sell(self, temp_data_file):
        """Test that position is removed when fully sold."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.50)
        system.sell("AAPL", 100, 180.00)

        assert "AAPL" not in system.portfolio.positions

    def test_multiple_buys_average_cost(self, temp_data_file):
        """Test average cost calculation on multiple buys."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.00)
        system.buy("AAPL", 100, 185.00)

        position = system.portfolio.positions["AAPL"]
        assert position.quantity == 200
        assert position.avg_cost == 180.00  # (100*175 + 100*185) / 200

    def test_portfolio_summary(self, temp_data_file):
        """Test portfolio summary calculation."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.50)

        summary = system.get_portfolio_summary()

        assert summary['initial_balance'] == 100000.0
        assert summary['cash_balance'] == 100000.0 - 17550.0
        assert summary['positions_count'] == 1
        assert summary['trades_count'] == 1
        assert "DISCLAIMER" in summary['disclaimer']

    def test_persistence(self, temp_data_file):
        """Test portfolio persistence to file."""
        # Create system and make trades
        system1 = PaperTradingSystem(data_file=temp_data_file)
        system1.buy("AAPL", 100, 175.50)
        system1.buy("BTC", 0.5, 45000.0, asset_type="crypto")

        # Load in new system instance
        system2 = PaperTradingSystem(data_file=temp_data_file)

        assert len(system2.portfolio.positions) == 2
        assert "AAPL" in system2.portfolio.positions
        assert "BTC" in system2.portfolio.positions
        assert len(system2.portfolio.trades) == 2

    def test_reset_portfolio(self, temp_data_file):
        """Test portfolio reset."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.50)
        system.reset_portfolio(initial_balance=50000.0)

        assert system.portfolio.initial_balance == 50000.0
        assert system.portfolio.cash_balance == 50000.0
        assert len(system.portfolio.positions) == 0
        assert len(system.portfolio.trades) == 0

    def test_metrics_calculation(self, temp_data_file):
        """Test portfolio metrics calculation."""
        system = PaperTradingSystem(data_file=temp_data_file)

        system.buy("AAPL", 100, 175.50)
        system.sell("AAPL", 50, 180.00)

        metrics = system.calculate_metrics()

        assert metrics['total_trades'] == 2
        assert metrics['buy_trades'] == 1
        assert metrics['sell_trades'] == 1
        assert "DISCLAIMER" in metrics['disclaimer']


class TestAdapterConfiguration:
    """Test adapter.yaml configuration."""

    def test_adapter_yaml_exists(self):
        """Test that adapter.yaml file exists."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

    def test_adapter_yaml_structure(self):
        """Test adapter.yaml has required structure."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check required fields
        assert config['name'] == 'investment'
        assert 'description' in config
        assert 'version' in config

        # Check paper trading is enabled by default
        assert 'paper_trading' in config
        assert config['paper_trading']['enabled'] is True

        # Check domain configuration
        assert 'domain' in config
        assert 'keywords' in config['domain']
        assert 'asset_classes' in config['domain']

        # Check asset classes
        asset_classes = config['domain']['asset_classes']
        assert 'stocks' in asset_classes
        assert 'crypto' in asset_classes
        assert 'options' in asset_classes
        assert 'real_estate' in asset_classes

    def test_data_sources_configured(self):
        """Test data sources are configured."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'sources' in config
        sources = config['sources']

        assert 'yahoo_finance' in sources
        assert sources['yahoo_finance']['enabled'] is True

        assert 'coingecko' in sources
        assert sources['coingecko']['enabled'] is True

        assert 'sec_edgar' in sources
        assert sources['sec_edgar']['enabled'] is True

    def test_quality_gates_configured(self):
        """Test quality gates are configured."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'quality_gates' in config
        gates = config['quality_gates']

        assert 'source_recency' in gates
        assert gates['source_recency']['enabled'] is True

        assert 'confirmation_bias' in gates
        assert gates['confirmation_bias']['enabled'] is True
        assert gates['confirmation_bias']['requirements'][0] == 'require_bear_case'

        assert 'risk_disclosure' in gates
        assert gates['risk_disclosure']['enabled'] is True

        assert 'liquidity_check' in gates
        assert gates['liquidity_check']['enabled'] is True

        assert 'backtesting_caveat' in gates
        assert gates['backtesting_caveat']['enabled'] is True

    def test_mandatory_disclaimer_configured(self):
        """Test mandatory disclaimer is in config."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'output' in config
        assert 'mandatory_disclaimer' in config['output']

        disclaimer = config['output']['mandatory_disclaimer']
        assert 'NOT financial advice' in disclaimer
        assert 'Past performance' in disclaimer
        assert 'afford to lose' in disclaimer


class TestInvestmentAgents:
    """Test investment analysis agents."""

    def test_fundamental_analyst_exists(self):
        """Test that fundamental-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'fundamental-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_fundamental_analyst_structure(self):
        """Test fundamental analyst has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'fundamental-analyst.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for disclaimer
        assert 'NOT financial advice' in content
        assert 'Paper trading' in content

        # Check for required sections
        assert '# Fundamental Analyst Agent' in content
        assert 'Financial Statement Analysis' in content
        assert 'Valuation Analysis' in content
        assert 'Competitive Moat' in content

        # Check for key metrics
        assert 'P/E' in content or 'PE' in content
        assert 'ROE' in content
        assert 'Revenue' in content

    def test_technical_analyst_exists(self):
        """Test that technical-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'technical-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_technical_analyst_structure(self):
        """Test technical analyst has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'technical-analyst.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for disclaimer
        assert 'NOT financial advice' in content
        assert 'Paper trading' in content

        # Check for required sections
        assert '# Technical Analyst Agent' in content
        assert 'Chart Pattern' in content
        assert 'Momentum Indicator' in content
        assert 'Support' in content
        assert 'Resistance' in content

        # Check for key indicators
        assert 'RSI' in content
        assert 'MACD' in content
        assert 'Moving Average' in content

    def test_risk_assessor_exists(self):
        """Test that risk-assessor.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'risk-assessor.md'
        )
        assert os.path.exists(agent_path)

    def test_risk_assessor_structure(self):
        """Test risk assessor has required sections."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'risk-assessor.md'
        )

        with open(agent_path, 'r') as f:
            content = f.read()

        # Check for disclaimer
        assert 'NOT financial advice' in content
        assert 'Paper trading' in content

        # Check for required sections
        assert '# Risk Assessor Agent' in content
        assert 'Volatility' in content
        assert 'Drawdown' in content
        assert 'Correlation' in content
        assert 'Position Sizing' in content

        # Check for key metrics
        assert 'Max Drawdown' in content or 'Maximum Drawdown' in content
        assert 'VaR' in content or 'Value at Risk' in content


class TestQualityGates:
    """Test investment quality gates."""

    def test_quality_gates_file_exists(self):
        """Test quality_gates.md exists."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_quality_gates_coverage(self):
        """Test quality gates cover required areas."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'prompts',
            'quality_gates.md'
        )

        with open(gates_path, 'r') as f:
            content = f.read()

        # Check for mandatory disclaimer
        assert 'NOT financial advice' in content

        # Check for required gates
        assert 'Gate 1: Source Recency' in content
        assert 'Gate 2: Confirmation Bias' in content
        assert 'Gate 3: Risk Disclosure' in content
        assert 'Gate 4: Liquidity' in content
        assert 'Gate 5: Backtesting' in content

        # Check for specific requirements
        assert 'require_bear_case' in content
        assert 'require_bull_case' in content
        assert 'paper_trading_notice' in content


class TestEndToEndInvestmentQuery:
    """Test end-to-end investment research query flow."""

    def test_sample_stock_query_components(self):
        """Test that all components are in place for stock research."""
        # 1. Verify Yahoo Finance client exists and can be instantiated
        client = YahooFinanceClient(paper_trading=True)
        assert hasattr(client, 'get_quote')
        assert hasattr(client, 'get_financials')
        assert hasattr(client, 'get_historical_prices')
        assert hasattr(client, 'paper_trade')

        # 2. Verify fundamental analyst agent exists
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'fundamental-analyst.md'
        )
        assert os.path.exists(agent_path)

        # 3. Verify technical analyst agent exists
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'technical-analyst.md'
        )
        assert os.path.exists(agent_path)

        # 4. Verify risk assessor exists
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'risk-assessor.md'
        )
        assert os.path.exists(agent_path)

    def test_sample_crypto_query_components(self):
        """Test that all components are in place for crypto research."""
        # 1. Verify CoinGecko client exists and can be instantiated
        client = CoinGeckoClient(paper_trading=True)
        assert hasattr(client, 'get_token_info')
        assert hasattr(client, 'get_historical_prices')
        assert hasattr(client, 'get_trending')
        assert hasattr(client, 'paper_trade')

        # 2. Verify adapter config has crypto asset class
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )
        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'crypto' in config['domain']['asset_classes']
        assert config['domain']['asset_classes']['crypto']['enabled'] is True

    def test_paper_trading_integration(self):
        """Test paper trading system integration."""
        # Use temporary file for test
        fd, temp_path = tempfile.mkstemp(suffix='.json')
        os.close(fd)

        try:
            # 1. Create paper trading system
            system = PaperTradingSystem(data_file=temp_path)

            # 2. Execute paper trades
            system.buy("AAPL", 100, 175.50, asset_type="stock")
            system.buy("bitcoin", 0.5, 45000.0, asset_type="crypto")

            # 3. Check portfolio
            summary = system.get_portfolio_summary()
            assert summary['positions_count'] == 2

            # 4. Sell one position
            system.sell("AAPL", 50, 180.00)

            # 5. Verify metrics
            metrics = system.calculate_metrics()
            assert metrics['total_trades'] == 3
            assert metrics['buy_trades'] == 2
            assert metrics['sell_trades'] == 1

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_integration_readiness(self):
        """Test that all integration points are ready."""
        # 1. Adapter configuration exists
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

        # 2. Yahoo Finance client module exists
        yf_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'lib',
            'yahoo_finance_client.py'
        )
        assert os.path.exists(yf_path)

        # 3. CoinGecko client module exists
        cg_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'lib',
            'coingecko_client.py'
        )
        assert os.path.exists(cg_path)

        # 4. Paper trading module exists
        pt_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'lib',
            'paper_trading.py'
        )
        assert os.path.exists(pt_path)

        # 5. All agents exist
        for agent in ['fundamental-analyst.md', 'technical-analyst.md', 'risk-assessor.md']:
            agent_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'agents',
                agent
            )
            assert os.path.exists(agent_path)

        # 6. Quality gates documentation exists
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)


class TestMandatoryDisclaimers:
    """Test that all components include mandatory disclaimers."""

    def test_yahoo_client_disclaimer(self):
        """Test Yahoo Finance client includes disclaimer."""
        quote = StockQuote(
            symbol="TEST",
            price=100.0,
            change=0.0,
            change_percent=0.0,
            volume=0,
            avg_volume=0,
            market_cap=0,
            pe_ratio=None,
            eps=None,
            dividend_yield=None,
            fifty_two_week_high=0,
            fifty_two_week_low=0,
            timestamp="",
            exchange="",
            currency=""
        )
        assert "NOT financial advice" in quote.disclaimer

    def test_coingecko_client_disclaimer(self):
        """Test CoinGecko client includes disclaimer."""
        token = TokenInfo(
            id="test",
            symbol="TEST",
            name="Test",
            current_price=0,
            market_cap=0,
            market_cap_rank=None,
            total_volume=0,
            price_change_24h=0,
            price_change_percentage_24h=0,
            price_change_percentage_7d=None,
            price_change_percentage_30d=None,
            circulating_supply=0,
            total_supply=None,
            max_supply=None,
            ath=0,
            ath_change_percentage=0,
            atl=0,
            atl_change_percentage=0,
            last_updated=""
        )
        assert "NOT financial advice" in token.disclaimer
        assert "highly volatile" in token.disclaimer

    def test_paper_trading_disclaimer(self):
        """Test paper trading system includes disclaimer."""
        assert "NOT financial advice" in PaperTradingSystem.DISCLAIMER
        assert "No real money" in PaperTradingSystem.DISCLAIMER

    def test_adapter_config_disclaimer(self):
        """Test adapter config includes disclaimer."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        disclaimer = config['output']['mandatory_disclaimer']
        assert "NOT financial advice" in disclaimer
        assert "Past performance" in disclaimer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
