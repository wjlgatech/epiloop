# RG-TDD: Gaps Analysis and Solutions

## Executive Summary

This document analyzes the capability gaps in claude-loop for Reality-Grounded Test-Driven Development (RG-TDD) and the solutions implemented to address them.

## Definition: Reality-Grounded TDD

Traditional TDD tests code in isolation with unit tests. RG-TDD extends this by testing what users actually see and experience:

```
Traditional TDD:        RG-TDD:
  Code → Test             Code → Build → Run → Browser → Test
  (logic testing)         (reality testing)
```

RG-TDD answers: "Does the app actually work when a user clicks this button?"

---

## Capability Gaps Identified

### Gap 1: No Browser Automation

**Problem**: claude-loop can write code and run CLI commands, but cannot:
- Launch a browser
- Navigate to pages
- Click buttons/fill forms
- Verify visual output

**Impact**: Cannot test that UI actually renders correctly, user flows work, or visual design matches expectations.

**Solution**: Created `/rg-tdd` skill with Playwright integration

```python
# New capability: Browser automation
with BrowserRunner(config) as runner:
    runner.page.goto("http://localhost:3000")
    runner.page.click("[data-testid='login-button']")
    runner.page.fill("#email", "test@example.com")
    runner.page.screenshot(path="login-filled.png")
```

---

### Gap 2: No Screenshot Capture & Comparison

**Problem**: No mechanism to:
- Capture what the app looks like
- Compare against baseline images
- Detect visual regressions

**Impact**: Visual bugs slip through even when unit tests pass.

**Solution**: Implemented `VisualDiff` class with pixel-level comparison

```python
# New capability: Visual regression detection
differ = VisualDiff(threshold=0.05)
result = differ.compare(
    baseline_path="screenshots/baseline/login.png",
    current_path="screenshots/current/login.png",
    diff_path="screenshots/diff/login.png"
)
# result.passed = True/False
# result.diff_percentage = 0.02
```

---

### Gap 3: No Test Plan Generation from Source

**Problem**: Manually creating test plans is tedious and error-prone. No automatic extraction of:
- Routes from Next.js app directory
- Interactive elements from components
- Expected behaviors from code

**Impact**: Test coverage is incomplete or inconsistent.

**Solution**: Implemented `PlanGenerator` that analyzes source code

```python
# New capability: Auto-generate test plan from code
generator = PlanGenerator("src/app/")
plan = generator.analyze()
# Extracts:
# - All routes (/, /login, /dashboard, etc.)
# - Page components
# - Creates test scenarios automatically
```

---

### Gap 4: No Headless Testing for Sandboxed Environments

**Problem**: In restricted environments (like this sandbox), cannot:
- Run full browser
- Access localhost from external
- Execute Playwright

**Impact**: RG-TDD is blocked in CI/CD or sandboxed environments.

**Solution**: Created `CLITester` for static analysis when browser unavailable

```python
# New capability: CLI-based testing without browser
tester = CLITester(app_dir)
report = tester.run_all_tests()
# Tests:
# - Project structure exists
# - Pages are properly defined
# - API routes present
# - TypeScript health
# - data-testid coverage
# - i18n setup
# - Accessibility basics
```

---

### Gap 5: No Viewport/Responsive Testing

**Problem**: Apps need to work across device sizes, but no way to test:
- Mobile viewport (375x667)
- Tablet viewport (768x1024)
- Desktop viewport (1280x720)

**Impact**: Mobile users experience broken layouts.

**Solution**: Test plan includes viewport configuration per test

```json
{
  "id": "VT-100",
  "name": "Mobile Viewport - Landing",
  "viewport": {"width": 375, "height": 667},
  "page": "/",
  "actions": [
    {"type": "screenshot", "name": "mobile-landing"}
  ]
}
```

---

### Gap 6: No Auth-Aware Testing

**Problem**: Many pages require authentication, but no mechanism to:
- Login before testing protected pages
- Maintain session across tests
- Test authenticated user flows

**Impact**: Cannot test dashboard, interview, chapters, etc.

**Solution**: Test plan includes `requiresAuth` flag and auth config

```json
{
  "auth": {
    "testUser": {
      "email": "test@example.com",
      "password": "TestPassword123!"
    }
  },
  "tests": [
    {
      "id": "VT-030",
      "page": "/dashboard",
      "requiresAuth": true
    }
  ]
}
```

---

### Gap 7: No Test Reporting

**Problem**: No way to:
- Generate human-readable reports
- Track pass/fail over time
- Integrate with CI/CD

**Impact**: Cannot measure quality or catch regressions.

**Solution**: Implemented `ReportGenerator` for HTML and JSON reports

```
rg-tdd-results/
├── plan.json           # Test plan
├── results.json        # Machine-readable results
├── report.html         # Human-readable report
└── screenshots/
    ├── baseline/       # Expected images
    ├── current/        # Actual images
    └── diff/           # Visual differences
```

---

## New Skill: /rg-tdd

### Files Created

```
skills/rg-tdd/
├── SKILL.md                    # Documentation (200+ lines)
├── scripts/
│   ├── main.py                 # Main entry point (500+ lines)
│   │   ├── PlanGenerator       # Extracts routes from Next.js
│   │   ├── BrowserRunner       # Playwright automation
│   │   ├── VisualDiff          # Screenshot comparison
│   │   └── ReportGenerator     # HTML/JSON reports
│   └── cli_tester.py           # CLI-only testing (400+ lines)
│       ├── test_project_structure
│       ├── test_pages_exist
│       ├── test_components_structure
│       ├── test_api_routes
│       ├── test_typescript_errors
│       ├── test_imports
│       ├── test_data_testids
│       ├── test_accessibility_basics
│       └── test_i18n_setup
```

### Usage

```bash
# Generate test plan from app
./claude-loop.sh --skill rg-tdd --skill-arg plan src/app/

# Run visual tests (requires browser)
./claude-loop.sh --skill rg-tdd --skill-arg test http://localhost:3000

# Compare against baseline
./claude-loop.sh --skill rg-tdd --skill-arg compare --baseline screenshots/baseline

# Full RG-TDD cycle
./claude-loop.sh --skill rg-tdd --skill-arg full src/app/ http://localhost:3000

# CLI testing (no browser needed)
python skills/rg-tdd/scripts/cli_tester.py src/app/ --verbose
```

---

## Test Plan for New Legacy Biography

Created comprehensive test plan at `autobiography/rg-tdd-test-plan.json`:

| Category    | Tests | Description |
|-------------|-------|-------------|
| Landing     | 3     | Hero, features, full page |
| Auth        | 4     | Login, register, error states |
| Dashboard   | 2     | Overview, navigation |
| Interview   | 3     | Start, chat, topics |
| Chapters    | 2     | List, author styles |
| Analysis    | 2     | Dashboard, strengths |
| Family      | 2     | Tree view, add member |
| Export      | 2     | Formats, preview |
| Settings    | 2     | Profile, voice |
| Responsive  | 3     | Mobile, tablet |
| **Total**   | **25**| Full coverage |

### Test Suites

- `smoke`: Quick sanity check (3 tests)
- `auth`: Authentication flows (4 tests)
- `main`: Core features (7 tests)
- `responsive`: Multi-device (3 tests)
- `full`: All tests (25 tests)

---

## CLI Test Results (New Legacy Biography)

Quick structure verification:

| Check | Status | Details |
|-------|--------|---------|
| src/app exists | ✅ | Next.js app router |
| src/components | ✅ | 18 component directories |
| TSX files | ✅ | 116 files |
| API routes | ✅ | 43 routes |
| Pages | ✅ | All expected pages exist |

Pages verified:
- `/` (landing)
- `/login`, `/register` (auth)
- `/dashboard` (main)
- `/interview`, `/interview/[id]`
- `/chapters`, `/chapters/[id]`
- `/analysis`, `/analysis/[id]`
- `/family`, `/family/[id]`
- `/export/[id]`
- `/settings`

---

## Future Enhancements

### Phase 1: Core RG-TDD (Implemented)
- [x] Playwright integration
- [x] Screenshot capture
- [x] Visual diff
- [x] Test plan generation
- [x] CLI fallback testing
- [x] Report generation

### Phase 2: Enhanced Testing
- [ ] Video recording of test runs
- [ ] Accessibility testing (axe-core)
- [ ] Performance metrics (LCP, FID, CLS)
- [ ] Network request validation
- [ ] Console error capture

### Phase 3: CI/CD Integration
- [ ] GitHub Actions workflow
- [ ] Baseline management
- [ ] PR comment with visual diff
- [ ] Slack notifications
- [ ] Historical tracking

### Phase 4: AI-Assisted Testing
- [ ] LLM-powered test generation
- [ ] Natural language test definitions
- [ ] Intelligent failure analysis
- [ ] Self-healing selectors

---

## Conclusion

The `/rg-tdd` skill addresses all major gaps for Reality-Grounded TDD in claude-loop:

1. **Browser automation** via Playwright
2. **Visual regression** via pixel comparison
3. **Auto-generated test plans** from source code
4. **CLI fallback** for restricted environments
5. **Multi-viewport** responsive testing
6. **Auth-aware** testing
7. **Comprehensive reporting**

This enables true end-to-end testing where we verify not just that code compiles, but that the actual user experience works as intended.

---

*Generated by claude-loop RG-TDD skill*
