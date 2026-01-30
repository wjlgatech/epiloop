#!/bin/bash
#
# monitoring.sh - Real-time monitoring and cost tracking for claude-loop
#
# Provides functions to track:
#   - Token usage (input/output)
#   - Cost calculation (Opus pricing: $15/M input, $75/M output)
#   - Iteration duration
#   - Live terminal display with cost ticker
#
# Usage:
#   source lib/monitoring.sh
#   start_monitoring
#   track_iteration "$story_id" "$tokens_in" "$tokens_out" "$duration_ms"
#   end_monitoring

# ============================================================================
# Pricing Configuration (Claude Opus 4)
# ============================================================================

# Pricing per million tokens (USD)
PRICE_INPUT_PER_M=15.00    # $15 per 1M input tokens
PRICE_OUTPUT_PER_M=75.00   # $75 per 1M output tokens

# ============================================================================
# Monitoring State Variables
# ============================================================================

# Session totals
MONITORING_TOTAL_TOKENS_IN=0
MONITORING_TOTAL_TOKENS_OUT=0
MONITORING_TOTAL_COST_USD=0
MONITORING_TOTAL_DURATION_MS=0
MONITORING_ITERATION_COUNT=0
MONITORING_START_TIME=""
MONITORING_SESSION_ID=""

# Current iteration tracking
MONITORING_CURRENT_ITER_START=""
MONITORING_CURRENT_STORY_ID=""
MONITORING_CURRENT_STORY_TITLE=""
MONITORING_CURRENT_AGENTS=""
MONITORING_CURRENT_AGENT_REASONING=""
MONITORING_CURRENT_MODEL=""

# Model usage tracking
MONITORING_MODEL_COUNTS_HAIKU=0
MONITORING_MODEL_COUNTS_SONNET=0
MONITORING_MODEL_COUNTS_OPUS=0

# Cache statistics tracking
MONITORING_CACHE_HITS=0
MONITORING_CACHE_MISSES=0
MONITORING_CACHE_SAVED_TOKENS=0

# Parallel execution tracking
MONITORING_PARALLEL_ENABLED=false
MONITORING_PARALLEL_BATCHES=0
MONITORING_PARALLEL_TIME_MS=0
MONITORING_SEQUENTIAL_ESTIMATE_MS=0
MONITORING_PARALLEL_WORKERS_USED=0
MONITORING_PARALLEL_MAX_CONCURRENT=0

# Display settings
MONITORING_TICKER_ENABLED=true
MONITORING_TICKER_PID=""

# JSON logging settings
MONITORING_JSON_ENABLED=true
MONITORING_RUN_DIR=""
MONITORING_METRICS_FILE=""
MONITORING_ITERATIONS_DATA=""  # JSON array of iteration data

# HTML report settings
MONITORING_HTML_ENABLED=true
MONITORING_REPORT_FILE=""

# Colors for monitoring output
MON_CYAN='\033[0;36m'
MON_GREEN='\033[0;32m'
MON_YELLOW='\033[1;33m'
MON_MAGENTA='\033[0;35m'
MON_NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

# Get current timestamp in milliseconds
get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: use perl for millisecond precision
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        # Linux: use date with nanoseconds
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Get current timestamp as ISO string
get_timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Calculate cost from token counts (default: Opus pricing)
calculate_cost() {
    local tokens_in="$1"
    local tokens_out="$2"

    # Use bc for floating point calculation
    # Cost = (tokens_in / 1000000) * PRICE_INPUT + (tokens_out / 1000000) * PRICE_OUTPUT
    local cost
    cost=$(echo "scale=6; ($tokens_in / 1000000) * $PRICE_INPUT_PER_M + ($tokens_out / 1000000) * $PRICE_OUTPUT_PER_M" | bc)
    echo "$cost"
}

# Model-specific pricing per million tokens (USD)
# Haiku:  $0.25/M input, $1.25/M output
# Sonnet: $3/M input, $15/M output
# Opus:   $15/M input, $75/M output

# Calculate cost for a specific model
calculate_cost_for_model() {
    local tokens_in="$1"
    local tokens_out="$2"
    local model="${3:-opus}"

    local input_price output_price

    case "$model" in
        haiku)
            input_price=0.25
            output_price=1.25
            ;;
        sonnet)
            input_price=3.00
            output_price=15.00
            ;;
        opus|*)
            input_price=15.00
            output_price=75.00
            ;;
    esac

    local cost
    cost=$(echo "scale=6; ($tokens_in / 1000000) * $input_price + ($tokens_out / 1000000) * $output_price" | bc)
    echo "$cost"
}

# Calculate what cost would have been with Opus (for savings comparison)
calculate_opus_baseline_cost() {
    local tokens_in="$1"
    local tokens_out="$2"

    local cost
    cost=$(echo "scale=6; ($tokens_in / 1000000) * 15.00 + ($tokens_out / 1000000) * 75.00" | bc)
    echo "$cost"
}

# Format cost for display (e.g., "$0.0023" or "$1.23")
format_cost() {
    local cost="$1"
    printf "$%.4f" "$cost"
}

# Format duration for display (e.g., "1.23s" or "2m 15s")
format_duration() {
    local duration_ms="$1"
    local duration_s=$((duration_ms / 1000))

    if [ "$duration_s" -lt 60 ]; then
        echo "${duration_s}s"
    else
        local mins=$((duration_s / 60))
        local secs=$((duration_s % 60))
        echo "${mins}m ${secs}s"
    fi
}

# Format token count for display (e.g., "1.2K" or "1.5M")
format_tokens() {
    local tokens="$1"

    if [ "$tokens" -lt 1000 ]; then
        echo "$tokens"
    elif [ "$tokens" -lt 1000000 ]; then
        echo "$(echo "scale=1; $tokens / 1000" | bc)K"
    else
        echo "$(echo "scale=2; $tokens / 1000000" | bc)M"
    fi
}

# ============================================================================
# Core Monitoring Functions
# ============================================================================

# Initialize monitoring for a new run
start_monitoring() {
    MONITORING_SESSION_ID=$(date +%Y%m%d_%H%M%S)
    MONITORING_START_TIME=$(get_timestamp_ms)
    MONITORING_TOTAL_TOKENS_IN=0
    MONITORING_TOTAL_TOKENS_OUT=0
    MONITORING_TOTAL_COST_USD=0
    MONITORING_TOTAL_DURATION_MS=0
    MONITORING_ITERATION_COUNT=0

    # Initialize JSON logging
    init_json_logging

    # Display monitoring header
    echo ""
    echo -e "${MON_CYAN}[MONITORING]${MON_NC} Session started: $MONITORING_SESSION_ID"
    echo -e "${MON_CYAN}[MONITORING]${MON_NC} Pricing: \$${PRICE_INPUT_PER_M}/M input, \$${PRICE_OUTPUT_PER_M}/M output"
    echo ""
}

# Start tracking a single iteration
# Usage: start_iteration "story_id" "story_title" "agents_list" "reasoning" "model"
start_iteration() {
    local story_id="$1"
    local story_title="${2:-}"
    local agents="${3:-}"
    local reasoning="${4:-}"
    local model="${5:-sonnet}"

    MONITORING_CURRENT_ITER_START=$(get_timestamp_ms)
    MONITORING_CURRENT_STORY_ID="$story_id"
    MONITORING_CURRENT_STORY_TITLE="$story_title"
    MONITORING_CURRENT_AGENTS="$agents"
    MONITORING_CURRENT_AGENT_REASONING="$reasoning"
    MONITORING_CURRENT_MODEL="$model"

    # Show iteration start with agent info
    echo ""
    echo -e "${MON_CYAN}[COST]${MON_NC} Starting iteration for $story_id..."

    # Display agent-task association
    if [ -n "$agents" ]; then
        # Display each agent working on this task
        for agent in $(echo "$agents" | tr ',' ' '); do
            if [ -n "$agent" ]; then
                echo -e "${MON_MAGENTA}[AGENT: ${agent}]${MON_NC} Working on: ${story_id} - ${story_title}"
            fi
        done
    fi
}

# Set current agent info (can be called separately for verbose mode)
set_current_agent_info() {
    local agents="${1:-}"
    local reasoning="${2:-}"

    MONITORING_CURRENT_AGENTS="$agents"
    MONITORING_CURRENT_AGENT_REASONING="$reasoning"
}

# Display agent selection reasoning (for verbose mode)
display_agent_reasoning() {
    local verbose="${1:-false}"

    if [ "$verbose" != "true" ]; then
        return
    fi

    if [ -n "$MONITORING_CURRENT_AGENT_REASONING" ]; then
        echo -e "${MON_CYAN}[AGENT SELECTION]${MON_NC} Reasoning:"
        # Display each line of reasoning with indentation
        echo "$MONITORING_CURRENT_AGENT_REASONING" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                echo -e "  ${line}"
            fi
        done
    fi
}

# Record metrics for a completed iteration
# Usage: track_iteration "$story_id" "$tokens_in" "$tokens_out" "$status" "$agents_used" "$model"
track_iteration() {
    local story_id="$1"
    local tokens_in="${2:-0}"
    local tokens_out="${3:-0}"
    local status="${4:-unknown}"
    local agents_used="${5:-}"
    local model="${6:-$MONITORING_CURRENT_MODEL}"

    # Calculate duration
    local iter_end
    iter_end=$(get_timestamp_ms)
    local duration_ms=0
    if [ -n "$MONITORING_CURRENT_ITER_START" ]; then
        duration_ms=$((iter_end - MONITORING_CURRENT_ITER_START))
    fi

    # Calculate cost for this iteration (using actual model pricing)
    local iter_cost
    iter_cost=$(calculate_cost_for_model "$tokens_in" "$tokens_out" "$model")

    # Update totals
    MONITORING_TOTAL_TOKENS_IN=$((MONITORING_TOTAL_TOKENS_IN + tokens_in))
    MONITORING_TOTAL_TOKENS_OUT=$((MONITORING_TOTAL_TOKENS_OUT + tokens_out))
    MONITORING_TOTAL_COST_USD=$(echo "$MONITORING_TOTAL_COST_USD + $iter_cost" | bc)
    MONITORING_TOTAL_DURATION_MS=$((MONITORING_TOTAL_DURATION_MS + duration_ms))
    MONITORING_ITERATION_COUNT=$((MONITORING_ITERATION_COUNT + 1))

    # Update model usage counts
    case "$model" in
        haiku)
            MONITORING_MODEL_COUNTS_HAIKU=$((MONITORING_MODEL_COUNTS_HAIKU + 1))
            ;;
        sonnet)
            MONITORING_MODEL_COUNTS_SONNET=$((MONITORING_MODEL_COUNTS_SONNET + 1))
            ;;
        opus)
            MONITORING_MODEL_COUNTS_OPUS=$((MONITORING_MODEL_COUNTS_OPUS + 1))
            ;;
    esac

    # Display iteration summary
    display_iteration_cost "$story_id" "$tokens_in" "$tokens_out" "$iter_cost" "$duration_ms" "$model"

    # Log to JSON file
    log_iteration_json "$story_id" "$tokens_in" "$tokens_out" "$duration_ms" "$status" "$agents_used" "" "$model"
}

# Display cost ticker for current iteration
display_iteration_cost() {
    local story_id="$1"
    local tokens_in="$2"
    local tokens_out="$3"
    local cost="$4"
    local duration_ms="$5"
    local model="${6:-opus}"

    local formatted_cost
    formatted_cost=$(format_cost "$cost")
    local formatted_duration
    formatted_duration=$(format_duration "$duration_ms")
    local formatted_in
    formatted_in=$(format_tokens "$tokens_in")
    local formatted_out
    formatted_out=$(format_tokens "$tokens_out")

    echo -e "${MON_GREEN}[COST]${MON_NC} $story_id: ${formatted_in} in / ${formatted_out} out | ${MON_YELLOW}${formatted_cost}${MON_NC} | ${formatted_duration} | model: $model"
}

# Display running total (live ticker)
display_running_total() {
    local formatted_cost
    formatted_cost=$(format_cost "$MONITORING_TOTAL_COST_USD")
    local formatted_in
    formatted_in=$(format_tokens "$MONITORING_TOTAL_TOKENS_IN")
    local formatted_out
    formatted_out=$(format_tokens "$MONITORING_TOTAL_TOKENS_OUT")
    local formatted_duration
    formatted_duration=$(format_duration "$MONITORING_TOTAL_DURATION_MS")

    # Build agent info string if available
    local agent_info=""
    if [ -n "$MONITORING_CURRENT_AGENTS" ]; then
        # Count agents
        local agent_count
        agent_count=$(echo "$MONITORING_CURRENT_AGENTS" | tr ',' '\n' | grep -c . || echo 0)
        if [ "$agent_count" -gt 0 ]; then
            agent_info=" | ${MON_MAGENTA}${agent_count} agent(s)${MON_NC}"
        fi
    fi

    echo -e "${MON_CYAN}[TOTAL]${MON_NC} ${MONITORING_ITERATION_COUNT} iterations | ${formatted_in} in / ${formatted_out} out | ${MON_YELLOW}${formatted_cost}${MON_NC} | ${formatted_duration}${agent_info}"
}

# Get current agent info as formatted string
get_current_agent_display() {
    if [ -n "$MONITORING_CURRENT_AGENTS" ]; then
        echo "$MONITORING_CURRENT_AGENTS" | tr ',' ', '
    fi
}

# End monitoring and display final summary
end_monitoring() {
    local end_time
    end_time=$(get_timestamp_ms)
    local total_wall_time=$((end_time - MONITORING_START_TIME))

    # Save final metrics and summary JSON
    save_metrics_json
    save_summary_json

    # Generate HTML report
    generate_html_report

    echo ""
    echo -e "${MON_MAGENTA}══════════════════════════════════════════════════════════════${MON_NC}"
    echo -e "${MON_MAGENTA}                     MONITORING SUMMARY${MON_NC}"
    echo -e "${MON_MAGENTA}══════════════════════════════════════════════════════════════${MON_NC}"
    echo ""
    echo -e "  ${MON_CYAN}Session ID:${MON_NC}    $MONITORING_SESSION_ID"
    echo -e "  ${MON_CYAN}Iterations:${MON_NC}    $MONITORING_ITERATION_COUNT"
    echo ""
    echo -e "  ${MON_CYAN}Tokens:${MON_NC}"
    echo -e "    Input:       $(format_tokens $MONITORING_TOTAL_TOKENS_IN) tokens"
    echo -e "    Output:      $(format_tokens $MONITORING_TOTAL_TOKENS_OUT) tokens"
    echo ""
    echo -e "  ${MON_CYAN}Cost:${MON_NC}          ${MON_YELLOW}$(format_cost $MONITORING_TOTAL_COST_USD)${MON_NC}"
    echo ""

    # Display model usage statistics
    local model_total=$((MONITORING_MODEL_COUNTS_HAIKU + MONITORING_MODEL_COUNTS_SONNET + MONITORING_MODEL_COUNTS_OPUS))
    if [ "$model_total" -gt 0 ]; then
        echo -e "  ${MON_CYAN}Models:${MON_NC}"
        echo -e "    Haiku:       $MONITORING_MODEL_COUNTS_HAIKU iterations"
        echo -e "    Sonnet:      $MONITORING_MODEL_COUNTS_SONNET iterations"
        echo -e "    Opus:        $MONITORING_MODEL_COUNTS_OPUS iterations"
        echo ""
    fi

    # Display cache statistics if there was any cache activity
    local cache_total=$((MONITORING_CACHE_HITS + MONITORING_CACHE_MISSES))
    if [ "$cache_total" -gt 0 ]; then
        local cache_hit_rate
        cache_hit_rate=$(get_cache_hit_rate)
        echo -e "  ${MON_CYAN}Cache:${MON_NC}"
        echo -e "    Hit rate:    ${cache_hit_rate}% (${MONITORING_CACHE_HITS}/${cache_total})"
        echo -e "    Tokens saved: $(format_tokens $MONITORING_CACHE_SAVED_TOKENS) (estimated)"
        echo ""
    fi

    # Display parallel execution statistics if enabled
    if $MONITORING_PARALLEL_ENABLED && [ "$MONITORING_PARALLEL_BATCHES" -gt 0 ]; then
        local speedup
        speedup=$(get_parallel_speedup)
        local time_saved_ms
        time_saved_ms=$(get_parallel_time_saved_ms)
        echo -e "  ${MON_CYAN}Parallel:${MON_NC}"
        echo -e "    Batches:     $MONITORING_PARALLEL_BATCHES"
        echo -e "    Workers:     $MONITORING_PARALLEL_WORKERS_USED (max $MONITORING_PARALLEL_MAX_CONCURRENT concurrent)"
        echo -e "    Speedup:     ${speedup}x"
        echo -e "    Time saved:  $(format_duration $time_saved_ms)"
        echo ""
    fi

    echo -e "  ${MON_CYAN}Time:${MON_NC}"
    echo -e "    API time:    $(format_duration $MONITORING_TOTAL_DURATION_MS)"
    echo -e "    Wall time:   $(format_duration $total_wall_time)"
    echo ""
    if $MONITORING_JSON_ENABLED && [ -n "$MONITORING_RUN_DIR" ]; then
        echo -e "  ${MON_CYAN}Reports:${MON_NC}"
        echo -e "    Metrics:     $MONITORING_METRICS_FILE"
        echo -e "    Summary:     ${MONITORING_RUN_DIR}/summary.json"
        if [ -n "$MONITORING_REPORT_FILE" ]; then
            echo -e "    HTML:        $MONITORING_REPORT_FILE"
        fi
        echo ""
    fi
    echo -e "${MON_MAGENTA}══════════════════════════════════════════════════════════════${MON_NC}"
    echo ""
}

# Get current metrics as JSON (for external consumption)
get_metrics_json() {
    cat << EOF
{
  "session_id": "$MONITORING_SESSION_ID",
  "iterations": $MONITORING_ITERATION_COUNT,
  "tokens_in": $MONITORING_TOTAL_TOKENS_IN,
  "tokens_out": $MONITORING_TOTAL_TOKENS_OUT,
  "cost_usd": $MONITORING_TOTAL_COST_USD,
  "duration_ms": $MONITORING_TOTAL_DURATION_MS,
  "pricing": {
    "input_per_m": $PRICE_INPUT_PER_M,
    "output_per_m": $PRICE_OUTPUT_PER_M
  }
}
EOF
}

# Get iteration data as JSON (for logging)
get_iteration_json() {
    local story_id="$1"
    local tokens_in="$2"
    local tokens_out="$3"
    local duration_ms="$4"
    local status="$5"
    local agents_used="$6"
    local cost
    cost=$(calculate_cost "$tokens_in" "$tokens_out")

    cat << EOF
{
  "story_id": "$story_id",
  "tokens_in": $tokens_in,
  "tokens_out": $tokens_out,
  "cost_usd": $cost,
  "duration_ms": $duration_ms,
  "status": "$status",
  "agents_used": "$agents_used",
  "timestamp": "$(get_timestamp_iso)"
}
EOF
}

# ============================================================================
# Token Estimation (when actual counts unavailable)
# ============================================================================

# Estimate tokens from text length (rough approximation)
# Average: ~4 characters per token for English text
estimate_tokens_from_text() {
    local text="$1"
    local char_count=${#text}
    echo $((char_count / 4))
}

# Estimate tokens from file size
estimate_tokens_from_file() {
    local file="$1"
    if [ -f "$file" ]; then
        local size
        size=$(wc -c < "$file" | tr -d ' ')
        echo $((size / 4))
    else
        echo 0
    fi
}

# ============================================================================
# Cache Statistics Functions
# ============================================================================

# Update cache statistics from context-cache.py output
# Usage: update_cache_stats [cache_dir]
update_cache_stats() {
    local cache_dir="${1:-.claude-loop/cache}"
    local script_dir
    script_dir="$(dirname "${BASH_SOURCE[0]}")"
    local context_cache="${script_dir}/context-cache.py"

    if [ ! -f "$context_cache" ]; then
        return
    fi

    # Get stats from context-cache.py
    local stats_json
    stats_json=$(python3 "$context_cache" stats --cache-dir "$cache_dir" --json 2>/dev/null)

    if [ -n "$stats_json" ]; then
        MONITORING_CACHE_HITS=$(echo "$stats_json" | jq -r '.cache_hits // 0')
        MONITORING_CACHE_MISSES=$(echo "$stats_json" | jq -r '.cache_misses // 0')
        MONITORING_CACHE_SAVED_TOKENS=$(echo "$stats_json" | jq -r '.saved_tokens_estimate // 0')
    fi
}

# Track cache hit for current iteration
# Usage: track_cache_hit [tokens_saved]
track_cache_hit() {
    local tokens_saved="${1:-0}"
    MONITORING_CACHE_HITS=$((MONITORING_CACHE_HITS + 1))
    MONITORING_CACHE_SAVED_TOKENS=$((MONITORING_CACHE_SAVED_TOKENS + tokens_saved))
}

# Track cache miss for current iteration
track_cache_miss() {
    MONITORING_CACHE_MISSES=$((MONITORING_CACHE_MISSES + 1))
}

# Get cache hit rate as percentage
# Returns: Float percentage (e.g., "75.5")
get_cache_hit_rate() {
    local total=$((MONITORING_CACHE_HITS + MONITORING_CACHE_MISSES))
    if [ "$total" -eq 0 ]; then
        echo "0"
        return
    fi
    echo "scale=1; ($MONITORING_CACHE_HITS / $total) * 100" | bc
}

# Get cache statistics as JSON
get_cache_stats_json() {
    local hit_rate
    hit_rate=$(get_cache_hit_rate)

    cat << EOF
{
  "cache_hits": $MONITORING_CACHE_HITS,
  "cache_misses": $MONITORING_CACHE_MISSES,
  "hit_rate": $hit_rate,
  "saved_tokens_estimate": $MONITORING_CACHE_SAVED_TOKENS
}
EOF
}

# Display cache statistics
display_cache_stats() {
    local hit_rate
    hit_rate=$(get_cache_hit_rate)
    local total=$((MONITORING_CACHE_HITS + MONITORING_CACHE_MISSES))

    if [ "$total" -gt 0 ]; then
        echo -e "${MON_CYAN}[CACHE]${MON_NC} Hit rate: ${hit_rate}% (${MONITORING_CACHE_HITS}/${total}) | Tokens saved: $(format_tokens $MONITORING_CACHE_SAVED_TOKENS)"
    fi
}

# ============================================================================
# Parallel Execution Statistics Functions
# ============================================================================

# Enable parallel execution tracking
# Usage: enable_parallel_tracking
enable_parallel_tracking() {
    MONITORING_PARALLEL_ENABLED=true
}

# Disable parallel execution tracking
disable_parallel_tracking() {
    MONITORING_PARALLEL_ENABLED=false
}

# Track completion of a parallel batch
# Usage: track_parallel_batch $batch_size $batch_duration_ms $max_concurrent
track_parallel_batch() {
    local batch_size="${1:-1}"
    local batch_duration_ms="${2:-0}"
    local max_concurrent="${3:-1}"

    MONITORING_PARALLEL_BATCHES=$((MONITORING_PARALLEL_BATCHES + 1))
    MONITORING_PARALLEL_TIME_MS=$((MONITORING_PARALLEL_TIME_MS + batch_duration_ms))
    MONITORING_PARALLEL_WORKERS_USED=$((MONITORING_PARALLEL_WORKERS_USED + batch_size))

    # Track maximum concurrent workers seen
    if [ "$max_concurrent" -gt "$MONITORING_PARALLEL_MAX_CONCURRENT" ]; then
        MONITORING_PARALLEL_MAX_CONCURRENT="$max_concurrent"
    fi
}

# Track sequential time estimate (sum of all individual story durations)
# Usage: track_sequential_estimate $story_duration_ms
track_sequential_estimate() {
    local duration_ms="${1:-0}"
    MONITORING_SEQUENTIAL_ESTIMATE_MS=$((MONITORING_SEQUENTIAL_ESTIMATE_MS + duration_ms))
}

# Calculate parallel execution speedup factor
# Returns: Speedup factor as decimal (e.g., "2.5" means 2.5x faster)
get_parallel_speedup() {
    if [ "$MONITORING_PARALLEL_TIME_MS" -eq 0 ]; then
        echo "1.0"
        return
    fi
    echo "scale=2; $MONITORING_SEQUENTIAL_ESTIMATE_MS / $MONITORING_PARALLEL_TIME_MS" | bc
}

# Calculate time saved by parallel execution in milliseconds
get_parallel_time_saved_ms() {
    local saved=$((MONITORING_SEQUENTIAL_ESTIMATE_MS - MONITORING_PARALLEL_TIME_MS))
    if [ "$saved" -lt 0 ]; then
        saved=0
    fi
    echo "$saved"
}

# Get parallel execution statistics as JSON
get_parallel_stats_json() {
    local speedup
    speedup=$(get_parallel_speedup)
    local time_saved_ms
    time_saved_ms=$(get_parallel_time_saved_ms)

    cat << EOF
{
  "enabled": $MONITORING_PARALLEL_ENABLED,
  "batches": $MONITORING_PARALLEL_BATCHES,
  "workers_used": $MONITORING_PARALLEL_WORKERS_USED,
  "max_concurrent": $MONITORING_PARALLEL_MAX_CONCURRENT,
  "parallel_time_ms": $MONITORING_PARALLEL_TIME_MS,
  "sequential_estimate_ms": $MONITORING_SEQUENTIAL_ESTIMATE_MS,
  "time_saved_ms": $time_saved_ms,
  "speedup_factor": $speedup
}
EOF
}

# Display parallel execution statistics
display_parallel_stats() {
    if ! $MONITORING_PARALLEL_ENABLED; then
        return
    fi

    local speedup
    speedup=$(get_parallel_speedup)
    local time_saved_ms
    time_saved_ms=$(get_parallel_time_saved_ms)

    echo -e "${MON_CYAN}[PARALLEL]${MON_NC} ${MONITORING_PARALLEL_BATCHES} batches | ${MONITORING_PARALLEL_WORKERS_USED} workers (max ${MONITORING_PARALLEL_MAX_CONCURRENT} concurrent)"
    echo -e "${MON_CYAN}[PARALLEL]${MON_NC} Speedup: ${speedup}x | Time saved: $(format_duration $time_saved_ms)"
}

# ============================================================================
# JSON Metrics Logging Functions
# ============================================================================

# Initialize JSON logging for a run
# Creates .claude-loop/runs/{timestamp}/ directory structure
init_json_logging() {
    if ! $MONITORING_JSON_ENABLED; then
        return
    fi

    local base_dir=".claude-loop/runs"
    MONITORING_RUN_DIR="${base_dir}/${MONITORING_SESSION_ID}"
    MONITORING_METRICS_FILE="${MONITORING_RUN_DIR}/metrics.json"
    MONITORING_ITERATIONS_DATA="[]"

    # Create directory structure
    mkdir -p "$MONITORING_RUN_DIR"

    echo -e "${MON_CYAN}[METRICS]${MON_NC} Run directory: $MONITORING_RUN_DIR"
}

# Log iteration data to JSON
# Usage: log_iteration_json "$story_id" "$tokens_in" "$tokens_out" "$duration_ms" "$status" "$agents_used" "$story_title" "$model"
log_iteration_json() {
    if ! $MONITORING_JSON_ENABLED; then
        return
    fi

    local story_id="$1"
    local tokens_in="${2:-0}"
    local tokens_out="${3:-0}"
    local duration_ms="${4:-0}"
    local status="${5:-unknown}"
    local agents_used="${6:-}"
    local story_title="${7:-$MONITORING_CURRENT_STORY_TITLE}"
    local model="${8:-$MONITORING_CURRENT_MODEL}"

    # Calculate cost for this iteration using actual model pricing
    local iter_cost
    iter_cost=$(calculate_cost_for_model "$tokens_in" "$tokens_out" "$model")

    # Calculate what it would have cost with Opus (for savings tracking)
    local opus_cost
    opus_cost=$(calculate_opus_baseline_cost "$tokens_in" "$tokens_out")

    # Convert agents_used from comma-separated string to JSON array
    local agents_json="[]"
    if [ -n "$agents_used" ]; then
        # Build JSON array from comma-separated agents
        agents_json="["
        local first=true
        for agent in $(echo "$agents_used" | tr ',' ' '); do
            if [ -n "$agent" ]; then
                if [ "$first" = true ]; then
                    first=false
                else
                    agents_json+=", "
                fi
                agents_json+="\"$agent\""
            fi
        done
        agents_json+="]"
    fi

    # Create iteration JSON object with model info
    local iter_json
    iter_json=$(cat << EOF
{
  "iteration": $MONITORING_ITERATION_COUNT,
  "story_id": "$story_id",
  "story_title": "$story_title",
  "tokens_in": $tokens_in,
  "tokens_out": $tokens_out,
  "cost_usd": $iter_cost,
  "opus_baseline_cost_usd": $opus_cost,
  "model": "$model",
  "duration_ms": $duration_ms,
  "status": "$status",
  "agents_used": $agents_json,
  "agents_used_count": $(echo "$agents_used" | tr ',' '\n' | grep -c . || echo 0),
  "timestamp": "$(get_timestamp_iso)"
}
EOF
)

    # Append to iterations array
    if [ "$MONITORING_ITERATIONS_DATA" = "[]" ]; then
        MONITORING_ITERATIONS_DATA="[$iter_json]"
    else
        # Remove trailing ] and append new object
        MONITORING_ITERATIONS_DATA="${MONITORING_ITERATIONS_DATA%]}, $iter_json]"
    fi

    # Write incremental metrics file after each iteration
    save_metrics_json

    # Also log to provider_usage.jsonl for compatibility with multi-provider system
    log_provider_usage_jsonl "$story_id" "$tokens_in" "$tokens_out" "$iter_cost" "$duration_ms" "$status" "$model"
}

# Log provider usage to provider_usage.jsonl
# This is always enabled (not conditional on dashboard/progress flags)
# Usage: log_provider_usage_jsonl "$story_id" "$tokens_in" "$tokens_out" "$cost_usd" "$latency_ms" "$status" "$model"
log_provider_usage_jsonl() {
    local story_id="$1"
    local tokens_in="${2:-0}"
    local tokens_out="${3:-0}"
    local cost_usd="${4:-0.0}"
    local latency_ms="${5:-0}"
    local status="${6:-unknown}"
    local model="${7:-sonnet}"

    # Ensure log directory exists
    local log_dir=".claude-loop/logs"
    mkdir -p "$log_dir"

    local log_file="${log_dir}/provider_usage.jsonl"

    # Determine provider from model name
    local provider="anthropic"
    if [[ "$model" == "gpt-"* ]]; then
        provider="openai"
    elif [[ "$model" == "gemini-"* ]]; then
        provider="google"
    elif [[ "$model" == "deepseek-"* ]]; then
        provider="deepseek"
    fi

    # Determine success status
    local success="true"
    if [[ "$status" == "failed" || "$status" == "error" || "$status" == "blocked" ]]; then
        success="false"
    fi

    # Calculate complexity (use iteration count as proxy)
    local complexity=$MONITORING_ITERATION_COUNT
    if [ $complexity -gt 10 ]; then
        complexity=10
    fi

    # Create log entry in provider_usage.jsonl format
    local log_entry
    log_entry=$(cat << EOF
{"timestamp": "$(get_timestamp_iso)", "story_id": "$story_id", "iteration": $MONITORING_ITERATION_COUNT, "provider": "$provider", "model": "$model", "complexity": $complexity, "input_tokens": $tokens_in, "output_tokens": $tokens_out, "cost_usd": $cost_usd, "latency_ms": $latency_ms, "success": $success, "fallback_used": false}
EOF
)

    # Atomic append to provider_usage.jsonl using temp file + rename
    # This ensures the JSONL file is never corrupted even with concurrent writes
    local temp_file="${log_file}.tmp.$$"
    echo "$log_entry" > "$temp_file"

    # Use file locking for true atomicity across concurrent processes
    # Create lock directory (atomic operation on all Unix systems)
    local lock_dir="${log_file}.lock"
    local lock_acquired=false
    local max_wait=5  # Maximum 5 seconds wait for lock
    local wait_time=0

    while [ $wait_time -lt $max_wait ]; do
        if mkdir "$lock_dir" 2>/dev/null; then
            lock_acquired=true
            break
        fi
        sleep 0.1
        wait_time=$((wait_time + 1))
    done

    if $lock_acquired; then
        # Lock acquired - append and release
        cat "$temp_file" >> "$log_file"
        rm -f "$temp_file"
        rmdir "$lock_dir" 2>/dev/null
    else
        # Couldn't acquire lock - fallback to direct append with warning
        log_warn "Could not acquire lock for $log_file, using non-atomic append"
        cat "$temp_file" >> "$log_file"
        rm -f "$temp_file"
    fi
}

# Save current metrics to metrics.json
save_metrics_json() {
    if ! $MONITORING_JSON_ENABLED || [ -z "$MONITORING_RUN_DIR" ]; then
        return
    fi

    local current_time
    current_time=$(get_timestamp_ms)
    local elapsed_ms=$((current_time - MONITORING_START_TIME))

    cat > "$MONITORING_METRICS_FILE" << EOF
{
  "session_id": "$MONITORING_SESSION_ID",
  "started_at": "$(date -u -r $((MONITORING_START_TIME / 1000)) +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "updated_at": "$(get_timestamp_iso)",
  "pricing": {
    "haiku": {"input_per_m_usd": 0.25, "output_per_m_usd": 1.25},
    "sonnet": {"input_per_m_usd": 3.00, "output_per_m_usd": 15.00},
    "opus": {"input_per_m_usd": 15.00, "output_per_m_usd": 75.00}
  },
  "model_usage": {
    "haiku": $MONITORING_MODEL_COUNTS_HAIKU,
    "sonnet": $MONITORING_MODEL_COUNTS_SONNET,
    "opus": $MONITORING_MODEL_COUNTS_OPUS
  },
  "cache": {
    "hits": $MONITORING_CACHE_HITS,
    "misses": $MONITORING_CACHE_MISSES,
    "hit_rate": $(get_cache_hit_rate),
    "saved_tokens_estimate": $MONITORING_CACHE_SAVED_TOKENS
  },
  "parallel": {
    "enabled": $MONITORING_PARALLEL_ENABLED,
    "batches": $MONITORING_PARALLEL_BATCHES,
    "workers_used": $MONITORING_PARALLEL_WORKERS_USED,
    "max_concurrent": $MONITORING_PARALLEL_MAX_CONCURRENT,
    "parallel_time_ms": $MONITORING_PARALLEL_TIME_MS,
    "sequential_estimate_ms": $MONITORING_SEQUENTIAL_ESTIMATE_MS,
    "time_saved_ms": $(get_parallel_time_saved_ms),
    "speedup_factor": $(get_parallel_speedup)
  },
  "totals": {
    "iterations": $MONITORING_ITERATION_COUNT,
    "tokens_in": $MONITORING_TOTAL_TOKENS_IN,
    "tokens_out": $MONITORING_TOTAL_TOKENS_OUT,
    "cost_usd": $MONITORING_TOTAL_COST_USD,
    "api_duration_ms": $MONITORING_TOTAL_DURATION_MS,
    "wall_duration_ms": $elapsed_ms
  },
  "iterations": $MONITORING_ITERATIONS_DATA
}
EOF
}

# Save final run summary to summary.json
save_summary_json() {
    if ! $MONITORING_JSON_ENABLED || [ -z "$MONITORING_RUN_DIR" ]; then
        return
    fi

    local summary_file="${MONITORING_RUN_DIR}/summary.json"
    local end_time
    end_time=$(get_timestamp_ms)
    local total_wall_time=$((end_time - MONITORING_START_TIME))

    # Count completed stories by parsing iterations data
    local completed_count=0
    local failed_count=0

    # Use jq if available for accurate counting
    if command -v jq &> /dev/null; then
        completed_count=$(echo "$MONITORING_ITERATIONS_DATA" | jq '[.[] | select(.status == "complete" or .status == "completed")] | length')
        failed_count=$(echo "$MONITORING_ITERATIONS_DATA" | jq '[.[] | select(.status == "failed" or .status == "error" or .status == "blocked")] | length')
    else
        # Simple grep-based counting as fallback
        completed_count=$(echo "$MONITORING_ITERATIONS_DATA" | grep -c '"status": "complete"' || echo 0)
        failed_count=$(echo "$MONITORING_ITERATIONS_DATA" | grep -c '"status": "failed"\|"status": "error"\|"status": "blocked"' || echo 0)
    fi

    # Calculate opus baseline cost for savings comparison
    local opus_baseline_cost
    opus_baseline_cost=$(calculate_opus_baseline_cost "$MONITORING_TOTAL_TOKENS_IN" "$MONITORING_TOTAL_TOKENS_OUT")
    local savings
    savings=$(echo "scale=6; $opus_baseline_cost - $MONITORING_TOTAL_COST_USD" | bc)
    local savings_pct
    if [ "$(echo "$opus_baseline_cost > 0" | bc)" -eq 1 ]; then
        savings_pct=$(echo "scale=1; ($savings / $opus_baseline_cost) * 100" | bc)
    else
        savings_pct="0"
    fi

    cat > "$summary_file" << EOF
{
  "session_id": "$MONITORING_SESSION_ID",
  "started_at": "$(date -u -r $((MONITORING_START_TIME / 1000)) +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "completed_at": "$(get_timestamp_iso)",
  "status": "completed",
  "stories": {
    "total": $MONITORING_ITERATION_COUNT,
    "completed": $completed_count,
    "failed": $failed_count
  },
  "model_usage": {
    "haiku": $MONITORING_MODEL_COUNTS_HAIKU,
    "sonnet": $MONITORING_MODEL_COUNTS_SONNET,
    "opus": $MONITORING_MODEL_COUNTS_OPUS
  },
  "cache": {
    "hits": $MONITORING_CACHE_HITS,
    "misses": $MONITORING_CACHE_MISSES,
    "hit_rate": $(get_cache_hit_rate),
    "saved_tokens_estimate": $MONITORING_CACHE_SAVED_TOKENS
  },
  "parallel": {
    "enabled": $MONITORING_PARALLEL_ENABLED,
    "batches": $MONITORING_PARALLEL_BATCHES,
    "workers_used": $MONITORING_PARALLEL_WORKERS_USED,
    "max_concurrent": $MONITORING_PARALLEL_MAX_CONCURRENT,
    "parallel_time_ms": $MONITORING_PARALLEL_TIME_MS,
    "sequential_estimate_ms": $MONITORING_SEQUENTIAL_ESTIMATE_MS,
    "time_saved_ms": $(get_parallel_time_saved_ms),
    "speedup_factor": $(get_parallel_speedup),
    "parallel_formatted": "$(format_duration $MONITORING_PARALLEL_TIME_MS)",
    "sequential_formatted": "$(format_duration $MONITORING_SEQUENTIAL_ESTIMATE_MS)",
    "time_saved_formatted": "$(format_duration $(get_parallel_time_saved_ms))"
  },
  "tokens": {
    "input": $MONITORING_TOTAL_TOKENS_IN,
    "output": $MONITORING_TOTAL_TOKENS_OUT,
    "total": $((MONITORING_TOTAL_TOKENS_IN + MONITORING_TOTAL_TOKENS_OUT))
  },
  "cost": {
    "total_usd": $MONITORING_TOTAL_COST_USD,
    "opus_baseline_usd": $opus_baseline_cost,
    "savings_usd": $savings,
    "savings_percent": $savings_pct,
    "output_usd": $(echo "scale=6; ($MONITORING_TOTAL_TOKENS_OUT / 1000000) * $PRICE_OUTPUT_PER_M" | bc)
  },
  "duration": {
    "api_ms": $MONITORING_TOTAL_DURATION_MS,
    "wall_ms": $total_wall_time,
    "api_formatted": "$(format_duration $MONITORING_TOTAL_DURATION_MS)",
    "wall_formatted": "$(format_duration $total_wall_time)"
  },
  "metrics_file": "$MONITORING_METRICS_FILE",
  "run_directory": "$MONITORING_RUN_DIR"
}
EOF

    echo -e "${MON_CYAN}[METRICS]${MON_NC} Summary saved: $summary_file"
}

# Enable JSON logging (default: enabled)
enable_json_logging() {
    MONITORING_JSON_ENABLED=true
}

# Disable JSON logging
disable_json_logging() {
    MONITORING_JSON_ENABLED=false
}

# Get the current run directory path
get_run_directory() {
    echo "$MONITORING_RUN_DIR"
}

# Get the metrics file path
get_metrics_file() {
    echo "$MONITORING_METRICS_FILE"
}

# ============================================================================
# HTML Report Generation Functions
# ============================================================================

# Generate HTML report using Python report generator
generate_html_report() {
    if ! $MONITORING_HTML_ENABLED || [ -z "$MONITORING_RUN_DIR" ]; then
        return
    fi

    local script_dir
    script_dir="$(dirname "${BASH_SOURCE[0]}")"
    local report_generator="${script_dir}/report-generator.py"

    if [ ! -f "$report_generator" ]; then
        echo -e "${MON_YELLOW}[REPORT]${MON_NC} Report generator not found: $report_generator"
        return
    fi

    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${MON_YELLOW}[REPORT]${MON_NC} Python 3 not found, skipping HTML report"
        return
    fi

    echo -e "${MON_CYAN}[REPORT]${MON_NC} Generating HTML report..."

    # Run the report generator (which now includes agent improvement analysis)
    local output
    if output=$(python3 "$report_generator" "$MONITORING_RUN_DIR" 2>&1); then
        MONITORING_REPORT_FILE="${MONITORING_RUN_DIR}/report.html"
        echo -e "${MON_GREEN}[REPORT]${MON_NC} Report generated: $MONITORING_REPORT_FILE"
    else
        echo -e "${MON_YELLOW}[REPORT]${MON_NC} Failed to generate report: $output"
    fi
}

# Run agent improver analysis (standalone, without HTML report)
run_agent_improver() {
    if [ -z "$MONITORING_RUN_DIR" ]; then
        echo -e "${MON_YELLOW}[IMPROVER]${MON_NC} No run directory available"
        return 1
    fi

    local script_dir
    script_dir="$(dirname "${BASH_SOURCE[0]}")"
    local agent_improver="${script_dir}/agent-improver.py"

    if [ ! -f "$agent_improver" ]; then
        echo -e "${MON_YELLOW}[IMPROVER]${MON_NC} Agent improver not found: $agent_improver"
        return 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "${MON_YELLOW}[IMPROVER]${MON_NC} Python 3 not found"
        return 1
    fi

    echo -e "${MON_CYAN}[IMPROVER]${MON_NC} Analyzing run for improvement suggestions..."

    local output
    if output=$(python3 "$agent_improver" "$MONITORING_RUN_DIR" 2>&1); then
        echo -e "${MON_GREEN}[IMPROVER]${MON_NC} Improvements saved: ${MONITORING_RUN_DIR}/improvements.json"
        return 0
    else
        echo -e "${MON_YELLOW}[IMPROVER]${MON_NC} Failed to run agent improver: $output"
        return 1
    fi
}

# Get the improvements file path
get_improvements_file() {
    echo "${MONITORING_RUN_DIR}/improvements.json"
}

# Enable HTML report generation (default: enabled)
enable_html_report() {
    MONITORING_HTML_ENABLED=true
}

# Disable HTML report generation
disable_html_report() {
    MONITORING_HTML_ENABLED=false
}

# Get the report file path
get_report_file() {
    echo "$MONITORING_REPORT_FILE"
}

# ============================================================================
# Export Functions for Sourcing
# ============================================================================

export -f get_timestamp_ms
export -f get_timestamp_iso
export -f calculate_cost
export -f calculate_cost_for_model
export -f calculate_opus_baseline_cost
export -f format_cost
export -f format_duration
export -f format_tokens
export -f start_monitoring
export -f start_iteration
export -f set_current_agent_info
export -f display_agent_reasoning
export -f get_current_agent_display
export -f track_iteration
export -f display_iteration_cost
export -f display_running_total
export -f end_monitoring
export -f get_metrics_json
export -f get_iteration_json
export -f estimate_tokens_from_text
export -f estimate_tokens_from_file
export -f update_cache_stats
export -f track_cache_hit
export -f track_cache_miss
export -f get_cache_hit_rate
export -f get_cache_stats_json
export -f display_cache_stats
export -f enable_parallel_tracking
export -f disable_parallel_tracking
export -f track_parallel_batch
export -f track_sequential_estimate
export -f get_parallel_speedup
export -f get_parallel_time_saved_ms
export -f get_parallel_stats_json
export -f display_parallel_stats
export -f init_json_logging
export -f log_iteration_json
export -f log_provider_usage_jsonl
export -f save_metrics_json
export -f save_summary_json
export -f enable_json_logging
export -f disable_json_logging
export -f get_run_directory
export -f get_metrics_file
export -f generate_html_report
export -f enable_html_report
export -f disable_html_report
export -f get_report_file
export -f run_agent_improver
export -f get_improvements_file
