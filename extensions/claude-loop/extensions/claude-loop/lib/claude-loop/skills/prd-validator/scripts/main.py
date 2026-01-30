#!/usr/bin/env python3
"""
prd-validator skill - Validate PRD JSON files

Validates PRD structure, dependencies, and file scopes.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any

class PRDValidator:
    """Validates PRD JSON files for correctness and completeness."""

    def __init__(self, prd_path: str):
        self.prd_path = prd_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.prd_data: Dict[str, Any] = {}

    def load_prd(self) -> bool:
        """Load and parse PRD JSON file."""
        try:
            with open(self.prd_path, 'r') as f:
                self.prd_data = json.load(f)
            return True
        except FileNotFoundError:
            self.errors.append(f"PRD file not found: {self.prd_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error loading PRD: {e}")
            return False

    def validate_schema(self) -> bool:
        """Validate required top-level fields."""
        required_fields = ['project', 'branchName', 'description', 'userStories']

        for field in required_fields:
            if field not in self.prd_data:
                self.errors.append(f"Missing required field: '{field}'")

        # Validate userStories is a list
        if 'userStories' in self.prd_data:
            if not isinstance(self.prd_data['userStories'], list):
                self.errors.append("Field 'userStories' must be an array")
            elif len(self.prd_data['userStories']) == 0:
                self.warnings.append("PRD has no user stories")

        return len([e for e in self.errors if 'required field' in e or 'must be' in e]) == 0

    def validate_stories(self) -> bool:
        """Validate each user story structure."""
        if 'userStories' not in self.prd_data:
            return False

        required_story_fields = ['id', 'title', 'description', 'acceptanceCriteria', 'priority', 'passes']
        story_ids = set()

        for i, story in enumerate(self.prd_data['userStories']):
            story_id = story.get('id', f'Story#{i}')

            # Check required fields
            for field in required_story_fields:
                if field not in story:
                    self.errors.append(f"Story {story_id}: Missing required field '{field}'")

            # Validate ID uniqueness
            if 'id' in story:
                if story['id'] in story_ids:
                    self.errors.append(f"Duplicate story ID: {story['id']}")
                story_ids.add(story['id'])

            # Validate acceptanceCriteria is a list
            if 'acceptanceCriteria' in story:
                if not isinstance(story['acceptanceCriteria'], list):
                    self.errors.append(f"Story {story_id}: 'acceptanceCriteria' must be an array")
                elif len(story['acceptanceCriteria']) == 0:
                    self.warnings.append(f"Story {story_id}: No acceptance criteria defined")

            # Validate priority is a number
            if 'priority' in story:
                if not isinstance(story['priority'], (int, float)):
                    self.errors.append(f"Story {story_id}: 'priority' must be a number")
                elif story['priority'] > 10:
                    self.warnings.append(f"Story {story_id}: Priority value {story['priority']} is unusual (typically 1-5)")

            # Validate passes is a boolean
            if 'passes' in story:
                if not isinstance(story['passes'], bool):
                    self.errors.append(f"Story {story_id}: 'passes' must be a boolean")

            # Validate optional fields
            if 'estimatedComplexity' in story:
                valid_complexities = ['simple', 'medium', 'complex']
                if story['estimatedComplexity'] not in valid_complexities:
                    self.errors.append(
                        f"Story {story_id}: Invalid 'estimatedComplexity' value: '{story['estimatedComplexity']}'. "
                        f"Valid values: {', '.join(valid_complexities)}"
                    )

            if 'suggestedModel' in story:
                valid_models = ['haiku', 'sonnet', 'opus']
                if story['suggestedModel'] not in valid_models:
                    self.errors.append(
                        f"Story {story_id}: Invalid 'suggestedModel' value: '{story['suggestedModel']}'. "
                        f"Valid values: {', '.join(valid_models)}"
                    )

        return len([e for e in self.errors if 'Story' in e]) == 0

    def validate_dependencies(self) -> bool:
        """Validate story dependencies and check for circular dependencies."""
        if 'userStories' not in self.prd_data:
            return False

        # Build story ID set
        story_ids = {story['id'] for story in self.prd_data['userStories'] if 'id' in story}

        # Build dependency graph
        dep_graph: Dict[str, List[str]] = {}
        for story in self.prd_data['userStories']:
            story_id = story.get('id')
            if not story_id:
                continue

            dependencies = story.get('dependencies', [])
            if not isinstance(dependencies, list):
                self.errors.append(f"Story {story_id}: 'dependencies' must be an array")
                continue

            dep_graph[story_id] = dependencies

            # Check if referenced dependencies exist
            for dep_id in dependencies:
                if dep_id not in story_ids:
                    self.errors.append(f"Story {story_id}: Dependency '{dep_id}' does not exist")

        # Check for circular dependencies
        cycles = self._detect_cycles(dep_graph)
        if cycles:
            for cycle in cycles:
                cycle_str = ' -> '.join(cycle) + ' -> ' + cycle[0]
                self.errors.append(f"Circular dependency detected: {cycle_str}")

        return len([e for e in self.errors if 'dependency' in e.lower() or 'Circular' in e]) == 0

    def _detect_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Detect cycles in dependency graph using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:])

            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    def validate_file_scopes(self) -> bool:
        """Validate file scopes (soft warnings for non-existent files)."""
        if 'userStories' not in self.prd_data:
            return False

        base_path = Path(self.prd_path).parent

        for story in self.prd_data['userStories']:
            story_id = story.get('id', 'Unknown')
            file_scope = story.get('fileScope', [])

            if not isinstance(file_scope, list):
                self.errors.append(f"Story {story_id}: 'fileScope' must be an array")
                continue

            for file_path in file_scope:
                # Check if file exists (soft warning)
                full_path = base_path / file_path
                if not full_path.exists() and not any(glob_char in file_path for glob_char in ['*', '?', '**']):
                    self.warnings.append(f"Story {story_id}: File '{file_path}' in fileScope does not exist")

        return True

    def check_parallel_safety(self) -> bool:
        """Check if stories are safe for parallel execution."""
        if 'userStories' not in self.prd_data:
            return False

        # Build file scope map
        file_to_stories: Dict[str, List[str]] = {}

        for story in self.prd_data['userStories']:
            story_id = story.get('id', 'Unknown')
            file_scope = story.get('fileScope', [])

            for file_path in file_scope:
                if file_path not in file_to_stories:
                    file_to_stories[file_path] = []
                file_to_stories[file_path].append(story_id)

        # Check for overlapping file scopes
        for file_path, story_ids in file_to_stories.items():
            if len(story_ids) > 1:
                self.warnings.append(
                    f"File '{file_path}' is modified by multiple stories: {', '.join(story_ids)}. "
                    "These stories cannot be executed in parallel."
                )

        return True

    def validate(self) -> bool:
        """Run all validations."""
        if not self.load_prd():
            return False

        schema_valid = self.validate_schema()
        stories_valid = self.validate_stories()
        deps_valid = self.validate_dependencies()
        file_scopes_valid = self.validate_file_scopes()
        self.check_parallel_safety()

        return schema_valid and stories_valid and deps_valid and file_scopes_valid

    def print_report(self) -> None:
        """Print validation report."""
        print("PRD Validator v1.0")
        print("=" * 50)
        print()
        print(f"File: {self.prd_path}")

        if self.prd_data:
            print(f"Project: {self.prd_data.get('project', 'N/A')}")
            print(f"Branch: {self.prd_data.get('branchName', 'N/A')}")
            print(f"Stories: {len(self.prd_data.get('userStories', []))}")

        print()

        # Print validation results
        has_errors = len(self.errors) > 0
        has_warnings = len(self.warnings) > 0

        if has_errors:
            print("✗ VALIDATION FAILED")
            print()
            print("Errors:")
            for error in self.errors:
                print(f"  ✗ {error}")
            print()
        else:
            print("✓ VALIDATION PASSED")
            print()

        if has_warnings:
            print(f"⚠ Warnings: {len(self.warnings)}")
            print()
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
            print()

        # Summary
        if has_errors:
            print("Summary: PRD is INVALID")
        elif has_warnings:
            print("Summary: PRD is VALID with warnings")
        else:
            print("Summary: PRD is VALID")
        print()

def main():
    """Main entry point."""
    # Get PRD file path from arguments or use default
    if len(sys.argv) > 1:
        prd_path = sys.argv[1]
    else:
        prd_path = "prd.json"

    # Validate PRD
    validator = PRDValidator(prd_path)
    is_valid = validator.validate()

    # Print report
    validator.print_report()

    # Exit with appropriate code
    if not is_valid:
        sys.exit(1)
    elif len(validator.warnings) > 0:
        sys.exit(0)  # Still exit 0 for warnings
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
