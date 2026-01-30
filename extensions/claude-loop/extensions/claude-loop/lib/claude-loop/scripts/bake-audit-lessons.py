#!/usr/bin/env python3
"""
Bake Self-Improvement Audit Lessons into Experience Store

Extracts key lessons from the audit and stores them as experiences in ChromaDB
so future iterations can semantically retrieve and apply these learnings.

Why Experience Store vs Code/Docs:
1. Semantic Search: Agents can find relevant lessons when facing similar issues
2. Runtime Retrieval: Lessons are actively queried during execution
3. Ranking: Helpful lessons bubble up in search results
4. Persistent Memory: Survives across sessions and branches

Why Not Just Code/Docs:
- Code: Lessons aren't executable, they're knowledge/patterns
- AGENTS.md: Static reference, not semantically searchable at runtime
- Docs: Agents don't read entire docs, they query experience store
"""

import json
import sys
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

# Import from experience-store.py using importlib (handles hyphenated filename)
_lib_dir = Path(__file__).parent.parent / "lib"
_store_path = _lib_dir / "experience-store.py"

try:
    _spec = importlib.util.spec_from_file_location("experience_store", _store_path)
    _store_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_store_module)
    ExperienceStore = _store_module.ExperienceStore
    DomainContext = _store_module.DomainContext
except (ImportError, AttributeError, FileNotFoundError) as e:
    print(f"Error: Cannot import ExperienceStore from {_store_path}")
    print(f"Details: {e}")
    print("Make sure lib/experience-store.py exists and ChromaDB is installed")
    sys.exit(1)


# Lessons extracted from self-improvement audit
AUDIT_LESSONS = [
    # Performance Lessons (US-002)
    {
        "id": "lesson-perf-001",
        "category": "performance",
        "context": "PRD parsing taking 2+ seconds for 20 stories",
        "problem": "Excessive jq subprocess calls - validation spawned 220 separate jq processes for 20 stories (11 calls per story)",
        "solution": "Batch jq queries into single pass per story. Use --argjson to pass index and check all fields in one jq invocation. Reduces 220 processes to 20.",
        "code_example": "jq -e --argjson i \"$i\" '.userStories[$i] | select(.id and .title and .priority)' prd.json",
        "impact": "80-90% reduction in validation time (1-2s → 100-200ms)",
        "tags": ["performance", "jq", "subprocess", "prd-parsing", "optimization"],
        "helpful_rate": 1.0,
        "story_id": "US-002",
        "confidence": "high"
    },
    {
        "id": "lesson-perf-002",
        "category": "performance",
        "context": "Model selection spawning Python subprocess for each worker in parallel execution",
        "problem": "Model selector spawned 10 separate Python processes for 10 workers (200-300ms each = 2-3s overhead)",
        "solution": "Pre-compute model assignments for entire batch before launching workers. Single Python call: python3 lib/model-selector.py analyze prd.json --json, then lookup cached assignments.",
        "code_example": "precompute_models() { python3 lib/model-selector.py analyze prd.json > models.json; }",
        "impact": "90% reduction in model selection overhead (2-3s → 200-300ms)",
        "tags": ["performance", "subprocess", "parallel", "model-selection", "caching"],
        "helpful_rate": 1.0,
        "story_id": "US-002",
        "confidence": "high"
    },
    {
        "id": "lesson-perf-003",
        "category": "performance",
        "context": "Logs growing unbounded to 28MB+ without cleanup",
        "problem": "No log rotation strategy. Worker logs, execution logs, and run logs accumulate indefinitely.",
        "solution": "Implement log rotation at 10MB, gzip old logs, cleanup workers older than 30 days. Use find with -mtime flag: find .claude-loop/workers -mtime +30 -exec rm -rf {} \\;",
        "code_example": "rotate_log() { if [ $(stat -f%z log.jsonl) -gt 10485760 ]; then gzip log.jsonl; > log.jsonl; fi; }",
        "impact": "70% disk usage reduction (28MB → 8MB)",
        "tags": ["performance", "disk", "logs", "cleanup", "rotation"],
        "helpful_rate": 1.0,
        "story_id": "US-002",
        "confidence": "high"
    },
    {
        "id": "lesson-perf-004",
        "category": "performance",
        "context": "Agent tier lookup performing O(n²) linear searches",
        "problem": "get_agent_tier() loops through 3 arrays (5+18+11=34 agents) linearly for each keyword match. With 50 keywords: 2,250 comparisons.",
        "solution": "Build lookup map once on script load using bash associative array. O(1) lookup instead of O(n). declare -A AGENT_TIERS; AGENT_TIERS[agent-name]=1",
        "code_example": "init_tier_map() { for a in \"${TIER1[@]}\"; do AGENT_TIERS[$a]=1; done; }",
        "impact": "80-90% reduction in agent selection (100-500ms → 10-50ms)",
        "tags": ["performance", "algorithm", "agent-selection", "optimization", "complexity"],
        "helpful_rate": 1.0,
        "story_id": "US-002",
        "confidence": "high"
    },

    # Security Lessons (US-004, US-006)
    {
        "id": "lesson-sec-001",
        "category": "security",
        "context": "Command injection vulnerability via subprocess.run(shell=True)",
        "problem": "Using shell=True allows command chaining (ls; rm -rf /), command substitution $(malicious), and pipe attacks (data | bash)",
        "solution": "ALWAYS use shell=False with explicit argument arrays. Parse commands with shlex.split(). Add command whitelist for sandbox mode. Validate against dangerous patterns.",
        "code_example": "subprocess.run(shlex.split(cmd), shell=False, timeout=30)",
        "impact": "Prevents complete system compromise (CVSS 9.8 vulnerability eliminated)",
        "tags": ["security", "command-injection", "subprocess", "critical", "vulnerability"],
        "helpful_rate": 1.0,
        "story_id": "US-004",
        "confidence": "high"
    },
    {
        "id": "lesson-sec-002",
        "category": "security",
        "context": "Path traversal via symlinks bypassing sandbox validation",
        "problem": "Using os.path.abspath() validates path but doesn't resolve symlinks. Attacker creates symlink to /etc/passwd, path validation passes.",
        "solution": "ALWAYS use os.path.realpath() to resolve symlinks BEFORE validation. Check resolved path is within allowed directory.",
        "code_example": "real_path = os.path.realpath(file_path); if not real_path.startswith(sandbox): raise PermissionError",
        "impact": "Prevents unauthorized file access outside sandbox (CVSS 9.1 vulnerability eliminated)",
        "tags": ["security", "path-traversal", "symlinks", "sandbox", "critical"],
        "helpful_rate": 1.0,
        "story_id": "US-004",
        "confidence": "high"
    },
    {
        "id": "lesson-sec-003",
        "category": "security",
        "context": "Command injection via eval with user-controlled data",
        "problem": "Using eval to build curl commands allows URL injection (http://evil.com'; rm -rf /) and payload injection",
        "solution": "NEVER use eval with user data. Use bash arrays with proper quoting: declare -a curl_args=(-X POST \"$url\" -d \"$data\")",
        "code_example": "curl_args=(-X POST \"$url\" -H \"Content-Type: application/json\" -d \"$payload\"); curl \"${curl_args[@]}\"",
        "impact": "Prevents remote code execution via webhooks (CVSS 8.0 vulnerability eliminated)",
        "tags": ["security", "eval", "command-injection", "webhook", "quoting"],
        "helpful_rate": 1.0,
        "story_id": "US-004",
        "confidence": "high"
    },

    # Safety Lessons (US-003, US-006)
    {
        "id": "lesson-safety-001",
        "category": "safety",
        "context": "TOCTOU race condition in session state updates",
        "problem": "Check-then-update pattern allows two processes to read same state, modify, and overwrite each other's changes. Data corruption in parallel mode.",
        "solution": "Use file locking with flock. Lock file before read, hold lock during update, release after write. exec 200>file.lock; flock 200; # critical section; flock -u 200",
        "code_example": "with_lock() { exec 200>\"$file.lock\"; flock 200; \"$@\"; flock -u 200; exec 200>&-; }",
        "impact": "Prevents data loss in multi-instance deployments and parallel execution",
        "tags": ["safety", "race-condition", "toctou", "file-locking", "concurrency"],
        "helpful_rate": 1.0,
        "story_id": "US-003",
        "confidence": "high"
    },
    {
        "id": "lesson-safety-002",
        "category": "safety",
        "context": "Bare except clauses catching all exceptions including SystemExit",
        "problem": "except: catches SystemExit, KeyboardInterrupt, MemoryError making debugging impossible. Violations of PEP 8.",
        "solution": "ALWAYS use specific exception types. For unknown errors: except Exception as e. Common types: json.JSONDecodeError, KeyError, ValueError, OSError.",
        "code_example": "try: data = json.loads(text); except (json.JSONDecodeError, KeyError) as e: log.error(f'Parse failed: {e}')",
        "impact": "Improves error visibility and debugging capability",
        "tags": ["safety", "exception-handling", "python", "debugging", "pep8"],
        "helpful_rate": 1.0,
        "story_id": "US-003",
        "confidence": "high"
    },
    {
        "id": "lesson-safety-003",
        "category": "safety",
        "context": "Missing input validation causing cryptic errors during execution",
        "problem": "CLI arguments and PRD fields accepted without validation. Negative numbers, invalid enums, non-existent files cause failures deep in execution.",
        "solution": "Validate ALL user input at startup (fail fast). Check: file existence, numeric ranges, enum values, field types. Aggregate errors and report all at once.",
        "code_example": "if [ $max_iter -lt 1 ]; then errors+=(\"max-iterations must be positive\"); fi",
        "impact": "Catches 90%+ of user input errors at startup with clear error messages",
        "tags": ["safety", "validation", "input", "cli", "fail-fast"],
        "helpful_rate": 1.0,
        "story_id": "US-006",
        "confidence": "high"
    },

    # Code Quality Lessons (US-001, US-006)
    {
        "id": "lesson-quality-001",
        "category": "code-quality",
        "context": "Duplicate code pattern found 20+ times across codebase",
        "problem": "jq PRD parsing duplicated 5 times (120 lines), error formatting 8 times (85 lines), timestamp generation 3 times (60 lines). Total: ~365 lines duplicate.",
        "solution": "Extract to shared functions in lib/common-utils.sh. Single source of truth. get_story_field(), format_error(), get_timestamp_ms().",
        "code_example": "get_story_field() { local prd=$1 story=$2 field=$3; jq -r --arg id \"$story\" --arg f \"$field\" '.userStories[]|select(.id==$id)|.[$f]' \"$prd\"; }",
        "impact": "Reduces codebase by ~365 lines, improves maintainability",
        "tags": ["code-quality", "duplication", "refactoring", "maintainability"],
        "helpful_rate": 0.9,
        "story_id": "US-001",
        "confidence": "high"
    },
    {
        "id": "lesson-quality-002",
        "category": "code-quality",
        "context": "Unquoted shell variables causing word splitting failures",
        "problem": "Unquoted variables like $file cause word splitting when path has spaces. ~200 instances found across codebase.",
        "solution": "ALWAYS quote shell variables: \"$var\". Exceptions: Arrays \"${arr[@]}\", numeric comparisons [ $n -gt 0 ], assignment var=$val.",
        "code_example": "for file in \"$FILES\"; do process \"$file\"; done  # Both quoted",
        "impact": "Prevents failures with filenames containing spaces or special characters",
        "tags": ["code-quality", "shell", "quoting", "word-splitting", "safety"],
        "helpful_rate": 1.0,
        "story_id": "US-006",
        "confidence": "high"
    },

    # Testing Lessons (US-008)
    {
        "id": "lesson-testing-001",
        "category": "testing",
        "context": "Need to prove performance issues are real before optimizing",
        "problem": "Theoretical performance claims without empirical evidence. Can't validate improvements without baseline.",
        "solution": "ALWAYS establish baseline benchmarks FIRST. Prove issue exists with real measurements. Then optimize. Then compare. Require minimum thresholds: Critical ≥50%, High ≥30%, Medium ≥15%.",
        "code_example": "time bash -c 'source lib/prd-parser.sh && validate_prd prd.json'  # Baseline",
        "impact": "Prevents wasted effort on non-issues, validates improvements are real",
        "tags": ["testing", "performance", "benchmarking", "empirical", "validation"],
        "helpful_rate": 1.0,
        "story_id": "US-008",
        "confidence": "high"
    },
    {
        "id": "lesson-testing-002",
        "category": "testing",
        "context": "Code optimizations introducing bloat and complexity",
        "problem": "Performance optimizations often add LOC and complexity. Without tracking, codebase becomes unmaintainable.",
        "solution": "Track code complexity metrics BEFORE and AFTER optimization. Require: LOC increase ≤10%, function size <100 lines, no new duplicate code.",
        "code_example": "grep -v '^\\s*#' file.sh | grep -v '^\\s*$' | wc -l  # Count LOC",
        "impact": "Prevents optimization bloat, maintains code quality",
        "tags": ["testing", "anti-bloat", "complexity", "metrics", "quality"],
        "helpful_rate": 1.0,
        "story_id": "US-008",
        "confidence": "high"
    },

    # Documentation Lessons (US-007)
    {
        "id": "lesson-docs-001",
        "category": "documentation",
        "context": "Complex algorithms difficult to understand without overview",
        "problem": "Implementation jumps straight into code without explaining algorithm, making maintenance difficult.",
        "solution": "Document algorithm BEFORE implementation: Overview, steps, time/space complexity, example. Use docstring for Python, comment block for shell.",
        "code_example": "# Topological sort using Kahn's algorithm\\n# 1. Calculate in-degree\\n# 2. Queue zero-degree nodes\\n# Time: O(V+E), Space: O(V)",
        "impact": "Improves code comprehension and maintainability",
        "tags": ["documentation", "algorithms", "maintainability", "comments"],
        "helpful_rate": 0.9,
        "story_id": "US-007",
        "confidence": "high"
    },

    # Meta-Lesson: Self-Improvement Process
    {
        "id": "lesson-meta-001",
        "category": "meta",
        "context": "Self-improvement audit identifying issues but lessons not integrated into runtime knowledge",
        "problem": "Audit findings only in markdown docs. Agents don't query docs during execution. Lessons not available for semantic retrieval.",
        "solution": "Bake lessons into experience store (ChromaDB) so future iterations can semantically retrieve when facing similar issues. Tag with story_id, category, and confidence.",
        "code_example": "python3 scripts/bake-audit-lessons.py  # Adds lessons to ChromaDB",
        "impact": "Enables continuous learning - future iterations benefit from audit findings",
        "tags": ["meta", "self-improvement", "knowledge-base", "experience-store", "learning"],
        "helpful_rate": 1.0,
        "story_id": "META",
        "confidence": "high"
    }
]


def bake_lessons_into_experience_store():
    """
    Store audit lessons in ChromaDB experience store.

    This makes lessons semantically searchable during execution so future
    iterations can retrieve relevant experiences when facing similar issues.
    """
    print("=" * 80)
    print("BAKING SELF-IMPROVEMENT AUDIT LESSONS INTO EXPERIENCE STORE")
    print("=" * 80)
    print()

    # Initialize experience store
    print("Initializing experience store...")
    try:
        store = ExperienceStore()
    except Exception as e:
        print(f"❌ Failed to initialize experience store: {e}")
        print("\nMake sure ChromaDB is installed:")
        print("  pip3 install chromadb")
        return 1

    print(f"✓ Experience store initialized")
    print()

    # Process each lesson
    success_count = 0
    fail_count = 0

    for lesson in AUDIT_LESSONS:
        lesson_id = lesson["id"]
        category = lesson["category"]

        print(f"Adding lesson: {lesson_id} ({category})")

        # Build problem signature (what to search for)
        problem = f"""
{category.upper()} - {lesson['context']}

Problem: {lesson['problem']}
Tags: {', '.join(lesson['tags'])}
""".strip()

        # Build solution (what to learn)
        solution = f"""
Solution: {lesson['solution']}

Code Example:
```
{lesson['code_example']}
```

Impact: {lesson['impact']}

Source: Self-Improvement Audit (Story {lesson['story_id']})
Confidence: {lesson['confidence']}
""".strip()

        # Prepare domain context and metadata
        domain_context = DomainContext(project_type='code-improvement')

        context_dict = {
            "lesson_id": lesson_id,
            "story_id": lesson.get("story_id", ""),
            "confidence": lesson.get("confidence", "medium"),
            "helpful_rate": lesson.get("helpful_rate", 0.5),
            "source": "self-improvement-audit"
        }

        try:
            # Record experience using correct API
            exp_id, success = store.record_experience(
                problem=problem,
                solution=solution,
                domain_context=domain_context,
                context=context_dict,
                category=category,
                tags=lesson["tags"]
            )
            if success:
                print(f"  ✓ Added: {lesson_id} (exp_id: {exp_id})")
                success_count += 1
            else:
                print(f"  ✗ Failed: {lesson_id} - record_experience returned False")
                fail_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {lesson_id} - {e}")
            fail_count += 1

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total lessons: {len(AUDIT_LESSONS)}")
    print(f"Successfully added: {success_count}")
    print(f"Failed: {fail_count}")
    print()

    # Test retrieval
    print("=" * 80)
    print("TESTING SEMANTIC RETRIEVAL")
    print("=" * 80)
    print()

    test_queries = [
        "PRD parsing is very slow",
        "command injection vulnerability",
        "race condition in file updates",
        "how to optimize subprocess calls"
    ]

    domain_context = DomainContext(project_type='code-improvement')

    for query in test_queries:
        print(f"Query: '{query}'")
        try:
            # search_similar returns List[Tuple[ExperienceEntry, float]]
            results = store.search_similar(
                problem=query,
                domain_context=domain_context,
                k=2,
                similarity_threshold=0.5
            )
            if results:
                for i, (entry, score) in enumerate(results, 1):
                    lesson_id = entry.context.get('lesson_id', 'unknown') if entry.context else 'unknown'
                    print(f"  {i}. {lesson_id} (score: {score:.3f})")
                    print(f"     Category: {entry.category}")
                    print(f"     Tags: {', '.join(entry.tags)}")
            else:
                print("  No results found")
        except Exception as e:
            print(f"  Error: {e}")
        print()

    print("=" * 80)
    print("LESSONS BAKED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print("Future iterations can now retrieve these lessons semantically.")
    print("Example: When an agent encounters 'PRD parsing slow', it will")
    print("automatically retrieve the lesson about batching jq calls.")
    print()

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(bake_lessons_into_experience_store())
