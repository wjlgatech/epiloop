# Using claude-loop Skills

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST use that skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule

**Use relevant skills BEFORE any response or action.** Even a 1% chance a skill might apply means you should use it. If a skill turns out to be wrong for the situation after using it, you don't need to follow it.

## Red Flags - These Thoughts Mean STOP

These thoughts mean you're rationalizing. Check for skills instead:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check files quickly" | Skills provide systematic approaches. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Check current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. |

## Available Skills (Implemented)

### Planning & Design

**brainstorming**
- **When**: Before any creative work - creating features, building components, architecture decisions
- **Core principle**: Socratic design refinement before code
- **Process**: Ask questions one at a time → explore alternatives → present design in sections → validate incrementally
- **Usage**: Mandatory for complexity >= 5, recommended for all new features
- **Location**: `skills/brainstorming/SKILL.md`

### Code Generation & Specification

**api-spec-generator**
- **When**: Generating OpenAPI specifications from existing code or requirements
- **Core principle**: Automated API documentation generation
- **Usage**: When building or documenting REST APIs
- **Location**: `skills/api-spec-generator/SKILL.md`

**test-scaffolder**
- **When**: Need to generate test file structures from code
- **Core principle**: Automated test template generation
- **Usage**: When starting testing for new modules or files
- **Location**: `skills/test-scaffolder/SKILL.md`

### PRD & Project Management

**prd**
- **When**: Converting user requirements into structured PRD JSON format
- **Core principle**: Structured requirement documentation
- **Usage**: At project start when defining user stories and requirements
- **Location**: `skills/prd/SKILL.md`

**prd-validator**
- **When**: Validating PRD structure, dependencies, and completeness
- **Core principle**: Ensure PRD quality before execution
- **Usage**: After creating or modifying PRD files
- **Location**: `skills/prd-validator/SKILL.md`

**claude-loop**
- **When**: Need to convert PRD from various formats to claude-loop JSON format
- **Core principle**: PRD format standardization
- **Usage**: When importing PRDs from external sources
- **Location**: `skills/claude-loop/SKILL.md`

### Git & Code Quality

**commit-formatter**
- **When**: Creating git commits during development
- **Core principle**: Enforce commit message standards and conventions
- **Usage**: Always use when making commits (automatic via hooks)
- **Location**: `skills/commit-formatter/SKILL.md`

### Optimization

**cost-optimizer**
- **When**: Analyzing story complexity to recommend appropriate models
- **Core principle**: Balance quality and cost by selecting right model for task complexity
- **Usage**: At story planning phase
- **Location**: `skills/cost-optimizer/SKILL.md`

### Meta

**hello-world**
- **When**: Learning to create new skills
- **Core principle**: Example skill template with script execution
- **Usage**: Reference when building new skills
- **Location**: `skills/hello-world/SKILL.md`

## Skill Priority

When multiple skills could apply, use this order:

1. **Process skills first** (brainstorming) - determine HOW to approach the task
2. **Planning skills second** (prd, prd-validator) - structure requirements
3. **Implementation skills third** (api-spec-generator, test-scaffolder) - generate code/specs
4. **Quality skills last** (commit-formatter, cost-optimizer) - ensure quality and efficiency

**Examples**:
- "Let's build authentication feature" → brainstorming → prd → api-spec-generator → test-scaffolder → commit-formatter
- "Create API for user management" → api-spec-generator → test-scaffolder
- "Convert requirements doc to PRD" → prd → prd-validator

## Skill Invocation

**In this session:**
- Skills are stored in `skills/` directory
- Use the Read tool to load skill content: `skills/<skill-name>/SKILL.md`
- Follow the skill exactly as presented

**Announcing skill usage:**
When using a skill, announce it: "I'm using the <skill-name> skill to <purpose>."

## Remember

- Skills are **mandatory workflows**, not suggestions
- Check for skills **before** any action
- Follow skills **exactly** - don't adapt away discipline
- If 1% chance applies → use it
- Process skills before implementation skills
- Announce skill usage clearly

---

## TODO: Skills to be Implemented

The following skills are referenced in workflows but not yet implemented. They will be added in future releases:

### Testing & Quality (TODO)
- **test-driven-development**: Write test first, watch it fail, write minimal code to pass (TDD Iron Law)
- **systematic-debugging**: 4-phase root cause process for debugging
- **verification-before-completion**: Ensure tasks are actually complete before marking done

### Planning & Execution (TODO)
- **writing-plans**: Break tasks into bite-sized 2-5 minute steps with exact code
- **executing-plans**: Batch execution of written plans with checkpoints
- **subagent-driven-development**: Fresh subagent per task + two-stage review

### Code Review (TODO)
- **requesting-code-review**: Pre-review checklist + two-stage review (spec compliance → code quality)
- **receiving-code-review**: Systematic response to review feedback

### Git & Workflow (TODO)
- **using-git-worktrees**: Isolated workspaces with safety verification
- **finishing-a-development-branch**: Verify tests, present merge/PR/keep/discard options

### Meta (TODO)
- **writing-skills**: Best practices for creating new skills with testing methodology

**Note**: Until these skills are implemented, refer to documentation in:
- `docs/features/tdd-enforcement.md` (for TDD guidance)
- `docs/features/two-stage-review.md` (for code review guidance)
- `docs/features/brainstorming.md` (for planning guidance)
