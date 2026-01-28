#!/usr/bin/env python3
# pylint: disable=broad-except
"""
experience-retriever.py - Experience Retrieval with Feedback Loop for claude-loop

Provides intelligent experience retrieval with outcome tracking to learn
retrieval quality over time. Builds on experience-store.py to provide:

- Domain-filtered retrieval (exact or parent category match)
- Similarity ranking with quality weighting (similarity * helpful_rate * recency)
- Outcome tracking ('used', 'ignored', 'helped', 'hurt')
- Automatic decay for low helpful_rate experiences
- Quality reporting (hit rate, helpful rate by domain)
- JSONL logging of all retrieval outcomes

Usage:
    # Search for similar experiences with domain context
    python3 lib/experience-retriever.py search "UI element not found" \\
        --domain '{"project_type": "unity_xr", "language": "csharp"}'

    # Record feedback for a retrieved experience
    python3 lib/experience-retriever.py feedback <experience_id> --outcome helped

    # View retrieval quality report
    python3 lib/experience-retriever.py quality-report

    # Decay low-quality experiences
    python3 lib/experience-retriever.py decay --threshold 0.2 --min-retrievals 10

CLI Options:
    --db-dir DIR        Database directory (default: .claude-loop/experiences)
    --json              Output as JSON
    --verbose           Enable verbose output
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import from experience-store using importlib (handles hyphenated filename)
import importlib.util
_store_path = Path(__file__).parent / "experience-store.py"
_spec = importlib.util.spec_from_file_location("experience_store", _store_path)
_experience_store_module = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(_experience_store_module)  # type: ignore

ExperienceStore = _experience_store_module.ExperienceStore
ExperienceEntry = _experience_store_module.ExperienceEntry
DomainContext = _experience_store_module.DomainContext
DOMAIN_TYPES = _experience_store_module.DOMAIN_TYPES
DEFAULT_DB_DIR = _experience_store_module.DEFAULT_DB_DIR


# ============================================================================
# Constants
# ============================================================================

RETRIEVAL_LOG_FILE = ".claude-loop/retrieval_outcomes.jsonl"
DEFAULT_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75
MIN_HELPFUL_RATE = 0.20  # Experiences below this (with 10+ retrievals) get decayed
MIN_RETRIEVALS_FOR_DECAY = 10
DECAY_FACTOR = 0.5  # How much to reduce success_count on decay
RECENCY_HALF_LIFE_DAYS = 30  # Half-life for recency decay factor


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class RetrievalOutcome:
    """Records an outcome from retrieving an experience."""
    experience_id: str
    query: str
    domain_context: Dict[str, Any]
    outcome: str  # 'used', 'ignored', 'helped', 'hurt'
    similarity_score: float
    ranking_score: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'RetrievalOutcome':
        return cls(**data)


@dataclass
class RetrievalResult:
    """Result from a retrieval operation with ranking information."""
    experience: ExperienceEntry
    similarity_score: float
    helpful_rate: float
    recency_factor: float
    ranking_score: float

    def to_dict(self) -> dict:
        data = {
            'experience': self.experience.to_dict(),
            'similarity_score': round(self.similarity_score, 4),
            'helpful_rate': round(self.helpful_rate, 4),
            'recency_factor': round(self.recency_factor, 4),
            'ranking_score': round(self.ranking_score, 4),
        }
        return data


@dataclass
class QualityStats:
    """Quality statistics for retrieval performance."""
    total_retrievals: int
    retrievals_used: int
    retrievals_helped: int
    retrievals_ignored: int
    retrievals_hurt: int
    hit_rate: float  # retrievals_used / total_retrievals
    helpful_rate: float  # retrievals_helped / retrievals_used
    domain_stats: Dict[str, Dict[str, Any]]  # Per-domain breakdown
    time_period_days: int

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Experience Retriever Class
# ============================================================================

class ExperienceRetriever:
    """
    Intelligent experience retrieval with feedback loop.

    Retrieves similar experiences filtered by domain, ranked by a combination
    of similarity score, helpful rate, and recency. Tracks outcomes to learn
    what retrievals are actually useful.
    """

    def __init__(
        self,
        db_dir: str = DEFAULT_DB_DIR,
        log_file: str = RETRIEVAL_LOG_FILE,
        use_embeddings: bool = True,
    ):
        """Initialize the experience retriever.

        Args:
            db_dir: Directory for experience database
            log_file: Path to retrieval outcomes log
            use_embeddings: Whether to use sentence-transformer embeddings
        """
        self.store = ExperienceStore(db_dir=db_dir, use_embeddings=use_embeddings)
        self.log_file = Path(log_file)
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Create log directory if needed."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _calculate_recency_factor(self, last_used: str) -> float:
        """Calculate recency factor based on last_used timestamp.

        Uses exponential decay with configurable half-life.
        Recent experiences get higher weight.

        Args:
            last_used: ISO timestamp of last use

        Returns:
            Recency factor between 0 and 1
        """
        if not last_used:
            return 0.5  # Default for unknown

        try:
            last_used_dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            days_ago = (now - last_used_dt).days

            # Exponential decay: factor = 0.5^(days/half_life)
            decay = 0.5 ** (days_ago / RECENCY_HALF_LIFE_DAYS)
            return max(0.1, min(1.0, decay))  # Clamp to [0.1, 1.0]
        except (ValueError, TypeError):
            return 0.5

    def _calculate_ranking_score(
        self,
        similarity: float,
        helpful_rate: float,
        recency_factor: float,
    ) -> float:
        """Calculate combined ranking score.

        Formula: similarity * (helpful_rate / max(retrieval_count, 1)) * recency_factor
        For experiences with no retrievals, use default helpful_rate of 0.5

        Args:
            similarity: Cosine similarity score
            helpful_rate: Helpful count / retrieval count (or 0.5 if no retrievals)
            recency_factor: Recency decay factor

        Returns:
            Combined ranking score
        """
        # Use 0.5 as default helpful_rate for new experiences (no retrievals yet)
        effective_helpful_rate = helpful_rate if helpful_rate > 0 else 0.5

        return similarity * effective_helpful_rate * recency_factor

    def retrieve_similar(
        self,
        problem: str,
        domain_context: Optional[DomainContext] = None,
        k: int = DEFAULT_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> List[RetrievalResult]:
        """Retrieve similar experiences with domain filtering and quality ranking.

        Filters by domain (exact match first, then parent category).
        Only returns experiences above similarity threshold.
        Ranks by: similarity * helpful_rate * recency_factor

        Args:
            problem: Problem description to search for
            domain_context: Domain context for filtering (optional)
            k: Maximum number of results
            similarity_threshold: Minimum cosine similarity (default 0.75)

        Returns:
            List of RetrievalResult with ranking information
        """
        results: List[RetrievalResult] = []

        # Search with domain filtering
        raw_results = self.store.search_similar(
            problem=problem,
            domain_context=domain_context,
            k=k * 2,  # Fetch extra to filter by helpful_rate
            similarity_threshold=similarity_threshold,
        )

        for experience, similarity in raw_results:
            helpful_rate = experience.get_helpful_rate()
            recency_factor = self._calculate_recency_factor(experience.last_used)
            ranking_score = self._calculate_ranking_score(
                similarity, helpful_rate, recency_factor
            )

            results.append(RetrievalResult(
                experience=experience,
                similarity_score=similarity,
                helpful_rate=helpful_rate,
                recency_factor=recency_factor,
                ranking_score=ranking_score,
            ))

        # Sort by ranking score and return top k
        results.sort(key=lambda x: x.ranking_score, reverse=True)
        return results[:k]

    def mark_retrieval_outcome(
        self,
        experience_id: str,
        outcome: str,
        query: str = "",
        domain_context: Optional[DomainContext] = None,
        similarity_score: float = 0.0,
        ranking_score: float = 0.0,
    ) -> bool:
        """Mark the outcome of a retrieved experience.

        Updates the experience store with outcome and logs to JSONL.

        Args:
            experience_id: ID of the experience
            outcome: One of 'used', 'ignored', 'helped', 'hurt'
            query: The original query (for logging)
            domain_context: Domain context used (for logging)
            similarity_score: Similarity score (for logging)
            ranking_score: Ranking score (for logging)

        Returns:
            True if successful
        """
        valid_outcomes = ['used', 'ignored', 'helped', 'hurt']
        if outcome not in valid_outcomes:
            print(f"Invalid outcome '{outcome}'. Must be one of: {valid_outcomes}",
                  file=sys.stderr)
            return False

        # Update experience store
        success = self.store.update_retrieval_outcome(experience_id, outcome)
        if not success:
            return False

        # Log outcome
        log_entry = RetrievalOutcome(
            experience_id=experience_id,
            query=query,
            domain_context=domain_context.to_dict() if domain_context else {},
            outcome=outcome,
            similarity_score=similarity_score,
            ranking_score=ranking_score,
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        )
        self._log_outcome(log_entry)

        return True

    def _log_outcome(self, outcome: RetrievalOutcome) -> None:
        """Append outcome to JSONL log file."""
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(outcome.to_dict()) + '\n')
        except IOError as e:
            print(f"Warning: Failed to log outcome: {e}", file=sys.stderr)

    def decay_low_quality_experiences(
        self,
        min_helpful_rate: float = MIN_HELPFUL_RATE,
        min_retrievals: int = MIN_RETRIEVALS_FOR_DECAY,
        dry_run: bool = False,
    ) -> List[Tuple[str, float]]:
        """Decay experiences with low helpful_rate.

        Reduces success_count for experiences below threshold.
        Only applies to experiences with sufficient retrieval history.

        Args:
            min_helpful_rate: Threshold below which to decay (default 0.2)
            min_retrievals: Minimum retrievals before decay applies (default 10)
            dry_run: If True, report what would be decayed without doing it

        Returns:
            List of (experience_id, helpful_rate) that were/would be decayed
        """
        decayed = []
        all_experiences = self.store._get_all_experiences()

        for exp in all_experiences:
            if exp.retrieval_count < min_retrievals:
                continue

            helpful_rate = exp.get_helpful_rate()
            if helpful_rate < min_helpful_rate:
                if not dry_run:
                    # Reduce success_count by decay factor
                    new_success = max(0, int(exp.success_count * DECAY_FACTOR))
                    self.store._update_experience_metadata(exp, {
                        'success_count': new_success,
                    })
                decayed.append((exp.id, helpful_rate))

        return decayed

    def get_quality_report(self, days: int = 30) -> QualityStats:
        """Generate quality statistics for retrieval performance.

        Analyzes retrieval outcomes log to calculate metrics.

        Args:
            days: Number of days to analyze (default 30)

        Returns:
            QualityStats with hit rates and domain breakdown
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat().replace('+00:00', 'Z')

        # Initialize counters
        total = 0
        used = 0
        helped = 0
        ignored = 0
        hurt = 0
        domain_data: Dict[str, Dict[str, int]] = {}

        # Read and analyze log file
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get('timestamp', '') < cutoff_str:
                                continue

                            outcome = entry.get('outcome', '')
                            total += 1

                            if outcome == 'used':
                                used += 1
                            elif outcome == 'helped':
                                helped += 1
                                used += 1  # helped implies used
                            elif outcome == 'ignored':
                                ignored += 1
                            elif outcome == 'hurt':
                                hurt += 1
                                used += 1  # hurt implies used

                            # Domain breakdown
                            domain_ctx = entry.get('domain_context', {})
                            domain_type = domain_ctx.get('project_type', 'other')
                            if domain_type not in domain_data:
                                domain_data[domain_type] = {
                                    'total': 0, 'used': 0, 'helped': 0,
                                    'ignored': 0, 'hurt': 0
                                }
                            domain_data[domain_type]['total'] += 1
                            domain_data[domain_type][outcome] += 1

                        except json.JSONDecodeError:
                            continue
            except IOError:
                pass

        # Calculate rates
        hit_rate = used / total if total > 0 else 0.0
        helpful_rate = helped / used if used > 0 else 0.0

        # Calculate domain stats
        domain_stats = {}
        for domain, counts in domain_data.items():
            domain_total = counts['total']
            domain_used = counts.get('used', 0) + counts.get('helped', 0) + counts.get('hurt', 0)
            domain_helped = counts.get('helped', 0)
            domain_stats[domain] = {
                'total_retrievals': domain_total,
                'hit_rate': domain_used / domain_total if domain_total > 0 else 0.0,
                'helpful_rate': domain_helped / domain_used if domain_used > 0 else 0.0,
            }

        return QualityStats(
            total_retrievals=total,
            retrievals_used=used,
            retrievals_helped=helped,
            retrievals_ignored=ignored,
            retrievals_hurt=hurt,
            hit_rate=round(hit_rate, 4),
            helpful_rate=round(helpful_rate, 4),
            domain_stats=domain_stats,
            time_period_days=days,
        )

    def get_retrieval_history(
        self,
        experience_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[RetrievalOutcome]:
        """Get retrieval history from log file.

        Args:
            experience_id: Filter by experience ID (optional)
            limit: Maximum entries to return

        Returns:
            List of RetrievalOutcome entries
        """
        outcomes = []

        if not self.log_file.exists():
            return outcomes

        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()

            # Process in reverse order (most recent first)
            for line in reversed(lines):
                if len(outcomes) >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if experience_id and entry.get('experience_id') != experience_id:
                        continue
                    outcomes.append(RetrievalOutcome.from_dict(entry))
                except json.JSONDecodeError:
                    continue

        except IOError:
            pass

        return outcomes


# ============================================================================
# CLI Interface
# ============================================================================

def _parse_domain_context(args: argparse.Namespace) -> Optional[DomainContext]:
    """Parse domain context from CLI arguments."""
    if hasattr(args, 'domain') and args.domain:
        try:
            domain_data = json.loads(args.domain)
            return DomainContext.from_dict(domain_data)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --domain", file=sys.stderr)
            return None
    elif hasattr(args, 'domain_type') and args.domain_type:
        return DomainContext(project_type=args.domain_type)
    return None


def cmd_search(args: argparse.Namespace, retriever: ExperienceRetriever) -> int:
    """Search for similar experiences with quality ranking."""
    domain_context = _parse_domain_context(args)

    results = retriever.retrieve_similar(
        problem=args.query,
        domain_context=domain_context,
        k=args.limit,
        similarity_threshold=args.threshold,
    )

    if args.json:
        output = {
            "count": len(results),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        if not results:
            print("No similar experiences found")
            return 0

        print(f"Similar Experiences ({len(results)}):")
        for result in results:
            exp = result.experience
            problem_preview = (exp.problem_signature[:50] + "..."
                             if len(exp.problem_signature) > 50
                             else exp.problem_signature)

            print(f"\n  [{exp.id}]")
            print(f"    Ranking Score: {result.ranking_score:.3f}")
            print(f"      - Similarity:   {result.similarity_score:.3f}")
            print(f"      - Helpful Rate: {result.helpful_rate:.3f}")
            print(f"      - Recency:      {result.recency_factor:.3f}")
            print(f"    Domain:   {exp.domain_context.project_type}")
            print(f"    Problem:  {problem_preview}")
            print(f"    Solution: {exp.solution_approach[:60]}...")
            print(f"    Stats:    {exp.helpful_count}/{exp.retrieval_count} helpful")

    return 0


def cmd_feedback(args: argparse.Namespace, retriever: ExperienceRetriever) -> int:
    """Record feedback for a retrieved experience."""
    success = retriever.mark_retrieval_outcome(
        experience_id=args.experience_id,
        outcome=args.outcome,
        query=getattr(args, 'query', ''),
    )

    if args.json:
        result = {
            "success": success,
            "experience_id": args.experience_id,
            "outcome": args.outcome,
        }
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"Recorded feedback '{args.outcome}' for {args.experience_id}")
        else:
            print(f"Failed to record feedback: experience not found", file=sys.stderr)
            return 1

    return 0


def cmd_quality_report(args: argparse.Namespace, retriever: ExperienceRetriever) -> int:
    """Show retrieval quality report."""
    stats = retriever.get_quality_report(days=args.days)

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2))
    else:
        print(f"Retrieval Quality Report (last {stats.time_period_days} days)")
        print("=" * 50)
        print(f"\nOverall Statistics:")
        print(f"  Total retrievals:  {stats.total_retrievals}")
        print(f"  Used:              {stats.retrievals_used}")
        print(f"  Helped:            {stats.retrievals_helped}")
        print(f"  Ignored:           {stats.retrievals_ignored}")
        print(f"  Hurt:              {stats.retrievals_hurt}")
        print(f"\n  Hit Rate:          {stats.hit_rate:.2%}")
        print(f"  Helpful Rate:      {stats.helpful_rate:.2%}")

        if stats.domain_stats:
            print(f"\nBy Domain:")
            for domain, domain_stat in sorted(stats.domain_stats.items()):
                print(f"\n  [{domain}]")
                print(f"    Retrievals:   {domain_stat['total_retrievals']}")
                print(f"    Hit Rate:     {domain_stat['hit_rate']:.2%}")
                print(f"    Helpful Rate: {domain_stat['helpful_rate']:.2%}")

    return 0


def cmd_decay(args: argparse.Namespace, retriever: ExperienceRetriever) -> int:
    """Decay low-quality experiences."""
    decayed = retriever.decay_low_quality_experiences(
        min_helpful_rate=args.threshold,
        min_retrievals=args.min_retrievals,
        dry_run=args.dry_run,
    )

    if args.json:
        result = {
            "decayed_count": len(decayed),
            "dry_run": args.dry_run,
            "decayed": [{"id": id, "helpful_rate": rate} for id, rate in decayed],
        }
        print(json.dumps(result, indent=2))
    else:
        action = "Would decay" if args.dry_run else "Decayed"
        if decayed:
            print(f"{action} {len(decayed)} low-quality experiences:")
            for exp_id, rate in decayed:
                print(f"  {exp_id}: helpful_rate={rate:.2%}")
        else:
            print("No experiences below threshold")

    return 0


def cmd_history(args: argparse.Namespace, retriever: ExperienceRetriever) -> int:
    """Show retrieval history."""
    history = retriever.get_retrieval_history(
        experience_id=getattr(args, 'experience_id', None),
        limit=args.limit,
    )

    if args.json:
        result = {
            "count": len(history),
            "entries": [h.to_dict() for h in history],
        }
        print(json.dumps(result, indent=2))
    else:
        if not history:
            print("No retrieval history found")
            return 0

        print(f"Retrieval History ({len(history)} entries):")
        for entry in history:
            print(f"\n  {entry.timestamp}")
            print(f"    Experience: {entry.experience_id}")
            print(f"    Outcome:    {entry.outcome}")
            if entry.query:
                query_preview = (entry.query[:50] + "..."
                               if len(entry.query) > 50 else entry.query)
                print(f"    Query:      {query_preview}")
            if entry.similarity_score > 0:
                print(f"    Similarity: {entry.similarity_score:.3f}")

    return 0


def create_parser():
    """Create argument parser."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"Database directory (default: {DEFAULT_DB_DIR})",
    )
    parent_parser.add_argument(
        "--log-file",
        default=RETRIEVAL_LOG_FILE,
        help=f"Retrieval outcomes log file (default: {RETRIEVAL_LOG_FILE})",
    )
    parent_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parent_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parent_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Use hash-based embeddings (skip sentence-transformers)",
    )

    # Main parser
    parser = argparse.ArgumentParser(
        description="Experience Retrieval with Feedback Loop for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # search command
    search_parser = subparsers.add_parser(
        "search", help="Search for similar experiences with quality ranking",
        parents=[parent_parser]
    )
    search_parser.add_argument("query", help="Problem description to search for")
    search_parser.add_argument(
        "--domain-type",
        choices=DOMAIN_TYPES,
        help="Filter by domain type",
    )
    search_parser.add_argument(
        "--domain", "-d",
        help="Full domain context as JSON",
    )
    search_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=DEFAULT_K,
        help=f"Maximum number of results (default: {DEFAULT_K})",
    )
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Minimum similarity threshold (default: {DEFAULT_SIMILARITY_THRESHOLD})",
    )

    # feedback command
    feedback_parser = subparsers.add_parser(
        "feedback", help="Record feedback for a retrieved experience",
        parents=[parent_parser]
    )
    feedback_parser.add_argument("experience_id", help="Experience ID")
    feedback_parser.add_argument(
        "--outcome",
        choices=["used", "ignored", "helped", "hurt"],
        required=True,
        help="Retrieval outcome",
    )
    feedback_parser.add_argument(
        "--query",
        help="Original query (for logging)",
    )

    # quality-report command
    report_parser = subparsers.add_parser(
        "quality-report", help="Show retrieval quality report",
        parents=[parent_parser]
    )
    report_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)",
    )

    # decay command
    decay_parser = subparsers.add_parser(
        "decay", help="Decay low-quality experiences",
        parents=[parent_parser]
    )
    decay_parser.add_argument(
        "--threshold",
        type=float,
        default=MIN_HELPFUL_RATE,
        help=f"Minimum helpful_rate threshold (default: {MIN_HELPFUL_RATE})",
    )
    decay_parser.add_argument(
        "--min-retrievals",
        type=int,
        default=MIN_RETRIEVALS_FOR_DECAY,
        help=f"Minimum retrievals before decay applies (default: {MIN_RETRIEVALS_FOR_DECAY})",
    )
    decay_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be decayed without doing it",
    )

    # history command
    history_parser = subparsers.add_parser(
        "history", help="Show retrieval history",
        parents=[parent_parser]
    )
    history_parser.add_argument(
        "--experience-id",
        help="Filter by experience ID",
    )
    history_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum entries to show (default: 100)",
    )

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize retriever
    retriever = ExperienceRetriever(
        db_dir=args.db_dir,
        log_file=args.log_file,
        use_embeddings=not args.no_embeddings,
    )

    # Dispatch to command handler
    commands = {
        "search": cmd_search,
        "feedback": cmd_feedback,
        "quality-report": cmd_quality_report,
        "decay": cmd_decay,
        "history": cmd_history,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args, retriever)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
