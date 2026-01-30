# Research Loop

**Agentic Research Team for claude-loop**

Research Loop is an autonomous research orchestration system that coordinates specialized AI agents to investigate complex questions, synthesize findings from multiple sources, and produce verified research reports with confidence scores.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Domain Adapters](#domain-adapters)
- [Configuration Options](#configuration-options)
- [Safety Features](#safety-features)
- [Quality Gates](#quality-gates)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)

---

## Quick Start

### Basic Usage

```bash
# Run a research query
./research-loop.sh "What are the latest advances in vision transformers?"

# Run with specific domain adapter
./research-loop.sh --adapter ai-ml "Compare BERT and GPT architectures"

# Investment research (paper trading mode enabled by default)
./research-loop.sh --adapter investment "Should I invest in AAPL?"

# Interactive mode with human checkpoints
./research-loop.sh --interactive "Analyze the crypto market trends"
```

### Installation

Research Loop is built on claude-loop and requires no additional installation beyond the base system.

```bash
# Ensure claude-loop is set up
cd /path/to/claude-loop

# Verify research-loop is available
./research-loop.sh --help
```

### Dependencies

- Python 3.10+
- YAML configuration support
- Optional: API keys for external data sources (Tavily, arXiv, etc.)

---

## Architecture Overview

Research Loop uses a multi-agent architecture where specialized agents collaborate under the direction of a Lead Researcher agent.

```
                     +-------------------+
                     |  Research Query   |
                     +--------+----------+
                              |
                     +--------v----------+
                     | Question Decomposer|
                     +--------+----------+
                              |
              +---------------+---------------+
              |               |               |
     +--------v------+ +------v-------+ +-----v--------+
     | Sub-Question 1| |Sub-Question 2| |Sub-Question 3|
     +--------+------+ +------+-------+ +-----+--------+
              |               |               |
     +--------v------+ +------v-------+ +-----v--------+
     |Academic Scanner| |Benchmark    | |Technical    |
     |               | |Analyst      | |Diver        |
     +--------+------+ +------+-------+ +-----+--------+
              |               |               |
              +---------------+---------------+
                              |
                     +--------v----------+
                     |   Synthesizer     |
                     +--------+----------+
                              |
                     +--------v----------+
                     | Quality Control   |
                     | (Fact Checker,    |
                     |  Devil's Advocate)|
                     +--------+----------+
                              |
                     +--------v----------+
                     |  Research Report  |
                     +-------------------+
```

### Core Components

| Component | Description | Location |
|-----------|-------------|----------|
| **Research Orchestrator** | Main coordination logic | `lib/research-orchestrator.py` |
| **Question Decomposer** | Breaks questions into sub-questions | `lib/question-decomposer.py` |
| **Research Synthesizer** | Combines findings from multiple agents | `lib/research_synthesizer.py` |
| **Confidence Scorer** | Calculates confidence scores | `lib/confidence_scorer.py` |
| **Source Evaluator** | Evaluates source credibility | `lib/source-evaluator.py` |
| **Claim Verifier** | Verifies claims against sources | `lib/claim-verifier.py` |

### Agents

| Agent | Role | Location |
|-------|------|----------|
| **Lead Researcher** | Orchestrates research, synthesizes findings | `agents/lead-researcher.md` |
| **Academic Scanner** | Searches arXiv, Semantic Scholar | `agents/academic-scanner.md` |
| **Technical Diver** | Searches GitHub, documentation | `agents/technical-diver.md` |
| **Market Analyst** | Searches market data, news | `agents/market-analyst.md` |
| **Benchmark Analyst** | Tracks SOTA benchmarks | `agents/benchmark-analyst.md` |
| **Fact Checker** | Verifies claims | `agents/fact-checker.md` |
| **Devil's Advocate** | Challenges conclusions | `agents/devils-advocate.md` |

---

## Domain Adapters

Domain adapters customize Research Loop for specific research domains.

### AI-ML Adapter

Specialized for AI and Machine Learning research.

**Features:**
- arXiv API integration (cs.AI, cs.LG, cs.CL, cs.CV categories)
- Papers With Code integration for SOTA benchmarks
- Reproducibility checking (code/data availability)
- Benchmark validation against known datasets

**Configuration:** `adapters/ai-ml/adapter.yaml`

```yaml
name: ai-ml
domain:
  arxiv_categories:
    - cs.AI
    - cs.LG
    - cs.CL
    - cs.CV
  top_venues:
    conferences: [NeurIPS, ICML, ICLR, CVPR, ACL]
    journals: [JMLR, PAMI, Nature Machine Intelligence]

quality_gates:
  reproducibility:
    enabled: true
    check_code_availability: true
  benchmark_validity:
    enabled: true
    known_benchmarks:
      nlp: [GLUE, SuperGLUE, SQuAD, MMLU]
      vision: [ImageNet, COCO, ADE20K]
```

**Usage:**
```bash
./research-loop.sh --adapter ai-ml "What are the latest advances in vision transformers?"
```

### Investment Adapter

Specialized for investment research with mandatory safety features.

**Features:**
- Yahoo Finance integration for stock data
- CoinGecko integration for cryptocurrency data
- Paper trading mode (enabled by default)
- Human checkpoints for all investment research
- Mandatory risk disclosures

**Configuration:** `adapters/investment/adapter.yaml`

```yaml
name: investment
paper_trading:
  enabled: true  # ALWAYS default to true

domain:
  asset_classes:
    stocks: {enabled: true}
    crypto: {enabled: true}
    options: {enabled: true}

quality_gates:
  source_recency:
    enabled: true
    thresholds:
      trading_decisions:
        max_age_hours: 24
  confirmation_bias:
    enabled: true
    requirements:
      - require_bear_case
      - require_bull_case
  risk_disclosure:
    enabled: true
    required_disclosures:
      - paper_trading_notice
      - not_financial_advice
      - past_performance_warning
```

**Usage:**
```bash
# Paper trading mode is ALWAYS enabled by default
./research-loop.sh --adapter investment "Should I invest in AAPL?"
```

**DISCLAIMER:** Investment research is for informational purposes only and does NOT constitute financial advice. Paper trading mode ensures no real money is involved. Always consult a qualified financial advisor.

---

## Configuration Options

### Global Configuration

Set in `config.yaml`:

```yaml
research_loop:
  # Default adapter
  default_adapter: ai-ml

  # Human checkpoint settings
  checkpoints:
    require_approval: true
    timeout_seconds: 300
    investment_always_checkpoint: true
    low_confidence_threshold: 50

  # Output settings
  output:
    format: markdown
    include_citations: true
    include_confidence_scores: true
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RESEARCH_LOOP_ADAPTER` | Default domain adapter | `ai-ml` |
| `RESEARCH_LOOP_INTERACTIVE` | Enable interactive mode | `false` |
| `TAVILY_API_KEY` | Tavily search API key | (none) |
| `SERPAPI_KEY` | SerpAPI key (fallback) | (none) |

### Command Line Options

```bash
./research-loop.sh [OPTIONS] "research question"

Options:
  --adapter <name>      Domain adapter (ai-ml, investment)
  --interactive         Enable human checkpoints
  --auto-approve        Auto-approve checkpoints (non-interactive)
  --output <format>     Output format (markdown, json, html)
  --max-depth <n>       Maximum research depth
  --timeout <seconds>   Research timeout
  --verbose            Enable verbose logging
  --help               Show help
```

---

## Safety Features

### Paper Trading (Investment)

Paper trading is **always enabled by default** for investment research. This ensures no real money is ever involved.

```python
# Paper trading is enforced in code
client = YahooFinanceClient()  # paper_trading=True by default
assert client.paper_trading is True
```

**Paper Trading Features:**
- $100,000 simulated starting balance
- Track trades without real money
- Calculate theoretical P&L
- No connection to real brokerage accounts

### Human Checkpoints

Human checkpoints pause research at critical points for human review.

**Triggers:**
- Investment domain research (always)
- Low confidence findings (<50%)
- High-stakes domains (medical, legal)
- Conflicting findings
- When explicitly requested

**Checkpoint Options:**
1. **Approve** - Continue with current findings
2. **Request More Depth** - Gather additional information
3. **Redirect** - Change research direction
4. **Cancel** - Stop research

### Mandatory Disclaimers

Investment research always includes:

```
---
DISCLAIMER: This is research synthesis, NOT financial advice.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
Paper trading mode is enabled - no real money involved.
---
```

### Confirmation Bias Protection

Investment research requires:
- Bull case analysis
- Bear case analysis
- Minimum 2 opposing viewpoints
- Devil's advocate review

---

## Quality Gates

### Universal Quality Gates

| Gate | Description | Applies To |
|------|-------------|------------|
| **Source Recency** | Flags stale data | All domains |
| **Citation Accuracy** | Verifies claims against sources | All domains |
| **Confidence Calibration** | Ensures scores are well-calibrated | All domains |

### AI-ML Quality Gates

| Gate | Description |
|------|-------------|
| **Reproducibility** | Checks for code/data availability |
| **Benchmark Validity** | Validates against known benchmarks |
| **Citation Normalization** | Accounts for paper age in citations |
| **Recency Weight** | Weights recent papers higher in fast-moving fields |

### Investment Quality Gates

| Gate | Description |
|------|-------------|
| **Source Recency** | Trading data max 24 hours old |
| **Confirmation Bias** | Requires bull and bear cases |
| **Risk Disclosure** | Mandatory risk warnings |
| **Liquidity Check** | Verifies adequate trading volume |
| **Backtesting Caveat** | Warns about backtesting limitations |

---

## Usage Examples

### AI-ML Research

```bash
# Research latest advances
./research-loop.sh --adapter ai-ml \
  "What are the latest advances in vision transformers for image classification?"

# Compare architectures
./research-loop.sh --adapter ai-ml \
  "Compare transformer and CNN architectures for computer vision"

# Find SOTA benchmarks
./research-loop.sh --adapter ai-ml \
  "What is the current SOTA on ImageNet classification?"
```

### Investment Research

```bash
# Stock analysis (paper trading mode)
./research-loop.sh --adapter investment \
  "Analyze AAPL stock fundamentals and technicals"

# Crypto research
./research-loop.sh --adapter investment \
  "What are the investment risks of Bitcoin?"

# With explicit human checkpoints
./research-loop.sh --adapter investment --interactive \
  "Should I invest in semiconductor ETFs?"
```

### General Research

```bash
# Technology research
./research-loop.sh "What are the environmental impacts of AI training?"

# Comparative research
./research-loop.sh "Compare different approaches to AI alignment"
```

---

## API Reference

### Research Orchestrator

```python
from lib.research_orchestrator import ResearchOrchestrator

# Initialize
orchestrator = ResearchOrchestrator(adapter='ai-ml')

# Run research
result = orchestrator.research(
    question="What are the latest advances in transformers?",
    max_depth=3,
    interactive=False
)

# Access results
print(result.synthesis.summary)
print(result.synthesis.confidence.score)
print(result.synthesis.sources)
```

### Research Synthesizer

```python
from lib.research_synthesizer import ResearchSynthesizer, Finding

# Initialize
synthesizer = ResearchSynthesizer(domain='ai-ml')

# Create findings
findings_by_agent = {
    'academic-scanner': [
        Finding(
            id='F-001',
            content='Finding from academic source',
            source_url='https://arxiv.org/abs/...',
            agent='academic-scanner',
            relevance_score=0.95
        )
    ]
}

# Synthesize
synthesis = synthesizer.synthesize(
    question="Research question",
    findings_by_agent=findings_by_agent,
    sub_questions=[...]
)
```

### Confidence Scorer

```python
from lib.confidence_scorer import ConfidenceScorer

scorer = ConfidenceScorer(domain='ai-ml')

result = scorer.score(
    sources=[{'url': '...', 'relevance': 0.9, 'agent': '...'}],
    gaps=0,
    conflicts=0
)

print(f"Confidence: {result.score}%")
print(f"Explanation: {result.explanation}")
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to Research Loop.

### Running Tests

```bash
# Run all research-loop tests
pytest tests/test_ai_ml_research.py tests/test_investment_research.py tests/test_research_quality_gates.py -v

# Run specific test file
pytest tests/test_ai_ml_research.py -v

# Run with coverage
pytest tests/test_*research*.py --cov=lib --cov-report=html
```

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

Research Loop is built on claude-loop's orchestration layer and integrates with:
- arXiv API for academic papers
- Papers With Code for SOTA benchmarks
- Yahoo Finance for stock data
- CoinGecko for cryptocurrency data
- Tavily for web search

---

**Note:** For investment research, always remember that this tool provides research synthesis only, NOT financial advice. Paper trading mode is enabled by default to ensure safety.
