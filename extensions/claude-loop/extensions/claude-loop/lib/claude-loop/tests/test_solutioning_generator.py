#!/usr/bin/env python3
"""
Unit tests for solutioning-generator.py

Tests for architecture documentation and ADR template generation:
- ADR topic detection from keywords
- Architecture template generation
- ADR template generation
- Complexity-based generation skipping
- Output directory handling
"""

import json
import os
import sys
import tempfile
import shutil
import pytest

# Add lib directory to path for imports
LIB_DIR = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.insert(0, LIB_DIR)

# Import with hyphenated module name workaround
import importlib.util
spec = importlib.util.spec_from_file_location(
    "solutioning_generator",
    os.path.join(LIB_DIR, "solutioning-generator.py")
)
if spec is None or spec.loader is None:
    raise ImportError("Could not load solutioning-generator.py")
solutioning_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solutioning_generator)

# Extract functions and classes from the module
count_keyword_matches = solutioning_generator.count_keyword_matches
detect_adr_topics = solutioning_generator.detect_adr_topics
generate_architecture_template = solutioning_generator.generate_architecture_template
generate_adr_template = solutioning_generator.generate_adr_template
generate_solutioning_artifacts = solutioning_generator.generate_solutioning_artifacts
ensure_directory = solutioning_generator.ensure_directory
ADR_TOPICS = solutioning_generator.ADR_TOPICS
ADRDetectionResult = solutioning_generator.ADRDetectionResult
GenerationResult = solutioning_generator.GenerationResult


class TestKeywordMatching:
    """Test keyword detection for ADR topics."""

    def test_count_database_keywords(self):
        """Test database keyword detection."""
        text = "Store user data in PostgreSQL database with Redis caching"
        count, matches = count_keyword_matches(text, ADR_TOPICS["database"]["keywords"])
        assert count >= 3  # database, postgresql, redis
        assert "database" in matches
        assert "redis" in matches

    def test_count_api_style_keywords(self):
        """Test API style keyword detection."""
        text = "Create REST API endpoints with GraphQL for complex queries"
        count, matches = count_keyword_matches(text, ADR_TOPICS["api_style"]["keywords"])
        assert count >= 3  # api, rest, graphql
        assert "api" in matches
        assert "rest" in matches

    def test_count_auth_keywords(self):
        """Test authentication keyword detection."""
        text = "Implement OAuth 2.0 authentication with JWT tokens for session management"
        count, matches = count_keyword_matches(text, ADR_TOPICS["authentication"]["keywords"])
        assert count >= 3  # oauth, auth, jwt, token, session
        assert "jwt" in matches

    def test_count_state_keywords(self):
        """Test state management keyword detection."""
        text = "Use Redux for global state management with React Context for local state"
        count, matches = count_keyword_matches(text, ADR_TOPICS["state_management"]["keywords"])
        assert count >= 3  # redux, state, context
        assert "redux" in matches
        assert "state" in matches

    def test_case_insensitive_matching(self):
        """Test that keyword matching is case insensitive."""
        text = "POSTGRESQL DATABASE with REDIS caching"
        count, _ = count_keyword_matches(text, ADR_TOPICS["database"]["keywords"])
        assert count >= 2

    def test_no_matches(self):
        """Test when no keywords match."""
        text = "Simple text with no technical terms"
        count, matched = count_keyword_matches(text, ADR_TOPICS["database"]["keywords"])
        assert count == 0
        assert len(matched) == 0

    def test_word_boundary_matching(self):
        """Test that keywords match on word boundaries."""
        text = "Use api for communication"
        _, matches = count_keyword_matches(text, ADR_TOPICS["api_style"]["keywords"])
        assert "api" in matches


class TestADRTopicDetection:
    """Test ADR topic detection from PRD content."""

    def test_detect_database_topic(self):
        """Test detection of database-related topics."""
        prd_content = "Store user data in PostgreSQL database with Redis for caching"
        results = detect_adr_topics(prd_content)

        db_result = next(r for r in results if r.topic == "database")
        assert db_result.should_generate is True
        assert db_result.match_count >= 2
        assert len(db_result.keyword_matches) >= 2

    def test_detect_auth_topic(self):
        """Test detection of authentication topics."""
        prd_content = "Implement OAuth authentication with JWT tokens and SSO support"
        results = detect_adr_topics(prd_content)

        auth_result = next(r for r in results if r.topic == "authentication")
        assert auth_result.should_generate is True
        assert auth_result.match_count >= 2

    def test_skip_topic_with_few_matches(self):
        """Test that topics with < 2 matches are not generated."""
        prd_content = "Add simple database storage"  # Only 1 match (database)
        results = detect_adr_topics(prd_content)

        db_result = next(r for r in results if r.topic == "database")
        # With only "database" matching, should not generate
        assert db_result.match_count == 1
        assert db_result.should_generate is False

    def test_detect_multiple_topics(self):
        """Test detection of multiple ADR topics."""
        prd_content = """
        Build a REST API backend using GraphQL for complex queries.
        Store data in PostgreSQL database with Redis caching.
        Implement OAuth2 authentication with JWT tokens.
        """
        results = detect_adr_topics(prd_content)

        should_generate = [r for r in results if r.should_generate]
        topics = [r.topic for r in should_generate]

        assert "api_style" in topics
        assert "database" in topics
        assert "authentication" in topics

    def test_detect_from_prd_data(self):
        """Test detection from PRD JSON data."""
        prd_data = {
            "project": "test-project",
            "description": "A simple project",
            "userStories": [
                {
                    "id": "US-001",
                    "title": "Database Setup",
                    "description": "Configure PostgreSQL database with connection pooling"
                },
                {
                    "id": "US-002",
                    "title": "API Layer",
                    "description": "Build REST API endpoints with OpenAPI documentation"
                }
            ]
        }
        results = detect_adr_topics("", prd_data)

        should_generate = [r for r in results if r.should_generate]
        assert len(should_generate) >= 2

    def test_adr_result_structure(self):
        """Test ADRDetectionResult structure."""
        prd_content = "Use PostgreSQL database with Redis cache"
        results = detect_adr_topics(prd_content)

        assert len(results) == len(ADR_TOPICS)
        for result in results:
            assert hasattr(result, 'topic')
            assert hasattr(result, 'keyword_matches')
            assert hasattr(result, 'match_count')
            assert hasattr(result, 'should_generate')
            assert hasattr(result, 'title')
            assert hasattr(result, 'context')
            assert hasattr(result, 'options')


class TestArchitectureTemplateGeneration:
    """Test architecture.md template generation."""

    def test_generate_basic_template(self):
        """Test basic architecture template generation."""
        prd_data = {
            "project": "test-project",
            "description": "A test project description",
            "userStories": [
                {"id": "US-001", "title": "Feature 1"},
                {"id": "US-002", "title": "Feature 2"},
            ]
        }
        detected_topics = []

        template = generate_architecture_template(prd_data, detected_topics)

        assert "# Architecture Document: test-project" in template
        assert "A test project description" in template
        assert "US-001" in template
        assert "US-002" in template
        assert "## 1. Overview" in template
        assert "## 2. Components" in template
        assert "## 3. Data Flow" in template
        assert "## 4. API Contracts" in template
        assert "## 5. Security" in template

    def test_template_with_file_scope(self):
        """Test template extracts components from fileScope."""
        prd_data = {
            "project": "test-project",
            "description": "Test",
            "userStories": [
                {"id": "US-001", "title": "Story", "fileScope": ["lib/auth.py", "lib/user.py"]},
                {"id": "US-002", "title": "Story 2", "fileScope": ["tests/test_auth.py"]},
            ]
        }
        detected_topics = []

        template = generate_architecture_template(prd_data, detected_topics)

        assert "`lib/`" in template
        assert "`tests/`" in template

    def test_template_with_detected_topics(self):
        """Test template includes detected ADR topics."""
        prd_data = {
            "project": "test-project",
            "description": "Test",
            "userStories": []
        }
        detected_topics = [
            ADRDetectionResult(
                topic="database",
                keyword_matches=["database", "postgresql"],
                match_count=2,
                should_generate=True,
                title="Database Technology Selection",
                context="System requires data persistence",
                options=[]
            )
        ]

        template = generate_architecture_template(prd_data, detected_topics)

        assert "Database Technology" in template
        assert "See ADR-XXX" in template

    def test_template_limits_stories_display(self):
        """Test template limits story list to first 10."""
        prd_data = {
            "project": "test-project",
            "description": "Test",
            "userStories": [{"id": f"US-{i:03d}", "title": f"Story {i}"} for i in range(15)]
        }
        detected_topics = []

        template = generate_architecture_template(prd_data, detected_topics)

        # First 10 stories should be displayed (US-000 through US-009)
        assert "US-000" in template
        assert "US-009" in template
        # Stories after 10 should not be shown
        assert "US-010" not in template
        assert "US-011" not in template
        assert "5 more stories" in template


class TestADRTemplateGeneration:
    """Test ADR template generation."""

    def test_generate_basic_adr(self):
        """Test basic ADR template generation."""
        topic_result = ADRDetectionResult(
            topic="database",
            keyword_matches=["database", "postgresql"],
            match_count=2,
            should_generate=True,
            title="Database Technology Selection",
            context="The system requires data persistence",
            options=[
                "PostgreSQL - Relational database",
                "MongoDB - Document database"
            ]
        )

        template = generate_adr_template(topic_result, 1, "test-project")

        assert "# ADR-001: Database Technology Selection" in template
        assert "Project: test-project" in template
        assert "Status: **Proposed**" in template
        assert "The system requires data persistence" in template
        assert "database, postgresql" in template
        assert "PostgreSQL - Relational database" in template
        assert "MongoDB - Document database" in template

    def test_adr_numbering(self):
        """Test ADR number formatting."""
        topic_result = ADRDetectionResult(
            topic="api",
            keyword_matches=["api"],
            match_count=1,
            should_generate=True,
            title="API Style",
            context="Context",
            options=[]
        )

        template1 = generate_adr_template(topic_result, 1, "project")
        template10 = generate_adr_template(topic_result, 10, "project")
        template100 = generate_adr_template(topic_result, 100, "project")

        assert "ADR-001:" in template1
        assert "ADR-010:" in template10
        assert "ADR-100:" in template100

    def test_adr_keywords_limit(self):
        """Test that keywords are limited to 5."""
        topic_result = ADRDetectionResult(
            topic="database",
            keyword_matches=["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
            match_count=7,
            should_generate=True,
            title="Test",
            context="Context",
            options=[]
        )

        template = generate_adr_template(topic_result, 1, "project")

        # Should only include first 5 keywords
        assert "keyword1, keyword2, keyword3, keyword4, keyword5" in template
        assert "keyword6" not in template
        assert "keyword7" not in template


class TestSolutioningArtifactGeneration:
    """Test full artifact generation flow."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)

    @pytest.fixture
    def complex_prd(self, temp_dir):
        """Create a complex PRD that should trigger generation."""
        prd_data = {
            "project": "complex-test-project",
            "description": """
            Build a comprehensive user authentication system with OAuth 2.0,
            JWT tokens for session management. Store user data in PostgreSQL
            database with Redis for caching. Expose REST API endpoints.
            """,
            "userStories": [
                {"id": f"US-{i:03d}", "title": f"Story {i}", "fileScope": ["lib/auth.py"]}
                for i in range(10)
            ]
        }
        prd_path = os.path.join(temp_dir, "prd.json")
        with open(prd_path, 'w') as f:
            json.dump(prd_data, f)
        return prd_path

    @pytest.fixture
    def simple_prd(self, temp_dir):
        """Create a simple PRD that may not trigger generation."""
        prd_data = {
            "project": "simple-test-project",
            "description": "Fix a typo in the readme",
            "userStories": [
                {"id": "US-001", "title": "Fix typo"}
            ]
        }
        prd_path = os.path.join(temp_dir, "simple-prd.json")
        with open(prd_path, 'w') as f:
            json.dump(prd_data, f)
        return prd_path

    def test_generate_with_force(self, complex_prd, temp_dir):
        """Test generation with force flag."""
        output_dir = os.path.join(temp_dir, "docs")

        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=output_dir,
            force=True
        )

        assert result.success is True
        assert result.architecture_path is not None
        assert os.path.exists(result.architecture_path)
        assert "architecture.md" in result.architecture_path

    def test_generate_creates_adrs(self, complex_prd, temp_dir):
        """Test that ADRs are created for detected topics."""
        output_dir = os.path.join(temp_dir, "docs")

        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=output_dir,
            force=True
        )

        assert result.success is True
        assert len(result.adr_paths) > 0
        for adr_path in result.adr_paths:
            assert os.path.exists(adr_path)
            assert "adr-" in adr_path

    def test_generate_detected_topics(self, complex_prd, temp_dir):
        """Test that detected topics are returned."""
        output_dir = os.path.join(temp_dir, "docs")

        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=output_dir,
            force=True
        )

        assert len(result.detected_topics) > 0
        # The complex PRD mentions auth, database, and api
        assert any(t in ["authentication", "database", "api_style"] for t in result.detected_topics)

    def test_generate_default_output_dir(self, complex_prd, temp_dir):
        """Test generation uses docs/ relative to PRD by default."""
        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=None,
            force=True
        )

        assert result.success is True
        assert "docs" in result.architecture_path

        # Cleanup
        docs_dir = os.path.join(temp_dir, "docs")
        if os.path.exists(docs_dir):
            shutil.rmtree(docs_dir)

    def test_generate_fails_with_missing_prd(self, temp_dir):
        """Test generation fails gracefully with missing PRD."""
        result = generate_solutioning_artifacts(
            prd_path="/nonexistent/path/prd.json",
            output_dir=temp_dir,
            force=True
        )

        assert result.success is False
        assert result.skipped_reason is not None
        assert "Failed to load PRD" in result.skipped_reason

    def test_generate_fails_with_invalid_json(self, temp_dir):
        """Test generation fails with invalid JSON."""
        bad_prd = os.path.join(temp_dir, "bad.json")
        with open(bad_prd, 'w') as f:
            f.write("not valid json {{{")

        result = generate_solutioning_artifacts(
            prd_path=bad_prd,
            output_dir=temp_dir,
            force=True
        )

        assert result.success is False
        assert "Failed to load PRD" in result.skipped_reason

    def test_architecture_content_is_valid(self, complex_prd, temp_dir):
        """Test generated architecture.md has expected content."""
        output_dir = os.path.join(temp_dir, "docs")

        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=output_dir,
            force=True
        )

        with open(result.architecture_path, 'r') as f:
            content = f.read()

        assert "complex-test-project" in content
        assert "## 1. Overview" in content
        assert "## 5. Security" in content

    def test_adr_content_is_valid(self, complex_prd, temp_dir):
        """Test generated ADRs have expected content."""
        output_dir = os.path.join(temp_dir, "docs")

        result = generate_solutioning_artifacts(
            prd_path=complex_prd,
            output_dir=output_dir,
            force=True
        )

        assert len(result.adr_paths) > 0

        with open(result.adr_paths[0], 'r') as f:
            content = f.read()

        assert "# ADR-" in content
        assert "Status: **Proposed**" in content
        assert "## Context" in content
        assert "## Decision Outcome" in content


class TestEnsureDirectory:
    """Test directory creation utility."""

    def test_creates_directory(self):
        """Test directory is created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "subdir", "nested")
            result = ensure_directory(new_dir)

            assert result is True
            assert os.path.isdir(new_dir)

    def test_handles_existing_directory(self):
        """Test handles existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ensure_directory(temp_dir)
            assert result is True


class TestComplexityIntegration:
    """Test integration with complexity detector."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path)

    def test_skips_low_complexity(self, temp_dir):
        """Test that generation is skipped for low complexity PRDs."""
        # Create a simple PRD that should be low complexity
        prd_data = {
            "project": "simple-project",
            "description": "Fix typo",
            "userStories": [
                {"id": "US-001", "title": "Fix typo"}
            ]
        }
        prd_path = os.path.join(temp_dir, "prd.json")
        with open(prd_path, 'w') as f:
            json.dump(prd_data, f)

        result = generate_solutioning_artifacts(
            prd_path=prd_path,
            output_dir=os.path.join(temp_dir, "docs"),
            force=False,
            min_complexity=3
        )

        # Result depends on whether complexity detector is available
        # Either it's skipped due to low complexity, or force=False has no effect
        if result.complexity_level is not None and result.complexity_level < 3:
            assert result.architecture_path is None
            assert "skipping" in result.skipped_reason.lower()

    def test_force_overrides_complexity(self, temp_dir):
        """Test that force flag overrides complexity check."""
        prd_data = {
            "project": "simple-project",
            "description": "Fix typo",
            "userStories": [
                {"id": "US-001", "title": "Fix typo"}
            ]
        }
        prd_path = os.path.join(temp_dir, "prd.json")
        with open(prd_path, 'w') as f:
            json.dump(prd_data, f)

        result = generate_solutioning_artifacts(
            prd_path=prd_path,
            output_dir=os.path.join(temp_dir, "docs"),
            force=True,
            min_complexity=3
        )

        # With force=True, should generate regardless of complexity
        assert result.success is True
        assert result.architecture_path is not None


class TestGenerationResultStructure:
    """Test GenerationResult dataclass."""

    def test_generation_result_fields(self):
        """Test GenerationResult has all expected fields."""
        result = GenerationResult(
            success=True,
            architecture_path="/path/to/arch.md",
            adr_paths=["/path/to/adr.md"],
            skipped_reason=None,
            complexity_level=3,
            detected_topics=["database"]
        )

        assert result.success is True
        assert result.architecture_path == "/path/to/arch.md"
        assert len(result.adr_paths) == 1
        assert result.skipped_reason is None
        assert result.complexity_level == 3
        assert "database" in result.detected_topics
