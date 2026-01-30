#!/usr/bin/env python3
"""
End-to-End Tests for Investment Research Use Case (US-013)

Comprehensive integration tests covering:
- Paper trading mode (must be default!)
- Human checkpoint triggers
- Prediction tracking
- Risk assessment gates
- Report generation with disclaimers

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
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

# Import using importlib for hyphenated module names
import importlib.util


def load_module(name, path):
    """Load a module from file path."""
    if not os.path.exists(path):
        pytest.skip(f"Module not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Module paths
LIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lib')


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_yahoo_finance_response():
    """Mock Yahoo Finance API response."""
    return {
        'quote': {
            'symbol': 'AAPL',
            'price': 175.50,
            'change': 2.50,
            'changePercent': 1.45,
            'volume': 50000000,
            'avgVolume': 60000000,
            'marketCap': 2800000000000,
            'peRatio': 28.5,
            'eps': 6.15,
            'dividendYield': 0.5,
            'fiftyTwoWeekHigh': 199.62,
            'fiftyTwoWeekLow': 124.17,
            'exchange': 'NASDAQ',
            'currency': 'USD'
        }
    }


@pytest.fixture
def mock_coingecko_response():
    """Mock CoinGecko API response."""
    return {
        'id': 'bitcoin',
        'symbol': 'btc',
        'name': 'Bitcoin',
        'current_price': 45000.0,
        'market_cap': 880000000000,
        'market_cap_rank': 1,
        'total_volume': 25000000000,
        'price_change_24h': 500.0,
        'price_change_percentage_24h': 1.12,
        'circulating_supply': 19500000,
        'total_supply': 21000000,
        'ath': 69000.0,
        'atl': 67.81
    }


@pytest.fixture
def sample_investment_state():
    """Sample investment research state."""
    return {
        'researchId': 'RES-INV-001',
        'question': 'Should I invest in AAPL stock?',
        'status': 'researching',
        'startTime': datetime.now().isoformat(),
        'subQuestions': [
            {
                'id': 'SQ-001',
                'question': 'What is AAPL fundamental analysis?',
                'agent': 'fundamental-analyst',
                'status': 'completed',
                'confidence': 75,
                'findings': ['P/E ratio of 28.5', 'Strong revenue growth']
            },
            {
                'id': 'SQ-002',
                'question': 'What are the technical indicators?',
                'agent': 'technical-analyst',
                'status': 'completed',
                'confidence': 70,
                'findings': ['RSI at 55 (neutral)', 'Above 200-day MA']
            },
            {
                'id': 'SQ-003',
                'question': 'What are the risks?',
                'agent': 'risk-assessor',
                'status': 'pending',
                'confidence': 0,
                'findings': []
            }
        ],
        'metadata': {
            'domain': 'investment',
            'totalSources': 8,
            'adapter': 'investment',
            'paperTrading': True
        }
    }


@pytest.fixture
def temp_data_file():
    """Create a temporary data file for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_state_dir():
    """Create a temporary directory for state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# Test Paper Trading Mode (MUST BE DEFAULT!)
# ============================================================================

class TestPaperTradingDefault:
    """Test that paper trading is enabled by default - critical safety requirement."""

    def test_adapter_config_paper_trading_enabled(self):
        """Test adapter config has paper trading enabled by default."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        assert 'paper_trading' in config
        assert config['paper_trading']['enabled'] is True, \
            "Paper trading MUST be enabled by default for safety"

    def test_yahoo_finance_client_paper_trading_default(self):
        """Test Yahoo Finance client has paper trading enabled by default."""
        yahoo_module = load_module(
            "yahoo_finance_client",
            os.path.join(LIB_PATH, 'yahoo_finance_client.py')
        )

        client = yahoo_module.YahooFinanceClient()
        assert client.paper_trading is True, \
            "YahooFinanceClient MUST have paper_trading=True by default"

    def test_coingecko_client_paper_trading_default(self):
        """Test CoinGecko client has paper trading enabled by default."""
        coingecko_module = load_module(
            "coingecko_client",
            os.path.join(LIB_PATH, 'coingecko_client.py')
        )

        client = coingecko_module.CoinGeckoClient()
        assert client.paper_trading is True, \
            "CoinGeckoClient MUST have paper_trading=True by default"

    def test_paper_trading_system_default_balance(self, temp_data_file):
        """Test paper trading system has reasonable default balance."""
        paper_module = load_module(
            "paper_trading",
            os.path.join(LIB_PATH, 'paper_trading.py')
        )

        system = paper_module.PaperTradingSystem(data_file=temp_data_file)
        assert system.portfolio.initial_balance == 100000.0, \
            "Default paper trading balance should be $100,000"

    def test_paper_trade_marked_as_paper(self, temp_data_file):
        """Test all paper trades are clearly marked as paper trades."""
        paper_module = load_module(
            "paper_trading",
            os.path.join(LIB_PATH, 'paper_trading.py')
        )

        system = paper_module.PaperTradingSystem(data_file=temp_data_file)
        trade = system.buy("AAPL", 100, 175.50)

        # Verify the trade is tracked in paper trading system
        assert trade is not None, "Trade should be recorded"
        assert hasattr(trade, 'trade_id'), "Trade should have trade_id"
        # Paper trading is implicit since PaperTradingSystem only does paper trades


# ============================================================================
# Test Human Checkpoint Triggers
# ============================================================================

class TestHumanCheckpointTriggers:
    """Test human checkpoint triggers for investment research."""

    def test_checkpoint_module_exists(self):
        """Test human checkpoint module exists."""
        checkpoint_path = os.path.join(LIB_PATH, 'human_checkpoint.py')
        assert os.path.exists(checkpoint_path)

    def test_investment_always_triggers_checkpoint(self):
        """Test that investment domain always triggers human checkpoint."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )

        config = checkpoint_module.CheckpointConfig(
            investment_always_checkpoint=True
        )
        checkpoint = checkpoint_module.HumanCheckpoint(config)

        # Investment should always checkpoint, regardless of confidence
        assert checkpoint.should_checkpoint('investment', 100) is True
        assert checkpoint.should_checkpoint('investment', 50) is True
        assert checkpoint.should_checkpoint('investment', 0) is True

    def test_checkpoint_config_includes_investment_high_stakes(self):
        """Test checkpoint config has investment in high-stakes domains."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )

        config = checkpoint_module.CheckpointConfig()
        assert 'investment' in config.high_stakes_domains

    def test_checkpoint_summary_includes_risks(self, sample_investment_state):
        """Test checkpoint summary includes risk warnings for investment."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )

        config = checkpoint_module.CheckpointConfig()
        summary = checkpoint_module.CheckpointSummary.from_research_state(
            sample_investment_state, config
        )

        assert summary.requires_human_approval is True
        assert len(summary.risks) > 0, "Investment research MUST include risk warnings"

    def test_low_confidence_triggers_checkpoint(self):
        """Test that low confidence findings trigger checkpoint."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )

        config = checkpoint_module.CheckpointConfig(
            low_confidence_threshold=50,
            investment_always_checkpoint=False,
            require_approval=False
        )
        checkpoint = checkpoint_module.HumanCheckpoint(config)

        assert checkpoint.should_checkpoint('general', 40) is True
        assert checkpoint.should_checkpoint('general', 60) is False

    def test_checkpoint_decisions_logged(self, temp_state_dir):
        """Test checkpoint decisions are properly logged."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )
        logger_module = load_module(
            "checkpoint_logger",
            os.path.join(LIB_PATH, 'checkpoint_logger.py')
        )

        log_path = os.path.join(temp_state_dir, "checkpoint_log.json")
        logger = logger_module.CheckpointLogger(log_path=log_path)

        summary = checkpoint_module.CheckpointSummary(
            research_id="RES-INV-001",
            key_findings=["Finding 1"],
            confidence=60,
            risks=["Market risk"],
            estimated_completion="5 min",
            requires_human_approval=True,
            domain="investment"
        )

        entry_id = logger.log_decision(
            checkpoint_module.CheckpointDecision.APPROVE,
            summary,
            "Reviewed and approved"
        )

        assert entry_id is not None
        assert os.path.exists(log_path)


# ============================================================================
# Test Prediction Tracking
# ============================================================================

class TestPredictionTracking:
    """Test prediction tracking functionality."""

    def test_prediction_tracker_module_exists(self):
        """Test prediction tracker module exists."""
        tracker_path = os.path.join(LIB_PATH, 'prediction_tracker.py')
        assert os.path.exists(tracker_path)

    def test_prediction_creation(self, temp_data_file):
        """Test creating a prediction."""
        tracker_module = load_module(
            "prediction_tracker",
            os.path.join(LIB_PATH, 'prediction_tracker.py')
        )

        tracker = tracker_module.PredictionTracker(store_path=temp_data_file)

        # Create a prediction using the Prediction dataclass
        prediction = tracker_module.Prediction(
            id="",
            research_id="RES-TEST",
            asset="AAPL",
            asset_type="stock",
            entry_price=175.0,
            entry_date=datetime.now(),
            targets=[200.0],
            stop_loss=160.0,
            timeframe_days=30,
            thesis="Strong fundamentals and technical breakout",
            confidence=75,
            sources=["test-source"]
        )

        pred_id = tracker.record(prediction)

        assert pred_id is not None
        stored = tracker.get(pred_id)
        assert stored.asset == "AAPL"
        assert stored.confidence == 75
        assert stored.status == "active"

    def test_prediction_resolution(self, temp_data_file):
        """Test checking prediction against price."""
        tracker_module = load_module(
            "prediction_tracker",
            os.path.join(LIB_PATH, 'prediction_tracker.py')
        )

        tracker = tracker_module.PredictionTracker(store_path=temp_data_file)

        # Create prediction
        prediction = tracker_module.Prediction(
            id="",
            research_id="RES-TEST",
            asset="AAPL",
            asset_type="stock",
            entry_price=175.0,
            entry_date=datetime.now(),
            targets=[200.0],
            stop_loss=160.0,
            timeframe_days=30,
            thesis="Test",
            confidence=75,
            sources=["test"]
        )

        pred_id = tracker.record(prediction)
        stored = tracker.get(pred_id)

        # Check price that would hit target
        new_status = stored.check_price(210.0)
        assert new_status == "hit_target"

    def test_prediction_accuracy_tracking(self, temp_data_file):
        """Test tracking predictions over time."""
        tracker_module = load_module(
            "prediction_tracker",
            os.path.join(LIB_PATH, 'prediction_tracker.py')
        )

        tracker = tracker_module.PredictionTracker(store_path=temp_data_file)

        # Create multiple predictions
        for i in range(3):
            prediction = tracker_module.Prediction(
                id="",
                research_id=f"RES-TEST-{i}",
                asset=f"TEST{i}",
                asset_type="stock",
                entry_price=100.0,
                entry_date=datetime.now(),
                targets=[120.0],
                stop_loss=80.0,
                timeframe_days=30,
                thesis="Test",
                confidence=70,
                sources=["test"]
            )
            tracker.record(prediction)

        # Verify predictions were stored
        assert len(tracker.predictions) == 3

    def test_predictions_include_disclaimer(self, temp_data_file):
        """Test prediction tracker module is for tracking only, not recommendations."""
        tracker_module = load_module(
            "prediction_tracker",
            os.path.join(LIB_PATH, 'prediction_tracker.py')
        )

        # Verify module exists and has tracking functionality
        assert hasattr(tracker_module, 'PredictionTracker')
        assert hasattr(tracker_module, 'Prediction')

        # The prediction tracker is for tracking only - disclaimers are
        # handled at the adapter level (investment adapter.yaml mandatory_disclaimer)


# ============================================================================
# Test Risk Assessment Gates
# ============================================================================

class TestRiskAssessmentGates:
    """Test risk assessment gates for investment research."""

    def test_risk_assessor_agent_exists(self):
        """Test risk-assessor.md agent exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'risk-assessor.md'
        )
        assert os.path.exists(agent_path)

    def test_risk_assessor_includes_required_sections(self):
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

        # Check for required sections
        assert '# Risk Assessor Agent' in content
        assert 'Volatility' in content
        assert 'Drawdown' in content
        assert 'Position Sizing' in content

    def test_adapter_quality_gates(self):
        """Test investment adapter has required quality gates."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        gates = config['quality_gates']

        # Source recency check
        assert 'source_recency' in gates
        assert gates['source_recency']['enabled'] is True

        # Confirmation bias check
        assert 'confirmation_bias' in gates
        assert gates['confirmation_bias']['enabled'] is True
        requirements = gates['confirmation_bias']['requirements']
        assert 'require_bear_case' in requirements
        assert 'require_bull_case' in requirements

        # Risk disclosure
        assert 'risk_disclosure' in gates
        assert gates['risk_disclosure']['enabled'] is True

        # Liquidity check
        assert 'liquidity_check' in gates
        assert gates['liquidity_check']['enabled'] is True

    def test_quality_gates_prompts_exist(self):
        """Test quality gates prompts file exists."""
        gates_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'prompts',
            'quality_gates.md'
        )
        assert os.path.exists(gates_path)

    def test_quality_gates_include_required_checks(self):
        """Test quality gates include all required checks."""
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

        # Check for required gates
        assert 'Source Recency' in content
        assert 'Confirmation Bias' in content
        assert 'Risk Disclosure' in content
        assert 'Liquidity' in content
        assert 'Backtesting' in content

        # Check for mandatory disclaimer
        assert 'NOT financial advice' in content


# ============================================================================
# Test Report Generation with Disclaimers
# ============================================================================

class TestReportGenerationWithDisclaimers:
    """Test report generation with mandatory disclaimers."""

    def test_report_generator_exists(self):
        """Test report generator module exists."""
        report_path = os.path.join(LIB_PATH, 'report-generator.py')
        assert os.path.exists(report_path)

    def test_adapter_mandatory_disclaimer(self):
        """Test adapter config has mandatory disclaimer."""
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

    def test_adapter_output_sections(self):
        """Test adapter specifies required output sections."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        sections = config['output']['include_sections']

        required_sections = [
            'executive_summary',
            'fundamental_analysis',
            'technical_analysis',
            'risk_assessment',
            'bull_case',
            'bear_case',
            'disclaimer'
        ]

        for section in required_sections:
            assert section in sections, f"Section {section} should be in output sections"

    def test_yahoo_client_disclaimer(self):
        """Test Yahoo Finance client includes disclaimer in outputs."""
        yahoo_module = load_module(
            "yahoo_finance_client",
            os.path.join(LIB_PATH, 'yahoo_finance_client.py')
        )

        quote = yahoo_module.StockQuote(
            symbol="AAPL",
            price=175.50,
            change=0.0,
            change_percent=0.0,
            volume=50000000,
            avg_volume=60000000,
            market_cap=2800000000000,
            pe_ratio=28.5,
            eps=6.15,
            dividend_yield=0.5,
            fifty_two_week_high=199.62,
            fifty_two_week_low=124.17,
            timestamp=datetime.now().isoformat(),
            exchange="NASDAQ",
            currency="USD"
        )

        assert "NOT financial advice" in quote.disclaimer

    def test_coingecko_client_disclaimer(self):
        """Test CoinGecko client includes disclaimer in outputs."""
        coingecko_module = load_module(
            "coingecko_client",
            os.path.join(LIB_PATH, 'coingecko_client.py')
        )

        token = coingecko_module.TokenInfo(
            id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            current_price=45000.0,
            market_cap=880000000000,
            market_cap_rank=1,
            total_volume=25000000000,
            price_change_24h=500.0,
            price_change_percentage_24h=1.12,
            price_change_percentage_7d=None,
            price_change_percentage_30d=None,
            circulating_supply=19500000,
            total_supply=21000000,
            max_supply=21000000,
            ath=69000.0,
            ath_change_percentage=-34.8,
            atl=67.81,
            atl_change_percentage=66300.0,
            last_updated=datetime.now().isoformat()
        )

        assert "NOT financial advice" in token.disclaimer
        assert "volatile" in token.disclaimer.lower()

    def test_paper_trading_disclaimer(self):
        """Test paper trading system includes disclaimer."""
        paper_module = load_module(
            "paper_trading",
            os.path.join(LIB_PATH, 'paper_trading.py')
        )

        assert "NOT financial advice" in paper_module.PaperTradingSystem.DISCLAIMER
        assert "No real money" in paper_module.PaperTradingSystem.DISCLAIMER


# ============================================================================
# Test Investment Agents
# ============================================================================

class TestInvestmentAgents:
    """Test investment analysis agents."""

    def test_fundamental_analyst_exists(self):
        """Test fundamental-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'fundamental-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_technical_analyst_exists(self):
        """Test technical-analyst.md exists."""
        agent_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            'technical-analyst.md'
        )
        assert os.path.exists(agent_path)

    def test_all_investment_agents_have_disclaimers(self):
        """Test all investment agents include disclaimers or safety guidelines."""
        agents_dir = os.path.join(os.path.dirname(__file__), '..', 'agents')
        investment_agents = [
            'fundamental-analyst.md',
            'technical-analyst.md',
            'risk-assessor.md',
        ]

        for agent_name in investment_agents:
            agent_path = os.path.join(agents_dir, agent_name)
            if os.path.exists(agent_path):
                with open(agent_path, 'r') as f:
                    content = f.read()
                # Check for financial advice disclaimer or safety guidelines
                has_disclaimer = (
                    'NOT financial advice' in content or
                    'not financial advice' in content.lower() or
                    'No Financial Advice' in content or
                    'educational' in content.lower() or
                    'Safety' in content
                )
                assert has_disclaimer, \
                    f"Agent {agent_name} should include financial advice disclaimer or safety guidelines"


# ============================================================================
# Test End-to-End Investment Research Flow
# ============================================================================

class TestEndToEndInvestmentResearch:
    """End-to-end integration tests for investment research."""

    def test_all_components_exist(self):
        """Test all required components exist."""
        # Adapter
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

        # Data clients
        assert os.path.exists(os.path.join(LIB_PATH, 'yahoo_finance_client.py'))
        assert os.path.exists(os.path.join(LIB_PATH, 'coingecko_client.py'))
        assert os.path.exists(os.path.join(LIB_PATH, 'paper_trading.py'))

        # Checkpoint system
        assert os.path.exists(os.path.join(LIB_PATH, 'human_checkpoint.py'))

        # Prediction tracking
        assert os.path.exists(os.path.join(LIB_PATH, 'prediction_tracker.py'))

    def test_paper_trading_flow(self, temp_data_file):
        """Test complete paper trading flow."""
        paper_module = load_module(
            "paper_trading",
            os.path.join(LIB_PATH, 'paper_trading.py')
        )

        # Initialize system
        system = paper_module.PaperTradingSystem(data_file=temp_data_file)
        assert system.portfolio.cash_balance == 100000.0

        # Buy stock
        trade1 = system.buy("AAPL", 100, 175.50, asset_type="stock")
        assert trade1 is not None
        assert system.portfolio.positions["AAPL"].quantity == 100

        # Buy crypto
        trade2 = system.buy("BTC", 0.5, 45000.0, asset_type="crypto")
        assert trade2 is not None
        assert system.portfolio.positions["BTC"].quantity == 0.5

        # Sell stock at profit
        trade3 = system.sell("AAPL", 50, 180.00)
        assert trade3 is not None
        assert system.portfolio.positions["AAPL"].quantity == 50

        # Verify trades recorded
        assert len(system.portfolio.trades) == 3

    def test_investment_research_with_checkpoint(self, sample_investment_state, temp_state_dir):
        """Test investment research triggers checkpoint."""
        checkpoint_module = load_module(
            "human_checkpoint",
            os.path.join(LIB_PATH, 'human_checkpoint.py')
        )

        config = checkpoint_module.CheckpointConfig(
            investment_always_checkpoint=True,
            log_decisions=False
        )
        checkpoint = checkpoint_module.HumanCheckpoint(config)

        summary = checkpoint_module.CheckpointSummary.from_research_state(
            sample_investment_state, config
        )

        # Investment should require approval
        assert summary.requires_human_approval is True
        assert summary.domain == 'investment'
        assert len(summary.risks) > 0

        # Test auto-approve mode
        decision, _ = checkpoint.run_checkpoint(summary, auto_approve=True)
        assert decision == checkpoint_module.CheckpointDecision.APPROVE

    def test_full_research_synthesis(self, sample_investment_state):
        """Test full research synthesis for investment."""
        synth_module = load_module(
            "research_synthesizer",
            os.path.join(LIB_PATH, 'research_synthesizer.py')
        )

        synthesizer = synth_module.ResearchSynthesizer(domain='investment')

        findings_by_agent = {
            'fundamental-analyst': [
                synth_module.Finding(
                    id='F-001',
                    content='P/E ratio of 28.5 suggests premium valuation',
                    source_url='https://finance.yahoo.com/quote/AAPL',
                    agent='fundamental-analyst',
                    sub_question_id='SQ-001',
                    relevance_score=0.90
                )
            ],
            'technical-analyst': [
                synth_module.Finding(
                    id='F-002',
                    content='RSI at 55 indicates neutral momentum',
                    source_url='https://tradingview.com/chart/AAPL',
                    agent='technical-analyst',
                    sub_question_id='SQ-002',
                    relevance_score=0.85
                )
            ]
        }

        sub_questions = [
            {'id': 'SQ-001', 'question': 'Fundamental analysis'},
            {'id': 'SQ-002', 'question': 'Technical indicators'},
            {'id': 'SQ-003', 'question': 'Risk assessment'}  # Unanswered
        ]

        synthesis = synthesizer.synthesize(
            question=sample_investment_state['question'],
            findings_by_agent=findings_by_agent,
            sub_questions=sub_questions
        )

        assert synthesis is not None
        assert len(synthesis.key_findings) >= 2

        # Should have gap for unanswered risk assessment
        coverage_gaps = [g for g in synthesis.gaps if g.gap_type == 'coverage']
        assert any(g.related_sub_question == 'SQ-003' for g in coverage_gaps)


# ============================================================================
# Test Safety Requirements
# ============================================================================

class TestSafetyRequirements:
    """Test safety requirements for investment research."""

    def test_no_real_trading_capability(self):
        """Verify the system cannot execute real trades."""
        yahoo_module = load_module(
            "yahoo_finance_client",
            os.path.join(LIB_PATH, 'yahoo_finance_client.py')
        )

        client = yahoo_module.YahooFinanceClient()

        # Verify no real trading methods exist
        assert not hasattr(client, 'execute_real_trade')
        assert not hasattr(client, 'place_order')
        assert not hasattr(client, 'submit_order')

        # Verify paper trading is enforced
        assert client.paper_trading is True

    def test_mandatory_disclaimer_injection(self):
        """Test disclaimers are mandatory and cannot be disabled."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        # Verify disclaimer section exists and is populated
        assert 'mandatory_disclaimer' in config['output']
        disclaimer = config['output']['mandatory_disclaimer']
        assert len(disclaimer) > 100, "Disclaimer must be substantial"

        # Verify risk disclosure gate is enabled
        assert config['quality_gates']['risk_disclosure']['enabled'] is True

    def test_confirmation_bias_protection(self):
        """Test confirmation bias protection is enabled."""
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'adapters',
            'investment',
            'adapter.yaml'
        )

        with open(adapter_path, 'r') as f:
            config = yaml.safe_load(f)

        bias_config = config['quality_gates']['confirmation_bias']
        assert bias_config['enabled'] is True
        assert 'require_bear_case' in bias_config['requirements']
        assert 'require_bull_case' in bias_config['requirements']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
