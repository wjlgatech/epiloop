# Autonomous Mission Defaults

This document defines default behaviors that are ALWAYS active during claude-loop execution, even when not explicitly mentioned by the user.

---

## Core Execution Principles (Always Active)

These principles are baked into every claude-loop execution and require no user invocation:

### 1. Maximum Parallelization
**Always spawn parallel agents when independent tasks exist.**

- If multiple research topics need exploration → spawn parallel Task agents
- If multiple tests need running → run them concurrently
- If multiple files need analysis → read them in parallel
- **Rule**: Never serialize what can be parallelized

```bash
# This is implicit - no flag needed
# Every execution automatically parallelizes where possible
```

### 2. TDD Approach (Test-Driven Development)
**Write tests before or alongside implementation.**

- Before implementing a feature, create test cases
- Run tests after every significant change
- Never mark a story complete without passing tests
- **Rule**: Code without tests is incomplete code

```bash
# This is implicit - no flag needed
# Every story implementation includes test creation/execution
```

### 3. Efficiency & Cost Monitoring
**Track and optimize resource usage.**

- Monitor token usage per iteration
- Use haiku for simple tasks, sonnet/opus for complex
- Batch similar operations to reduce API calls
- Report cost estimates in progress.txt
- **Rule**: Optimize for value per dollar

```bash
# This is implicit - no flag needed
# Cost tracking is automatic
```

### 4. Self-Upgrade from Learnings
**Continuously improve from experience.**

- After each iteration, extract learnings
- Update AGENTS.md with new patterns discovered
- Add to experience store for future retrieval
- Self-critique solutions before finalizing
- **Rule**: Every failure or deficiency is a learning opportunity

```bash
# This is implicit - no flag needed
# Learning extraction is automatic
```

---

## Time-Based Mission Protocol

### When a user specifies a time-based deadline (e.g., "until 8 AM", "for 6 hours"):

**CRITICAL RULES:**

1. **Create Time-Constraint Todo**
   ```json
   {
     "content": "HARD CONSTRAINT: Continue until [DEADLINE]",
     "status": "in_progress",
     "activeForm": "Working until deadline"
   }
   ```
   This todo MUST remain `in_progress` until the actual time passes or user says stop.

2. **Infinite Work Queue**
   After completing primary deliverables, generate additional work:
   - Improve existing documents
   - Add more tests
   - Create visualizations
   - Research deeper
   - Draft additional outputs
   - Validate and refine claims

3. **"What Else?" Loop**
   When all defined tasks are done, ask:
   - Can I improve any deliverable?
   - Can I add more depth?
   - Can I validate claims with more sources?
   - Can I create supporting materials?
   - Can I anticipate next steps?

4. **Never Declare "Mission Complete" Early**
   The phrase "mission complete" or equivalent can ONLY be used when:
   - Time deadline has passed, OR
   - User explicitly says to stop

   Until then, ALWAYS find more valuable work to do.

---

## Implicit Quality Gates

Every execution passes through these gates automatically:

### Code Quality
- [ ] Compiles without errors
- [ ] Type checks pass
- [ ] Linter passes
- [ ] Tests pass (>80% coverage for new code)
- [ ] No security vulnerabilities
- [ ] No hardcoded secrets

### Research Quality
- [ ] Multiple sources consulted
- [ ] Contrarian views considered
- [ ] Claims are verifiable
- [ ] Limitations acknowledged
- [ ] Confidence scores provided

### Documentation Quality
- [ ] Clear and actionable
- [ ] Examples provided
- [ ] Edge cases noted
- [ ] Dependencies documented

---

## Self-Critique Protocol

Before finalizing ANY major output:

1. **Devil's Advocate Pass**
   - What could go wrong?
   - What are the weakest claims?
   - What would a critic say?

2. **Completeness Check**
   - Did I address all requirements?
   - Did I miss any edge cases?
   - Is this production-ready?

3. **Improvement Identification**
   - What would make this 10% better?
   - What's the next logical step?
   - What did I learn that applies elsewhere?

---

## Failure Recovery

When encountering blockers:

1. **Document the Failure**
   - What went wrong?
   - What was tried?
   - What is the root cause?

2. **Attempt Recovery**
   - Try alternative approaches
   - Seek additional context
   - Simplify the problem

3. **Learn from Failure**
   - Add to experience store
   - Update patterns documentation
   - Prevent future occurrences

4. **Never Give Up Silently**
   - Always report what was attempted
   - Always suggest next steps
   - Always preserve partial progress

---

## Configuration

These defaults can be overridden with explicit flags if needed:

```bash
# Override parallelization
./claude-loop.sh --no-parallel

# Override TDD requirement
./claude-loop.sh --skip-tests

# Override cost monitoring
./claude-loop.sh --no-cost-tracking

# Override self-upgrade
./claude-loop.sh --no-learning
```

But by default, ALL of these are ACTIVE.

---

*This document is part of the claude-loop operating system and defines implicit behaviors.*
