#!/usr/bin/env python3
"""
commit-formatter skill - Format and validate commit messages

Enforces Conventional Commits specification.
"""

import sys
import re
from typing import Optional, List, Tuple

class CommitFormatter:
    """Formats and validates commit messages."""

    VALID_TYPES = [
        'feat', 'fix', 'docs', 'style', 'refactor',
        'perf', 'test', 'build', 'ci', 'chore', 'revert'
    ]

    COMMON_PATTERNS = {
        r'^add(ed|ing)?\s+(.+)': 'feat: add {}',
        r'^fix(ed|ing)?\s+(.+)': 'fix: {}',
        r'^update(d|ing)?\s+(.+)': 'docs: update {}',
        r'^remove(d|ing)?\s+(.+)': 'refactor: remove {}',
        r'^improve(d|ing)?\s+(.+)': 'refactor: improve {}',
        r'^clean(ed|ing)?\s+up\s+(.+)': 'chore: clean up {}',
    }

    def __init__(self, message: str):
        self.original_message = message
        self.formatted_message = message
        self.is_valid = False
        self.auto_corrected = False
        self.errors: List[str] = []
        self.recommendations: List[str] = []

    def parse_conventional_format(self) -> Optional[Tuple[str, Optional[str], str, bool]]:
        """Parse message as Conventional Commit format."""
        # Pattern: type(scope)!?: description
        pattern = r'^([a-z]+)(\([a-zA-Z0-9-]+\))?(!)?:\s*(.+)'
        match = re.match(pattern, self.original_message, re.MULTILINE)

        if match:
            commit_type = match.group(1)
            scope = match.group(2)  # includes parentheses
            breaking = match.group(3) == '!'
            description = match.group(4).strip()

            # Remove parentheses from scope
            if scope:
                scope = scope[1:-1]

            return (commit_type, scope, description, breaking)

        return None

    def validate_conventional_format(self) -> bool:
        """Validate if message follows Conventional Commits."""
        parsed = self.parse_conventional_format()

        if not parsed:
            self.errors.append("Message does not follow Conventional Commits format")
            return False

        commit_type, scope, description, breaking = parsed

        # Validate type
        if commit_type not in self.VALID_TYPES:
            self.errors.append(f"Invalid commit type: '{commit_type}'")
            self.errors.append(f"Valid types: {', '.join(self.VALID_TYPES)}")
            return False

        # Validate subject length
        subject = f"{commit_type}"
        if scope:
            subject += f"({scope})"
        if breaking:
            subject += "!"
        subject += f": {description}"

        if len(subject) > 72:
            self.recommendations.append(f"Subject line is {len(subject)} characters (recommend < 72)")

        # Check for imperative mood
        if description and description[0].islower():
            # Common non-imperative patterns
            if description.startswith(('added', 'fixed', 'updated', 'removed')):
                self.recommendations.append("Use imperative mood: 'add' not 'added'")

        # Check if description starts with capital letter
        if description and description[0].isupper():
            self.recommendations.append("Description should start with lowercase")

        # Suggest scope if missing
        if not scope:
            self.recommendations.append("Consider adding a scope: e.g., feat(auth): ...")

        self.is_valid = True
        return True

    def attempt_auto_correction(self) -> bool:
        """Attempt to auto-correct common formatting issues."""
        message = self.original_message.strip()

        # Try to match common patterns
        for pattern, template in self.COMMON_PATTERNS.items():
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                # Extract the description part
                if len(match.groups()) >= 2:
                    description = match.group(2).strip()
                else:
                    description = match.group(1).strip()

                # Ensure lowercase
                description = description[0].lower() + description[1:] if description else ""

                self.formatted_message = template.format(description)
                self.auto_corrected = True
                self.is_valid = True
                return True

        # If message starts with capital letter but no type, suggest feat
        if message and message[0].isupper():
            description = message[0].lower() + message[1:]
            self.formatted_message = f"feat: {description}"
            self.auto_corrected = True
            self.is_valid = True
            return True

        return False

    def format(self) -> bool:
        """Main formatting workflow."""
        # First try to validate as-is
        if self.validate_conventional_format():
            self.formatted_message = self.original_message
            return True

        # If invalid, try auto-correction
        if self.attempt_auto_correction():
            self.recommendations.append("Message was auto-corrected")
            return True

        # Could not correct
        self.errors.append("Unable to auto-correct message format")
        return False

    def print_report(self) -> None:
        """Print formatting report."""
        print("Commit Formatter v1.0")
        print("=" * 50)
        print()

        print("Original:")
        print(f"  {self.original_message}")
        print()

        if self.auto_corrected:
            print("Formatted:")
            print(f"  {self.formatted_message}")
            print()

        if self.is_valid:
            print("Status: ✓ VALID" + (" (auto-corrected)" if self.auto_corrected else ""))
        else:
            print("Status: ✗ INVALID")
        print()

        if self.errors:
            print("Errors:")
            for error in self.errors:
                print(f"  ✗ {error}")
            print()

        if self.recommendations:
            print("Recommendations:")
            for rec in self.recommendations:
                print(f"  ℹ {rec}")
            print()

    def get_formatted_message(self) -> str:
        """Get the formatted message."""
        return self.formatted_message if self.is_valid else self.original_message

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: commit-formatter <commit_message>")
        print('Example: commit-formatter "feat: add user authentication"')
        sys.exit(2)

    message = sys.argv[1]

    formatter = CommitFormatter(message)
    success = formatter.format()

    formatter.print_report()

    # Output formatted message
    if success:
        print("Formatted message:")
        print(formatter.get_formatted_message())

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
