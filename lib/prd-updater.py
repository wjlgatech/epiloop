#!/usr/bin/env python3
"""
PRD Updater Tool

Safely update PRD files with story completion status.
Enhanced version with atomic writes, backups, and validation.

Usage:
    python3 lib/prd-updater.py mark-complete <prd_file> <story_id> [notes]
    python3 lib/prd-updater.py status <prd_file> <story_id>
    python3 lib/prd-updater.py list-incomplete <prd_file>

Examples:
    python3 lib/prd-updater.py mark-complete prd.json US-001 "Implemented all criteria"
    python3 lib/prd-updater.py status prd.json US-001
    python3 lib/prd-updater.py list-incomplete prd.json
"""

import json
import sys
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class PRDUpdater:
    """Safely update PRD files with atomic writes and backups."""

    def __init__(self, prd_file: str):
        """
        Initialize PRD updater.

        Args:
            prd_file: Path to PRD JSON file

        Raises:
            FileNotFoundError: If PRD file doesn't exist
        """
        self.prd_file = Path(prd_file)
        if not self.prd_file.exists():
            raise FileNotFoundError(f"PRD file not found: {prd_file}")

    def load_prd(self) -> Dict[str, Any]:
        """
        Load PRD from file.

        Returns:
            PRD dictionary

        Raises:
            json.JSONDecodeError: If PRD has invalid JSON
        """
        with open(self.prd_file, 'r') as f:
            return json.load(f)

    def save_prd(self, prd: Dict[str, Any]) -> None:
        """
        Save PRD to file with atomic write and backup.

        Uses temp file + rename for atomic operation.
        Creates backup before overwriting.

        Args:
            prd: PRD dictionary to save

        Raises:
            json.JSONDecodeError: If generated JSON is invalid
            IOError: If file operations fail
        """
        # Create backup of existing PRD
        backup_file = self.prd_file.with_suffix('.json.backup')
        if self.prd_file.exists():
            shutil.copy(self.prd_file, backup_file)
            print(f"💾 Created backup: {backup_file}")

        # Write to temp file first
        temp_file = self.prd_file.with_suffix('.json.tmp')
        with open(temp_file, 'w') as f:
            json.dump(prd, f, indent=2)

        # Validate temp file has valid JSON
        with open(temp_file, 'r') as f:
            try:
                json.load(f)  # Ensure valid JSON
            except json.JSONDecodeError as e:
                print(f"❌ Error: Generated JSON is corrupted, rolling back")
                os.remove(temp_file)
                raise e

        # Atomic rename (replaces original file)
        temp_file.rename(self.prd_file)

    def find_story(self, prd: Dict[str, Any], story_id: str) -> Optional[Dict[str, Any]]:
        """
        Find story by ID in PRD.

        Args:
            prd: PRD dictionary
            story_id: Story ID to find

        Returns:
            Story dictionary if found, None otherwise
        """
        for story in prd.get('userStories', []):
            if story.get('id') == story_id:
                return story
        return None

    def mark_complete(self, story_id: str, notes: str = "", commit_sha: str = "") -> bool:
        """
        Mark a story as complete.

        Args:
            story_id: Story ID to mark complete
            notes: Optional notes about completion
            commit_sha: Optional commit SHA

        Returns:
            True if successful, False otherwise
        """
        try:
            prd = self.load_prd()
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in PRD file: {e}")
            return False

        story = self.find_story(prd, story_id)

        if not story:
            print(f"❌ Error: Story {story_id} not found in PRD")
            return False

        # Check if already complete
        if story.get('passes') == True:
            print(f"ℹ️  Story {story_id} is already marked as complete")
            print(f"   Title: {story.get('title', 'N/A')}")
            print(f"   Notes: {story.get('notes', 'No notes')}")
            return True

        # Update story
        story['passes'] = True
        story['notes'] = notes or f"Completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        if commit_sha:
            story['implementationCommit'] = commit_sha

        # Save updated PRD
        try:
            self.save_prd(prd)
        except Exception as e:
            print(f"❌ Error: Failed to save PRD: {e}")
            return False

        print(f"✅ Story {story_id} marked as complete")
        print(f"   Title: {story.get('title', 'N/A')}")
        print(f"   Notes: {story['notes']}")
        if commit_sha:
            print(f"   Commit: {commit_sha}")

        return True

    def get_status(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a story.

        Args:
            story_id: Story ID to check

        Returns:
            Story dictionary if found, None otherwise
        """
        try:
            prd = self.load_prd()
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in PRD file: {e}")
            return None

        story = self.find_story(prd, story_id)

        if not story:
            print(f"❌ Error: Story {story_id} not found")
            return None

        # Print status
        print(f"📊 Story Status: {story['id']}")
        print(f"   Title: {story.get('title', 'N/A')}")
        print(f"   Passes: {'✅ Yes' if story.get('passes') else '❌ No'}")
        print(f"   Priority: {story.get('priority', 'N/A')}")
        print(f"   Notes: {story.get('notes', 'No notes')}")

        # Show acceptance criteria summary
        criteria = story.get('acceptanceCriteria', [])
        if criteria:
            print(f"   Criteria: {len(criteria)} defined")
            for i, criterion in enumerate(criteria, 1):
                if isinstance(criterion, dict):
                    desc = criterion.get('description', criterion.get('text', 'N/A'))
                    passed = criterion.get('passed', 'unknown')
                    status_icon = '✅' if passed == True else '❌' if passed == False else '❓'
                    print(f"     {i}. {status_icon} {desc[:60]}{'...' if len(desc) > 60 else ''}")
                else:
                    print(f"     {i}. {criterion}")

        return story

    def list_incomplete(self) -> None:
        """List all incomplete stories."""
        try:
            prd = self.load_prd()
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in PRD file: {e}")
            return

        incomplete = [s for s in prd.get('userStories', []) if not s.get('passes')]

        if not incomplete:
            print("✅ All stories complete!")
            return

        print(f"📋 {len(incomplete)} incomplete stories:")
        for story in sorted(incomplete, key=lambda s: s.get('priority', 999)):
            priority = story.get('priority', 'N/A')
            title = story.get('title', 'N/A')
            story_id = story.get('id', 'N/A')
            print(f"  [{priority}] {story_id}: {title}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 lib/prd-updater.py mark-complete <prd_file> <story_id> [notes]")
        print("  python3 lib/prd-updater.py status <prd_file> <story_id>")
        print("  python3 lib/prd-updater.py list-incomplete <prd_file>")
        print("")
        print("Examples:")
        print('  python3 lib/prd-updater.py mark-complete prd.json US-001 "Implemented all criteria"')
        print("  python3 lib/prd-updater.py status prd.json US-001")
        print("  python3 lib/prd-updater.py list-incomplete prd.json")
        sys.exit(1)

    command = sys.argv[1]

    if command == "mark-complete":
        if len(sys.argv) < 4:
            print("❌ Error: mark-complete requires prd_file and story_id")
            print("Usage: python3 lib/prd-updater.py mark-complete <prd_file> <story_id> [notes]")
            sys.exit(1)

        prd_file = sys.argv[2]
        story_id = sys.argv[3]
        notes = sys.argv[4] if len(sys.argv) > 4 else ""

        try:
            updater = PRDUpdater(prd_file)
            success = updater.mark_complete(story_id, notes)
            sys.exit(0 if success else 1)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)

    elif command == "status":
        if len(sys.argv) < 4:
            print("❌ Error: status requires prd_file and story_id")
            print("Usage: python3 lib/prd-updater.py status <prd_file> <story_id>")
            sys.exit(1)

        prd_file = sys.argv[2]
        story_id = sys.argv[3]

        try:
            updater = PRDUpdater(prd_file)
            result = updater.get_status(story_id)
            sys.exit(0 if result else 1)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)

    elif command == "list-incomplete":
        if len(sys.argv) < 3:
            print("❌ Error: list-incomplete requires prd_file")
            print("Usage: python3 lib/prd-updater.py list-incomplete <prd_file>")
            sys.exit(1)

        prd_file = sys.argv[2]

        try:
            updater = PRDUpdater(prd_file)
            updater.list_incomplete()
            sys.exit(0)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)

    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: mark-complete, status, list-incomplete")
        sys.exit(1)


if __name__ == "__main__":
    main()
