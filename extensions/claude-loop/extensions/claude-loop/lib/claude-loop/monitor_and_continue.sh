#!/bin/bash

# Monitor current benchmark and automatically start agent-zero testing
# This script waits for the 2-way benchmark to complete, then starts 3-way

LOG_FILE="/tmp/benchmark_monitor.log"
BENCHMARK_LOG="/tmp/benchmark_100run.log"
RESULTS_DIR="/Users/jialiang.wu/Documents/Projects/benchmark-results"

echo "==================================================================" | tee -a "$LOG_FILE"
echo "BENCHMARK MONITOR - Automatic Continuation Script" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Function to check if benchmark is running
is_benchmark_running() {
    pgrep -f "benchmark_runner.py" > /dev/null
    return $?
}

# Phase 1: Wait for current benchmark to complete
echo "[Phase 1] Monitoring current 2-way benchmark (Baseline vs Claude-Loop)..." | tee -a "$LOG_FILE"
echo "Waiting for benchmark process to complete..." | tee -a "$LOG_FILE"

while is_benchmark_running; do
    # Show progress every 5 minutes
    echo "  [$(date '+%H:%M:%S')] Benchmark still running..." | tee -a "$LOG_FILE"
    tail -3 "$BENCHMARK_LOG" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    sleep 300  # Check every 5 minutes
done

echo "" | tee -a "$LOG_FILE"
echo "✓ 2-way benchmark completed at $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Small delay to ensure all files are written
sleep 10

# Phase 2: Quick analysis of 2-way results
echo "[Phase 2] Analyzing 2-way comparison results..." | tee -a "$LOG_FILE"
echo "Results directory: $RESULTS_DIR" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Count result files
RESULT_COUNT=$(find "$RESULTS_DIR" -name "*.json" -type f | wc -l)
echo "Found $RESULT_COUNT result files" | tee -a "$LOG_FILE"

# Show summary from benchmark log
echo "" | tee -a "$LOG_FILE"
echo "=== 2-Way Benchmark Summary ===" | tee -a "$LOG_FILE"
tail -50 "$BENCHMARK_LOG" | grep -E "(✓|✗|PASS|FAIL|Score)" | tail -20 | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Phase 3: Enable agent-zero in config
echo "[Phase 3] Enabling agent-zero for 3-way comparison..." | tee -a "$LOG_FILE"

cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks

# Create backup of current config
cp benchmark_runner.py benchmark_runner.py.backup

# Uncomment agent-zero line (line 612)
sed -i '' 's/# Subject.AGENT_ZERO,  # Debugging in parallel, will add later/Subject.AGENT_ZERO,  # ✅ Now operational with Claude 3 Haiku/' benchmark_runner.py

echo "✓ Agent-zero enabled in configuration" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Phase 4: Start 3-way benchmark
echo "[Phase 4] Starting 3-way benchmark (Baseline vs Claude-Loop vs Agent-Zero)..." | tee -a "$LOG_FILE"
echo "Configuration: 10 tasks × 3 subjects × 5 runs = 150 total executions" | tee -a "$LOG_FILE"
echo "Estimated duration: 3-4 hours" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Archive the 2-way results
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mv "$BENCHMARK_LOG" "/tmp/benchmark_2way_${TIMESTAMP}.log"
echo "✓ 2-way results archived to: /tmp/benchmark_2way_${TIMESTAMP}.log" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Start 3-way benchmark
NEW_LOG="/tmp/benchmark_3way.log"
python3 -u benchmark_runner.py 2>&1 | tee "$NEW_LOG" &
BENCHMARK_PID=$!

echo "✓ 3-way benchmark started with PID: $BENCHMARK_PID" | tee -a "$LOG_FILE"
echo "✓ Live output: tail -f $NEW_LOG" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
echo "Monitor script completed at $(date)" | tee -a "$LOG_FILE"
echo "The 3-way benchmark is now running in the background." | tee -a "$LOG_FILE"
echo "==================================================================" | tee -a "$LOG_FILE"
