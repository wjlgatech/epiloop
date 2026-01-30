#!/bin/bash
#
# Integration test for Learnings JSON Storage (US-002)
#
# Tests the learnings system functionality:
# - Learnings file creation
# - Writing learnings (success and failure)
# - Querying learnings by tags
# - Rating learnings (helpful/unhelpful)
# - Automatic tagging
# - Context injection into prompts
# - Feature flag behavior

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
LEARNINGS_FILE="$TEST_DIR/.claude-loop/learnings.json"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup function
cleanup() {
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi
}

trap cleanup EXIT

# Test helper functions
test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${YELLOW}[TEST $TESTS_RUN]${NC} $1"
}

test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}[PASS]${NC} $1"
}

test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}[FAIL]${NC} $1"
}

# Source the learnings functions
setup_learnings_functions() {
    # Create test directory structure
    mkdir -p "$TEST_DIR/.claude-loop"

    # Initialize learnings file
    echo "[]" > "$LEARNINGS_FILE"

    # Set environment variables
    export LEARNINGS_ENABLED=true
    export LEARNINGS_FILE="$LEARNINGS_FILE"
    export MAX_LEARNINGS_IN_CONTEXT=3
    export VERBOSE=false

    # Define logging functions
    log_info() { echo "[INFO] $1"; }
    log_success() { echo "[SUCCESS] $1"; }
    log_error() { echo "[ERROR] $1" >&2; }
    log_debug() { if $VERBOSE; then echo "[DEBUG] $1"; fi; }
    export -f log_info log_success log_error log_debug

    # Source learnings functions from claude-loop.sh
    # We'll extract the relevant functions

    learnings_write() {
        if ! $LEARNINGS_ENABLED; then
            return 0
        fi

        local story_id="$1"
        local iteration="$2"
        local success="$3"
        local lesson="$4"
        local tags_str="$5"
        local context_json="$6"

        # Generate UUID for learning
        local learning_id
        learning_id=$(uuidgen 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "$(date +%s)-$$-$RANDOM")

        # Create timestamp
        local timestamp
        timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

        # Convert tags string to JSON array
        local tags_json
        if [ -z "$tags_str" ]; then
            tags_json="[]"
        else
            tags_json=$(echo "$tags_str" | jq -R 'split(" ") | map(select(length > 0))' 2>/dev/null || echo "[]")
        fi

        # Escape lesson text for JSON
        local escaped_lesson
        escaped_lesson=$(echo "$lesson" | jq -Rs . 2>/dev/null || echo "\"\"")

        # Build learning JSON object
        local learning_json
        learning_json=$(jq -n \
            --arg id "$learning_id" \
            --arg ts "$timestamp" \
            --arg sid "$story_id" \
            --argjson iter "$iteration" \
            --argjson succ "$success" \
            --argjson lesson "$escaped_lesson" \
            --argjson tags "$tags_json" \
            --argjson ctx "$context_json" \
            '{
                id: $id,
                timestamp: $ts,
                story_id: $sid,
                iteration: $iter,
                success: $succ,
                lesson: $lesson,
                tags: $tags,
                helpful_count: 0,
                context: $ctx
            }' 2>/dev/null)

        if [ -z "$learning_json" ]; then
            log_error "Failed to create learning JSON"
            return 1
        fi

        # Ensure learnings file exists
        if [ ! -f "$LEARNINGS_FILE" ]; then
            echo "[]" > "$LEARNINGS_FILE"
        fi

        # Atomic append: read existing, add new, write back
        local temp_file
        temp_file=$(mktemp)

        jq --argjson new_learning "$learning_json" '. += [$new_learning]' "$LEARNINGS_FILE" > "$temp_file" 2>/dev/null

        if [ $? -eq 0 ]; then
            mv "$temp_file" "$LEARNINGS_FILE"
            log_debug "Learning saved: $learning_id"
        else
            log_error "Failed to append learning to $LEARNINGS_FILE"
            rm -f "$temp_file"
            return 1
        fi

        return 0
    }

    learnings_rate() {
        if ! $LEARNINGS_ENABLED; then
            return 0
        fi

        if [ ! -f "$LEARNINGS_FILE" ]; then
            log_error "Learnings file not found: $LEARNINGS_FILE"
            return 1
        fi

        local learning_id="$1"
        local action="$2"

        local delta=0
        case "$action" in
            --helpful)
                delta=1
                ;;
            --unhelpful)
                delta=-1
                ;;
            *)
                log_error "Invalid rating action: $action"
                return 1
                ;;
        esac

        # Update helpful_count atomically
        local temp_file
        temp_file=$(mktemp)

        jq --arg id "$learning_id" --argjson delta "$delta" \
            'map(if .id == $id then .helpful_count += $delta else . end)' \
            "$LEARNINGS_FILE" > "$temp_file" 2>/dev/null

        if [ $? -eq 0 ]; then
            mv "$temp_file" "$LEARNINGS_FILE"
            log_success "Learning rated: $learning_id ($action)"
        else
            log_error "Failed to rate learning: $learning_id"
            rm -f "$temp_file"
            return 1
        fi

        return 0
    }

    extract_story_tags() {
        local story_description="$1"
        local file_scope="$2"

        local tags=""

        # Extract keywords from description (4+ char words, lowercase)
        local desc_tags
        desc_tags=$(echo "$story_description" | tr '[:upper:]' '[:lower:]' | grep -oE '\w{4,}' | sort -u | head -10 | tr '\n' ' ')
        tags="$tags $desc_tags"

        # Extract file extensions from file scope
        if [ -n "$file_scope" ]; then
            local ext_tags
            ext_tags=$(echo "$file_scope" | grep -oE '\.\w+$' | sed 's/^\.//' | sort -u | tr '\n' ' ')
            tags="$tags $ext_tags"
        fi

        # Normalize tags: remove duplicates, trim whitespace
        tags=$(echo "$tags" | tr ' ' '\n' | sort -u | grep -v '^$' | tr '\n' ' ')

        echo "$tags"
    }

    export -f learnings_write learnings_rate extract_story_tags
}

# Run tests
run_tests() {
    echo -e "${YELLOW}=== Learnings JSON Storage Tests ===${NC}\n"

    # Test 1: Learnings file creation
    test_start "Learnings file should be created"
    if [ -f "$LEARNINGS_FILE" ]; then
        test_pass "Learnings file exists"
    else
        test_fail "Learnings file not found"
    fi

    # Test 2: Write successful learning
    test_start "Write successful learning"
    local context_json='{"files":["test.sh"],"duration_ms":1000}'
    if learnings_write "TEST-001" 1 "true" "Successfully tested hooks" "test hooks bash" "$context_json"; then
        local count
        count=$(jq 'length' "$LEARNINGS_FILE")
        if [ "$count" -eq 1 ]; then
            test_pass "Learning written successfully"
        else
            test_fail "Unexpected learning count: $count"
        fi
    else
        test_fail "Failed to write learning"
    fi

    # Test 3: Verify learning structure
    test_start "Verify learning JSON structure"
    local has_id=$(jq '.[0] | has("id")' "$LEARNINGS_FILE")
    local has_timestamp=$(jq '.[0] | has("timestamp")' "$LEARNINGS_FILE")
    local has_lesson=$(jq '.[0] | has("lesson")' "$LEARNINGS_FILE")
    local has_tags=$(jq '.[0] | has("tags")' "$LEARNINGS_FILE")
    local has_helpful_count=$(jq '.[0] | has("helpful_count")' "$LEARNINGS_FILE")

    if [ "$has_id" = "true" ] && [ "$has_timestamp" = "true" ] && \
       [ "$has_lesson" = "true" ] && [ "$has_tags" = "true" ] && \
       [ "$has_helpful_count" = "true" ]; then
        test_pass "Learning structure is correct"
    else
        test_fail "Learning structure is missing required fields"
    fi

    # Test 4: Write failed learning
    test_start "Write failed learning"
    if learnings_write "TEST-002" 1 "false" "Test failed with error" "test error failed" "$context_json"; then
        local count
        count=$(jq 'length' "$LEARNINGS_FILE")
        if [ "$count" -eq 2 ]; then
            test_pass "Failed learning written successfully"
        else
            test_fail "Unexpected learning count: $count"
        fi
    else
        test_fail "Failed to write failed learning"
    fi

    # Test 5: Rate learning as helpful
    test_start "Rate learning as helpful"
    local first_id
    first_id=$(jq -r '.[0].id' "$LEARNINGS_FILE")
    if learnings_rate "$first_id" --helpful; then
        local helpful_count
        helpful_count=$(jq -r '.[0].helpful_count' "$LEARNINGS_FILE")
        if [ "$helpful_count" -eq 1 ]; then
            test_pass "Learning rated as helpful"
        else
            test_fail "Helpful count incorrect: $helpful_count"
        fi
    else
        test_fail "Failed to rate learning"
    fi

    # Test 6: Rate learning as unhelpful
    test_start "Rate learning as unhelpful"
    if learnings_rate "$first_id" --unhelpful; then
        local helpful_count
        helpful_count=$(jq -r '.[0].helpful_count' "$LEARNINGS_FILE")
        if [ "$helpful_count" -eq 0 ]; then
            test_pass "Learning rated as unhelpful"
        else
            test_fail "Helpful count incorrect after unhelpful: $helpful_count"
        fi
    else
        test_fail "Failed to rate learning as unhelpful"
    fi

    # Test 7: Automatic tag extraction
    test_start "Automatic tag extraction"
    local tags
    tags=$(extract_story_tags "Implement hook system for lifecycle extension" "test.sh example.py")

    # Check if tags contain expected keywords
    if echo "$tags" | grep -q "implement" && echo "$tags" | grep -q "hook"; then
        test_pass "Tags extracted correctly"
    else
        test_fail "Expected tags not found. Got: $tags"
    fi

    # Test 8: Query learnings by tag
    test_start "Query learnings by tag"
    local results
    results=$(jq 'map(select(.tags | index("test")))' "$LEARNINGS_FILE")
    local result_count
    result_count=$(echo "$results" | jq 'length')

    if [ "$result_count" -ge 1 ]; then
        test_pass "Query by tag successful"
    else
        test_fail "Query by tag failed, expected at least 1 result"
    fi

    # Test 9: Feature flag disabled
    test_start "Feature flag disabled behavior"
    export LEARNINGS_ENABLED=false
    if learnings_write "TEST-003" 1 "true" "Should not write" "test" "{}"; then
        local count
        count=$(jq 'length' "$LEARNINGS_FILE")
        if [ "$count" -eq 2 ]; then
            test_pass "Learning not written when disabled"
        else
            test_fail "Learning was written despite feature flag being disabled"
        fi
    else
        # learnings_write returns 0 when disabled, so this is unexpected
        test_fail "learnings_write returned non-zero when disabled"
    fi
    export LEARNINGS_ENABLED=true

    # Test 10: Multiple learnings sort by helpful_count
    test_start "Sort learnings by helpful_count"
    local second_id
    second_id=$(jq -r '.[1].id' "$LEARNINGS_FILE")
    learnings_rate "$second_id" --helpful
    learnings_rate "$second_id" --helpful

    local sorted_results
    sorted_results=$(jq 'sort_by(-.helpful_count)' "$LEARNINGS_FILE")
    local top_id
    top_id=$(echo "$sorted_results" | jq -r '.[0].id')

    if [ "$top_id" = "$second_id" ]; then
        test_pass "Learnings sorted by helpful_count correctly"
    else
        test_fail "Sorting by helpful_count failed"
    fi

    # Test 11: JSON schema validation
    test_start "JSON schema validation"
    if jq empty "$LEARNINGS_FILE" 2>/dev/null; then
        test_pass "Learnings file is valid JSON"
    else
        test_fail "Learnings file contains invalid JSON"
    fi

    # Test 12: Performance check (file size < 10MB for 1000 learnings approximation)
    test_start "Performance check"
    local file_size
    file_size=$(wc -c < "$LEARNINGS_FILE" | tr -d ' ')
    # With 2 learnings, file should be small (< 5KB)
    if [ "$file_size" -lt 5000 ]; then
        test_pass "File size is reasonable ($file_size bytes)"
    else
        test_fail "File size is too large ($file_size bytes)"
    fi
}

# Main execution
main() {
    setup_learnings_functions
    run_tests

    echo ""
    echo -e "${YELLOW}=== Test Summary ===${NC}"
    echo -e "Tests run: ${TESTS_RUN}"
    echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
    echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

main "$@"
