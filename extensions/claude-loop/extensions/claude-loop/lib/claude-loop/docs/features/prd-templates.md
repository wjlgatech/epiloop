# PRD Templates (US-002)

Comprehensive PRD template library for common project types with variable substitution, metadata, and CLI tooling.

## Available Templates

### 1. Web Feature Template (`web-feature`)
**Use for**: Full-stack features with frontend + backend + tests
**Complexity**: Medium | **Duration**: 4-8 hours
**Required Skills**: frontend, backend, testing, API design

Creates 4 user stories:
- Backend API Endpoints
- Frontend UI Components
- State Management Integration
- End-to-End Testing

### 2. API Endpoint Template (`api-endpoint`)
**Use for**: REST or GraphQL endpoints with validation + docs
**Complexity**: Simple | **Duration**: 2-4 hours
**Required Skills**: backend, API design, testing

Creates 3 user stories:
- API Endpoint Implementation
- API Documentation
- Integration Testing

### 3. Refactoring Template (`refactoring`)
**Use for**: Code restructuring with backwards compatibility
**Complexity**: Medium | **Duration**: 3-6 hours
**Required Skills**: code architecture, testing, migration planning

Creates 4 user stories:
- Analysis and Planning
- Implementation with Feature Flags
- Testing and Validation
- Migration and Cleanup

### 4. Bug Fix Template (`bug-fix`)
**Use for**: Issue reproduction + fix + regression tests
**Complexity**: Simple | **Duration**: 1-3 hours
**Required Skills**: debugging, testing

Creates 3 user stories:
- Reproduction and Analysis
- Fix Implementation
- Regression Testing

### 5. Documentation Template (`documentation`)
**Use for**: README/docs updates with examples
**Complexity**: Simple | **Duration**: 2-4 hours
**Required Skills**: technical writing

Creates 3 user stories:
- Documentation Updates
- Code Examples
- Review and Polish

### 6. Testing Template (`testing`)
**Use for**: Test coverage expansion (unit + integration)
**Complexity**: Medium | **Duration**: 3-5 hours
**Required Skills**: testing, test automation

Creates 3 user stories:
- Unit Test Implementation
- Integration Test Implementation
- Test Infrastructure

## CLI Usage

### List Templates
```bash
./lib/template-generator.sh list
```

### Show Template Details
```bash
./lib/template-generator.sh show web-feature
```

### Generate PRD (Interactive)
```bash
./lib/template-generator.sh generate web-feature
# Prompts for: PROJECT_NAME, FEATURE_NAME, etc.
```

### Generate PRD (Non-Interactive)
```bash
./lib/template-generator.sh generate web-feature \
  --var PROJECT_NAME=ecommerce \
  --var FEATURE_NAME=user-auth \
  --output prd-user-auth.json
```

### Generate from Variables File
```bash
# vars.json: {"PROJECT_NAME": "myapp", "FEATURE_NAME": "payments"}
./lib/template-generator.sh generate web-feature --vars-file vars.json
```

### Validate Generated PRD
```bash
./lib/template-generator.sh validate prd-user-auth.json
```

## Template Structure

Each template includes:

### Metadata Section
```json
{
  "metadata": {
    "templateName": "web-feature",
    "templateVersion": "1.0.0",
    "description": "...",
    "estimatedComplexity": "medium",
    "typicalDuration": "4-8 hours",
    "requiredSkills": ["frontend", "backend", "testing"],
    "variables": [...]
  }
}
```

### Variables
Variables use `{{VARIABLE_NAME}}` syntax:
- `{{PROJECT_NAME}}` - Project name
- `{{FEATURE_NAME}}` - Feature name
- `{{BRANCH_NAME}}` - Git branch (defaults to feature/{{FEATURE_NAME}})
- `{{COMPONENT_NAME}}` - Component/module name (optional)
- Custom variables per template

### PRD Section
Complete PRD structure with:
- User stories with IDs (WF-001, API-001, etc.)
- Acceptance criteria
- Dependencies
- File scopes
- Complexity estimates
- Suggested models (sonnet/opus/haiku)

## Integration with claude-loop

### Quick Start from Template
```bash
# 1. Generate PRD
./lib/template-generator.sh generate web-feature

# 2. Run claude-loop
./claude-loop.sh --prd prd-web-feature.json
```

### With Workspace Sandboxing (US-003)
```bash
./lib/template-generator.sh generate api-endpoint \
  --var PROJECT_NAME=backend \
  --var FEATURE_NAME=user-api

./claude-loop.sh --prd prd-user-api.json --workspace src/api/
```

## Template Variables

### Common Variables
- `PROJECT_NAME`: Project/application name
- `FEATURE_NAME`: Feature being implemented
- `BRANCH_NAME`: Git branch (optional, defaults to feature/FEATURE_NAME)

### Web Feature Variables
- `COMPONENT_NAME`: Main component name
- `API_ROUTE`: API route prefix
- `MODEL_NAME`: Database model name

### API Endpoint Variables
- `ENDPOINT_PATH`: API endpoint path
- `HTTP_METHOD`: HTTP method (GET/POST/PUT/DELETE)
- `RESOURCE_NAME`: Resource name

### Refactoring Variables
- `MODULE_NAME`: Module to refactor
- `OLD_PATTERN`: Pattern being replaced
- `NEW_PATTERN`: New pattern

## Benefits

1. **Faster PRD Authoring**: 60% time reduction vs manual writing
2. **Consistency**: All PRDs follow same structure and quality standards
3. **Best Practices**: Templates embody lessons from successful projects
4. **Lower Barrier**: New users can generate valid PRDs immediately
5. **Customizable**: Templates are JSON, easily modified for your needs

## Implementation Details

- **Module**: `lib/template-generator.sh` (476 lines)
- **Templates**: `templates/cowork-inspired/*.json` (6 templates, ~1000 lines total)
- **Format**: JSON with metadata + PRD sections
- **Substitution**: Bash parameter expansion with validation
- **Integration**: Works standalone or integrated with claude-loop CLI

## See Also

- [Enhanced Progress Indicators](./progress-indicators.md) - US-001
- [Workspace Sandboxing](./workspace-sandboxing.md) - US-003 (coming soon)
- [Checkpoint Confirmations](./checkpoint-confirmations.md) - US-004 (coming soon)
