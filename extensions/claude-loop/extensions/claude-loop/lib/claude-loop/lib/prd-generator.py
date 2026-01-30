#!/usr/bin/env python3
"""
prd-generator.py - Dynamic PRD Generation from Natural Language

Generates complete PRD with user stories from high-level project goals.
Uses Claude to analyze goals and decompose into implementable user stories.

Usage:
    python3 lib/prd-generator.py generate "Add user auth with JWT"
    python3 lib/prd-generator.py generate "Build GraphQL API" --output prd-custom.json
    python3 lib/prd-generator.py generate --input goal.txt --codebase-analysis
    python3 lib/prd-generator.py validate prd-output.json

Features:
    - Goal analysis: Identify requirements, constraints, domain
    - Story decomposition: Generate 5-10 focused user stories
    - Dependency inference: Determine logical story execution order
    - File scope estimation: Analyze codebase to predict file changes
    - Complexity calculation: Use complexity-detector.py for project level
    - Branch naming: Generate feature branch names
    - Validation: Validate generated PRD structure
"""

import argparse
import glob
import hashlib
import json
import os
import re
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
COMPLEXITY_DETECTOR = SCRIPT_DIR / "complexity-detector.py"


@dataclass
class UserStory:
    """A user story in the PRD"""
    id: str
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    dependencies: list[str]
    fileScope: list[str]
    estimatedComplexity: str  # simple, medium, complex
    passes: bool = False
    notes: str = ""


@dataclass
class PRDDocument:
    """Complete PRD document"""
    project: str
    branchName: str
    description: str
    userStories: list[UserStory]
    complexity: int  # 0-4 from complexity-detector
    estimatedDuration: str
    successMetrics: dict


def kebab_case(text: str) -> str:
    """Convert text to kebab-case for branch names"""
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')


def call_claude(prompt: str, model: str = "sonnet", timeout: int = 120) -> str:
    """Call Claude CLI with prompt and return response

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (haiku, sonnet, opus)
        timeout: Timeout in seconds

    Returns:
        Claude's response as string
    """
    try:
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        # Call Claude CLI
        result = subprocess.run(
            ['claude', '-m', model, prompt_file],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Clean up temp file
        os.unlink(prompt_file)

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        if os.path.exists(prompt_file):
            os.unlink(prompt_file)
        raise TimeoutError(f"Claude CLI timed out after {timeout}s")
    except Exception as e:
        if os.path.exists(prompt_file):
            os.unlink(prompt_file)
        raise


def extract_json_from_response(response: str) -> dict:
    """Extract JSON object from Claude's response

    Claude may return text + JSON, so we need to find the JSON part.
    """
    # Look for { ... } pattern
    start = response.find('{')
    end = response.rfind('}') + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found in response")

    json_str = response[start:end]
    return json.loads(json_str)


def analyze_codebase_structure() -> dict:
    """Analyze codebase to understand structure and common patterns

    Returns:
        dict with codebase metadata: languages, directories, patterns
    """
    structure = {
        "languages": set(),
        "directories": set(),
        "file_patterns": {},
        "total_files": 0
    }

    # Scan for common programming language file extensions
    extensions = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript-react',
        '.jsx': 'javascript-react',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.sh': 'shell',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
    }

    try:
        # Find files (limit to 1000 for performance)
        for ext, lang in extensions.items():
            pattern = str(PROJECT_ROOT / f"**/*{ext}")
            files = list(Path(PROJECT_ROOT).glob(f"**/*{ext}"))[:1000]

            if files:
                structure["languages"].add(lang)
                structure["file_patterns"][ext] = len(files)
                structure["total_files"] += len(files)

                # Extract directories
                for f in files:
                    rel_path = f.relative_to(PROJECT_ROOT)
                    if len(rel_path.parts) > 1:
                        structure["directories"].add(str(rel_path.parts[0]))

        # Convert sets to lists for JSON serialization
        structure["languages"] = list(structure["languages"])
        structure["directories"] = list(structure["directories"])

        return structure

    except Exception as e:
        print(f"Warning: Codebase analysis failed: {e}", file=sys.stderr)
        return structure


def estimate_file_scopes_from_codebase(stories: list[dict], codebase_structure: dict) -> list[dict]:
    """Estimate file scopes for stories based on codebase structure

    Uses story titles and descriptions to predict which files will be modified.
    """
    for story in stories:
        title = story.get('title', '').lower()
        description = story.get('description', '').lower()
        text = f"{title} {description}"

        predicted_scope = []

        # Match against known directories
        for directory in codebase_structure.get('directories', []):
            if directory.lower() in text or any(keyword in text for keyword in [
                'test' if directory == 'tests' else '',
                'doc' if directory == 'docs' else '',
                'lib' if directory == 'lib' else '',
                'src' if directory == 'src' else '',
            ]):
                # Predict file patterns in that directory
                for ext, count in codebase_structure.get('file_patterns', {}).items():
                    if count > 0:
                        predicted_scope.append(f"{directory}/*{ext}")
                        break  # Only add one pattern per directory

        # If no scope predicted, use generic patterns
        if not predicted_scope:
            # Default to common patterns based on primary language
            languages = codebase_structure.get('languages', [])
            if 'python' in languages:
                predicted_scope = ['lib/*.py', 'tests/*.py']
            elif 'typescript' in languages or 'javascript' in languages:
                predicted_scope = ['src/*.ts', 'tests/*.ts']
            elif 'go' in languages:
                predicted_scope = ['*.go', '*_test.go']
            else:
                predicted_scope = ['**/*']

        story['fileScope'] = predicted_scope

    return stories


def infer_dependencies(stories: list[dict]) -> list[dict]:
    """Infer story dependencies based on logical order and relationships

    Rules:
    - Stories that create data models/schemas come first
    - Stories that use those models depend on them
    - Testing stories depend on implementation stories
    - Integration stories depend on individual feature stories
    """
    # Keywords indicating foundational work (should come first)
    foundation_keywords = [
        'model', 'schema', 'database', 'migration', 'setup',
        'initialize', 'config', 'structure', 'foundation'
    ]

    # Keywords indicating dependent work
    dependent_keywords = {
        'test': ['implement', 'create', 'add', 'build'],
        'integration': ['implement', 'create', 'add', 'api', 'endpoint'],
        'validation': ['implement', 'create', 'add'],
        'documentation': ['implement', 'create', 'add'],
    }

    # First pass: identify foundation stories (no dependencies)
    foundation_story_ids = []
    for story in stories:
        text = f"{story.get('title', '')} {story.get('description', '')}".lower()
        if any(keyword in text for keyword in foundation_keywords):
            foundation_story_ids.append(story['id'])
            story['dependencies'] = []

    # Second pass: add dependencies for non-foundation stories
    for i, story in enumerate(stories):
        if story['id'] in foundation_story_ids:
            continue  # Already processed

        text = f"{story.get('title', '')} {story.get('description', '')}".lower()
        deps = []

        # Check if this is a dependent type of story
        for dep_keyword, required_keywords in dependent_keywords.items():
            if dep_keyword in text:
                # Find stories that match required keywords
                for j, other_story in enumerate(stories):
                    if i != j and other_story['id'] != story['id']:
                        other_text = f"{other_story.get('title', '')} {other_story.get('description', '')}".lower()
                        if any(req in other_text for req in required_keywords):
                            if other_story['id'] not in deps:
                                deps.append(other_story['id'])

        # If still no dependencies, depend on previous story (sequential)
        if not deps and i > 0:
            deps = [stories[i-1]['id']]

        story['dependencies'] = deps

    return stories


def generate_prd_from_goal(
    goal: str,
    analyze_codebase: bool = False,
    output_path: Optional[Path] = None
) -> PRDDocument:
    """Generate complete PRD from high-level goal

    Args:
        goal: High-level project goal/description
        analyze_codebase: Whether to analyze codebase for file scope estimation
        output_path: Optional custom output path

    Returns:
        PRDDocument with generated user stories
    """
    print("🔍 Analyzing goal and generating PRD...")
    print(f"Goal: {goal}")
    print()

    # Step 1: Analyze codebase if requested
    codebase_structure = {}
    if analyze_codebase:
        print("📂 Analyzing codebase structure...")
        codebase_structure = analyze_codebase_structure()
        print(f"   Found {len(codebase_structure.get('languages', []))} languages: {', '.join(codebase_structure.get('languages', []))}")
        print(f"   Found {len(codebase_structure.get('directories', []))} top-level directories")
        print()

    # Step 2: Call Claude to decompose goal into user stories
    prompt = f"""You are helping generate a complete Product Requirements Document (PRD) from a high-level project goal.

## Project Goal

{goal}

## Codebase Context

{"Languages: " + ", ".join(codebase_structure.get('languages', [])) if codebase_structure.get('languages') else "No codebase analysis available"}
{"Directories: " + ", ".join(codebase_structure.get('directories', [])) if codebase_structure.get('directories') else ""}

## Task

Please analyze this goal and generate a complete PRD with 5-10 user stories. For each story, provide:

1. **id**: Unique identifier (US-001, US-002, etc.)
2. **title**: Clear, concise title (< 10 words)
3. **description**: User story format "As a [role], I want [feature] so that [benefit]"
4. **acceptanceCriteria**: 3-5 specific, testable criteria
5. **priority**: 1 (highest) to 3 (lowest)
6. **estimatedComplexity**: "simple", "medium", or "complex"

**Guidelines**:
- Each story should be completable in one iteration (2-8 hours)
- Stories should be ordered logically (foundation → features → polish)
- Acceptance criteria must be specific and testable
- Focus on delivering incremental value
- Consider technical feasibility and dependencies

**Project Metadata**:
- Generate a project name (kebab-case, e.g., "user-authentication")
- Write a 1-2 sentence project description
- Define 2-3 success metrics (measurable outcomes)

Please return a JSON response in this EXACT format:

{{
  "project_name": "project-name-kebab-case",
  "project_description": "Brief description of what this project accomplishes",
  "success_metrics": {{
    "metric1": "Description of measurable outcome 1",
    "metric2": "Description of measurable outcome 2"
  }},
  "user_stories": [
    {{
      "id": "US-001",
      "title": "Story title",
      "description": "As a [role], I want [feature] so that [benefit]",
      "acceptanceCriteria": [
        "Specific testable criterion 1",
        "Specific testable criterion 2",
        "Specific testable criterion 3"
      ],
      "priority": 1,
      "estimatedComplexity": "medium"
    }}
  ]
}}

Return ONLY the JSON, no other text."""

    print("🤖 Calling Claude to generate user stories...")
    try:
        response = call_claude(prompt, model="sonnet", timeout=120)
        parsed = extract_json_from_response(response)
        print("✓ Claude analysis complete")
        print()
    except Exception as e:
        print(f"Error: Failed to get response from Claude: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Extract and validate response
    project_name = parsed.get('project_name', kebab_case(goal[:50]))
    project_description = parsed.get('project_description', goal)
    success_metrics = parsed.get('success_metrics', {})
    user_stories_data = parsed.get('user_stories', [])

    if not user_stories_data:
        print("Error: No user stories generated", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Generated {len(user_stories_data)} user stories")

    # Step 4: Infer dependencies
    print("🔗 Inferring story dependencies...")
    user_stories_data = infer_dependencies(user_stories_data)
    print("✓ Dependencies inferred")

    # Step 5: Estimate file scopes
    if analyze_codebase and codebase_structure:
        print("📁 Estimating file scopes from codebase...")
        user_stories_data = estimate_file_scopes_from_codebase(user_stories_data, codebase_structure)
        print("✓ File scopes estimated")
    else:
        # Add empty file scopes if not analyzed
        for story in user_stories_data:
            if 'fileScope' not in story:
                story['fileScope'] = []

    # Step 6: Convert to UserStory dataclass instances
    user_stories = []
    for story_data in user_stories_data:
        story = UserStory(
            id=story_data['id'],
            title=story_data['title'],
            description=story_data['description'],
            acceptanceCriteria=story_data['acceptanceCriteria'],
            priority=story_data.get('priority', 1),
            dependencies=story_data.get('dependencies', []),
            fileScope=story_data.get('fileScope', []),
            estimatedComplexity=story_data.get('estimatedComplexity', 'medium'),
            passes=False,
            notes=""
        )
        user_stories.append(story)

    # Step 7: Calculate project complexity
    print("📊 Calculating project complexity...")
    try:
        # Create temp PRD for complexity detection
        temp_prd = {
            "description": project_description,
            "userStories": user_stories_data
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(temp_prd, f)
            temp_prd_path = f.name

        # Run complexity detector
        result = subprocess.run(
            [sys.executable, str(COMPLEXITY_DETECTOR), 'detect', '--prd', temp_prd_path, '--json'],
            capture_output=True,
            text=True,
            timeout=10
        )

        os.unlink(temp_prd_path)

        if result.returncode == 0:
            complexity_data = json.loads(result.stdout)
            complexity_level = complexity_data.get('level', 2)
            print(f"✓ Complexity Level: {complexity_level} ({complexity_data.get('level_name', 'medium')})")
        else:
            complexity_level = 2
            print("⚠ Using default complexity level: 2 (medium)")

    except Exception as e:
        print(f"Warning: Complexity detection failed: {e}", file=sys.stderr)
        complexity_level = 2

    # Step 8: Estimate duration based on complexity and story count
    story_count = len(user_stories)
    if complexity_level <= 1:
        estimated_duration = f"{story_count * 2}-{story_count * 4} hours"
    elif complexity_level == 2:
        estimated_duration = f"{story_count * 4}-{story_count * 8} hours"
    elif complexity_level == 3:
        estimated_duration = f"{story_count // 2}-{story_count} days"
    else:
        estimated_duration = f"{story_count}-{story_count * 2} days"

    # Step 9: Create PRD document
    branch_name = f"feature/{project_name}"

    prd = PRDDocument(
        project=project_name,
        branchName=branch_name,
        description=project_description,
        userStories=user_stories,
        complexity=complexity_level,
        estimatedDuration=estimated_duration,
        successMetrics=success_metrics
    )

    print()
    print("✨ PRD generation complete!")
    print()

    return prd


def save_prd(prd: PRDDocument, output_path: Optional[Path] = None) -> Path:
    """Save PRD to JSON file

    Args:
        prd: PRD document to save
        output_path: Optional custom output path

    Returns:
        Path where PRD was saved
    """
    if output_path is None:
        output_path = PROJECT_ROOT / f"prd-{prd.project}.json"

    # Convert to dict
    prd_dict = {
        "project": prd.project,
        "branchName": prd.branchName,
        "description": prd.description,
        "userStories": [asdict(story) for story in prd.userStories],
        "complexity": prd.complexity,
        "estimatedDuration": prd.estimatedDuration,
        "successMetrics": prd.successMetrics
    }

    # Check if file exists
    if output_path.exists():
        response = input(f"File {output_path} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)

    # Save to file
    with open(output_path, 'w') as f:
        json.dump(prd_dict, f, indent=2)

    print(f"💾 PRD saved to: {output_path}")
    return output_path


def display_prd_summary(prd: PRDDocument):
    """Display PRD summary in terminal with formatting"""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                    Generated PRD Summary                       ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"📦 Project: {prd.project}")
    print(f"🌿 Branch: {prd.branchName}")
    print(f"📊 Complexity: Level {prd.complexity}")
    print(f"⏱️  Estimated Duration: {prd.estimatedDuration}")
    print()
    print(f"📝 Description:")
    print(f"   {prd.description}")
    print()
    print(f"🎯 Success Metrics:")
    for key, value in prd.successMetrics.items():
        print(f"   • {key}: {value}")
    print()
    print(f"📋 User Stories ({len(prd.userStories)}):")
    print()

    for story in prd.userStories:
        deps_str = f" [depends on: {', '.join(story.dependencies)}]" if story.dependencies else ""
        print(f"  {story.id}: {story.title}{deps_str}")
        print(f"     Priority: {story.priority} | Complexity: {story.estimatedComplexity}")
        print(f"     {len(story.acceptanceCriteria)} acceptance criteria")
        if story.fileScope:
            print(f"     File scope: {', '.join(story.fileScope[:3])}{'...' if len(story.fileScope) > 3 else ''}")
        print()


def validate_prd_file(prd_path: Path) -> tuple[bool, str]:
    """Validate PRD structure

    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        with open(prd_path, 'r') as f:
            prd_data = json.load(f)

        # Check required fields
        required_fields = ['project', 'branchName', 'description', 'userStories']
        for field in required_fields:
            if field not in prd_data:
                return False, f"Missing required field: {field}"

        # Check user stories
        if not prd_data['userStories']:
            return False, "No user stories in PRD"

        for story in prd_data['userStories']:
            required_story_fields = ['id', 'title', 'description', 'acceptanceCriteria', 'priority']
            for field in required_story_fields:
                if field not in story:
                    return False, f"Story {story.get('id', '?')} missing field: {field}"

        return True, "PRD structure is valid"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Validation failed: {e}"


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Generate PRD from natural language project goals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate PRD from goal string
  python3 lib/prd-generator.py generate "Add user authentication with JWT"

  # Generate with codebase analysis for file scopes
  python3 lib/prd-generator.py generate "Add GraphQL API" --codebase-analysis

  # Generate from goal file with custom output
  python3 lib/prd-generator.py generate --input goal.txt --output prd-custom.json

  # Validate a PRD file
  python3 lib/prd-generator.py validate prd-output.json
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # generate command
    gen_parser = subparsers.add_parser('generate', help='Generate PRD from goal')
    gen_parser.add_argument(
        'goal',
        nargs='?',
        help='Project goal/description as string'
    )
    gen_parser.add_argument(
        '--input', '-i',
        type=Path,
        help='Read goal from file instead of argument'
    )
    gen_parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Custom output path for generated PRD (default: prd-{project}.json)'
    )
    gen_parser.add_argument(
        '--codebase-analysis',
        action='store_true',
        help='Analyze codebase to estimate file scopes'
    )
    gen_parser.add_argument(
        '--no-display',
        action='store_true',
        help='Skip displaying PRD summary (just save to file)'
    )

    # validate command
    val_parser = subparsers.add_parser('validate', help='Validate PRD structure')
    val_parser.add_argument(
        'prd_path',
        type=Path,
        help='Path to PRD JSON file'
    )

    args = parser.parse_args()

    if args.command == 'generate':
        # Get goal text
        goal = None
        if args.input:
            try:
                with open(args.input, 'r') as f:
                    goal = f.read().strip()
            except Exception as e:
                print(f"Error: Failed to read input file: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.goal:
            goal = args.goal
        else:
            parser.error("Either goal argument or --input file required")

        # Generate PRD
        prd = generate_prd_from_goal(
            goal=goal,
            analyze_codebase=args.codebase_analysis,
            output_path=args.output
        )

        # Display summary
        if not args.no_display:
            display_prd_summary(prd)

        # Save to file
        output_path = save_prd(prd, args.output)

        print()
        print("Next steps:")
        print(f"  1. Review the generated PRD: {output_path}")
        print(f"  2. Edit if needed (add/remove stories, adjust priorities)")
        print(f"  3. Run: ./claude-loop.sh {output_path}")
        print()

    elif args.command == 'validate':
        is_valid, message = validate_prd_file(args.prd_path)
        print(f"Validation: {message}")
        sys.exit(0 if is_valid else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
