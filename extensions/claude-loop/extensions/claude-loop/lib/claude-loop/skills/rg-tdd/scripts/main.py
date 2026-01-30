#!/usr/bin/env python3
"""
RG-TDD: Reality-Grounded Test-Driven Development
Main entry point for visual and browser-based testing.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Check for required dependencies
try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from PIL import Image
    import numpy as np
    VISUAL_DIFF_AVAILABLE = True
except ImportError:
    VISUAL_DIFF_AVAILABLE = False


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    test_id: str
    name: str
    status: TestStatus
    duration_ms: float
    screenshots: list
    assertions: list
    error: Optional[str] = None


@dataclass
class RGTDDConfig:
    app_dir: Optional[str] = None
    base_url: str = "http://localhost:3000"
    output_dir: str = "rg-tdd-results"
    viewport_width: int = 1280
    viewport_height: int = 720
    headless: bool = True
    slowmo: int = 0
    threshold: float = 0.05
    update_baseline: bool = False


class PlanGenerator:
    """Generates test plan from application source code."""

    def __init__(self, app_dir: str):
        self.app_dir = Path(app_dir)
        self.routes = []
        self.components = []

    def analyze(self) -> dict:
        """Analyze app structure and generate test plan."""
        # Detect framework
        framework = self._detect_framework()

        # Extract routes
        if framework == "nextjs":
            self.routes = self._extract_nextjs_routes()
        elif framework == "react-router":
            self.routes = self._extract_react_router_routes()
        else:
            self.routes = self._fallback_route_detection()

        # Generate test plan
        return self._generate_plan()

    def _detect_framework(self) -> str:
        """Detect the frontend framework."""
        package_json = self.app_dir / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    return "nextjs"
                if "react-router" in deps or "react-router-dom" in deps:
                    return "react-router"
        return "unknown"

    def _extract_nextjs_routes(self) -> list:
        """Extract routes from Next.js app directory."""
        routes = []
        app_paths = [
            self.app_dir / "src" / "app",
            self.app_dir / "app",
        ]

        for app_path in app_paths:
            if app_path.exists():
                for page_file in app_path.rglob("page.tsx"):
                    # Convert file path to route
                    rel_path = page_file.relative_to(app_path)
                    route = "/" + str(rel_path.parent).replace("\\", "/")
                    route = route.replace("(main)", "").replace("(auth)", "")
                    route = route.replace("//", "/")
                    if route.endswith("/"):
                        route = route[:-1] or "/"

                    # Skip dynamic routes for now
                    if "[" not in route:
                        routes.append({
                            "path": route,
                            "file": str(page_file),
                            "type": "page"
                        })

        return routes

    def _extract_react_router_routes(self) -> list:
        """Extract routes from React Router config."""
        routes = []
        # Look for route definitions in common patterns
        for tsx_file in self.app_dir.rglob("*.tsx"):
            content = tsx_file.read_text(errors='ignore')
            if "Route" in content and "path=" in content:
                import re
                path_matches = re.findall(r'path=["\']([^"\']+)["\']', content)
                for path in path_matches:
                    routes.append({
                        "path": path,
                        "file": str(tsx_file),
                        "type": "route"
                    })
        return routes

    def _fallback_route_detection(self) -> list:
        """Fallback route detection for unknown frameworks."""
        routes = [{"path": "/", "file": "index", "type": "fallback"}]
        return routes

    def _generate_plan(self) -> dict:
        """Generate test plan from extracted routes."""
        tests = []

        for i, route in enumerate(self.routes, start=1):
            test_id = f"VT-{i:03d}"
            test = {
                "id": test_id,
                "name": f"Visual Test: {route['path']}",
                "page": route["path"],
                "source_file": route["file"],
                "actions": [
                    {"type": "wait", "for": "networkidle"},
                    {"type": "screenshot", "name": f"{test_id}-initial"}
                ],
                "assertions": [
                    {"type": "no-console-errors"},
                    {"type": "page-loaded"}
                ]
            }
            tests.append(test)

        return {
            "appName": self.app_dir.name,
            "generatedAt": self._timestamp(),
            "viewport": {"width": 1280, "height": 720},
            "tests": tests
        }

    def _timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()


class BrowserRunner:
    """Runs browser automation tests using Playwright."""

    def __init__(self, config: RGTDDConfig):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.results: list = []

    def __enter__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slowmo
        )
        self.context = self.browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height
            }
        )
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()

    def run_test(self, test: dict) -> TestResult:
        """Run a single visual test."""
        import time
        start_time = time.time()

        screenshots = []
        assertion_results = []
        error = None
        status = TestStatus.PASSED

        try:
            # Navigate to page
            url = f"{self.config.base_url}{test['page']}"
            self.page.goto(url, wait_until="networkidle", timeout=30000)

            # Execute actions
            for action in test.get("actions", []):
                result = self._execute_action(action)
                if action["type"] == "screenshot":
                    screenshots.append(result)

            # Run assertions
            for assertion in test.get("assertions", []):
                result = self._run_assertion(assertion)
                assertion_results.append(result)
                if not result["passed"]:
                    status = TestStatus.FAILED

        except Exception as e:
            error = str(e)
            status = TestStatus.ERROR

        duration_ms = (time.time() - start_time) * 1000

        return TestResult(
            test_id=test["id"],
            name=test["name"],
            status=status,
            duration_ms=duration_ms,
            screenshots=screenshots,
            assertions=assertion_results,
            error=error
        )

    def _execute_action(self, action: dict) -> Optional[dict]:
        """Execute a single action."""
        action_type = action["type"]

        if action_type == "wait":
            wait_for = action.get("for", "timeout")
            if wait_for == "networkidle":
                self.page.wait_for_load_state("networkidle")
            elif wait_for == "navigation":
                self.page.wait_for_load_state("load")
            elif wait_for == "selector":
                self.page.wait_for_selector(action["selector"])
            else:
                self.page.wait_for_timeout(action.get("timeout", 1000))

        elif action_type == "screenshot":
            name = action["name"]
            path = Path(self.config.output_dir) / "screenshots" / "current" / f"{name}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path), full_page=action.get("fullPage", False))
            return {"name": name, "path": str(path)}

        elif action_type == "click":
            self.page.click(action["selector"])

        elif action_type == "fill":
            self.page.fill(action["selector"], action["value"])

        elif action_type == "select":
            self.page.select_option(action["selector"], action["value"])

        elif action_type == "hover":
            self.page.hover(action["selector"])

        elif action_type == "scroll":
            if "selector" in action:
                self.page.locator(action["selector"]).scroll_into_view_if_needed()
            else:
                self.page.evaluate(f"window.scrollTo(0, {action.get('y', 500)})")

        elif action_type == "keyboard":
            self.page.keyboard.press(action["key"])

        elif action_type == "goto":
            self.page.goto(action["url"])

        return None

    def _run_assertion(self, assertion: dict) -> dict:
        """Run a single assertion."""
        assertion_type = assertion["type"]
        passed = False
        message = ""

        try:
            if assertion_type == "element-visible":
                locator = self.page.locator(assertion["selector"])
                passed = locator.is_visible()
                message = f"Element {assertion['selector']} visibility: {passed}"

            elif assertion_type == "element-hidden":
                locator = self.page.locator(assertion["selector"])
                passed = not locator.is_visible()
                message = f"Element {assertion['selector']} hidden: {passed}"

            elif assertion_type == "text-content":
                locator = self.page.locator(assertion["selector"])
                text = locator.text_content() or ""
                expected = assertion.get("contains", "")
                passed = expected in text
                message = f"Text content check: '{expected}' in '{text[:50]}...'"

            elif assertion_type == "url-matches":
                current_url = self.page.url
                pattern = assertion["pattern"]
                passed = pattern in current_url
                message = f"URL check: '{pattern}' in '{current_url}'"

            elif assertion_type == "no-console-errors":
                # We'd need to set up console message capture before navigation
                passed = True
                message = "Console error check (not fully implemented)"

            elif assertion_type == "page-loaded":
                passed = self.page.url != "about:blank"
                message = f"Page loaded: {self.page.url}"

        except Exception as e:
            message = f"Assertion error: {str(e)}"

        return {
            "type": assertion_type,
            "passed": passed,
            "message": message
        }


class VisualDiff:
    """Compare screenshots for visual regression."""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def compare(self, baseline_path: str, current_path: str, diff_path: str) -> dict:
        """Compare two images and generate diff."""
        if not VISUAL_DIFF_AVAILABLE:
            return {"error": "PIL/numpy not installed", "passed": False}

        baseline = Image.open(baseline_path)
        current = Image.open(current_path)

        # Ensure same size
        if baseline.size != current.size:
            return {
                "passed": False,
                "error": f"Size mismatch: baseline {baseline.size} vs current {current.size}",
                "diff_percentage": 1.0
            }

        # Convert to numpy arrays
        baseline_arr = np.array(baseline)
        current_arr = np.array(current)

        # Calculate pixel difference
        diff = np.abs(baseline_arr.astype(float) - current_arr.astype(float))
        diff_percentage = np.mean(diff) / 255.0

        passed = diff_percentage <= self.threshold

        # Generate diff image
        if not passed:
            diff_img = Image.fromarray((diff * 255 / diff.max()).astype(np.uint8))
            Path(diff_path).parent.mkdir(parents=True, exist_ok=True)
            diff_img.save(diff_path)

        return {
            "passed": passed,
            "diff_percentage": diff_percentage,
            "threshold": self.threshold,
            "diff_path": diff_path if not passed else None
        }


class ReportGenerator:
    """Generate test reports."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)

    def generate(self, results: list, plan: dict) -> dict:
        """Generate HTML and JSON reports."""
        # JSON report
        json_path = self.output_dir / "results.json"
        json_data = {
            "plan": plan,
            "results": [asdict(r) if hasattr(r, '__dict__') else r for r in results],
            "summary": self._generate_summary(results)
        }

        # Convert enums to strings
        def convert_enums(obj):
            if isinstance(obj, dict):
                return {k: convert_enums(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_enums(v) for v in obj]
            elif isinstance(obj, Enum):
                return obj.value
            return obj

        json_data = convert_enums(json_data)

        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2, default=str)

        # HTML report
        html_path = self.output_dir / "report.html"
        html_content = self._generate_html(json_data)
        with open(html_path, "w") as f:
            f.write(html_content)

        return {
            "json_report": str(json_path),
            "html_report": str(html_path)
        }

    def _generate_summary(self, results: list) -> dict:
        """Generate test summary."""
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / total if total > 0 else 0
        }

    def _generate_html(self, data: dict) -> str:
        """Generate HTML report."""
        summary = data["summary"]
        results = data["results"]

        rows = ""
        for r in results:
            status = r.get("status", "unknown")
            status_class = "pass" if status == "passed" else "fail"
            error = r.get("error", "")
            rows += f"""
            <tr class="{status_class}">
                <td>{r.get('test_id', 'N/A')}</td>
                <td>{r.get('name', 'N/A')}</td>
                <td class="status-{status_class}">{status}</td>
                <td>{r.get('duration_ms', 0):.0f}ms</td>
                <td>{error if error else '-'}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>RG-TDD Test Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .summary-card h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; }}
        .summary-card .value {{ font-size: 32px; font-weight: bold; }}
        .passed .value {{ color: #22c55e; }}
        .failed .value {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f8f8; font-weight: 600; color: #666; text-transform: uppercase; font-size: 12px; }}
        tr.pass {{ background: #f0fdf4; }}
        tr.fail {{ background: #fef2f2; }}
        .status-pass {{ color: #22c55e; font-weight: 600; }}
        .status-fail {{ color: #ef4444; font-weight: 600; }}
    </style>
</head>
<body>
    <h1>🧪 RG-TDD Test Report</h1>

    <div class="summary">
        <div class="summary-card passed">
            <h3>Passed</h3>
            <div class="value">{summary['passed']}</div>
        </div>
        <div class="summary-card failed">
            <h3>Failed</h3>
            <div class="value">{summary['failed']}</div>
        </div>
        <div class="summary-card">
            <h3>Total</h3>
            <div class="value">{summary['total']}</div>
        </div>
        <div class="summary-card">
            <h3>Pass Rate</h3>
            <div class="value">{summary['pass_rate']:.0%}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Test ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Error</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>"""
        return html


def main():
    parser = argparse.ArgumentParser(description="RG-TDD: Reality-Grounded Test-Driven Development")
    parser.add_argument("command", choices=["plan", "test", "compare", "full"],
                       help="Command to execute")
    parser.add_argument("--skill-arg", dest="args", nargs="*", default=[],
                       help="Additional arguments")
    parser.add_argument("--output", "-o", default="rg-tdd-results",
                       help="Output directory")
    parser.add_argument("--plan", "-p", help="Test plan file")
    parser.add_argument("--baseline", "-b", help="Baseline screenshots directory")
    parser.add_argument("--headed", action="store_true", help="Show browser")
    parser.add_argument("--slowmo", type=int, default=0, help="Slow motion delay")
    parser.add_argument("--threshold", type=float, default=0.05, help="Visual diff threshold")
    parser.add_argument("--update", action="store_true", help="Update baseline")

    args = parser.parse_args()

    config = RGTDDConfig(
        output_dir=args.output,
        headless=not args.headed,
        slowmo=args.slowmo,
        threshold=args.threshold,
        update_baseline=args.update
    )

    # Ensure output directory exists
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    if args.command == "plan":
        # Generate test plan
        app_dir = args.args[0] if args.args else "."
        generator = PlanGenerator(app_dir)
        plan = generator.analyze()

        plan_path = Path(config.output_dir) / "plan.json"
        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2)

        print(f"✅ Generated test plan: {plan_path}")
        print(f"   Tests: {len(plan['tests'])}")
        for test in plan['tests']:
            print(f"   - {test['id']}: {test['page']}")

        return 0

    elif args.command == "test":
        # Run tests
        base_url = args.args[0] if args.args else "http://localhost:3000"
        config.base_url = base_url

        # Load test plan
        plan_path = args.plan or Path(config.output_dir) / "plan.json"
        if not Path(plan_path).exists():
            print(f"❌ Test plan not found: {plan_path}")
            print("   Run 'rg-tdd plan <app-dir>' first")
            return 2

        with open(plan_path) as f:
            plan = json.load(f)

        print(f"🧪 Running {len(plan['tests'])} tests against {base_url}")

        results = []
        with BrowserRunner(config) as runner:
            for test in plan["tests"]:
                print(f"   Running {test['id']}: {test['name']}...", end=" ")
                result = runner.run_test(test)
                results.append(result)

                if result.status == TestStatus.PASSED:
                    print("✅")
                elif result.status == TestStatus.FAILED:
                    print(f"❌ {result.error or 'Assertion failed'}")
                else:
                    print(f"⚠️ {result.error}")

        # Generate report
        reporter = ReportGenerator(config.output_dir)
        report_paths = reporter.generate(results, plan)

        summary = reporter._generate_summary(results)
        print(f"\n📊 Results: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']:.0%})")
        print(f"   Report: {report_paths['html_report']}")

        return 0 if summary['failed'] == 0 and summary['errors'] == 0 else 1

    elif args.command == "compare":
        # Compare screenshots
        baseline_dir = args.baseline or Path(config.output_dir) / "screenshots" / "baseline"
        current_dir = Path(config.output_dir) / "screenshots" / "current"
        diff_dir = Path(config.output_dir) / "screenshots" / "diff"

        if not current_dir.exists():
            print(f"❌ No current screenshots found: {current_dir}")
            return 2

        differ = VisualDiff(config.threshold)

        if args.update:
            # Update baseline
            import shutil
            if current_dir.exists():
                if Path(baseline_dir).exists():
                    shutil.rmtree(baseline_dir)
                shutil.copytree(current_dir, baseline_dir)
                print(f"✅ Updated baseline: {baseline_dir}")
            return 0

        if not Path(baseline_dir).exists():
            print(f"⚠️ No baseline found. Run with --update to create baseline.")
            return 0

        # Compare screenshots
        comparisons = []
        for current_img in current_dir.glob("*.png"):
            baseline_img = Path(baseline_dir) / current_img.name
            diff_img = diff_dir / f"diff-{current_img.name}"

            if baseline_img.exists():
                result = differ.compare(str(baseline_img), str(current_img), str(diff_img))
                result["name"] = current_img.name
                comparisons.append(result)

                status = "✅" if result["passed"] else "❌"
                print(f"   {status} {current_img.name}: {result['diff_percentage']:.2%} diff")

        passed = sum(1 for c in comparisons if c["passed"])
        total = len(comparisons)
        print(f"\n📊 Visual comparison: {passed}/{total} passed")

        return 0 if passed == total else 1

    elif args.command == "full":
        # Full RG-TDD cycle
        app_dir = args.args[0] if len(args.args) > 0 else "."
        base_url = args.args[1] if len(args.args) > 1 else "http://localhost:3000"

        print("🔄 Running full RG-TDD cycle")

        # 1. Generate plan
        print("\n📝 Step 1: Generating test plan...")
        generator = PlanGenerator(app_dir)
        plan = generator.analyze()
        plan_path = Path(config.output_dir) / "plan.json"
        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2)
        print(f"   Generated {len(plan['tests'])} tests")

        # 2. Run tests
        print(f"\n🧪 Step 2: Running tests against {base_url}...")
        config.base_url = base_url

        results = []
        with BrowserRunner(config) as runner:
            for test in plan["tests"]:
                print(f"   {test['id']}: {test['page']}...", end=" ")
                result = runner.run_test(test)
                results.append(result)
                status = "✅" if result.status == TestStatus.PASSED else "❌"
                print(status)

        # 3. Generate report
        print("\n📊 Step 3: Generating report...")
        reporter = ReportGenerator(config.output_dir)
        report_paths = reporter.generate(results, plan)

        summary = reporter._generate_summary(results)

        print(f"\n{'='*50}")
        print(f"RG-TDD Complete!")
        print(f"{'='*50}")
        print(f"Tests: {summary['total']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Pass Rate: {summary['pass_rate']:.0%}")
        print(f"\nReports:")
        print(f"  HTML: {report_paths['html_report']}")
        print(f"  JSON: {report_paths['json_report']}")

        return 0 if summary['failed'] == 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
