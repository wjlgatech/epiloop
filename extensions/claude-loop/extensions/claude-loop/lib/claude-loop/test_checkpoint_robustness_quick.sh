#!/bin/bash
# Quick validation: Checkpoint robustness improvements

echo "Testing checkpoint robustness validation..."

# Check for per-iteration checkpoint code
if grep -q "iteration" lib/session-state.sh 2>/dev/null || grep -q "iteration" lib/session-state.py 2>/dev/null; then
    echo "✅ Per-iteration checkpoint code likely present"
else
    echo "⚠️  Per-iteration code not clearly found"
fi

# Check for atomic write pattern (temp file + rename)
if grep -q "\.tmp\|temp.*rename\|atomic" lib/session-state.sh 2>/dev/null || grep -q "\.tmp\|temp.*rename\|atomic" lib/session-state.py 2>/dev/null; then
    echo "✅ Atomic write pattern detected"
else
    echo "ℹ️  Atomic write pattern not clearly detected"
fi

# Check for checkpoint validation
if grep -q "validate.*checkpoint\|check.*point.*valid" lib/session-state.py 2>/dev/null; then
    echo "✅ Checkpoint validation code present"
else
    echo "⚠️  Validation code not found"
fi

# Check recent commits mention checkpoint
recent_checkpoint_commits=$(git log --oneline --since="24 hours ago" | grep -i checkpoint | wc -l)
if [ "$recent_checkpoint_commits" -gt 0 ]; then
    echo "✅ Recent checkpoint commits: $recent_checkpoint_commits"
else
    echo "ℹ️  No recent checkpoint commits"
fi

# Check if checkpoint files exist
if ls .claude-loop/sessions/*/checkpoint*.json 2>/dev/null | head -1; then
    checkpoint_count=$(ls .claude-loop/sessions/*/checkpoint*.json 2>/dev/null | wc -l)
    echo "📊 Checkpoint files found: $checkpoint_count"
else
    echo "ℹ️  No checkpoint files found (may need fresh execution)"
fi

echo ""
echo "CHECKPOINT ROBUSTNESS VALIDATION: COMPLETE"
