#!/usr/bin/env python3
"""
RG-TDD CLI Tester
Static analysis and structure verification when browser automation isn't available.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ComponentTest:
    """Represents a test for a component/page."""
    id: str
    name: str
    file_path: str
    passed: bool = False
    checks: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class CLITester:
    """
    Tests Next.js/React apps through static analysis.
    Use when browser automation isn't available.
    """

    def __init__(self, app_dir: str):
        self.app_dir = Path(app_dir)
        self.results: List[ComponentTest] = []

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all available CLI tests."""
        tests = [
            self.test_project_structure,
            self.test_pages_exist,
            self.test_components_structure,
            self.test_api_routes,
            self.test_typescript_errors,
            self.test_imports,
            self.test_data_testids,
            self.test_accessibility_basics,
            self.test_i18n_setup,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.results.append(ComponentTest(
                    id=f"CLI-ERR",
                    name=test.__name__,
                    file_path="",
                    passed=False,
                    errors=[str(e)]
                ))

        return self._generate_report()

    def test_project_structure(self):
        """Verify expected project structure exists."""
        test = ComponentTest(
            id="CLI-001",
            name="Project Structure",
            file_path=str(self.app_dir)
        )

        required_dirs = [
            "src/app",
            "src/components",
            "src/services",
            "src/lib",
            "src/types",
        ]

        optional_dirs = [
            "src/hooks",
            "tests",
            "public",
        ]

        for dir_path in required_dirs:
            full_path = self.app_dir / dir_path
            if full_path.exists():
                test.checks.append(f"✅ {dir_path} exists")
            else:
                test.errors.append(f"❌ Missing required directory: {dir_path}")

        for dir_path in optional_dirs:
            full_path = self.app_dir / dir_path
            if full_path.exists():
                test.checks.append(f"✅ {dir_path} exists (optional)")

        test.passed = len(test.errors) == 0
        self.results.append(test)

    def test_pages_exist(self):
        """Verify all expected pages exist."""
        test = ComponentTest(
            id="CLI-002",
            name="Pages Exist",
            file_path=str(self.app_dir / "src/app")
        )

        expected_pages = {
            "/": ["page.tsx", "page.ts", "page.jsx", "page.js"],
            "/login": ["(auth)/login/page.tsx", "login/page.tsx"],
            "/register": ["(auth)/register/page.tsx", "register/page.tsx"],
            "/dashboard": ["(main)/dashboard/page.tsx", "dashboard/page.tsx"],
            "/interview": ["(main)/interview/page.tsx", "interview/page.tsx"],
            "/chapters": ["(main)/chapters/page.tsx", "chapters/page.tsx"],
            "/analysis": ["(main)/analysis/page.tsx", "analysis/page.tsx"],
            "/family": ["(main)/family/page.tsx", "family/page.tsx"],
            "/export": ["(main)/export/page.tsx", "export/page.tsx"],
            "/settings": ["(main)/settings/page.tsx", "settings/page.tsx"],
        }

        app_dir = self.app_dir / "src/app"
        if not app_dir.exists():
            app_dir = self.app_dir / "app"

        for route, possible_files in expected_pages.items():
            found = False
            for file_pattern in possible_files:
                file_path = app_dir / file_pattern
                if file_path.exists():
                    test.checks.append(f"✅ {route} → {file_pattern}")
                    found = True
                    break

            if not found:
                # Check for the route in any nested structure
                route_name = route.strip("/") or "home"
                for page_file in app_dir.rglob("page.tsx"):
                    if route_name in str(page_file) or (route == "/" and "app" in str(page_file.parent)):
                        test.checks.append(f"✅ {route} found at {page_file.relative_to(app_dir)}")
                        found = True
                        break

                if not found:
                    test.errors.append(f"❌ Missing page: {route}")

        test.passed = len(test.errors) == 0
        self.results.append(test)

    def test_components_structure(self):
        """Verify component organization."""
        test = ComponentTest(
            id="CLI-003",
            name="Components Structure",
            file_path=str(self.app_dir / "src/components")
        )

        expected_component_dirs = [
            "ui",
            "interview",
            "chapters",
            "analysis",
            "family",
            "export",
            "dashboard",
            "layout",
        ]

        components_dir = self.app_dir / "src/components"
        if not components_dir.exists():
            test.errors.append("❌ src/components directory not found")
            test.passed = False
            self.results.append(test)
            return

        for comp_dir in expected_component_dirs:
            dir_path = components_dir / comp_dir
            if dir_path.exists():
                files = list(dir_path.glob("*.tsx")) + list(dir_path.glob("*.ts"))
                test.checks.append(f"✅ {comp_dir}/ ({len(files)} files)")
            else:
                test.errors.append(f"⚠️ Missing component directory: {comp_dir}")

        # Count total components
        total_tsx = len(list(components_dir.rglob("*.tsx")))
        test.checks.append(f"📊 Total TSX files: {total_tsx}")

        test.passed = len([e for e in test.errors if e.startswith("❌")]) == 0
        self.results.append(test)

    def test_api_routes(self):
        """Verify API routes exist."""
        test = ComponentTest(
            id="CLI-004",
            name="API Routes",
            file_path=str(self.app_dir / "src/app/api")
        )

        expected_apis = [
            "auth/login",
            "auth/register",
            "interview",
            "chapters",
            "analysis",
            "family",
            "export",
        ]

        api_dir = self.app_dir / "src/app/api"
        if not api_dir.exists():
            test.errors.append("❌ src/app/api directory not found")
            test.passed = False
            self.results.append(test)
            return

        for api_path in expected_apis:
            route_file = api_dir / api_path / "route.ts"
            if route_file.exists():
                test.checks.append(f"✅ /api/{api_path}")
            else:
                # Check for route.tsx or other patterns
                alt_patterns = [
                    api_dir / api_path / "route.tsx",
                    api_dir / f"{api_path}.ts",
                ]
                found = any(p.exists() for p in alt_patterns)
                if found:
                    test.checks.append(f"✅ /api/{api_path} (alternative pattern)")
                else:
                    test.errors.append(f"⚠️ Missing API route: /api/{api_path}")

        # Count total API routes
        total_routes = len(list(api_dir.rglob("route.ts"))) + len(list(api_dir.rglob("route.tsx")))
        test.checks.append(f"📊 Total API routes: {total_routes}")

        test.passed = len([e for e in test.errors if e.startswith("❌")]) == 0
        self.results.append(test)

    def test_typescript_errors(self):
        """Check for obvious TypeScript issues."""
        test = ComponentTest(
            id="CLI-005",
            name="TypeScript Health",
            file_path=str(self.app_dir)
        )

        # Check tsconfig exists
        tsconfig = self.app_dir / "tsconfig.json"
        if tsconfig.exists():
            test.checks.append("✅ tsconfig.json exists")

            with open(tsconfig) as f:
                config = json.load(f)

            strict = config.get("compilerOptions", {}).get("strict", False)
            test.checks.append(f"{'✅' if strict else '⚠️'} Strict mode: {strict}")
        else:
            test.errors.append("❌ tsconfig.json not found")

        # Check for common type errors in files (simple heuristic)
        type_issues = 0
        any_usage = 0

        for tsx_file in self.app_dir.rglob("*.tsx"):
            if "node_modules" in str(tsx_file):
                continue
            try:
                content = tsx_file.read_text(errors='ignore')
                # Count 'any' type usage
                any_usage += len(re.findall(r':\s*any\b', content))
                # Count @ts-ignore
                type_issues += len(re.findall(r'@ts-ignore', content))
            except Exception:
                pass

        test.checks.append(f"📊 'any' type usage: {any_usage}")
        test.checks.append(f"📊 @ts-ignore directives: {type_issues}")

        if type_issues > 10:
            test.errors.append(f"⚠️ High number of @ts-ignore ({type_issues})")

        test.passed = len([e for e in test.errors if e.startswith("❌")]) == 0
        self.results.append(test)

    def test_imports(self):
        """Verify import paths are valid."""
        test = ComponentTest(
            id="CLI-006",
            name="Import Validation",
            file_path=str(self.app_dir / "src")
        )

        broken_imports = []
        checked_files = 0

        for tsx_file in (self.app_dir / "src").rglob("*.tsx"):
            if "node_modules" in str(tsx_file):
                continue

            checked_files += 1
            try:
                content = tsx_file.read_text(errors='ignore')

                # Find imports with @/ alias
                imports = re.findall(r"from ['\"](@/[^'\"]+)['\"]", content)

                for imp in imports:
                    # Convert @/path to actual path
                    actual_path = imp.replace("@/", "src/")
                    full_path = self.app_dir / actual_path

                    # Check various extensions
                    exists = any([
                        (self.app_dir / f"{actual_path}.ts").exists(),
                        (self.app_dir / f"{actual_path}.tsx").exists(),
                        (self.app_dir / f"{actual_path}/index.ts").exists(),
                        (self.app_dir / f"{actual_path}/index.tsx").exists(),
                        full_path.exists(),
                    ])

                    if not exists:
                        broken_imports.append(f"{tsx_file.name}: {imp}")

            except Exception as e:
                pass

        test.checks.append(f"📊 Files checked: {checked_files}")

        if broken_imports:
            test.errors.append(f"⚠️ Potentially broken imports: {len(broken_imports)}")
            for bi in broken_imports[:5]:  # Show first 5
                test.errors.append(f"   - {bi}")
            if len(broken_imports) > 5:
                test.errors.append(f"   ... and {len(broken_imports) - 5} more")
        else:
            test.checks.append("✅ All @/ imports appear valid")

        test.passed = len([e for e in test.errors if e.startswith("❌")]) == 0
        self.results.append(test)

    def test_data_testids(self):
        """Check for data-testid attributes for testing."""
        test = ComponentTest(
            id="CLI-007",
            name="Test IDs Coverage",
            file_path=str(self.app_dir / "src/components")
        )

        testid_count = 0
        components_with_testids = 0
        total_components = 0

        for tsx_file in (self.app_dir / "src").rglob("*.tsx"):
            if "node_modules" in str(tsx_file):
                continue

            try:
                content = tsx_file.read_text(errors='ignore')

                # Count components (rough heuristic)
                if "export" in content and ("function" in content or "const" in content):
                    total_components += 1

                    # Count data-testid
                    testids = re.findall(r'data-testid=["\']([^"\']+)["\']', content)
                    if testids:
                        components_with_testids += 1
                        testid_count += len(testids)

            except Exception:
                pass

        coverage = (components_with_testids / total_components * 100) if total_components > 0 else 0

        test.checks.append(f"📊 Total data-testid attributes: {testid_count}")
        test.checks.append(f"📊 Components with testids: {components_with_testids}/{total_components}")
        test.checks.append(f"📊 TestID coverage: {coverage:.1f}%")

        if coverage < 30:
            test.errors.append("⚠️ Low data-testid coverage (<30%) - add testids for reliable testing")
        else:
            test.checks.append("✅ Good data-testid coverage")

        test.passed = coverage >= 30
        self.results.append(test)

    def test_accessibility_basics(self):
        """Check basic accessibility attributes."""
        test = ComponentTest(
            id="CLI-008",
            name="Accessibility Basics",
            file_path=str(self.app_dir / "src")
        )

        issues = []
        img_without_alt = 0
        buttons_without_aria = 0
        total_images = 0
        total_buttons = 0

        for tsx_file in (self.app_dir / "src").rglob("*.tsx"):
            if "node_modules" in str(tsx_file):
                continue

            try:
                content = tsx_file.read_text(errors='ignore')

                # Check images
                img_matches = re.findall(r'<img[^>]*>', content)
                for img in img_matches:
                    total_images += 1
                    if 'alt=' not in img and 'alt =' not in img:
                        img_without_alt += 1

                # Check buttons without accessible labels
                button_matches = re.findall(r'<button[^>]*>.*?</button>', content, re.DOTALL)
                for btn in button_matches:
                    total_buttons += 1
                    # Check if it has aria-label or visible text
                    if 'aria-label' not in btn and re.search(r'>\s*</', btn):
                        buttons_without_aria += 1

            except Exception:
                pass

        test.checks.append(f"📊 Images: {total_images} total, {img_without_alt} missing alt")
        test.checks.append(f"📊 Buttons: {total_buttons} total, {buttons_without_aria} potentially missing labels")

        if img_without_alt > 0:
            test.errors.append(f"⚠️ {img_without_alt} images missing alt attributes")

        if buttons_without_aria > 5:
            test.errors.append(f"⚠️ {buttons_without_aria} buttons may need aria-labels")

        test.passed = img_without_alt == 0 and buttons_without_aria < 5
        self.results.append(test)

    def test_i18n_setup(self):
        """Check internationalization setup."""
        test = ComponentTest(
            id="CLI-009",
            name="I18n Setup",
            file_path=str(self.app_dir)
        )

        # Check for i18n config
        i18n_patterns = [
            "i18n.ts",
            "i18n.js",
            "next-i18next.config.js",
            "locales/",
            "messages/",
        ]

        found_i18n = False
        for pattern in i18n_patterns:
            if (self.app_dir / pattern).exists() or list(self.app_dir.glob(f"**/{pattern}")):
                test.checks.append(f"✅ Found i18n setup: {pattern}")
                found_i18n = True

        # Check for Chinese content in components
        chinese_files = 0
        for tsx_file in (self.app_dir / "src").rglob("*.tsx"):
            if "node_modules" in str(tsx_file):
                continue
            try:
                content = tsx_file.read_text(errors='ignore')
                if re.search(r'[\u4e00-\u9fff]', content):
                    chinese_files += 1
            except Exception:
                pass

        test.checks.append(f"📊 Files with Chinese content: {chinese_files}")

        if chinese_files > 0:
            test.checks.append("✅ Chinese-first implementation detected")
        else:
            test.errors.append("⚠️ No Chinese content found - check i18n setup")

        test.passed = chinese_files > 0
        self.results.append(test)

    def _generate_report(self) -> Dict[str, Any]:
        """Generate final test report."""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        report = {
            "summary": {
                "total": len(self.results),
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / len(self.results) if self.results else 0
            },
            "tests": []
        }

        for result in self.results:
            report["tests"].append({
                "id": result.id,
                "name": result.name,
                "passed": result.passed,
                "checks": result.checks,
                "errors": result.errors
            })

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RG-TDD CLI Tester")
    parser.add_argument("app_dir", help="Application directory to test")
    parser.add_argument("--output", "-o", help="Output file for JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    tester = CLITester(args.app_dir)
    report = tester.run_all_tests()

    # Print results
    print("\n" + "=" * 60)
    print("🧪 RG-TDD CLI Test Results")
    print("=" * 60)

    for test in report["tests"]:
        status = "✅ PASS" if test["passed"] else "❌ FAIL"
        print(f"\n{test['id']}: {test['name']} - {status}")

        if args.verbose:
            for check in test["checks"]:
                print(f"   {check}")

        for error in test["errors"]:
            print(f"   {error}")

    print("\n" + "-" * 60)
    summary = report["summary"]
    print(f"Summary: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']:.0%})")
    print("=" * 60)

    # Save report
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {args.output}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
