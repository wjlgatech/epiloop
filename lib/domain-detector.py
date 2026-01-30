#!/usr/bin/env python3
# pylint: disable=broad-except
"""
domain-detector.py - Project Domain Detection for claude-loop

Automatically detects the domain context of a project by analyzing:
- Configuration files (package.json, requirements.txt, *.csproj, etc.)
- File patterns and directory structures
- Framework and tool usage

Domain Taxonomy:
    web_frontend    - React, Vue, Angular, Next.js frontends
    web_backend     - Express, FastAPI, Django, Flask backends
    unity_game      - Unity game development
    unity_xr        - Unity XR/VR/AR projects
    isaac_sim       - NVIDIA Isaac Sim projects
    ml_training     - PyTorch/TensorFlow training code
    ml_inference    - Model serving and inference
    data_pipeline   - ETL, data processing
    cli_tool        - Command-line tools
    robotics        - ROS2, robotics projects
    other           - Unknown/general projects

Confidence Levels:
    high    - Strong indicators (specific config files or frameworks)
    medium  - Moderate indicators (file patterns, common libraries)
    low     - Weak indicators (generic patterns)

Usage:
    python3 lib/domain-detector.py detect /path/to/project
    python3 lib/domain-detector.py detect /path/to/project --json
    python3 lib/domain-detector.py detect  # Uses current directory
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Import domain types from experience-store
import importlib.util
_store_path = Path(__file__).parent / "experience-store.py"
if _store_path.exists():
    _spec = importlib.util.spec_from_file_location("experience_store", _store_path)
    _experience_store_module = importlib.util.module_from_spec(_spec)  # type: ignore
    _spec.loader.exec_module(_experience_store_module)  # type: ignore
    DomainContext = _experience_store_module.DomainContext
    DOMAIN_TYPES = _experience_store_module.DOMAIN_TYPES
    DOMAIN_PARENT_CATEGORIES = _experience_store_module.DOMAIN_PARENT_CATEGORIES
else:
    # Fallback definitions
    DOMAIN_TYPES = [
        "web_frontend", "web_backend", "unity_game", "unity_xr",
        "isaac_sim", "ml_training", "ml_inference", "data_pipeline",
        "cli_tool", "robotics", "other"
    ]
    DOMAIN_PARENT_CATEGORIES = {
        "web_frontend": "web", "web_backend": "web",
        "unity_game": "unity", "unity_xr": "unity",
        "isaac_sim": "simulation",
        "ml_training": "ml", "ml_inference": "ml",
        "data_pipeline": "data", "cli_tool": "cli",
        "robotics": "physical", "other": "other"
    }

    @dataclass
    class DomainContext:
        project_type: str
        language: str = ""
        frameworks: List[str] = None  # type: ignore
        tools_used: List[str] = None  # type: ignore

        def __post_init__(self):
            if self.frameworks is None:
                self.frameworks = []
            if self.tools_used is None:
                self.tools_used = []

        def to_dict(self) -> dict:
            return asdict(self)


# ============================================================================
# Detection Signals
# ============================================================================

@dataclass
class DetectionSignal:
    """A signal that indicates a specific domain."""
    signal_type: str  # 'file', 'pattern', 'content', 'framework'
    value: str  # What was found
    weight: float  # Strength of signal (0-1)
    domain: str  # Domain it indicates


@dataclass
class DetectionResult:
    """Result of domain detection."""
    project_type: str
    language: str
    frameworks: List[str]
    tools_used: List[str]
    confidence: str  # 'high', 'medium', 'low'
    confidence_score: float  # 0-1
    signals: List[DetectionSignal]
    alternatives: List[Tuple[str, float]]  # Other possible domains

    def to_dict(self) -> dict:
        data = {
            'project_type': self.project_type,
            'language': self.language,
            'frameworks': self.frameworks,
            'tools_used': self.tools_used,
            'confidence': self.confidence,
            'confidence_score': round(self.confidence_score, 3),
            'signals': [
                {'signal_type': s.signal_type, 'value': s.value,
                 'weight': s.weight, 'domain': s.domain}
                for s in self.signals
            ],
            'alternatives': [
                {'domain': d, 'score': round(s, 3)}
                for d, s in self.alternatives
            ],
        }
        return data

    def to_domain_context(self) -> DomainContext:
        """Convert to DomainContext for experience store."""
        return DomainContext(
            project_type=self.project_type,
            language=self.language,
            frameworks=self.frameworks,
            tools_used=self.tools_used,
        )


# ============================================================================
# Domain Detection Rules
# ============================================================================

# Config files and their domain associations
CONFIG_FILE_SIGNALS: Dict[str, List[Tuple[str, float]]] = {
    # Unity
    "*.csproj": [("unity_game", 0.5)],
    "*.sln": [("unity_game", 0.3)],
    "ProjectSettings/ProjectVersion.txt": [("unity_game", 0.9)],
    "Assets/": [("unity_game", 0.6)],
    "Packages/manifest.json": [("unity_game", 0.8)],

    # Unity XR (must come after unity_game checks)
    "Assets/XR/": [("unity_xr", 0.8)],
    "Packages/com.unity.xr.*": [("unity_xr", 0.9)],

    # Isaac Sim / Omniverse
    ".kit": [("isaac_sim", 0.9)],
    "*.usd": [("isaac_sim", 0.4)],
    "*.usda": [("isaac_sim", 0.4)],
    "*.usdc": [("isaac_sim", 0.4)],
    "omniverse/": [("isaac_sim", 0.7)],
    "exts/": [("isaac_sim", 0.5)],

    # ROS2 / Robotics
    "package.xml": [("robotics", 0.8)],
    "CMakeLists.txt": [("robotics", 0.2)],
    "colcon.meta": [("robotics", 0.9)],
    "*.launch.py": [("robotics", 0.7)],
    "*.srv": [("robotics", 0.7)],
    "*.msg": [("robotics", 0.7)],
    "ros2_ws/": [("robotics", 0.9)],

    # Web Frontend
    "package.json": [("web_frontend", 0.3), ("web_backend", 0.3)],
    "tsconfig.json": [("web_frontend", 0.4)],
    "next.config.js": [("web_frontend", 0.9)],
    "next.config.mjs": [("web_frontend", 0.9)],
    "next.config.ts": [("web_frontend", 0.9)],
    "nuxt.config.ts": [("web_frontend", 0.9)],
    "nuxt.config.js": [("web_frontend", 0.9)],
    "vite.config.ts": [("web_frontend", 0.7)],
    "vite.config.js": [("web_frontend", 0.7)],
    "angular.json": [("web_frontend", 0.9)],
    ".vue": [("web_frontend", 0.7)],
    "tailwind.config.js": [("web_frontend", 0.6)],
    "tailwind.config.ts": [("web_frontend", 0.6)],
    "postcss.config.js": [("web_frontend", 0.4)],
    "webpack.config.js": [("web_frontend", 0.5)],
    "src/App.tsx": [("web_frontend", 0.8)],
    "src/App.jsx": [("web_frontend", 0.8)],
    "src/App.vue": [("web_frontend", 0.8)],
    "public/index.html": [("web_frontend", 0.5)],

    # Web Backend
    "requirements.txt": [("web_backend", 0.2), ("ml_training", 0.2)],
    "pyproject.toml": [("web_backend", 0.2), ("ml_training", 0.2), ("cli_tool", 0.2)],
    "setup.py": [("cli_tool", 0.3)],
    "Pipfile": [("web_backend", 0.3)],
    "manage.py": [("web_backend", 0.9)],  # Django
    "app.py": [("web_backend", 0.5)],
    "main.py": [("web_backend", 0.2), ("cli_tool", 0.3)],
    "server.js": [("web_backend", 0.8)],
    "server.ts": [("web_backend", 0.8)],
    "express.js": [("web_backend", 0.8)],
    "nest-cli.json": [("web_backend", 0.9)],
    "prisma/": [("web_backend", 0.7)],
    "drizzle.config.ts": [("web_backend", 0.7)],
    "Dockerfile": [("web_backend", 0.3)],
    "docker-compose.yml": [("web_backend", 0.3)],
    "docker-compose.yaml": [("web_backend", 0.3)],

    # ML Training
    "train.py": [("ml_training", 0.7)],
    "model.py": [("ml_training", 0.5)],
    "dataset.py": [("ml_training", 0.6)],
    "trainer.py": [("ml_training", 0.7)],
    "configs/": [("ml_training", 0.3)],
    "checkpoints/": [("ml_training", 0.5)],
    "*.pt": [("ml_training", 0.4)],
    "*.pth": [("ml_training", 0.4)],
    "*.ckpt": [("ml_training", 0.4)],
    "*.h5": [("ml_training", 0.4)],
    "notebooks/": [("ml_training", 0.4)],
    "*.ipynb": [("ml_training", 0.3)],

    # ML Inference
    "serve.py": [("ml_inference", 0.8)],
    "inference.py": [("ml_inference", 0.7)],
    "predict.py": [("ml_inference", 0.6)],
    "*.onnx": [("ml_inference", 0.7)],
    "models/": [("ml_inference", 0.3), ("ml_training", 0.3)],
    "triton/": [("ml_inference", 0.9)],
    "model_repository/": [("ml_inference", 0.9)],

    # Data Pipeline
    "dags/": [("data_pipeline", 0.8)],
    "airflow.cfg": [("data_pipeline", 0.9)],
    "prefect.yaml": [("data_pipeline", 0.9)],
    "dagster.yaml": [("data_pipeline", 0.9)],
    "etl/": [("data_pipeline", 0.7)],
    "pipelines/": [("data_pipeline", 0.5)],
    "*.sql": [("data_pipeline", 0.3)],
    "dbt_project.yml": [("data_pipeline", 0.9)],

    # CLI Tool
    "setup.cfg": [("cli_tool", 0.4)],
    "cli/": [("cli_tool", 0.6)],
    "commands/": [("cli_tool", 0.5)],
    "bin/": [("cli_tool", 0.4)],
}

# Content patterns to search in files
CONTENT_SIGNALS: Dict[str, List[Tuple[str, str, float]]] = {
    # file pattern -> [(content_regex, domain, weight), ...]
    "package.json": [
        ("react", "web_frontend", 0.8),
        ("vue", "web_frontend", 0.8),
        ("@angular/core", "web_frontend", 0.9),
        ("next", "web_frontend", 0.8),
        ("nuxt", "web_frontend", 0.8),
        ("svelte", "web_frontend", 0.8),
        ("express", "web_backend", 0.7),
        ("fastify", "web_backend", 0.7),
        ("@nestjs/core", "web_backend", 0.9),
        ("koa", "web_backend", 0.7),
        ("hapi", "web_backend", 0.7),
        ("commander", "cli_tool", 0.6),
        ("yargs", "cli_tool", 0.6),
        ("oclif", "cli_tool", 0.8),
    ],
    "requirements.txt": [
        ("torch", "ml_training", 0.7),
        ("tensorflow", "ml_training", 0.7),
        ("pytorch-lightning", "ml_training", 0.8),
        ("transformers", "ml_training", 0.7),
        ("scikit-learn", "ml_training", 0.5),
        ("fastapi", "web_backend", 0.8),
        ("flask", "web_backend", 0.7),
        ("django", "web_backend", 0.9),
        ("uvicorn", "web_backend", 0.6),
        ("gunicorn", "web_backend", 0.6),
        ("celery", "web_backend", 0.5),
        ("click", "cli_tool", 0.5),
        ("typer", "cli_tool", 0.7),
        ("argparse", "cli_tool", 0.4),
        ("pandas", "data_pipeline", 0.4),
        ("dask", "data_pipeline", 0.7),
        ("pyspark", "data_pipeline", 0.8),
        ("apache-airflow", "data_pipeline", 0.9),
        ("prefect", "data_pipeline", 0.8),
        ("omni.isaac", "isaac_sim", 0.9),
        ("isaacsim", "isaac_sim", 0.9),
        ("pxr", "isaac_sim", 0.7),
        ("ros2", "robotics", 0.8),
        ("rclpy", "robotics", 0.9),
    ],
    "pyproject.toml": [
        ("torch", "ml_training", 0.7),
        ("tensorflow", "ml_training", 0.7),
        ("fastapi", "web_backend", 0.8),
        ("flask", "web_backend", 0.7),
        ("django", "web_backend", 0.9),
        ("click", "cli_tool", 0.5),
        ("typer", "cli_tool", 0.7),
        ("scripts", "cli_tool", 0.4),
    ],
    "*.csproj": [
        ("Unity", "unity_game", 0.8),
        ("UnityEngine", "unity_game", 0.9),
        ("XR", "unity_xr", 0.7),
        ("OpenXR", "unity_xr", 0.8),
        ("ARFoundation", "unity_xr", 0.9),
        ("Oculus", "unity_xr", 0.8),
    ],
    "Packages/manifest.json": [
        ("com.unity.xr", "unity_xr", 0.9),
        ("com.unity.inputsystem", "unity_game", 0.5),
        ("com.unity.render-pipelines", "unity_game", 0.6),
    ],
}

# Framework to language mapping
FRAMEWORK_LANGUAGES: Dict[str, str] = {
    "react": "typescript",
    "vue": "typescript",
    "angular": "typescript",
    "next": "typescript",
    "nuxt": "typescript",
    "svelte": "typescript",
    "express": "javascript",
    "fastify": "typescript",
    "nest": "typescript",
    "fastapi": "python",
    "flask": "python",
    "django": "python",
    "pytorch": "python",
    "tensorflow": "python",
    "unity": "csharp",
    "isaac_sim": "python",
    "ros2": "python",
}


# ============================================================================
# Domain Detector Class
# ============================================================================

class DomainDetector:
    """Detects project domain from file structure and contents."""

    def __init__(self, project_path: str = "."):
        """Initialize detector for a project path.

        Args:
            project_path: Path to project root directory
        """
        self.project_path = Path(project_path).resolve()
        self.signals: List[DetectionSignal] = []
        self.domain_scores: Dict[str, float] = {d: 0.0 for d in DOMAIN_TYPES}
        self.frameworks: Set[str] = set()
        self.tools: Set[str] = set()
        self.languages: Set[str] = set()

    def detect(self) -> DetectionResult:
        """Run detection and return result.

        Returns:
            DetectionResult with detected domain and confidence
        """
        # Check config files
        self._check_config_files()

        # Check file contents
        self._check_file_contents()

        # Check file patterns
        self._check_file_patterns()

        # Determine primary domain
        primary_domain, confidence_score = self._calculate_primary_domain()

        # Determine confidence level
        if confidence_score >= 0.7:
            confidence = "high"
        elif confidence_score >= 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        # Get alternatives
        alternatives = self._get_alternatives(primary_domain)

        # Determine primary language
        language = self._determine_language(primary_domain)

        return DetectionResult(
            project_type=primary_domain,
            language=language,
            frameworks=sorted(list(self.frameworks)),
            tools_used=sorted(list(self.tools)),
            confidence=confidence,
            confidence_score=confidence_score,
            signals=self.signals,
            alternatives=alternatives,
        )

    def _add_signal(
        self,
        signal_type: str,
        value: str,
        weight: float,
        domain: str,
    ) -> None:
        """Add a detection signal."""
        self.signals.append(DetectionSignal(
            signal_type=signal_type,
            value=value,
            weight=weight,
            domain=domain,
        ))
        self.domain_scores[domain] = self.domain_scores.get(domain, 0) + weight

    def _check_config_files(self) -> None:
        """Check for known configuration files."""
        for pattern, signals in CONFIG_FILE_SIGNALS.items():
            matches = []

            # Handle glob patterns
            if "*" in pattern or pattern.endswith("/"):
                if pattern.endswith("/"):
                    # Directory check
                    dir_path = self.project_path / pattern.rstrip("/")
                    if dir_path.is_dir():
                        matches = [pattern]
                else:
                    matches = list(self.project_path.glob(pattern))
            else:
                # Exact file check
                file_path = self.project_path / pattern
                if file_path.exists():
                    matches = [pattern]

            if matches:
                for domain, weight in signals:
                    self._add_signal("file", pattern, weight, domain)

    def _check_file_contents(self) -> None:
        """Check file contents for framework/library indicators."""
        for file_pattern, content_checks in CONTENT_SIGNALS.items():
            # Find matching files
            if "*" in file_pattern:
                files = list(self.project_path.glob(file_pattern))
            else:
                files = [self.project_path / file_pattern]

            for file_path in files:
                if not file_path.exists() or not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    content_lower = content.lower()

                    for search_term, domain, weight in content_checks:
                        if search_term.lower() in content_lower:
                            self._add_signal("content", f"{file_path.name}:{search_term}", weight, domain)
                            self.frameworks.add(search_term)

                except (IOError, UnicodeDecodeError):
                    pass

    def _check_file_patterns(self) -> None:
        """Check for common file patterns indicating domains."""
        # Count file extensions
        extension_counts: Dict[str, int] = {}
        for file_path in self.project_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                extension_counts[ext] = extension_counts.get(ext, 0) + 1

        # Python files
        py_count = extension_counts.get(".py", 0)
        if py_count > 10:
            self.languages.add("python")

        # TypeScript/JavaScript files
        ts_count = extension_counts.get(".ts", 0) + extension_counts.get(".tsx", 0)
        js_count = extension_counts.get(".js", 0) + extension_counts.get(".jsx", 0)
        if ts_count > 5:
            self.languages.add("typescript")
            self._add_signal("pattern", "typescript_files", 0.3, "web_frontend")
        if js_count > 5:
            self.languages.add("javascript")

        # C# files
        cs_count = extension_counts.get(".cs", 0)
        if cs_count > 5:
            self.languages.add("csharp")
            self._add_signal("pattern", "csharp_files", 0.4, "unity_game")

        # Jupyter notebooks
        ipynb_count = extension_counts.get(".ipynb", 0)
        if ipynb_count > 2:
            self._add_signal("pattern", "notebooks", 0.4, "ml_training")

        # USD files (Omniverse/Isaac)
        usd_count = (extension_counts.get(".usd", 0) +
                     extension_counts.get(".usda", 0) +
                     extension_counts.get(".usdc", 0))
        if usd_count > 0:
            self._add_signal("pattern", "usd_files", 0.5, "isaac_sim")

        # ROS message/service files
        msg_count = extension_counts.get(".msg", 0) + extension_counts.get(".srv", 0)
        if msg_count > 0:
            self._add_signal("pattern", "ros_files", 0.6, "robotics")

    def _calculate_primary_domain(self) -> Tuple[str, float]:
        """Calculate primary domain from accumulated scores."""
        if not self.domain_scores:
            return "other", 0.0

        # Normalize scores
        max_score = max(self.domain_scores.values())
        if max_score == 0:
            return "other", 0.0

        # Find domain with highest score
        primary = max(self.domain_scores.items(), key=lambda x: x[1])
        domain = primary[0]
        raw_score = primary[1]

        # Calculate confidence score (normalized by max possible)
        # Consider number of signals and their weights
        signal_count = len([s for s in self.signals if s.domain == domain])
        confidence = min(1.0, raw_score / 2.0)  # Scale so 2.0 total weight = 100%

        # Boost confidence if multiple signals agree
        if signal_count >= 3:
            confidence = min(1.0, confidence * 1.2)

        return domain, confidence

    def _get_alternatives(self, primary: str) -> List[Tuple[str, float]]:
        """Get alternative domains sorted by score."""
        alternatives = []
        max_score = max(self.domain_scores.values()) if self.domain_scores else 1.0

        for domain, score in self.domain_scores.items():
            if domain != primary and score > 0:
                normalized = score / max_score if max_score > 0 else 0
                alternatives.append((domain, normalized))

        return sorted(alternatives, key=lambda x: x[1], reverse=True)[:3]

    def _determine_language(self, domain: str) -> str:
        """Determine primary language for the domain."""
        # Check detected languages
        if self.languages:
            # Prefer languages that match domain expectations
            domain_expected = {
                "unity_game": "csharp",
                "unity_xr": "csharp",
                "web_frontend": "typescript",
                "web_backend": "python",
                "ml_training": "python",
                "ml_inference": "python",
                "data_pipeline": "python",
                "robotics": "python",
                "isaac_sim": "python",
                "cli_tool": "python",
            }

            expected = domain_expected.get(domain, "")
            if expected and expected in self.languages:
                return expected

            # Return most common detected language
            return list(self.languages)[0]

        # Check frameworks for language hints
        for framework in self.frameworks:
            lang = FRAMEWORK_LANGUAGES.get(framework.lower())
            if lang:
                return lang

        return ""


# ============================================================================
# CLI Interface
# ============================================================================

def cmd_detect(args: argparse.Namespace) -> int:
    """Detect domain for a project."""
    project_path = args.path or "."

    if not Path(project_path).exists():
        print(f"Error: Path does not exist: {project_path}", file=sys.stderr)
        return 1

    detector = DomainDetector(project_path)
    result = detector.detect()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Domain Detection Result for: {Path(project_path).resolve()}")
        print("=" * 60)
        print(f"\nPrimary Domain: {result.project_type}")
        print(f"Confidence:     {result.confidence} ({result.confidence_score:.0%})")
        print(f"Language:       {result.language or 'unknown'}")

        if result.frameworks:
            print(f"Frameworks:     {', '.join(result.frameworks[:5])}")

        if result.tools_used:
            print(f"Tools:          {', '.join(result.tools_used[:5])}")

        if result.alternatives:
            print(f"\nAlternatives:")
            for domain, score in result.alternatives:
                print(f"  - {domain}: {score:.0%}")

        if args.verbose and result.signals:
            print(f"\nDetection Signals:")
            for signal in result.signals[:10]:
                print(f"  [{signal.signal_type}] {signal.value} -> {signal.domain} (weight: {signal.weight})")

    return 0


def cmd_list_domains(args: argparse.Namespace) -> int:
    """List all supported domain types."""
    _ = args  # Unused
    print("Supported Domain Types:")
    print("=" * 40)
    for domain in DOMAIN_TYPES:
        parent = DOMAIN_PARENT_CATEGORIES.get(domain, "other")
        print(f"  {domain:20} [{parent}]")
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Project Domain Detection for claude-loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # detect command
    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect domain for a project",
    )
    detect_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to project (default: current directory)",
    )
    detect_parser.add_argument("--json", action="store_true", help="Output as JSON")
    detect_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # list-domains command
    subparsers.add_parser(
        "list-domains",
        help="List all supported domain types",
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        # Default to detect current directory
        args.command = "detect"
        args.path = "."

    if args.command == "detect":
        return cmd_detect(args)
    elif args.command == "list-domains":
        return cmd_list_domains(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
