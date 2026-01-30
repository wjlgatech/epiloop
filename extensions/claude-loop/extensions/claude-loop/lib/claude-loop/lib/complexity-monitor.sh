#!/bin/bash
#
# complexity-monitor.sh - Runtime complexity detection for adaptive story splitting
#
# Monitors story execution for complexity signals:
#   - Acceptance criteria taking >2x estimated time
#   - File scope expansion (files modified beyond initial fileScope)
#   - High error count (>3 errors in single story)
#   - Agent clarification requests (uncertainty signals in output)
#
# Usage:
#   source lib/complexity-monitor.sh
#   init_complexity_monitor "$story_id" "$estimated_duration_ms" "$file_scope_array"
#   track_acceptance_criterion "$criterion_id" "$start_time" "$end_time"
#   track_file_modification "$file_path"
#   track_error "$error_message"
#   track_agent_output "$output_text"
#   complexity_score=$(get_complexity_score)
#   should_split=$(should_trigger_split "$threshold")

# ============================================================================
# Configuration
# ============================================================================

# Default complexity threshold (0-10 scale, trigger split if exceeded)
COMPLEXITY_DEFAULT_THRESHOLD=7

# Signal weights for complexity score calculation (must sum to 1.0)
WEIGHT_TIME_OVERRUN=0.35      # 35% - Acceptance criteria time overrun
WEIGHT_FILE_EXPANSION=0.25    # 25% - File scope expansion
WEIGHT_ERROR_COUNT=0.25       # 25% - Error count
WEIGHT_CLARIFICATIONS=0.15    # 15% - Agent clarification requests

# Complexity scoring thresholds
TIME_OVERRUN_THRESHOLD=2.0    # 2x estimated time
ERROR_COUNT_THRESHOLD=3       # >3 errors triggers high score
FILE_EXPANSION_THRESHOLD=0.3  # 30% expansion beyond initial scope

# Clarification detection patterns (regex)
CLARIFICATION_PATTERNS=(
    "I'm not sure"
    "unclear"
    "ambiguous"
    "need clarification"
    "could you clarify"
    "what do you mean"
    "I don't understand"
    "can you explain"
    "uncertain"
    "confusing"
)

# ============================================================================
# State Variables
# ============================================================================

# Story metadata
COMPLEXITY_STORY_ID=""
COMPLEXITY_ESTIMATED_DURATION_MS=0
COMPLEXITY_INITIAL_FILE_SCOPE=""  # Comma-separated file paths
COMPLEXITY_START_TIME=""

# Acceptance criteria tracking
COMPLEXITY_AC_COUNT=0
COMPLEXITY_AC_COMPLETED=0
COMPLEXITY_AC_TOTAL_TIME_MS=0
COMPLEXITY_AC_ESTIMATED_TIME_PER_AC=0

# File scope tracking
COMPLEXITY_FILES_MODIFIED=()
COMPLEXITY_FILES_OUTSIDE_SCOPE=0

# Error tracking
COMPLEXITY_ERROR_COUNT=0
COMPLEXITY_ERRORS=()

# Clarification tracking
COMPLEXITY_CLARIFICATION_COUNT=0
COMPLEXITY_CLARIFICATIONS=()

# Scoring
COMPLEXITY_SCORE=0
COMPLEXITY_SIGNALS_LOG=""  # Path to complexity-signals.jsonl

# ============================================================================
# Initialization
# ============================================================================

# Initialize complexity monitor for a story
# Args: story_id, estimated_duration_ms, file_scope (comma-separated)
init_complexity_monitor() {
    local story_id="$1"
    local estimated_duration_ms="$2"
    local file_scope="$3"
    local ac_count="${4:-5}"  # Default 5 acceptance criteria

    COMPLEXITY_STORY_ID="$story_id"
    COMPLEXITY_ESTIMATED_DURATION_MS="$estimated_duration_ms"
    COMPLEXITY_INITIAL_FILE_SCOPE="$file_scope"
    COMPLEXITY_AC_COUNT="$ac_count"
    COMPLEXITY_START_TIME=$(get_timestamp_ms)

    # Calculate estimated time per acceptance criterion
    if [ "$ac_count" -gt 0 ]; then
        COMPLEXITY_AC_ESTIMATED_TIME_PER_AC=$((estimated_duration_ms / ac_count))
    else
        COMPLEXITY_AC_ESTIMATED_TIME_PER_AC="$estimated_duration_ms"
    fi

    # Reset state
    COMPLEXITY_AC_COMPLETED=0
    COMPLEXITY_AC_TOTAL_TIME_MS=0
    COMPLEXITY_FILES_MODIFIED=()
    COMPLEXITY_FILES_OUTSIDE_SCOPE=0
    COMPLEXITY_ERROR_COUNT=0
    COMPLEXITY_ERRORS=()
    COMPLEXITY_CLARIFICATION_COUNT=0
    COMPLEXITY_CLARIFICATIONS=()
    COMPLEXITY_SCORE=0

    # Set up complexity signals log
    local loop_dir="${CLAUDE_LOOP_DIR:-.claude-loop}"
    COMPLEXITY_SIGNALS_LOG="$loop_dir/complexity-signals.jsonl"
    mkdir -p "$loop_dir"
    touch "$COMPLEXITY_SIGNALS_LOG"

    log_complexity_signal "monitor_init" "Initialized complexity monitor for $story_id" ""
}

# Get current timestamp in milliseconds (same as monitoring.sh)
get_timestamp_ms() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000'
    else
        echo $(($(date +%s%N) / 1000000))
    fi
}

# Get ISO 8601 timestamp
get_timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# ============================================================================
# Signal Tracking Functions
# ============================================================================

# Track completion of an acceptance criterion
# Args: criterion_id, start_time_ms, end_time_ms
track_acceptance_criterion() {
    local criterion_id="$1"
    local start_time="$2"
    local end_time="$3"

    local duration=$((end_time - start_time))
    COMPLEXITY_AC_COMPLETED=$((COMPLEXITY_AC_COMPLETED + 1))
    COMPLEXITY_AC_TOTAL_TIME_MS=$((COMPLEXITY_AC_TOTAL_TIME_MS + duration))

    # Check if this AC took >2x estimated time
    local time_ratio=$(echo "scale=2; $duration / $COMPLEXITY_AC_ESTIMATED_TIME_PER_AC" | bc)
    local overrun=$(echo "$time_ratio > $TIME_OVERRUN_THRESHOLD" | bc)

    if [ "$overrun" -eq 1 ]; then
        local message="AC $criterion_id took ${time_ratio}x estimated time (${duration}ms vs ${COMPLEXITY_AC_ESTIMATED_TIME_PER_AC}ms)"
        log_complexity_signal "time_overrun" "$message" "{\"criterion_id\": \"$criterion_id\", \"duration_ms\": $duration, \"estimated_ms\": $COMPLEXITY_AC_ESTIMATED_TIME_PER_AC, \"ratio\": $time_ratio}"
    fi
}

# Track file modification
# Args: file_path
track_file_modification() {
    local file_path="$1"

    # Add to modified files list
    COMPLEXITY_FILES_MODIFIED+=("$file_path")

    # Check if file is outside initial scope
    local in_scope=false
    IFS=',' read -ra scope_array <<< "$COMPLEXITY_INITIAL_FILE_SCOPE"
    for scope_pattern in "${scope_array[@]}"; do
        # Support glob patterns in fileScope
        if [[ "$file_path" == $scope_pattern* ]] || [[ "$file_path" == *"$scope_pattern"* ]]; then
            in_scope=true
            break
        fi
    done

    if [ "$in_scope" = false ]; then
        COMPLEXITY_FILES_OUTSIDE_SCOPE=$((COMPLEXITY_FILES_OUTSIDE_SCOPE + 1))
        log_complexity_signal "file_expansion" "File modified outside initial scope: $file_path" "{\"file_path\": \"$file_path\", \"initial_scope\": \"$COMPLEXITY_INITIAL_FILE_SCOPE\"}"
    fi
}

# Track error occurrence
# Args: error_message
track_error() {
    local error_message="$1"

    COMPLEXITY_ERROR_COUNT=$((COMPLEXITY_ERROR_COUNT + 1))
    COMPLEXITY_ERRORS+=("$error_message")

    # Log high error count signal
    if [ "$COMPLEXITY_ERROR_COUNT" -gt "$ERROR_COUNT_THRESHOLD" ]; then
        log_complexity_signal "high_error_count" "Error count exceeded threshold: $COMPLEXITY_ERROR_COUNT errors" "{\"error_count\": $COMPLEXITY_ERROR_COUNT, \"threshold\": $ERROR_COUNT_THRESHOLD, \"latest_error\": \"$(echo "$error_message" | sed 's/"/\\"/g')\"}"
    fi
}

# Track agent output for clarification requests
# Args: output_text
track_agent_output() {
    local output_text="$1"

    # Check for clarification patterns in output
    for pattern in "${CLARIFICATION_PATTERNS[@]}"; do
        if echo "$output_text" | grep -iq "$pattern"; then
            COMPLEXITY_CLARIFICATION_COUNT=$((COMPLEXITY_CLARIFICATION_COUNT + 1))
            COMPLEXITY_CLARIFICATIONS+=("$pattern")
            log_complexity_signal "clarification_request" "Agent expressed uncertainty: '$pattern'" "{\"pattern\": \"$pattern\", \"count\": $COMPLEXITY_CLARIFICATION_COUNT}"
            break  # Only count once per output
        fi
    done
}

# ============================================================================
# Complexity Scoring
# ============================================================================

# Calculate overall complexity score (0-10 scale)
# Returns: complexity score as float
get_complexity_score() {
    local time_score=0
    local file_score=0
    local error_score=0
    local clarification_score=0

    # Time overrun score (0-10)
    if [ "$COMPLEXITY_AC_COMPLETED" -gt 0 ] && [ "$COMPLEXITY_AC_ESTIMATED_TIME_PER_AC" -gt 0 ]; then
        local avg_time_per_ac=$((COMPLEXITY_AC_TOTAL_TIME_MS / COMPLEXITY_AC_COMPLETED))
        local time_ratio=$(echo "scale=2; $avg_time_per_ac / $COMPLEXITY_AC_ESTIMATED_TIME_PER_AC" | bc)

        # Score scales from 0 (on time) to 10 (5x over)
        time_score=$(echo "scale=2; if ($time_ratio > 5) 10 else ($time_ratio - 1) * 2.5" | bc)
        if (( $(echo "$time_score < 0" | bc -l) )); then
            time_score=0
        fi
    fi

    # File expansion score (0-10)
    local initial_scope_count=$(echo "$COMPLEXITY_INITIAL_FILE_SCOPE" | tr ',' '\n' | wc -l | tr -d ' ')
    if [ "$initial_scope_count" -gt 0 ]; then
        local expansion_ratio=$(echo "scale=2; $COMPLEXITY_FILES_OUTSIDE_SCOPE / $initial_scope_count" | bc)

        # Score scales from 0 (no expansion) to 10 (2x expansion)
        file_score=$(echo "scale=2; if ($expansion_ratio > 2) 10 else $expansion_ratio * 5" | bc)
    fi

    # Error count score (0-10)
    if [ "$COMPLEXITY_ERROR_COUNT" -gt "$ERROR_COUNT_THRESHOLD" ]; then
        # Score scales from 0 (at threshold) to 10 (threshold + 10 errors)
        local excess_errors=$((COMPLEXITY_ERROR_COUNT - ERROR_COUNT_THRESHOLD))
        error_score=$(echo "scale=2; if ($excess_errors > 10) 10 else $excess_errors" | bc)
    fi

    # Clarification score (0-10)
    if [ "$COMPLEXITY_CLARIFICATION_COUNT" -gt 0 ]; then
        # Score scales from 0 to 10 (5+ clarifications = 10)
        clarification_score=$(echo "scale=2; if ($COMPLEXITY_CLARIFICATION_COUNT > 5) 10 else $COMPLEXITY_CLARIFICATION_COUNT * 2" | bc)
    fi

    # Weighted combination
    local weighted_score=$(echo "scale=2; ($time_score * $WEIGHT_TIME_OVERRUN) + ($file_score * $WEIGHT_FILE_EXPANSION) + ($error_score * $WEIGHT_ERROR_COUNT) + ($clarification_score * $WEIGHT_CLARIFICATIONS)" | bc)

    COMPLEXITY_SCORE="$weighted_score"
    echo "$weighted_score"
}

# Check if split should be triggered
# Args: threshold (default: COMPLEXITY_DEFAULT_THRESHOLD)
# Returns: 0 (true) if split should trigger, 1 (false) otherwise
should_trigger_split() {
    local threshold="${1:-$COMPLEXITY_DEFAULT_THRESHOLD}"

    local current_score=$(get_complexity_score)
    local should_split=$(echo "$current_score > $threshold" | bc)

    if [ "$should_split" -eq 1 ]; then
        log_complexity_signal "split_triggered" "Complexity score ($current_score) exceeded threshold ($threshold)" "{\"score\": $current_score, \"threshold\": $threshold}"
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Logging
# ============================================================================

# Log complexity signal to JSONL file
# Args: signal_type, message, extra_data (JSON string)
log_complexity_signal() {
    local signal_type="$1"
    local message="$2"
    local extra_data="${3:-{}}"

    local timestamp=$(get_timestamp_iso)
    local log_entry=$(cat <<EOF
{"timestamp": "$timestamp", "story_id": "$COMPLEXITY_STORY_ID", "signal_type": "$signal_type", "message": "$message", "data": $extra_data}
EOF
)

    echo "$log_entry" >> "$COMPLEXITY_SIGNALS_LOG"
}

# Get complexity report as JSON
get_complexity_report_json() {
    local score=$(get_complexity_score)
    local timestamp=$(get_timestamp_iso)

    cat <<EOF
{
  "story_id": "$COMPLEXITY_STORY_ID",
  "timestamp": "$timestamp",
  "complexity_score": $score,
  "signals": {
    "acceptance_criteria": {
      "completed": $COMPLEXITY_AC_COMPLETED,
      "total": $COMPLEXITY_AC_COUNT,
      "total_time_ms": $COMPLEXITY_AC_TOTAL_TIME_MS,
      "estimated_time_per_ac": $COMPLEXITY_AC_ESTIMATED_TIME_PER_AC
    },
    "file_scope": {
      "initial_scope": "$COMPLEXITY_INITIAL_FILE_SCOPE",
      "files_modified": ${#COMPLEXITY_FILES_MODIFIED[@]},
      "files_outside_scope": $COMPLEXITY_FILES_OUTSIDE_SCOPE
    },
    "errors": {
      "count": $COMPLEXITY_ERROR_COUNT,
      "threshold": $ERROR_COUNT_THRESHOLD
    },
    "clarifications": {
      "count": $COMPLEXITY_CLARIFICATION_COUNT
    }
  },
  "threshold": $COMPLEXITY_DEFAULT_THRESHOLD,
  "should_split": $(should_trigger_split && echo "true" || echo "false")
}
EOF
}

# Display complexity report to terminal
display_complexity_report() {
    local score=$(get_complexity_score)

    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              Complexity Detection Report                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Story ID: $COMPLEXITY_STORY_ID"
    echo "Complexity Score: $(printf "%.2f" "$score")/10"
    echo ""
    echo "Signals:"
    echo "  ├─ Time Overrun:      AC completed: $COMPLEXITY_AC_COMPLETED/$COMPLEXITY_AC_COUNT"
    echo "  │                     Total time: ${COMPLEXITY_AC_TOTAL_TIME_MS}ms"
    echo "  ├─ File Expansion:    Files outside scope: $COMPLEXITY_FILES_OUTSIDE_SCOPE"
    echo "  ├─ Error Count:       Total errors: $COMPLEXITY_ERROR_COUNT (threshold: $ERROR_COUNT_THRESHOLD)"
    echo "  └─ Clarifications:    Count: $COMPLEXITY_CLARIFICATION_COUNT"
    echo ""

    if should_trigger_split "$COMPLEXITY_DEFAULT_THRESHOLD"; then
        echo "⚠️  Split Recommended: Score exceeds threshold ($COMPLEXITY_DEFAULT_THRESHOLD)"
    else
        echo "✓  No split needed: Score below threshold ($COMPLEXITY_DEFAULT_THRESHOLD)"
    fi
    echo ""
}

# ============================================================================
# CLI Commands (for standalone usage)
# ============================================================================

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    # Script is being executed directly, not sourced

    case "${1:-}" in
        report)
            # Display complexity report for current story
            display_complexity_report
            ;;

        json)
            # Output complexity report as JSON
            get_complexity_report_json
            ;;

        score)
            # Output complexity score only
            get_complexity_score
            ;;

        should-split)
            # Check if split should trigger (exit code 0 = yes, 1 = no)
            threshold="${2:-$COMPLEXITY_DEFAULT_THRESHOLD}"
            if should_trigger_split "$threshold"; then
                echo "true"
                exit 0
            else
                echo "false"
                exit 1
            fi
            ;;

        signals)
            # Show recent complexity signals from log
            count="${2:-10}"
            if [ -f "$COMPLEXITY_SIGNALS_LOG" ]; then
                tail -n "$count" "$COMPLEXITY_SIGNALS_LOG" | jq -r '.timestamp + " [" + .signal_type + "] " + .message'
            else
                echo "No signals log found at $COMPLEXITY_SIGNALS_LOG"
            fi
            ;;

        *)
            echo "Usage: $0 {report|json|score|should-split [threshold]|signals [count]}"
            echo ""
            echo "Commands:"
            echo "  report          Display complexity report in terminal"
            echo "  json            Output complexity report as JSON"
            echo "  score           Output complexity score only"
            echo "  should-split    Check if split should trigger (exit 0 = yes, 1 = no)"
            echo "  signals [N]     Show recent N complexity signals from log (default: 10)"
            exit 1
            ;;
    esac
fi
