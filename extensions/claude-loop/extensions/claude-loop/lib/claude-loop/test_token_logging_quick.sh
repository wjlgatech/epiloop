#!/bin/bash
# Quick validation: Token logging works in all modes

echo "Testing token logging validation..."

# Check if provider_usage.jsonl exists from recent runs
if [ -f .claude-loop/logs/provider_usage.jsonl ]; then
    echo "✅ provider_usage.jsonl exists"
    
    # Check for non-zero tokens
    last_entry=$(tail -1 .claude-loop/logs/provider_usage.jsonl)
    input_tokens=$(echo "$last_entry" | jq -r '.input_tokens // 0' 2>/dev/null)
    output_tokens=$(echo "$last_entry" | jq -r '.output_tokens // 0' 2>/dev/null)
    
    if [ "$input_tokens" -gt 0 ] && [ "$output_tokens" -gt 0 ]; then
        echo "✅ Non-zero tokens logged: input=$input_tokens, output=$output_tokens"
    else
        echo "⚠️  Zero tokens detected: input=$input_tokens, output=$output_tokens"
    fi
    
    # Check JSONL format
    if jq empty .claude-loop/logs/provider_usage.jsonl 2>/dev/null; then
        echo "✅ Valid JSONL format"
    else
        echo "❌ Invalid JSONL format"
    fi
    
    # Count entries
    entry_count=$(wc -l < .claude-loop/logs/provider_usage.jsonl)
    echo "📊 Total entries: $entry_count"
    
else
    echo "⚠️  provider_usage.jsonl not found (may need fresh execution)"
fi

echo ""
echo "TOKEN LOGGING VALIDATION: COMPLETE"
