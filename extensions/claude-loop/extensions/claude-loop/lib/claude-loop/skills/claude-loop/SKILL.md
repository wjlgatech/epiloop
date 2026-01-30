# /claude-loop - PRD to JSON Converter

Convert a markdown PRD to the prd.json format required by claude-loop.

## Usage

```
/claude-loop <PRD.md file>
/claude-loop PRD.md
/claude-loop docs/feature-prd.md
```

## What This Skill Does

Parses a markdown PRD file and converts it to a structured `prd.json` file
that claude-loop can process for autonomous feature implementation.

## Input Format

The skill expects a PRD.md file with user stories in this format:

```markdown
# PRD: [Feature Name]

## Overview
[Description]

## User Stories

### US-001: [Story Title]
**As a** [user type]
**I want** [capability]
**So that** [benefit]

**Acceptance Criteria:**
- [ ] [Criterion 1]
- [ ] [Criterion 2]

**Priority:** 1

---

### US-002: [Story Title]
...
```

## Output Format

Generates a `prd.json` file:

```json
{
  "project": "feature-name",
  "branchName": "feature/feature-name",
  "description": "Overview from PRD",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story Title",
      "description": "As a [user] I want [capability] so that [benefit]",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Conversion Rules

### Project Name
- Extracted from PRD title: `# PRD: Dark Mode Toggle` → `"dark-mode-toggle"`
- Converted to kebab-case
- Used for branch naming: `feature/dark-mode-toggle`

### Story ID
- Preserved from PRD: `### US-001:` → `"id": "US-001"`
- If not present, auto-generated: `US-001`, `US-002`, etc.

### Story Title
- Extracted from heading: `### US-001: Create theme context` → `"title": "Create theme context"`

### Description
- Combines As a/I want/So that into single string
- Falls back to any paragraph after the heading if format not found

### Acceptance Criteria
- Extracted from checkbox list items
- `- [ ] Criterion` or `- [x] Criterion` → `["Criterion"]`
- Checkmarks stripped (all start as `passes: false`)

### Priority
- Extracted from `**Priority:** N`
- Defaults to story order if not specified

### Passes & Notes
- Always initialized as `passes: false`
- Notes field starts empty, populated during iterations

## Example Conversion

**Input (PRD.md):**
```markdown
# PRD: User Settings Page

## Overview
Create a settings page where users can manage their preferences.

## User Stories

### US-001: Create settings route
**As a** user
**I want** to access a settings page
**So that** I can manage my preferences

**Acceptance Criteria:**
- [ ] /settings route exists
- [ ] Route is protected (requires auth)
- [ ] Page renders without errors

**Priority:** 1

---

### US-002: Add profile section
**As a** user
**I want** to see my profile information
**So that** I can verify my account details

**Acceptance Criteria:**
- [ ] Profile section displays name and email
- [ ] Avatar is shown if available
- [ ] Edit button links to profile edit

**Priority:** 2
```

**Output (prd.json):**
```json
{
  "project": "user-settings-page",
  "branchName": "feature/user-settings-page",
  "description": "Create a settings page where users can manage their preferences.",
  "userStories": [
    {
      "id": "US-001",
      "title": "Create settings route",
      "description": "As a user I want to access a settings page so that I can manage my preferences",
      "acceptanceCriteria": [
        "/settings route exists",
        "Route is protected (requires auth)",
        "Page renders without errors"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    },
    {
      "id": "US-002",
      "title": "Add profile section",
      "description": "As a user I want to see my profile information so that I can verify my account details",
      "acceptanceCriteria": [
        "Profile section displays name and email",
        "Avatar is shown if available",
        "Edit button links to profile edit"
      ],
      "priority": 2,
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Validation Checks

The skill validates the generated prd.json:

1. **Required fields**: All stories must have id, title, description, acceptanceCriteria
2. **Unique IDs**: No duplicate story IDs
3. **Priority order**: Warns if priorities suggest wrong dependency order
4. **Story count**: Warns if > 10 stories (may indicate too-large scope)
5. **Acceptance criteria**: Each story must have at least one criterion

## Branch Naming

The branch name is auto-generated:
- `# PRD: Add Dark Mode` → `feature/add-dark-mode`
- `# PRD: Fix Authentication Bug` → `feature/fix-authentication-bug`
- Spaces → hyphens, lowercase, special chars removed

## Workflow

```bash
# 1. Create or obtain PRD.md
claude "/prd Add user authentication"  # Or write manually

# 2. Convert to prd.json
claude "/claude-loop PRD.md"

# 3. Review prd.json
cat prd.json | jq .

# 4. Optionally adjust priorities or split stories
# Edit prd.json manually if needed

# 5. Run claude-loop
./claude-loop.sh
```

## Handling Edge Cases

### Missing Priorities
If no priority is specified, stories are numbered by order of appearance:
```markdown
### US-001: First story    → priority: 1
### US-002: Second story   → priority: 2
```

### Non-Standard Formats
The skill attempts to parse various formats:
```markdown
# These all work:
**Priority:** 1
Priority: 1
*Priority*: 1
```

### Large PRDs
If the PRD has many stories:
1. Consider splitting into multiple PRDs
2. Or run claude-loop with higher `--max-iterations`

## Tips

1. **Review before running**: Always review prd.json before running claude-loop
2. **Adjust priorities**: Ensure dependencies are reflected in priority order
3. **Split large stories**: If a story seems too big, split it in prd.json
4. **Add notes**: Use the notes field to add context for tricky stories
