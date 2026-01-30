# /rg-tdd - Reality-Grounded Test-Driven Development

Reality-Grounded TDD (RG-TDD) enables testing applications by actually running them in browsers and verifying visual/functional behavior through screenshots and interaction.

## Overview

Traditional TDD tests code in isolation. RG-TDD tests the reality of what users see and experience:
- **Visual Testing**: Capture screenshots and compare against expectations
- **Interaction Testing**: Click buttons, fill forms, verify state changes
- **Flow Testing**: Complete end-to-end user journeys
- **Regression Testing**: Detect visual/functional regressions

## Usage

```bash
# Generate visual test plan for an app
./claude-loop.sh --skill rg-tdd --skill-arg plan src/app/

# Run visual tests with screenshot capture
./claude-loop.sh --skill rg-tdd --skill-arg test http://localhost:3000

# Compare screenshots against baseline
./claude-loop.sh --skill rg-tdd --skill-arg compare --baseline ./screenshots/baseline

# Full RG-TDD cycle
./claude-loop.sh --skill rg-tdd --skill-arg full src/app/ http://localhost:3000
```

## What This Skill Does

### 1. Test Plan Generation
Analyzes your application source code and generates a visual test plan:
- Extracts routes/pages from Next.js, React Router, etc.
- Identifies interactive elements (buttons, forms, links)
- Creates test scenarios for each component/page
- Generates expected behavior assertions

### 2. Browser Automation
Uses Playwright to interact with the running application:
- Navigate to pages
- Click buttons and links
- Fill forms with test data
- Scroll and interact with dynamic content
- Wait for async operations

### 3. Screenshot Capture
Captures visual state at key points:
- Full page screenshots
- Component-level screenshots
- Before/after interaction captures
- Viewport-responsive captures (mobile, tablet, desktop)

### 4. Visual Comparison
Compares captured screenshots:
- Pixel-diff detection with configurable threshold
- Structural similarity (SSIM) comparison
- Highlights visual differences
- Reports regression severity

### 5. Report Generation
Produces comprehensive test reports:
- HTML report with side-by-side comparisons
- JSON results for CI integration
- Coverage metrics (pages tested, interactions verified)
- Failure screenshots with annotations

## Test Plan Schema

```json
{
  "appName": "new-legacy-biography",
  "baseUrl": "http://localhost:3000",
  "viewport": {"width": 1280, "height": 720},
  "tests": [
    {
      "id": "VT-001",
      "name": "Landing Page Visual",
      "page": "/",
      "actions": [
        {"type": "screenshot", "name": "landing-hero"}
      ],
      "assertions": [
        {"type": "element-visible", "selector": "[data-testid='hero-title']"},
        {"type": "text-content", "selector": "h1", "contains": "传承新遗产"}
      ]
    },
    {
      "id": "VT-002",
      "name": "Login Flow",
      "page": "/login",
      "actions": [
        {"type": "screenshot", "name": "login-empty"},
        {"type": "fill", "selector": "#email", "value": "test@example.com"},
        {"type": "fill", "selector": "#password", "value": "testpass123"},
        {"type": "screenshot", "name": "login-filled"},
        {"type": "click", "selector": "button[type='submit']"},
        {"type": "wait", "for": "navigation"},
        {"type": "screenshot", "name": "login-success"}
      ],
      "assertions": [
        {"type": "url-matches", "pattern": "/dashboard"},
        {"type": "element-visible", "selector": "[data-testid='dashboard']"}
      ]
    }
  ]
}
```

## Supported Actions

### Navigation
- `goto`: Navigate to URL
- `wait`: Wait for condition (navigation, selector, timeout)
- `refresh`: Reload page

### Interaction
- `click`: Click element by selector
- `fill`: Fill input field
- `select`: Select dropdown option
- `check`: Check checkbox
- `hover`: Hover over element
- `scroll`: Scroll to element or position
- `keyboard`: Type keys (Enter, Tab, etc.)

### Capture
- `screenshot`: Capture full page or element
- `snapshot`: Capture DOM state

### Assertion
- `element-visible`: Element is visible
- `element-hidden`: Element is not visible
- `text-content`: Element contains text
- `attribute`: Element has attribute value
- `url-matches`: URL matches pattern
- `screenshot-matches`: Visual comparison passes

## CLI Options

```bash
# Plan generation
--skill-arg plan <app-dir>          # Generate test plan from app code
--skill-arg plan --output plan.json # Custom output path

# Test execution
--skill-arg test <base-url>         # Run tests against URL
--skill-arg test --plan plan.json   # Use custom test plan
--skill-arg test --headed           # Show browser window
--skill-arg test --slowmo 100       # Slow down for debugging

# Comparison
--skill-arg compare                 # Compare against baseline
--skill-arg compare --update        # Update baseline
--skill-arg compare --threshold 0.1 # Pixel diff threshold

# Full cycle
--skill-arg full <app-dir> <url>    # Plan + Test + Compare
```

## Output Structure

```
rg-tdd-results/
├── plan.json              # Generated test plan
├── screenshots/
│   ├── baseline/          # Baseline screenshots
│   │   ├── landing-hero.png
│   │   └── login-empty.png
│   ├── current/           # Current run screenshots
│   │   └── ...
│   └── diff/              # Visual diff images
│       └── ...
├── results.json           # Test results
└── report.html            # Human-readable report
```

## Integration with claude-loop

### Pre-commit Visual Testing
```bash
# Run visual tests before marking story complete
./claude-loop.sh --skill rg-tdd --skill-arg test http://localhost:3000

# If visual regressions detected, fail the quality gate
if [ $? -ne 0 ]; then
    echo "Visual regression detected - story cannot be completed"
    exit 1
fi
```

### Story-Level Visual Testing
Add to PRD for automatic visual testing:
```json
{
  "id": "US-010",
  "title": "Login page styling",
  "visualTests": ["VT-001", "VT-002"],
  "acceptanceCriteria": [
    "Login form matches design mockup",
    "Error states display correctly"
  ]
}
```

### CI/CD Integration
```yaml
# GitHub Actions
- name: Run RG-TDD
  run: |
    npm run dev &
    sleep 10
    ./claude-loop.sh --skill rg-tdd --skill-arg test http://localhost:3000
    ./claude-loop.sh --skill rg-tdd --skill-arg compare
```

## Example: Testing New Legacy Biography

### Auto-Generated Test Plan
```bash
./claude-loop.sh --skill rg-tdd --skill-arg plan src/app/
```

Generates tests for:
- Landing page (`/`)
- Login/Register (`/login`, `/register`)
- Dashboard (`/dashboard`)
- Interview (`/interview`)
- Chapters (`/chapters`, `/chapters/[id]`)
- Analysis (`/analysis`)
- Family Tree (`/family`)
- Export (`/export`)
- Settings (`/settings`)

### Running Tests
```bash
# Start dev server
npm run dev &

# Wait for server
sleep 10

# Run all visual tests
./claude-loop.sh --skill rg-tdd --skill-arg test http://localhost:3000

# Check for regressions
./claude-loop.sh --skill rg-tdd --skill-arg compare --threshold 0.05
```

## Script Implementation

The skill is implemented in Python using Playwright:

- `scripts/main.py` - Main entry point
- `scripts/plan_generator.py` - Analyzes app and generates test plan
- `scripts/browser_runner.py` - Playwright browser automation
- `scripts/screenshot_capture.py` - Screenshot capture and management
- `scripts/visual_diff.py` - Pixel and SSIM comparison
- `scripts/report_generator.py` - HTML/JSON report generation

## Requirements

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Additional dependencies
pip install pillow numpy scikit-image
```

## Exit Codes

- `0` - All tests passed
- `1` - Some tests failed (visual regression or assertion failure)
- `2` - Invalid arguments or configuration error
- `3` - Browser automation error

## Tips for RG-TDD Success

1. **Start with baselines**: Run tests once to establish baseline screenshots
2. **Use data-testid**: Add `data-testid` attributes for reliable selectors
3. **Handle async**: Use proper waits for dynamic content
4. **Viewport consistency**: Test at consistent viewport sizes
5. **CI environment**: Use consistent fonts/rendering in CI
6. **Threshold tuning**: Adjust pixel diff threshold for your needs

## Related Skills

- `/test-scaffolder` - Generate unit test boilerplate
- `/prd-validator` - Validate PRD before testing
- `/cost-optimizer` - Optimize test suite for performance

## Further Reading

- [Playwright Documentation](https://playwright.dev/python/docs/intro)
- [Visual Regression Testing Best Practices](docs/visual-testing.md)
- [RG-TDD Philosophy](docs/rg-tdd-philosophy.md)
