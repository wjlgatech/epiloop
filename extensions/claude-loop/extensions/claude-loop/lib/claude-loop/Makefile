# Claude-Loop Makefile
#
# Common development tasks for claude-loop project
#

.PHONY: help test test-phase1 test-phase2 test-all test-quick clean

# Default target
help:
	@echo "Claude-Loop Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make test              - Run all tests"
	@echo "  make test-phase1       - Run Phase 1 tests only"
	@echo "  make test-phase2       - Run Phase 2 tests only"
	@echo "  make test-quick        - Run quick integration tests"
	@echo "  make test-individual   - Run individual feature tests"
	@echo "  make test-combined     - Run combined feature tests"
	@echo "  make test-performance  - Run performance tests"
	@echo "  make test-rollback     - Run rollback tests"
	@echo "  make test-error        - Run error injection tests"
	@echo "  make clean             - Clean test artifacts"
	@echo ""

# =============================================================================
# Test Targets
# =============================================================================

# Run all tests
test: test-phase1 test-phase2

# Phase 1 tests
test-phase1:
	@echo "Running Phase 1 tests..."
	@./tests/hooks_test.sh
	@./tests/learnings_test.sh
	@./tests/decomposition_test.sh
	@./tests/structured_output_test.sh
	@echo "Phase 1 tests complete"

# Phase 2 tests (all categories)
test-phase2:
	@echo "Running Phase 2 integration tests (all categories)..."
	@./tests/phase2_integration_test.sh --category all
	@echo "Phase 2 tests complete"

# Quick integration tests (individual features only)
test-quick:
	@echo "Running quick integration tests..."
	@./tests/mcp_test.sh
	@./tests/multi_provider_test.sh
	@./tests/delegation_test.sh
	@echo "Quick tests complete"

# Individual feature tests
test-individual:
	@echo "Running individual feature tests..."
	@./tests/phase2_integration_test.sh --category individual
	@echo "Individual feature tests complete"

# Combined feature tests
test-combined:
	@echo "Running combined feature tests..."
	@./tests/phase2_integration_test.sh --category combined
	@echo "Combined feature tests complete"

# Performance tests
test-performance:
	@echo "Running performance tests..."
	@./tests/phase2_integration_test.sh --category performance
	@echo "Performance tests complete"

# Rollback tests
test-rollback:
	@echo "Running rollback tests..."
	@./tests/phase2_integration_test.sh --category rollback
	@echo "Rollback tests complete"

# Error injection tests
test-error:
	@echo "Running error injection tests..."
	@./tests/phase2_integration_test.sh --category error_injection
	@echo "Error injection tests complete"

# Full test suite (verbose)
test-all:
	@echo "Running full test suite (verbose)..."
	@./tests/phase2_integration_test.sh --verbose --category all
	@echo "Full test suite complete"

# =============================================================================
# Cleanup Targets
# =============================================================================

clean:
	@echo "Cleaning test artifacts..."
	@rm -rf .claude-loop/delegation
	@rm -f .claude-loop/mcp-config-test.json
	@rm -f .claude-loop/mcp-config-error-test.json
	@rm -f .claude-loop/mcp-config-invalid.json
	@rm -f .claude-loop/logs/*.backup
	@git worktree prune 2>/dev/null || true
	@echo "Cleanup complete"

# =============================================================================
# Development Targets
# =============================================================================

# Run specific test with verbose output
test-verbose:
	@./tests/phase2_integration_test.sh --verbose

# Watch mode (re-run tests on file changes)
# Requires: entr (brew install entr)
test-watch:
	@echo "Watching for changes (Ctrl+C to stop)..."
	@find tests lib -type f | entr -c make test-phase2
