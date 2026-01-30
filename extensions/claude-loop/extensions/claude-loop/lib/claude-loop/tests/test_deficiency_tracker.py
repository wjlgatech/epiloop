#!/usr/bin/env python3
"""Tests for deficiency_tracker.py"""

import json
import pytest
import tempfile
from pathlib import Path
from lib.deficiency_tracker import (
    DeficiencyTracker,
    DeficiencyType,
    Deficiency
)


@pytest.fixture
def temp_deficiencies_file():
    """Create temporary deficiencies file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def tracker(temp_deficiencies_file):
    """Create deficiency tracker with temp file"""
    return DeficiencyTracker(deficiencies_file=temp_deficiencies_file)


def test_record_deficiency_new(tracker, temp_deficiencies_file):
    """Test recording a new deficiency"""
    deficiency_id = tracker.record_deficiency(
        deficiency_type=DeficiencyType.COORDINATOR_BUG,
        description="Unbound variable in deregister_prd",
        context={"file": "lib/prd-coordinator.sh", "line": 378},
        solution="Fixed variable name"
    )

    assert deficiency_id is not None
    assert len(deficiency_id) == 16  # SHA256 hash truncated to 16 chars

    # Verify file written
    with open(temp_deficiencies_file) as f:
        lines = f.readlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record['deficiency_type'] == "coordinator_bug"
        assert record['description'] == "Unbound variable in deregister_prd"
        assert record['frequency'] == 1
        assert record['remediation_status'] == "open"


def test_record_deficiency_duplicate(tracker):
    """Test recording same deficiency multiple times"""
    id1 = tracker.record_deficiency(
        deficiency_type=DeficiencyType.API_FAILURE,
        description="Rate limit exceeded",
        context={"provider": "anthropic"}
    )

    id2 = tracker.record_deficiency(
        deficiency_type=DeficiencyType.API_FAILURE,
        description="Rate limit exceeded",
        context={"provider": "openai"}
    )

    # Should be same ID (same type + description)
    assert id1 == id2

    # Frequency should increase
    deficiency = tracker._deficiencies[id1]
    assert deficiency.frequency == 2

    # Context should be merged
    assert 'provider' in deficiency.context


def test_record_deficiency_recurring(tracker):
    """Test that recurring deficiencies get suggestions"""
    for i in range(5):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.SILENT_FAILURE,
            description="Worker died without logging",
            context={"worker": f"worker-{i}"}
        )

    # Should have suggestions after 3+ occurrences
    deficiency_id = list(tracker._deficiencies.keys())[0]
    deficiency = tracker._deficiencies[deficiency_id]

    assert deficiency.frequency == 5
    assert len(deficiency.improvement_suggestions) > 0
    assert any('logging' in s.lower() for s in deficiency.improvement_suggestions)


def test_mark_fixed(tracker):
    """Test marking deficiency as fixed"""
    deficiency_id = tracker.record_deficiency(
        deficiency_type=DeficiencyType.LOGIC_ERROR,
        description="Null pointer error",
        solution="Added null check"
    )

    tracker.mark_fixed(deficiency_id, commit_hash="abc123", github_issue="#42")

    deficiency = tracker._deficiencies[deficiency_id]
    assert deficiency.remediation_status == "fixed"
    assert deficiency.remediation_commit == "abc123"
    assert deficiency.github_issue == "#42"


def test_mark_in_progress(tracker):
    """Test marking deficiency as in progress"""
    deficiency_id = tracker.record_deficiency(
        deficiency_type=DeficiencyType.RESOURCE_ISSUE,
        description="Memory leak in worker"
    )

    tracker.mark_in_progress(deficiency_id, github_issue="#43")

    deficiency = tracker._deficiencies[deficiency_id]
    assert deficiency.remediation_status == "in_progress"
    assert deficiency.github_issue == "#43"


def test_mark_nonexistent_deficiency(tracker):
    """Test marking nonexistent deficiency raises error"""
    with pytest.raises(ValueError):
        tracker.mark_fixed("nonexistent_id")


def test_detect_patterns(tracker):
    """Test pattern detection"""
    # Add recurring deficiency
    for i in range(5):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.API_FAILURE,
            description="Timeout connecting to API",
            context={"attempt": i}
        )

    # Add non-recurring deficiency
    tracker.record_deficiency(
        deficiency_type=DeficiencyType.LOGIC_ERROR,
        description="Edge case bug",
    )

    patterns = tracker.detect_patterns()

    # Should only have the recurring one
    assert len(patterns) == 1
    assert patterns[0]['frequency'] == 5
    assert patterns[0]['type'] == "api_failure"
    assert len(patterns[0]['suggestions']) > 0


def test_detect_patterns_sorted_by_frequency(tracker):
    """Test patterns are sorted by frequency"""
    # Add deficiencies with different frequencies
    for i in range(3):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Bug A"
        )

    for i in range(7):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Bug B"
        )

    for i in range(5):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Bug C"
        )

    patterns = tracker.detect_patterns()

    assert len(patterns) == 3
    assert patterns[0]['frequency'] == 7  # Bug B (most frequent)
    assert patterns[1]['frequency'] == 5  # Bug C
    assert patterns[2]['frequency'] == 3  # Bug A


def test_get_suggestions(tracker):
    """Test getting improvement suggestions"""
    # Add recurring deficiency
    for i in range(4):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.COORDINATOR_BUG,
            description="Race condition in registry"
        )

    suggestions = tracker.get_suggestions()

    assert len(suggestions) == 1
    assert suggestions[0]['type'] == "coordinator_bug"
    assert suggestions[0]['frequency'] == 4
    assert suggestions[0]['priority'] > 0
    assert len(suggestions[0]['suggestions']) > 0


def test_get_suggestions_filtered_by_type(tracker):
    """Test filtering suggestions by type"""
    # Add different types
    for i in range(3):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.API_FAILURE,
            description="API issue"
        )

    for i in range(4):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Logic bug"
        )

    api_suggestions = tracker.get_suggestions(deficiency_type=DeficiencyType.API_FAILURE)
    bug_suggestions = tracker.get_suggestions(deficiency_type=DeficiencyType.LOGIC_ERROR)

    assert len(api_suggestions) == 1
    assert api_suggestions[0]['type'] == "api_failure"

    assert len(bug_suggestions) == 1
    assert bug_suggestions[0]['type'] == "logic_error"


def test_get_suggestions_filtered_by_status(tracker):
    """Test filtering suggestions by remediation status"""
    deficiency_id = tracker.record_deficiency(
        deficiency_type=DeficiencyType.LOGIC_ERROR,
        description="Bug"
    )

    # Record multiple times to make it recurring
    for i in range(3):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Bug"
        )

    # Initially open
    open_suggestions = tracker.get_suggestions(status="open")
    assert len(open_suggestions) == 1

    # Mark fixed
    tracker.mark_fixed(deficiency_id)
    open_suggestions = tracker.get_suggestions(status="open")
    fixed_suggestions = tracker.get_suggestions(status="fixed")

    assert len(open_suggestions) == 0
    assert len(fixed_suggestions) == 1


def test_get_deficiency_stats(tracker):
    """Test getting deficiency statistics"""
    # Add various deficiencies
    for i in range(5):
        tracker.record_deficiency(DeficiencyType.API_FAILURE, "API error")

    for i in range(2):
        tracker.record_deficiency(DeficiencyType.LOGIC_ERROR, "Bug")

    tracker.record_deficiency(DeficiencyType.API_FAILURE, "Timeout")

    # Mark one as fixed
    deficiency_id = list(tracker._deficiencies.keys())[0]
    tracker.mark_fixed(deficiency_id)

    stats = tracker.get_deficiency_stats()

    assert stats['total'] == 3  # 3 unique deficiencies
    assert stats['by_type']['api_failure'] == 2  # API error + timeout (both API_FAILURE)
    assert stats['by_type']['logic_error'] == 1
    assert stats['by_status']['fixed'] == 1
    assert stats['by_status']['open'] == 2
    assert stats['recurring'] == 1  # Only API_FAILURE has freq >= 3


def test_export_for_experience_store(tracker):
    """Test exporting deficiency for experience store"""
    deficiency_id = tracker.record_deficiency(
        deficiency_type=DeficiencyType.COORDINATOR_BUG,
        description="Unbound variable",
        context={"file": "coordinator.sh", "line": 378},
        solution="Fixed variable name"
    )

    export = tracker.export_for_experience_store(deficiency_id)

    assert export['problem'] == "Unbound variable"
    assert export['solution'] == "Fixed variable name"
    assert export['context']['file'] == "coordinator.sh"
    assert export['deficiency_type'] == "coordinator_bug"
    assert export['frequency'] == 1


def test_export_nonexistent_deficiency(tracker):
    """Test exporting nonexistent deficiency raises error"""
    with pytest.raises(ValueError):
        tracker.export_for_experience_store("nonexistent_id")


def test_priority_calculation(tracker):
    """Test priority score calculation"""
    # High frequency, recent
    id1 = tracker.record_deficiency(
        deficiency_type=DeficiencyType.COORDINATOR_BUG,
        description="Critical bug"
    )
    for i in range(9):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.COORDINATOR_BUG,
            description="Critical bug"
        )

    # Low frequency
    id2 = tracker.record_deficiency(
        deficiency_type=DeficiencyType.LOGIC_ERROR,
        description="Minor bug"
    )

    priority1 = tracker._calculate_priority(tracker._deficiencies[id1])
    priority2 = tracker._calculate_priority(tracker._deficiencies[id2])

    # High frequency should have higher priority
    assert priority1 > priority2


def test_suggestions_coordinator_bug(tracker):
    """Test suggestions for coordinator bugs"""
    for i in range(3):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.COORDINATOR_BUG,
            description="Bug"
        )

    deficiency = list(tracker._deficiencies.values())[0]
    suggestions = deficiency.improvement_suggestions

    assert any('unit tests' in s.lower() for s in suggestions)
    assert any('integration tests' in s.lower() for s in suggestions)


def test_suggestions_silent_failure(tracker):
    """Test suggestions for silent failures"""
    for i in range(3):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.SILENT_FAILURE,
            description="Worker died"
        )

    deficiency = list(tracker._deficiencies.values())[0]
    suggestions = deficiency.improvement_suggestions

    assert any('logging' in s.lower() for s in suggestions)
    assert any('heartbeat' in s.lower() for s in suggestions)


def test_suggestions_high_frequency(tracker):
    """Test suggestions for high frequency deficiencies"""
    for i in range(6):
        tracker.record_deficiency(
            deficiency_type=DeficiencyType.LOGIC_ERROR,
            description="Frequent bug"
        )

    deficiency = list(tracker._deficiencies.values())[0]
    suggestions = deficiency.improvement_suggestions

    assert any('CRITICAL' in s for s in suggestions)
    assert any('automated prevention' in s.lower() for s in suggestions)


def test_persistence(temp_deficiencies_file):
    """Test deficiencies persist across instances"""
    # Create tracker and add deficiency
    tracker1 = DeficiencyTracker(deficiencies_file=temp_deficiencies_file)
    deficiency_id = tracker1.record_deficiency(
        deficiency_type=DeficiencyType.LOGIC_ERROR,
        description="Test bug"
    )

    # Create new tracker instance
    tracker2 = DeficiencyTracker(deficiencies_file=temp_deficiencies_file)

    # Should load existing deficiency
    assert deficiency_id in tracker2._deficiencies
    assert tracker2._deficiencies[deficiency_id].description == "Test bug"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
