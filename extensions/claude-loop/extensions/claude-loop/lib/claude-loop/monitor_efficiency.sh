#!/bin/bash
# Monitor benchmark progress and efficiency metrics

RESULTS_FILE="/Users/jialiang.wu/Documents/Projects/benchmark-results/benchmark_auto_with_fixes_results.json"
LOG_FILE="/tmp/benchmark_efficiency_monitor.log"

echo "=== Benchmark Efficiency Monitor ===" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    echo "=== Update: $(date) ===" | tee -a "$LOG_FILE"

    # Check if benchmark is running
    if ! ps aux | grep -q "[b]enchmark_auto_with_fixes.py"; then
        echo "Benchmark process not found. Either completed or not started." | tee -a "$LOG_FILE"

        # Check if results file exists with completed status
        if [ -f "$RESULTS_FILE" ]; then
            echo "Results file exists. Analyzing final results..." | tee -a "$LOG_FILE"
            python3 << 'EOF' | tee -a "$LOG_FILE"
import json
results_file = "/Users/jialiang.wu/Documents/Projects/benchmark-results/benchmark_auto_with_fixes_results.json"
try:
    with open(results_file, 'r') as f:
        data = json.load(f)

    total = data['summary']['total']
    successes = data['summary']['successes']
    success_rate = data['summary']['success_rate']

    metrics = data.get('efficiency_metrics', {})
    total_tokens = metrics.get('total_tokens', 0)
    total_cost = metrics.get('total_cost', 0)

    print(f"\n📊 FINAL RESULTS:")
    print(f"  Success Rate: {successes}/{total} ({success_rate*100:.1f}%)")
    print(f"  Total Tokens: {total_tokens:,}")
    print(f"  Total Cost: ${total_cost:.2f}")
    print(f"  Avg Tokens/Case: {total_tokens/total if total > 0 else 0:.0f}")
    print(f"  Avg Cost/Case: ${total_cost/total if total > 0 else 0:.4f}")

    opportunities = metrics.get('optimization_opportunities', [])
    if opportunities:
        print(f"\n💡 Optimization Opportunities: {len(opportunities)}")
        for i, opp in enumerate(opportunities[:3], 1):
            print(f"  {i}. {opp.get('type', 'Unknown')}")
            print(f"     → {opp.get('recommendation', 'No recommendation')}")

    print("\nBenchmark monitoring complete.")
except Exception as e:
    print(f"Error reading results: {e}")
EOF
            break
        else
            echo "No results file found yet." | tee -a "$LOG_FILE"
            break
        fi
    fi

    # Check current progress
    if [ -f "$RESULTS_FILE" ]; then
        echo "Progress update:" | tee -a "$LOG_FILE"
        python3 << 'EOF' | tee -a "$LOG_FILE"
import json
results_file = "/Users/jialiang.wu/Documents/Projects/benchmark-results/benchmark_auto_with_fixes_results.json"
try:
    with open(results_file, 'r') as f:
        data = json.load(f)

    results = data.get('results', [])
    total_expected = 50
    completed = len(results)
    successes = sum(1 for r in results if r.get('success', False))

    metrics = data.get('efficiency_metrics', {})
    total_tokens = metrics.get('total_tokens', 0)
    total_cost = metrics.get('total_cost', 0)

    print(f"  Cases completed: {completed}/50 ({completed/50*100:.0f}%)")
    print(f"  Success rate so far: {successes}/{completed} ({successes/completed*100:.1f}%)" if completed > 0 else "  No cases completed yet")
    print(f"  Tokens used: {total_tokens:,}")
    print(f"  Cost so far: ${total_cost:.2f}")
    print(f"  Avg tokens/case: {total_tokens/completed if completed > 0 else 0:.0f}")

    # Feature activation stats
    fa = metrics.get('feature_activations', {})
    filtered = fa.get('complexity_filtered', 0)
    if completed > 0:
        print(f"  Complexity filtered: {filtered}/{completed} ({filtered/completed*100:.0f}%)")

    # Estimate completion
    if completed > 0:
        results_sorted = sorted(results, key=lambda x: x.get('timestamp', ''))
        if len(results_sorted) >= 2:
            from datetime import datetime
            start = datetime.fromisoformat(results_sorted[0]['timestamp'])
            latest = datetime.fromisoformat(results_sorted[-1]['timestamp'])
            elapsed = (latest - start).total_seconds()
            avg_time_per_case = elapsed / completed
            remaining_cases = 50 - completed
            estimated_remaining = avg_time_per_case * remaining_cases
            print(f"  Estimated time remaining: {estimated_remaining/3600:.1f} hours")

except Exception as e:
    print(f"Error reading progress: {e}")
EOF
    else
        echo "  No results file yet. Waiting for benchmark to start..." | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    sleep 300  # Check every 5 minutes
done

echo "=== Monitoring Complete: $(date) ===" | tee -a "$LOG_FILE"
