#!/usr/bin/env python3
"""
Solutioning Generator for Claude-Loop

Automatically generates architecture documentation and ADR templates for complex features
(Level >= 3). Part of the Invisible Intelligence system.

Generated Artifacts:
- architecture.md: Overview, Components, Data Flow, API Contracts, Security
- ADR templates: Major technical decisions detected from PRD keywords

ADR Topic Detection Keywords:
- Database: database, postgres, mysql, mongodb, redis, dynamodb, storage
- API Style: api, rest, graphql, grpc, websocket
- Authentication: auth, oauth, jwt, sso, saml, authentication
- State Management: state, redux, context, store, session

Usage:
    solutioning-generator.py generate --prd prd.json
    solutioning-generator.py generate --prd prd.json --output-dir ./docs
    solutioning-generator.py detect-adrs --prd prd.json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

# Add lib directory to path for imports
LIB_DIR = os.path.dirname(__file__)
sys.path.insert(0, LIB_DIR)

# Try to import complexity detector for complexity checking
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "complexity_detector",
        os.path.join(LIB_DIR, "complexity-detector.py")
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not load complexity-detector.py")
    complexity_detector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(complexity_detector)
    detect_complexity = complexity_detector.detect_complexity
    COMPLEXITY_DETECTOR_AVAILABLE = True
except Exception:
    COMPLEXITY_DETECTOR_AVAILABLE = False
    detect_complexity = None


# ADR topic detection keywords
ADR_TOPICS = {
    "database": {
        "keywords": [
            "database", "postgres", "postgresql", "mysql", "mariadb",
            "mongodb", "dynamodb", "redis", "cassandra", "sqlite",
            "sql", "nosql", "data storage", "persistence", "orm",
            "migration", "schema", "table", "collection",
        ],
        "title": "Database Technology Selection",
        "context": "The system requires data persistence and retrieval capabilities.",
        "options": [
            "PostgreSQL - Mature relational database with strong consistency",
            "MongoDB - Document database for flexible schemas",
            "Redis - In-memory store for caching and fast lookups",
            "SQLite - Embedded database for simpler deployments",
        ],
    },
    "api_style": {
        "keywords": [
            "api", "rest", "restful", "graphql", "grpc", "rpc",
            "websocket", "webhook", "endpoint", "http", "https",
            "openapi", "swagger", "json-rpc", "soap",
        ],
        "title": "API Architecture Style",
        "context": "The system needs to expose APIs for client communication.",
        "options": [
            "REST - Standard HTTP methods with resource-based URLs",
            "GraphQL - Flexible query language for complex data needs",
            "gRPC - High-performance RPC with Protocol Buffers",
            "WebSocket - Bidirectional real-time communication",
        ],
    },
    "authentication": {
        "keywords": [
            "auth", "oauth", "oauth2", "jwt", "token", "sso",
            "saml", "authentication", "authorization", "login",
            "session", "credential", "identity", "iam", "rbac",
            "permission", "role", "user management",
        ],
        "title": "Authentication and Authorization Strategy",
        "context": "The system requires user authentication and access control.",
        "options": [
            "JWT - Stateless tokens for distributed systems",
            "OAuth 2.0 - Industry standard for third-party authorization",
            "Session-based - Server-side session management",
            "SAML - Enterprise SSO integration",
        ],
    },
    "state_management": {
        "keywords": [
            "state", "redux", "context", "store", "vuex", "mobx",
            "session", "cache", "local storage", "session storage",
            "global state", "application state", "client state",
            "server state", "react query", "swr", "zustand",
        ],
        "title": "State Management Approach",
        "context": "The application needs to manage client-side or server-side state.",
        "options": [
            "Redux - Predictable state container with middleware support",
            "React Context - Built-in React state sharing",
            "Zustand - Lightweight state management",
            "Server-side sessions - Traditional session management",
        ],
    },
    "infrastructure": {
        "keywords": [
            "kubernetes", "k8s", "docker", "container", "serverless",
            "lambda", "cloud", "aws", "gcp", "azure", "terraform",
            "infrastructure", "deployment", "ci/cd", "pipeline",
        ],
        "title": "Infrastructure and Deployment Strategy",
        "context": "The system needs a deployment and infrastructure approach.",
        "options": [
            "Kubernetes - Container orchestration for complex deployments",
            "Serverless - Event-driven functions for cost efficiency",
            "Docker Compose - Simplified container management",
            "Traditional VMs - Standard virtual machine deployment",
        ],
    },
    "caching": {
        "keywords": [
            "cache", "caching", "redis", "memcached", "cdn",
            "edge caching", "browser cache", "http cache",
            "in-memory", "distributed cache",
        ],
        "title": "Caching Strategy",
        "context": "The system needs caching to improve performance.",
        "options": [
            "Redis - Distributed in-memory cache",
            "CDN - Edge caching for static assets",
            "Application-level caching - In-process cache",
            "HTTP caching - Browser and proxy caching",
        ],
    },
    "messaging": {
        "keywords": [
            "queue", "message", "kafka", "rabbitmq", "sqs", "sns",
            "pubsub", "event", "event-driven", "async", "worker",
            "background job", "celery", "bull",
        ],
        "title": "Messaging and Event Architecture",
        "context": "The system needs asynchronous communication or event processing.",
        "options": [
            "Kafka - High-throughput event streaming",
            "RabbitMQ - Feature-rich message broker",
            "AWS SQS/SNS - Managed cloud messaging",
            "Redis Pub/Sub - Lightweight messaging",
        ],
    },
}


@dataclass
class ADRDetectionResult:
    """Result of ADR topic detection."""
    topic: str
    keyword_matches: list
    match_count: int
    should_generate: bool
    title: str
    context: str
    options: list


@dataclass
class GenerationResult:
    """Result of artifact generation."""
    success: bool
    architecture_path: Optional[str]
    adr_paths: list
    skipped_reason: Optional[str]
    complexity_level: Optional[int]
    detected_topics: list


def count_keyword_matches(text: str, keywords: list) -> tuple:
    """
    Count keyword matches and return matched keywords.

    Returns:
        Tuple of (match_count, list of matched keywords)
    """
    text_lower = text.lower()
    matches = []
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, text_lower):
            matches.append(keyword)
    return len(matches), matches


def detect_adr_topics(prd_content: str, prd_data: Optional[dict] = None) -> list:
    """
    Detect ADR topics from PRD content.

    Args:
        prd_content: Text content from PRD
        prd_data: Optional parsed PRD JSON

    Returns:
        List of ADRDetectionResult for topics that should have ADRs generated
    """
    # Combine text sources
    combined_text = prd_content
    if prd_data:
        combined_text += " " + json.dumps(prd_data)

    results = []
    for topic, config in ADR_TOPICS.items():
        match_count, matched_keywords = count_keyword_matches(
            combined_text,
            config["keywords"]
        )

        # Generate ADR if 2+ keyword matches
        should_generate = match_count >= 2

        results.append(ADRDetectionResult(
            topic=topic,
            keyword_matches=matched_keywords,
            match_count=match_count,
            should_generate=should_generate,
            title=config["title"],
            context=config["context"],
            options=config["options"],
        ))

    return results


def generate_architecture_template(
    prd_data: dict,
    detected_topics: list,
) -> str:
    """
    Generate architecture.md template content.

    Args:
        prd_data: Parsed PRD JSON
        detected_topics: List of ADRDetectionResult

    Returns:
        Markdown content for architecture.md
    """
    project_name = prd_data.get("project", "Project")
    description = prd_data.get("description", "")
    stories = prd_data.get("userStories", [])

    # Extract components from story fileScope
    components = set()
    for story in stories:
        file_scope = story.get("fileScope", [])
        for path in file_scope:
            # Extract component directory from path
            parts = path.split("/")
            if len(parts) >= 2:
                components.add(parts[0])

    # Build architecture template
    template = f"""# Architecture Document: {project_name}

> Generated by claude-loop solutioning-generator
> Date: {datetime.now().strftime('%Y-%m-%d')}

## 1. Overview

### 1.1 Purpose

{description if description else '[Describe the purpose and goals of this system]'}

### 1.2 Scope

This document covers the architecture for the following user stories:

"""
    # Add story list
    for story in stories[:10]:  # Limit to first 10
        story_id = story.get("id", "")
        title = story.get("title", "")
        template += f"- **{story_id}**: {title}\n"

    if len(stories) > 10:
        template += f"- ... and {len(stories) - 10} more stories\n"

    template += """
### 1.3 Key Requirements

- [List key functional requirements]
- [List key non-functional requirements]
- [List constraints and assumptions]

## 2. Components

"""
    # Generate component section
    if components:
        template += """### 2.1 Component Overview

| Component | Responsibility | Technology |
|-----------|----------------|------------|
"""
        for comp in sorted(components):
            template += f"| `{comp}/` | [Describe responsibility] | [Technology] |\n"
    else:
        template += """### 2.1 Component Overview

| Component | Responsibility | Technology |
|-----------|----------------|------------|
| [component-name] | [Describe responsibility] | [Technology] |
"""

    template += """
### 2.2 Component Details

"""
    # Add detected technology topics as component hints
    for topic_result in detected_topics:
        if topic_result.should_generate:
            template += f"""#### {topic_result.title.replace(' Selection', '').replace(' Strategy', '').replace(' Approach', '')}

- **Decision**: See ADR-XXX
- **Rationale**: {topic_result.context}

"""

    template += """## 3. Data Flow

### 3.1 High-Level Data Flow

```
[User] --> [Frontend] --> [API Layer] --> [Business Logic] --> [Data Store]
```

### 3.2 Key Data Flows

1. **[Flow Name]**
   - Input: [Description]
   - Processing: [Steps]
   - Output: [Description]

## 4. API Contracts

### 4.1 Internal APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| [/api/resource] | [GET/POST] | [Description] |

### 4.2 External Integrations

| Service | Purpose | Authentication |
|---------|---------|----------------|
| [Service Name] | [Purpose] | [Auth method] |

## 5. Security

### 5.1 Authentication

- **Method**: [JWT/OAuth/Session/etc.]
- **Token Storage**: [Description]
- **Session Duration**: [Duration]

### 5.2 Authorization

- **Model**: [RBAC/ABAC/etc.]
- **Roles**: [List roles]
- **Permissions**: [Description]

### 5.3 Data Protection

- **Encryption at Rest**: [Yes/No/Details]
- **Encryption in Transit**: [TLS/Details]
- **Sensitive Data Handling**: [Description]

### 5.4 Security Considerations

- [List security considerations]
- [Threat model summary]
- [Compliance requirements]

## 6. Deployment

### 6.1 Infrastructure

- **Environment**: [Cloud/On-premise/Hybrid]
- **Container Runtime**: [Docker/Kubernetes/etc.]
- **CI/CD**: [Platform/Approach]

### 6.2 Scalability

- **Horizontal Scaling**: [Approach]
- **Load Balancing**: [Strategy]
- **Caching**: [Strategy]

## 7. Monitoring and Observability

- **Logging**: [Approach]
- **Metrics**: [Tools/Metrics]
- **Tracing**: [Approach]
- **Alerting**: [Strategy]

## 8. Related Documents

- [Link to ADRs]
- [Link to API documentation]
- [Link to runbook]

---

*This document should be updated as the architecture evolves.*
"""
    return template


def generate_adr_template(
    topic_result: ADRDetectionResult,
    adr_number: int,
    project_name: str,
) -> str:
    """
    Generate ADR template for a detected topic.

    Args:
        topic_result: ADRDetectionResult for the topic
        adr_number: ADR sequence number
        project_name: Project name for context

    Returns:
        Markdown content for the ADR
    """
    template = f"""# ADR-{adr_number:03d}: {topic_result.title}

> Project: {project_name}
> Status: **Proposed**
> Date: {datetime.now().strftime('%Y-%m-%d')}
> Decision Makers: [List team members]

## Context

{topic_result.context}

Keywords detected in requirements: {', '.join(topic_result.keyword_matches[:5])}

## Decision Drivers

- [Driver 1: e.g., Performance requirements]
- [Driver 2: e.g., Team expertise]
- [Driver 3: e.g., Cost constraints]
- [Driver 4: e.g., Scalability needs]

## Considered Options

"""
    for i, option in enumerate(topic_result.options, 1):
        template += f"{i}. {option}\n"

    template += """
## Decision Outcome

**Chosen option**: "[Option X]"

### Rationale

[Explain why this option was chosen, referencing the decision drivers]

### Consequences

#### Positive

- [Benefit 1]
- [Benefit 2]

#### Negative

- [Tradeoff 1]
- [Tradeoff 2]

#### Neutral

- [Implication that is neither positive nor negative]

## Validation

How will we validate this decision was correct?

- [Metric 1]
- [Metric 2]

## Related Decisions

- [Link to related ADRs]

## Notes

- [Additional context or considerations]

---

*Template based on [MADR](https://adr.github.io/madr/)*
"""
    return template


def ensure_directory(path: str) -> bool:
    """
    Ensure directory exists, create if needed.

    Returns:
        True if directory exists or was created, False on error
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        print(f"Error creating directory {path}: {e}", file=sys.stderr)
        return False


def generate_solutioning_artifacts(
    prd_path: str,
    output_dir: Optional[str] = None,
    force: bool = False,
    min_complexity: int = 3,
) -> GenerationResult:
    """
    Generate architecture.md and ADR templates for a PRD.

    Args:
        prd_path: Path to PRD JSON file
        output_dir: Base directory for output (default: project root based on prd location)
        force: Generate even if complexity < min_complexity
        min_complexity: Minimum complexity level to generate (default: 3)

    Returns:
        GenerationResult with paths to generated files
    """
    # Load PRD
    try:
        with open(prd_path, 'r') as f:
            prd_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return GenerationResult(
            success=False,
            architecture_path=None,
            adr_paths=[],
            skipped_reason=f"Failed to load PRD: {e}",
            complexity_level=None,
            detected_topics=[],
        )

    # Check complexity level
    complexity_level = None
    if COMPLEXITY_DETECTOR_AVAILABLE and detect_complexity is not None and not force:
        description = prd_data.get("description", "")
        result = detect_complexity(description, prd_path)
        complexity_level = result.level

        if complexity_level < min_complexity:
            return GenerationResult(
                success=True,
                architecture_path=None,
                adr_paths=[],
                skipped_reason=f"Complexity level {complexity_level} < {min_complexity}, skipping generation",
                complexity_level=complexity_level,
                detected_topics=[],
            )

    # Determine output directory
    if output_dir is None:
        # Use docs/ relative to PRD location
        prd_dir = os.path.dirname(os.path.abspath(prd_path))
        output_dir = os.path.join(prd_dir, "docs")

    architecture_dir = os.path.join(output_dir, "architecture")
    adr_dir = os.path.join(output_dir, "adrs")

    # Ensure directories exist
    if not ensure_directory(architecture_dir) or not ensure_directory(adr_dir):
        return GenerationResult(
            success=False,
            architecture_path=None,
            adr_paths=[],
            skipped_reason="Failed to create output directories",
            complexity_level=complexity_level,
            detected_topics=[],
        )

    # Detect ADR topics
    prd_content = prd_data.get("description", "")
    topic_results = detect_adr_topics(prd_content, prd_data)
    topics_to_generate = [t for t in topic_results if t.should_generate]

    # Generate architecture.md
    architecture_content = generate_architecture_template(prd_data, topics_to_generate)
    architecture_path = os.path.join(architecture_dir, "architecture.md")

    try:
        with open(architecture_path, 'w') as f:
            f.write(architecture_content)
    except OSError as e:
        return GenerationResult(
            success=False,
            architecture_path=None,
            adr_paths=[],
            skipped_reason=f"Failed to write architecture.md: {e}",
            complexity_level=complexity_level,
            detected_topics=[t.topic for t in topics_to_generate],
        )

    # Generate ADR templates
    project_name = prd_data.get("project", "Project")
    adr_paths = []

    for i, topic_result in enumerate(topics_to_generate, 1):
        adr_content = generate_adr_template(topic_result, i, project_name)
        adr_filename = f"adr-{i:03d}-{topic_result.topic.replace('_', '-')}.md"
        adr_path = os.path.join(adr_dir, adr_filename)

        try:
            with open(adr_path, 'w') as f:
                f.write(adr_content)
            adr_paths.append(adr_path)
        except OSError as e:
            print(f"Warning: Failed to write {adr_path}: {e}", file=sys.stderr)

    return GenerationResult(
        success=True,
        architecture_path=architecture_path,
        adr_paths=adr_paths,
        skipped_reason=None,
        complexity_level=complexity_level,
        detected_topics=[t.topic for t in topics_to_generate],
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate architecture documentation and ADR templates for complex features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  solutioning-generator.py generate --prd prd.json
  solutioning-generator.py generate --prd prd.json --output-dir ./docs
  solutioning-generator.py generate --prd prd.json --force
  solutioning-generator.py detect-adrs --prd prd.json
  solutioning-generator.py detect-adrs --prd prd.json --json

ADR Topics Detected:
  - database: PostgreSQL, MongoDB, Redis, etc.
  - api_style: REST, GraphQL, gRPC, WebSocket
  - authentication: JWT, OAuth, SSO, SAML
  - state_management: Redux, Context, Zustand
  - infrastructure: Kubernetes, Docker, Serverless
  - caching: Redis, CDN, HTTP caching
  - messaging: Kafka, RabbitMQ, SQS
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # generate command
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate architecture.md and ADR templates"
    )
    generate_parser.add_argument(
        "--prd",
        type=str,
        required=True,
        help="Path to PRD JSON file",
    )
    generate_parser.add_argument(
        "--output-dir",
        type=str,
        help="Base directory for output (default: docs/ relative to PRD)",
    )
    generate_parser.add_argument(
        "--force",
        action="store_true",
        help="Generate even if complexity < 3",
    )
    generate_parser.add_argument(
        "--min-complexity",
        type=int,
        default=3,
        help="Minimum complexity level to generate (default: 3)",
    )
    generate_parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    # detect-adrs command
    detect_parser = subparsers.add_parser(
        "detect-adrs",
        help="Detect ADR topics without generating files"
    )
    detect_parser.add_argument(
        "--prd",
        type=str,
        required=True,
        help="Path to PRD JSON file",
    )
    detect_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # topics command
    topics_parser = subparsers.add_parser(
        "topics",
        help="List available ADR topics and their keywords"
    )
    topics_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.command == "generate":
        result = generate_solutioning_artifacts(
            prd_path=args.prd,
            output_dir=args.output_dir,
            force=args.force,
            min_complexity=args.min_complexity,
        )

        if args.json:
            output = {
                "success": result.success,
                "architecture_path": result.architecture_path,
                "adr_paths": result.adr_paths,
                "skipped_reason": result.skipped_reason,
                "complexity_level": result.complexity_level,
                "detected_topics": result.detected_topics,
            }
            print(json.dumps(output, indent=2))
        else:
            if result.skipped_reason:
                print(f"Skipped: {result.skipped_reason}")
            elif result.success:
                print("Successfully generated solutioning artifacts:")
                if result.complexity_level is not None:
                    print(f"  Complexity Level: {result.complexity_level}")
                if result.architecture_path:
                    print(f"  Architecture: {result.architecture_path}")
                if result.adr_paths:
                    print(f"  ADRs ({len(result.adr_paths)}):")
                    for path in result.adr_paths:
                        print(f"    - {path}")
                if result.detected_topics:
                    print(f"  Topics: {', '.join(result.detected_topics)}")
            else:
                print(f"Error: {result.skipped_reason}")
                sys.exit(1)

    elif args.command == "detect-adrs":
        # Load PRD
        try:
            with open(args.prd, 'r') as f:
                prd_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading PRD: {e}", file=sys.stderr)
            sys.exit(1)

        prd_content = prd_data.get("description", "")
        results = detect_adr_topics(prd_content, prd_data)

        if args.json:
            output = [asdict(r) for r in results]
            print(json.dumps(output, indent=2))
        else:
            print("ADR Topic Detection Results:")
            print("-" * 60)
            for result in results:
                status = "GENERATE" if result.should_generate else "skip"
                print(f"\n[{status}] {result.topic}")
                print(f"  Title: {result.title}")
                print(f"  Matches: {result.match_count}")
                if result.keyword_matches:
                    print(f"  Keywords: {', '.join(result.keyword_matches[:5])}")

    elif args.command == "topics":
        if args.json:
            output = {}
            for topic, config in ADR_TOPICS.items():
                output[topic] = {
                    "title": config["title"],
                    "keywords": config["keywords"],
                    "options": config["options"],
                }
            print(json.dumps(output, indent=2))
        else:
            print("Available ADR Topics:")
            print("-" * 60)
            for topic, config in ADR_TOPICS.items():
                print(f"\n{topic}:")
                print(f"  Title: {config['title']}")
                print(f"  Keywords: {', '.join(config['keywords'][:8])}...")
                print(f"  Options: {len(config['options'])}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
