#!/bin/bash
# Quick validation: Enhanced error diagnostics

echo "Testing error diagnostics validation..."

# Check if error capture code exists
if grep -q "stderr" lib/execution-logger.sh 2>/dev/null; then
    echo "✅ Error capture code present in execution-logger.sh"
else
    echo "⚠️  Error capture code not found"
fi

# Check for actionable suggestions code
if grep -q "suggestion\|Suggestion\|SUGGESTION" lib/worker.sh 2>/dev/null || grep -q "suggestion\|Suggestion" lib/execution-logger.sh 2>/dev/null; then
    echo "✅ Actionable suggestions code present"
else
    echo "⚠️  Suggestion code not found"
fi

# Check execution log for error types
if [ -f .claude-loop/execution_log.jsonl ]; then
    error_types=$(jq -r 'select(.error_type != null) | .error_type' .claude-loop/execution_log.jsonl 2>/dev/null | sort -u)
    if [ -n "$error_types" ]; then
        echo "✅ Error categorization working:"
        echo "$error_types" | sed 's/^/  - /'
    else
        echo "ℹ️  No errors logged recently (good or no recent runs)"
    fi
else
    echo "ℹ️  No execution log found"
fi

echo ""
echo "ERROR DIAGNOSTICS VALIDATION: COMPLETE"
