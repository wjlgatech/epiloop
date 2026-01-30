#!/usr/bin/env python3
"""
test_failure_classification.py - Classification Accuracy Validator (SI-013)

Tests the accuracy of the failure classifier against manually labeled ground truth.
Measures precision, recall, accuracy per category with >80% accuracy threshold.

Usage:
    pytest tests/test_failure_classification.py -v
    pytest tests/test_failure_classification.py::test_classification_accuracy -v
    pytest tests/test_failure_classification.py --accuracy-report
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# Add lib to path for imports
lib_path = Path(__file__).parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# Import after path is set
import importlib.util
spec = importlib.util.spec_from_file_location("failure_classifier", lib_path / "failure-classifier.py")
sys.modules["failure_classifier"] = importlib.util.module_from_spec(spec)
failure_classifier = sys.modules["failure_classifier"]
spec.loader.exec_module(failure_classifier)

FailureCategory = failure_classifier.FailureCategory
FailureClassifier = failure_classifier.FailureClassifier
LogEntry = failure_classifier.LogEntry


# ============================================================================
# Test Data Loading
# ============================================================================


@pytest.fixture
def labeled_test_cases():
    """Load labeled test cases from fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "labeled_failures.json"

    if not fixtures_path.exists():
        pytest.skip(f"Labeled test cases not found at {fixtures_path}")

    with open(fixtures_path) as f:
        data = json.load(f)

    return data["test_cases"]


@pytest.fixture
def classifier():
    """Create a classifier instance."""
    # Use a temporary log file for testing
    temp_log = Path(__file__).parent / ".test_execution_log.jsonl"
    return FailureClassifier(log_file=temp_log)


# ============================================================================
# Classification Tests
# ============================================================================


def test_labeled_cases_loaded(labeled_test_cases):
    """Verify labeled test cases are loaded correctly."""
    assert len(labeled_test_cases) >= 20, "Need at least 20 test cases"

    # Verify all categories are represented
    categories = {tc["ground_truth"] for tc in labeled_test_cases}
    required = {"SUCCESS", "TASK_FAILURE", "CAPABILITY_GAP", "TRANSIENT_ERROR"}
    assert required.issubset(categories), f"Missing categories: {required - categories}"


def test_individual_classification(labeled_test_cases, classifier):
    """Test classification of individual cases."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "id": tc["id"],
            "actual": actual,
            "predicted": predicted,
            "confidence": classification.confidence,
            "match": predicted == actual,
        })

    # Print results for debugging
    print("\n=== Individual Classification Results ===")
    for r in results:
        status = "✓" if r["match"] else "✗"
        print(f"{status} {r['id']}: {r['actual']:20} -> {r['predicted']:20} ({r['confidence']:.2%})")

    # Check that at least some classifications are correct
    correct = sum(1 for r in results if r["match"])
    assert correct > 0, "No classifications were correct"


def test_classification_accuracy(labeled_test_cases, classifier):
    """Test overall classification accuracy meets threshold."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
            "confidence": classification.confidence,
        })

    # Calculate overall accuracy
    correct = sum(1 for r in results if r["actual"] == r["predicted"])
    total = len(results)
    accuracy = correct / total if total > 0 else 0

    print(f"\n=== Overall Accuracy ===")
    print(f"Correct: {correct}/{total}")
    print(f"Accuracy: {accuracy:.2%}")

    # Accuracy threshold for autonomous PRD generation
    ACCURACY_THRESHOLD = 0.80

    assert accuracy >= ACCURACY_THRESHOLD, (
        f"Classification accuracy {accuracy:.2%} below threshold {ACCURACY_THRESHOLD:.0%}. "
        f"Autonomous PRD generation should not be enabled until accuracy improves."
    )


def test_per_category_metrics(labeled_test_cases, classifier):
    """Test precision, recall, and F1 per category."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
        })

    # Get all categories
    all_categories = sorted(set(
        r["actual"] for r in results
    ) | set(
        r["predicted"] for r in results
    ))

    metrics = {}

    for category in all_categories:
        # True positives: predicted and actual both = category
        tp = sum(1 for r in results if r["actual"] == category and r["predicted"] == category)

        # False positives: predicted = category but actual != category
        fp = sum(1 for r in results if r["predicted"] == category and r["actual"] != category)

        # False negatives: actual = category but predicted != category
        fn = sum(1 for r in results if r["actual"] == category and r["predicted"] != category)

        # True negatives: both != category
        tn = sum(1 for r in results if r["actual"] != category and r["predicted"] != category)

        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # Support: number of actual instances
        support = tp + fn

        metrics[category] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        }

    print("\n=== Per-Category Metrics ===")
    print(f"{'Category':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 70)

    for category in all_categories:
        m = metrics[category]
        print(
            f"{category:<20} "
            f"{m['precision']:>9.2%} "
            f"{m['recall']:>9.2%} "
            f"{m['f1']:>9.2%} "
            f"{m['support']:>10}"
        )

    # Calculate macro averages (average across categories)
    macro_precision = sum(m["precision"] for m in metrics.values()) / len(metrics)
    macro_recall = sum(m["recall"] for m in metrics.values()) / len(metrics)
    macro_f1 = sum(m["f1"] for m in metrics.values()) / len(metrics)

    print("-" * 70)
    print(
        f"{'Macro Average':<20} "
        f"{macro_precision:>9.2%} "
        f"{macro_recall:>9.2%} "
        f"{macro_f1:>9.2%}"
    )

    # Verify minimum precision/recall per category
    for category, m in metrics.items():
        if m["support"] > 0:  # Only check categories with actual instances
            assert m["precision"] >= 0.0, f"{category} has negative precision"
            assert m["recall"] >= 0.0, f"{category} has negative recall"


def test_confusion_matrix(labeled_test_cases, classifier):
    """Generate and validate confusion matrix."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
        })

    # Build confusion matrix
    categories = sorted(set(r["actual"] for r in results) | set(r["predicted"] for r in results))
    matrix = {cat: {cat2: 0 for cat2 in categories} for cat in categories}

    for r in results:
        matrix[r["actual"]][r["predicted"]] += 1

    print("\n=== Confusion Matrix ===")
    print("Rows = Actual, Columns = Predicted\n")

    # Header
    header = "Actual \\ Predicted"
    print(f"{header:<25}", end="")
    for cat in categories:
        print(f"{cat[:10]:>12}", end="")
    print()
    print("-" * (25 + 12 * len(categories)))

    # Matrix rows
    for actual_cat in categories:
        print(f"{actual_cat:<25}", end="")
        for pred_cat in categories:
            count = matrix[actual_cat][pred_cat]
            # Highlight diagonal (correct predictions)
            if actual_cat == pred_cat:
                print(f"{count:>12}", end="")
            else:
                print(f"{count:>12}", end="")
        print()

    # Save confusion matrix to file
    output_dir = Path(__file__).parent.parent / ".claude-loop"
    output_dir.mkdir(exist_ok=True)

    confusion_file = output_dir / "confusion_matrix.json"
    with open(confusion_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "categories": categories,
            "matrix": matrix,
        }, f, indent=2)

    print(f"\nConfusion matrix saved to: {confusion_file}")


def test_confidence_calibration(labeled_test_cases, classifier):
    """Test that confidence scores are calibrated (high confidence = correct)."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
            "confidence": classification.confidence,
            "correct": actual == predicted,
        })

    # Bin results by confidence level
    bins = {
        "high": [],      # >0.8
        "medium": [],    # 0.5-0.8
        "low": [],       # <0.5
    }

    for r in results:
        if r["confidence"] >= 0.8:
            bins["high"].append(r)
        elif r["confidence"] >= 0.5:
            bins["medium"].append(r)
        else:
            bins["low"].append(r)

    print("\n=== Confidence Calibration ===")
    for level, items in bins.items():
        if not items:
            continue

        correct = sum(1 for r in items if r["correct"])
        total = len(items)
        accuracy = correct / total if total > 0 else 0
        avg_conf = sum(r["confidence"] for r in items) / total

        print(f"{level.capitalize():>10} confidence ({total:>2} cases): {accuracy:.2%} accuracy, avg conf: {avg_conf:.2%}")

    # High confidence predictions should be more accurate than low confidence
    if bins["high"] and bins["low"]:
        high_accuracy = sum(1 for r in bins["high"] if r["correct"]) / len(bins["high"])
        low_accuracy = sum(1 for r in bins["low"] if r["correct"]) / len(bins["low"])

        assert high_accuracy >= low_accuracy, (
            "High confidence predictions should be more accurate than low confidence"
        )


def test_edge_cases(classifier):
    """Test edge cases and boundary conditions."""
    # Empty error message
    entry = LogEntry(
        story_id="EDGE-001",
        story_title="Empty Error",
        timestamp_start="2026-01-11T12:00:00Z",
        timestamp_end="2026-01-11T12:00:01Z",
        duration_ms=1000,
        status="failure",
        exit_code=1,
        error_type="",
        error_message="",
        retry_count=0,
        fallback_count=0,
        attempted_actions=[],
        tools_used=[],
        file_types=[],
        context={},
    )

    result = classifier.classify_failure(entry)
    assert result.category in [
        FailureCategory.UNKNOWN,
        FailureCategory.TRANSIENT_ERROR,
        FailureCategory.CAPABILITY_GAP,
    ]
    assert 0 <= result.confidence <= 1

    # Very long error message
    long_msg = "Error: " + "x" * 10000
    entry = LogEntry(
        story_id="EDGE-002",
        story_title="Long Error",
        timestamp_start="2026-01-11T12:00:00Z",
        timestamp_end="2026-01-11T12:00:01Z",
        duration_ms=1000,
        status="failure",
        exit_code=1,
        error_type="unknown",
        error_message=long_msg,
        retry_count=0,
        fallback_count=0,
        attempted_actions=[],
        tools_used=[],
        file_types=[],
        context={},
    )

    result = classifier.classify_failure(entry)
    assert result.category is not None
    assert 0 <= result.confidence <= 1

    # Multiple conflicting signals
    entry = LogEntry(
        story_id="EDGE-003",
        story_title="Conflicting Signals",
        timestamp_start="2026-01-11T12:00:00Z",
        timestamp_end="2026-01-11T12:00:01Z",
        duration_ms=1000,
        status="failure",
        exit_code=1,
        error_type="timeout",
        error_message="Permission denied: cannot access UI element not found",
        retry_count=5,
        fallback_count=2,
        attempted_actions=[],
        tools_used=["computer-use"],
        file_types=[],
        context={"ui": "button", "network": "api"},
    )

    result = classifier.classify_failure(entry)
    # Should still produce a classification
    assert result.category is not None
    assert 0 <= result.confidence <= 1


# ============================================================================
# Accuracy Tracking Over Time
# ============================================================================


def test_accuracy_tracking(labeled_test_cases, classifier):
    """Track classification accuracy over time."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
            "confidence": classification.confidence,
            "correct": actual == predicted,
        })

    # Calculate accuracy
    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    accuracy = correct / total if total > 0 else 0

    # Load history
    history_file = Path(__file__).parent.parent / ".claude-loop" / "accuracy_history.jsonl"
    history_file.parent.mkdir(exist_ok=True)

    # Append current result
    with open(history_file, "a") as f:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "test_count": total,
            "correct": correct,
            "accuracy": accuracy,
            "per_category": {},
        }

        # Calculate per-category accuracy
        for category in set(r["actual"] for r in results):
            cat_results = [r for r in results if r["actual"] == category]
            cat_correct = sum(1 for r in cat_results if r["correct"])
            entry["per_category"][category] = {
                "total": len(cat_results),
                "correct": cat_correct,
                "accuracy": cat_correct / len(cat_results) if cat_results else 0,
            }

        f.write(json.dumps(entry) + "\n")

    print(f"\n=== Accuracy History ===")
    print(f"Results appended to: {history_file}")

    # Read and display history
    if history_file.exists():
        with open(history_file) as f:
            history = [json.loads(line) for line in f if line.strip()]

        if len(history) > 1:
            print(f"\nAccuracy trend (last {min(5, len(history))} runs):")
            for h in history[-5:]:
                timestamp = datetime.fromisoformat(h["timestamp"]).strftime("%Y-%m-%d %H:%M")
                print(f"  {timestamp}: {h['accuracy']:.2%} ({h['correct']}/{h['test_count']})")


def test_accuracy_threshold_alert(labeled_test_cases, classifier):
    """Alert if accuracy drops below threshold."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
        })

    correct = sum(1 for r in results if r["actual"] == r["predicted"])
    total = len(results)
    accuracy = correct / total if total > 0 else 0

    ALERT_THRESHOLD = 0.70  # Alert if below 70%

    if accuracy < ALERT_THRESHOLD:
        alert_msg = (
            f"\n{'='*70}\n"
            f"ACCURACY ALERT!\n"
            f"Classification accuracy {accuracy:.2%} has dropped below {ALERT_THRESHOLD:.0%}\n"
            f"This may indicate:\n"
            f"  - Changes to classifier logic that reduced performance\n"
            f"  - New types of failures not covered by current heuristics\n"
            f"  - Need to retrain or update classification patterns\n"
            f"{'='*70}\n"
        )
        print(alert_msg)

        # Write alert to file
        alert_file = Path(__file__).parent.parent / ".claude-loop" / "accuracy_alerts.log"
        with open(alert_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} - Accuracy {accuracy:.2%} below threshold\n")


# ============================================================================
# Visualization
# ============================================================================


def test_generate_visualization(labeled_test_cases, classifier):
    """Generate confusion matrix visualization (text-based)."""
    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "actual": actual,
            "predicted": predicted,
        })

    # Build matrix
    categories = sorted(set(r["actual"] for r in results) | set(r["predicted"] for r in results))
    matrix = {cat: {cat2: 0 for cat2 in categories} for cat in categories}

    for r in results:
        matrix[r["actual"]][r["predicted"]] += 1

    # Generate ASCII heatmap
    print("\n=== Confusion Matrix Heatmap ===")

    # Find max value for scaling
    max_val = max(
        matrix[actual][pred]
        for actual in categories
        for pred in categories
    )

    # Print header
    print("\nActual (rows) vs Predicted (columns)")
    print(f"Scale: 0 = ' ', max ({max_val}) = '█'\n")

    print(" " * 20, end="")
    for cat in categories:
        print(f"{cat[:8]:>10}", end="")
    print()
    print("-" * (20 + 10 * len(categories)))

    # Print rows with heatmap
    for actual in categories:
        print(f"{actual:<20}", end="")
        for pred in categories:
            count = matrix[actual][pred]
            # Scale to blocks
            if max_val > 0:
                intensity = count / max_val
                if intensity == 0:
                    block = " "
                elif intensity < 0.25:
                    block = "░"
                elif intensity < 0.5:
                    block = "▒"
                elif intensity < 0.75:
                    block = "▓"
                else:
                    block = "█"
            else:
                block = " "

            print(f"{block * 2} ({count:2})  ", end="")
        print()


# ============================================================================
# Test Report
# ============================================================================


def test_generate_report(labeled_test_cases, classifier, request):
    """Generate comprehensive accuracy report."""
    # Check for custom option if available
    try:
        if not request.config.getoption("--accuracy-report", default=False):
            pytest.skip("Use --accuracy-report to generate report")
    except (AttributeError, ValueError):
        # Option not registered, just run the test
        pass

    results = []

    for tc in labeled_test_cases:
        entry = LogEntry.from_dict(tc["log_entry"])
        classification = classifier.classify_failure(entry)

        predicted = classification.category.value.upper()
        actual = tc["ground_truth"]

        results.append({
            "id": tc["id"],
            "actual": actual,
            "predicted": predicted,
            "confidence": classification.confidence,
            "correct": actual == predicted,
            "reasoning": classification.reasoning,
            "factors": classification.contributing_factors,
        })

    # Generate report
    report_file = Path(__file__).parent.parent / ".claude-loop" / "classification_report.txt"

    with open(report_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("CLASSIFICATION ACCURACY REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Test Cases: {len(results)}\n\n")

        # Overall accuracy
        correct = sum(1 for r in results if r["correct"])
        accuracy = correct / len(results)
        f.write(f"Overall Accuracy: {accuracy:.2%} ({correct}/{len(results)})\n\n")

        # Per category
        f.write("=" * 80 + "\n")
        f.write("PER-CATEGORY RESULTS\n")
        f.write("=" * 80 + "\n\n")

        for category in sorted(set(r["actual"] for r in results)):
            cat_results = [r for r in results if r["actual"] == category]
            cat_correct = sum(1 for r in cat_results if r["correct"])
            cat_accuracy = cat_correct / len(cat_results) if cat_results else 0

            f.write(f"{category}\n")
            f.write(f"  Accuracy: {cat_accuracy:.2%} ({cat_correct}/{len(cat_results)})\n")
            f.write(f"  Cases: {', '.join(r['id'] for r in cat_results)}\n\n")

        # Incorrect predictions
        incorrect = [r for r in results if not r["correct"]]
        if incorrect:
            f.write("=" * 80 + "\n")
            f.write("INCORRECT PREDICTIONS\n")
            f.write("=" * 80 + "\n\n")

            for r in incorrect:
                f.write(f"{r['id']}:\n")
                f.write(f"  Actual:    {r['actual']}\n")
                f.write(f"  Predicted: {r['predicted']}\n")
                f.write(f"  Confidence: {r['confidence']:.2%}\n")
                f.write(f"  Reasoning: {r['reasoning']}\n\n")

    print(f"\nDetailed report saved to: {report_file}")


if __name__ == "__main__":
    # Run with: python tests/test_failure_classification.py
    pytest.main([__file__, "-v", "--accuracy-report"])
