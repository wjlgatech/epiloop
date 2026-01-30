# AI/ML Research Quality Gates

Quality gates specific to AI and Machine Learning research that ensure findings are reproducible, benchmarks are valid, and claims are properly supported.

## Gate 1: Reproducibility Check

### Criteria
- **Code Availability**: GitHub/GitLab repository linked or code in appendix
- **Data Availability**: Training/evaluation datasets publicly available or clearly described
- **Environment Specification**: Python/framework versions, hardware requirements documented
- **Pre-trained Models**: Model checkpoints available for download
- **Hyperparameters**: All hyperparameter settings documented

### Scoring
```python
def reproducibility_score(paper):
    score = 0.0

    if has_code_repository:
        score += 0.30
    if has_pretrained_models:
        score += 0.25
    if has_public_datasets or has_dataset_details:
        score += 0.20
    if has_environment_spec:
        score += 0.15
    if has_hyperparameter_details:
        score += 0.10

    return score  # 0.0-1.0
```

### Pass/Fail Thresholds
- **Pass**: Score >= 0.50 (at least code + data or code + models)
- **Warning**: Score 0.30-0.49 (partial reproducibility)
- **Fail**: Score < 0.30 (minimal reproducibility information)

### Actions
- **Pass**: Include in synthesis with confidence boost (+0.10)
- **Warning**: Include but note reproducibility limitations
- **Fail**: Flag as low confidence (-0.20), note in caveats section

---

## Gate 2: Benchmark Validity

### Criteria
- **Standard Dataset**: Uses recognized benchmark dataset (ImageNet, GLUE, etc.)
- **Standard Metrics**: Reports standard metrics for the task
- **Standard Split**: Uses official train/val/test splits
- **Fair Comparison**: Compares against recent baselines on same setting
- **Statistical Significance**: Reports confidence intervals or multiple runs

### Dataset Recognition
```python
KNOWN_BENCHMARKS = {
    "nlp": ["GLUE", "SuperGLUE", "SQuAD", "MMLU", "BIG-Bench", "HellaSwag"],
    "vision": ["ImageNet", "COCO", "ADE20K", "Cityscapes"],
    "multimodal": ["VQA", "CLIP", "Flamingo"],
    "rl": ["Atari", "MuJoCo", "Gym"]
}

STANDARD_METRICS = {
    "classification": ["accuracy", "f1", "precision", "recall"],
    "generation": ["BLEU", "ROUGE", "perplexity", "FID"],
    "detection": ["mAP", "IoU"],
    "rl": ["return", "success_rate"]
}
```

### Validation Checks
```python
def validate_benchmark(paper):
    checks = {
        "uses_standard_dataset": False,
        "reports_standard_metrics": False,
        "uses_official_split": False,
        "compares_to_baselines": False,
        "reports_significance": False
    }

    # Check each criterion
    if dataset_name in KNOWN_BENCHMARKS:
        checks["uses_standard_dataset"] = True

    if any(metric in paper.metrics for metric in STANDARD_METRICS):
        checks["reports_standard_metrics"] = True

    # ... additional checks

    return checks
```

### Pass/Fail Thresholds
- **Pass**: >= 3/5 checks pass
- **Warning**: 2/5 checks pass
- **Fail**: < 2/5 checks pass

### Actions
- **Pass**: High confidence in results
- **Warning**: Include with caveat about non-standard evaluation
- **Fail**: Flag as incomparable to existing work

---

## Gate 3: Recency & Relevance (Fast-Moving Fields)

### Criteria
AI/ML moves fast. Recent work (< 12 months) often supersedes older work.

### Fast-Moving Subfields
- Large Language Models (LLMs)
- Diffusion Models
- Multimodal Models
- Vision Transformers
- Efficient Training Methods

### Recency Scoring
```python
def calculate_recency_score(publication_date, subfield):
    months_old = months_since(publication_date)

    if subfield in FAST_MOVING:
        # Aggressive decay for fast-moving areas
        if months_old <= 6:
            return 1.0
        elif months_old <= 12:
            return 0.7
        elif months_old <= 24:
            return 0.4
        else:
            return 0.2
    else:
        # Standard decay
        if months_old <= 12:
            return 1.0
        elif months_old <= 24:
            return 0.8
        elif months_old <= 36:
            return 0.6
        else:
            return 0.4
```

### Actions
- **Recent (score >= 0.7)**: High confidence
- **Moderate (0.4-0.69)**: Include but note age
- **Stale (< 0.4)**: Flag as potentially outdated, check for newer work

---

## Gate 4: Citation Normalization

### Criteria
Newer papers have fewer citations. Normalize by publication age.

### Normalization Formula
```python
def normalized_citation_score(citations, months_old):
    # Expected citations by age
    if months_old <= 6:
        expected = 5
    elif months_old <= 12:
        expected = 20
    elif months_old <= 24:
        expected = 50
    elif months_old <= 36:
        expected = 100
    else:
        expected = 200

    # Normalize
    normalized = citations / expected

    # Cap at 1.0
    return min(1.0, normalized)
```

### Thresholds
- **Highly Cited**: normalized >= 0.8
- **Moderately Cited**: normalized 0.4-0.79
- **Low Citations**: normalized < 0.4

---

## Gate 5: Code Quality Assessment

When code is available, assess quality indicators.

### Criteria
- **Repository Activity**: Recent commits, maintained
- **Documentation**: README, API docs, examples
- **Tests**: Unit tests, integration tests
- **Dependencies**: Clear requirements.txt or environment.yml
- **Stars/Forks**: Community adoption (GitHub stars)

### Scoring
```python
def code_quality_score(repo):
    score = 0.0

    if has_recent_commits:
        score += 0.20
    if has_readme_and_docs:
        score += 0.25
    if has_tests:
        score += 0.20
    if has_dependencies_spec:
        score += 0.15
    if github_stars > 100:
        score += 0.10
    if github_stars > 1000:
        score += 0.10

    return min(1.0, score)
```

---

## Gate 6: Benchmark Leaderboard Cross-Check

### Criteria
If paper claims SOTA, verify against official leaderboard.

### Verification Process
```python
def verify_sota_claim(paper, task, dataset):
    # 1. Query Papers With Code
    pwc_results = paperswithcode_client.get_sota_benchmarks(task, dataset)

    # 2. Check if paper is in top-k
    paper_in_leaderboard = any(r.paper_title == paper.title for r in pwc_results[:10])

    # 3. Check metric value match
    claimed_value = paper.reported_metric
    leaderboard_value = find_value_in_leaderboard(paper.title, pwc_results)

    value_matches = abs(claimed_value - leaderboard_value) < 0.01

    return {
        "in_leaderboard": paper_in_leaderboard,
        "value_matches": value_matches
    }
```

### Actions
- **Verified**: In leaderboard with matching value → High confidence
- **Partial**: In leaderboard but value differs → Check paper version
- **Missing**: Not in leaderboard → Lower confidence, note as unverified claim

---

## Integrated Quality Gate Pipeline

### Pipeline Flow
```
1. Reproducibility Check
   ├─ Pass → Confidence +0.10
   ├─ Warning → No change
   └─ Fail → Confidence -0.20

2. Benchmark Validity
   ├─ Pass → Proceed
   ├─ Warning → Note non-standard eval
   └─ Fail → Flag incomparable

3. Recency Check
   ├─ Recent → High priority
   ├─ Moderate → Include
   └─ Stale → Check for updates

4. Citation Normalization
   └─ Adjust confidence based on normalized citations

5. Code Quality (if available)
   └─ Confidence boost 0.0-0.15

6. Leaderboard Verification (if SOTA claimed)
   ├─ Verified → Confidence +0.10
   └─ Unverified → Confidence -0.10
```

### Final Confidence Score
```python
def calculate_final_confidence(paper):
    base_confidence = 0.5

    # Apply gate adjustments
    confidence = base_confidence
    confidence += reproducibility_adjustment
    confidence += benchmark_validity_adjustment
    confidence *= recency_multiplier
    confidence += citation_adjustment
    confidence += code_quality_boost
    confidence += leaderboard_verification_adjustment

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))
```

### Confidence Levels
- **High (0.8-1.0)**: Reproducible, validated, recent, well-cited
- **Moderate (0.5-0.79)**: Some gaps in reproducibility or validation
- **Low (0.3-0.49)**: Significant concerns, use with caution
- **Very Low (<0.3)**: Multiple red flags, likely not reliable

---

## Report Integration

Quality gate results should be included in research reports:

```markdown
### Quality Assessment

**Reproducibility**: ✓ Pass (0.75)
- Code available: ✓ (GitHub)
- Pre-trained models: ✓ (HuggingFace)
- Data available: ✓ (Public dataset)
- Environment spec: ✓ (requirements.txt)

**Benchmark Validity**: ✓ Pass (4/5 criteria)
- Standard dataset: ✓ (ImageNet)
- Standard metrics: ✓ (top-1/top-5 accuracy)
- Official split: ✓
- Baseline comparison: ✓
- Statistical significance: ✗ (single run)

**Recency**: ✓ Recent (Published 3 months ago)

**Citations**: Moderate (Normalized score: 0.6)
- Raw citations: 12
- Expected for 3 months: 20
- Normalized: 0.6

**Code Quality**: ✓ High (0.85)
- Active maintenance: ✓
- Documentation: ✓
- Tests: ✓
- 1.2k GitHub stars

**SOTA Verification**: ✓ Verified
- Listed on Papers With Code
- Metric matches leaderboard: ✓

**Final Confidence**: 0.82 (High)
```

---

## Implementation Notes

These quality gates should be implemented in:
- `lib/ai-ml-quality-gates.py` - Python module for gate execution
- Integration with `lib/research_synthesizer.py` - Apply gates during synthesis
- Integration with `lib/confidence_scorer.py` - Incorporate into confidence calculation

Gates are configurable via `adapters/ai-ml/adapter.yaml` under the `quality_gates` section.
