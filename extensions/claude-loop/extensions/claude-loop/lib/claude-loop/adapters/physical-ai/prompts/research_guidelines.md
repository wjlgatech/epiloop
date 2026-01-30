# Physical AI Research Guidelines

## Overview

This document provides guidelines for autonomous research on Physical AI topics, specifically the Self-Calibrating World Model (SCWM) project.

## Research Principles

### 1. Rigor and Reproducibility

- **Always cite sources** with full bibliographic information
- **Prefer open-source implementations** that can be verified
- **Note computational requirements** for reproducibility
- **Document experimental conditions** including random seeds, hardware

### 2. Technical Depth

- **Understand the math** before summarizing methods
- **Trace implementation details** in code repositories
- **Note assumptions and limitations** of each approach
- **Compare fairly** using consistent evaluation protocols

### 3. Practical Relevance

- **Focus on deployable methods** for robotics applications
- **Consider compute constraints** of real-time systems
- **Evaluate sim-to-real transfer** potential
- **Note safety implications** of uncertainty-aware systems

## Key Research Questions for SCWM

### World Models
1. What architecture best balances expressiveness and computational cost?
2. How to handle multi-modal observations (vision, proprioception, force)?
3. What is the optimal horizon for model-based planning?

### Uncertainty Quantification
1. Which method provides best-calibrated uncertainty estimates?
2. How does uncertainty propagate through multi-step predictions?
3. What is the computational overhead of different uncertainty methods?

### Online Calibration
1. How to detect distribution shift in real-time?
2. What adaptation rate balances stability and responsiveness?
3. How to prevent catastrophic forgetting during online updates?

### Integration
1. How to inject SCWM into Cosmos-Predict2's conditioning mechanism?
2. What interfaces does Isaac Lab need for world model integration?
3. How to share latent representations between SCWM and video models?

## Search Strategies

### Literature Search
```
# Primary queries
"world model" AND "uncertainty" AND (robotics OR manipulation)
"epistemic uncertainty" AND "neural network" AND calibration
"model-based reinforcement learning" AND "ensemble"
"video prediction" AND "action-conditioned"

# Secondary queries
DreamerV3 OR TD-MPC2 OR IRIS OR "latent dynamics"
"online adaptation" AND "neural network" AND robotics
"sim-to-real" AND "world model"
```

### Code Search
```
# GitHub searches
org:NVlabs world model
org:google-deepmind dreamer
language:python "deep ensemble" uncertainty
language:python "rssm" "world model"
```

## Quality Checklist

### For Each Paper Reviewed
- [ ] Publication venue and year
- [ ] Citation count (normalized by age)
- [ ] Code availability
- [ ] Benchmark results reported
- [ ] Real-world validation (if any)
- [ ] Limitations acknowledged

### For Each Technical Analysis
- [ ] Mathematical formulation understood
- [ ] Implementation complexity assessed
- [ ] Computational requirements documented
- [ ] Integration feasibility evaluated
- [ ] Alternatives compared

### For Each Integration Analysis
- [ ] API compatibility verified
- [ ] Data format requirements documented
- [ ] Performance impact estimated
- [ ] Failure modes identified
- [ ] Rollback plan considered

## Output Format

### Literature Survey
```markdown
# [Topic] Literature Survey

## Executive Summary
[2-3 sentences]

## Taxonomy
[Classification of approaches]

## Key Papers
### [Paper Title] (Venue Year)
- **Authors**: ...
- **Key Contribution**: ...
- **Method**: ...
- **Results**: ...
- **Limitations**: ...
- **Relevance to SCWM**: ...

## Research Gaps
[Identified opportunities]

## Recommendations
[Actionable next steps]

## References
[Full citations]
```

### Technical Analysis
```markdown
# [Method] Technical Analysis

## Overview
[What it is and why it matters]

## Mathematical Formulation
[Key equations with explanations]

## Implementation Details
[Code structure, dependencies, complexity]

## Computational Requirements
[Memory, FLOPs, training time]

## Strengths
[What it does well]

## Limitations
[Known issues and constraints]

## Comparison Matrix
[Table comparing alternatives]

## Recommendation
[Whether and how to use for SCWM]
```

### Integration Analysis
```markdown
# [System] Integration Analysis

## System Overview
[Target system architecture]

## Integration Points
[Where SCWM connects]

## API Requirements
[Data formats, function signatures]

## Implementation Roadmap
[Step-by-step integration plan]

## Risk Assessment
[What could go wrong]

## Compute Budget
[Resource requirements]

## Recommendation
[Integration feasibility and approach]
```

## Fact-Checking Protocol

1. **Verify claims** against original sources
2. **Cross-reference** findings across multiple papers
3. **Check for retractions** or corrections
4. **Note conflicting evidence** explicitly
5. **Flag unverified claims** with confidence scores

## Devil's Advocate Prompts

For each major conclusion, consider:
- What if the opposite were true?
- What evidence would disprove this?
- What are we assuming without verification?
- Who benefits from this being believed?
- What alternative explanations exist?

## Confidence Scoring

| Score | Meaning | Criteria |
|-------|---------|----------|
| 90-100 | Very High | Multiple high-quality sources, reproducible results |
| 75-89 | High | Peer-reviewed sources, some verification |
| 60-74 | Moderate | Limited sources, some uncertainty |
| 45-59 | Low | Single source, unverified claims |
| 0-44 | Very Low | Speculation, contradictory evidence |

## Escalation Triggers

Pause and request human review when:
- Confidence score < 60%
- Conflicting findings from reputable sources
- Architectural decisions with long-term implications
- Integration changes affecting multiple systems
- Publication strategy decisions
