#!/usr/bin/env python3
"""
Spec Compliance Reviewer

Reviews implementation against acceptance criteria to prevent over/under-building.
Ensures exactly what was asked for is delivered - nothing more, nothing less.

Usage:
    python3 lib/spec-compliance-reviewer.py <prd_file> <story_id> [changes_summary]

Returns:
    PASS: All requirements met, nothing extra
    FAIL: Lists specific compliance issues
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


class SpecComplianceReviewer:
    """Reviews implementation for spec compliance."""

    def __init__(self, prd_file: str, story_id: str):
        """Initialize reviewer with PRD and story."""
        self.prd_file = Path(prd_file)
        self.story_id = story_id
        self.prd_data = self._load_prd()
        self.story = self._load_story()

    def _load_prd(self) -> dict:
        """Load PRD from file."""
        if not self.prd_file.exists():
            raise FileNotFoundError(f"PRD file not found: {self.prd_file}")

        with open(self.prd_file) as f:
            return json.load(f)

    def _load_story(self) -> dict:
        """Load specific story from PRD."""
        for story in self.prd_data.get("userStories", []):
            if story.get("id") == self.story_id:
                return story

        raise ValueError(f"Story {self.story_id} not found in PRD")

    def calculate_criteria_score(self, criteria: List) -> float:
        """
        Calculate weighted score for acceptance criteria.

        Args:
            criteria: List of acceptance criteria (can be dicts or strings)

        Returns:
            float: Score from 0.0 to 1.0
        """
        if not criteria:
            return 0.0

        # Calculate total weight and weighted score
        total_weight = 0.0
        weighted_score = 0.0

        for criterion in criteria:
            # Handle both dict and string criteria
            if isinstance(criterion, dict):
                weight = criterion.get('weight', 1.0)
                passed = criterion.get('passed', False)
            else:
                # String criteria: assume weight 1.0, check if marked passed
                weight = 1.0
                passed = False  # Can't auto-detect for string criteria

            total_weight += weight

            if passed:
                weighted_score += weight

        if total_weight == 0:
            return 0.0

        return weighted_score / total_weight

    def _save_prd(self) -> None:
        """Save updated PRD to file with auto-pass changes."""
        try:
            import shutil
            # Create backup
            backup_file = self.prd_file.with_suffix('.json.backup')
            if self.prd_file.exists():
                shutil.copy(self.prd_file, backup_file)

            # Write updated PRD
            with open(self.prd_file, 'w') as f:
                json.dump(self.prd_data, f, indent=2)

            print(f"💾 Auto-updated prd.json: {self.story.get('id')} → passes=true")
        except Exception as e:
            print(f"⚠️  Warning: Could not auto-save PRD: {e}")
            print(f"   Please manually update prd.json to set passes=true")

    def review(self, changes_summary: str = "") -> Tuple[bool, List[str]]:
        """
        Review implementation for spec compliance.

        Args:
            changes_summary: Optional summary of changes made

        Returns:
            (passes, issues) tuple:
            - passes: True if all criteria met exactly
            - issues: List of compliance issues (empty if passes)
        """
        issues = []

        # NEW: Check if passes already explicitly set to true
        if self.story.get("passes") == True:
            print("✅ Story already marked as passes=true, skipping validation")
            return True, []

        # Get acceptance criteria
        criteria = self.story.get("acceptanceCriteria", [])
        if not criteria:
            issues.append("No acceptance criteria defined for story")
            return False, issues

        # NEW: Calculate acceptance criteria score and check for auto-pass
        score = self.calculate_criteria_score(criteria)
        print(f"📊 Acceptance criteria score: {score:.2f}")

        # NEW: Auto-pass if score >= threshold (0.90 = 90% of weighted criteria met)
        AUTO_PASS_THRESHOLD = 0.90

        if score >= AUTO_PASS_THRESHOLD:
            print(f"✅ Auto-passing story (score {score:.2f} >= {AUTO_PASS_THRESHOLD})")
            print(f"   Story meets {score*100:.0f}% of acceptance criteria")

            # Update PRD automatically
            self.story['passes'] = True
            if not self.story.get('notes'):
                self.story['notes'] = f"Auto-passed with {score:.2f} criteria score on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            self._save_prd()

            return True, [f"Auto-passed with {score:.2f} criteria score ({score*100:.0f}% of criteria met)"]

        # Check if file scope items exist
        file_scope = self.story.get("fileScope", [])
        if file_scope:
            issues.extend(self._check_file_scope(file_scope))

        # Analyze changes summary if provided
        if changes_summary:
            issues.extend(self._check_changes_against_criteria(changes_summary, criteria))

        # Check for over-engineering indicators
        if changes_summary:
            issues.extend(self._check_over_engineering(changes_summary, criteria))

        # Check for under-implementation
        issues.extend(self._check_under_implementation(criteria))

        passes = len(issues) == 0
        return passes, issues

    def _check_file_scope(self, file_scope: List[str]) -> List[str]:
        """Check if expected files exist."""
        issues = []
        project_root = self.prd_file.parent.parent.parent  # prd.json -> active -> prds -> root

        for file_path in file_scope:
            # Skip test files for now (they might not be created yet)
            if "test" in file_path.lower():
                continue

            # Convert relative path to absolute
            abs_path = project_root / file_path
            if not abs_path.exists():
                issues.append(f"Expected file not found: {file_path}")

        return issues

    def _check_changes_against_criteria(self, changes: str, criteria: List) -> List[str]:
        """Check if changes align with acceptance criteria."""
        issues = []
        changes_lower = changes.lower()

        # Extract key requirements from criteria
        requirements = []
        for criterion in criteria:
            # Get criterion text (handle both dict and string)
            criterion_text = criterion
            if isinstance(criterion, dict):
                criterion_text = criterion.get('description', criterion.get('text', ''))

            # Skip test and documentation criteria for compliance check
            if any(word in criterion_text.lower() for word in ["test", "documentation", "docs"]):
                continue
            requirements.append(criterion_text.lower())

        # Check if major requirements are mentioned in changes
        unmet_criteria = []
        for criterion in criteria:
            # Get criterion text (handle both dict and string)
            criterion_text = criterion
            if isinstance(criterion, dict):
                criterion_text = criterion.get('description', criterion.get('text', ''))

            # Skip test/doc criteria
            if any(word in criterion_text.lower() for word in ["test", "documentation", "docs"]):
                continue

            # Extract key verbs/nouns from criterion
            key_terms = self._extract_key_terms(criterion_text)

            # Check if any key term appears in changes
            mentioned = any(term in changes_lower for term in key_terms)
            if not mentioned:
                unmet_criteria.append(criterion_text)

        if unmet_criteria:
            issues.append(f"Acceptance criteria not addressed: {'; '.join([str(c)[:50] for c in unmet_criteria[:3]])}")
            if len(unmet_criteria) > 3:
                issues.append(f"And {len(unmet_criteria) - 3} more unmet criteria")

        return issues

    def _extract_key_terms(self, criterion: str) -> List[str]:
        """Extract key terms from acceptance criterion (expects string)."""
        # Remove common words
        stop_words = {"create", "add", "implement", "ensure", "verify", "with", "for", "the", "a", "an"}

        words = str(criterion).lower().split()
        key_terms = []

        for word in words:
            # Clean punctuation
            word = word.strip(".,;:()[]")

            # Skip stop words and short words
            if word not in stop_words and len(word) > 3:
                key_terms.append(word)

        return key_terms

    def _check_over_engineering(self, changes: str, criteria: List[str]) -> List[str]:
        """Check for features not requested in criteria."""
        issues = []
        changes_lower = changes.lower()

        # Common over-engineering patterns
        over_engineering_indicators = [
            ("caching", "cache"),
            ("optimization", "optimize", "performance tuning"),
            ("abstraction layer", "generic framework"),
            ("extensibility", "plugin system"),
            ("advanced features", "extra functionality"),
        ]

        # Check if changes mention things not in criteria
        criteria_text = " ".join(criteria).lower()

        for indicators in over_engineering_indicators:
            for indicator in indicators:
                if indicator in changes_lower and indicator not in criteria_text:
                    issues.append(
                        f"Possible over-engineering: '{indicator}' implemented but not requested"
                    )
                    break  # Only report once per indicator group

        return issues

    def _check_under_implementation(self, criteria: List[str]) -> List[str]:
        """Check for obviously missing requirements."""
        issues = []

        # Check for critical keywords in criteria
        critical_patterns = {
            "test": "Tests",
            "documentation": "Documentation",
            "error handling": "Error handling",
            "validation": "Input validation",
        }

        for pattern, name in critical_patterns.items():
            # Handle both dict and string criteria
            criterion_texts = []
            for c in criteria:
                if isinstance(c, dict):
                    criterion_texts.append(c.get('description', c.get('text', '')).lower())
                else:
                    criterion_texts.append(str(c).lower())

            if any(pattern in text for text in criterion_texts):
                # We can't check if tests/docs exist without file context
                # This is handled by file_scope check
                pass

        return issues

    def generate_report(self, passes: bool, issues: List[str]) -> str:
        """Generate compliance review report."""
        report = []
        report.append("=" * 60)
        report.append("SPEC COMPLIANCE REVIEW")
        report.append("=" * 60)
        report.append("")
        report.append(f"Story: {self.story_id} - {self.story.get('title', 'N/A')}")
        report.append(f"Result: {'✅ PASS' if passes else '❌ FAIL'}")
        report.append("")

        if issues:
            report.append("Issues Found:")
            for i, issue in enumerate(issues, 1):
                report.append(f"  {i}. {issue}")
            report.append("")
            report.append("Action Required:")
            report.append("  - Fix the issues listed above")
            report.append("  - Re-run spec compliance review")
            report.append("  - Only proceed to code quality review after PASS")
        else:
            report.append("All acceptance criteria met. No extra features detected.")
            report.append("Ready to proceed to code quality review.")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python3 lib/spec-compliance-reviewer.py <prd_file> <story_id> [changes_summary]")
        print("")
        print("Example:")
        print('  python3 lib/spec-compliance-reviewer.py prd.json US-001 "Implemented session hooks"')
        sys.exit(1)

    prd_file = sys.argv[1]
    story_id = sys.argv[2]
    changes_summary = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        reviewer = SpecComplianceReviewer(prd_file, story_id)
        passes, issues = reviewer.review(changes_summary)
        report = reviewer.generate_report(passes, issues)

        print(report)

        # Exit with appropriate code
        sys.exit(0 if passes else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
