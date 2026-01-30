#!/usr/bin/env python3
"""
Mark Story Complete Utility

Simple tool to mark a user story as complete in prd.json.
This prevents the common validation gap where Claude implements a story
but forgets to update the "passes" field.

Usage:
    python3 lib/mark-story-complete.py <prd_file> <story_id> [notes]

Example:
    python3 lib/mark-story-complete.py prd.json US-001 "Implemented in commit abc123"
    python3 lib/mark-story-complete.py prd.json US-002
"""

import sys
import json
from pathlib import Path
from datetime import datetime


def mark_story_complete(prd_file: str, story_id: str, notes: str = "") -> bool:
    """
    Mark a story as complete in PRD.

    Args:
        prd_file: Path to prd.json
        story_id: Story ID to mark complete (e.g., "US-001")
        notes: Optional notes about completion

    Returns:
        True if successful, False otherwise
    """
    prd_path = Path(prd_file)

    if not prd_path.exists():
        print(f"❌ Error: PRD file not found: {prd_file}", file=sys.stderr)
        return False

    # Load PRD
    try:
        with open(prd_path, 'r') as f:
            prd = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {prd_file}: {e}", file=sys.stderr)
        return False

    # Find and update story
    story_found = False
    for story in prd.get('userStories', []):
        if story.get('id') == story_id:
            story_found = True

            # Check if already complete
            if story.get('passes') == True:
                print(f"⚠️  Story {story_id} is already marked as complete")
                return True

            # Mark as complete
            story['passes'] = True

            # Add notes
            if notes:
                story['notes'] = notes
            elif 'notes' not in story or not story['notes']:
                story['notes'] = f"Completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            print(f"✅ Marked story {story_id} as complete: {story.get('title', 'N/A')}")
            print(f"   Notes: {story['notes']}")
            break

    if not story_found:
        print(f"❌ Error: Story {story_id} not found in PRD", file=sys.stderr)
        return False

    # Write updated PRD
    try:
        with open(prd_path, 'w') as f:
            json.dump(prd, f, indent=2)
        print(f"✅ Updated {prd_file}")
        return True
    except Exception as e:
        print(f"❌ Error: Failed to write PRD: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python3 lib/mark-story-complete.py <prd_file> <story_id> [notes]")
        print("")
        print("Example:")
        print('  python3 lib/mark-story-complete.py prd.json US-001 "Implemented in commit abc123"')
        print('  python3 lib/mark-story-complete.py prd.json US-002')
        sys.exit(1)

    prd_file = sys.argv[1]
    story_id = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else ""

    success = mark_story_complete(prd_file, story_id, notes)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
