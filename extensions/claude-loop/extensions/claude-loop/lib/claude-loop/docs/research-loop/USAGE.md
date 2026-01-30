# Research Loop Usage Guide

This comprehensive guide covers installation, running research queries, interpreting results, customizing agents, and adding new domain adapters.

## Table of Contents

1. [Installation](#installation)
2. [Running Research Queries](#running-research-queries)
3. [Interpreting Results](#interpreting-results)
4. [Customizing Agents](#customizing-agents)
5. [Adding New Domain Adapters](#adding-new-domain-adapters)
6. [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

Research Loop is built on claude-loop and requires:

- **Python 3.10+** with standard library
- **PyYAML** for configuration parsing
- **claude-loop** base system

### Setup Steps

1. **Clone or navigate to claude-loop directory:**

   ```bash
   cd /path/to/claude-loop
   ```

2. **Verify research-loop is available:**

   ```bash
   ./research-loop.sh --help
   ```

3. **Install Python dependencies (if not already installed):**

   ```bash
   pip install pyyaml requests
   ```

4. **Configure API keys (optional but recommended):**

   Create or update `config.yaml` with your API keys:

   ```yaml
   api_keys:
     tavily: "your-tavily-api-key"  # For web search
     serpapi: "your-serpapi-key"    # Fallback search
   ```

   Or set environment variables:

   ```bash
   export TAVILY_API_KEY="your-tavily-api-key"
   export SERPAPI_KEY="your-serpapi-key"
   ```

### Verifying Installation

Run the test suite to verify everything is working:

```bash
pytest tests/test_ai_ml_research.py -v
pytest tests/test_investment_research.py -v
pytest tests/test_research_quality_gates.py -v
```

---

## Running Research Queries

### Basic Usage

The simplest way to run a research query:

```bash
./research-loop.sh "Your research question here"
```

### Domain-Specific Research

Use the `--adapter` flag to specify a domain:

```bash
# AI/ML Research
./research-loop.sh --adapter ai-ml "What are the latest advances in transformer architectures?"

# Investment Research (paper trading mode always enabled)
./research-loop.sh --adapter investment "Analyze Tesla stock fundamentals"
```

### Interactive Mode

Interactive mode enables human checkpoints for review:

```bash
./research-loop.sh --interactive "Complex research question"
```

In interactive mode, you'll be prompted at checkpoints to:
- **Approve** findings and continue
- **Request more depth** on specific topics
- **Redirect** the research direction
- **Cancel** the research

### Command Line Options

```bash
./research-loop.sh [OPTIONS] "research question"

Core Options:
  --adapter <name>        Domain adapter: ai-ml, investment (default: auto-detect)
  --interactive           Enable human checkpoints
  --auto-approve          Auto-approve all checkpoints (for automation)

Output Options:
  --output <format>       Output format: markdown, json, html (default: markdown)
  --output-file <path>    Save output to file
  --verbose               Enable verbose logging
  --quiet                 Suppress progress output

Research Control:
  --max-depth <n>         Maximum sub-question depth (default: 3)
  --max-sources <n>       Maximum sources per sub-question (default: 10)
  --timeout <seconds>     Research timeout (default: 300)

Help:
  --help                  Show this help message
  --version               Show version information
```

### Examples

#### AI/ML Research Examples

```bash
# Research latest advances
./research-loop.sh --adapter ai-ml \
  "What are the latest advances in vision transformers for image classification?"

# Compare approaches
./research-loop.sh --adapter ai-ml \
  "Compare few-shot learning approaches in NLP"

# Find SOTA benchmarks
./research-loop.sh --adapter ai-ml \
  "What is the current state-of-the-art on the GLUE benchmark?"

# Research specific architecture
./research-loop.sh --adapter ai-ml \
  "Explain the Mixture of Experts architecture and its applications"
```

#### Investment Research Examples

**Important:** Paper trading mode is ALWAYS enabled by default. No real money is ever involved.

```bash
# Stock analysis
./research-loop.sh --adapter investment \
  "Analyze Apple (AAPL) stock - fundamentals, technicals, and risks"

# Cryptocurrency research
./research-loop.sh --adapter investment \
  "What are the investment risks and opportunities in Ethereum?"

# Sector analysis
./research-loop.sh --adapter investment \
  "Analyze the semiconductor sector outlook for 2024"

# Interactive with checkpoints
./research-loop.sh --adapter investment --interactive \
  "Should I invest in AI-focused ETFs?"
```

---

## Interpreting Results

### Research Report Structure

A typical research report includes:

```markdown
# Research Report: [Your Question]

## Executive Summary
Brief overview of key findings with confidence score.

## Sub-Questions Investigated
1. Sub-question 1 - Agent: academic-scanner - Confidence: 85%
2. Sub-question 2 - Agent: benchmark-analyst - Confidence: 90%
3. Sub-question 3 - Agent: technical-diver - Confidence: 75%

## Key Findings
1. **Finding 1** [Source: arxiv.org] (Confidence: 90%)
   Detailed explanation of the finding...

2. **Finding 2** [Source: paperswithcode.com] (Confidence: 85%)
   Detailed explanation of the finding...

## Gaps Identified
- Coverage Gap: Sub-question 3 needs more sources
- Perspective Gap: Missing technical implementation details

## Confidence Analysis
Overall Confidence: 82%
- Source Count: 85% (8 authoritative sources)
- Source Agreement: 90% (high consensus)
- Recency: 75% (some older sources)
- Authority: 88% (mostly academic/official sources)

## Sources
1. [Paper Title](https://arxiv.org/abs/...) - arxiv.org
2. [Benchmark Results](https://paperswithcode.com/...) - paperswithcode.com
...

## Methodology
Description of research approach and agents used.

---
*Generated by Research Loop on [date]*
```

### Understanding Confidence Scores

Confidence scores range from 0-100 and are calculated based on:

| Factor | Weight (AI-ML) | Weight (Investment) | Description |
|--------|----------------|---------------------|-------------|
| Source Count | 20% | 15% | Number of quality sources |
| Source Agreement | 20% | 20% | Consensus among sources |
| Recency | 20% | 25% | How recent the data is |
| Authority | 25% | 25% | Domain authority of sources |
| Gaps | -penalty | -penalty | Deduction for research gaps |
| Conflicts | -penalty | -penalty | Deduction for unresolved conflicts |

**Confidence Levels:**
- **High (80-100)**: Strong evidence, multiple authoritative sources agree
- **Medium (50-79)**: Moderate evidence, some gaps or minor conflicts
- **Low (0-49)**: Limited evidence, significant gaps or conflicts

### Understanding Gaps

| Gap Type | Description | Action |
|----------|-------------|--------|
| **Coverage** | Sub-question not adequately answered | More research needed |
| **Perspective** | Missing agent perspective (e.g., no devil's advocate) | Run additional agents |
| **Depth** | Single source for a topic | Find corroborating sources |
| **Recency** | Sources too old for the domain | Find newer sources |

### Investment-Specific Results

Investment reports include additional sections:

```markdown
## Bull Case
Arguments supporting investment...

## Bear Case
Arguments against investment...

## Risk Assessment
- Market Risk: [rating]
- Liquidity Risk: [rating]
- Volatility: [rating]

## Paper Trading Summary
- Initial Balance: $100,000
- No real money involved

---
DISCLAIMER: This is research synthesis, NOT financial advice.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
---
```

---

## Customizing Agents

### Agent File Structure

Agents are defined in markdown files in the `agents/` directory:

```
agents/
  academic-scanner.md
  benchmark-analyst.md
  technical-diver.md
  market-analyst.md
  fact-checker.md
  devils-advocate.md
  lead-researcher.md
  fundamental-analyst.md
  technical-analyst.md
  risk-assessor.md
```

### Agent Specification Format

```markdown
# Agent Name

## Description
Brief description of the agent's purpose.

## Capabilities
- Capability 1
- Capability 2

## Search Strategy
How the agent searches for information...

## Output Format
```json
{
  "findings": [...],
  "sources": [...],
  "confidence": 0-100
}
```

## Quality Criteria
How findings are validated...

## Safety Guidelines
Important safety considerations...
```

### Modifying Existing Agents

To customize an agent:

1. **Copy the agent file:**
   ```bash
   cp agents/academic-scanner.md agents/custom-academic-scanner.md
   ```

2. **Edit the capabilities, search strategy, or output format**

3. **Reference in your adapter configuration:**
   ```yaml
   agents:
     primary:
       - custom-academic-scanner
   ```

### Creating New Agents

1. **Create a new agent file:**

   ```markdown
   # Custom Agent Name

   ## Description
   This agent specializes in [domain].

   ## Capabilities
   - Search [specific sources]
   - Analyze [specific data types]
   - Evaluate [specific criteria]

   ## Search Strategy
   1. Primary sources: [list sources]
   2. Secondary sources: [list sources]
   3. Validation: [approach]

   ## Output Format
   Structured findings with:
   - Content summary
   - Source URL
   - Relevance score (0-1)
   - Confidence level (0-100)

   ## Quality Criteria
   - Source authority check
   - Recency validation
   - Cross-reference verification

   ## Safety Guidelines
   - [Domain-specific safety considerations]
   ```

2. **Add to adapter configuration:**

   ```yaml
   agents:
     primary:
       - custom-agent-name
     secondary:
       - existing-agent
   ```

---

## Adding New Domain Adapters

### Adapter Structure

Create a new directory under `adapters/`:

```
adapters/
  your-domain/
    adapter.yaml        # Main configuration
    prompts/
      quality_gates.md  # Domain-specific quality gates
      synthesis.md      # Synthesis prompts (optional)
```

### Step 1: Create adapter.yaml

```yaml
---
# Your Domain Adapter Configuration
name: your-domain
description: "Description of your domain adapter"
version: 1.0.0

# Domain configuration
domain:
  # Keywords that trigger this adapter
  keywords:
    - keyword1
    - keyword2
    - keyword3

  # Domain-specific categories or classifications
  categories:
    - category1
    - category2

# Data source configurations
sources:
  primary_source:
    enabled: true
    base_url: "https://api.example.com"
    rate_limit:
      requests_per_second: 1
      burst: 5
    endpoints:
      search: "/search"
      details: "/details/{id}"

  secondary_source:
    enabled: true
    base_url: "https://api2.example.com"

# Quality gates specific to your domain
quality_gates:
  gate_name_1:
    enabled: true
    description: "What this gate checks"
    threshold: 0.7

  gate_name_2:
    enabled: true
    description: "Another quality check"
    requirements:
      - requirement1
      - requirement2

# Confidence scoring weights for your domain
confidence_weights:
  source_authority: 0.25
  data_recency: 0.20
  confirmation: 0.20
  domain_specific_factor: 0.35

# Agent assignments for your domain
agents:
  primary:
    - agent1
    - agent2
  secondary:
    - agent3
  quality_control:
    - devils-advocate

# Output template customization
output:
  mandatory_sections:
    - executive_summary
    - key_findings
    - sources
  optional_sections:
    - methodology
    - limitations

# Rate limiting and caching
cache:
  enabled: true
  ttl_hours: 24
  max_size_mb: 100
```

### Step 2: Create Quality Gates

Create `adapters/your-domain/prompts/quality_gates.md`:

```markdown
# Quality Gates for [Your Domain]

## Gate 1: [Gate Name]

### Purpose
[What this gate checks for]

### Implementation
```python
def check_gate_1(finding):
    # Check logic
    score = calculate_score(finding)
    return {
        'passed': score >= threshold,
        'score': score,
        'message': 'Explanation'
    }
```

### Thresholds
- Pass: >= 0.7
- Warning: 0.5 - 0.69
- Fail: < 0.5

## Gate 2: [Gate Name]

### Purpose
[What this gate checks for]

...
```

### Step 3: Create Domain-Specific Clients (Optional)

If your domain requires custom data clients:

```python
# lib/your_domain_client.py

from dataclasses import dataclass
from typing import List, Optional
import requests

@dataclass
class YourDomainResult:
    """Result from your domain API."""
    id: str
    title: str
    content: str
    url: str
    relevance_score: float

class YourDomainClient:
    """Client for your domain API."""

    BASE_URL = "https://api.example.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.rate_limit_seconds = 1.0

    def search(self, query: str, max_results: int = 10) -> List[YourDomainResult]:
        """Search for results in your domain."""
        # Implementation
        pass

    def get_details(self, id: str) -> YourDomainResult:
        """Get details for a specific result."""
        # Implementation
        pass
```

### Step 4: Register the Adapter

Add your adapter to the domain detection logic in `lib/agent-selector.py`:

```python
DOMAIN_KEYWORDS = {
    'ai-ml': [...],
    'investment': [...],
    'your-domain': [
        'keyword1',
        'keyword2',
        'keyword3'
    ]
}
```

### Step 5: Add Tests

Create tests for your adapter:

```python
# tests/test_your_domain_adapter.py

import pytest
import yaml
import os

class TestYourDomainAdapter:
    def test_adapter_yaml_exists(self):
        adapter_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'adapters', 'your-domain', 'adapter.yaml'
        )
        assert os.path.exists(adapter_path)

    def test_adapter_configuration(self):
        # Load and validate configuration
        pass

    def test_quality_gates(self):
        # Test domain-specific quality gates
        pass
```

---

## Troubleshooting

### Common Issues

#### "Module not found" errors

Ensure the lib directory is in your Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/claude-loop/lib"
```

#### API rate limiting

If you hit rate limits:

1. Check rate limit configuration in adapter.yaml
2. Enable caching if not already enabled
3. Add delays between requests

```yaml
rate_limits:
  source_name:
    requests_per_second: 0.5  # Reduce rate
    burst: 3

cache:
  enabled: true
  ttl_hours: 48  # Increase cache time
```

#### Low confidence scores

If confidence scores are consistently low:

1. Check source availability (API keys configured?)
2. Verify sources are returning data
3. Review quality gate thresholds
4. Check for network issues

#### Human checkpoint timeouts

If checkpoints are timing out:

```yaml
checkpoints:
  timeout_seconds: 600  # Increase timeout
```

Or use auto-approve mode for automation:

```bash
./research-loop.sh --auto-approve "Your question"
```

### Debug Mode

Enable verbose logging for debugging:

```bash
./research-loop.sh --verbose "Your question"
```

Or set the environment variable:

```bash
export RESEARCH_LOOP_DEBUG=1
./research-loop.sh "Your question"
```

### Getting Help

- Check the [FAQ](../FAQ.md)
- Review [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
- Open an issue on GitHub

---

## Best Practices

### For AI-ML Research

1. Be specific about the subfield (NLP, CV, RL, etc.)
2. Mention specific benchmarks if relevant
3. Specify time constraints ("papers from 2023")
4. Ask about reproducibility when important

### For Investment Research

1. **Always use paper trading mode** (it's the default)
2. Specify the asset type (stock, crypto, ETF)
3. Include both fundamental and technical aspects
4. Request explicit risk assessment
5. Use interactive mode for important decisions

### General Tips

1. Start with broad questions, then narrow down
2. Use follow-up queries for depth
3. Review gaps and address them in subsequent queries
4. Cross-reference findings with primary sources
5. Consider multiple perspectives

---

*Last updated: January 2024*
