#!/usr/bin/env python3
"""
Auto-Format Hook

Automatically formats code after story completion.
Supports Python (black, isort), JavaScript (prettier), and more.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

# Add lib to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lib'))

from hooks import HookContext, HookType, register_hook


class CodeFormatter:
    """Auto-format code based on file type."""

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize code formatter.

        Args:
            project_root: Root directory of project (defaults to current directory)
        """
        self.project_root = project_root or os.getcwd()

    def get_changed_files(self) -> List[str]:
        """Get list of changed files from git."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]

            return []

        except Exception as e:
            print(f"Failed to get changed files: {e}")
            return []

    def format_python_file(self, file_path: str) -> bool:
        """
        Format Python file with black and isort.

        Args:
            file_path: Path to Python file

        Returns:
            True if formatted successfully
        """
        success = True

        # Try black
        try:
            result = subprocess.run(
                ['black', file_path, '--quiet'],
                cwd=self.project_root,
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"Black formatting failed for {file_path}")
                success = False

        except FileNotFoundError:
            print("black not installed, skipping Python formatting")
            success = False
        except Exception as e:
            print(f"Black formatting error: {e}")
            success = False

        # Try isort
        try:
            result = subprocess.run(
                ['isort', file_path, '--quiet'],
                cwd=self.project_root,
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"isort failed for {file_path}")
                success = False

        except FileNotFoundError:
            # isort optional
            pass
        except Exception as e:
            print(f"isort error: {e}")

        return success

    def format_javascript_file(self, file_path: str) -> bool:
        """
        Format JavaScript/TypeScript file with prettier.

        Args:
            file_path: Path to JS/TS file

        Returns:
            True if formatted successfully
        """
        try:
            result = subprocess.run(
                ['npx', 'prettier', '--write', file_path],
                cwd=self.project_root,
                capture_output=True,
                timeout=10
            )

            if result.returncode == 0:
                return True
            else:
                print(f"Prettier formatting failed for {file_path}")
                return False

        except FileNotFoundError:
            print("prettier not installed, skipping JS formatting")
            return False
        except Exception as e:
            print(f"Prettier formatting error: {e}")
            return False

    def format_file(self, file_path: str) -> bool:
        """
        Format file based on extension.

        Args:
            file_path: Path to file

        Returns:
            True if formatted successfully
        """
        ext = Path(file_path).suffix.lower()

        if ext == '.py':
            return self.format_python_file(file_path)
        elif ext in ['.js', '.jsx', '.ts', '.tsx', '.json', '.css', '.html']:
            return self.format_javascript_file(file_path)
        else:
            # Unknown extension, skip
            return True

    def format_all_changed(self) -> int:
        """
        Format all changed files.

        Returns:
            Number of files formatted
        """
        changed_files = self.get_changed_files()

        if not changed_files:
            print("No changed files to format")
            return 0

        formatted_count = 0

        for file_path in changed_files:
            full_path = os.path.join(self.project_root, file_path)

            if not os.path.exists(full_path):
                continue

            print(f"Formatting: {file_path}")

            if self.format_file(full_path):
                formatted_count += 1

        return formatted_count


def auto_format_after_story(context: HookContext) -> HookContext:
    """
    Auto-format code after story completion.

    Hook: AFTER_STORY_COMPLETE
    Priority: 25 (run after other hooks)
    """
    try:
        print(f"\n=== Auto-formatting code for {context.story_id} ===")

        formatter = CodeFormatter()
        formatted_count = formatter.format_all_changed()

        print(f"Formatted {formatted_count} file(s)")

        # Add to context metadata
        context.update(formatted_files=formatted_count)

    except Exception as e:
        # Error isolation: don't fail the hook
        print(f"Auto-format hook failed: {e}")

    return context


def format_before_tool_call(context: HookContext) -> HookContext:
    """
    Format specific file before tool call (if it's a write operation).

    Hook: BEFORE_TOOL_CALL
    Priority: 30
    """
    try:
        # Only format on write operations
        if context.tool_name not in ['write_file', 'edit_file']:
            return context

        # Get file path from tool args
        if not context.tool_args:
            return context

        file_path = context.tool_args.get('file_path') or context.tool_args.get('path')

        if not file_path:
            return context

        print(f"Pre-formatting: {file_path}")

        formatter = CodeFormatter()
        formatter.format_file(file_path)

    except Exception as e:
        print(f"Pre-format hook failed: {e}")

    return context


# Register hooks when module is imported
if __name__ != "__main__":
    # Check if formatting tools are available
    has_formatters = False

    try:
        subprocess.run(['black', '--version'], capture_output=True, timeout=2)
        has_formatters = True
    except:
        pass

    if has_formatters:
        register_hook(HookType.AFTER_STORY_COMPLETE, auto_format_after_story, priority=25)
        print("Auto-format hook registered (after story completion)")

        # Optionally enable pre-formatting (can be noisy)
        if os.getenv('ENABLE_PRE_FORMAT') == 'true':
            register_hook(HookType.BEFORE_TOOL_CALL, format_before_tool_call, priority=30)
            print("Pre-format hook registered (before tool calls)")
    else:
        print("No code formatters found (black, prettier), skipping auto-format hooks")


# Example usage
if __name__ == "__main__":
    import tempfile

    print("Testing auto-format hooks...")

    # Create a test Python file with bad formatting
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
def badly_formatted(x,y,z):
    return x+y+z

class   BadlySpaced:
    def __init__(  self  ):
        pass
""")
        test_file = f.name

    print(f"\nCreated test file: {test_file}")
    print("Original content:")
    with open(test_file, 'r') as f:
        print(f.read())

    # Format it
    formatter = CodeFormatter()
    formatter.format_file(test_file)

    print("\nFormatted content:")
    with open(test_file, 'r') as f:
        print(f.read())

    # Clean up
    os.unlink(test_file)
    print("\nTest complete!")
