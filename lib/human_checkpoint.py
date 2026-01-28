#!/usr/bin/env python3
"""
Human Checkpoint System for Research Loop

Provides human-in-the-loop checkpoints for research validation,
especially critical for investment research domains.

Usage:
    python lib/human_checkpoint.py --research-id RES-123 --summary
    python lib/human_checkpoint.py --list-pending
    python lib/human_checkpoint.py --approve RES-123
"""

import argparse
import json
import sys
import os
import select
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any


class CheckpointDecision(Enum):
    """Enumeration of possible checkpoint decisions"""
    APPROVE = "approve"
    REQUEST_MORE_DEPTH = "more_depth"
    REDIRECT = "redirect"
    CANCEL = "cancel"


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint behavior"""
    require_approval: bool = True
    timeout_seconds: int = 300  # 5 min default
    log_decisions: bool = True
    investment_always_checkpoint: bool = True  # Mandatory for investment
    low_confidence_threshold: int = 50  # Checkpoint if confidence below this
    high_stakes_domains: List[str] = field(default_factory=lambda: [
        'investment', 'medical', 'legal', 'security'
    ])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'require_approval': self.require_approval,
            'timeout_seconds': self.timeout_seconds,
            'log_decisions': self.log_decisions,
            'investment_always_checkpoint': self.investment_always_checkpoint,
            'low_confidence_threshold': self.low_confidence_threshold,
            'high_stakes_domains': self.high_stakes_domains
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointConfig':
        """Create from dictionary"""
        return cls(
            require_approval=data.get('require_approval', True),
            timeout_seconds=data.get('timeout_seconds', 300),
            log_decisions=data.get('log_decisions', True),
            investment_always_checkpoint=data.get('investment_always_checkpoint', True),
            low_confidence_threshold=data.get('low_confidence_threshold', 50),
            high_stakes_domains=data.get('high_stakes_domains', [
                'investment', 'medical', 'legal', 'security'
            ])
        )


@dataclass
class CheckpointSummary:
    """Summary data for a checkpoint"""
    research_id: str
    key_findings: List[str]
    confidence: int
    risks: List[str]  # Especially important for investment
    estimated_completion: str
    requires_human_approval: bool
    domain: str = "general"
    question: str = ""
    sources_count: int = 0
    sub_questions_completed: int = 0
    sub_questions_total: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    status: str = "pending"  # pending, approved, rejected, redirected

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'research_id': self.research_id,
            'key_findings': self.key_findings,
            'confidence': self.confidence,
            'risks': self.risks,
            'estimated_completion': self.estimated_completion,
            'requires_human_approval': self.requires_human_approval,
            'domain': self.domain,
            'question': self.question,
            'sources_count': self.sources_count,
            'sub_questions_completed': self.sub_questions_completed,
            'sub_questions_total': self.sub_questions_total,
            'created_at': self.created_at,
            'status': self.status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointSummary':
        """Create from dictionary"""
        return cls(
            research_id=data.get('research_id', ''),
            key_findings=data.get('key_findings', []),
            confidence=data.get('confidence', 0),
            risks=data.get('risks', []),
            estimated_completion=data.get('estimated_completion', 'Unknown'),
            requires_human_approval=data.get('requires_human_approval', True),
            domain=data.get('domain', 'general'),
            question=data.get('question', ''),
            sources_count=data.get('sources_count', 0),
            sub_questions_completed=data.get('sub_questions_completed', 0),
            sub_questions_total=data.get('sub_questions_total', 0),
            created_at=data.get('created_at', datetime.utcnow().isoformat() + 'Z'),
            status=data.get('status', 'pending')
        )

    @classmethod
    def from_research_state(cls, state: Dict[str, Any], config: 'CheckpointConfig') -> 'CheckpointSummary':
        """Create summary from research state"""
        # Extract key findings from sub-questions
        key_findings = []
        for sq in state.get('subQuestions', []):
            for finding in sq.get('findings', []):
                if isinstance(finding, dict):
                    key_findings.append(finding.get('summary', str(finding)))
                else:
                    key_findings.append(str(finding))

        # Limit to top 5 findings
        key_findings = key_findings[:5] if key_findings else ['Research in progress...']

        # Calculate confidence
        confidences = [sq.get('confidence', 0) for sq in state.get('subQuestions', [])]
        avg_confidence = sum(confidences) // len(confidences) if confidences else 0

        # Extract risks (especially for investment domain)
        risks = state.get('metadata', {}).get('risks', [])
        if not risks and state.get('metadata', {}).get('domain') == 'investment':
            risks = ['No risk assessment available - please review findings carefully']

        # Calculate completion status
        sub_questions = state.get('subQuestions', [])
        completed = sum(1 for sq in sub_questions if sq.get('status') == 'completed')
        total = len(sub_questions)

        # Estimate completion time
        if completed == total:
            estimated_completion = "Complete"
        elif completed == 0:
            estimated_completion = "Just started"
        else:
            remaining = total - completed
            estimated_completion = f"~{remaining * 2} minutes remaining"

        # Determine if approval required
        domain = state.get('metadata', {}).get('domain', 'general')
        checkpoint = HumanCheckpoint(config)
        requires_approval = checkpoint.should_checkpoint(domain, avg_confidence)

        return cls(
            research_id=state.get('researchId', 'UNKNOWN'),
            key_findings=key_findings,
            confidence=avg_confidence,
            risks=risks,
            estimated_completion=estimated_completion,
            requires_human_approval=requires_approval,
            domain=domain,
            question=state.get('question', ''),
            sources_count=state.get('metadata', {}).get('totalSources', 0),
            sub_questions_completed=completed,
            sub_questions_total=total
        )


class HumanCheckpoint:
    """
    Human checkpoint system for research validation.

    Provides interactive checkpoints at key stages of research,
    especially critical for investment domains.
    """

    # ANSI colors for terminal output
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

    def __init__(self, config: Optional[CheckpointConfig] = None):
        """
        Initialize checkpoint system.

        Args:
            config: Checkpoint configuration (uses defaults if not provided)
        """
        self.config = config or CheckpointConfig()
        self._logger = None

    @property
    def logger(self):
        """Lazy-load checkpoint logger"""
        if self._logger is None:
            from checkpoint_logger import CheckpointLogger
            self._logger = CheckpointLogger()
        return self._logger

    def should_checkpoint(self, domain: str, confidence: int) -> bool:
        """
        Determine if a checkpoint is required.

        Args:
            domain: Research domain (investment, ai-ml, general, etc.)
            confidence: Current confidence score (0-100)

        Returns:
            True if checkpoint is required
        """
        # Always checkpoint for investment domain
        if self.config.investment_always_checkpoint and domain == 'investment':
            return True

        # Checkpoint if confidence is below threshold
        if confidence < self.config.low_confidence_threshold:
            return True

        # Checkpoint for high-stakes domains
        if domain in self.config.high_stakes_domains:
            return True

        # Default: respect require_approval setting
        return self.config.require_approval

    def display_summary(self, summary: CheckpointSummary) -> None:
        """
        Display checkpoint summary to user.

        Args:
            summary: Checkpoint summary to display
        """
        print()
        print(f"{self.BOLD}{'=' * 60}{self.NC}")
        print(f"{self.BOLD}{self.CYAN}  HUMAN CHECKPOINT - Research Review Required{self.NC}")
        print(f"{self.BOLD}{'=' * 60}{self.NC}")
        print()

        # Research info
        print(f"{self.BOLD}Research ID:{self.NC} {summary.research_id}")
        print(f"{self.BOLD}Domain:{self.NC} {summary.domain}")
        print(f"{self.BOLD}Question:{self.NC} {summary.question[:80]}{'...' if len(summary.question) > 80 else ''}")
        print()

        # Progress
        print(f"{self.BOLD}Progress:{self.NC} {summary.sub_questions_completed}/{summary.sub_questions_total} sub-questions completed")
        print(f"{self.BOLD}Sources:{self.NC} {summary.sources_count} sources analyzed")
        print(f"{self.BOLD}Estimated Completion:{self.NC} {summary.estimated_completion}")
        print()

        # Confidence indicator
        confidence_color = self.GREEN if summary.confidence >= 70 else (self.YELLOW if summary.confidence >= 50 else self.RED)
        confidence_bar = self._generate_confidence_bar(summary.confidence)
        print(f"{self.BOLD}Confidence:{self.NC} {confidence_color}{summary.confidence}%{self.NC} {confidence_bar}")
        print()

        # Key findings
        print(f"{self.BOLD}Key Findings:{self.NC}")
        for i, finding in enumerate(summary.key_findings, 1):
            finding_display = finding[:100] + '...' if len(finding) > 100 else finding
            print(f"  {i}. {finding_display}")
        print()

        # Risks (especially important for investment)
        if summary.risks:
            print(f"{self.RED}{self.BOLD}Risks:{self.NC}")
            for risk in summary.risks:
                print(f"  {self.RED}!{self.NC} {risk}")
            print()

        # Investment warning
        if summary.domain == 'investment':
            print(f"{self.YELLOW}{self.BOLD}WARNING:{self.NC} This is investment research.")
            print(f"{self.YELLOW}Please review all findings carefully before making any decisions.{self.NC}")
            print(f"{self.YELLOW}This is not financial advice.{self.NC}")
            print()

        print(f"{self.BOLD}{'=' * 60}{self.NC}")

    def _generate_confidence_bar(self, confidence: int) -> str:
        """Generate a visual confidence bar"""
        filled = confidence // 10
        empty = 10 - filled
        color = self.GREEN if confidence >= 70 else (self.YELLOW if confidence >= 50 else self.RED)
        return f"[{color}{'#' * filled}{self.NC}{'.' * empty}]"

    def get_decision(self, timeout: Optional[int] = None) -> CheckpointDecision:
        """
        Get user decision at checkpoint (interactive).

        Args:
            timeout: Timeout in seconds (uses config default if not provided)

        Returns:
            User's checkpoint decision
        """
        timeout = timeout or self.config.timeout_seconds

        print(f"{self.BOLD}Please select an action:{self.NC}")
        print(f"  {self.GREEN}[a]{self.NC} Approve - Continue with research synthesis")
        print(f"  {self.BLUE}[m]{self.NC} More depth - Request additional research on findings")
        print(f"  {self.YELLOW}[r]{self.NC} Redirect - Change research direction")
        print(f"  {self.RED}[c]{self.NC} Cancel - Stop research")
        print()
        print(f"(Timeout in {timeout} seconds - defaults to 'cancel' if no input)")
        print()

        try:
            # Check if running in interactive mode
            if sys.stdin.isatty():
                user_input = self._get_input_with_timeout(timeout)
            else:
                # Non-interactive mode - default to cancel
                print("Non-interactive mode detected. Use --approve flag for auto-approval.")
                return CheckpointDecision.CANCEL

            user_input = user_input.strip().lower()

            if user_input in ['a', 'approve', 'yes', 'y']:
                return CheckpointDecision.APPROVE
            elif user_input in ['m', 'more', 'depth', 'more_depth']:
                return CheckpointDecision.REQUEST_MORE_DEPTH
            elif user_input in ['r', 'redirect']:
                return CheckpointDecision.REDIRECT
            elif user_input in ['c', 'cancel', 'n', 'no']:
                return CheckpointDecision.CANCEL
            else:
                print(f"Invalid input: '{user_input}'. Defaulting to cancel.")
                return CheckpointDecision.CANCEL

        except TimeoutError:
            print(f"\n{self.YELLOW}Timeout reached. Cancelling research.{self.NC}")
            return CheckpointDecision.CANCEL
        except KeyboardInterrupt:
            print(f"\n{self.YELLOW}Interrupted. Cancelling research.{self.NC}")
            return CheckpointDecision.CANCEL

    def _get_input_with_timeout(self, timeout: int) -> str:
        """Get user input with timeout"""
        print(f"{self.BOLD}Enter choice: {self.NC}", end='', flush=True)

        # Use select for timeout on Unix systems
        if hasattr(select, 'select'):
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if ready:
                return sys.stdin.readline()
            else:
                raise TimeoutError("Input timeout")
        else:
            # Fallback for Windows - no timeout support
            return input()

    def handle_redirect(self) -> str:
        """
        Get new research direction from user.

        Returns:
            New research direction/question
        """
        print()
        print(f"{self.BOLD}Enter new research direction:{self.NC}")
        print("(This will refocus the research on your new question)")
        print()

        try:
            new_direction = input(f"{self.BOLD}New direction: {self.NC}")
            return new_direction.strip()
        except KeyboardInterrupt:
            return ""

    def handle_more_depth(self) -> List[str]:
        """
        Get areas requiring more depth from user.

        Returns:
            List of areas to explore more deeply
        """
        print()
        print(f"{self.BOLD}Which areas need more depth?{self.NC}")
        print("(Enter areas separated by commas, or press Enter to explore all findings)")
        print()

        try:
            areas = input(f"{self.BOLD}Areas: {self.NC}")
            if not areas.strip():
                return []  # Empty means explore all
            return [a.strip() for a in areas.split(',') if a.strip()]
        except KeyboardInterrupt:
            return []

    def log_decision(self, decision: CheckpointDecision, summary: CheckpointSummary,
                     feedback: Optional[str] = None) -> None:
        """
        Log checkpoint decision for audit.

        Args:
            decision: The decision made
            summary: Checkpoint summary at time of decision
            feedback: Optional user feedback
        """
        if not self.config.log_decisions:
            return

        try:
            self.logger.log_decision(decision, summary, feedback)
        except Exception as e:
            print(f"{self.YELLOW}Warning: Failed to log decision: {e}{self.NC}")

    def run_checkpoint(self, summary: CheckpointSummary,
                       auto_approve: bool = False) -> tuple[CheckpointDecision, Optional[str]]:
        """
        Run a complete checkpoint flow.

        Args:
            summary: Checkpoint summary
            auto_approve: If True, auto-approve and log (non-interactive mode)

        Returns:
            Tuple of (decision, additional_data) where additional_data is
            redirect direction or areas for more depth
        """
        # Display summary
        self.display_summary(summary)

        # Auto-approve mode (non-interactive)
        if auto_approve:
            print(f"{self.GREEN}Auto-approving checkpoint (non-interactive mode){self.NC}")
            decision = CheckpointDecision.APPROVE
            self.log_decision(decision, summary, "Auto-approved (non-interactive mode)")
            return decision, None

        # Check if approval required
        if not summary.requires_human_approval:
            print(f"{self.GREEN}Checkpoint passed automatically (high confidence, non-critical domain){self.NC}")
            decision = CheckpointDecision.APPROVE
            self.log_decision(decision, summary, "Auto-passed (criteria met)")
            return decision, None

        # Get user decision
        decision = self.get_decision()
        additional_data = None

        # Handle decision
        if decision == CheckpointDecision.REDIRECT:
            additional_data = self.handle_redirect()
        elif decision == CheckpointDecision.REQUEST_MORE_DEPTH:
            areas = self.handle_more_depth()
            additional_data = ','.join(areas) if areas else 'all'

        # Log decision
        self.log_decision(decision, summary, additional_data)

        return decision, additional_data


class PendingCheckpoints:
    """Manager for pending checkpoints"""

    def __init__(self, state_dir: str = "./.claude-loop"):
        """
        Initialize pending checkpoints manager.

        Args:
            state_dir: Directory containing research states
        """
        self.state_dir = Path(state_dir)

    def list_pending(self) -> List[Dict[str, Any]]:
        """
        List all research with pending checkpoints.

        Returns:
            List of pending checkpoint summaries
        """
        pending = []

        # Find all research state files
        state_file = self.state_dir / "research-state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)

                # Check if checkpoint is needed
                config = CheckpointConfig()
                summary = CheckpointSummary.from_research_state(state, config)

                if summary.requires_human_approval and summary.status == 'pending':
                    pending.append(summary.to_dict())
            except Exception as e:
                print(f"Warning: Failed to read state file: {e}")

        # Also check sessions directory
        sessions_dir = self.state_dir / "sessions"
        if sessions_dir.exists():
            for session_file in sessions_dir.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        state = json.load(f)

                    config = CheckpointConfig()
                    summary = CheckpointSummary.from_research_state(state, config)

                    if summary.requires_human_approval and summary.status == 'pending':
                        pending.append(summary.to_dict())
                except Exception:
                    continue

        return pending

    def approve(self, research_id: str) -> bool:
        """
        Approve a pending checkpoint by research ID.

        Args:
            research_id: Research ID to approve

        Returns:
            True if approved successfully
        """
        # Find the research state
        state_file = self.state_dir / "research-state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)

                if state.get('researchId') == research_id:
                    # Log the approval
                    config = CheckpointConfig()
                    summary = CheckpointSummary.from_research_state(state, config)
                    checkpoint = HumanCheckpoint(config)
                    checkpoint.log_decision(
                        CheckpointDecision.APPROVE,
                        summary,
                        "Approved via CLI"
                    )
                    print(f"Approved checkpoint for research: {research_id}")
                    return True
            except Exception as e:
                print(f"Error approving checkpoint: {e}")

        print(f"Research not found: {research_id}")
        return False


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(description='Human Checkpoint System for Research Loop')
    parser.add_argument('--research-id', help='Research ID for operations')
    parser.add_argument('--summary', action='store_true', help='Display checkpoint summary')
    parser.add_argument('--list-pending', action='store_true', help='List pending checkpoints')
    parser.add_argument('--approve', metavar='ID', help='Approve checkpoint for research ID')
    parser.add_argument('--state-dir', default='./.claude-loop', help='Research state directory')
    parser.add_argument('--auto-approve', action='store_true', help='Auto-approve (non-interactive)')

    args = parser.parse_args()

    # List pending checkpoints
    if args.list_pending:
        manager = PendingCheckpoints(args.state_dir)
        pending = manager.list_pending()

        if not pending:
            print("No pending checkpoints.")
            return 0

        print(f"\nPending Checkpoints ({len(pending)}):")
        print("-" * 60)
        for item in pending:
            print(f"  ID: {item['research_id']}")
            print(f"  Domain: {item['domain']}")
            print(f"  Confidence: {item['confidence']}%")
            print(f"  Created: {item['created_at']}")
            print()
        return 0

    # Approve checkpoint
    if args.approve:
        manager = PendingCheckpoints(args.state_dir)
        success = manager.approve(args.approve)
        return 0 if success else 1

    # Display summary
    if args.summary and args.research_id:
        # Load research state
        state_file = Path(args.state_dir) / "research-state.json"
        if not state_file.exists():
            print(f"Error: Research state file not found")
            return 1

        with open(state_file, 'r') as f:
            state = json.load(f)

        if state.get('researchId') != args.research_id:
            print(f"Error: Research ID mismatch")
            return 1

        config = CheckpointConfig()
        summary = CheckpointSummary.from_research_state(state, config)

        checkpoint = HumanCheckpoint(config)
        decision, additional = checkpoint.run_checkpoint(summary, auto_approve=args.auto_approve)

        print(f"\nDecision: {decision.value}")
        if additional:
            print(f"Additional: {additional}")

        return 0 if decision == CheckpointDecision.APPROVE else 1

    # Interactive mode - run checkpoint from current state
    if args.research_id:
        manager = PendingCheckpoints(args.state_dir)
        state_file = Path(args.state_dir) / "research-state.json"

        if not state_file.exists():
            print(f"Error: No research state found")
            return 1

        with open(state_file, 'r') as f:
            state = json.load(f)

        config = CheckpointConfig()
        summary = CheckpointSummary.from_research_state(state, config)

        checkpoint = HumanCheckpoint(config)
        decision, additional = checkpoint.run_checkpoint(summary, auto_approve=args.auto_approve)

        return 0 if decision == CheckpointDecision.APPROVE else 1

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
