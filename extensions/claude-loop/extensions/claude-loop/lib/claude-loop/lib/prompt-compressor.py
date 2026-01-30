#!/usr/bin/env python3
# pylint: disable=broad-except
"""
prompt-compressor.py - Prompt compression for claude-loop

Reduces token usage by:
- Filtering files to story.fileScope only
- Summarizing previous iterations instead of full history
- Referencing unchanged files by hash (not content)
- Estimating token counts before/after compression

Usage:
    # Compress prompt context for a specific story
    python3 lib/prompt-compressor.py compress <story_id> prd.json

    # Estimate token savings without compressing
    python3 lib/prompt-compressor.py estimate <story_id> prd.json

    # Get compressed file references (hash-based)
    python3 lib/prompt-compressor.py file-refs <story_id> prd.json

    # Summarize progress.txt for context
    python3 lib/prompt-compressor.py summarize-progress progress.txt

CLI Options:
    --full-context          Disable compression (include everything)
    --cache-dir DIR         Cache directory (default: .claude-loop/cache)
    --max-iterations N      Max iterations to include in summary (default: 5)
    --json                  Output as JSON
    --verbose               Enable verbose output
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# ============================================================================
# Constants
# ============================================================================

# Approximate characters per token (Claude tokenization)
CHARS_PER_TOKEN = 4

# Default cache directory
DEFAULT_CACHE_DIR = ".claude-loop/cache"

# Maximum iterations to include in progress summary
DEFAULT_MAX_ITERATIONS = 5


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TokenEstimate:
    """Token count estimation result."""
    original_tokens: int
    compressed_tokens: int
    saved_tokens: int
    compression_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileReference:
    """Reference to a file by hash instead of content."""
    file_path: str
    content_hash: str
    size_bytes: int
    changed: bool
    tokens_saved: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IterationSummary:
    """Summarized iteration from progress.txt."""
    story_id: str
    title: str
    status: str
    files_changed: List[str] = field(default_factory=list)
    key_learnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompressedContext:
    """Result of prompt compression."""
    story_id: str
    file_scope: List[str]
    file_references: List[FileReference]
    iteration_summary: str
    unchanged_files_note: str
    token_estimate: TokenEstimate
    full_context_mode: bool = False

    def to_dict(self) -> dict:
        result = asdict(self)
        result['file_references'] = [fr if isinstance(fr, dict) else fr.to_dict()
                                      for fr in self.file_references]
        result['token_estimate'] = self.token_estimate.to_dict() if hasattr(self.token_estimate, 'to_dict') else self.token_estimate
        return result


# ============================================================================
# Token Estimation Functions
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_file_tokens(file_path: str) -> int:
    """Estimate tokens for a file's contents."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return estimate_tokens(content)
    except (IOError, OSError):
        return 0


# ============================================================================
# File Hash Functions
# ============================================================================

def compute_file_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash of file contents."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError):
        return None


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


# ============================================================================
# Cache Integration
# ============================================================================

def load_cache_index(cache_dir: str) -> Dict[str, Any]:
    """Load cache index from context-cache.py's storage."""
    cache_index_path = Path(cache_dir) / "cache_index.json"
    if cache_index_path.exists():
        try:
            with open(cache_index_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"entries": {}, "stats": {"hits": 0, "misses": 0}}


def is_file_cached(file_path: str, cache_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if file is in cache and return its hash.

    Returns:
        Tuple of (is_cached, content_hash)
    """
    abs_path = os.path.abspath(file_path)
    entries = cache_data.get("entries", {})

    if abs_path in entries:
        entry = entries[abs_path]
        cached_mtime = entry.get("mtime", 0)

        # Check if file still exists and mtime matches
        try:
            current_mtime = os.path.getmtime(abs_path)
            if current_mtime == cached_mtime:
                return True, entry.get("content_hash")
        except OSError:
            pass

    return False, None


def check_file_changed(file_path: str, cache_data: Dict[str, Any]) -> bool:
    """Check if file has changed since last cache."""
    is_cached, cached_hash = is_file_cached(file_path, cache_data)

    if not is_cached:
        return True  # Not cached = treat as changed

    # Verify hash matches
    current_hash = compute_file_hash(file_path)
    return current_hash != cached_hash


# ============================================================================
# PRD and Story Functions
# ============================================================================

def load_prd(prd_file: str) -> Dict[str, Any]:
    """Load PRD from JSON file."""
    with open(prd_file, 'r') as f:
        return json.load(f)


def get_story(prd: Dict[str, Any], story_id: str) -> Optional[Dict[str, Any]]:
    """Get story by ID from PRD."""
    for story in prd.get("userStories", []):
        if story.get("id") == story_id:
            return story
    return None


def get_story_file_scope(story: Dict[str, Any]) -> List[str]:
    """Get file scope for a story."""
    return story.get("fileScope", [])


def get_all_file_scopes(prd: Dict[str, Any]) -> List[str]:
    """Get all unique file scopes across all stories."""
    all_files = set()
    for story in prd.get("userStories", []):
        for file_path in story.get("fileScope", []):
            all_files.add(file_path)
    return sorted(list(all_files))


# ============================================================================
# Progress Summary Functions
# ============================================================================

def parse_progress_file(progress_file: str) -> List[IterationSummary]:
    """Parse progress.txt into structured iteration summaries."""
    if not os.path.exists(progress_file):
        return []

    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, OSError):
        return []

    iterations = []

    # Split by iteration headers
    # Pattern: ### Iteration: DATE TIME
    iteration_pattern = r'###\s+Iteration:\s*(.+?)(?=###\s+Iteration:|$)'
    matches = re.findall(iteration_pattern, content, re.DOTALL)

    for match in matches:
        iteration_text = match.strip()

        # Parse story info
        story_match = re.search(r'\*\*Story\*\*:\s*(\S+)\s*-\s*(.+?)(?=\n|$)', iteration_text)
        if not story_match:
            continue

        story_id = story_match.group(1)
        title = story_match.group(2).strip()

        # Parse status
        status_match = re.search(r'\*\*Status\*\*:\s*(.+?)(?=\n|$)', iteration_text)
        status = status_match.group(1).strip() if status_match else "Unknown"

        # Parse files changed
        files_changed = []
        files_section = re.search(r'\*\*Files changed\*\*:(.+?)(?=\*\*|$)', iteration_text, re.DOTALL)
        if files_section:
            files_text = files_section.group(1)
            files_changed = [f.strip().lstrip('- ') for f in files_text.strip().split('\n') if f.strip().startswith('-')]

        # Parse key learnings
        learnings = []
        learnings_section = re.search(r'\*\*Learnings.*?\*\*:(.+?)(?=---|$)', iteration_text, re.DOTALL)
        if learnings_section:
            learnings_text = learnings_section.group(1)
            learnings = [l.strip().lstrip('- ') for l in learnings_text.strip().split('\n') if l.strip().startswith('-')]

        iterations.append(IterationSummary(
            story_id=story_id,
            title=title,
            status=status,
            files_changed=files_changed,
            key_learnings=learnings[:3]  # Keep top 3 learnings
        ))

    return iterations


def summarize_iterations(iterations: List[IterationSummary], max_iterations: int = DEFAULT_MAX_ITERATIONS) -> str:
    """Create a condensed summary of recent iterations."""
    if not iterations:
        return "No previous iterations recorded."

    # Take most recent iterations
    recent = iterations[-max_iterations:]

    lines = [f"## Previous Iterations Summary (last {len(recent)})"]
    lines.append("")

    for iteration in recent:
        status_icon = "✓" if iteration.status.lower() == "complete" else "○"
        lines.append(f"- {status_icon} **{iteration.story_id}**: {iteration.title}")

        if iteration.files_changed:
            files_preview = ", ".join(iteration.files_changed[:3])
            if len(iteration.files_changed) > 3:
                files_preview += f" (+{len(iteration.files_changed) - 3} more)"
            lines.append(f"  - Files: {files_preview}")

        if iteration.key_learnings:
            lines.append(f"  - Key learning: {iteration.key_learnings[0]}")

    return "\n".join(lines)


def get_full_progress_content(progress_file: str) -> str:
    """Get full progress.txt content for --full-context mode."""
    if not os.path.exists(progress_file):
        return ""
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            return f.read()
    except (IOError, OSError):
        return ""


# ============================================================================
# Prompt Compression Functions
# ============================================================================

def create_file_references(
    file_scope: List[str],
    cache_data: Dict[str, Any],
    full_context: bool = False
) -> List[FileReference]:
    """Create file references for story's file scope.

    In compressed mode, unchanged files are referenced by hash only.
    In full context mode, all files are marked as changed (content included).
    """
    references = []

    for file_path in file_scope:
        if not os.path.exists(file_path):
            continue

        content_hash = compute_file_hash(file_path)
        size_bytes = get_file_size(file_path)

        if full_context:
            changed = True
            tokens_saved = 0
        else:
            changed = check_file_changed(file_path, cache_data)
            # If not changed, we save the tokens by referencing by hash
            tokens_saved = estimate_file_tokens(file_path) if not changed else 0

        references.append(FileReference(
            file_path=file_path,
            content_hash=content_hash or "",
            size_bytes=size_bytes,
            changed=changed,
            tokens_saved=tokens_saved
        ))

    return references


def create_unchanged_files_note(file_references: List[FileReference]) -> str:
    """Create a note about unchanged files for the prompt."""
    unchanged = [fr for fr in file_references if not fr.changed]

    if not unchanged:
        return ""

    lines = [
        "## Unchanged Files (Reference by Hash)",
        "",
        "The following files have not changed since last iteration.",
        "They are referenced by content hash to save tokens:",
        ""
    ]

    for fr in unchanged:
        short_hash = fr.content_hash[:12] if fr.content_hash else "unknown"
        lines.append(f"- `{fr.file_path}` (hash: `{short_hash}...`)")

    lines.append("")
    lines.append("*Use file hash to verify consistency. Read file only if modification needed.*")

    return "\n".join(lines)


def compress_context(
    story_id: str,
    prd_file: str,
    progress_file: str = "progress.txt",
    cache_dir: str = DEFAULT_CACHE_DIR,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    full_context: bool = False
) -> CompressedContext:
    """Compress prompt context for a story.

    Args:
        story_id: The story ID to compress context for
        prd_file: Path to prd.json
        progress_file: Path to progress.txt
        cache_dir: Path to cache directory
        max_iterations: Max iterations to include in summary
        full_context: If True, disable compression

    Returns:
        CompressedContext with all compressed elements
    """
    # Load PRD and get story
    prd = load_prd(prd_file)
    story = get_story(prd, story_id)

    if not story:
        raise ValueError(f"Story not found: {story_id}")

    # Get file scope
    file_scope = get_story_file_scope(story)

    # Load cache data
    cache_data = load_cache_index(cache_dir)

    # Create file references
    file_references = create_file_references(file_scope, cache_data, full_context)

    # Parse and summarize progress
    iterations = parse_progress_file(progress_file)

    if full_context:
        iteration_summary = get_full_progress_content(progress_file)
    else:
        iteration_summary = summarize_iterations(iterations, max_iterations)

    # Create unchanged files note
    unchanged_note = "" if full_context else create_unchanged_files_note(file_references)

    # Estimate tokens
    original_tokens = estimate_original_tokens(file_scope, progress_file)
    compressed_tokens = estimate_compressed_tokens(file_references, iteration_summary, unchanged_note)
    saved_tokens = max(0, original_tokens - compressed_tokens)
    compression_ratio = (saved_tokens / original_tokens * 100) if original_tokens > 0 else 0

    token_estimate = TokenEstimate(
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        saved_tokens=saved_tokens,
        compression_ratio=round(compression_ratio, 2)
    )

    return CompressedContext(
        story_id=story_id,
        file_scope=file_scope,
        file_references=file_references,
        iteration_summary=iteration_summary,
        unchanged_files_note=unchanged_note,
        token_estimate=token_estimate,
        full_context_mode=full_context
    )


def estimate_original_tokens(file_scope: List[str], progress_file: str) -> int:
    """Estimate tokens if we included all file contents and full progress."""
    total = 0

    # Add file contents
    for file_path in file_scope:
        total += estimate_file_tokens(file_path)

    # Add progress file
    if os.path.exists(progress_file):
        total += estimate_file_tokens(progress_file)

    return total


def estimate_compressed_tokens(
    file_references: List[FileReference],
    iteration_summary: str,
    unchanged_note: str
) -> int:
    """Estimate tokens after compression."""
    total = 0

    # Changed files still contribute full content
    for fr in file_references:
        if fr.changed:
            total += fr.size_bytes // CHARS_PER_TOKEN
        else:
            # Hash reference is much smaller
            total += 50  # Approximate tokens for hash reference line

    # Add summary and note
    total += estimate_tokens(iteration_summary)
    total += estimate_tokens(unchanged_note)

    return total


# ============================================================================
# Output Formatting Functions
# ============================================================================

def format_compressed_prompt_section(context: CompressedContext) -> str:
    """Format the compressed context as a prompt section."""
    lines = []

    if context.full_context_mode:
        lines.append("# Context (Full Mode)")
        lines.append("")
        lines.append("*Running in full context mode - no compression applied.*")
    else:
        lines.append("# Compressed Context")
        lines.append("")
        lines.append(f"**Token Savings**: {context.token_estimate.saved_tokens:,} tokens ({context.token_estimate.compression_ratio:.1f}% reduction)")

    lines.append("")

    # File scope section
    lines.append("## File Scope")
    lines.append("")
    for file_path in context.file_scope:
        lines.append(f"- `{file_path}`")

    lines.append("")

    # Unchanged files note
    if context.unchanged_files_note:
        lines.append(context.unchanged_files_note)
        lines.append("")

    # Iteration summary
    lines.append(context.iteration_summary)

    return "\n".join(lines)


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_compress(args: argparse.Namespace) -> int:
    """Compress prompt context for a story."""
    try:
        context = compress_context(
            story_id=args.story_id,
            prd_file=args.prd_file,
            progress_file=args.progress_file,
            cache_dir=args.cache_dir,
            max_iterations=args.max_iterations,
            full_context=args.full_context
        )

        if args.json:
            print(json.dumps(context.to_dict(), indent=2))
        else:
            print(format_compressed_prompt_section(context))

        return 0
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_estimate(args: argparse.Namespace) -> int:
    """Estimate token savings for a story."""
    try:
        context = compress_context(
            story_id=args.story_id,
            prd_file=args.prd_file,
            progress_file=args.progress_file,
            cache_dir=args.cache_dir,
            max_iterations=args.max_iterations,
            full_context=False  # Always estimate with compression
        )

        estimate = context.token_estimate

        if args.json:
            print(json.dumps(estimate.to_dict(), indent=2))
        else:
            print("Token Estimate:")
            print(f"  Original tokens:   {estimate.original_tokens:,}")
            print(f"  Compressed tokens: {estimate.compressed_tokens:,}")
            print(f"  Saved tokens:      {estimate.saved_tokens:,}")
            print(f"  Compression ratio: {estimate.compression_ratio:.1f}%")

        return 0
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_file_refs(args: argparse.Namespace) -> int:
    """Get file references for a story."""
    try:
        prd = load_prd(args.prd_file)
        story = get_story(prd, args.story_id)

        if not story:
            print(f"Error: Story not found: {args.story_id}", file=sys.stderr)
            return 1

        file_scope = get_story_file_scope(story)
        cache_data = load_cache_index(args.cache_dir)
        references = create_file_references(file_scope, cache_data, args.full_context)

        if args.json:
            result = {
                "story_id": args.story_id,
                "file_scope": file_scope,
                "references": [fr.to_dict() for fr in references],
                "changed_count": sum(1 for fr in references if fr.changed),
                "unchanged_count": sum(1 for fr in references if not fr.changed),
                "total_tokens_saved": sum(fr.tokens_saved for fr in references)
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"File References for {args.story_id}:")
            print()
            for fr in references:
                status = "CHANGED" if fr.changed else "unchanged"
                short_hash = fr.content_hash[:12] if fr.content_hash else "n/a"
                saved = f" (saves ~{fr.tokens_saved:,} tokens)" if fr.tokens_saved > 0 else ""
                print(f"  [{status}] {fr.file_path}")
                print(f"           hash: {short_hash}...{saved}")

        return 0
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_summarize_progress(args: argparse.Namespace) -> int:
    """Summarize progress.txt."""
    try:
        iterations = parse_progress_file(args.progress_file)
        summary = summarize_iterations(iterations, args.max_iterations)

        if args.json:
            result = {
                "total_iterations": len(iterations),
                "summarized_count": min(len(iterations), args.max_iterations),
                "iterations": [it.to_dict() for it in iterations[-args.max_iterations:]],
                "summary": summary
            }
            print(json.dumps(result, indent=2))
        else:
            print(summary)

        return 0
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ============================================================================
# CLI Parser
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with shared options."""
    # Parent parser with shared options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help=f"Cache directory (default: {DEFAULT_CACHE_DIR})"
    )
    parent_parser.add_argument(
        "--full-context",
        action="store_true",
        help="Disable compression (include everything)"
    )
    parent_parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Max iterations to include in summary (default: {DEFAULT_MAX_ITERATIONS})"
    )
    parent_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parent_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    # Main parser
    parser = argparse.ArgumentParser(
        description="Prompt compression for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser]
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # compress command
    compress_parser = subparsers.add_parser(
        "compress",
        help="Compress prompt context for a story",
        parents=[parent_parser]
    )
    compress_parser.add_argument("story_id", help="Story ID")
    compress_parser.add_argument("prd_file", help="Path to prd.json")
    compress_parser.add_argument(
        "--progress-file",
        default="progress.txt",
        help="Path to progress.txt (default: progress.txt)"
    )

    # estimate command
    estimate_parser = subparsers.add_parser(
        "estimate",
        help="Estimate token savings for a story",
        parents=[parent_parser]
    )
    estimate_parser.add_argument("story_id", help="Story ID")
    estimate_parser.add_argument("prd_file", help="Path to prd.json")
    estimate_parser.add_argument(
        "--progress-file",
        default="progress.txt",
        help="Path to progress.txt (default: progress.txt)"
    )

    # file-refs command
    file_refs_parser = subparsers.add_parser(
        "file-refs",
        help="Get file references for a story",
        parents=[parent_parser]
    )
    file_refs_parser.add_argument("story_id", help="Story ID")
    file_refs_parser.add_argument("prd_file", help="Path to prd.json")

    # summarize-progress command
    summarize_parser = subparsers.add_parser(
        "summarize-progress",
        help="Summarize progress.txt",
        parents=[parent_parser]
    )
    summarize_parser.add_argument("progress_file", help="Path to progress.txt")

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    commands = {
        "compress": cmd_compress,
        "estimate": cmd_estimate,
        "file-refs": cmd_file_refs,
        "summarize-progress": cmd_summarize_progress,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
