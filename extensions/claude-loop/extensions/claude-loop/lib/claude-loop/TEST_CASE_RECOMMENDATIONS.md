# Test Case Recommendations for claude-loop

**Quick Reference Guide**

---

## Top 3 Test Projects

### 1. DeepCode (PRIMARY) ⭐⭐⭐⭐⭐

**Path**: `/Users/jialiang.wu/Documents/Projects/DeepCode`

**What it is**: Multi-agent code generation system that transforms research papers into production code

**Why it's perfect**:
- 7 specialized agents (orchestrator, intent, document parsing, code planning, reference mining, indexing, generation)
- Uses MCP (Model Context Protocol) - same foundation as claude-loop
- Achieved 75.9% on PaperBench (beats human experts at 72.4%)
- Meta-circular test: AI agent system improving AI agent system

**Recommended Test**:
```
Task: "Add automated testing agent to DeepCode that validates generated code"
Duration: 3-5 days
Success: Tests pass DeepCode's own quality standards
```

**Stress-Test Value**: HIGHEST
- Multiple agent coordination
- Large codebase navigation
- Complex workflow orchestration
- Real-world benchmark validation

---

### 2. physical_ai_playground (SECONDARY) ⭐⭐⭐⭐

**Path**: `/Users/jialiang.wu/Documents/Projects/physical_ai_playground`

**What it is**: Collection of 15+ ML/AI research projects (Cosmos-Predict2, weather forecasting, object detection, robotics)

**Why it's valuable**:
- Multi-domain complexity (ML, CV, robotics, weather)
- Recent autonomous research mission (8 hours, 3,626 lines of code generated)
- Tests generalization across different problem spaces
- Real research-quality code

**Recommended Test**:
```
Task: "Create unified monitoring dashboard for all subprojects"
Duration: 4-6 days
Success: Dashboard tracks metrics from all 15 subprojects
```

**Stress-Test Value**: HIGH
- Multi-project coordination
- Domain breadth (ML/AI/research)
- Documentation-heavy navigation
- Research code patterns

---

### 3. AI-Trader (TERTIARY) ⭐⭐⭐⭐

**Path**: `/Users/jialiang.wu/Documents/Projects/AI-Trader`

**What it is**: Autonomous AI trading system where multiple AI models compete in real markets

**Why it's useful**:
- MCP toolchain architecture (similar to claude-loop)
- Multi-agent system (multiple AI traders competing)
- Real-world data integration (financial APIs, news)
- Production constraints (money, time-series data)

**Recommended Test**:
```
Task: "Implement risk management layer monitoring all agents"
Duration: 3-4 days
Success: Successfully prevents trading anomalies
```

**Stress-Test Value**: HIGH
- Real-time system integration
- Domain expertise required (finance)
- Safety-critical code
- State persistence across time

---

## Quick Comparison

| Feature | DeepCode | physical_ai | AI-Trader |
|---------|----------|-------------|-----------|
| **Complexity** | Very High | High | High |
| **Multi-Agent** | 7 agents | Research agents | Trading agents |
| **MCP Integration** | ✅ Yes | ❌ No | ✅ Yes |
| **Lines of Code** | ~50K+ | ~100K+ (scattered) | ~15K |
| **Domain** | Code Gen | ML/Research | Finance |
| **Setup Time** | 30 min | 1-2 hours | 30 min |
| **Best Tests** | Meta-level | Generalization | Production |

---

## Test Sequence

### Week 1-2: DeepCode
- Primary validation test
- Meta-circular proof of concept
- Benchmark against PaperBench

### Week 3: physical_ai_playground
- Domain generalization test
- Multi-project coordination
- Research code quality

### Week 4: AI-Trader
- Production patterns test
- Real-time system integration
- Safety-critical code

---

## Success Criteria

### For DeepCode:
- [ ] Successfully adds testing agent
- [ ] Generated code passes existing tests
- [ ] Integrates with 7 existing agents
- [ ] Follows DeepCode patterns

### For physical_ai_playground:
- [ ] Dashboard tracks all 15 subprojects
- [ ] Integrates with existing infrastructure
- [ ] Research-quality code
- [ ] Proper documentation

### For AI-Trader:
- [ ] Risk layer monitors all agents
- [ ] Integrates with MCP tools
- [ ] Handles real-time data
- [ ] Prevents anomalies

---

## Why These Three?

1. **Coverage**: Code generation, ML/research, finance
2. **Complexity**: Very High → High → High
3. **Patterns**: Multi-agent, pipelines, real-time
4. **Tech**: MCP, Python, various frameworks
5. **Domains**: Proves generalization

If claude-loop succeeds on all three:
✅ Validates core concept
✅ Demonstrates production readiness
✅ Proves cross-domain capability
✅ Shows agent coordination at scale

---

## Other Projects Surveyed (Not Recommended)

### lennyhub-rag ⭐⭐⭐
- Good RAG system example
- Well-documented
- But: Lower complexity, single-purpose
- Use as: Optional test #4 if time permits

### openwork ⭐⭐⭐
- Interesting desktop app example
- TypeScript instead of Python
- But: Different paradigm, UI-heavy
- Use as: Optional test #5 for TypeScript validation

### airefinery-sdk ⭐⭐
- Enterprise platform SDK
- But: Requires Accenture API key
- Not recommended unless access available

---

## Quick Start Commands

### DeepCode:
```bash
cd ~/Documents/Projects/DeepCode
# Review architecture
cat README.md
ls -la
# Start test
```

### physical_ai_playground:
```bash
cd ~/Documents/Projects/physical_ai_playground
# Explore structure
ls -la
# Check subprojects
ls cosmos-predict2/
```

### AI-Trader:
```bash
cd ~/Documents/Projects/AI-Trader
# Review trading system
cat README.md
# Check agent structure
ls agent/
```

---

## Next Steps

1. **This week**: Start DeepCode test
2. **Gather baseline**: Run DeepCode manually first
3. **Document process**: Record what manual approach looks like
4. **Run claude-loop**: Execute test with improvements
5. **Compare**: Manual vs. automated results
6. **Iterate**: Refine based on learnings

---

*For detailed analysis, see: [PROJECT_SURVEY_ANALYSIS.md](./PROJECT_SURVEY_ANALYSIS.md)*
