#!/bin/bash

# Script to rename clawdbot to epiloop throughout the codebase

echo "🔄 Renaming clawdbot → epiloop throughout the codebase..."

# Find and replace in files (excluding build artifacts and dependencies)
find . -type f \
  -name "*.md" -o \
  -name "*.json" -o \
  -name "*.ts" -o \
  -name "*.tsx" -o \
  -name "*.js" -o \
  -name "*.jsx" -o \
  -name "*.yaml" -o \
  -name "*.yml" -o \
  -name "*.sh" -o \
  -name "*.txt" \
  2>/dev/null | while read -r file; do

  # Skip if file is in excluded directories
  if [[ "$file" =~ node_modules/ ]] || \
     [[ "$file" =~ /.git/ ]] || \
     [[ "$file" =~ /dist/ ]] || \
     [[ "$file" =~ /coverage/ ]] || \
     [[ "$file" =~ /.claude-loop/ ]] || \
     [[ "$file" =~ /lib/claude-loop/ ]]; then
    continue
  fi

  # Check if file contains "clawdbot" (case-insensitive)
  if grep -qi "clawdbot" "$file" 2>/dev/null; then
    echo "  Updating: $file"

    # Create backup
    cp "$file" "$file.bak"

    # Replace all variations (case-sensitive)
    sed -i '' \
      -e 's/clawdbot/epiloop/g' \
      -e 's/Clawdbot/Epiloop/g' \
      -e 's/CLAWDBOT/EPILOOP/g' \
      "$file"

    # Remove backup if successful
    if [ $? -eq 0 ]; then
      rm "$file.bak"
    else
      echo "  ⚠️  Failed to update $file, restoring backup"
      mv "$file.bak" "$file"
    fi
  fi
done

echo "✅ Renaming complete!"
echo ""
echo "📝 Summary of changes:"
git diff --stat
