# /prd - Product Requirements Document Generator

Generate structured PRDs for features that can be processed by claude-loop.

## Usage

```
/prd <feature description>
/prd "Add user authentication with OAuth support"
/prd --from-issue <issue-url>
```

## What This Skill Does

Transforms a feature idea into a well-structured Product Requirements Document (PRD)
with properly sized user stories that can be implemented autonomously by claude-loop.

## Output Format

The skill generates a `PRD.md` file with:

```markdown
# PRD: [Feature Name]

## Overview
[Brief description of the feature and its value]

## Problem Statement
[What problem does this solve? Why is it needed?]

## Goals
- [Goal 1]
- [Goal 2]

## Non-Goals
- [What this feature explicitly does NOT do]

## User Stories

### US-001: [Story Title]
**As a** [user type]
**I want** [capability]
**So that** [benefit]

**Acceptance Criteria:**
- [ ] [Criterion 1]
- [ ] [Criterion 2]

**Priority:** 1 (highest)
**Estimated Complexity:** Small/Medium/Large

---

### US-002: [Story Title]
...

## Technical Considerations
- [Architecture decisions]
- [Dependencies]
- [Constraints]

## Success Metrics
- [How we measure success]
```

## Story Sizing Guidelines

**CRITICAL**: Each story must be completable in a single claude-loop iteration
(one LLM context window). Follow these guidelines:

### Small Stories (Preferred)
- Single file changes
- One function or component
- Simple logic
- ~30 min human equivalent

### Medium Stories (Acceptable)
- 2-3 file changes
- One module or feature slice
- Moderate complexity
- ~1-2 hour human equivalent

### Large Stories (Split Required)
If a story feels large, split it:
- Split by layer (data → API → UI)
- Split by operation (create → read → update → delete)
- Split by component (header → body → footer)

## Story Ordering Rules

Stories must be ordered by dependency:
1. **Foundation first**: Setup, configuration, types
2. **Data layer**: Models, schemas, database
3. **Logic layer**: Business logic, services
4. **API layer**: Endpoints, controllers
5. **UI layer**: Components, pages
6. **Polish**: Documentation, cleanup

## Example

**Input:**
```
/prd Add a dark mode toggle to the settings page
```

**Output (PRD.md):**
```markdown
# PRD: Dark Mode Toggle

## Overview
Add the ability for users to switch between light and dark themes.

## Problem Statement
Users working in low-light environments experience eye strain with the
current light-only theme. A dark mode option improves accessibility and
user comfort.

## Goals
- Provide a toggle in settings to switch themes
- Persist theme preference across sessions
- Apply theme consistently across all components

## Non-Goals
- System-preference auto-detection (future enhancement)
- Custom color themes beyond light/dark

## User Stories

### US-001: Create theme context and types
**As a** developer
**I want** a theme context with TypeScript types
**So that** components can access and update the current theme

**Acceptance Criteria:**
- [ ] ThemeContext created with light/dark values
- [ ] useTheme hook for accessing theme
- [ ] TypeScript types for theme values
- [ ] Unit tests pass

**Priority:** 1
**Estimated Complexity:** Small

---

### US-002: Implement theme persistence
**As a** user
**I want** my theme preference saved
**So that** it persists across browser sessions

**Acceptance Criteria:**
- [ ] Theme saved to localStorage
- [ ] Theme loaded on app initialization
- [ ] Fallback to light theme if no preference

**Priority:** 2
**Estimated Complexity:** Small

---

### US-003: Create CSS custom properties for theming
**As a** developer
**I want** CSS variables for theme colors
**So that** components can use theme-aware colors

**Acceptance Criteria:**
- [ ] CSS custom properties defined for both themes
- [ ] Variables cover: background, text, borders, accents
- [ ] Smooth transition between themes

**Priority:** 3
**Estimated Complexity:** Small

---

### US-004: Add toggle component to settings
**As a** user
**I want** a toggle switch in settings
**So that** I can switch between light and dark mode

**Acceptance Criteria:**
- [ ] Toggle component renders in settings page
- [ ] Toggle reflects current theme state
- [ ] Clicking toggle changes theme immediately
- [ ] Visual feedback on toggle state

**Priority:** 4
**Estimated Complexity:** Small

---

### US-005: Apply theme to existing components
**As a** user
**I want** all UI components to respect my theme choice
**So that** the entire app follows my preference

**Acceptance Criteria:**
- [ ] All components use CSS custom properties
- [ ] No hardcoded colors remain
- [ ] Visual verification in both themes passes

**Priority:** 5
**Estimated Complexity:** Medium

## Technical Considerations
- Use CSS custom properties for maximum compatibility
- Consider prefers-color-scheme for future enhancement
- Ensure sufficient color contrast in both themes (WCAG AA)

## Success Metrics
- Toggle works without page reload
- Theme persists across sessions
- All components render correctly in both themes
```

## Converting to prd.json

After generating PRD.md, use the `/claude-loop` skill to convert it to
the prd.json format required by claude-loop:

```
/claude-loop PRD.md
```

## Tips for Good PRDs

1. **Be specific**: Vague requirements lead to vague implementations
2. **Define acceptance criteria**: Each criterion should be verifiable
3. **Order by dependency**: Later stories can depend on earlier ones
4. **Keep stories small**: When in doubt, split the story
5. **Include non-goals**: Prevents scope creep
6. **Note technical constraints**: Helps avoid dead ends

## Integration with claude-loop

```bash
# 1. Generate PRD
claude "/prd Add user authentication"

# 2. Review and edit PRD.md as needed

# 3. Convert to prd.json
claude "/claude-loop PRD.md"

# 4. Run claude-loop
./claude-loop.sh
```
