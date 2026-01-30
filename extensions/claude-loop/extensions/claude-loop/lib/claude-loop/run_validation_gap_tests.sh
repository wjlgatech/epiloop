#!/bin/bash
#
# Quick Start Script for Validation Gap Tests
#
# Usage:
#   ./run_validation_gap_tests.sh baseline     # Test without fixes
#   ./run_validation_gap_tests.sh with-fixes   # Test with fixes
#   ./run_validation_gap_tests.sh compare      # Compare results
#   ./run_validation_gap_tests.sh full         # Run both + compare
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo "========================================================================"
echo "  VALIDATION GAP TEST SUITE - Priority 1 Fixes Validation"
echo "========================================================================"
echo ""

MODE="${1:-help}"

case "$MODE" in
    baseline)
        echo -e "${YELLOW}Running BASELINE tests (without Priority 1 fixes)...${NC}"
        echo "This simulates claude-loop behavior before Priority 1 was implemented."
        echo ""
        python3 validation_gap_test.py --baseline --runs 3
        ;;

    with-fixes)
        echo -e "${GREEN}Running WITH-FIXES tests (Priority 1 enabled)...${NC}"
        echo "This tests claude-loop with all Priority 1 fixes enabled."
        echo ""
        python3 validation_gap_test.py --with-fixes --runs 3
        ;;

    compare)
        echo -e "${YELLOW}Comparing BASELINE vs WITH-FIXES results...${NC}"
        echo ""
        python3 validation_gap_test.py --compare
        ;;

    full)
        echo -e "${YELLOW}Running FULL validation (baseline + with-fixes + compare)...${NC}"
        echo "This will take approximately 1 hour (30 min baseline + 30 min fixes)."
        echo ""
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "Step 1/3: Running BASELINE tests..."
            python3 validation_gap_test.py --baseline --runs 3

            echo ""
            echo "Step 2/3: Running WITH-FIXES tests..."
            python3 validation_gap_test.py --with-fixes --runs 3

            echo ""
            echo "Step 3/3: Comparing results..."
            python3 validation_gap_test.py --compare

            echo ""
            echo -e "${GREEN}✓ Full validation complete!${NC}"
        else
            echo "Cancelled."
            exit 0
        fi
        ;;

    quick)
        echo -e "${GREEN}Running QUICK validation (1 run per case)...${NC}"
        echo "Fast check to verify fixes are working (10-15 minutes)."
        echo ""
        python3 validation_gap_test.py --with-fixes --runs 1
        ;;

    help|*)
        echo "Usage: $0 <mode>"
        echo ""
        echo "Modes:"
        echo "  baseline     - Run tests without Priority 1 fixes (simulates pre-fix behavior)"
        echo "  with-fixes   - Run tests with Priority 1 fixes enabled (default)"
        echo "  compare      - Compare baseline vs with-fixes results"
        echo "  full         - Run baseline, with-fixes, and compare (1 hour)"
        echo "  quick        - Quick validation with 1 run per case (15 minutes)"
        echo ""
        echo "Examples:"
        echo "  $0 quick              # Quick check (15 min)"
        echo "  $0 with-fixes         # Test fixes (30 min)"
        echo "  $0 full               # Complete validation (1 hour)"
        echo ""
        echo "Test Cases:"
        echo "  VGAP-001: Simple File Copy (tests reminder effectiveness)"
        echo "  VGAP-002: JSON Validator (tests auto-pass logic)"
        echo "  VGAP-003: String Reversal (tests tool usability)"
        echo "  VGAP-004: Config Parser (tests under cognitive load)"
        echo "  VGAP-005: Email Validator (tests threshold boundary)"
        echo ""
        echo "Expected Improvements:"
        echo "  Validation Gap Rate: 20-40% → <5% (>50% reduction)"
        echo "  Success Rate: 60-80% → >95% (+20% increase)"
        echo ""
        echo "Results saved to: validation_gap_results/"
        echo ""
        ;;
esac
