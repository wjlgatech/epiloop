#!/usr/bin/env bash
#
# Test: Skills Catalog Consistency
#
# Verifies that skills-overview.md only references implemented skills
# and skill-enforcer.sh only enforces skills that exist.

set -uo pipefail  # Removed -e to allow script to continue on errors

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((pass_count++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((fail_count++))
}

# Test 1: Verify all skills in skills-overview.md have SKILL.md files
echo "Test 1: Skills catalog consistency"
echo "-----------------------------------"

# Extract skill names from skills-overview.md (under "Available Skills (Implemented)")
# Look for lines that start with ** and contain only skill name (no spaces after **)
# This pattern: **skill-name** followed by newline
skills_in_overview=$(grep -A 200 "## Available Skills (Implemented)" "$PROJECT_ROOT/lib/skills-overview.md" | grep -B 200 "## TODO:" | grep '^\*\*[a-z-]*\*\*$' | sed 's/\*\*//g' | grep -v "^$")

missing_skills=()
while IFS= read -r skill; do
    [ -z "$skill" ] && continue  # Skip empty lines
    skill_path="$PROJECT_ROOT/skills/$skill/SKILL.md"
    if [ ! -f "$skill_path" ]; then
        missing_skills+=("$skill")
        fail "Skill '$skill' listed in skills-overview.md but $skill_path not found"
    else
        pass "Skill '$skill' has implementation at $skill_path"
    fi
done <<< "$skills_in_overview"

if [ ${#missing_skills[@]} -eq 0 ]; then
    pass "All skills in overview have implementations"
else
    fail "Found ${#missing_skills[@]} skills without implementations"
fi

# Test 2: Verify TODO skills are NOT in Available Skills section
echo ""
echo "Test 2: TODO skills not in Available Skills"
echo "--------------------------------------------"

todo_skills=("test-driven-development" "systematic-debugging" "verification-before-completion" "writing-plans" "executing-plans" "subagent-driven-development" "requesting-code-review" "receiving-code-review" "using-git-worktrees" "finishing-a-development-branch" "writing-skills")

for skill in "${todo_skills[@]}"; do
    # Check if skill appears in "Available Skills (Implemented)" section
    if grep -A 200 "## Available Skills (Implemented)" "$PROJECT_ROOT/lib/skills-overview.md" | grep -B 200 "## TODO:" | grep -q "^\*\*$skill\*\*"; then
        fail "TODO skill '$skill' found in Available Skills section"
    else
        pass "TODO skill '$skill' correctly in TODO section only"
    fi
done

# Test 3: Verify skill-enforcer.sh doesn't enforce unimplemented skills
echo ""
echo "Test 3: Skill enforcer doesn't enforce unimplemented skills"
echo "------------------------------------------------------------"

# Test with story requiring TDD (should NOT enforce since test-driven-development doesn't exist)
output=$(bash "$PROJECT_ROOT/lib/skill-enforcer.sh" "implement user authentication feature" 3 2>&1 || true)
if echo "$output" | grep -q "test-driven-development"; then
    fail "skill-enforcer.sh tried to enforce unimplemented 'test-driven-development'"
else
    pass "skill-enforcer.sh does not enforce unimplemented 'test-driven-development'"
fi

# Test with story requiring debugging (should NOT enforce since systematic-debugging doesn't exist)
output=$(bash "$PROJECT_ROOT/lib/skill-enforcer.sh" "fix bug in login flow" 2 2>&1 || true)
if echo "$output" | grep -q "systematic-debugging"; then
    fail "skill-enforcer.sh tried to enforce unimplemented 'systematic-debugging'"
else
    pass "skill-enforcer.sh does not enforce unimplemented 'systematic-debugging'"
fi

# Test with story requiring brainstorming (SHOULD enforce since brainstorming exists)
output=$(bash "$PROJECT_ROOT/lib/skill-enforcer.sh" "design authentication system" 7 2>&1 || true)
if echo "$output" | grep -q "brainstorming"; then
    pass "skill-enforcer.sh correctly enforces implemented 'brainstorming'"
else
    fail "skill-enforcer.sh failed to enforce implemented 'brainstorming'"
fi

# Test 4: Verify all implemented skills are in skills-overview.md
echo ""
echo "Test 4: All implemented skills are documented"
echo "----------------------------------------------"

for skill_dir in "$PROJECT_ROOT/skills"/*/; do
    skill_name=$(basename "$skill_dir")
    skill_file="$skill_dir/SKILL.md"

    if [ -f "$skill_file" ]; then
        # Check if skill is mentioned in skills-overview.md
        if grep -q "\*\*$skill_name\*\*" "$PROJECT_ROOT/lib/skills-overview.md"; then
            pass "Implemented skill '$skill_name' is documented in skills-overview.md"
        else
            fail "Implemented skill '$skill_name' is NOT documented in skills-overview.md"
        fi
    fi
done

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Passed: $pass_count"
echo "Failed: $fail_count"

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
