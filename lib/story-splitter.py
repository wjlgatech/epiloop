#!/usr/bin/env python3
"""
story-splitter.py - Adaptive Story Splitting with Claude-powered decomposition

Generates split proposals when story complexity exceeds thresholds.
Uses Claude to analyze complex stories and decompose into 2-4 sub-stories.

Usage:
    python3 lib/story-splitter.py propose <prd_path> <story_id> [--complexity-report <path>]
    python3 lib/story-splitter.py show-proposal <proposal_id>
    python3 lib/story-splitter.py approve <proposal_id>
    python3 lib/story-splitter.py reject <proposal_id> --reason "<reason>"
    python3 lib/story-splitter.py list-proposals

Workflow:
    1. complexity-monitor.sh detects high complexity
    2. story-splitter.py generates split proposal via Claude
    3. User reviews proposal in terminal
    4. User approves/rejects/edits/skips
    5. If approved, sub-stories are inserted into PRD
"""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Default paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CLAUDE_LOOP_DIR = PROJECT_ROOT / ".claude-loop"
PROPOSALS_DIR = CLAUDE_LOOP_DIR / "split-proposals"
PROPOSALS_LOG = CLAUDE_LOOP_DIR / "split-proposals.jsonl"


@dataclass
class SubStory:
    """A sub-story generated from splitting a complex story"""
    id: str  # e.g., "US-002A", "US-002B"
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    dependencies: list[str]  # Dependencies on other sub-stories
    fileScope: list[str]
    estimatedComplexity: str  # simple, medium, complex
    estimatedDuration: str  # e.g., "2-3 hours"
    passes: bool = False
    notes: str = ""


@dataclass
class SplitProposal:
    """A proposal to split a complex story into sub-stories"""
    proposal_id: str  # Generated hash
    story_id: str  # Original story ID
    prd_path: str  # Path to PRD file
    original_story: dict  # Original story data
    sub_stories: list[SubStory]
    rationale: str  # Why the split is recommended
    complexity_signals: dict  # Signals from complexity-monitor
    estimated_time_savings: str  # Expected benefit
    created_at: str
    status: str  # pending, approved, rejected, applied
    reviewed_at: Optional[str] = None
    reviewer_notes: Optional[str] = None


def load_prd(prd_path: Path) -> dict:
    """Load PRD JSON file"""
    try:
        with open(prd_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Failed to load PRD from {prd_path}: {e}", file=sys.stderr)
        sys.exit(1)


def save_prd(prd_path: Path, prd_data: dict, validate: bool = True) -> tuple[bool, Optional[Path], Optional[str]]:
    """Save PRD JSON file with atomic updates, file locking, backup, and validation

    Returns:
        tuple: (success: bool, backup_path: Optional[Path], error: Optional[str])
    """
    backup_path = None
    temp_file = None
    lock_file = None
    lock_file_path = None

    try:
        # Create backup first
        backup_dir = CLAUDE_LOOP_DIR / "prd-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"prd_backup_{timestamp}.json"

        if prd_path.exists():
            import shutil
            shutil.copy2(prd_path, backup_path)
            print(f"✓ Backup created: {backup_path}")

        # Acquire file lock to prevent race conditions
        lock_file_path = prd_path.with_suffix('.lock')
        lock_file = open(lock_file_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        # Write to temporary file first (atomic operation)
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=f"prd_tmp_{timestamp}_",
            suffix=".json",
            dir=prd_path.parent
        )

        try:
            with os.fdopen(temp_fd, 'w') as temp_f:
                json.dump(prd_data, temp_f, indent=2)

            # Validate the PRD if requested
            if validate:
                print("Validating updated PRD...")
                validation_result = validate_prd_file(Path(temp_path))
                if not validation_result[0]:
                    raise ValueError(f"PRD validation failed: {validation_result[1]}")
                print("✓ PRD validation passed")

            # Atomic rename (replace old file with new)
            os.replace(temp_path, prd_path)
            print(f"✓ PRD updated atomically")

            return True, backup_path, None

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        error_msg = f"Failed to save PRD: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return False, backup_path, error_msg

    finally:
        # Release lock
        if lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            # Clean up lock file
            if lock_file_path and lock_file_path.exists():
                lock_file_path.unlink()


def get_story_from_prd(prd_data: dict, story_id: str) -> Optional[dict]:
    """Extract a story from PRD by ID"""
    for story in prd_data.get('userStories', []):
        if story.get('id') == story_id:
            return story
    return None


def validate_prd_file(prd_path: Path) -> tuple[bool, str]:
    """Validate PRD using prd-validator skill or prd-parser

    Returns:
        tuple: (is_valid: bool, message: str)
    """
    # First try using prd-validator skill (from Phase 2)
    validator_skill = PROJECT_ROOT / "skills" / "prd-validator" / "scripts" / "validate.sh"
    if validator_skill.exists():
        try:
            result = subprocess.run(
                [str(validator_skill), str(prd_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, "PRD validation passed (prd-validator skill)"
            else:
                return False, f"PRD validation failed: {result.stderr}"
        except Exception as e:
            print(f"Warning: prd-validator skill failed: {e}", file=sys.stderr)

    # Fallback to prd-parser.sh validation
    prd_parser = PROJECT_ROOT / "lib" / "prd-parser.sh"
    if prd_parser.exists():
        try:
            result = subprocess.run(
                ['bash', '-c', f'source {prd_parser} && validate_prd {prd_path}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, "PRD validation passed (prd-parser)"
            else:
                return False, f"PRD validation failed: {result.stderr}"
        except Exception as e:
            return False, f"PRD validation error: {e}"

    # Basic JSON validation if no validator available
    try:
        with open(prd_path, 'r') as f:
            data = json.load(f)

        # Check required fields
        required = ['project', 'branchName', 'userStories']
        missing = [f for f in required if f not in data]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        # Check user stories structure
        stories = data.get('userStories', [])
        for i, story in enumerate(stories):
            story_required = ['id', 'title', 'priority']
            story_missing = [f for f in story_required if f not in story]
            if story_missing:
                return False, f"Story {i} missing fields: {', '.join(story_missing)}"

        return True, "PRD validation passed (basic)"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"


def rollback_prd(prd_path: Path, backup_path: Path) -> bool:
    """Rollback PRD to backup if update fails

    Returns:
        bool: True if rollback succeeded, False otherwise
    """
    try:
        if not backup_path or not backup_path.exists():
            print(f"Error: Backup file not found: {backup_path}", file=sys.stderr)
            return False

        import shutil
        shutil.copy2(backup_path, prd_path)
        print(f"✓ PRD rolled back to backup: {backup_path}")
        return True

    except Exception as e:
        print(f"Error: Rollback failed: {e}", file=sys.stderr)
        return False


def generate_proposal_id(story_id: str, timestamp: str) -> str:
    """Generate unique proposal ID"""
    content = f"{story_id}_{timestamp}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"SPLIT-{hash_digest.upper()}"


def load_complexity_report(report_path: Optional[Path]) -> dict:
    """Load complexity report from complexity-monitor"""
    if not report_path or not report_path.exists():
        return {
            "complexity_score": 0,
            "signals": {},
            "threshold": 7,
            "should_split": False
        }

    try:
        with open(report_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load complexity report: {e}", file=sys.stderr)
        return {}


def call_claude_for_split(story: dict, complexity_report: dict, prd_data: dict) -> dict:
    """Use Claude to generate split proposal"""

    # Build prompt for Claude
    prompt = f"""You are helping split a complex user story into smaller, manageable sub-stories.

## Original Story

**ID**: {story.get('id')}
**Title**: {story.get('title')}
**Description**: {story.get('description')}

**Acceptance Criteria**:
{chr(10).join(f"- {ac}" for ac in story.get('acceptanceCriteria', []))}

**File Scope**: {', '.join(story.get('fileScope', []))}
**Estimated Complexity**: {story.get('estimatedComplexity', 'unknown')}

## Complexity Signals

The complexity monitor detected the following signals:
- Complexity Score: {complexity_report.get('complexity_score', 'N/A')}/10
- Time overruns: {complexity_report.get('signals', {}).get('acceptance_criteria', {}).get('completed', 0)} AC completed
- File scope expansion: {complexity_report.get('signals', {}).get('file_scope', {}).get('files_outside_scope', 0)} files outside scope
- Error count: {complexity_report.get('signals', {}).get('errors', {}).get('count', 0)}
- Clarification requests: {complexity_report.get('signals', {}).get('clarifications', {}).get('count', 0)}

## Project Context

**Project**: {prd_data.get('project', 'Unknown')}
**Description**: {prd_data.get('description', 'No description')}

## Task

Please decompose this story into 2-4 smaller sub-stories. Each sub-story should:

1. Have a unique ID suffix (e.g., {story.get('id')}A, {story.get('id')}B, {story.get('id')}C)
2. Have a clear, focused title
3. Have a description following user story format: "As a [role], I want [feature] so that [benefit]"
4. Have 2-4 specific, testable acceptance criteria
5. Inherit appropriate file scope from the parent (refine if needed)
6. Have an estimated complexity (simple/medium/complex)
7. Have an estimated duration (e.g., "1-2 hours", "2-4 hours")
8. Have dependencies on previous sub-stories if needed (e.g., A→B→C)

**Important Guidelines**:
- Sub-stories should be implementable independently (after dependencies are met)
- Each sub-story should deliver incremental value
- The sum of sub-stories should equal the original story scope
- Avoid creating sub-stories that are too small (< 1 hour) or too large (> 4 hours)

Please return a JSON response in this EXACT format:

{{
  "rationale": "A clear explanation of why this split makes sense and how it addresses the complexity signals",
  "estimated_time_savings": "Expected benefit, e.g., '20% reduction in iteration time'",
  "sub_stories": [
    {{
      "id": "{story.get('id')}A",
      "title": "Sub-story title",
      "description": "User story description",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2"],
      "priority": 1,
      "dependencies": [],
      "fileScope": ["file1.py", "file2.py"],
      "estimatedComplexity": "simple",
      "estimatedDuration": "1-2 hours",
      "passes": false,
      "notes": ""
    }}
  ]
}}

Return ONLY the JSON, no other text."""

    # Call Claude via subprocess (using claude command line)
    try:
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        # Call Claude CLI
        result = subprocess.run(
            ['claude', '-m', 'sonnet', prompt_file],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Clean up temp file
        os.unlink(prompt_file)

        if result.returncode != 0:
            print(f"Error: Claude CLI failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse JSON response
        output = result.stdout.strip()

        # Extract JSON from Claude's response (may have surrounding text)
        # Look for { ... } pattern
        start = output.find('{')
        end = output.rfind('}') + 1
        if start == -1 or end == 0:
            print(f"Error: Could not find JSON in Claude's response", file=sys.stderr)
            print(f"Response: {output}", file=sys.stderr)
            sys.exit(1)

        json_str = output[start:end]
        return json.loads(json_str)

    except subprocess.TimeoutExpired:
        print("Error: Claude CLI timed out", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON from Claude: {e}", file=sys.stderr)
        print(f"Response: {output}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to call Claude: {e}", file=sys.stderr)
        sys.exit(1)


def save_proposal(proposal: SplitProposal):
    """Save split proposal to file and log"""
    # Ensure directories exist
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_LOOP_DIR.mkdir(parents=True, exist_ok=True)

    # Save proposal as JSON file
    proposal_path = PROPOSALS_DIR / f"{proposal.proposal_id}.json"
    with open(proposal_path, 'w') as f:
        json.dump(asdict(proposal), f, indent=2)

    # Append to JSONL log
    log_entry = {
        "timestamp": proposal.created_at,
        "proposal_id": proposal.proposal_id,
        "story_id": proposal.story_id,
        "status": proposal.status,
        "sub_story_count": len(proposal.sub_stories)
    }
    with open(PROPOSALS_LOG, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

    return proposal_path


def load_proposal(proposal_id: str) -> Optional[SplitProposal]:
    """Load a split proposal from file"""
    proposal_path = PROPOSALS_DIR / f"{proposal_id}.json"
    if not proposal_path.exists():
        return None

    try:
        with open(proposal_path, 'r') as f:
            data = json.load(f)

        # Convert sub_stories dicts back to SubStory objects
        sub_stories = [SubStory(**s) for s in data['sub_stories']]
        data['sub_stories'] = sub_stories

        return SplitProposal(**data)
    except Exception as e:
        print(f"Error: Failed to load proposal {proposal_id}: {e}", file=sys.stderr)
        return None


def update_proposal_status(proposal_id: str, status: str, reviewer_notes: Optional[str] = None):
    """Update proposal status"""
    proposal = load_proposal(proposal_id)
    if not proposal:
        print(f"Error: Proposal {proposal_id} not found", file=sys.stderr)
        sys.exit(1)

    proposal.status = status
    proposal.reviewed_at = datetime.now(timezone.utc).isoformat()
    if reviewer_notes:
        proposal.reviewer_notes = reviewer_notes

    # Save updated proposal
    save_proposal(proposal)


def display_proposal(proposal: SplitProposal):
    """Display split proposal in terminal with formatting"""
    print("\n" + "="*80)
    print("  ADAPTIVE STORY SPLITTING - Split Proposal")
    print("="*80)
    print(f"\nProposal ID: {proposal.proposal_id}")
    print(f"Original Story: {proposal.story_id}")
    print(f"Status: {proposal.status}")
    print(f"Created: {proposal.created_at}")

    print("\n" + "-"*80)
    print("  RATIONALE")
    print("-"*80)
    print(proposal.rationale)

    print("\n" + "-"*80)
    print("  COMPLEXITY SIGNALS")
    print("-"*80)
    signals = proposal.complexity_signals
    print(f"Complexity Score: {signals.get('complexity_score', 'N/A')}/10")
    print(f"Should Split: {signals.get('should_split', False)}")

    print("\n" + "-"*80)
    print("  ORIGINAL STORY")
    print("-"*80)
    orig = proposal.original_story
    print(f"ID: {orig.get('id')}")
    print(f"Title: {orig.get('title')}")
    print(f"Acceptance Criteria: {len(orig.get('acceptanceCriteria', []))} items")

    print("\n" + "-"*80)
    print(f"  PROPOSED SUB-STORIES ({len(proposal.sub_stories)} stories)")
    print("-"*80)

    for i, sub_story in enumerate(proposal.sub_stories, 1):
        print(f"\n{i}. {sub_story.id}: {sub_story.title}")
        print(f"   Description: {sub_story.description}")
        print(f"   Complexity: {sub_story.estimatedComplexity} | Duration: {sub_story.estimatedDuration}")
        print(f"   Acceptance Criteria ({len(sub_story.acceptanceCriteria)}):")
        for ac in sub_story.acceptanceCriteria:
            print(f"      - {ac}")
        if sub_story.dependencies:
            print(f"   Dependencies: {', '.join(sub_story.dependencies)}")

    print("\n" + "-"*80)
    print("  EXPECTED BENEFITS")
    print("-"*80)
    print(proposal.estimated_time_savings)

    print("\n" + "="*80)


def interactive_review(proposal: SplitProposal) -> str:
    """Interactive checkpoint prompt for proposal review"""
    display_proposal(proposal)

    print("\n" + "="*80)
    print("  REVIEW OPTIONS")
    print("="*80)
    print("  [a] Approve - Accept this split and insert sub-stories into PRD")
    print("  [r] Reject - Reject this split and continue with original story")
    print("  [e] Edit - Open sub-stories in $EDITOR for manual editing")
    print("  [s] Skip - Skip for now, decide later")
    print("="*80)

    while True:
        choice = input("\nYour choice [a/r/e/s]: ").lower().strip()
        if choice in ['a', 'r', 'e', 's']:
            return choice
        print("Invalid choice. Please enter a, r, e, or s.")


def edit_proposal_in_editor(proposal: SplitProposal) -> SplitProposal:
    """Open proposal in $EDITOR for manual editing"""
    editor = os.environ.get('EDITOR', 'vim')

    # Create temp file with sub-stories as JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Write editable content
        editable_data = {
            "rationale": proposal.rationale,
            "estimated_time_savings": proposal.estimated_time_savings,
            "sub_stories": [asdict(s) for s in proposal.sub_stories]
        }
        json.dump(editable_data, f, indent=2)
        temp_path = f.name

    # Open in editor
    subprocess.run([editor, temp_path])

    # Read edited content
    with open(temp_path, 'r') as f:
        edited_data = json.load(f)

    # Clean up temp file
    os.unlink(temp_path)

    # Update proposal
    proposal.rationale = edited_data.get('rationale', proposal.rationale)
    proposal.estimated_time_savings = edited_data.get('estimated_time_savings', proposal.estimated_time_savings)
    proposal.sub_stories = [SubStory(**s) for s in edited_data.get('sub_stories', [])]

    return proposal


def apply_split_to_prd(proposal: SplitProposal) -> bool:
    """Insert sub-stories into PRD with atomic updates, validation, and rollback

    Returns:
        bool: True if split applied successfully, False otherwise
    """
    prd_path = Path(proposal.prd_path)
    prd_data = load_prd(prd_path)
    backup_path = None

    try:
        # Find index of original story
        stories = prd_data.get('userStories', [])
        original_index = None
        for i, story in enumerate(stories):
            if story.get('id') == proposal.story_id:
                original_index = i
                break

        if original_index is None:
            print(f"Error: Original story {proposal.story_id} not found in PRD", file=sys.stderr)
            return False

        # Mark original story as 'split' (not completed, but replaced)
        original_story = stories[original_index]
        original_story['notes'] = f"Split into {len(proposal.sub_stories)} sub-stories: {', '.join(s.id for s in proposal.sub_stories)}. See proposal {proposal.proposal_id}."
        original_story['split'] = True  # Special flag
        original_story['split_proposal_id'] = proposal.proposal_id
        # Don't mark as passes=true, keep it False to indicate it was split

        # Insert sub-stories after original story
        sub_stories_dicts = [asdict(s) for s in proposal.sub_stories]

        # Update dependencies: first sub-story depends on original story's dependencies
        # Subsequent sub-stories depend on previous sub-story (chain: A→B→C)
        if sub_stories_dicts:
            # First sub-story inherits original dependencies
            first_sub = sub_stories_dicts[0]
            first_sub['dependencies'] = original_story.get('dependencies', [])

            # Subsequent sub-stories depend on previous sub-story
            for i in range(1, len(sub_stories_dicts)):
                prev_sub_id = sub_stories_dicts[i-1]['id']
                sub_stories_dicts[i]['dependencies'] = [prev_sub_id]

        # Insert sub-stories after original story
        stories[original_index+1:original_index+1] = sub_stories_dicts

        # Update PRD metadata
        prd_data['userStories'] = stories

        # Update story count metadata
        total_stories = len(stories)
        prd_data['totalStories'] = total_stories

        # Update complexity metadata if present
        if 'complexity' in prd_data:
            # Recalculate complexity based on sub-stories
            complexity_sum = sum(
                {'simple': 1, 'medium': 2, 'complex': 3}.get(s.get('estimatedComplexity', 'medium'), 2)
                for s in sub_stories_dicts
            )
            # Map back to 0-4 scale (simple complexity heuristic)
            prd_data['complexity'] = min(4, complexity_sum // len(sub_stories_dicts) + 1)

        # Save updated PRD with atomic updates, validation, and backup
        print("\nApplying split to PRD...")
        success, backup_path, error = save_prd(prd_path, prd_data, validate=True)

        if not success:
            print(f"Error: Failed to apply split: {error}", file=sys.stderr)
            if backup_path:
                print("Attempting rollback...", file=sys.stderr)
                rollback_prd(prd_path, backup_path)
            return False

        print(f"\n✓ Split applied successfully!")
        print(f"  - Original story {proposal.story_id} marked as 'split'")
        print(f"  - {len(proposal.sub_stories)} sub-stories inserted")
        print(f"  - Dependencies updated: {sub_stories_dicts[0]['id']} → {sub_stories_dicts[1]['id'] if len(sub_stories_dicts) > 1 else 'none'}")
        print(f"  - Total stories in PRD: {total_stories}")
        print(f"  - Next story to execute: {proposal.sub_stories[0].id}")
        print(f"  - Backup location: {backup_path}")

        return True

    except Exception as e:
        print(f"Error: Exception during split application: {e}", file=sys.stderr)
        if backup_path:
            print("Attempting rollback...", file=sys.stderr)
            rollback_prd(prd_path, backup_path)
        return False


def cmd_propose(args):
    """Generate a split proposal for a complex story"""
    prd_path = Path(args.prd_path)
    if not prd_path.exists():
        print(f"Error: PRD not found: {prd_path}", file=sys.stderr)
        sys.exit(1)

    # Load PRD
    prd_data = load_prd(prd_path)

    # Get story
    story = get_story_from_prd(prd_data, args.story_id)
    if not story:
        print(f"Error: Story {args.story_id} not found in PRD", file=sys.stderr)
        sys.exit(1)

    # Load complexity report
    complexity_report_path = Path(args.complexity_report) if args.complexity_report else None
    complexity_report = load_complexity_report(complexity_report_path)

    # Generate proposal using Claude
    print(f"Generating split proposal for {args.story_id}...")
    print("Calling Claude for analysis...")

    claude_response = call_claude_for_split(story, complexity_report, prd_data)

    # Create proposal object
    timestamp = datetime.now(timezone.utc).isoformat()
    proposal_id = generate_proposal_id(args.story_id, timestamp)

    sub_stories = [SubStory(**s) for s in claude_response['sub_stories']]

    proposal = SplitProposal(
        proposal_id=proposal_id,
        story_id=args.story_id,
        prd_path=str(prd_path.absolute()),
        original_story=story,
        sub_stories=sub_stories,
        rationale=claude_response['rationale'],
        complexity_signals=complexity_report,
        estimated_time_savings=claude_response['estimated_time_savings'],
        created_at=timestamp,
        status='pending'
    )

    # Save proposal
    proposal_path = save_proposal(proposal)
    print(f"\n✓ Split proposal generated: {proposal_id}")
    print(f"  Saved to: {proposal_path}")

    # Interactive review (if --interactive flag)
    if not args.json:
        choice = interactive_review(proposal)

        if choice == 'a':
            # Approve and apply
            update_proposal_status(proposal_id, 'approved')
            if apply_split_to_prd(proposal):
                update_proposal_status(proposal_id, 'applied')
            else:
                print(f"\n✗ Failed to apply split. Proposal remains approved but not applied.", file=sys.stderr)
                sys.exit(1)

        elif choice == 'r':
            # Reject
            reason = input("Rejection reason: ").strip()
            update_proposal_status(proposal_id, 'rejected', reason)
            print(f"\n✓ Proposal {proposal_id} rejected")

        elif choice == 'e':
            # Edit
            edited_proposal = edit_proposal_in_editor(proposal)
            save_proposal(edited_proposal)
            print(f"\n✓ Proposal edited and saved")

            # Ask again after editing
            choice = interactive_review(edited_proposal)
            if choice == 'a':
                update_proposal_status(proposal_id, 'approved')
                if apply_split_to_prd(edited_proposal):
                    update_proposal_status(proposal_id, 'applied')
                else:
                    print(f"\n✗ Failed to apply edited split.", file=sys.stderr)
                    sys.exit(1)

        elif choice == 's':
            # Skip
            print(f"\n✓ Proposal {proposal_id} saved for later review")

    # JSON output
    if args.json:
        print(json.dumps(asdict(proposal), indent=2))


def cmd_show_proposal(args):
    """Show a split proposal"""
    proposal = load_proposal(args.proposal_id)
    if not proposal:
        print(f"Error: Proposal {args.proposal_id} not found", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(asdict(proposal), indent=2))
    else:
        display_proposal(proposal)


def cmd_approve(args):
    """Approve a split proposal"""
    proposal = load_proposal(args.proposal_id)
    if not proposal:
        print(f"Error: Proposal {args.proposal_id} not found", file=sys.stderr)
        sys.exit(1)

    update_proposal_status(args.proposal_id, 'approved')
    if apply_split_to_prd(proposal):
        update_proposal_status(args.proposal_id, 'applied')
        print(f"\n✓ Proposal {args.proposal_id} applied successfully")
    else:
        print(f"\n✗ Failed to apply proposal {args.proposal_id}", file=sys.stderr)
        sys.exit(1)


def cmd_reject(args):
    """Reject a split proposal"""
    update_proposal_status(args.proposal_id, 'rejected', args.reason)
    print(f"✓ Proposal {args.proposal_id} rejected")


def cmd_list_proposals(args):
    """List all split proposals"""
    if not PROPOSALS_DIR.exists():
        print("No proposals found.")
        return

    proposals = []
    for proposal_file in PROPOSALS_DIR.glob("SPLIT-*.json"):
        proposal = load_proposal(proposal_file.stem)
        if proposal:
            proposals.append(proposal)

    if not proposals:
        print("No proposals found.")
        return

    # Sort by created_at (newest first)
    proposals.sort(key=lambda p: p.created_at, reverse=True)

    if args.json:
        output = [asdict(p) for p in proposals]
        print(json.dumps(output, indent=2))
    else:
        print(f"\nFound {len(proposals)} split proposal(s):\n")
        print(f"{'ID':<15} {'Story':<10} {'Status':<12} {'Sub-Stories':<12} {'Created':<20}")
        print("-" * 80)
        for p in proposals:
            print(f"{p.proposal_id:<15} {p.story_id:<10} {p.status:<12} {len(p.sub_stories):<12} {p.created_at[:19]}")


def main():
    parser = argparse.ArgumentParser(description="Adaptive Story Splitter - Claude-powered split proposals")
    parser.add_argument('--json', action='store_true', help="Output as JSON")

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # propose command
    propose_parser = subparsers.add_parser('propose', help='Generate split proposal for a story')
    propose_parser.add_argument('prd_path', help='Path to PRD file')
    propose_parser.add_argument('story_id', help='Story ID to split')
    propose_parser.add_argument('--complexity-report', help='Path to complexity report JSON')

    # show-proposal command
    show_parser = subparsers.add_parser('show-proposal', help='Show a split proposal')
    show_parser.add_argument('proposal_id', help='Proposal ID')

    # approve command
    approve_parser = subparsers.add_parser('approve', help='Approve and apply a split proposal')
    approve_parser.add_argument('proposal_id', help='Proposal ID')

    # reject command
    reject_parser = subparsers.add_parser('reject', help='Reject a split proposal')
    reject_parser.add_argument('proposal_id', help='Proposal ID')
    reject_parser.add_argument('--reason', required=True, help='Rejection reason')

    # list-proposals command
    list_parser = subparsers.add_parser('list-proposals', help='List all split proposals')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handlers
    if args.command == 'propose':
        cmd_propose(args)
    elif args.command == 'show-proposal':
        cmd_show_proposal(args)
    elif args.command == 'approve':
        cmd_approve(args)
    elif args.command == 'reject':
        cmd_reject(args)
    elif args.command == 'list-proposals':
        cmd_list_proposals(args)


if __name__ == '__main__':
    main()
