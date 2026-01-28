#!/usr/bin/env python3
"""
prd-from-description.py - Generate PRD from Feature Description (INV-008)

Part of the Invisible Intelligence system. Enables single-command entry point:
    ./claude-loop.sh "Add user authentication with OAuth"

This script generates a prd.json file from a plain text feature description,
automatically detecting complexity, selecting appropriate tracks/phases, and
creating properly-sized user stories.

Usage:
    python lib/prd-from-description.py generate "Add user authentication with OAuth"
    python lib/prd-from-description.py generate "Add user authentication" --output prd.json
    python lib/prd-from-description.py generate "Add user authentication" --json
    python lib/prd-from-description.py analyze "Add dark mode toggle"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import from sibling modules with hyphenated names
import importlib.util


def _import_module(module_name: str, file_name: str):
    """Import a module from a hyphenated filename."""
    module_path = Path(__file__).parent / file_name
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Try to import complexity detector
_complexity_detector = _import_module("complexity_detector", "complexity-detector.py")

if _complexity_detector:
    detect_complexity = _complexity_detector.detect_complexity
    get_track = _complexity_detector.get_track
    get_phases = _complexity_detector.get_phases
    get_track_config = _complexity_detector.get_track_config
    COMPLEXITY_LEVELS = _complexity_detector.COMPLEXITY_LEVELS
else:
    # Fallback defaults if complexity detector not available
    COMPLEXITY_LEVELS = {
        0: {"name": "micro", "description": "Bug fix, typo"},
        1: {"name": "small", "description": "Simple feature"},
        2: {"name": "medium", "description": "Standard feature"},
        3: {"name": "large", "description": "Complex feature"},
        4: {"name": "enterprise", "description": "Enterprise feature"},
    }
    detect_complexity = None
    get_track = None
    get_phases = None
    get_track_config = None


# ============================================================================
# Story Generation Templates
# ============================================================================

# Keywords that suggest specific story types
STORY_KEYWORDS = {
    # Data layer
    "database": ["schema", "model", "migration"],
    "model": ["schema", "model", "entity"],
    "schema": ["schema", "model"],
    "data": ["data", "model", "schema"],

    # API layer
    "api": ["api", "endpoint", "route"],
    "endpoint": ["api", "endpoint", "route"],
    "rest": ["api", "endpoint", "rest"],
    "graphql": ["api", "graphql", "schema"],

    # Auth
    "auth": ["auth", "login", "register", "token"],
    "login": ["auth", "login"],
    "oauth": ["auth", "oauth", "provider"],
    "jwt": ["auth", "jwt", "token"],

    # UI
    "ui": ["ui", "component", "page"],
    "component": ["ui", "component"],
    "page": ["ui", "page", "component"],
    "form": ["ui", "form", "validation"],
    "dashboard": ["ui", "dashboard", "chart"],
    "toggle": ["ui", "toggle", "switch"],

    # Integration
    "integration": ["integration", "api", "client"],
    "webhook": ["webhook", "handler"],
    "notification": ["notification", "email", "push"],

    # Testing
    "test": ["test", "unit", "integration"],
}


# Story templates for common feature types
STORY_TEMPLATES = {
    "setup": {
        "title": "Initial Setup and Configuration",
        "description": "Set up the basic structure and configuration for {feature}",
        "criteria": [
            "Create necessary files and directories",
            "Add configuration options if needed",
            "Set up any required dependencies",
            "Document initial setup"
        ],
        "complexity": "simple",
    },
    "model": {
        "title": "Create Data Models",
        "description": "Define the data models and schema for {feature}",
        "criteria": [
            "Create data model/schema definitions",
            "Add validation rules",
            "Include TypeScript types if applicable",
            "Add unit tests for model validation"
        ],
        "complexity": "simple",
    },
    "api": {
        "title": "Implement API Endpoints",
        "description": "Create the API endpoints for {feature}",
        "criteria": [
            "Implement CRUD endpoints as needed",
            "Add request/response validation",
            "Handle errors appropriately",
            "Add API tests"
        ],
        "complexity": "medium",
    },
    "auth": {
        "title": "Add Authentication/Authorization",
        "description": "Implement authentication and authorization for {feature}",
        "criteria": [
            "Add auth middleware or decorators",
            "Implement role-based access if needed",
            "Secure sensitive endpoints",
            "Add auth-related tests"
        ],
        "complexity": "medium",
    },
    "ui": {
        "title": "Create UI Components",
        "description": "Build the user interface components for {feature}",
        "criteria": [
            "Create necessary UI components",
            "Implement responsive design",
            "Add accessibility attributes",
            "Add component tests"
        ],
        "complexity": "medium",
    },
    "integration": {
        "title": "External Integration",
        "description": "Integrate with external services for {feature}",
        "criteria": [
            "Set up API client/SDK",
            "Implement error handling and retries",
            "Add integration tests",
            "Document integration setup"
        ],
        "complexity": "medium",
    },
    "test": {
        "title": "Comprehensive Testing",
        "description": "Add comprehensive tests for {feature}",
        "criteria": [
            "Add unit tests for all components",
            "Add integration tests",
            "Ensure test coverage > 80%",
            "All tests pass"
        ],
        "complexity": "simple",
    },
    "docs": {
        "title": "Documentation and Cleanup",
        "description": "Document and finalize {feature}",
        "criteria": [
            "Update relevant documentation",
            "Add usage examples",
            "Remove debug code",
            "Code review completed"
        ],
        "complexity": "simple",
    },
}


@dataclass
class UserStory:
    """A user story for the PRD."""
    id: str
    title: str
    description: str
    acceptanceCriteria: list[str]
    priority: int
    passes: bool = False
    notes: str = ""
    dependencies: list[str] = field(default_factory=list)
    fileScope: list[str] = field(default_factory=list)
    estimatedComplexity: str = "medium"
    suggestedModel: str = "sonnet"


@dataclass
class GeneratedPRD:
    """A generated PRD structure."""
    project: str
    branchName: str
    description: str
    userStories: list[UserStory]
    # Additional metadata
    generated_at: str = ""
    complexity_level: int = 2
    track: str = "standard"
    phases: list[str] = field(default_factory=list)
    auto_detected: bool = True


def generate_project_id(description: str) -> str:
    """Generate a short project ID from description."""
    # Extract key words
    words = re.findall(r'\b[a-z]+\b', description.lower())

    # Filter common words
    stopwords = {'a', 'an', 'the', 'to', 'for', 'with', 'and', 'or', 'in', 'on', 'add', 'create', 'implement'}
    keywords = [w for w in words if w not in stopwords and len(w) > 2][:3]

    if not keywords:
        keywords = words[:3] if words else ['feature']

    # Generate ID
    base_id = '-'.join(keywords)

    # Add short hash for uniqueness
    hash_suffix = hashlib.md5(description.encode()).hexdigest()[:4]

    return f"{base_id}-{hash_suffix}"


def detect_feature_type(description: str) -> list[str]:
    """Detect the type of feature from description."""
    description_lower = description.lower()
    detected_types = set()

    for keyword, types in STORY_KEYWORDS.items():
        if keyword in description_lower:
            detected_types.update(types)

    # Always include setup and docs
    detected_types.add('setup')

    # If no specific types detected, add generic stories
    if len(detected_types) <= 1:
        detected_types.add('model')
        detected_types.add('api')
        detected_types.add('test')

    # Always end with test and docs
    detected_types.add('test')
    detected_types.add('docs')

    return list(detected_types)


def estimate_story_count(description: str, complexity_level: int) -> int:
    """Estimate the number of stories based on description and complexity."""
    base_count = {
        0: 1,   # micro
        1: 2,   # small
        2: 4,   # medium
        3: 8,   # large
        4: 15,  # enterprise
    }.get(complexity_level, 4)

    # Adjust based on keywords
    description_lower = description.lower()

    # More stories for complex features
    if any(kw in description_lower for kw in ['oauth', 'authentication', 'dashboard', 'integration']):
        base_count += 2

    if any(kw in description_lower for kw in ['api', 'endpoint', 'crud']):
        base_count += 1

    if any(kw in description_lower for kw in ['test', 'testing']):
        base_count += 1

    return min(base_count, 15)  # Cap at 15 stories


def generate_stories_for_description(
    description: str,
    project_id: str,
    complexity_level: int
) -> list[UserStory]:
    """Generate user stories based on description."""
    stories = []
    feature_types = detect_feature_type(description)
    target_count = estimate_story_count(description, complexity_level)

    # Order story types logically
    type_order = ['setup', 'model', 'schema', 'data', 'auth', 'api', 'endpoint',
                  'route', 'graphql', 'integration', 'webhook', 'ui', 'component',
                  'page', 'form', 'dashboard', 'toggle', 'notification', 'test', 'docs']

    ordered_types = sorted(feature_types, key=lambda t: type_order.index(t) if t in type_order else 100)

    # Map feature types to story templates
    type_to_template = {
        'setup': 'setup',
        'model': 'model',
        'schema': 'model',
        'data': 'model',
        'auth': 'auth',
        'api': 'api',
        'endpoint': 'api',
        'route': 'api',
        'graphql': 'api',
        'integration': 'integration',
        'webhook': 'integration',
        'ui': 'ui',
        'component': 'ui',
        'page': 'ui',
        'form': 'ui',
        'dashboard': 'ui',
        'toggle': 'ui',
        'notification': 'integration',
        'test': 'test',
        'docs': 'docs',
    }

    # Generate stories
    seen_templates = set()
    priority = 1

    for feature_type in ordered_types:
        template_name = type_to_template.get(feature_type, feature_type)

        # Skip duplicate templates
        if template_name in seen_templates:
            continue
        seen_templates.add(template_name)

        template = STORY_TEMPLATES.get(template_name)
        if not template:
            continue

        # Generate story ID
        story_id = f"{project_id.upper()}-{str(priority).zfill(3)}"

        # Customize template with feature description
        title = template['title']
        if '{feature}' in template['description']:
            story_desc = template['description'].format(feature=description)
        else:
            story_desc = f"{template['description']} for: {description}"

        # Build acceptance criteria
        criteria = [c.format(feature=description) if '{feature}' in c else c
                   for c in template['criteria']]

        # Map complexity to model
        complexity = template.get('complexity', 'medium')
        model = {
            'simple': 'haiku',
            'medium': 'sonnet',
            'complex': 'opus',
        }.get(complexity, 'sonnet')

        # Set dependencies (each story depends on previous except first)
        dependencies = []
        if priority > 1:
            prev_id = f"{project_id.upper()}-{str(priority-1).zfill(3)}"
            dependencies = [prev_id]

        story = UserStory(
            id=story_id,
            title=title,
            description=story_desc,
            acceptanceCriteria=criteria,
            priority=priority,
            dependencies=dependencies,
            estimatedComplexity=complexity,
            suggestedModel=model,
        )

        stories.append(story)
        priority += 1

        # Stop if we have enough stories
        if len(stories) >= target_count:
            break

    return stories


def generate_prd_from_description(
    description: str,
    output_path: str | None = None,
) -> GeneratedPRD:
    """
    Generate a complete PRD from a feature description.

    Args:
        description: Plain text feature description
        output_path: Optional path to save the PRD JSON

    Returns:
        GeneratedPRD object with all fields populated
    """
    # Generate project ID
    project_id = generate_project_id(description)

    # Detect complexity using complexity detector if available
    complexity_level = 2  # Default to medium
    track = "standard"
    phases = ["implementation"]

    if detect_complexity:
        try:
            result = detect_complexity(description)
            complexity_level = result.level
        except Exception:
            pass

    if get_track:
        try:
            track = get_track(complexity_level)
        except Exception:
            pass

    if get_phases:
        try:
            phases = get_phases(complexity_level)
        except Exception:
            pass

    # Generate user stories
    stories = generate_stories_for_description(
        description,
        project_id,
        complexity_level
    )

    # Build PRD
    prd = GeneratedPRD(
        project=project_id,
        branchName=f"feature/{project_id}",
        description=description,
        userStories=stories,
        generated_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        complexity_level=complexity_level,
        track=track,
        phases=phases,
        auto_detected=True,
    )

    # Save to file if path provided
    if output_path:
        save_prd(prd, output_path)

    return prd


def save_prd(prd: GeneratedPRD, output_path: str) -> None:
    """Save PRD to a JSON file."""
    # Convert to dict, excluding metadata fields not in standard PRD format
    prd_dict = {
        "project": prd.project,
        "branchName": prd.branchName,
        "description": prd.description,
        "userStories": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "acceptanceCriteria": s.acceptanceCriteria,
                "priority": s.priority,
                "passes": s.passes,
                "notes": s.notes,
                "dependencies": s.dependencies,
                "fileScope": s.fileScope,
                "estimatedComplexity": s.estimatedComplexity,
                "suggestedModel": s.suggestedModel,
            }
            for s in prd.userStories
        ],
        # Include parallelization config
        "parallelization": {
            "enabled": True,
            "maxWorkers": 3,
            "modelStrategy": "auto"
        },
        # Metadata comment
        "_generated": {
            "by": "prd-from-description.py",
            "at": prd.generated_at,
            "complexity_level": prd.complexity_level,
            "track": prd.track,
            "phases": prd.phases,
            "auto_detected": prd.auto_detected,
        }
    }

    # Ensure parent directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(prd_dict, f, indent=2)


def display_auto_detection_summary(prd: GeneratedPRD) -> None:
    """Display a summary of auto-detected settings."""
    level_info = COMPLEXITY_LEVELS.get(prd.complexity_level, {})
    level_name = level_info.get('name', 'unknown')

    print()
    print("═══════════════════════════════════════════════════════════════")
    print("               AUTO-DETECTION SUMMARY (INV-008)")
    print("═══════════════════════════════════════════════════════════════")
    print()
    print(f"  Description: {prd.description}")
    print()
    print(f"  Project ID:  {prd.project}")
    print(f"  Branch:      {prd.branchName}")
    print()
    print(f"  Complexity:  Level {prd.complexity_level} ({level_name})")
    print(f"  Track:       {prd.track}")
    print(f"  Phases:      {' → '.join(prd.phases)}")
    print()
    print(f"  Stories:     {len(prd.userStories)}")
    for story in prd.userStories[:5]:  # Show first 5
        print(f"    - {story.id}: {story.title}")
    if len(prd.userStories) > 5:
        print(f"    ... and {len(prd.userStories) - 5} more")
    print()
    print("═══════════════════════════════════════════════════════════════")
    print()


def analyze_description(description: str) -> dict[str, Any]:
    """Analyze a description and return detection results without generating PRD."""
    # Detect complexity
    complexity_level = 2
    complexity_result = None

    if detect_complexity:
        try:
            complexity_result = detect_complexity(description)
            complexity_level = complexity_result.level
        except Exception:
            pass

    # Get track and phases
    track = get_track(complexity_level) if get_track else "standard"
    phases = get_phases(complexity_level) if get_phases else ["implementation"]

    # Detect feature types
    feature_types = detect_feature_type(description)
    story_count = estimate_story_count(description, complexity_level)

    # Generate project ID
    project_id = generate_project_id(description)

    return {
        "description": description,
        "project_id": project_id,
        "branch_name": f"feature/{project_id}",
        "complexity": {
            "level": complexity_level,
            "name": COMPLEXITY_LEVELS.get(complexity_level, {}).get('name', 'unknown'),
            "description": COMPLEXITY_LEVELS.get(complexity_level, {}).get('description', ''),
        },
        "track": track,
        "phases": phases,
        "detected_features": feature_types,
        "estimated_stories": story_count,
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate PRD from feature description (INV-008)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python lib/prd-from-description.py generate "Add user authentication"
    python lib/prd-from-description.py generate "Add OAuth support" --output prd.json
    python lib/prd-from-description.py analyze "Add dark mode toggle"
    python lib/prd-from-description.py analyze "Add dashboard" --json
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate PRD from description")
    gen_parser.add_argument("description", help="Feature description")
    gen_parser.add_argument("--output", "-o", default="prd.json", help="Output file path")
    gen_parser.add_argument("--json", action="store_true", help="Output as JSON to stdout")
    gen_parser.add_argument("--quiet", "-q", action="store_true", help="Suppress summary output")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze description without generating")
    analyze_parser.add_argument("description", help="Feature description to analyze")
    analyze_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "generate":
        # Generate PRD
        output_path = None if args.json else args.output
        prd = generate_prd_from_description(args.description, output_path)

        if args.json:
            # Output full PRD as JSON
            prd_dict = {
                "project": prd.project,
                "branchName": prd.branchName,
                "description": prd.description,
                "userStories": [asdict(s) for s in prd.userStories],
                "complexity_level": prd.complexity_level,
                "track": prd.track,
                "phases": prd.phases,
                "generated_at": prd.generated_at,
            }
            print(json.dumps(prd_dict, indent=2))
        else:
            if not args.quiet:
                display_auto_detection_summary(prd)
                print(f"PRD saved to: {args.output}")

    elif args.command == "analyze":
        # Analyze without generating
        result = analyze_description(args.description)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print()
            print(f"Description: {result['description']}")
            print(f"Project ID:  {result['project_id']}")
            print(f"Branch:      {result['branch_name']}")
            print()
            print(f"Complexity:  Level {result['complexity']['level']} ({result['complexity']['name']})")
            print(f"             {result['complexity']['description']}")
            print(f"Track:       {result['track']}")
            print(f"Phases:      {' → '.join(result['phases'])}")
            print()
            print(f"Detected features: {', '.join(result['detected_features'])}")
            print(f"Estimated stories: {result['estimated_stories']}")
            print()


if __name__ == "__main__":
    main()
