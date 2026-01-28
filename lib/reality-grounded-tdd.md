# Reality-Grounded TDD (RG-TDD)

**Version**: 1.0
**Status**: Core OS Component
**Purpose**: Extend TDD beyond unit tests to include real-world validation

---

## The Problem with Traditional TDD

```
Traditional TDD Pipeline:
  Unit Tests Pass → Integration Tests Pass → Ship → 💥 FAILS IN PRODUCTION

Why it fails:
  - Tests verify our ASSUMPTIONS, not REALITY
  - Edge cases we imagine ≠ edge cases that exist
  - Simulated environments ≠ real environments
  - Small scale ≠ production scale
```

**The Brutal Truth**: Code that passes all tests can still be useless.

---

## RG-TDD: Three-Layer Testing Pyramid

```
                    ▲
                   /│\
                  / │ \
                 /  │  \          LAYER 3: REALITY TESTS
                /   │   \         - SOTA benchmarks
               /    │    \        - Real-world deployment
              /     │     \       - Adversarial scenarios
             /      │      \      - User acceptance
            /───────│───────\
           /        │        \    LAYER 2: CHALLENGE TESTS
          /         │         \   - Edge cases from failures
         /          │          \  - Cross-domain transfer
        /           │           \ - Scale stress tests
       /            │            \- Competitive baselines
      /─────────────│─────────────\
     /              │              \  LAYER 1: FOUNDATION TESTS
    /               │               \ - Unit tests
   /                │                \- Integration tests
  /                 │                 \- Type checks, linting
 /──────────────────│──────────────────\
```

### Layer 1: Foundation Tests (Traditional TDD)
- ✅ Unit tests for functions
- ✅ Integration tests for modules
- ✅ Type checking, linting
- **Purpose**: Catch obvious bugs
- **Limitation**: Only tests what we think of

### Layer 2: Challenge Tests (New)
- ✅ Edge cases harvested from production failures
- ✅ Cross-domain transfer tests (train on A, test on B)
- ✅ Scale stress tests (10x, 100x expected load)
- ✅ Competitive baseline comparisons
- **Purpose**: Catch non-obvious bugs
- **Limitation**: Still in controlled environment

### Layer 3: Reality Tests (New)
- ✅ SOTA benchmark evaluation
- ✅ Real-world deployment with monitoring
- ✅ Adversarial/red-team scenarios
- ✅ User acceptance testing
- **Purpose**: Validate actual usefulness
- **Limitation**: Expensive, slow - use strategically

---

## RG-TDD Protocol for claude-loop

### Before Marking Story "Complete"

```python
def validate_story_completion(story):
    # Layer 1: Foundation (MUST PASS)
    assert run_unit_tests(story) == PASS
    assert run_integration_tests(story) == PASS
    assert run_type_check(story) == PASS

    # Layer 2: Challenge (MUST PASS for production code)
    if story.is_production_code:
        assert run_edge_case_tests(story) == PASS
        assert run_baseline_comparison(story) >= BASELINE
        assert run_scale_test(story, scale=10) == PASS

    # Layer 3: Reality (MUST PASS for release)
    if story.is_release_candidate:
        assert run_benchmark_eval(story) >= SOTA_THRESHOLD
        assert run_adversarial_tests(story) == PASS
        assert get_user_acceptance(story) >= 0.8

    return COMPLETE
```

### Continuous Reality Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    RG-TDD FEEDBACK LOOP                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   DEVELOP ──▶ TEST (L1) ──▶ TEST (L2) ──▶ TEST (L3)            │
│      ▲                                        │                 │
│      │                                        │                 │
│      │         FAILURE HARVESTING             │                 │
│      │    ┌───────────────────────────┐      │                 │
│      │    │ Extract failure patterns  │◀─────┘                 │
│      │    │ Add to Layer 2 test suite │                        │
│      │    │ Update training data      │                        │
│      │    └───────────────────────────┘                        │
│      │                 │                                        │
│      └─────────────────┘                                        │
│                                                                 │
│   Every L3 failure becomes an L2 test                          │
│   Every L2 failure becomes an L1 test                          │
│   Test suite grows from REALITY, not imagination               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation for Physical AI Research

### Layer 1: Foundation Tests (Always Run)

```yaml
foundation_tests:
  scwm:
    - test_world_model_forward_pass
    - test_uncertainty_estimation_bounds
    - test_calibration_network_update
    - test_rssm_state_dimensions

  ecot_vla:
    - test_reasoning_head_output_format
    - test_action_head_dimensions
    - test_grounding_token_parsing
    - test_consistency_loss_computation

  ncd:
    - test_gnn_message_passing
    - test_conservation_constraints
    - test_contact_detection
```

### Layer 2: Challenge Tests (Before PR Merge)

```yaml
challenge_tests:
  scwm:
    - test_zero_shot_transfer_novel_object      # Not in training
    - test_calibration_under_distribution_shift  # New environment
    - test_long_horizon_prediction_stability     # 100+ steps
    - test_vs_domain_randomization_baseline      # Must beat DR
    - test_adversarial_physics_perturbation      # Extreme friction

  ecot_vla:
    - test_reasoning_on_unseen_task_category     # Novel task type
    - test_grounding_accuracy_cluttered_scene    # Occlusion
    - test_vs_openvla_baseline                   # Must beat OpenVLA
    - test_reasoning_consistency_under_noise     # Sensor noise

  ncd:
    - test_deformable_generalization             # Novel materials
    - test_contact_prediction_accuracy           # < 5% force error
    - test_vs_fem_baseline                       # Must be faster
    - test_real_tactile_sensor_integration       # Hardware-in-loop
```

### Layer 3: Reality Tests (Before Release)

```yaml
reality_tests:
  scwm:
    benchmarks:
      - name: "RLBench"
        threshold: 0.70  # 70% success rate
      - name: "Meta-World ML45"
        threshold: 0.65
      - name: "Real Robot (Franka)"
        threshold: 0.60

    adversarial:
      - scenario: "Unexpected object in workspace"
      - scenario: "Lighting change during task"
      - scenario: "Human interference"

    user_acceptance:
      - criterion: "Robot completes task on first try"
        threshold: 0.80

  ecot_vla:
    benchmarks:
      - name: "ECoT-Bench (our benchmark)"
        threshold: 0.85  # Human agreement
      - name: "CALVIN"
        threshold: 0.70  # Chain completion
      - name: "Physical Bongard"
        threshold: 0.80  # Reasoning accuracy

    adversarial:
      - scenario: "Misleading language instruction"
      - scenario: "Physically impossible request"
      - scenario: "Ambiguous referring expression"
```

---

## Failure Harvesting Protocol

### When a Reality Test Fails

```python
def harvest_failure(failure):
    # 1. Document the failure
    failure_record = {
        "timestamp": now(),
        "test_layer": failure.layer,
        "test_name": failure.test,
        "input": failure.input,
        "expected": failure.expected,
        "actual": failure.actual,
        "root_cause": analyze_root_cause(failure),
        "environment": failure.environment,
    }

    # 2. Create regression test
    new_test = create_test_from_failure(failure_record)
    add_to_test_suite(new_test, layer=failure.layer - 1)  # Demote to lower layer

    # 3. Update training data (for ML systems)
    if is_ml_system(failure.component):
        add_to_training_data(failure.input, failure.expected)

    # 4. Update documentation
    add_to_known_issues(failure_record)

    # 5. Trigger re-evaluation
    schedule_re_test(failure.component)

    return failure_record
```

### Failure → Test Promotion

```
L3 Failure: "Robot drops object when lighting changes"
    ↓
L2 Test Added: test_manipulation_under_lighting_variation()
    ↓
L1 Test Added: test_visual_encoder_illumination_invariance()

L3 Failure: "Fleet learning diverges at 50 robots"
    ↓
L2 Test Added: test_convergence_at_scale(n=100)
    ↓
L1 Test Added: test_gradient_norm_bounds()
```

---

## SOTA Benchmark Integration

### Automatic Benchmark Tracking

```yaml
benchmarks:
  physical_ai:
    - name: "Open X-Embodiment"
      url: "https://robotics-transformer-x.github.io/"
      metrics: ["success_rate", "generalization"]
      our_target: "top_10_percentile"

    - name: "RLBench"
      url: "https://sites.google.com/view/rlbench"
      metrics: ["success_rate", "sample_efficiency"]
      our_target: "> 70%"

    - name: "CALVIN"
      url: "http://calvin.cs.uni-freiburg.de/"
      metrics: ["chain_completion"]
      our_target: "> 70%"

    - name: "Meta-World"
      url: "https://meta-world.github.io/"
      metrics: ["ML10", "ML45"]
      our_target: "> 65%"

  tracking:
    frequency: "weekly"
    alert_on: "regression > 5%"
    compare_to: ["baseline", "sota", "previous_week"]
```

### Competitive Baseline Requirement

```python
def validate_against_baselines(model, task):
    baselines = {
        "scwm": ["DreamerV3", "TD-MPC2", "Domain Randomization"],
        "ecot_vla": ["OpenVLA", "RT-2", "Octo"],
        "ncd": ["DiffPD", "PlasticineLab", "FEM"],
    }

    for baseline in baselines[model.type]:
        baseline_score = get_baseline_score(baseline, task)
        our_score = evaluate(model, task)

        assert our_score >= baseline_score, \
            f"Must beat {baseline}: {our_score} < {baseline_score}"

    return True
```

---

## Integration with claude-loop

### Updated Story Completion Criteria

```yaml
# In prd.json
userStories:
  - id: "US-001"
    title: "Implement SCWM Core"
    acceptanceCriteria:
      # Layer 1 (Foundation)
      - "All unit tests pass"
      - "Type checking passes"
      - "Code coverage > 80%"

      # Layer 2 (Challenge)
      - "Beats DreamerV3 baseline on block stacking"
      - "Handles 10x training distribution shift"
      - "Edge case suite passes (10 scenarios)"

      # Layer 3 (Reality) - for release stories only
      - "RLBench success rate > 70%"
      - "Real robot demo succeeds 3/5 trials"

    testLayers:
      foundation: required
      challenge: required
      reality: on_release
```

### Automatic Test Layer Detection

```python
def determine_test_requirements(story):
    if "prototype" in story.tags:
        return ["foundation"]
    elif "production" in story.tags:
        return ["foundation", "challenge"]
    elif "release" in story.tags:
        return ["foundation", "challenge", "reality"]
    else:
        return ["foundation"]
```

---

## Quality Gate Updates

### Before: Traditional TDD

```yaml
quality_gates:
  - syntax_check: required
  - type_check: required
  - unit_tests: required
  - integration_tests: required
  - coverage: "> 80%"
```

### After: RG-TDD

```yaml
quality_gates:
  layer_1_foundation:
    - syntax_check: required
    - type_check: required
    - unit_tests: required
    - integration_tests: required
    - coverage: "> 80%"

  layer_2_challenge:
    - edge_case_tests: required
    - baseline_comparison: "> baseline"
    - scale_test: "10x"
    - distribution_shift_test: required

  layer_3_reality:
    - benchmark_evaluation: "> SOTA threshold"
    - adversarial_tests: required
    - user_acceptance: "> 80%"
    - real_deployment_test: "3/5 success"

  failure_harvesting:
    - on_any_failure: "create_regression_test"
    - on_l3_failure: "add_to_l2_suite"
    - on_l2_failure: "add_to_l1_suite"
```

---

## Key Principles

### 1. Reality is the Ultimate Test
Unit tests passing means nothing if the product fails in the real world. SOTA benchmarks are the minimum bar for "working."

### 2. Failure is Data
Every failure in production is a gift - it tells us what we didn't know. Harvest failures systematically.

### 3. Tests Must Grow from Reality
The test suite should expand based on ACTUAL failures, not hypothetical edge cases we imagine.

### 4. Baselines are Mandatory
"It works" is meaningless. "It beats DreamerV3 by 15%" is meaningful.

### 5. Scale Early
Test at 10x expected scale BEFORE release. Scale surprises are the worst surprises.

---

## Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| L1 Pass Rate | % of foundation tests passing | 100% |
| L2 Pass Rate | % of challenge tests passing | > 95% |
| L3 Pass Rate | % of reality tests passing | > 80% |
| Failure Harvest Rate | % of L3 failures converted to L2 tests | 100% |
| Baseline Beat Rate | % of tasks where we beat baseline | > 90% |
| SOTA Threshold Met | % of benchmarks where we hit target | > 80% |
| Time to L3 | Days from feature complete to reality test | < 14 |

---

## Summary

**Traditional TDD**: "Does it work as I designed it?"

**RG-TDD**: "Does it work in the real world, better than alternatives, at scale?"

```
The code that ships is not the code that passes tests.
The code that ships is the code that survives reality.
```

---

*This document defines Reality-Grounded TDD for claude-loop and all research projects.*
*Version 1.0 - January 24, 2026*
