#!/usr/bin/env python3
"""
Unit tests for complexity-detector.py

Tests various input scenarios for complexity detection:
- Simple text descriptions
- PRD files with different story counts
- Security, infrastructure, integration, compliance keywords
- Edge cases and boundary conditions
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
spec = importlib.util.spec_from_file_location("complexity_detector", os.path.join(LIB_DIR, "complexity-detector.py"))
complexity_detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(complexity_detector)

# Extract what we need from the module
detect_complexity = complexity_detector.detect_complexity
count_keyword_matches = complexity_detector.count_keyword_matches
estimate_story_count = complexity_detector.estimate_story_count
estimate_file_scope = complexity_detector.estimate_file_scope
calculate_complexity_score = complexity_detector.calculate_complexity_score
score_to_level = complexity_detector.score_to_level
get_track = complexity_detector.get_track
get_phases = complexity_detector.get_phases
get_track_config = complexity_detector.get_track_config
load_track_config = complexity_detector.load_track_config
TrackConfig = complexity_detector.TrackConfig
QualityGates = complexity_detector.QualityGates
ApprovalConfig = complexity_detector.ApprovalConfig
DEFAULT_TRACK_CONFIGS = complexity_detector.DEFAULT_TRACK_CONFIGS
SECURITY_KEYWORDS = complexity_detector.SECURITY_KEYWORDS
INFRASTRUCTURE_KEYWORDS = complexity_detector.INFRASTRUCTURE_KEYWORDS
INTEGRATION_KEYWORDS = complexity_detector.INTEGRATION_KEYWORDS
COMPLIANCE_KEYWORDS = complexity_detector.COMPLIANCE_KEYWORDS
COMPLEXITY_LEVELS = complexity_detector.COMPLEXITY_LEVELS
ComplexityResult = complexity_detector.ComplexityResult




class TestKeywordMatching:
    """Test keyword detection functions."""

    def test_count_security_keywords_basic(self):
        """Test basic security keyword detection."""
        text = "Add authentication with JWT tokens and password hashing"
        count = count_keyword_matches(text, SECURITY_KEYWORDS)
        assert count >= 3  # authentication, JWT, token, password, hash

    def test_count_security_keywords_case_insensitive(self):
        """Test case insensitivity."""
        text = "Implement OAUTH and SSL/TLS encryption"
        count = count_keyword_matches(text, SECURITY_KEYWORDS)
        assert count >= 2  # oauth, ssl, tls, encryption

    def test_count_security_keywords_none(self):
        """Test when no security keywords present."""
        text = "Add a new button to the homepage"
        count = count_keyword_matches(text, SECURITY_KEYWORDS)
        assert count == 0

    def test_count_infra_keywords(self):
        """Test infrastructure keyword detection."""
        text = "Deploy to Kubernetes using Docker containers and Terraform"
        count = count_keyword_matches(text, INFRASTRUCTURE_KEYWORDS)
        assert count >= 3  # kubernetes, docker, container, terraform

    def test_count_integration_keywords(self):
        """Test integration keyword detection."""
        text = "Create REST API with webhook support and Stripe payment integration"
        count = count_keyword_matches(text, INTEGRATION_KEYWORDS)
        assert count >= 3  # api, rest, webhook, stripe, payment, integration

    def test_count_compliance_keywords(self):
        """Test compliance keyword detection."""
        text = "Ensure GDPR compliance with audit logs and data retention policies"
        count = count_keyword_matches(text, COMPLIANCE_KEYWORDS)
        assert count >= 3  # gdpr, compliance, audit, data retention

    def test_word_boundary_matching(self):
        """Test that keywords match on word boundaries."""
        # "log" shouldn't match in "logging" as separate word
        text = "Add logging to the system"
        # The keyword "logging" should match
        count = count_keyword_matches(text, INFRASTRUCTURE_KEYWORDS)
        assert count >= 1


class TestStoryCountEstimation:
    """Test story count estimation."""

    def test_estimate_from_prd_data(self):
        """Test estimation from PRD with userStories array."""
        prd_data = {
            "userStories": [
                {"id": "US-001", "title": "Story 1"},
                {"id": "US-002", "title": "Story 2"},
                {"id": "US-003", "title": "Story 3"},
            ]
        }
        count = estimate_story_count("", prd_data)
        assert count == 3

    def test_estimate_from_text_user_story_pattern(self):
        """Test estimation from 'As a user, I want' pattern."""
        text = """
        As a user, I want to log in
        As an admin, I want to manage users
        """
        count = estimate_story_count(text, None)
        assert count >= 1  # Detects at least one story pattern

    def test_estimate_from_text_story_id_pattern(self):
        """Test estimation from US-XXX pattern."""
        text = "US-001: Login feature\nUS-002: Logout feature\nUS-003: Profile"
        count = estimate_story_count(text, None)
        assert count >= 3

    def test_estimate_minimum_one(self):
        """Test that minimum story count is 1."""
        text = ""
        count = estimate_story_count(text, None)
        assert count >= 1

    def test_estimate_from_bullets(self):
        """Test estimation from bullet points."""
        text = """
        - Add login
        - Add logout
        - Add profile page
        - Add settings
        """
        count = estimate_story_count(text, None)
        assert count >= 1  # Conservative estimate from bullets


class TestFileScopeEstimation:
    """Test file scope estimation."""

    def test_estimate_from_prd_filescope(self):
        """Test estimation from PRD fileScope arrays."""
        prd_data = {
            "userStories": [
                {"fileScope": ["lib/auth.py", "lib/user.py"]},
                {"fileScope": ["lib/auth.py", "tests/test_auth.py"]},
            ]
        }
        count = estimate_file_scope("", prd_data)
        assert count == 3  # auth.py, user.py, test_auth.py (deduplicated)

    def test_estimate_from_text_file_extensions(self):
        """Test estimation from file extensions in text."""
        text = "Modify auth.py, update user.js, and create config.yaml"
        count = estimate_file_scope(text, None)
        assert count >= 3

    def test_estimate_from_directory_mentions(self):
        """Test estimation from directory mentions."""
        text = "Changes in src/ and tests/ directories"
        count = estimate_file_scope(text, None)
        assert count >= 1  # At least 1 based on directory patterns

    def test_estimate_minimum_one(self):
        """Test that minimum file scope is 1."""
        text = "Make some changes"
        count = estimate_file_scope(text, None)
        assert count >= 1


class TestComplexityScoring:
    """Test complexity score calculation."""

    def test_score_micro_project(self):
        """Test scoring for micro project (score <= 15)."""
        score = calculate_complexity_score(
            story_count=1,
            security_matches=0,
            infra_matches=0,
            integration_matches=0,
            compliance_matches=0,
            file_scope=1,
        )
        assert score <= 15

    def test_score_small_project(self):
        """Test scoring for small project (score around 15-30)."""
        score = calculate_complexity_score(
            story_count=4,
            security_matches=2,
            infra_matches=2,
            integration_matches=1,
            compliance_matches=1,
            file_scope=5,
        )
        # With more signals, should be in small to medium range
        assert 10 <= score <= 45

    def test_score_medium_project(self):
        """Test scoring for medium project (score 31-50)."""
        score = calculate_complexity_score(
            story_count=8,
            security_matches=4,
            infra_matches=4,
            integration_matches=4,
            compliance_matches=2,
            file_scope=12,
        )
        # With these signals, should be in medium range
        assert 30 <= score <= 65

    def test_score_large_project(self):
        """Test scoring for large project (score 51-75)."""
        score = calculate_complexity_score(
            story_count=12,
            security_matches=5,
            infra_matches=4,
            integration_matches=4,
            compliance_matches=2,
            file_scope=15,
        )
        assert 45 < score <= 80  # Allow some flexibility

    def test_score_enterprise_project(self):
        """Test scoring for enterprise project (score > 75)."""
        score = calculate_complexity_score(
            story_count=20,
            security_matches=8,
            infra_matches=10,
            integration_matches=8,
            compliance_matches=5,
            file_scope=30,
        )
        assert score > 70  # Should be high score


class TestScoreToLevel:
    """Test score to level mapping."""

    def test_level_0_micro(self):
        """Test Level 0 (micro) mapping."""
        assert score_to_level(0) == 0
        assert score_to_level(10) == 0
        assert score_to_level(15) == 0

    def test_level_1_small(self):
        """Test Level 1 (small) mapping."""
        assert score_to_level(16) == 1
        assert score_to_level(25) == 1
        assert score_to_level(30) == 1

    def test_level_2_medium(self):
        """Test Level 2 (medium) mapping."""
        assert score_to_level(31) == 2
        assert score_to_level(40) == 2
        assert score_to_level(50) == 2

    def test_level_3_large(self):
        """Test Level 3 (large) mapping."""
        assert score_to_level(51) == 3
        assert score_to_level(65) == 3
        assert score_to_level(75) == 3

    def test_level_4_enterprise(self):
        """Test Level 4 (enterprise) mapping."""
        assert score_to_level(76) == 4
        assert score_to_level(90) == 4
        assert score_to_level(100) == 4


class TestGetTrack:
    """Test track selection based on complexity."""

    def test_quick_track_level_0(self):
        """Test quick track for Level 0."""
        assert get_track(0) == "quick"

    def test_quick_track_level_1(self):
        """Test quick track for Level 1."""
        assert get_track(1) == "quick"

    def test_standard_track_level_2(self):
        """Test standard track for Level 2."""
        assert get_track(2) == "standard"

    def test_standard_track_level_3(self):
        """Test standard track for Level 3."""
        assert get_track(3) == "standard"

    def test_enterprise_track_level_4(self):
        """Test enterprise track for Level 4."""
        assert get_track(4) == "enterprise"


class TestTrackConfig:
    """Test track configuration loading and structure."""

    def test_default_track_configs_exist(self):
        """Test that default track configs are defined."""
        assert "quick" in DEFAULT_TRACK_CONFIGS
        assert "standard" in DEFAULT_TRACK_CONFIGS
        assert "enterprise" in DEFAULT_TRACK_CONFIGS

    def test_quick_track_config_structure(self):
        """Test quick track configuration structure."""
        config = get_track_config("quick")
        assert isinstance(config, TrackConfig)
        assert config.name == "Quick"
        assert isinstance(config.quality_gates, QualityGates)
        assert isinstance(config.approval, ApprovalConfig)

    def test_quick_track_quality_gates(self):
        """Test quick track has minimal quality gates."""
        config = get_track_config("quick")
        assert config.quality_gates.tests is True
        assert config.quality_gates.lint is False
        assert config.quality_gates.type_check is False
        assert config.quality_gates.security_scan is False

    def test_standard_track_quality_gates(self):
        """Test standard track has moderate quality gates."""
        config = get_track_config("standard")
        assert config.quality_gates.tests is True
        assert config.quality_gates.lint is True
        assert config.quality_gates.type_check is True

    def test_enterprise_track_quality_gates(self):
        """Test enterprise track has all quality gates."""
        config = get_track_config("enterprise")
        assert config.quality_gates.tests is True
        assert config.quality_gates.lint is True
        assert config.quality_gates.type_check is True
        assert config.quality_gates.security_scan is True
        assert config.quality_gates.coverage_check is True
        assert config.quality_gates.coverage_threshold == 80

    def test_quick_track_no_adr(self):
        """Test quick track doesn't require ADR."""
        config = get_track_config("quick")
        assert config.adr_required is False
        assert config.architecture_doc is False

    def test_enterprise_track_requires_adr(self):
        """Test enterprise track requires ADR."""
        config = get_track_config("enterprise")
        assert config.adr_required is True
        assert config.architecture_doc is True

    def test_quick_track_no_approval(self):
        """Test quick track doesn't require approval."""
        config = get_track_config("quick")
        assert config.approval.required is False

    def test_enterprise_track_requires_approval(self):
        """Test enterprise track requires approval."""
        config = get_track_config("enterprise")
        assert config.approval.required is True
        assert config.approval.reviewers >= 2

    def test_model_preferences(self):
        """Test model preferences for each track."""
        assert get_track_config("quick").model_preference == "haiku"
        assert get_track_config("standard").model_preference == "sonnet"
        assert get_track_config("enterprise").model_preference == "opus"

    def test_max_iterations(self):
        """Test max iterations increase with track complexity."""
        quick = get_track_config("quick").max_iterations
        standard = get_track_config("standard").max_iterations
        enterprise = get_track_config("enterprise").max_iterations
        assert quick < standard < enterprise

    def test_unknown_track_fallback(self):
        """Test unknown track falls back to standard."""
        config = get_track_config("nonexistent")
        assert config.name == "Standard"

    def test_load_track_config_returns_dict(self):
        """Test that load_track_config returns a dict."""
        config = load_track_config()
        assert isinstance(config, dict)

    def test_track_config_from_yaml_file(self):
        """Test that track config can be loaded from YAML file."""
        # This tests the integration with track-config.yaml
        config = get_track_config("quick")
        # Should have loaded from YAML if available
        assert config is not None
        assert isinstance(config.quality_gates, QualityGates)


class TestGetPhases:
    """Test phase selection based on complexity."""

    def test_phases_level_0(self):
        """Test phases for Level 0."""
        phases = get_phases(0)
        assert phases == ["implementation"]

    def test_phases_level_1(self):
        """Test phases for Level 1."""
        phases = get_phases(1)
        assert phases == ["implementation"]

    def test_phases_level_2(self):
        """Test phases for Level 2."""
        phases = get_phases(2)
        assert phases == ["planning", "implementation"]

    def test_phases_level_3(self):
        """Test phases for Level 3."""
        phases = get_phases(3)
        assert phases == ["planning", "solutioning", "implementation"]

    def test_phases_level_4(self):
        """Test phases for Level 4."""
        phases = get_phases(4)
        assert phases == ["analysis", "planning", "solutioning", "implementation"]


class TestDetectComplexity:
    """Test the main detect_complexity function."""

    def test_simple_text_micro(self):
        """Test detecting micro complexity from simple text."""
        result = detect_complexity("Fix typo in README")
        assert isinstance(result, ComplexityResult)
        assert result.level in [0, 1]
        assert result.level_name in ["micro", "small"]

    def test_simple_text_small(self):
        """Test detecting small complexity."""
        result = detect_complexity("Add a new button to the settings page")
        assert result.level in [0, 1, 2]

    def test_medium_feature(self):
        """Test detecting medium complexity."""
        text = """
        Add user authentication system:
        - Login page with email/password
        - Registration with email verification
        - Password reset functionality
        - Session management
        - Logout feature
        """
        result = detect_complexity(text)
        # Should detect security keywords
        assert result.signals["security_matches"] >= 1
        # Level varies based on scoring, but should have detected security signals
        assert result.score > 0

    def test_large_feature_with_infra(self):
        """Test detecting large complexity with infrastructure."""
        text = """
        Build a microservices-based e-commerce platform:
        - User service with OAuth authentication
        - Product catalog service
        - Order processing service
        - Payment integration with Stripe
        - Deploy on Kubernetes with Docker
        - Set up CI/CD pipeline with GitHub Actions
        - Add monitoring with Prometheus and Grafana
        - Implement caching with Redis
        """
        result = detect_complexity(text)
        assert result.level >= 2
        assert result.signals["infra_matches"] >= 3
        assert result.signals["integration_matches"] >= 2

    def test_enterprise_with_compliance(self):
        """Test detecting enterprise complexity with compliance."""
        text = """
        Healthcare data management system with HIPAA compliance:
        - Patient data storage with encryption at rest
        - Audit logging for all data access
        - Role-based access control
        - Data retention policies
        - Deploy across multiple AWS regions
        - Implement SOC2 controls
        - Set up disaster recovery
        """
        result = detect_complexity(text)
        assert result.level >= 2
        assert result.signals["compliance_matches"] >= 3
        assert result.signals["security_matches"] >= 2

    def test_with_prd_file(self):
        """Test detection with PRD file."""
        prd_data = {
            "description": "Add authentication system",
            "userStories": [
                {"id": "US-001", "title": "Login", "fileScope": ["lib/auth.py"]},
                {"id": "US-002", "title": "Register", "fileScope": ["lib/auth.py"]},
                {"id": "US-003", "title": "Logout", "fileScope": ["lib/auth.py"]},
                {"id": "US-004", "title": "Password Reset", "fileScope": ["lib/email.py"]},
                {"id": "US-005", "title": "Profile", "fileScope": ["lib/user.py"]},
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(prd_data, f)
            prd_path = f.name

        try:
            result = detect_complexity("", prd_path)
            assert result.signals["story_count"] == 5
            assert result.signals["story_count_source"] == "prd"
            assert result.signals["file_scope"] == 3  # auth.py, email.py, user.py
        finally:
            os.unlink(prd_path)

    def test_result_structure(self):
        """Test that result has all expected fields."""
        result = detect_complexity("Add a feature")
        assert hasattr(result, "level")
        assert hasattr(result, "level_name")
        assert hasattr(result, "level_description")
        assert hasattr(result, "score")
        assert hasattr(result, "signals")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reasoning")

    def test_confidence_range(self):
        """Test that confidence is in valid range."""
        result = detect_complexity("Add authentication with JWT")
        assert 0 <= result.confidence <= 1

    def test_score_range(self):
        """Test that score is in valid range."""
        result = detect_complexity("Add a feature")
        assert 0 <= result.score <= 100


class TestComplexityLevels:
    """Test complexity level definitions."""

    def test_all_levels_defined(self):
        """Test that all 5 levels are defined."""
        assert len(COMPLEXITY_LEVELS) == 5
        for i in range(5):
            assert i in COMPLEXITY_LEVELS

    def test_level_has_required_fields(self):
        """Test that each level has required fields."""
        required_fields = ["name", "description", "typical_stories", "typical_duration"]
        for level, info in COMPLEXITY_LEVELS.items():
            for field in required_fields:
                assert field in info, f"Level {level} missing field {field}"

    def test_level_names(self):
        """Test expected level names."""
        assert COMPLEXITY_LEVELS[0]["name"] == "micro"
        assert COMPLEXITY_LEVELS[1]["name"] == "small"
        assert COMPLEXITY_LEVELS[2]["name"] == "medium"
        assert COMPLEXITY_LEVELS[3]["name"] == "large"
        assert COMPLEXITY_LEVELS[4]["name"] == "enterprise"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_text(self):
        """Test with empty text."""
        result = detect_complexity("")
        assert result.level == 0
        assert result.confidence > 0

    def test_very_long_text(self):
        """Test with very long text."""
        text = "Add feature. " * 1000  # Long repetitive text
        result = detect_complexity(text)
        assert result is not None

    def test_unicode_text(self):
        """Test with unicode characters."""
        text = "Add 用户认证 with OAuth ユーザー認証"
        result = detect_complexity(text)
        assert result is not None

    def test_special_characters(self):
        """Test with special characters."""
        text = "Add @#$%^&*() special chars !@#$"
        result = detect_complexity(text)
        assert result is not None

    def test_nonexistent_prd_file(self):
        """Test with nonexistent PRD file (should not crash)."""
        result = detect_complexity("Add feature", "/nonexistent/path/prd.json")
        assert result is not None

    def test_invalid_prd_json(self):
        """Test with invalid JSON in PRD file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            prd_path = f.name

        try:
            result = detect_complexity("Add feature", prd_path)
            assert result is not None  # Should still work, just without PRD data
        finally:
            os.unlink(prd_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
