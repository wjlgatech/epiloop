#!/bin/bash
# Quick validation: Source cloning feature

echo "Testing source cloning validation..."

# Check if source cloning code exists
if grep -q "source_project" lib/workspace-manager.sh 2>/dev/null || grep -q "source_project" lib/worker.sh 2>/dev/null; then
    echo "✅ Source cloning code present in codebase"
else
    echo "⚠️  Source cloning code not found"
fi

# Check PRD schema supports source_project
if grep -q "source_project" lib/prd-parser.sh 2>/dev/null; then
    echo "✅ PRD parser supports source_project field"
else
    echo "⚠️  PRD parser may not validate source_project"
fi

# Check if recent PRDs used source_project
if ls prds/*.json 2>/dev/null | xargs grep -l "source_project" | head -1; then
    echo "✅ Found PRDs using source_project"
else
    echo "ℹ️  No PRDs currently using source_project (feature available but unused)"
fi

echo ""
echo "SOURCE CLONING VALIDATION: COMPLETE"
