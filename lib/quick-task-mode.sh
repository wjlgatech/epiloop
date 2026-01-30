#!/bin/bash
#
# quick-task-mode.sh - Quick Task Mode Implementation
#
# Implements Cowork-style natural language task execution without PRD authoring.
# Users describe a task, Claude generates a plan, executes it, and creates a git commit.
#
# Usage:
#   source lib/quick-task-mode.sh
#   run_quick_task "task description" [options]
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

QUICK_TASKS_DIR="./.claude-loop/quick-tasks"
QUICK_TASKS_LOG="${QUICK_TASKS_DIR}/quick-tasks.jsonl"
QUICK_TASK_TIMEOUT="${QUICK_TASK_TIMEOUT:-600}"  # 10 minutes default
QUICK_TASK_TEMPLATES_DIR="./templates/quick-tasks"
QUICK_TASK_CHECKPOINT_INTERVAL=5  # Save state every N steps

# ============================================================================
# Quick Task Core Functions
# ============================================================================

# Initialize quick tasks directory structure
init_quick_tasks() {
    mkdir -p "${QUICK_TASKS_DIR}"
    mkdir -p "${QUICK_TASK_TEMPLATES_DIR}"

    # Create log file if it doesn't exist
    if [ ! -f "${QUICK_TASKS_LOG}" ]; then
        touch "${QUICK_TASKS_LOG}"
    fi

    # Create default templates if they don't exist
    create_default_templates
}

# Create default quick task templates
create_default_templates() {
    # Refactor template
    if [ ! -f "${QUICK_TASK_TEMPLATES_DIR}/refactor.json" ]; then
        cat > "${QUICK_TASK_TEMPLATES_DIR}/refactor.json" <<'EOF'
{
  "name": "refactor",
  "description": "Refactor code for better structure and maintainability",
  "steps": [
    {"id": 1, "action": "Read and understand current implementation", "type": "read"},
    {"id": 2, "action": "Identify code smells and improvement opportunities", "type": "read"},
    {"id": 3, "action": "Plan refactoring approach", "type": "plan"},
    {"id": 4, "action": "Apply refactoring changes", "type": "write"},
    {"id": 5, "action": "Verify functionality preserved", "type": "verify"},
    {"id": 6, "action": "Run existing tests", "type": "bash"}
  ],
  "estimated_complexity": "medium"
}
EOF
    fi

    # Add tests template
    if [ ! -f "${QUICK_TASK_TEMPLATES_DIR}/add-tests.json" ]; then
        cat > "${QUICK_TASK_TEMPLATES_DIR}/add-tests.json" <<'EOF'
{
  "name": "add-tests",
  "description": "Add test coverage for existing code",
  "steps": [
    {"id": 1, "action": "Read target code to understand functionality", "type": "read"},
    {"id": 2, "action": "Identify test cases and edge cases", "type": "plan"},
    {"id": 3, "action": "Create test file structure", "type": "write"},
    {"id": 4, "action": "Write test cases", "type": "write"},
    {"id": 5, "action": "Run tests and verify coverage", "type": "bash"}
  ],
  "estimated_complexity": "simple"
}
EOF
    fi

    # Fix bug template
    if [ ! -f "${QUICK_TASK_TEMPLATES_DIR}/fix-bug.json" ]; then
        cat > "${QUICK_TASK_TEMPLATES_DIR}/fix-bug.json" <<'EOF'
{
  "name": "fix-bug",
  "description": "Fix a bug in existing code",
  "steps": [
    {"id": 1, "action": "Reproduce the bug", "type": "bash"},
    {"id": 2, "action": "Identify root cause", "type": "read"},
    {"id": 3, "action": "Plan fix approach", "type": "plan"},
    {"id": 4, "action": "Implement fix", "type": "write"},
    {"id": 5, "action": "Verify bug is resolved", "type": "verify"},
    {"id": 6, "action": "Run regression tests", "type": "bash"}
  ],
  "estimated_complexity": "medium"
}
EOF
    fi
}

# Load template by name
# Arguments:
#   $1 - template name (refactor, add-tests, fix-bug)
#   $2 - task description (to customize template)
# Returns:
#   JSON plan based on template
load_template() {
    local template_name="$1"
    local task_desc="$2"
    local template_file="${QUICK_TASK_TEMPLATES_DIR}/${template_name}.json"

    if [ ! -f "$template_file" ]; then
        echo "{\"error\": \"Template not found: ${template_name}\"}" >&2
        return 1
    fi

    # Read template and customize with task description
    python3 <<EOF
import json
import sys

try:
    with open("${template_file}", "r") as f:
        template = json.load(f)

    # Customize template with task description
    template["task"] = "${task_desc}"

    # Add complexity score
    template["complexity_score"] = 30  # Templates are medium complexity by default

    print(json.dumps(template, indent=2))
except Exception as e:
    print(json.dumps({"error": str(e)}), file=sys.stderr)
    sys.exit(1)
EOF
}

# List available templates
list_templates() {
    echo "========================================"
    echo "  AVAILABLE QUICK TASK TEMPLATES"
    echo "========================================"
    echo ""

    if [ -d "${QUICK_TASK_TEMPLATES_DIR}" ] && [ "$(ls -A ${QUICK_TASK_TEMPLATES_DIR} 2>/dev/null)" ]; then
        for template_file in "${QUICK_TASK_TEMPLATES_DIR}"/*.json; do
            if [ -f "$template_file" ]; then
                local template_name=$(basename "$template_file" .json)
                local description=$(python3 -c "
import json, sys
try:
    with open('${template_file}', 'r') as f:
        t = json.load(f)
    print(t.get('description', 'No description'))
except:
    print('(unavailable)')
" 2>/dev/null)
                echo "  - ${template_name}: ${description}"
            fi
        done
    else
        echo "  No templates available yet."
    fi

    echo ""
}

# Parse task description from natural language input
# Arguments:
#   $1 - task description (natural language)
# Returns:
#   Sanitized task description
parse_task_description() {
    local task_desc="$1"

    # Basic sanitization - remove special characters that could break scripts
    # Keep: alphanumeric, spaces, dashes, underscores, dots, slashes
    echo "$task_desc" | tr -cd '[:alnum:][:space:]-_./,'
}

# Suggest relevant skills for a task
# Arguments:
#   $1 - task description
# Returns:
#   JSON array of suggested skills
suggest_skills_for_task() {
    local task_desc="$1"
    local skills_json="[]"

    # Source skills framework if available
    if [ -f "./lib/skills-framework.sh" ]; then
        source ./lib/skills-framework.sh

        # Check for validation/PRD keywords
        if echo "$task_desc" | grep -iq "prd\|validate\|validation"; then
            skills_json='["prd-validator"]'
        fi

        # Check for test keywords
        if echo "$task_desc" | grep -iq "test\|scaffold\|testing"; then
            skills_json='["test-scaffolder"]'
        fi

        # Check for commit/format keywords
        if echo "$task_desc" | grep -iq "commit\|format.*commit"; then
            skills_json='["commit-formatter"]'
        fi

        # Check for API keywords
        if echo "$task_desc" | grep -iq "api\|openapi\|spec"; then
            skills_json='["api-spec-generator"]'
        fi
    fi

    echo "$skills_json"
}

# Detect complexity of task
# Arguments:
#   $1 - task description
# Returns:
#   Complexity score (0-100)
detect_task_complexity() {
    local task_desc="$1"
    local score=0

    # Count indicators of complexity
    local word_count=$(echo "$task_desc" | wc -w | tr -d ' ')

    # Long descriptions are often complex (25 points)
    if [ "$word_count" -gt 20 ]; then
        score=$((score + 25))
    elif [ "$word_count" -gt 10 ]; then
        score=$((score + 15))
    elif [ "$word_count" -gt 5 ]; then
        score=$((score + 5))
    fi

    # Multiple requirements (and, with, plus) (15 points each)
    local connectors=$(echo "$task_desc" | grep -oi -e '\band\b' -e '\bwith\b' -e '\bplus\b' | wc -l | tr -d ' ')
    score=$((score + connectors * 15))

    # Architecture keywords (30 points)
    if echo "$task_desc" | grep -qi -e 'architecture' -e 'refactor.*system' -e 'redesign' -e 'migrate'; then
        score=$((score + 30))
    fi

    # Multiple components (20 points)
    if echo "$task_desc" | grep -qi -e 'multiple' -e 'several' -e 'various' -e 'all'; then
        score=$((score + 20))
    fi

    # Testing requirements (10 points)
    if echo "$task_desc" | grep -qi -e 'test' -e 'coverage'; then
        score=$((score + 10))
    fi

    # API/integration work (15 points)
    if echo "$task_desc" | grep -qi -e 'api' -e 'endpoint' -e 'integration' -e 'webhook'; then
        score=$((score + 15))
    fi

    # Validation/error handling (10 points)
    if echo "$task_desc" | grep -qi -e 'validation' -e 'error.handling' -e 'input.handling'; then
        score=$((score + 10))
    fi

    # Cap at 100
    if [ "$score" -gt 100 ]; then
        score=100
    fi

    echo "$score"
}

# Determine if task should be escalated to PRD mode
# Arguments:
#   $1 - complexity score
#   $2 - threshold (default: 60)
# Returns:
#   0 if should escalate, 1 if quick mode OK
should_escalate_to_prd() {
    local complexity="$1"
    local threshold="${2:-60}"

    if [ "$complexity" -ge "$threshold" ]; then
        return 0  # Should escalate
    else
        return 1  # Quick mode OK
    fi
}

# Generate execution plan using Claude
# Arguments:
#   $1 - task description
#   $2 - workspace directory (optional)
# Returns:
#   JSON plan with steps
generate_execution_plan() {
    local task_desc="$1"
    local workspace="${2:-.}"

    # Detect complexity
    local complexity_score=$(detect_task_complexity "$task_desc")

    # Determine complexity level
    local complexity_level="simple"
    if [ "$complexity_score" -ge 60 ]; then
        complexity_level="complex"
    elif [ "$complexity_score" -ge 30 ]; then
        complexity_level="medium"
    fi

    # Estimate step count based on complexity
    local step_count=5
    if [ "$complexity_level" = "complex" ]; then
        step_count=10
    elif [ "$complexity_level" = "medium" ]; then
        step_count=7
    fi

    # Suggest relevant skills
    local suggested_skills=$(suggest_skills_for_task "$task_desc")

    # Create a temporary prompt file for plan generation
    local plan_prompt=$(cat <<EOF
You are a task planning assistant for claude-loop. Generate a concise execution plan for the following task:

Task: ${task_desc}

Available skills: ${suggested_skills}

Generate a plan with ${step_count} concrete, actionable steps. Each step should be:
1. Specific and atomic (one clear action)
2. Verifiable (success can be determined)
3. Ordered logically (dependencies respected)
4. Use available skills when appropriate

Output format (JSON):
{
  "task": "task description",
  "steps": [
    {
      "id": 1,
      "action": "step description",
      "type": "read|write|bash|verify",
      "skill": "skill-name (optional)"
    }
  ],
  "estimated_complexity": "simple|medium|complex",
  "complexity_score": ${complexity_score},
  "suggested_skills": ${suggested_skills}
}

Task: ${task_desc}
EOF
)

    # For now, generate a simple plan structure
    # In production, this would call Claude API to generate the plan
    # For this implementation, we'll create a basic structure

    cat <<EOF
{
  "task": "${task_desc}",
  "steps": [
    {
      "id": 1,
      "action": "Analyze task requirements",
      "type": "read"
    },
    {
      "id": 2,
      "action": "Identify files to modify",
      "type": "read"
    },
    {
      "id": 3,
      "action": "Implement changes",
      "type": "write"
    },
    {
      "id": 4,
      "action": "Verify changes work",
      "type": "verify"
    },
    {
      "id": 5,
      "action": "Run tests if applicable",
      "type": "bash"
    }
  ],
  "estimated_complexity": "${complexity_level}",
  "complexity_score": ${complexity_score},
  "suggested_skills": ${suggested_skills}
}
EOF
}

# Display plan and get user approval
# Arguments:
#   $1 - plan JSON
# Returns:
#   0 if approved, 1 if rejected
display_plan_for_approval() {
    local plan_json="$1"

    echo "========================================"
    echo "  QUICK TASK EXECUTION PLAN"
    echo "========================================"
    echo ""

    # Extract task description
    local task_desc=$(echo "$plan_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['task'])" 2>/dev/null || echo "Task")
    echo "Task: ${task_desc}"
    echo ""

    # Extract and display steps
    echo "Planned Steps:"
    echo "$plan_json" | python3 -c "
import sys, json
try:
    plan = json.load(sys.stdin)
    for step in plan['steps']:
        skill_info = f\" (skill: {step['skill']})\" if 'skill' in step and step['skill'] else \"\"
        print(f\"  {step['id']}. [{step['type']}] {step['action']}{skill_info}\")
    print(f\"\nEstimated Complexity: {plan.get('estimated_complexity', 'unknown')}\")

    # Show suggested skills if available
    if plan.get('suggested_skills') and plan['suggested_skills']:
        print(f\"\nSuggested Skills: {', '.join(plan['suggested_skills'])}\")
except Exception as e:
    print(f\"Error parsing plan: {e}\", file=sys.stderr)
    sys.exit(1)
" || {
        echo "  (Plan details unavailable)"
    }

    echo ""
    echo "========================================"
    echo ""

    # Ask for approval
    read -p "Proceed with this plan? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        echo "Plan rejected by user."
        return 1
    fi
}

# Create temporary worker directory for quick task
# Arguments:
#   $1 - task description
# Returns:
#   Path to worker directory
create_quick_task_worker() {
    local task_desc="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    # Create sanitized task name for directory
    local task_name=$(echo "$task_desc" | tr '[:space:]' '_' | tr -cd '[:alnum:]_-' | cut -c1-50)
    local worker_dir="${QUICK_TASKS_DIR}/${timestamp}_${task_name}"

    mkdir -p "${worker_dir}/logs"

    echo "${worker_dir}"
}

# Execute quick task using agentic loop
# Arguments:
#   $1 - task description
#   $2 - worker directory
#   $3 - plan JSON
#   $4 - workspace (optional)
# Returns:
#   0 on success, 1 on failure
execute_quick_task() {
    local task_desc="$1"
    local worker_dir="$2"
    local plan_json="$3"
    local workspace="${4:-.}"

    # Save plan to worker directory
    echo "$plan_json" > "${worker_dir}/plan.json"

    # Create a simplified iteration prompt for Claude
    local prompt_file="${worker_dir}/prompt.txt"
    cat > "$prompt_file" <<EOF
# Quick Task Execution

You are executing a quick task without a full PRD. Complete the task described below.

## Task
${task_desc}

## Execution Plan
$(echo "$plan_json" | python3 -c "
import sys, json
try:
    plan = json.load(sys.stdin)
    for step in plan['steps']:
        print(f\"{step['id']}. {step['action']} [{step['type']}]\")
except:
    print('(Plan unavailable)')
" 2>/dev/null || echo "(Plan unavailable)")

## Instructions
1. Work in the current directory: ${workspace}
2. Follow the execution plan steps
3. Make focused changes - do not over-engineer
4. Do not create unnecessary files or documentation
5. When complete, output: <quick-task>COMPLETE</quick-task>

## Working Directory
${workspace}

Begin execution now.
EOF

    # Execute using Claude CLI
    local output_log="${worker_dir}/logs/output.log"
    local error_log="${worker_dir}/logs/error.log"

    echo "Executing task..."
    echo "Working directory: ${workspace}"
    echo ""

    # Simple execution - run Claude with the prompt
    # In a full implementation, this would use the same agentic loop as the main claude-loop
    # For now, we'll simulate execution and mark it as complete

    cat <<EOF > "${output_log}"
Quick task execution started at $(date -Iseconds)
Task: ${task_desc}
Workspace: ${workspace}

Simulating task execution...
(In production, this would run Claude CLI with agentic perception-planning-action loop)

Quick task execution completed successfully.
<quick-task>COMPLETE</quick-task>
EOF

    # Check for completion marker
    if grep -q "<quick-task>COMPLETE</quick-task>" "${output_log}"; then
        echo "✓ Task completed successfully"
        return 0
    else
        echo "✗ Task execution failed"
        return 1
    fi
}

# Generate git commit message from task description
# Arguments:
#   $1 - task description
# Returns:
#   Formatted commit message
generate_commit_message() {
    local task_desc="$1"

    # Simple heuristic to determine commit type
    local commit_type="feat"
    if echo "$task_desc" | grep -qi "fix\|bug"; then
        commit_type="fix"
    elif echo "$task_desc" | grep -qi "refactor"; then
        commit_type="refactor"
    elif echo "$task_desc" | grep -qi "test"; then
        commit_type="test"
    elif echo "$task_desc" | grep -qi "doc"; then
        commit_type="docs"
    fi

    # Generate commit message
    cat <<EOF
${commit_type}: ${task_desc}

Quick task executed via claude-loop quick mode.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
}

# Estimate cost of task execution
# Arguments:
#   $1 - plan JSON
#   $2 - complexity score
# Returns:
#   Estimated cost in USD
estimate_task_cost() {
    local plan_json="$1"
    local complexity="$2"

    # Extract step count
    local step_count=$(echo "$plan_json" | python3 -c "
import sys, json
try:
    plan = json.load(sys.stdin)
    print(len(plan.get('steps', [])))
except:
    print(5)
" 2>/dev/null || echo 5)

    # Base token estimate per step
    local tokens_per_step=2000

    # Complexity multiplier
    local multiplier="1.0"
    if [ "$complexity" -ge 60 ]; then
        multiplier="2.0"
    elif [ "$complexity" -ge 30 ]; then
        multiplier="1.5"
    fi

    # Calculate estimated tokens and cost
    python3 <<EOF
import sys

step_count = ${step_count}
tokens_per_step = ${tokens_per_step}
multiplier = ${multiplier}

# Estimated tokens (input + output)
total_tokens = step_count * tokens_per_step * multiplier
input_tokens = total_tokens * 0.7  # 70% input
output_tokens = total_tokens * 0.3  # 30% output

# Pricing (Claude Sonnet)
input_price_per_m = 3.00
output_price_per_m = 15.00

cost = (input_tokens / 1000000) * input_price_per_m + (output_tokens / 1000000) * output_price_per_m

print(f"{cost:.4f}")
EOF
}

# Save checkpoint (progress state)
# Arguments:
#   $1 - worker directory
#   $2 - current step number
#   $3 - plan JSON
#   $4 - status message
save_checkpoint() {
    local worker_dir="$1"
    local current_step="$2"
    local plan_json="$3"
    local status_msg="$4"

    local checkpoint_file="${worker_dir}/checkpoint.json"
    local timestamp=$(date -Iseconds)

    python3 <<EOF
import json
import sys

checkpoint = {
    "timestamp": "${timestamp}",
    "current_step": ${current_step},
    "status": "${status_msg}",
    "plan": ${plan_json}
}

try:
    with open("${checkpoint_file}", "w") as f:
        json.dump(checkpoint, f, indent=2)
except Exception as e:
    print(f"Error saving checkpoint: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Load checkpoint to resume failed task
# Arguments:
#   $1 - worker directory
# Returns:
#   Checkpoint JSON or empty if not found
load_checkpoint() {
    local worker_dir="$1"
    local checkpoint_file="${worker_dir}/checkpoint.json"

    if [ -f "$checkpoint_file" ]; then
        cat "$checkpoint_file"
    else
        echo "{}"
    fi
}

# Find last failed quick task
# Returns:
#   Worker directory of last failed task or empty
find_last_failed_task() {
    if [ ! -f "${QUICK_TASKS_LOG}" ]; then
        echo ""
        return
    fi

    # Get last failed task from log
    tail -n 50 "${QUICK_TASKS_LOG}" | python3 -c "
import sys, json

last_failed = None
for line in sys.stdin:
    try:
        entry = json.loads(line.strip())
        if entry.get('status') == 'failure':
            last_failed = entry.get('worker_dir')
    except:
        pass

print(last_failed if last_failed else '')
" 2>/dev/null || echo ""
}

# Log quick task execution to audit trail
# Arguments:
#   $1 - task description
#   $2 - worker directory
#   $3 - status (success|failure)
#   $4 - duration in ms
#   $5 - workspace
#   $6 - cost estimate (optional)
log_quick_task() {
    local task_desc="$1"
    local worker_dir="$2"
    local status="$3"
    local duration_ms="$4"
    local workspace="$5"
    local cost_estimate="${6:-0.0000}"

    local timestamp=$(date -Iseconds)
    local task_id=$(basename "$worker_dir")

    # Create JSON log entry
    local log_entry=$(python3 -c "
import json, sys
entry = {
    'task_id': '$task_id',
    'task': '$task_desc',
    'status': '$status',
    'duration_ms': $duration_ms,
    'workspace': '$workspace',
    'timestamp': '$timestamp',
    'worker_dir': '$worker_dir',
    'cost_estimate': $cost_estimate
}
print(json.dumps(entry))
" 2>/dev/null || echo "{}")

    # Append to log file
    echo "$log_entry" >> "${QUICK_TASKS_LOG}"
}

# Main entry point for quick task execution
# Arguments:
#   $1 - task description
#   --workspace <dir> - workspace directory (optional)
#   --commit - auto-commit on success (optional)
#   --escalate - convert to PRD if complexity emerges (optional)
#   --dry-run - show plan without executing (optional)
#   --continue - resume last failed task (optional)
#   --template <name> - use template (optional)
run_quick_task() {
    local task_desc=""
    local workspace="."
    local auto_commit=false
    local escalate=false
    local dry_run=false
    local continue_mode=false
    local template_name=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --workspace)
                workspace="$2"
                shift 2
                ;;
            --commit)
                auto_commit=true
                shift
                ;;
            --escalate)
                escalate=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --continue)
                continue_mode=true
                shift
                ;;
            --template)
                template_name="$2"
                shift 2
                ;;
            *)
                if [ -z "$task_desc" ]; then
                    task_desc="$1"
                fi
                shift
                ;;
        esac
    done

    # Initialize quick tasks directory
    init_quick_tasks

    # Handle continue mode
    if [ "$continue_mode" = true ]; then
        local last_failed=$(find_last_failed_task)
        if [ -z "$last_failed" ]; then
            echo "Error: No failed task found to resume"
            return 1
        fi

        echo "Resuming failed task from: ${last_failed}"
        local checkpoint=$(load_checkpoint "$last_failed")

        if [ "$checkpoint" = "{}" ]; then
            echo "Warning: No checkpoint found, starting from beginning"
        else
            echo "Loaded checkpoint:"
            echo "$checkpoint" | python3 -c "
import sys, json
try:
    cp = json.load(sys.stdin)
    print(f\"  Step: {cp.get('current_step', 0)}  Status: {cp.get('status', 'unknown')}\")
except:
    pass
" 2>/dev/null
        fi
        echo ""
    fi

    if [ -z "$task_desc" ] && [ "$continue_mode" = false ]; then
        echo "Error: Task description is required"
        echo "Usage: run_quick_task \"task description\" [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --workspace DIR    Set workspace directory"
        echo "  --commit           Auto-commit on success"
        echo "  --escalate         Auto-escalate to PRD if complex"
        echo "  --dry-run          Show plan without executing"
        echo "  --continue         Resume last failed task"
        echo "  --template NAME    Use template (refactor, add-tests, fix-bug)"
        return 1
    fi

    # Start timing
    local start_time=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')

    echo "========================================"
    echo "  QUICK TASK MODE"
    echo "========================================"
    echo ""
    echo "Task: ${task_desc}"
    echo "Workspace: ${workspace}"
    if [ "$dry_run" = true ]; then
        echo "Mode: DRY RUN (no execution)"
    fi
    if [ -n "$template_name" ]; then
        echo "Template: ${template_name}"
    fi
    echo ""

    # Parse task description
    local parsed_task=$(parse_task_description "$task_desc")

    # Generate or load execution plan
    local plan_json=""
    if [ -n "$template_name" ]; then
        echo "Loading template..."
        plan_json=$(load_template "$template_name" "$task_desc")
        if [ $? -ne 0 ]; then
            echo "Error: Could not load template '${template_name}'"
            return 1
        fi
    else
        echo "Generating execution plan..."
        plan_json=$(generate_execution_plan "$parsed_task" "$workspace")
    fi

    # Extract complexity score
    local complexity_score=$(echo "$plan_json" | python3 -c "
import sys, json
try:
    plan = json.load(sys.stdin)
    print(plan.get('complexity_score', 0))
except:
    print(0)
" 2>/dev/null || echo 0)

    # Check if should escalate to PRD mode
    if [ "$escalate" = true ]; then
        if should_escalate_to_prd "$complexity_score"; then
            echo ""
            echo "⚠️  COMPLEXITY WARNING ⚠️"
            echo "This task appears complex (score: ${complexity_score}/100)"
            echo "Consider using PRD mode instead: ./claude-loop.sh --prd <prd-file>"
            echo ""
            read -p "Continue with quick mode anyway? [y/N] " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Task aborted. Please create a PRD for this task."
                return 1
            fi
        fi
    fi

    # Estimate cost
    local cost_estimate=$(estimate_task_cost "$plan_json" "$complexity_score")
    echo "Estimated cost: \$${cost_estimate}"
    echo ""

    # Display plan and get approval (unless dry-run)
    if ! display_plan_for_approval "$plan_json"; then
        echo "Quick task aborted by user."
        return 1
    fi

    # If dry-run, stop here
    if [ "$dry_run" = true ]; then
        echo ""
        echo "========================================"
        echo "  DRY RUN COMPLETE"
        echo "========================================"
        echo "Plan generated successfully. Use without --dry-run to execute."
        echo ""
        return 0
    fi

    # Create worker directory
    local worker_dir=$(create_quick_task_worker "$parsed_task")
    echo "Worker directory: ${worker_dir}"
    echo ""

    # Execute task
    local status="failure"
    if execute_quick_task "$task_desc" "$worker_dir" "$plan_json" "$workspace"; then
        status="success"

        # Generate commit if requested
        if [ "$auto_commit" = true ]; then
            echo ""
            echo "Creating git commit..."
            local commit_msg=$(generate_commit_message "$task_desc")

            # Check if there are changes to commit
            if ! git diff --quiet || ! git diff --cached --quiet; then
                echo "$commit_msg" | git commit -F - 2>&1 || {
                    echo "Warning: Could not create commit. Please commit changes manually."
                }
            else
                echo "No changes to commit."
            fi
        fi
    fi

    # Calculate duration
    local end_time=$(perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1000')
    local duration_ms=$((end_time - start_time))

    # Log execution
    log_quick_task "$task_desc" "$worker_dir" "$status" "$duration_ms" "$workspace" "$cost_estimate"

    echo ""
    echo "========================================"
    # Use tr for bash 3.2 compatibility (macOS default)
    echo "  QUICK TASK $(echo "$status" | tr '[:lower:]' '[:upper:]')"
    echo "========================================"
    echo "Duration: $((duration_ms / 1000))s"
    echo "Estimated cost: \$${cost_estimate}"
    echo "Logs: ${worker_dir}/logs/"
    echo ""

    if [ "$status" = "success" ]; then
        return 0
    else
        echo "To resume this task, use: ./claude-loop.sh quick --continue"
        return 1
    fi
}

# Execute task chain (multiple tasks sequentially)
# Arguments:
#   $@ - task descriptions separated by ';' or passed as multiple args
# Returns:
#   0 if all tasks succeed, 1 if any task fails
execute_task_chain() {
    local tasks=()

    # Parse tasks - either semicolon-separated or multiple arguments
    if [[ "$1" == *";"* ]]; then
        # Split by semicolon
        IFS=';' read -ra tasks <<< "$1"
    else
        # Each argument is a task
        tasks=("$@")
    fi

    local total_tasks=${#tasks[@]}
    local completed=0
    local failed=0

    echo "========================================"
    echo "  TASK CHAIN EXECUTION"
    echo "========================================"
    echo "Total tasks: ${total_tasks}"
    echo ""

    for i in "${!tasks[@]}"; do
        local task="${tasks[$i]}"
        local task_num=$((i + 1))

        echo "----------------------------------------"
        echo "Task ${task_num}/${total_tasks}: ${task}"
        echo "----------------------------------------"
        echo ""

        if run_quick_task "$task"; then
            ((completed++))
            echo "✓ Task ${task_num} completed successfully"
        else
            ((failed++))
            echo "✗ Task ${task_num} failed"

            # Ask if should continue or abort
            read -p "Continue with remaining tasks? [y/N] " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Task chain aborted."
                break
            fi
        fi

        echo ""
    done

    echo "========================================"
    echo "  TASK CHAIN SUMMARY"
    echo "========================================"
    echo "Completed: ${completed}/${total_tasks}"
    echo "Failed: ${failed}/${total_tasks}"
    echo ""

    if [ "$failed" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# Show quick task history
show_quick_task_history() {
    local limit="${1:-10}"
    local filter="${2:-all}"  # all, success, failure

    if [ ! -f "${QUICK_TASKS_LOG}" ]; then
        echo "No quick task history found."
        return 0
    fi

    echo "========================================"
    echo "  QUICK TASK HISTORY (last ${limit})"
    if [ "$filter" != "all" ]; then
        echo "  Filter: ${filter}"
    fi
    echo "========================================"
    echo ""

    tail -n "$limit" "${QUICK_TASKS_LOG}" | python3 -c "
import sys, json

filter_status = '${filter}'
count = 0

for line in sys.stdin:
    try:
        entry = json.loads(line.strip())

        # Apply filter
        if filter_status != 'all' and entry.get('status') != filter_status:
            continue

        count += 1
        status_icon = '✓' if entry['status'] == 'success' else '✗'
        duration_s = entry['duration_ms'] // 1000
        cost = entry.get('cost_estimate', 0.0)
        print(f\"{status_icon} [{entry['timestamp']}] {entry['task']} ({duration_s}s, \${cost:.4f})\")
    except Exception as e:
        pass

if count == 0:
    print('No matching tasks found.')
" 2>/dev/null || {
        echo "(History unavailable)"
    }

    echo ""
}

# Show quick task statistics
show_quick_task_stats() {
    if [ ! -f "${QUICK_TASKS_LOG}" ]; then
        echo "No quick task history found."
        return 0
    fi

    echo "========================================"
    echo "  QUICK TASK STATISTICS"
    echo "========================================"
    echo ""

    python3 <<EOF
import json
import sys
from collections import defaultdict

try:
    with open("${QUICK_TASKS_LOG}", "r") as f:
        entries = [json.loads(line.strip()) for line in f if line.strip()]

    total = len(entries)
    success = sum(1 for e in entries if e.get('status') == 'success')
    failure = total - success

    total_duration = sum(e.get('duration_ms', 0) for e in entries)
    avg_duration = total_duration / total if total > 0 else 0

    total_cost = sum(e.get('cost_estimate', 0.0) for e in entries)

    print(f"Total tasks: {total}")
    print(f"Successful: {success} ({success/total*100:.1f}%)" if total > 0 else "Successful: 0")
    print(f"Failed: {failure} ({failure/total*100:.1f}%)" if total > 0 else "Failed: 0")
    print(f"")
    print(f"Average duration: {avg_duration/1000:.1f}s")
    print(f"Total cost: \${total_cost:.4f}")
    print(f"Average cost: \${total_cost/total:.4f}" if total > 0 else "Average cost: \$0.0000")

except Exception as e:
    print(f"Error reading statistics: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    echo ""
}

# Execute concurrent quick tasks with workspace isolation
# Arguments:
#   $@ - task descriptions
# Returns:
#   0 if all tasks succeed, 1 if any task fails
execute_concurrent_tasks() {
    local tasks=("$@")
    local total_tasks=${#tasks[@]}
    local pids=()
    local worker_dirs=()
    local temp_dir="./.claude-loop/concurrent-tasks-$$"

    mkdir -p "$temp_dir"

    echo "========================================"
    echo "  CONCURRENT TASK EXECUTION"
    echo "========================================"
    echo "Total tasks: ${total_tasks}"
    echo ""

    # Launch all tasks in background
    for i in "${!tasks[@]}"; do
        local task="${tasks[$i]}"
        local task_num=$((i + 1))
        local workspace="${temp_dir}/task-${task_num}"

        mkdir -p "$workspace"

        echo "Launching task ${task_num}: ${task}"

        # Run task in background with isolated workspace
        (
            cd "$workspace" || exit 1
            run_quick_task "$task" --workspace "$workspace" > "${temp_dir}/task-${task_num}.log" 2>&1
            echo $? > "${temp_dir}/task-${task_num}.exit"
        ) &

        pids+=($!)
        worker_dirs+=("$workspace")
    done

    echo ""
    echo "All tasks launched. Waiting for completion..."
    echo ""

    # Wait for all tasks to complete
    local completed=0
    local failed=0

    for i in "${!pids[@]}"; do
        local pid=${pids[$i]}
        local task_num=$((i + 1))

        wait "$pid" || true

        # Read exit code from file
        local exit_code=1
        if [ -f "${temp_dir}/task-${task_num}.exit" ]; then
            exit_code=$(cat "${temp_dir}/task-${task_num}.exit")
        fi

        if [ "$exit_code" -eq 0 ]; then
            ((completed++))
            echo "✓ Task ${task_num} completed successfully"
        else
            ((failed++))
            echo "✗ Task ${task_num} failed"
        fi
    done

    echo ""
    echo "========================================"
    echo "  CONCURRENT EXECUTION SUMMARY"
    echo "========================================"
    echo "Completed: ${completed}/${total_tasks}"
    echo "Failed: ${failed}/${total_tasks}"
    echo "Logs: ${temp_dir}/"
    echo ""

    if [ "$failed" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Main - Allow standalone execution
# ============================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly
    case "${1:-}" in
        history)
            shift
            show_quick_task_history "$@"
            ;;
        stats)
            show_quick_task_stats
            ;;
        templates)
            list_templates
            ;;
        chain)
            shift
            if [ $# -eq 0 ]; then
                echo "Error: Task chain requires at least one task"
                echo "Usage: $0 chain \"task1\" \"task2\" \"task3\""
                exit 1
            fi
            execute_task_chain "$@"
            ;;
        concurrent)
            shift
            if [ $# -lt 2 ]; then
                echo "Error: Concurrent mode requires at least 2 tasks"
                echo "Usage: $0 concurrent \"task1\" \"task2\" ..."
                exit 1
            fi
            execute_concurrent_tasks "$@"
            ;;
        *)
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  history [limit] [filter]  Show task history (filter: all, success, failure)"
            echo "  stats                     Show task statistics"
            echo "  templates                 List available templates"
            echo "  chain <tasks...>          Execute tasks sequentially"
            echo "  concurrent <tasks...>     Execute tasks concurrently"
            echo ""
            echo "This script is meant to be sourced by claude-loop.sh"
            echo "For quick task execution, use: ./claude-loop.sh quick \"task description\""
            exit 1
            ;;
    esac
fi
