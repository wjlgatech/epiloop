# Specific Test Scenarios for claude-loop

**Actionable test cases with clear success criteria**

---

## Test #1: DeepCode - Automated Testing Agent

### Scenario
Add a new "Testing Agent" to DeepCode that automatically validates generated code quality.

### Context
DeepCode currently has 7 agents but lacks automated testing validation. Generated code quality depends on human review and SimpleJudge evaluation.

### Task Description
```
Project: DeepCode
Task: Implement an automated Testing Agent that validates generated code

Requirements:
1. New agent class: TestingAgent (similar to existing agent pattern)
2. Integration with existing MCP architecture
3. Functionality:
   - Static analysis (pylint, mypy, ruff)
   - Unit test generation (pytest)
   - Code coverage measurement
   - Security scanning (bandit)
   - Documentation validation
4. Configuration in mcp_agent.config.yaml
5. Integration with code generation pipeline
6. Test report generation

Deliverables:
- TestingAgent implementation
- MCP server integration
- Configuration updates
- Unit tests for TestingAgent
- Documentation
- Example test reports
```

### Files to Modify
- Create: `/tools/testing_agent.py`
- Create: `/tools/testing_mcp_server.py`
- Modify: `/mcp_agent.config.yaml` (add testing server)
- Modify: `/core/orchestrator.py` (add testing stage)
- Create: `/tests/test_testing_agent.py`
- Modify: `/README.md` (document new agent)

### Success Criteria
- [ ] TestingAgent class implemented with all required checks
- [ ] Integrated with MCP architecture
- [ ] Generates actionable test reports
- [ ] Successfully tests existing DeepCode generated code
- [ ] Passes DeepCode's own quality standards
- [ ] Documentation complete
- [ ] Unit tests achieve >80% coverage

### Expected Complexity
- Estimated LOC: 800-1200
- Files touched: 6-8
- Agent interactions: Orchestrator, Code Generation Agent
- External tools: pytest, pylint, mypy, ruff, bandit

### Stress Test Value
- Tests understanding of existing multi-agent architecture
- Validates MCP server creation and integration
- Checks code quality implementation
- Evaluates documentation generation

### Time Estimate
**Manual**: 2-3 days for experienced developer
**claude-loop goal**: Complete in 4-6 hours with minimal intervention

---

## Test #2: physical_ai_playground - Unified Monitoring Dashboard

### Scenario
Create a unified monitoring dashboard that tracks metrics across all 15 subprojects in the physical_ai_playground.

### Context
physical_ai_playground contains 15+ independent projects (cosmos-predict2, weather_forecasting, license_plate_detection, etc.) with no centralized monitoring or metrics collection.

### Task Description
```
Project: physical_ai_playground
Task: Create unified monitoring dashboard for all subprojects

Requirements:
1. Dashboard framework (Streamlit or Gradio)
2. Metrics collection:
   - Training/inference metrics (cosmos-predict2)
   - Weather prediction accuracy (weather_forecasting)
   - Detection performance (license_plate_detection)
   - System resource usage
   - Experiment tracking
3. Data aggregation from diverse sources:
   - Model checkpoints
   - Log files
   - Config files
   - Wandb/tensorboard exports
4. Visualization:
   - Real-time metrics
   - Historical trends
   - Cross-project comparisons
   - Resource utilization
5. Integration with existing projects (minimal code changes)
6. Configuration system for adding new projects

Deliverables:
- Monitoring dashboard application
- Metrics collection system
- Database/storage for metrics
- Configuration system
- Integration scripts for each subproject
- Documentation
```

### Files to Create
- `/monitoring/dashboard.py` (main application)
- `/monitoring/metrics_collector.py` (data collection)
- `/monitoring/data_store.py` (storage layer)
- `/monitoring/config.yaml` (project configuration)
- `/monitoring/integrations/cosmos.py` (cosmos-predict2)
- `/monitoring/integrations/weather.py` (weather_forecasting)
- `/monitoring/integrations/detection.py` (various detection projects)
- `/monitoring/README.md` (documentation)
- `/monitoring/requirements.txt` (dependencies)

### Success Criteria
- [ ] Dashboard displays metrics from at least 10 subprojects
- [ ] Real-time updates (refresh every 30 seconds)
- [ ] Historical data storage (SQLite or similar)
- [ ] Easy to add new projects (just config update)
- [ ] Responsive web interface
- [ ] Resource usage tracking
- [ ] Complete documentation
- [ ] No breaking changes to existing projects

### Expected Complexity
- Estimated LOC: 1500-2000
- Files created: 10-15
- Subprojects integrated: 10+
- Data sources: Logs, checkpoints, configs, tracking tools

### Stress Test Value
- Tests multi-project navigation and understanding
- Validates data integration across diverse systems
- Checks UI generation capability
- Evaluates system design skills

### Time Estimate
**Manual**: 4-6 days for experienced developer
**claude-loop goal**: Complete in 1-2 days with minimal intervention

---

## Test #3: AI-Trader - Risk Management Layer

### Scenario
Implement a comprehensive risk management layer that monitors all trading agents and prevents anomalies.

### Context
AI-Trader currently allows agents to trade autonomously with minimal oversight. Need safety layer to prevent runaway losses, detect anomalies, and enforce risk limits.

### Task Description
```
Project: AI-Trader
Task: Implement risk management layer for autonomous trading

Requirements:
1. Risk Manager Agent:
   - Monitors all trading agents in real-time
   - Enforces position limits
   - Detects anomalous behavior
   - Circuit breaker functionality
2. Risk Metrics:
   - Portfolio value at risk (VaR)
   - Maximum drawdown limits
   - Position concentration
   - Trade frequency limits
   - Volatility-based position sizing
3. Alert System:
   - Real-time notifications
   - Automatic trade halting
   - Configurable thresholds
   - Alert history
4. Integration:
   - Works with all existing agents
   - Minimal changes to agent code
   - Uses MCP toolchain
   - Hooks into trading pipeline
5. Configuration:
   - Risk parameters per agent
   - Market-specific limits
   - Escalation policies

Deliverables:
- Risk Manager Agent implementation
- Risk calculation module
- Alert system
- Configuration system
- Integration with existing agents
- Monitoring dashboard
- Documentation
- Unit tests
```

### Files to Create/Modify
- Create: `/agent/risk_manager/risk_manager.py`
- Create: `/agent/risk_manager/risk_metrics.py`
- Create: `/agent/risk_manager/alert_system.py`
- Modify: `/agent_tools/tool_trade.py` (add risk checks)
- Create: `/configs/risk_config.json`
- Create: `/agent/risk_manager/dashboard.py`
- Modify: `/main.py` (integrate risk manager)
- Create: `/tests/test_risk_manager.py`
- Modify: `/README.md` (document risk system)

### Success Criteria
- [ ] Risk Manager monitors all agents
- [ ] Successfully prevents simulated anomalies
- [ ] Enforces position limits correctly
- [ ] Alert system triggers appropriately
- [ ] Dashboard shows real-time risk metrics
- [ ] Configurable per agent and market
- [ ] Zero false positives in normal operation
- [ ] Complete documentation and tests

### Expected Complexity
- Estimated LOC: 1200-1800
- Files touched: 10-12
- Integration points: All agents, trading tools, data pipeline
- Domain expertise: Finance, risk management

### Stress Test Value
- Tests domain-specific knowledge (finance)
- Validates real-time system integration
- Checks safety-critical code patterns
- Evaluates multi-agent monitoring

### Time Estimate
**Manual**: 3-4 days for experienced developer with domain knowledge
**claude-loop goal**: Complete in 1-2 days with minimal intervention

---

## Test #4 (Optional): lennyhub-rag - YouTube Transcript Integration

### Scenario
Add YouTube transcript support to expand the knowledge base beyond podcast transcripts.

### Task Description
```
Project: lennyhub-rag
Task: Add YouTube video transcript integration

Requirements:
1. YouTube transcript downloader (youtube-transcript-api)
2. Transcript processing pipeline
3. Integration with existing RAG system
4. Configuration for channels/playlists
5. Duplicate detection
6. Metadata extraction (video title, date, speakers)
7. Update web UI to show video sources

Deliverables:
- YouTube transcript downloader
- Processing pipeline
- Integration code
- Configuration system
- Updated UI
- Documentation
```

### Success Criteria
- [ ] Successfully downloads YouTube transcripts
- [ ] Processes into RAG-compatible format
- [ ] Integrates with Qdrant database
- [ ] UI shows video sources
- [ ] Query results include YouTube content
- [ ] Documentation complete

### Time Estimate
**Manual**: 2-3 days
**claude-loop goal**: Complete in 1 day

---

## Test #5 (Optional): openwork - Plugin System

### Scenario
Implement extensible plugin system for custom automations.

### Task Description
```
Project: openwork
Task: Create plugin system for custom automation skills

Requirements:
1. Plugin architecture (TypeScript)
2. Plugin discovery and loading
3. API for plugin developers
4. Settings UI for plugins
5. Security sandboxing
6. Example plugins (file renamer, text processor)
7. Plugin marketplace prep

Deliverables:
- Plugin system implementation
- Developer API
- Settings UI
- Example plugins
- Documentation
- Plugin template
```

### Success Criteria
- [ ] Plugins can be loaded dynamically
- [ ] Settings UI works
- [ ] Example plugins functional
- [ ] Developer docs complete
- [ ] TypeScript types correct

### Time Estimate
**Manual**: 3-4 days
**claude-loop goal**: Complete in 1-2 days

---

## Evaluation Framework

### For Each Test, Measure:

#### 1. Completion Metrics
- Time to completion
- Number of iterations required
- Human intervention points
- Error recovery events

#### 2. Code Quality
- Passes existing tests
- New test coverage
- Code style compliance
- Documentation quality
- Architecture alignment

#### 3. Integration Quality
- Works with existing systems
- No breaking changes
- Proper error handling
- Performance acceptable

#### 4. Agent Performance
- Context window usage
- Number of file operations
- API calls made
- Tool usage patterns

#### 5. Domain Understanding
- Correct domain patterns
- Appropriate design decisions
- Proper terminology usage
- Best practices followed

---

## Baseline Establishment

### Before Running claude-loop Tests:

1. **Manual Baseline**:
   - Have experienced developer complete Task #1 manually
   - Record time, process, decisions made
   - Document challenges encountered

2. **Current claude-loop Baseline**:
   - Run Task #1 with current claude-loop version
   - Record performance, issues, failures
   - Note improvement opportunities

3. **Comparison**:
   - Manual time vs. claude-loop time
   - Code quality comparison
   - Integration success rate
   - Documentation completeness

### Success Definition:
claude-loop should achieve:
- ≥80% time reduction vs. manual
- ≥90% code quality vs. manual
- 100% integration success
- ≥95% documentation completeness

---

## Recommended Execution Order

### Week 1: Baseline & Setup
1. Manual completion of Test #1 (DeepCode)
2. Document manual process
3. Run current claude-loop on Test #1
4. Identify gaps

### Week 2: Improved claude-loop - Test #1
5. Apply improvements to claude-loop
6. Run Test #1 with improved version
7. Compare against baselines
8. Iterate on improvements

### Week 3: Test #2
9. Run improved claude-loop on Test #2 (physical_ai)
10. Validate cross-domain capability
11. Refine based on learnings

### Week 4: Test #3 & Optional Tests
12. Run Test #3 (AI-Trader)
13. Run optional tests if time permits
14. Final evaluation and report

---

## Success Indicators

### Test #1 (DeepCode) Success Indicators:
✅ Testing agent integrates seamlessly
✅ Generates useful test reports
✅ No breaking changes to existing agents
✅ Documentation is clear and complete
✅ Time: <6 hours with <3 human interventions

### Test #2 (physical_ai) Success Indicators:
✅ Dashboard tracks ≥10 subprojects
✅ Real-time updates work
✅ No changes required to subprojects
✅ Easy to add new projects
✅ Time: <2 days with <5 human interventions

### Test #3 (AI-Trader) Success Indicators:
✅ Risk manager prevents all test anomalies
✅ Zero false positives
✅ Integrates with all agents
✅ Dashboard shows real-time metrics
✅ Time: <2 days with <5 human interventions

---

## Failure Analysis Plan

### If Test Fails:

1. **Categorize Failure**:
   - Code quality issue
   - Integration problem
   - Domain understanding gap
   - Agent coordination failure
   - Context/memory limitation

2. **Root Cause**:
   - What specific capability was missing?
   - Where did agent get stuck?
   - What would have helped?

3. **Improvement**:
   - What specific improvement needed?
   - Priority (critical, high, medium, low)
   - Estimated effort to fix

4. **Retry**:
   - Apply improvement
   - Re-run test
   - Validate fix

---

## Reporting Template

### Test Report Format:

```markdown
# Test Report: [Test Name]

## Summary
- Start time: [timestamp]
- End time: [timestamp]
- Duration: [hours]
- Status: [Success/Partial/Failure]
- Human interventions: [count]

## Metrics
- Files created: [count]
- Files modified: [count]
- Lines of code: [count]
- Tests added: [count]
- API calls made: [count]

## Quality Assessment
- Code quality: [score/10]
- Integration quality: [score/10]
- Documentation quality: [score/10]
- Overall: [score/10]

## Agent Performance
- Context usage: [tokens/max]
- Iterations required: [count]
- Error recovery: [count]
- Tool efficiency: [score/10]

## Success Criteria Met
- [ ] Criterion 1
- [ ] Criterion 2
- ...

## Issues Encountered
1. Issue description
   - Impact: [High/Medium/Low]
   - Resolution: [description]

## Improvements Needed
1. Improvement description
   - Priority: [Critical/High/Medium/Low]
   - Effort: [hours]

## Comparison vs. Baseline
- Time: [X% of manual time]
- Quality: [X% of manual quality]
- Completeness: [X%]

## Conclusion
[Overall assessment and recommendations]
```

---

*Use these specific scenarios to validate claude-loop improvements systematically*
