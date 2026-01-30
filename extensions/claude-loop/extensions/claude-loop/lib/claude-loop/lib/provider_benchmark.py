#!/usr/bin/env python3
"""
Provider Benchmarking Tool

Benchmark different LLM providers on the same tasks to compare:
- Latency (response time)
- Token usage (input/output)
- Cost (based on provider pricing)
- Output quality (human rating)

Usage:
    python3 lib/provider_benchmark.py run <prompt> --providers all
    python3 lib/provider_benchmark.py report --task-type <type>
    python3 lib/provider_benchmark.py export --format csv
"""

import json
import os
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.llm_config import LLMConfigManager, ProviderConfig
from lib.llm_provider import LLMProvider, Message, MessageRole


@dataclass
class BenchmarkResult:
    """Result from benchmarking a single provider on a prompt"""
    benchmark_id: str
    provider: str
    model: str
    prompt: str
    task_type: str
    response: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float
    quality_rating: Optional[float]  # Human rating 0-10 (optional)
    timestamp: str
    error: Optional[str] = None


@dataclass
class BenchmarkComparison:
    """Comparison across multiple providers for the same task"""
    task_type: str
    prompt: str
    results: List[BenchmarkResult]
    fastest_provider: str
    cheapest_provider: str
    avg_latency_ms: float
    avg_cost: float
    timestamp: str


class Benchmarker:
    """Benchmark different LLM providers on the same tasks"""

    def __init__(self, config_manager: Optional[LLMConfigManager] = None, db_path: Optional[str] = None):
        self.config_manager = config_manager or LLMConfigManager()
        self.db_path = db_path or os.path.expanduser("~/.claude-loop/benchmarks.db")
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for benchmark results"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                benchmark_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                task_type TEXT NOT NULL,
                response TEXT,
                latency_ms REAL NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost REAL NOT NULL,
                quality_rating REAL,
                timestamp TEXT NOT NULL,
                error TEXT
            )
        """)

        # Create indexes separately
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_provider ON benchmarks (provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_type ON benchmarks (task_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON benchmarks (timestamp)")

        conn.commit()
        conn.close()

    def run_benchmark(
        self,
        prompt: str,
        task_type: str = "general",
        providers: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> List[BenchmarkResult]:
        """
        Run the same prompt across multiple providers and collect results

        Args:
            prompt: The prompt to send to each provider
            task_type: Category of task (general, coding, reasoning, etc.)
            providers: List of provider names, or None for all enabled
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            List of benchmark results for each provider
        """
        if providers is None:
            # Use all enabled providers
            provider_list = self.config_manager.list_providers(enabled_only=True)
            providers = [config.name for config in provider_list]

        results = []

        for provider_name in providers:
            result = self._benchmark_provider(
                provider_name=provider_name,
                prompt=prompt,
                task_type=task_type,
                temperature=temperature,
                max_tokens=max_tokens
            )
            results.append(result)

            # Store result in database
            self._store_result(result)

        return results

    def _benchmark_provider(
        self,
        provider_name: str,
        prompt: str,
        task_type: str,
        temperature: float,
        max_tokens: int
    ) -> BenchmarkResult:
        """Benchmark a single provider"""
        benchmark_id = f"{provider_name}_{int(time.time() * 1000)}"
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            # Get provider config
            config = self.config_manager.get_provider(provider_name)
            if not config:
                raise ValueError(f"Provider {provider_name} not found")

            # Initialize provider
            provider = self._init_provider(provider_name, config)

            # Measure latency
            start_time = time.time()

            messages = [Message(role=MessageRole.USER, content=prompt)]
            response = provider.complete(
                messages=messages,
                model=config.default_model,
                temperature=temperature,
                max_tokens=max_tokens
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            return BenchmarkResult(
                benchmark_id=benchmark_id,
                provider=provider_name,
                model=response.model,
                prompt=prompt,
                task_type=task_type,
                response=response.content,
                latency_ms=latency_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost=response.cost,
                quality_rating=None,  # Set manually later
                timestamp=timestamp,
                error=None
            )

        except Exception as e:
            return BenchmarkResult(
                benchmark_id=benchmark_id,
                provider=provider_name,
                model="unknown",
                prompt=prompt,
                task_type=task_type,
                response="",
                latency_ms=0.0,
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                quality_rating=None,
                timestamp=timestamp,
                error=str(e)
            )

    def _init_provider(self, provider_name: str, config: ProviderConfig) -> LLMProvider:
        """Initialize a provider instance"""
        if provider_name == "openai":
            from lib.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(config)
        elif provider_name == "gemini":
            from lib.providers.gemini_provider import GeminiProvider
            return GeminiProvider(config)
        elif provider_name == "deepseek":
            from lib.providers.deepseek_provider import DeepSeekProvider
            return DeepSeekProvider(config)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def _store_result(self, result: BenchmarkResult) -> None:
        """Store benchmark result in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO benchmarks (
                benchmark_id, provider, model, prompt, task_type,
                response, latency_ms, input_tokens, output_tokens,
                cost, quality_rating, timestamp, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.benchmark_id,
            result.provider,
            result.model,
            result.prompt,
            result.task_type,
            result.response,
            result.latency_ms,
            result.input_tokens,
            result.output_tokens,
            result.cost,
            result.quality_rating,
            result.timestamp,
            result.error
        ))

        conn.commit()
        conn.close()

    def set_quality_rating(self, benchmark_id: str, rating: float) -> None:
        """
        Set human quality rating for a benchmark result

        Args:
            benchmark_id: ID of the benchmark result
            rating: Quality rating 0-10
        """
        if not 0 <= rating <= 10:
            raise ValueError("Rating must be between 0 and 10")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE benchmarks SET quality_rating = ? WHERE benchmark_id = ?",
            (rating, benchmark_id)
        )

        conn.commit()
        conn.close()

    def get_comparison(self, task_type: Optional[str] = None, limit: int = 100) -> List[BenchmarkComparison]:
        """
        Get benchmark comparisons grouped by prompt

        Args:
            task_type: Filter by task type (optional)
            limit: Maximum number of comparisons to return

        Returns:
            List of benchmark comparisons
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get unique prompts
        if task_type:
            cursor.execute(
                "SELECT DISTINCT prompt, task_type FROM benchmarks WHERE task_type = ? LIMIT ?",
                (task_type, limit)
            )
        else:
            cursor.execute(
                "SELECT DISTINCT prompt, task_type FROM benchmarks LIMIT ?",
                (limit,)
            )

        prompts = cursor.fetchall()
        comparisons = []

        for prompt, task_type_val in prompts:
            # Get all results for this prompt
            cursor.execute("""
                SELECT benchmark_id, provider, model, prompt, task_type,
                       response, latency_ms, input_tokens, output_tokens,
                       cost, quality_rating, timestamp, error
                FROM benchmarks
                WHERE prompt = ?
                ORDER BY timestamp DESC
            """, (prompt,))

            rows = cursor.fetchall()
            results = [
                BenchmarkResult(
                    benchmark_id=row[0],
                    provider=row[1],
                    model=row[2],
                    prompt=row[3],
                    task_type=row[4],
                    response=row[5],
                    latency_ms=row[6],
                    input_tokens=row[7],
                    output_tokens=row[8],
                    cost=row[9],
                    quality_rating=row[10],
                    timestamp=row[11],
                    error=row[12]
                )
                for row in rows
            ]

            # Calculate comparison stats
            successful_results = [r for r in results if r.error is None]

            if successful_results:
                fastest = min(successful_results, key=lambda r: r.latency_ms)
                cheapest = min(successful_results, key=lambda r: r.cost)
                avg_latency = sum(r.latency_ms for r in successful_results) / len(successful_results)
                avg_cost = sum(r.cost for r in successful_results) / len(successful_results)

                comparisons.append(BenchmarkComparison(
                    task_type=task_type_val,
                    prompt=prompt,
                    results=results,
                    fastest_provider=fastest.provider,
                    cheapest_provider=cheapest.provider,
                    avg_latency_ms=avg_latency,
                    avg_cost=avg_cost,
                    timestamp=results[0].timestamp
                ))

        conn.close()
        return comparisons

    def get_provider_stats(self, provider: Optional[str] = None) -> Dict[str, Dict]:
        """
        Get aggregate statistics for providers

        Args:
            provider: Specific provider name, or None for all

        Returns:
            Dictionary of provider stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if provider:
            cursor.execute("""
                SELECT provider,
                       COUNT(*) as count,
                       AVG(latency_ms) as avg_latency,
                       AVG(cost) as avg_cost,
                       AVG(quality_rating) as avg_quality,
                       AVG(input_tokens) as avg_input_tokens,
                       AVG(output_tokens) as avg_output_tokens,
                       COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count
                FROM benchmarks
                WHERE provider = ?
                GROUP BY provider
            """, (provider,))
        else:
            cursor.execute("""
                SELECT provider,
                       COUNT(*) as count,
                       AVG(latency_ms) as avg_latency,
                       AVG(cost) as avg_cost,
                       AVG(quality_rating) as avg_quality,
                       AVG(input_tokens) as avg_input_tokens,
                       AVG(output_tokens) as avg_output_tokens,
                       COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count
                FROM benchmarks
                GROUP BY provider
            """)

        rows = cursor.fetchall()
        conn.close()

        stats = {}
        for row in rows:
            stats[row[0]] = {
                "count": row[1],
                "avg_latency_ms": round(row[2], 2) if row[2] else None,
                "avg_cost": round(row[3], 6) if row[3] else None,
                "avg_quality": round(row[4], 2) if row[4] else None,
                "avg_input_tokens": round(row[5], 1) if row[5] else None,
                "avg_output_tokens": round(row[6], 1) if row[6] else None,
                "error_count": row[7],
                "success_rate": round((row[1] - row[7]) / row[1] * 100, 1) if row[1] > 0 else 0.0
            }

        return stats

    def export_to_csv(self, output_path: str, task_type: Optional[str] = None) -> None:
        """
        Export benchmark results to CSV

        Args:
            output_path: Path to output CSV file
            task_type: Filter by task type (optional)
        """
        import csv

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if task_type:
            cursor.execute("""
                SELECT benchmark_id, provider, model, task_type, prompt,
                       latency_ms, input_tokens, output_tokens, cost,
                       quality_rating, timestamp, error
                FROM benchmarks
                WHERE task_type = ?
                ORDER BY timestamp DESC
            """, (task_type,))
        else:
            cursor.execute("""
                SELECT benchmark_id, provider, model, task_type, prompt,
                       latency_ms, input_tokens, output_tokens, cost,
                       quality_rating, timestamp, error
                FROM benchmarks
                ORDER BY timestamp DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "benchmark_id", "provider", "model", "task_type", "prompt",
                "latency_ms", "input_tokens", "output_tokens", "cost",
                "quality_rating", "timestamp", "error"
            ])
            writer.writerows(rows)

    def export_to_json(self, output_path: str, task_type: Optional[str] = None) -> None:
        """
        Export benchmark results to JSON

        Args:
            output_path: Path to output JSON file
            task_type: Filter by task type (optional)
        """
        comparisons = self.get_comparison(task_type=task_type, limit=1000)

        data = {
            "task_type": task_type or "all",
            "comparisons": [
                {
                    "task_type": comp.task_type,
                    "prompt": comp.prompt,
                    "fastest_provider": comp.fastest_provider,
                    "cheapest_provider": comp.cheapest_provider,
                    "avg_latency_ms": comp.avg_latency_ms,
                    "avg_cost": comp.avg_cost,
                    "results": [asdict(r) for r in comp.results]
                }
                for comp in comparisons
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark LLM providers")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # run command
    run_parser = subparsers.add_parser("run", help="Run benchmark on prompt")
    run_parser.add_argument("prompt", help="Prompt to benchmark")
    run_parser.add_argument("--providers", default="all", help="Comma-separated provider names or 'all'")
    run_parser.add_argument("--task-type", default="general", help="Task type category")
    run_parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    run_parser.add_argument("--max-tokens", type=int, default=500, help="Maximum tokens to generate")
    run_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # report command
    report_parser = subparsers.add_parser("report", help="Show benchmark report")
    report_parser.add_argument("--task-type", help="Filter by task type")
    report_parser.add_argument("--provider", help="Filter by provider")
    report_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # export command
    export_parser = subparsers.add_parser("export", help="Export results")
    export_parser.add_argument("--format", choices=["csv", "json"], default="json", help="Export format")
    export_parser.add_argument("--task-type", help="Filter by task type")
    export_parser.add_argument("--output", required=True, help="Output file path")

    # rate command
    rate_parser = subparsers.add_parser("rate", help="Rate benchmark quality")
    rate_parser.add_argument("benchmark_id", help="Benchmark ID to rate")
    rate_parser.add_argument("rating", type=float, help="Quality rating 0-10")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show provider statistics")
    stats_parser.add_argument("--provider", help="Specific provider")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    benchmarker = Benchmarker()

    if args.command == "run":
        # Parse providers
        if args.providers == "all":
            providers = None
        else:
            providers = [p.strip() for p in args.providers.split(",")]

        # Run benchmark
        results = benchmarker.run_benchmark(
            prompt=args.prompt,
            task_type=args.task_type,
            providers=providers,
            temperature=args.temperature,
            max_tokens=args.max_tokens
        )

        if args.json:
            print(json.dumps([asdict(r) for r in results], indent=2))
        else:
            print(f"\nBenchmark Results ({len(results)} providers):")
            print("=" * 80)
            for result in results:
                if result.error:
                    print(f"\n{result.provider} ({result.model}): ERROR")
                    print(f"  Error: {result.error}")
                else:
                    print(f"\n{result.provider} ({result.model}):")
                    print(f"  Latency: {result.latency_ms:.0f}ms")
                    print(f"  Tokens: {result.input_tokens} in / {result.output_tokens} out")
                    print(f"  Cost: ${result.cost:.6f}")
                    print(f"  Response: {result.response[:100]}...")

    elif args.command == "report":
        comparisons = benchmarker.get_comparison(task_type=args.task_type)

        if args.json:
            print(json.dumps([
                {
                    "task_type": comp.task_type,
                    "prompt": comp.prompt[:50] + "...",
                    "fastest_provider": comp.fastest_provider,
                    "cheapest_provider": comp.cheapest_provider,
                    "avg_latency_ms": comp.avg_latency_ms,
                    "avg_cost": comp.avg_cost,
                    "num_providers": len(comp.results)
                }
                for comp in comparisons
            ], indent=2))
        else:
            print(f"\nBenchmark Report ({len(comparisons)} comparisons):")
            print("=" * 80)
            for comp in comparisons:
                print(f"\nTask: {comp.task_type}")
                print(f"Prompt: {comp.prompt[:60]}...")
                print(f"Fastest: {comp.fastest_provider} ({comp.avg_latency_ms:.0f}ms avg)")
                print(f"Cheapest: {comp.cheapest_provider} (${comp.avg_cost:.6f} avg)")
                print(f"Providers tested: {len(comp.results)}")

    elif args.command == "export":
        if args.format == "csv":
            benchmarker.export_to_csv(args.output, task_type=args.task_type)
        else:
            benchmarker.export_to_json(args.output, task_type=args.task_type)
        print(f"Exported to {args.output}")

    elif args.command == "rate":
        benchmarker.set_quality_rating(args.benchmark_id, args.rating)
        print(f"Set rating {args.rating}/10 for benchmark {args.benchmark_id}")

    elif args.command == "stats":
        stats = benchmarker.get_provider_stats(provider=args.provider)

        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\nProvider Statistics:")
            print("=" * 80)
            for provider, data in stats.items():
                print(f"\n{provider}:")
                print(f"  Benchmarks: {data['count']}")
                print(f"  Avg Latency: {data['avg_latency_ms']:.0f}ms" if data['avg_latency_ms'] else "  Avg Latency: N/A")
                print(f"  Avg Cost: ${data['avg_cost']:.6f}" if data['avg_cost'] else "  Avg Cost: N/A")
                print(f"  Avg Quality: {data['avg_quality']:.1f}/10" if data['avg_quality'] else "  Avg Quality: Not rated")
                print(f"  Success Rate: {data['success_rate']:.1f}%")


if __name__ == "__main__":
    main()
