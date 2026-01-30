#!/usr/bin/env python3
"""
Tests for Human Checkpoint System

Comprehensive tests covering:
- Checkpoint triggering logic
- Decision handling (approve, redirect, cancel)
- Audit logging
- Investment always checkpoints
- Timeout handling
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

# Add lib directory to path
SCRIPT_DIR = Path(__file__).parent.parent / 'lib'
sys.path.insert(0, str(SCRIPT_DIR))

from human_checkpoint import (
    CheckpointConfig,
    CheckpointDecision,
    CheckpointSummary,
    HumanCheckpoint,
    PendingCheckpoints
)
from checkpoint_logger import CheckpointLogger, AuditReport


class TestCheckpointConfig(unittest.TestCase):
    """Tests for CheckpointConfig dataclass"""

    def test_default_values(self):
        """Test default configuration values"""
        config = CheckpointConfig()

        self.assertTrue(config.require_approval)
        self.assertEqual(config.timeout_seconds, 300)
        self.assertTrue(config.log_decisions)
        self.assertTrue(config.investment_always_checkpoint)
        self.assertEqual(config.low_confidence_threshold, 50)
        self.assertIn('investment', config.high_stakes_domains)
        self.assertIn('medical', config.high_stakes_domains)

    def test_custom_values(self):
        """Test custom configuration values"""
        config = CheckpointConfig(
            require_approval=False,
            timeout_seconds=60,
            log_decisions=False,
            investment_always_checkpoint=False,
            low_confidence_threshold=30,
            high_stakes_domains=['custom']
        )

        self.assertFalse(config.require_approval)
        self.assertEqual(config.timeout_seconds, 60)
        self.assertFalse(config.log_decisions)
        self.assertFalse(config.investment_always_checkpoint)
        self.assertEqual(config.low_confidence_threshold, 30)
        self.assertEqual(config.high_stakes_domains, ['custom'])

    def test_to_dict(self):
        """Test conversion to dictionary"""
        config = CheckpointConfig()
        config_dict = config.to_dict()

        self.assertIsInstance(config_dict, dict)
        self.assertIn('require_approval', config_dict)
        self.assertIn('timeout_seconds', config_dict)
        self.assertIn('high_stakes_domains', config_dict)

    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            'require_approval': False,
            'timeout_seconds': 120,
            'log_decisions': True,
            'investment_always_checkpoint': True,
            'low_confidence_threshold': 40,
            'high_stakes_domains': ['test']
        }

        config = CheckpointConfig.from_dict(data)

        self.assertFalse(config.require_approval)
        self.assertEqual(config.timeout_seconds, 120)
        self.assertEqual(config.low_confidence_threshold, 40)


class TestCheckpointDecision(unittest.TestCase):
    """Tests for CheckpointDecision enum"""

    def test_decision_values(self):
        """Test all decision values exist"""
        self.assertEqual(CheckpointDecision.APPROVE.value, "approve")
        self.assertEqual(CheckpointDecision.REQUEST_MORE_DEPTH.value, "more_depth")
        self.assertEqual(CheckpointDecision.REDIRECT.value, "redirect")
        self.assertEqual(CheckpointDecision.CANCEL.value, "cancel")

    def test_all_decisions(self):
        """Test all expected decisions are present"""
        decisions = list(CheckpointDecision)
        self.assertEqual(len(decisions), 4)


class TestCheckpointSummary(unittest.TestCase):
    """Tests for CheckpointSummary dataclass"""

    def test_basic_creation(self):
        """Test basic summary creation"""
        summary = CheckpointSummary(
            research_id="RES-123",
            key_findings=["Finding 1", "Finding 2"],
            confidence=75,
            risks=["Risk 1"],
            estimated_completion="5 minutes",
            requires_human_approval=True
        )

        self.assertEqual(summary.research_id, "RES-123")
        self.assertEqual(len(summary.key_findings), 2)
        self.assertEqual(summary.confidence, 75)
        self.assertTrue(summary.requires_human_approval)

    def test_to_dict(self):
        """Test conversion to dictionary"""
        summary = CheckpointSummary(
            research_id="RES-123",
            key_findings=["Finding 1"],
            confidence=50,
            risks=[],
            estimated_completion="Complete",
            requires_human_approval=False
        )

        summary_dict = summary.to_dict()

        self.assertIsInstance(summary_dict, dict)
        self.assertEqual(summary_dict['research_id'], "RES-123")
        self.assertEqual(summary_dict['confidence'], 50)

    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            'research_id': 'RES-456',
            'key_findings': ['Test finding'],
            'confidence': 80,
            'risks': ['Test risk'],
            'estimated_completion': '10 minutes',
            'requires_human_approval': True,
            'domain': 'investment',
            'question': 'Test question?'
        }

        summary = CheckpointSummary.from_dict(data)

        self.assertEqual(summary.research_id, 'RES-456')
        self.assertEqual(summary.domain, 'investment')
        self.assertEqual(summary.confidence, 80)

    def test_from_research_state(self):
        """Test creation from research state"""
        state = {
            'researchId': 'RES-789',
            'question': 'What are the latest AI trends?',
            'status': 'researching',
            'subQuestions': [
                {'id': 'SQ1', 'status': 'completed', 'confidence': 80, 'findings': ['Finding 1']},
                {'id': 'SQ2', 'status': 'pending', 'confidence': 0, 'findings': []}
            ],
            'metadata': {
                'domain': 'ai-ml',
                'totalSources': 5
            }
        }

        config = CheckpointConfig()
        summary = CheckpointSummary.from_research_state(state, config)

        self.assertEqual(summary.research_id, 'RES-789')
        self.assertEqual(summary.domain, 'ai-ml')
        self.assertEqual(summary.sub_questions_completed, 1)
        self.assertEqual(summary.sub_questions_total, 2)
        self.assertEqual(summary.sources_count, 5)

    def test_from_research_state_investment(self):
        """Test that investment domain adds risk warning"""
        state = {
            'researchId': 'RES-INV',
            'question': 'Should I invest in Bitcoin?',
            'status': 'researching',
            'subQuestions': [],
            'metadata': {
                'domain': 'investment',
                'totalSources': 3
            }
        }

        config = CheckpointConfig()
        summary = CheckpointSummary.from_research_state(state, config)

        self.assertEqual(summary.domain, 'investment')
        self.assertTrue(len(summary.risks) > 0)
        self.assertTrue(summary.requires_human_approval)


class TestHumanCheckpoint(unittest.TestCase):
    """Tests for HumanCheckpoint class"""

    def test_initialization(self):
        """Test checkpoint initialization"""
        checkpoint = HumanCheckpoint()
        self.assertIsNotNone(checkpoint.config)
        self.assertTrue(checkpoint.config.require_approval)

    def test_initialization_with_config(self):
        """Test checkpoint initialization with custom config"""
        config = CheckpointConfig(timeout_seconds=60)
        checkpoint = HumanCheckpoint(config)
        self.assertEqual(checkpoint.config.timeout_seconds, 60)

    def test_should_checkpoint_investment(self):
        """Test that investment domain always requires checkpoint"""
        config = CheckpointConfig(investment_always_checkpoint=True)
        checkpoint = HumanCheckpoint(config)

        # Investment should always checkpoint regardless of confidence
        self.assertTrue(checkpoint.should_checkpoint('investment', 100))
        self.assertTrue(checkpoint.should_checkpoint('investment', 50))
        self.assertTrue(checkpoint.should_checkpoint('investment', 0))

    def test_should_checkpoint_investment_disabled(self):
        """Test investment checkpoint when disabled"""
        config = CheckpointConfig(
            investment_always_checkpoint=False,
            require_approval=False,
            low_confidence_threshold=50,
            high_stakes_domains=['medical', 'legal']  # Remove investment from high-stakes
        )
        checkpoint = HumanCheckpoint(config)

        # High confidence investment without mandatory checkpoint
        self.assertFalse(checkpoint.should_checkpoint('investment', 80))
        # Low confidence still triggers
        self.assertTrue(checkpoint.should_checkpoint('investment', 30))

    def test_should_checkpoint_low_confidence(self):
        """Test that low confidence triggers checkpoint"""
        config = CheckpointConfig(
            low_confidence_threshold=50,
            require_approval=False
        )
        checkpoint = HumanCheckpoint(config)

        self.assertTrue(checkpoint.should_checkpoint('general', 40))
        self.assertTrue(checkpoint.should_checkpoint('general', 49))
        self.assertFalse(checkpoint.should_checkpoint('general', 50))
        self.assertFalse(checkpoint.should_checkpoint('general', 80))

    def test_should_checkpoint_high_stakes_domain(self):
        """Test that high-stakes domains trigger checkpoint"""
        config = CheckpointConfig(
            high_stakes_domains=['medical', 'legal'],
            require_approval=False
        )
        checkpoint = HumanCheckpoint(config)

        self.assertTrue(checkpoint.should_checkpoint('medical', 100))
        self.assertTrue(checkpoint.should_checkpoint('legal', 100))
        self.assertFalse(checkpoint.should_checkpoint('general', 100))

    def test_should_checkpoint_require_approval(self):
        """Test require_approval setting"""
        # With require_approval=True
        config = CheckpointConfig(require_approval=True)
        checkpoint = HumanCheckpoint(config)
        self.assertTrue(checkpoint.should_checkpoint('general', 100))

        # With require_approval=False
        config = CheckpointConfig(require_approval=False, low_confidence_threshold=0)
        checkpoint = HumanCheckpoint(config)
        self.assertFalse(checkpoint.should_checkpoint('general', 100))

    def test_display_summary(self):
        """Test summary display (captures output)"""
        checkpoint = HumanCheckpoint()
        summary = CheckpointSummary(
            research_id="RES-TEST",
            key_findings=["Finding 1", "Finding 2"],
            confidence=75,
            risks=["Risk 1"],
            estimated_completion="5 minutes",
            requires_human_approval=True,
            domain="investment",
            question="Test research question?"
        )

        # Capture stdout
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            checkpoint.display_summary(summary)

        output = captured_output.getvalue()
        self.assertIn("RES-TEST", output)
        self.assertIn("investment", output)
        self.assertIn("75%", output)
        self.assertIn("Risk 1", output)

    def test_generate_confidence_bar(self):
        """Test confidence bar generation"""
        checkpoint = HumanCheckpoint()

        # Test different confidence levels
        bar_high = checkpoint._generate_confidence_bar(90)
        bar_mid = checkpoint._generate_confidence_bar(60)
        bar_low = checkpoint._generate_confidence_bar(30)

        self.assertIn('#', bar_high)
        self.assertIn('.', bar_high)
        self.assertIn('#', bar_low)

    @patch('sys.stdin.isatty', return_value=False)
    def test_get_decision_non_interactive(self, mock_isatty):
        """Test decision in non-interactive mode"""
        checkpoint = HumanCheckpoint()

        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            decision = checkpoint.get_decision()

        self.assertEqual(decision, CheckpointDecision.CANCEL)

    def test_run_checkpoint_auto_approve(self):
        """Test auto-approve mode"""
        config = CheckpointConfig(log_decisions=False)
        checkpoint = HumanCheckpoint(config)

        summary = CheckpointSummary(
            research_id="RES-AUTO",
            key_findings=["Finding"],
            confidence=80,
            risks=[],
            estimated_completion="Complete",
            requires_human_approval=True
        )

        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            decision, additional = checkpoint.run_checkpoint(summary, auto_approve=True)

        self.assertEqual(decision, CheckpointDecision.APPROVE)
        self.assertIsNone(additional)

    def test_run_checkpoint_auto_pass(self):
        """Test auto-pass when criteria met"""
        config = CheckpointConfig(log_decisions=False)
        checkpoint = HumanCheckpoint(config)

        summary = CheckpointSummary(
            research_id="RES-PASS",
            key_findings=["Finding"],
            confidence=80,
            risks=[],
            estimated_completion="Complete",
            requires_human_approval=False  # No approval required
        )

        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            decision, additional = checkpoint.run_checkpoint(summary, auto_approve=False)

        self.assertEqual(decision, CheckpointDecision.APPROVE)


class TestCheckpointLogger(unittest.TestCase):
    """Tests for CheckpointLogger class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_checkpoint_log.json")
        self.logger = CheckpointLogger(log_path=self.log_path)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test logger initialization creates log file"""
        self.assertTrue(os.path.exists(self.log_path))

        with open(self.log_path, 'r') as f:
            data = json.load(f)

        self.assertEqual(data['version'], '1.0')
        self.assertIn('decisions', data)
        self.assertEqual(len(data['decisions']), 0)

    def test_log_decision(self):
        """Test logging a decision"""
        summary = CheckpointSummary(
            research_id="RES-LOG",
            key_findings=["Finding 1"],
            confidence=70,
            risks=["Risk 1"],
            estimated_completion="5 min",
            requires_human_approval=True,
            domain="investment"
        )

        entry_id = self.logger.log_decision(
            CheckpointDecision.APPROVE,
            summary,
            "User approved"
        )

        self.assertIsNotNone(entry_id)
        self.assertTrue(entry_id.startswith("LOG-"))

        # Verify log contents
        with open(self.log_path, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data['decisions']), 1)
        self.assertEqual(data['decisions'][0]['decision'], 'approve')
        self.assertEqual(data['decisions'][0]['research_id'], 'RES-LOG')
        self.assertEqual(data['decisions'][0]['feedback'], 'User approved')

    def test_log_multiple_decisions(self):
        """Test logging multiple decisions"""
        for i in range(5):
            summary = CheckpointSummary(
                research_id=f"RES-{i}",
                key_findings=["Finding"],
                confidence=50 + i * 10,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True
            )
            self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        with open(self.log_path, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data['decisions']), 5)

    def test_log_feedback(self):
        """Test logging feedback"""
        entry_id = self.logger.log_feedback(
            "RES-FB",
            "Great research results!",
            "quality"
        )

        self.assertIsNotNone(entry_id)
        self.assertTrue(entry_id.startswith("FB-"))

    def test_query_decisions(self):
        """Test querying decisions"""
        # Log some decisions
        for domain in ['investment', 'ai-ml', 'general']:
            summary = CheckpointSummary(
                research_id=f"RES-{domain}",
                key_findings=["Finding"],
                confidence=70,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True,
                domain=domain
            )
            self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        # Query all
        all_decisions = self.logger.query_decisions()
        self.assertEqual(len(all_decisions), 3)

        # Query by domain
        investment_decisions = self.logger.query_decisions(domain='investment')
        self.assertEqual(len(investment_decisions), 1)

        # Query by research ID
        specific = self.logger.query_decisions(research_id='RES-ai-ml')
        self.assertEqual(len(specific), 1)

    def test_query_with_limit(self):
        """Test query with limit"""
        # Log 10 decisions
        for i in range(10):
            summary = CheckpointSummary(
                research_id=f"RES-{i}",
                key_findings=["Finding"],
                confidence=70,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True
            )
            self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        # Query with limit
        limited = self.logger.query_decisions(limit=5)
        self.assertEqual(len(limited), 5)

    def test_get_decision_by_id(self):
        """Test retrieving decision by ID"""
        summary = CheckpointSummary(
            research_id="RES-FIND",
            key_findings=["Finding"],
            confidence=70,
            risks=[],
            estimated_completion="5 min",
            requires_human_approval=True
        )
        entry_id = self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        # Retrieve by ID
        decision = self.logger.get_decision_by_id(entry_id)
        self.assertIsNotNone(decision)
        self.assertEqual(decision['research_id'], 'RES-FIND')

        # Non-existent ID
        missing = self.logger.get_decision_by_id('LOG-NONEXISTENT')
        self.assertIsNone(missing)

    def test_get_stats(self):
        """Test getting statistics"""
        # Log various decisions
        for decision_type in [CheckpointDecision.APPROVE, CheckpointDecision.APPROVE,
                              CheckpointDecision.CANCEL, CheckpointDecision.REDIRECT]:
            summary = CheckpointSummary(
                research_id="RES-STATS",
                key_findings=["Finding"],
                confidence=70,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True,
                domain="investment"
            )
            self.logger.log_decision(decision_type, summary)

        stats = self.logger.get_stats()

        self.assertEqual(stats['total_decisions'], 4)
        self.assertEqual(stats['by_decision']['approve'], 2)
        self.assertEqual(stats['by_decision']['cancel'], 1)
        self.assertEqual(stats['by_decision']['redirect'], 1)
        self.assertEqual(stats['by_domain']['investment'], 4)

    def test_get_research_history(self):
        """Test getting complete research history"""
        # Log multiple entries for same research
        for i in range(3):
            summary = CheckpointSummary(
                research_id="RES-HIST",
                key_findings=[f"Finding {i}"],
                confidence=50 + i * 10,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True
            )
            self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        history = self.logger.get_research_history("RES-HIST")
        self.assertEqual(len(history), 3)

    def test_cleanup_old_entries(self):
        """Test cleanup of old entries"""
        # This test requires manipulating timestamps
        # For now, just verify the method runs without error
        removed = self.logger.cleanup_old_entries(days=90)
        self.assertEqual(removed, 0)  # Nothing old to remove

    def test_export_to_jsonl(self):
        """Test JSONL export"""
        # Log some decisions
        summary = CheckpointSummary(
            research_id="RES-EXPORT",
            key_findings=["Finding"],
            confidence=70,
            risks=[],
            estimated_completion="5 min",
            requires_human_approval=True
        )
        self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        # Export
        export_path = os.path.join(self.temp_dir, "export.jsonl")
        count = self.logger.export_to_jsonl(export_path)

        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(export_path))

        # Verify content
        with open(export_path, 'r') as f:
            line = f.readline()
            data = json.loads(line)
            self.assertEqual(data['research_id'], 'RES-EXPORT')


class TestAuditReport(unittest.TestCase):
    """Tests for AuditReport class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_checkpoint_log.json")
        self.logger = CheckpointLogger(log_path=self.log_path)
        self.report = AuditReport(self.logger)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_summary_report_empty(self):
        """Test summary report with no data"""
        report = self.report.generate_summary_report(days=30)

        self.assertIn("CHECKPOINT AUDIT REPORT", report)
        self.assertIn("Total Decisions: 0", report)

    def test_generate_summary_report_with_data(self):
        """Test summary report with data"""
        # Add some decisions
        for i in range(3):
            summary = CheckpointSummary(
                research_id=f"RES-{i}",
                key_findings=["Finding"],
                confidence=70,
                risks=[],
                estimated_completion="5 min",
                requires_human_approval=True,
                domain="ai-ml"
            )
            self.logger.log_decision(CheckpointDecision.APPROVE, summary)

        report = self.report.generate_summary_report(days=30)

        self.assertIn("Total Decisions: 3", report)
        self.assertIn("approve: 3", report)
        self.assertIn("ai-ml: 3", report)

    def test_generate_investment_report_empty(self):
        """Test investment report with no data"""
        report = self.report.generate_investment_report(days=30)

        self.assertIn("INVESTMENT CHECKPOINT REPORT", report)
        self.assertIn("No investment checkpoints", report)

    def test_generate_investment_report_with_data(self):
        """Test investment report with data"""
        # Add investment decisions
        for i in range(5):
            summary = CheckpointSummary(
                research_id=f"RES-INV-{i}",
                key_findings=["Finding"],
                confidence=50 + i * 10,
                risks=["Risk 1", "Risk 2"],
                estimated_completion="5 min",
                requires_human_approval=True,
                domain="investment"
            )
            decision = CheckpointDecision.APPROVE if i < 3 else CheckpointDecision.CANCEL
            self.logger.log_decision(decision, summary)

        report = self.report.generate_investment_report(days=30)

        self.assertIn("Total Investment Checkpoints: 5", report)
        self.assertIn("Decision Distribution", report)
        self.assertIn("Average Risks per Checkpoint", report)


class TestPendingCheckpoints(unittest.TestCase):
    """Tests for PendingCheckpoints class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.temp_dir, ".claude-loop")
        os.makedirs(self.state_dir)
        self.manager = PendingCheckpoints(self.state_dir)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_pending_empty(self):
        """Test listing pending when none exist"""
        pending = self.manager.list_pending()
        self.assertEqual(len(pending), 0)

    def test_list_pending_with_state(self):
        """Test listing pending with state file"""
        # Create state file
        state = {
            'researchId': 'RES-PENDING',
            'question': 'Test question?',
            'status': 'researching',
            'subQuestions': [
                {'id': 'SQ1', 'status': 'completed', 'confidence': 40, 'findings': []}
            ],
            'metadata': {
                'domain': 'investment',
                'totalSources': 3
            }
        }

        state_file = os.path.join(self.state_dir, "research-state.json")
        with open(state_file, 'w') as f:
            json.dump(state, f)

        pending = self.manager.list_pending()

        # Investment with low confidence should be pending
        self.assertGreater(len(pending), 0)


class TestTimeoutHandling(unittest.TestCase):
    """Tests for timeout handling"""

    def test_timeout_configuration(self):
        """Test timeout configuration"""
        config = CheckpointConfig(timeout_seconds=60)
        checkpoint = HumanCheckpoint(config)

        self.assertEqual(checkpoint.config.timeout_seconds, 60)

    def test_default_timeout(self):
        """Test default timeout value"""
        config = CheckpointConfig()
        self.assertEqual(config.timeout_seconds, 300)  # 5 minutes

    @patch('select.select', return_value=([], [], []))
    @patch('sys.stdin.isatty', return_value=True)
    def test_timeout_raises_exception(self, mock_isatty, mock_select):
        """Test that timeout raises TimeoutError"""
        checkpoint = HumanCheckpoint()

        with self.assertRaises(TimeoutError):
            checkpoint._get_input_with_timeout(1)


class TestIntegration(unittest.TestCase):
    """Integration tests for checkpoint system"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "checkpoint_log.json")

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_checkpoint_flow(self):
        """Test complete checkpoint flow"""
        # Create config with logging
        config = CheckpointConfig(log_decisions=True)

        # Create checkpoint with custom logger path
        checkpoint = HumanCheckpoint(config)
        checkpoint._logger = CheckpointLogger(log_path=self.log_path)

        # Create summary
        summary = CheckpointSummary(
            research_id="RES-FLOW",
            key_findings=["Finding 1", "Finding 2", "Finding 3"],
            confidence=65,
            risks=["Market volatility", "Limited data"],
            estimated_completion="3 minutes",
            requires_human_approval=True,
            domain="investment",
            question="What are the best ETFs for 2024?"
        )

        # Run with auto-approve
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            decision, additional = checkpoint.run_checkpoint(summary, auto_approve=True)

        # Verify decision
        self.assertEqual(decision, CheckpointDecision.APPROVE)

        # Verify logging
        with open(self.log_path, 'r') as f:
            data = json.load(f)

        self.assertEqual(len(data['decisions']), 1)
        self.assertEqual(data['decisions'][0]['decision'], 'approve')

    def test_investment_always_checkpoints(self):
        """Test that investment research always triggers checkpoint"""
        state = {
            'researchId': 'RES-INV-TEST',
            'question': 'Should I invest in crypto?',
            'status': 'researching',
            'subQuestions': [
                {'id': 'SQ1', 'status': 'completed', 'confidence': 95, 'findings': ['High confidence']}
            ],
            'metadata': {
                'domain': 'investment',
                'totalSources': 10
            }
        }

        config = CheckpointConfig(investment_always_checkpoint=True)
        summary = CheckpointSummary.from_research_state(state, config)

        # Even with 95% confidence, investment should require approval
        checkpoint = HumanCheckpoint(config)
        self.assertTrue(checkpoint.should_checkpoint('investment', 95))
        self.assertTrue(summary.requires_human_approval)


if __name__ == '__main__':
    unittest.main()
