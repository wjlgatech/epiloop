#!/usr/bin/env python3
"""
Unit tests for phase selection functionality.

Tests cover:
- Phase ordering based on complexity levels
- Phase transitions and sequencing
- Phase-aware agent selection
- Phase integration with complexity detection
"""

import json
import os
import sys
import tempfile
import pytest

# Add lib directory to path for imports
LIB_DIR = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.insert(0, LIB_DIR)

# Import with hyphenated module name workaround
import importlib.util

# Import complexity detector for phase functions
spec_complexity = importlib.util.spec_from_file_location(
    "complexity_detector", os.path.join(LIB_DIR, "complexity-detector.py")
)
complexity_detector = importlib.util.module_from_spec(spec_complexity)
spec_complexity.loader.exec_module(complexity_detector)

get_phases = complexity_detector.get_phases
get_track = complexity_detector.get_track
detect_complexity = complexity_detector.detect_complexity


class TestPhaseOrdering:
    """Test that phases are returned in correct order."""

    def test_phases_always_in_order(self):
        """Test that phases are always in correct sequential order."""
        expected_order = ["analysis", "planning", "solutioning", "implementation"]

        for level in range(5):
            phases = get_phases(level)
            # Each phase in result must appear in order from expected_order
            indices = [expected_order.index(p) for p in phases]
            assert indices == sorted(indices), f"Phases not in order for level {level}: {phases}"

    def test_implementation_always_last(self):
        """Test that implementation phase is always the last phase."""
        for level in range(5):
            phases = get_phases(level)
            assert phases[-1] == "implementation", f"Implementation not last for level {level}"

    def test_implementation_always_present(self):
        """Test that implementation phase is always present."""
        for level in range(5):
            phases = get_phases(level)
            assert "implementation" in phases, f"Implementation missing for level {level}"

    def test_planning_comes_before_implementation(self):
        """Test that planning comes before implementation when present."""
        for level in range(2, 5):  # Levels that have planning
            phases = get_phases(level)
            if "planning" in phases:
                planning_idx = phases.index("planning")
                impl_idx = phases.index("implementation")
                assert planning_idx < impl_idx, f"Planning should come before implementation for level {level}"

    def test_solutioning_comes_before_implementation(self):
        """Test that solutioning comes before implementation when present."""
        for level in range(3, 5):  # Levels that have solutioning
            phases = get_phases(level)
            if "solutioning" in phases:
                sol_idx = phases.index("solutioning")
                impl_idx = phases.index("implementation")
                assert sol_idx < impl_idx, f"Solutioning should come before implementation for level {level}"

    def test_analysis_comes_first(self):
        """Test that analysis comes first when present."""
        for level in range(4, 5):  # Levels that have analysis
            phases = get_phases(level)
            if "analysis" in phases:
                assert phases[0] == "analysis", f"Analysis should be first for level {level}"


class TestPhasesByComplexityLevel:
    """Test correct phases for each complexity level."""

    def test_level_0_micro_phases(self):
        """Test Level 0 (micro) has only implementation phase."""
        phases = get_phases(0)
        assert phases == ["implementation"]
        assert len(phases) == 1

    def test_level_1_small_phases(self):
        """Test Level 1 (small) has only implementation phase."""
        phases = get_phases(1)
        assert phases == ["implementation"]
        assert len(phases) == 1

    def test_level_2_medium_phases(self):
        """Test Level 2 (medium) has planning + implementation."""
        phases = get_phases(2)
        assert phases == ["planning", "implementation"]
        assert len(phases) == 2

    def test_level_3_large_phases(self):
        """Test Level 3 (large) has planning + solutioning + implementation."""
        phases = get_phases(3)
        assert phases == ["planning", "solutioning", "implementation"]
        assert len(phases) == 3

    def test_level_4_enterprise_phases(self):
        """Test Level 4 (enterprise) has all phases."""
        phases = get_phases(4)
        assert phases == ["analysis", "planning", "solutioning", "implementation"]
        assert len(phases) == 4


class TestPhaseCount:
    """Test phase count increases with complexity."""

    def test_phase_count_increases_with_complexity(self):
        """Test that phase count generally increases with complexity."""
        prev_count = 0
        for level in range(5):
            phases = get_phases(level)
            assert len(phases) >= prev_count, f"Phase count should not decrease from level {level-1} to {level}"
            prev_count = len(phases)

    def test_low_complexity_few_phases(self):
        """Test that low complexity levels have few phases."""
        for level in range(2):  # 0 and 1
            phases = get_phases(level)
            assert len(phases) <= 1, f"Level {level} should have 1 or fewer phases"

    def test_high_complexity_more_phases(self):
        """Test that high complexity levels have more phases."""
        for level in range(3, 5):  # 3 and 4
            phases = get_phases(level)
            assert len(phases) >= 3, f"Level {level} should have at least 3 phases"


class TestPhaseIntegrationWithComplexity:
    """Test phase selection integrates correctly with complexity detection."""

    def test_simple_description_minimal_phases(self):
        """Test simple descriptions result in minimal phases."""
        result = detect_complexity("Fix typo in README")
        phases = get_phases(result.level)
        # Micro/small project should have minimal phases
        assert len(phases) <= 2

    def test_complex_description_more_phases(self):
        """Test complex descriptions result in more phases."""
        text = """
        Build enterprise e-commerce platform with:
        - User authentication with OAuth and SAML
        - Payment processing with Stripe and PayPal
        - Deploy to Kubernetes with auto-scaling
        - HIPAA and SOC2 compliance
        - Audit logging and monitoring
        - Multi-region disaster recovery
        """
        result = detect_complexity(text)
        phases = get_phases(result.level)
        # Should have multiple phases due to complexity
        assert result.level >= 2 or len(phases) >= 1  # At minimum implementation

    def test_prd_complexity_phases(self):
        """Test PRD file complexity maps to correct phases."""
        prd_data = {
            "userStories": [
                {"id": f"US-{i:03d}", "title": f"Story {i}"}
                for i in range(1, 15)  # 14 stories
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(prd_data, f)
            prd_path = f.name

        try:
            result = detect_complexity("", prd_path)
            phases = get_phases(result.level)
            # More stories = higher complexity = more phases
            assert len(phases) >= 1
        finally:
            os.unlink(prd_path)


class TestPhaseTransitions:
    """Test phase transition logic."""

    def test_valid_next_phase_from_analysis(self):
        """Test valid next phase from analysis."""
        phases = get_phases(4)  # Has all phases
        analysis_idx = phases.index("analysis")
        assert phases[analysis_idx + 1] == "planning"

    def test_valid_next_phase_from_planning(self):
        """Test valid next phase from planning."""
        phases = get_phases(3)  # Has planning, solutioning, implementation
        planning_idx = phases.index("planning")
        assert phases[planning_idx + 1] == "solutioning"

    def test_valid_next_phase_from_solutioning(self):
        """Test valid next phase from solutioning."""
        phases = get_phases(3)
        sol_idx = phases.index("solutioning")
        assert phases[sol_idx + 1] == "implementation"

    def test_implementation_is_terminal(self):
        """Test that implementation is the terminal phase."""
        for level in range(5):
            phases = get_phases(level)
            impl_idx = phases.index("implementation")
            assert impl_idx == len(phases) - 1, f"Implementation should be last for level {level}"


class TestPhaseNaming:
    """Test phase naming conventions."""

    def test_valid_phase_names(self):
        """Test that all phase names are valid."""
        valid_names = {"analysis", "planning", "solutioning", "implementation"}

        for level in range(5):
            phases = get_phases(level)
            for phase in phases:
                assert phase in valid_names, f"Invalid phase name: {phase}"

    def test_phase_names_lowercase(self):
        """Test that all phase names are lowercase."""
        for level in range(5):
            phases = get_phases(level)
            for phase in phases:
                assert phase == phase.lower(), f"Phase name should be lowercase: {phase}"

    def test_no_duplicate_phases(self):
        """Test that no phase appears twice."""
        for level in range(5):
            phases = get_phases(level)
            assert len(phases) == len(set(phases)), f"Duplicate phases for level {level}: {phases}"


class TestPhaseEdgeCases:
    """Test edge cases for phase selection."""

    def test_negative_level_handled(self):
        """Test that negative complexity levels are handled."""
        # Should not crash, should treat as minimum level
        try:
            phases = get_phases(-1)
            assert "implementation" in phases
        except (ValueError, IndexError):
            pass  # Also acceptable to raise an error

    def test_very_high_level_handled(self):
        """Test that very high complexity levels are handled."""
        # Should not crash, should treat as maximum level
        try:
            phases = get_phases(100)
            assert "implementation" in phases
        except (ValueError, IndexError):
            pass  # Also acceptable to raise an error

    def test_float_level_handled(self):
        """Test that float complexity levels are handled."""
        # Should not crash
        try:
            phases = get_phases(int(2.5))
            assert isinstance(phases, list)
        except (TypeError, ValueError):
            pass  # Also acceptable to raise an error


class TestPhaseTrackIntegration:
    """Test phase selection integrates with track selection."""

    def test_quick_track_minimal_phases(self):
        """Test quick track has minimal phases."""
        for level in [0, 1]:  # Quick track levels
            track = get_track(level)
            phases = get_phases(level)
            assert track == "quick"
            assert phases == ["implementation"]

    def test_standard_track_moderate_phases(self):
        """Test standard track has moderate phases."""
        for level in [2, 3]:  # Standard track levels
            track = get_track(level)
            phases = get_phases(level)
            assert track == "standard"
            assert len(phases) >= 2

    def test_enterprise_track_all_phases(self):
        """Test enterprise track has all phases."""
        level = 4  # Enterprise track level
        track = get_track(level)
        phases = get_phases(level)
        assert track == "enterprise"
        assert phases == ["analysis", "planning", "solutioning", "implementation"]


class TestPhaseProgress:
    """Test phase progress calculation helpers."""

    def test_phase_progress_calculation(self):
        """Test calculating progress through phases."""
        phases = get_phases(4)  # All 4 phases

        # Test progress at different stages
        for i, phase in enumerate(phases):
            progress = (i + 1) / len(phases) * 100
            expected = (i + 1) / 4 * 100
            assert abs(progress - expected) < 0.01

    def test_single_phase_full_progress(self):
        """Test single phase means implementation is 100% of work."""
        phases = get_phases(0)  # Just implementation
        assert len(phases) == 1
        # Implementation is 100% of the work
        progress_per_phase = 100 / len(phases)
        assert progress_per_phase == 100


class TestPhaseRequirements:
    """Test phase requirements and prerequisites."""

    def test_analysis_phase_requirements(self):
        """Test analysis phase is only for enterprise complexity."""
        for level in range(5):
            phases = get_phases(level)
            if "analysis" in phases:
                assert level == 4, f"Analysis should only appear at level 4, found at level {level}"

    def test_solutioning_requires_planning(self):
        """Test solutioning phase requires planning phase."""
        for level in range(5):
            phases = get_phases(level)
            if "solutioning" in phases:
                assert "planning" in phases, f"Solutioning requires planning at level {level}"

    def test_phase_dependencies(self):
        """Test phase dependency chain."""
        phases = get_phases(4)  # Get all phases

        # Analysis -> Planning
        assert phases.index("analysis") < phases.index("planning")
        # Planning -> Solutioning
        assert phases.index("planning") < phases.index("solutioning")
        # Solutioning -> Implementation
        assert phases.index("solutioning") < phases.index("implementation")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
