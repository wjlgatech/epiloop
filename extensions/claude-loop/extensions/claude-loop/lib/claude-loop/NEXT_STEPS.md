# Next Steps: Execute Tier 1 Validation with Claude-Loop

## What Was Created

### 1. Comprehensive Analysis (58 pages)

**File**: `ANALYSIS.md`

**Contents**:
- Original analysis of both architectures (agent-zero, claude-loop)
- Competing recommendations (Sonnet 4.5 vs Opus 4.5)
- Synthesis and revised recommendation
- Patterns & antipatterns analysis
- 3 integration options (A, B, C)
- Benchmark design framework
- Decision framework
- Implementation roadmap

**Key Insight**: Selective Integration (Option B) is optimal, but VALIDATE FIRST with benchmarks.

---

### 2. Real-World Benchmark Suite

**Directory**: `benchmark-tasks/`

**Files Created**:
```
TASK-001-vision-summary.yaml        (MICRO task, agent-zero)
TASK-002-llm-health-check.yaml      (MESO task, claude-loop)
TASK-003-scheduler-duplicate-jobs.yaml (REGRESSION task, agent-zero)
benchmark_runner.py                  (Orchestrator, mock execution working)
README.md                            (Full documentation)
ANALYSIS.md                          (This comprehensive analysis)
```

**Demo Run Results** (mock execution):
```
Subject         | Success Rate | Avg Cost   | Avg Score
----------------------------------------------------------------------
baseline        |     100.0%   | $0.0304   |   0.79
agent-zero      |      66.7%   | $0.0488   |   0.55
claude-loop     |     100.0%   | $0.0281   |   0.83  ← Best
```

---

### 3. Claude-Loop PRD for Execution

**Directory**: `claude-loop/prds/drafts/tier1-validation/`

**Files Created**:
```
prd.json           (10 user stories for Tier 1 validation)
progress.txt       (Context and initialization notes)
MANIFEST.yaml      (Metadata, risks, approval workflow)
```

**User Stories**:
1. US-001: Implement Baseline Execution Adapter
2. US-002: Implement Claude-Loop Execution Adapter
3. US-003: Implement Agent-Zero Execution Adapter (optional)
4. US-004: Create Acceptance Criteria Validation Scripts
5. US-005: Execute Tier 1 Benchmark Suite
6. US-006: Implement Statistical Analysis
7. US-007: Perform Failure Analysis
8. US-008: Generate Decision Recommendation Report
9. US-009: Document Benchmark Execution Process
10. US-010: Create Presentation Slides (optional)

---

## How to Proceed

### Option 1: Execute with Claude-Loop (Dogfooding)

Use claude-loop itself to manage the validation process:

```bash
cd /Users/jialiang.wu/Documents/Projects/claude-loop

# Promote PRD from draft to active
python lib/prd-manager.py promote tier1-validation

# Execute with claude-loop
./claude-loop.sh --prd prds/active/tier1-validation/prd.json
```

**Benefits**:
- ✓ Dogfooding: Claude-loop manages its own validation
- ✓ Structured execution with checkpoints
- ✓ Automatic quality gates
- ✓ Progress tracking
- ✓ Git commits for each story

**Watch out for**:
- Claude-loop is designed for code implementation, not research
- May need to adapt prompts for research/validation tasks
- US-003 (agent-zero) may be complex; can defer

---

### Option 2: Execute Manually with Claude Code

Use Claude Code directly to implement each story:

```bash
cd /Users/jialiang.wu/Documents/Projects/benchmark-tasks

# Story by story
claude "Implement baseline execution adapter in benchmark_runner.py according to US-001"
claude "Implement claude-loop execution adapter according to US-002"
# ... etc
```

**Benefits**:
- ✓ More flexibility for research tasks
- ✓ Direct control over implementation
- ✓ Easier to iterate and adjust

**Drawbacks**:
- ✗ Manual progress tracking
- ✗ No automatic checkpointing
- ✗ Need to manage git commits manually

---

### Option 3: Hybrid Approach (Recommended)

Use claude-loop for execution-heavy stories, manual for analysis:

**Phase 1 (Implementation) - Use Claude-Loop**:
- US-001, US-002, US-004 (code implementation)
- Let claude-loop handle: coding, testing, committing

**Phase 2 (Execution) - Manual or Scripted**:
- US-005 (run benchmark)
- Monitor progress, collect results

**Phase 3 (Analysis) - Use Claude Code Directly**:
- US-006, US-007, US-008 (analysis and reporting)
- Interactive analysis works better with direct Claude interaction

---

## Quick Start (Recommended Path)

### Week 1: Implementation Phase

**Day 1-2: US-001 (Baseline Adapter)**

```bash
cd benchmark-tasks

# Option A: Use Claude Code
claude "Implement baseline execution adapter:
- Read TASK-001, TASK-002, TASK-003 YAML specs
- For each task, invoke Claude Code CLI with task description
- Capture stdout/stderr
- Parse for success/failure
- Extract token usage (approximate if not available)
- Validate acceptance criteria
- Save metrics to JSON

Implement _run_baseline() in benchmark_runner.py"

# Option B: Use Claude-Loop
cd ../claude-loop
./claude-loop.sh quick "Implement baseline execution adapter in ../benchmark-tasks/benchmark_runner.py according to US-001 in PRD"
```

**Day 3-4: US-002 (Claude-Loop Adapter)**

```bash
# This is easier since we're in the claude-loop codebase
claude "Implement claude-loop execution adapter:
- Convert task YAML to natural language prompt
- Invoke ./claude-loop.sh quick '<prompt>'
- Parse output from .claude-loop/quick-tasks/
- Extract metrics from monitoring logs
- Validate acceptance criteria
- Return results

Implement _run_claude_loop() in ../benchmark-tasks/benchmark_runner.py"
```

**Day 5: US-004 (Validation Scripts)**

```bash
cd benchmark-tasks

claude "Create validation scripts for 3 tasks:
- validation/task_001_validator.py (check vision byte removal)
- validation/task_002_validator.py (check health check works)
- validation/task_003_validator.py (check no duplicate jobs)

Each validator should:
- Read task output directory
- Check acceptance criteria
- Return score 0.0-1.0 for each criterion
- Output clear pass/fail

Use pytest framework where applicable."
```

**Day 5 (Optional): US-003 (Agent-Zero Adapter)**

Only if agent-zero integration is straightforward. Otherwise, defer.

---

### Week 2: Execution & Analysis

**Days 1-2: US-005 (Execute Benchmark)**

```bash
cd benchmark-tasks

# Test with one task first
python3 benchmark_runner.py --real-execution --tasks TASK-001 --subjects baseline claude-loop

# If successful, run full benchmark
python3 benchmark_runner.py --real-execution

# Monitor cost during execution
# Stop if approaching $40 (keep $10 buffer)
```

**Day 3: US-006 & US-007 (Analysis)**

```bash
claude "Implement analyze_results.py:
1. Load all results from benchmark-results/
2. Calculate aggregate metrics per subject
3. Perform t-tests comparing subjects
4. Calculate effect sizes (Cohen's d)
5. Classify failures into categories
6. Generate comparison tables
7. Output: analysis_report.json and analysis_report.md"

python3 analyze_results.py
```

**Day 4: US-008 (Decision Report)**

```bash
claude "Create DECISION_REPORT.md:
1. Summarize benchmark results
2. Apply decision framework:
   - >20% improvement → Recommend Option B
   - 10-20% → Judgment call
   - <10% → Stay current
3. Explain statistical significance
4. Highlight failure patterns
5. Outline next steps if proceeding
6. Include cost-benefit analysis

Use data from analysis_report.json"
```

**Day 5: US-009 & US-010 (Documentation)**

```bash
claude "Create EXECUTION_GUIDE.md documenting:
- Prerequisites
- Step-by-step execution
- Troubleshooting
- How to add new tasks
- Result interpretation

And create PRESENTATION.md with 8-12 slides:
- Executive summary
- Methodology
- Results (charts)
- Recommendation
- Q&A notes"
```

---

## Decision Framework

### After Week 2, Evaluate Results

**Scenario A: Clear Winner (>20% improvement)**
→ Recommend Option B (Selective Integration)
→ Proceed to Tier 2 benchmark (optional)
→ Begin implementation roadmap (Weeks 3-16)

**Scenario B: Marginal Difference (10-20%)**
→ Judgment call based on:
  - Which metrics improved (cost vs success vs time)
  - Team capacity
  - Risk tolerance
→ Consider Option A (Pattern Extraction) as lower-risk alternative

**Scenario C: No Clear Difference (<10%)**
→ Stay with current claude-loop
→ Revisit when more mature or when specific pain points emerge

**Scenario D: Claude-loop underperforms**
→ Investigate failure modes (likely configuration or task mismatch)
→ Re-run with adjustments
→ If persistent, reconsider claude-loop architecture

---

## Budget & Timeline

### Expected Costs

**API Calls**:
- Baseline execution: ~3,000-8,000 tokens/task × 3 tasks = ~$0.50-1.50
- Claude-loop execution: ~5,000-15,000 tokens/task × 3 tasks = ~$1.50-4.50
- Agent-zero (if included): ~8,000-20,000 tokens/task × 3 tasks = ~$2.40-6.00
- **Total estimated**: $5-15 (conservative), up to $50 (generous buffer)

**Human Time**:
- Week 1 implementation: 20-30 hours (engineer time)
- Week 2 execution + analysis: 10-15 hours
- **Total**: 30-45 hours

### Timeline

**Optimistic**: 1.5 weeks (if no blockers)
**Realistic**: 2 weeks
**Pessimistic**: 3 weeks (if agent-zero integration is complex)

---

## Success Criteria

### Must Have

- ✓ At least 6 runs completed (baseline + claude-loop, 3 tasks each)
- ✓ Metrics collected: success, time, cost, scores
- ✓ Statistical analysis performed
- ✓ Decision report with clear recommendation
- ✓ Budget < $50

### Nice to Have

- ✓ Agent-zero comparison (9 runs total)
- ✓ Presentation slides ready
- ✓ Failure analysis with patterns
- ✓ Reproducibility validation (re-run 1 task)

---

## Key Files Reference

### Already Created

| File | Location | Purpose |
|------|----------|---------|
| ANALYSIS.md | benchmark-tasks/ | Comprehensive analysis document |
| TASK-*.yaml | benchmark-tasks/ | 3 task specifications |
| benchmark_runner.py | benchmark-tasks/ | Orchestrator (needs real execution) |
| prd.json | claude-loop/prds/drafts/tier1-validation/ | 10 user stories |
| progress.txt | claude-loop/prds/drafts/tier1-validation/ | Context log |
| MANIFEST.yaml | claude-loop/prds/drafts/tier1-validation/ | PRD metadata |

### To Be Created (This Week)

| File | Purpose | Story |
|------|---------|-------|
| validation/*.py | Validators for 3 tasks | US-004 |
| analyze_results.py | Statistical analysis | US-006 |
| DECISION_REPORT.md | Final recommendation | US-008 |
| EXECUTION_GUIDE.md | Documentation | US-009 |
| PRESENTATION.md | Stakeholder slides | US-010 |

---

## Troubleshooting

### "Claude-loop PRD promotion fails"

```bash
# Check PRD location
ls -la claude-loop/prds/drafts/tier1-validation/

# Manually promote if needed
mkdir -p claude-loop/prds/active
mv claude-loop/prds/drafts/tier1-validation claude-loop/prds/active/
```

### "Baseline adapter: Can't extract token count"

Token count may not be directly available from Claude Code output. Options:
1. Approximate: Use tiktoken library to count prompt + response
2. Parse logs: Check if Claude Code logs token usage
3. Skip metric: Focus on success rate and cost estimation instead

### "Agent-zero adapter: Too complex"

It's okay to defer US-003. Baseline + Claude-loop comparison is sufficient:
- Update prd.json to mark US-003 as "deferred"
- Adjust US-005 to only run 6 executions
- Note in DECISION_REPORT that agent-zero comparison was deferred

### "Benchmark execution fails"

Capture partial results:
- Save whatever metrics are available
- Document failure mode
- Re-run specific failed task
- Proceed with available data (6/9 or 5/9 is still valuable)

---

## Contact & Questions

**For PRD execution issues**:
- Check claude-loop logs: `.claude-loop/execution_log.jsonl`
- Review progress: `cat claude-loop/prds/active/tier1-validation/progress.txt`

**For benchmark issues**:
- Check runner logs: `benchmark-results/*.json`
- Review task specs: `benchmark-tasks/TASK-*.yaml`

**For analysis questions**:
- Refer to ANALYSIS.md sections
- Decision framework in Section 8
- Benchmark design in Section 5

---

## Final Checklist

Before starting:
- [ ] Read ANALYSIS.md (at least executive summary + section 6)
- [ ] Review 3 task YAML files
- [ ] Understand decision thresholds (>20%, 10-20%, <10%)
- [ ] Confirm API keys configured for Claude Code
- [ ] Verify budget tracking capability

After Week 1:
- [ ] Baseline adapter working
- [ ] Claude-loop adapter working
- [ ] Validation scripts created
- [ ] Test run with 1 task successful

After Week 2:
- [ ] All benchmarks executed
- [ ] Results analyzed
- [ ] DECISION_REPORT.md created
- [ ] Recommendation clear
- [ ] Budget under $50

---

## The Goal

**Provide evidence-based answer to**: Should we integrate agent-zero capabilities into claude-loop? If yes, which approach (A, B, or C)?

**Success looks like**: Clear data-driven recommendation with statistical backing, completed in 2 weeks for <$50.

**Now**: Pick Option 1, 2, or 3 above and begin Week 1 implementation.

Good luck! 🚀
