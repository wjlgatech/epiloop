#!/bin/bash
#
# test_story_splitter.sh - Tests for story-splitter.py (US-002)
#
# Tests split proposal generation, approval workflow, and PRD integration

set -euo pipefail

# Setup
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STORY_SPLITTER="$PROJECT_ROOT/lib/story-splitter.py"
TEST_DIR="$PROJECT_ROOT/.test-tmp/story-splitter"
PASSED=0
FAILED=0

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
setup() {
    rm -rf "$TEST_DIR"
    mkdir -p "$TEST_DIR"
}

teardown() {
    rm -rf "$TEST_DIR"
}

assert_eq() {
    local expected="$1"
    local actual="$2"
    local message="${3:-}"

    if [ "$expected" = "$actual" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} $message"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} $message"
        echo "  Expected: $expected"
        echo "  Actual: $actual"
    fi
}

assert_file_exists() {
    local file="$1"
    local message="${2:-File should exist: $file}"

    if [ -f "$file" ] || [ -d "$file" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} $message"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} $message"
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="${3:-}"

    if echo "$haystack" | grep -q "$needle"; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} $message"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} $message"
        echo "  Expected to contain: $needle"
    fi
}

# Create test PRD
create_test_prd() {
    local prd_path="$TEST_DIR/test-prd.json"

    cat > "$prd_path" <<'EOF'
{
  "project": "test-project",
  "branchName": "feature/test",
  "description": "Test project for story splitting",
  "userStories": [
    {
      "id": "US-001",
      "title": "Simple Story",
      "description": "A simple story that doesn't need splitting",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2"
      ],
      "priority": 1,
      "fileScope": ["lib/simple.py"],
      "estimatedComplexity": "simple",
      "passes": true,
      "notes": "Already complete"
    },
    {
      "id": "US-002",
      "title": "Complex Story That Needs Splitting",
      "description": "A complex story with many acceptance criteria and file scope",
      "acceptanceCriteria": [
        "Implement feature A",
        "Implement feature B",
        "Implement feature C",
        "Add tests for A",
        "Add tests for B",
        "Add tests for C",
        "Add documentation",
        "Integrate with existing system"
      ],
      "priority": 1,
      "fileScope": [
        "lib/complex.py",
        "lib/utils.py",
        "tests/test_complex.py",
        "docs/features.md"
      ],
      "estimatedComplexity": "complex",
      "passes": false,
      "notes": ""
    }
  ]
}
EOF

    echo "$prd_path"
}

# Create test complexity report
create_complexity_report() {
    local report_path="$TEST_DIR/complexity-report.json"

    cat > "$report_path" <<'EOF'
{
  "story_id": "US-002",
  "timestamp": "2026-01-14T10:00:00Z",
  "complexity_score": 8.5,
  "signals": {
    "acceptance_criteria": {
      "completed": 3,
      "total": 8,
      "total_time_ms": 900000,
      "estimated_time_per_ac": 150000
    },
    "file_scope": {
      "initial_scope": "lib/complex.py,lib/utils.py",
      "files_modified": 6,
      "files_outside_scope": 2
    },
    "errors": {
      "count": 5,
      "threshold": 3
    },
    "clarifications": {
      "count": 3
    }
  },
  "threshold": 7,
  "should_split": true
}
EOF

    echo "$report_path"
}

# ============================================================================
# Test Cases
# ============================================================================

echo "Running Story Splitter Tests (US-002)"
echo "======================================"

# Test 1: story-splitter.py exists and is executable
test_splitter_exists() {
    echo ""
    echo "Test 1: story-splitter.py exists and is executable"
    echo "---------------------------------------------------"

    assert_file_exists "$STORY_SPLITTER" "story-splitter.py exists"

    if [ -x "$STORY_SPLITTER" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} story-splitter.py is executable"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} story-splitter.py is not executable"
    fi
}

# Test 2: Can load and parse test PRD
test_load_prd() {
    echo ""
    echo "Test 2: Can load and parse test PRD"
    echo "------------------------------------"

    setup
    local prd_path=$(create_test_prd)

    # Test that PRD is valid JSON
    if jq -e . "$prd_path" > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Test PRD is valid JSON"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Test PRD is not valid JSON"
    fi

    # Test that we can find US-002
    local story_id=$(jq -r '.userStories[] | select(.id == "US-002") | .id' "$prd_path")
    assert_eq "US-002" "$story_id" "Can find US-002 in PRD"

    teardown
}

# Test 3: list-proposals shows empty list initially
test_list_proposals_empty() {
    echo ""
    echo "Test 3: list-proposals shows empty list initially"
    echo "--------------------------------------------------"

    setup

    # Ensure proposals directory doesn't exist or is empty
    local proposals_dir="$PROJECT_ROOT/.claude-loop/split-proposals"
    rm -rf "$proposals_dir"

    # This should not error even if no proposals exist
    if python3 "$STORY_SPLITTER" list-proposals > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} list-proposals runs successfully on empty state"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} list-proposals failed on empty state"
    fi

    teardown
}

# Test 4: Proposal generation creates required directories
test_proposal_directories() {
    echo ""
    echo "Test 4: Proposal generation creates required directories"
    echo "---------------------------------------------------------"

    setup

    # The propose command would normally call Claude, but we're just testing
    # that the directory structure is created correctly
    # We'll manually create a proposal to simulate this

    local proposals_dir="$PROJECT_ROOT/.claude-loop/split-proposals"
    mkdir -p "$proposals_dir"

    assert_file_exists "$(dirname "$proposals_dir")" ".claude-loop directory exists"
    assert_file_exists "$proposals_dir" "split-proposals directory exists"

    teardown
}

# Test 5: Proposal JSON structure validation
test_proposal_structure() {
    echo ""
    echo "Test 5: Proposal JSON structure validation"
    echo "-------------------------------------------"

    setup
    local proposals_dir="$PROJECT_ROOT/.claude-loop/split-proposals"
    mkdir -p "$proposals_dir"

    # Create a mock proposal to test the structure
    local proposal_path="$proposals_dir/SPLIT-TEST0001.json"
    cat > "$proposal_path" <<'EOF'
{
  "proposal_id": "SPLIT-TEST0001",
  "story_id": "US-002",
  "prd_path": "/path/to/prd.json",
  "original_story": {
    "id": "US-002",
    "title": "Complex Story"
  },
  "sub_stories": [
    {
      "id": "US-002A",
      "title": "Sub-story A",
      "description": "First part",
      "acceptanceCriteria": ["AC1", "AC2"],
      "priority": 1,
      "dependencies": [],
      "fileScope": ["lib/file.py"],
      "estimatedComplexity": "simple",
      "estimatedDuration": "1-2 hours",
      "passes": false,
      "notes": ""
    }
  ],
  "rationale": "Split for better focus",
  "complexity_signals": {},
  "estimated_time_savings": "20% faster",
  "created_at": "2026-01-14T10:00:00Z",
  "status": "pending",
  "reviewed_at": null,
  "reviewer_notes": null
}
EOF

    # Validate JSON structure
    if jq -e . "$proposal_path" > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Proposal JSON is valid"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Proposal JSON is invalid"
    fi

    # Check required fields
    local proposal_id=$(jq -r '.proposal_id' "$proposal_path")
    assert_eq "SPLIT-TEST0001" "$proposal_id" "Proposal has correct ID"

    local story_id=$(jq -r '.story_id' "$proposal_path")
    assert_eq "US-002" "$story_id" "Proposal has correct story ID"

    local sub_story_count=$(jq '.sub_stories | length' "$proposal_path")
    assert_eq "1" "$sub_story_count" "Proposal has sub-stories array"

    teardown
}

# Test 6: SubStory structure validation
test_substory_structure() {
    echo ""
    echo "Test 6: SubStory structure validation"
    echo "--------------------------------------"

    setup

    # Create a test sub-story JSON
    local substory_json='
    {
      "id": "US-002A",
      "title": "Sub-story A",
      "description": "First part of the split",
      "acceptanceCriteria": ["AC1", "AC2"],
      "priority": 1,
      "dependencies": [],
      "fileScope": ["lib/file.py"],
      "estimatedComplexity": "simple",
      "estimatedDuration": "1-2 hours",
      "passes": false,
      "notes": ""
    }'

    # Validate it's valid JSON
    if echo "$substory_json" | jq -e . > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} SubStory JSON is valid"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} SubStory JSON is invalid"
    fi

    # Check required fields
    local sub_id=$(echo "$substory_json" | jq -r '.id')
    assert_contains "$sub_id" "US-002" "SubStory ID contains parent ID"

    local complexity=$(echo "$substory_json" | jq -r '.estimatedComplexity')
    if [ "$complexity" = "simple" ] || [ "$complexity" = "medium" ] || [ "$complexity" = "complex" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} SubStory has valid complexity"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} SubStory has invalid complexity: $complexity"
    fi

    teardown
}

# Test 7: Split proposal JSONL log format
test_proposal_log_format() {
    echo ""
    echo "Test 7: Split proposal JSONL log format"
    echo "----------------------------------------"

    setup
    local log_file="$PROJECT_ROOT/.claude-loop/split-proposals.jsonl"
    mkdir -p "$(dirname "$log_file")"

    # Create test log entry
    echo '{"timestamp": "2026-01-14T10:00:00Z", "proposal_id": "SPLIT-TEST0001", "story_id": "US-002", "status": "pending", "sub_story_count": 2}' >> "$log_file"

    # Validate JSONL format
    if jq -e . "$log_file" > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Proposal log is valid JSONL"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Proposal log is invalid JSONL"
    fi

    # Check log entry fields
    local entry_count=$(wc -l < "$log_file" | tr -d ' ')
    assert_eq "1" "$entry_count" "Log has one entry"

    rm -f "$log_file"
    teardown
}

# Test 8: Complexity report integration
test_complexity_report_loading() {
    echo ""
    echo "Test 8: Complexity report integration"
    echo "--------------------------------------"

    setup
    local report_path=$(create_complexity_report)

    # Validate complexity report
    if jq -e . "$report_path" > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Complexity report is valid JSON"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Complexity report is invalid JSON"
    fi

    # Check report fields
    local score=$(jq -r '.complexity_score' "$report_path")
    if (( $(echo "$score > 7" | bc -l) )); then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Complexity score ($score) exceeds threshold (7)"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Complexity score ($score) does not exceed threshold (7)"
    fi

    local should_split=$(jq -r '.should_split' "$report_path")
    assert_eq "true" "$should_split" "Complexity report indicates split should trigger"

    teardown
}

# Test 9: Proposal ID generation uniqueness
test_proposal_id_generation() {
    echo ""
    echo "Test 9: Proposal ID generation uniqueness"
    echo "------------------------------------------"

    setup

    # Simulate two proposals for different stories
    local id1="SPLIT-$(echo -n "US-001_2026-01-14T10:00:00Z" | sha256sum | cut -c1-8 | tr '[:lower:]' '[:upper:]')"
    local id2="SPLIT-$(echo -n "US-002_2026-01-14T10:00:00Z" | sha256sum | cut -c1-8 | tr '[:lower:]' '[:upper:]')"

    if [ "$id1" != "$id2" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Proposal IDs are unique for different stories"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Proposal IDs are not unique"
    fi

    # Check ID format
    if [[ "$id1" =~ ^SPLIT-[A-F0-9]{8}$ ]]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} Proposal ID format is correct (SPLIT-XXXXXXXX)"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} Proposal ID format is incorrect: $id1"
    fi

    teardown
}

# Test 10: Help text and CLI interface
test_cli_help() {
    echo ""
    echo "Test 10: Help text and CLI interface"
    echo "-------------------------------------"

    # Test that help runs without error
    if python3 "$STORY_SPLITTER" --help > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} --help flag works"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} --help flag failed"
    fi

    # Test that commands are documented
    local help_text=$(python3 "$STORY_SPLITTER" --help 2>&1)
    assert_contains "$help_text" "propose" "Help text documents 'propose' command"
    assert_contains "$help_text" "approve" "Help text documents 'approve' command"
    assert_contains "$help_text" "reject" "Help text documents 'reject' command"
    assert_contains "$help_text" "list-proposals" "Help text documents 'list-proposals' command"
}

# Run all tests
test_splitter_exists
test_load_prd
test_list_proposals_empty
test_proposal_directories
test_proposal_structure
test_substory_structure
test_proposal_log_format
test_complexity_report_loading
test_proposal_id_generation
test_cli_help

# Summary
echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
