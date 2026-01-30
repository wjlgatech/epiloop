#!/usr/bin/env python3
"""
test-scaffolder skill - Generate test file structures from code

Analyzes source files and generates test scaffolding.
"""

import sys
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

class TestScaffolder:
    """Generates test file scaffolding from source code."""

    LANGUAGE_CONFIG: Dict[str, Dict[str, Any]] = {
        '.sh': {
            'framework': 'bash-test',
            'test_dir': 'tests',
            'test_suffix': '_test.sh',
            'function_pattern': r'^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)',
        },
        '.py': {
            'framework': 'pytest',
            'test_dir': 'tests',
            'test_prefix': 'test_',
            'test_suffix': '.py',
            'function_pattern': r'^(?:def|async def)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        },
        '.js': {
            'framework': 'jest',
            'test_dir': '.',
            'test_suffix': '.test.js',
            'function_pattern': r'(?:function|const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[=\(]',
        },
        '.ts': {
            'framework': 'jest',
            'test_dir': '.',
            'test_suffix': '.test.ts',
            'function_pattern': r'(?:function|const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[=\(]',
        },
    }

    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.functions: List[str] = []
        self.config: Optional[Dict[str, Any]] = None

    def detect_language(self) -> bool:
        """Detect language from file extension."""
        ext = self.source_path.suffix
        if ext in self.LANGUAGE_CONFIG:
            self.config = self.LANGUAGE_CONFIG[ext]
            return True
        else:
            print(f"Error: Unsupported file type '{ext}'")
            print(f"Supported types: {', '.join(self.LANGUAGE_CONFIG.keys())}")
            return False

    def extract_functions(self) -> bool:
        """Extract function names from source file."""
        if not self.config:
            raise RuntimeError("Config not initialized")

        try:
            with open(self.source_path, 'r') as f:
                content = f.read()

            pattern = self.config['function_pattern']
            matches = re.findall(pattern, content, re.MULTILINE)

            # Filter out common non-test functions
            self.functions = [
                func for func in matches
                if not func.startswith('_') or self.source_path.suffix == '.py'
            ]

            if not self.functions:
                print(f"Warning: No functions found in {self.source_path}")
                return False

            print(f"Found {len(self.functions)} function(s): {', '.join(self.functions[:5])}{'...' if len(self.functions) > 5 else ''}")
            return True

        except FileNotFoundError:
            print(f"Error: Source file not found: {self.source_path}")
            return False
        except Exception as e:
            print(f"Error reading source file: {e}")
            return False

    def generate_test_path(self) -> Path:
        """Generate test file path based on source file."""
        if not self.config:
            raise RuntimeError("Config not initialized")
        test_dir = Path(self.config['test_dir'])

        # Get relative path from project root
        rel_path = self.source_path.parent

        # Create test directory structure
        if self.config['test_dir'] == '.':
            # Same directory (JS/TS style)
            test_file_dir = rel_path
        else:
            # Separate test directory (Python/Shell style)
            test_file_dir = test_dir / rel_path

        # Generate test filename
        stem = self.source_path.stem
        if 'test_prefix' in self.config:
            test_filename = f"{self.config['test_prefix']}{stem}{self.config['test_suffix']}"
        else:
            test_filename = f"{stem}{self.config['test_suffix']}"

        return test_file_dir / test_filename

    def generate_bash_test(self) -> str:
        """Generate Bash test file content."""
        source_rel = self.source_path.as_posix()

        content = f"""#!/bin/bash
# Tests for {source_rel}

set -euo pipefail

# Source the file under test
source {source_rel}

"""

        for func in self.functions:
            content += f"""test_{func}() {{
    # Test {func} function
    # TODO: Add test implementation
    local result=$({func})
    assertEquals "Expected {func} to succeed" "0" "$?"
}}

"""

        content += """# Run tests with bash-test or shunit2
# Uncomment based on your test framework:
# . shunit2
# or simply run: bash this_file.sh
"""

        return content

    def generate_python_test(self) -> str:
        """Generate Python test file content."""
        source_rel = self.source_path.as_posix()
        module_path = source_rel.replace('/', '.').replace('.py', '')

        # Extract import names
        import_names = ', '.join(self.functions[:10])  # Limit to first 10
        if len(self.functions) > 10:
            import_names += ", ..."

        content = f'''"""Tests for {source_rel}"""

import pytest
from {module_path} import {import_names}


'''

        for func in self.functions:
            content += f'''def test_{func}():
    """Test {func} function."""
    # TODO: Add test implementation
    result = {func}()
    assert result is not None


'''

        content += '''# Pytest fixtures (if needed)
@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {{"key": "value"}}
'''

        return content

    def generate_javascript_test(self) -> str:
        """Generate JavaScript/TypeScript test file content."""
        source_rel = self.source_path.as_posix()

        content = f"""// Tests for {source_rel}

const {{ {', '.join(self.functions[:10])} }} = require('./{self.source_path.name}');

describe('{self.source_path.stem}', () => {{
"""

        for func in self.functions:
            content += f"""  test('{func} should work correctly', () => {{
    // TODO: Add test implementation
    const result = {func}();
    expect(result).toBeDefined();
  }});

"""

        content += """});
"""

        return content

    def generate_test_content(self) -> str:
        """Generate test file content based on language."""
        if self.source_path.suffix == '.sh':
            return self.generate_bash_test()
        elif self.source_path.suffix == '.py':
            return self.generate_python_test()
        elif self.source_path.suffix in ['.js', '.ts']:
            return self.generate_javascript_test()
        else:
            return "# Test content generation not implemented for this language\n"

    def write_test_file(self, test_path: Path, content: str) -> bool:
        """Write test file to disk."""
        if not self.config:
            raise RuntimeError("Config not initialized")

        try:
            # Create directory if it doesn't exist
            test_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists
            if test_path.exists():
                print(f"Warning: Test file already exists: {test_path}")
                print("Use --overwrite to replace it.")
                return False

            # Write test file
            with open(test_path, 'w') as f:
                f.write(content)

            # Make executable if shell script
            if test_path.suffix == '.sh':
                os.chmod(test_path, 0o755)

            print(f"\n✓ Test file generated: {test_path}")
            print(f"  Framework: {self.config['framework']}")
            print(f"  Test cases: {len(self.functions)}")
            print(f"\nNext steps:")
            print(f"  1. Review and customize the test file")
            print(f"  2. Add meaningful assertions")
            print(f"  3. Run the tests")

            return True

        except Exception as e:
            print(f"Error writing test file: {e}")
            return False

    def scaffold(self) -> bool:
        """Main scaffolding workflow."""
        print(f"Test Scaffolder v1.0")
        print("=" * 50)
        print(f"Source file: {self.source_path}")
        print()

        if not self.source_path.exists():
            print(f"Error: Source file does not exist: {self.source_path}")
            return False

        if not self.detect_language():
            return False

        if not self.extract_functions():
            return False

        test_path = self.generate_test_path()
        content = self.generate_test_content()

        return self.write_test_file(test_path, content)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: test-scaffolder <source_file>")
        print("Example: test-scaffolder lib/prd-parser.sh")
        sys.exit(2)

    source_path = sys.argv[1]

    scaffolder = TestScaffolder(source_path)
    success = scaffolder.scaffold()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
