# SCWM Research Execution Guide

Complete guide for running autonomous research on the Self-Calibrating World Model (SCWM) project using the claude-loop research system.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Research Structure](#research-structure)
5. [Configuration](#configuration)
6. [Running Research](#running-research)
7. [Human Checkpoints](#human-checkpoints)
8. [Integration with Cosmos-Predict2](#integration-with-cosmos-predict2)
9. [Output Artifacts](#output-artifacts)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The SCWM Research Execution Plan uses claude-loop's research orchestration to autonomously investigate, analyze, and synthesize research on Self-Calibrating World Models. The system coordinates specialized AI agents to:

- Survey literature on world models and uncertainty quantification
- Analyze technical implementations and benchmarks
- Design integration strategies for Cosmos-Predict2 and Isaac Lab
- Generate comprehensive research reports

### Key Features

- **Autonomous Execution**: Runs research stories without manual intervention
- **Human Checkpoints**: Pauses for approval at critical decision points
- **Multi-Agent Coordination**: Combines expertise from specialized research agents
- **Quality Gates**: Ensures research meets rigorous standards
- **Cosmos Integration**: Direct analysis of Cosmos-Predict2 codebase

---

## Prerequisites

### System Requirements

```bash
# Required
- Python 3.10+
- Bash 4.0+
- 8GB RAM minimum
- Internet access for search APIs

# Optional
- jq (for JSON processing)
- CUDA-capable GPU (for Cosmos integration testing)
```

### API Keys

Set the following environment variables (optional but recommended):

```bash
export TAVILY_API_KEY="your-tavily-key"      # Primary search
export ANTHROPIC_API_KEY="your-anthropic-key" # Claude API
```

### Repository Structure

```
claude-loop/
├── prds/
│   └── scwm-research.json         # Research PRD
├── adapters/
│   └── physical-ai/
│       ├── adapter.yaml           # Domain adapter
│       └── prompts/
│           └── research_guidelines.md
├── agents/
│   └── world-model-specialist.md  # Custom agent
├── config-scwm-research.yaml      # Configuration
├── run-scwm-research.sh           # Execution script
└── research-outputs/
    └── scwm/                      # Output directory
```

---

## Quick Start

### 1. Navigate to claude-loop

```bash
cd /path/to/claude-loop
```

### 2. Verify Setup

```bash
# Check PRD exists
cat prds/scwm-research.json | head -20

# Check config
cat config-scwm-research.yaml | head -20
```

### 3. Run Research

```bash
# Start full research (interactive mode)
./run-scwm-research.sh

# Or start a specific milestone
./run-scwm-research.sh --milestone week1

# Or run a single story
./run-scwm-research.sh --story RS-001
```

---

## Research Structure

### Milestones

| Week | Milestone | Stories | Deliverables |
|------|-----------|---------|--------------|
| 1 | Foundation | RS-001, RS-002, RS-003 | Literature survey, uncertainty analysis, calibration methods |
| 2 | Architecture | RS-004, RS-005 | Benchmarks analysis, architecture design |
| 3 | Integration | RS-006, RS-007 | Cosmos integration, Isaac Lab integration |
| 4 | Planning | RS-008, RS-009, RS-010 | Experimental design, implementation plan, competitive analysis |
| 5 | Publication | RS-011 | Publication strategy, paper outline |
| 6 | Synthesis | RS-012 | Final research report |

### Research Stories

```
RS-001: Literature Survey - World Models for Robotics
RS-002: Technical Deep Dive - Uncertainty Quantification Methods
RS-003: Technical Deep Dive - Online Calibration Mechanisms
RS-004: Benchmark Analysis - Physical AI Datasets
RS-005: Architecture Design - SCWM Core Components
RS-006: Cosmos-Predict2 Integration Analysis
RS-007: Isaac Lab Integration Analysis
RS-008: Experimental Design - Ablation Studies
RS-009: Implementation Plan - Core SCWM Module
RS-010: Competitive Analysis - Related Systems
RS-011: Publication Strategy - Paper Outline
RS-012: Research Synthesis - Final Report
```

### Dependencies

```
RS-001 (Literature) ─┬─→ RS-002 (Uncertainty)
                     ├─→ RS-003 (Calibration)
                     ├─→ RS-004 (Benchmarks)
                     └─→ RS-010 (Competitive)

RS-002 + RS-003 ─────→ RS-005 (Architecture)

RS-005 ─┬─→ RS-006 (Cosmos)
        └─→ RS-007 (Isaac)

RS-004 + RS-005 ─────→ RS-008 (Experimental)

RS-005..RS-007 ──────→ RS-009 (Implementation)

RS-001..RS-005 ──────→ RS-011 (Publication)

ALL ─────────────────→ RS-012 (Synthesis)
```

---

## Configuration

### config-scwm-research.yaml

Key configuration options:

```yaml
research_loop:
  prd_file: "prds/scwm-research.json"
  adapter: "physical-ai"
  output_dir: "research-outputs/scwm"

agents:
  auto_select: true
  max_per_story: 3
  enabled_tiers: [1, 2, 3]

quality:
  min_confidence: 70
  require_fact_check: true
  min_sources_per_finding: 2

checkpoints:
  enabled: true
  auto_approve_threshold: 90
  mandatory:
    - afterLiteratureReview
    - afterArchitectureDesign
```

### Physical AI Adapter

The `adapters/physical-ai/adapter.yaml` configures:

- arXiv categories to search (cs.RO, cs.LG, cs.AI, cs.CV)
- Top venues (ICRA, CoRL, RSS, NeurIPS)
- Quality gates (reproducibility, benchmark validity)
- Integration targets (Cosmos-Predict2, Isaac Lab)

---

## Running Research

### Full Research Run

```bash
./run-scwm-research.sh
```

This runs all milestones sequentially with human checkpoints.

### Milestone Run

```bash
# Run Week 1: Foundation
./run-scwm-research.sh --milestone week1

# Run Week 3: Integration
./run-scwm-research.sh --milestone week3
```

### Single Story Run

```bash
# Run literature survey only
./run-scwm-research.sh --story RS-001

# Run architecture design
./run-scwm-research.sh --story RS-005
```

### Resume from Checkpoint

```bash
./run-scwm-research.sh --resume
```

### Auto-Approve Mode (CI/Automation)

```bash
./run-scwm-research.sh --auto --milestone week1
```

### Check Status

```bash
./run-scwm-research.sh --status
```

---

## Human Checkpoints

### Mandatory Checkpoints

The system pauses for human review at:

1. **After Literature Review** (RS-001)
   - Verify coverage of key papers
   - Approve taxonomy structure
   - Confirm gap identification

2. **After Architecture Design** (RS-005)
   - Validate technical feasibility
   - Review compute requirements
   - Approve component specifications

3. **After Integration Analysis** (RS-006, RS-007)
   - Verify integration points
   - Review API compatibility
   - Approve implementation approach

4. **Before Final Report** (RS-012)
   - Review all findings
   - Verify fact-checking
   - Approve recommendations

### Checkpoint Workflow

When checkpoint is triggered:

```
╔════════════════════════════════════════════════════════╗
║              Human Checkpoint Required                 ║
╠════════════════════════════════════════════════════════╣
║ Story: RS-005 Architecture Design                      ║
║ Confidence: 82%                                        ║
║                                                        ║
║ Key Findings:                                          ║
║ 1. RSSM architecture recommended (conf: 85%)           ║
║ 2. Deep Ensemble with N=5 (conf: 80%)                  ║
║ 3. Online calibration via replay buffer (conf: 78%)   ║
║                                                        ║
║ [A]pprove  [R]equest more depth  [D]irect  [C]ancel   ║
╚════════════════════════════════════════════════════════╝
```

Options:
- **A**: Approve and continue
- **R**: Request more research on specific topic
- **D**: Redirect research focus
- **C**: Cancel research

### Resume After Checkpoint

```bash
# Approve pending checkpoint
./run-scwm-research.sh --approve RS-005

# Resume from where it left off
./run-scwm-research.sh --resume
```

---

## Integration with Cosmos-Predict2

### Overview

The research plan includes deep analysis of NVIDIA's Cosmos-Predict2 for integration:

- **RS-006**: Analyzes Cosmos architecture and identifies integration points
- Output: `cosmos-integration.md` with technical specifications

### Key Integration Points

```
cosmos_predict2/
├── models/
│   └── video2world_action_model.py  # Action-conditioned model
├── pipelines/
│   └── video2world_action.py        # Inference pipeline
├── conditioner.py                    # Conditioning mechanisms
└── auxiliary/
    └── cosmos_reason1.py            # Prompt refinement
```

### SCWM Integration Strategy

1. **Uncertainty Injection**: Inject SCWM uncertainty estimates into Cosmos conditioning
2. **Latent Space Sharing**: Share representations between SCWM world model and Cosmos tokenizer
3. **Action Conditioning**: Use SCWM for action-conditioned video generation
4. **Calibration Feedback**: Use Cosmos outputs for SCWM calibration

### Code Analysis

The research system will analyze:

```bash
# Key files for integration
cosmos_predict2/conditioner.py         # Where to inject uncertainty
cosmos_predict2/models/video2world_action_dit.py  # Model architecture
cosmos_predict2/pipelines/video2world_action.py   # Inference pipeline
```

---

## Output Artifacts

### Research Reports

| File | Description |
|------|-------------|
| `literature-survey.md` | Comprehensive literature review |
| `uncertainty-methods.md` | Technical analysis of uncertainty methods |
| `online-calibration.md` | Calibration techniques survey |
| `benchmarks-analysis.md` | Physical AI benchmark survey |
| `architecture-design.md` | SCWM architecture specification |
| `cosmos-integration.md` | Cosmos-Predict2 integration plan |
| `isaac-integration.md` | Isaac Lab integration plan |
| `experimental-design.md` | Ablation study protocols |
| `implementation-plan.md` | Development roadmap |
| `competitive-analysis.md` | Market positioning |
| `publication-strategy.md` | Publication plan |
| `scwm-research-report.md` | Final comprehensive report |
| `executive-summary.md` | Stakeholder summary |

### Data Files

| File | Description |
|------|-------------|
| `paper-citations.json` | Citation database |
| `method-comparison.json` | Method comparison matrix |
| `benchmark-sota.json` | SOTA results database |
| `architecture-specs.json` | Architecture specifications |
| `integration-specs.json` | Integration specifications |
| `ablation-matrix.json` | Ablation configuration |
| `module-specs.json` | Module specifications |

### State Files

```
.claude-loop/
├── scwm-research-state.json       # Main research state
├── scwm-research-state-RS-001.json  # Per-story states
└── checkpoint-log.json            # Checkpoint audit trail
```

---

## Troubleshooting

### Common Issues

#### Research Not Starting

```bash
# Check PRD file
python3 -c "import json; json.load(open('prds/scwm-research.json'))"

# Check dependencies
./run-scwm-research.sh --status
```

#### Checkpoint Timeout

```bash
# Increase timeout in config
vim config-scwm-research.yaml
# Set: checkpoints.timeout_seconds: 1200
```

#### Low Confidence Scores

If research produces low confidence scores (<60%):

1. Check search API keys are configured
2. Verify internet connectivity
3. Review search queries in logs
4. Manually provide additional sources

#### Integration Analysis Fails

```bash
# Verify Cosmos-Predict2 path
ls ../physical_ai_playground/cosmos-predict2/

# Update path in config if needed
vim config-scwm-research.yaml
```

### Logs

```bash
# View research logs
tail -f logs/scwm-research/research.log

# View agent selection logs
grep "agent" logs/scwm-research/research.log

# View search queries
grep "search" logs/scwm-research/research.log
```

### Reset Research

```bash
# Clear state and restart
rm -rf .claude-loop/scwm-research-state*.json
rm -rf research-outputs/scwm/*.md
./run-scwm-research.sh
```

---

## Advanced Usage

### Custom Research Questions

```bash
# Use research-loop.sh directly for ad-hoc questions
./research-loop.sh "What uncertainty propagation methods work best for long-horizon predictions?"
```

### Agent Customization

Create custom agents in `agents/`:

```bash
# Create domain-specific agent
cp agents/academic-scanner.md agents/robotics-specialist.md
vim agents/robotics-specialist.md
```

### Integration with CI/CD

```yaml
# GitHub Actions example
jobs:
  research:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Research
        run: |
          ./run-scwm-research.sh --auto --milestone week1
        env:
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
```

---

## References

- [claude-loop README](../README.md)
- [Research Loop Documentation](../README-research-loop.md)
- [Physical AI Adapter](../adapters/physical-ai/adapter.yaml)
- [SCWM PRD](../prds/scwm-research.json)

---

*SCWM Research Guide v1.0*
*Last Updated: 2026-01-24*
