#!/usr/bin/env python3
# pylint: disable=broad-except
"""
domain-adapter.py - Domain Adapter Extension System for claude-loop

Provides domain-specific capabilities as separate versioned packages.
Adapters can provide: prompts, tools, validators, experience embeddings.

Key Features:
- Adapter manifest (adapter.json) with name, version, domain, capabilities, maintainer
- Adapters directory: adapters/{domain}/ with isolated code
- Adapters are versioned independently (semver)
- Adapters cannot modify core claude-loop files
- Domain-based auto-loading based on detected project domain
- Graceful degradation if adapter unavailable

Directory Structure:
    adapters/
        unity/
            adapter.json        # Manifest
            prompts/            # Domain-specific prompts
            tools/              # Custom tool definitions
            validators/         # Domain-specific validators
            embeddings/         # Custom embedding functions
            CHANGELOG.md        # Version history
            README.md           # Documentation

Usage:
    # List installed adapters
    python3 lib/domain-adapter.py list

    # Enable/disable an adapter
    python3 lib/domain-adapter.py enable <name>
    python3 lib/domain-adapter.py disable <name>

    # Update an adapter to latest
    python3 lib/domain-adapter.py update <name>

    # Show adapter info
    python3 lib/domain-adapter.py info <name>

    # Load adapters for a domain (used internally)
    python3 lib/domain-adapter.py load-for-domain <domain>

CLI Options:
    --adapters-dir DIR  Adapters directory (default: ./adapters)
    --json              Output as JSON
    --verbose           Enable verbose output
"""

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ============================================================================
# Constants
# ============================================================================

DEFAULT_ADAPTERS_DIR = "adapters"
CONFIG_FILE = ".claude-loop/adapter_config.json"
MANIFEST_FILE = "adapter.json"
CORE_FILES = [
    "claude-loop.sh",
    "lib/execution-logger.sh",
    "lib/core-protection.py",
    "lib/prd-parser.sh",
    "lib/monitoring.sh",
    "lib/worker.sh",
    "lib/parallel.sh",
]

# Adapter capability types
CAPABILITY_TYPES = [
    "prompts",       # Domain-specific prompt templates
    "tools",         # Custom tool definitions
    "validators",    # Domain-specific validators
    "embeddings",    # Custom embedding functions
]

# Semver regex pattern
SEMVER_PATTERN = re.compile(
    r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
    r'(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)'
    r')?(?:\+(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AdapterCapability:
    """A capability provided by an adapter."""
    type: str  # prompts, tools, validators, embeddings
    name: str
    path: str  # Relative path within adapter
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AdapterManifest:
    """Manifest describing a domain adapter."""
    name: str
    version: str  # semver
    domain: str  # Primary domain this adapter supports
    domains: List[str]  # All domains this adapter supports
    description: str
    maintainer: str
    capabilities: List[AdapterCapability]
    dependencies: List[str] = field(default_factory=list)  # Other adapters required
    min_claude_loop_version: str = "1.0.0"
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["capabilities"] = [c.to_dict() if hasattr(c, 'to_dict') else c
                                   for c in self.capabilities]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AdapterManifest":
        """Create manifest from dictionary."""
        capabilities = []
        for cap in data.get("capabilities", []):
            if isinstance(cap, dict):
                capabilities.append(AdapterCapability(**cap))
            else:
                capabilities.append(cap)

        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.0.0"),
            domain=data.get("domain", "other"),
            domains=data.get("domains", [data.get("domain", "other")]),
            description=data.get("description", ""),
            maintainer=data.get("maintainer", ""),
            capabilities=capabilities,
            dependencies=data.get("dependencies", []),
            min_claude_loop_version=data.get("min_claude_loop_version", "1.0.0"),
            keywords=data.get("keywords", []),
        )


@dataclass
class AdapterState:
    """Runtime state of an adapter."""
    name: str
    path: str  # Absolute path to adapter directory
    manifest: AdapterManifest
    enabled: bool
    loaded: bool = False
    load_error: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "manifest": self.manifest.to_dict(),
            "enabled": self.enabled,
            "loaded": self.loaded,
            "load_error": self.load_error,
            "last_updated": self.last_updated,
        }


@dataclass
class AdapterConfig:
    """Configuration for adapter management."""
    enabled_adapters: List[str] = field(default_factory=list)
    disabled_adapters: List[str] = field(default_factory=list)
    adapter_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_update_check: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AdapterConfig":
        return cls(
            enabled_adapters=data.get("enabled_adapters", []),
            disabled_adapters=data.get("disabled_adapters", []),
            adapter_settings=data.get("adapter_settings", {}),
            last_update_check=data.get("last_update_check"),
        )


# ============================================================================
# Adapter Manager
# ============================================================================

class AdapterManager:
    """Manages domain adapters for claude-loop."""

    def __init__(
        self,
        adapters_dir: str = DEFAULT_ADAPTERS_DIR,
        base_dir: str = ".",
        verbose: bool = False,
    ):
        self.adapters_dir = Path(adapters_dir).resolve()
        self.base_dir = Path(base_dir).resolve()
        self.config_file = self.base_dir / CONFIG_FILE
        self.verbose = verbose

        # Runtime state
        self._adapters: Dict[str, AdapterState] = {}
        self._config: Optional[AdapterConfig] = None
        self._loaded_for_domains: Set[str] = set()

    def _log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[adapter] {message}", file=sys.stderr)

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> AdapterConfig:
        """Load adapter configuration."""
        if self._config is not None:
            return self._config

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                self._config = AdapterConfig.from_dict(data)
            except Exception as e:
                self._log(f"Error loading config: {e}")
                self._config = AdapterConfig()
        else:
            self._config = AdapterConfig()

        return self._config

    def _save_config(self) -> None:
        """Save adapter configuration."""
        self._ensure_config_dir()
        config = self._load_config()
        try:
            with open(self.config_file, "w") as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception as e:
            self._log(f"Error saving config: {e}")

    def _load_manifest(self, adapter_dir: Path) -> Optional[AdapterManifest]:
        """Load adapter manifest from directory."""
        manifest_path = adapter_dir / MANIFEST_FILE
        if not manifest_path.exists():
            self._log(f"No manifest found at {manifest_path}")
            return None

        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
            return AdapterManifest.from_dict(data)
        except Exception as e:
            self._log(f"Error loading manifest: {e}")
            return None

    def _validate_semver(self, version: str) -> bool:
        """Validate semantic version format."""
        return SEMVER_PATTERN.match(version) is not None

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two semver versions. Returns: -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
        def parse_version(v: str) -> Tuple[int, int, int, str]:
            match = SEMVER_PATTERN.match(v)
            if not match:
                return (0, 0, 0, "")
            return (
                int(match.group("major")),
                int(match.group("minor")),
                int(match.group("patch")),
                match.group("prerelease") or "",
            )

        v1_major, v1_minor, v1_patch, v1_pre = parse_version(v1)
        v2_major, v2_minor, v2_patch, v2_pre = parse_version(v2)

        # Compare major.minor.patch
        if v1_major < v2_major:
            return -1
        if v1_major > v2_major:
            return 1
        if v1_minor < v2_minor:
            return -1
        if v1_minor > v2_minor:
            return 1
        if v1_patch < v2_patch:
            return -1
        if v1_patch > v2_patch:
            return 1

        # Compare prerelease (no prerelease > prerelease)
        if not v1_pre and v2_pre:
            return 1
        if v1_pre and not v2_pre:
            return -1
        if v1_pre < v2_pre:
            return -1
        if v1_pre > v2_pre:
            return 1

        return 0

    def discover_adapters(self) -> List[AdapterState]:
        """Discover all adapters in the adapters directory."""
        if not self.adapters_dir.exists():
            self._log(f"Adapters directory does not exist: {self.adapters_dir}")
            return []

        config = self._load_config()
        adapters = []

        for adapter_dir in self.adapters_dir.iterdir():
            if not adapter_dir.is_dir():
                continue
            if adapter_dir.name.startswith("."):
                continue

            manifest = self._load_manifest(adapter_dir)
            if manifest is None:
                self._log(f"Skipping {adapter_dir.name}: no valid manifest")
                continue

            # Determine if enabled
            enabled = True
            if manifest.name in config.disabled_adapters:
                enabled = False
            elif manifest.name in config.enabled_adapters:
                enabled = True

            state = AdapterState(
                name=manifest.name,
                path=str(adapter_dir),
                manifest=manifest,
                enabled=enabled,
            )

            adapters.append(state)
            self._adapters[manifest.name] = state

        return adapters

    def get_adapter(self, name: str) -> Optional[AdapterState]:
        """Get an adapter by name."""
        if not self._adapters:
            self.discover_adapters()
        return self._adapters.get(name)

    def list_adapters(self) -> List[AdapterState]:
        """List all discovered adapters."""
        if not self._adapters:
            self.discover_adapters()
        return list(self._adapters.values())

    def enable_adapter(self, name: str) -> Tuple[bool, str]:
        """Enable an adapter."""
        adapter = self.get_adapter(name)
        if adapter is None:
            return False, f"Adapter '{name}' not found"

        config = self._load_config()

        # Remove from disabled, add to enabled
        if name in config.disabled_adapters:
            config.disabled_adapters.remove(name)
        if name not in config.enabled_adapters:
            config.enabled_adapters.append(name)

        adapter.enabled = True
        self._save_config()

        return True, f"Adapter '{name}' enabled"

    def disable_adapter(self, name: str) -> Tuple[bool, str]:
        """Disable an adapter."""
        adapter = self.get_adapter(name)
        if adapter is None:
            return False, f"Adapter '{name}' not found"

        config = self._load_config()

        # Remove from enabled, add to disabled
        if name in config.enabled_adapters:
            config.enabled_adapters.remove(name)
        if name not in config.disabled_adapters:
            config.disabled_adapters.append(name)

        adapter.enabled = False
        self._save_config()

        return True, f"Adapter '{name}' disabled"

    def get_adapter_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about an adapter."""
        adapter = self.get_adapter(name)
        if adapter is None:
            return None

        adapter_dir = Path(adapter.path)

        # Get changelog if present
        changelog_path = adapter_dir / "CHANGELOG.md"
        changelog = None
        if changelog_path.exists():
            try:
                with open(changelog_path, "r") as f:
                    changelog = f.read()
            except Exception:
                pass

        # Get README if present
        readme_path = adapter_dir / "README.md"
        readme = None
        if readme_path.exists():
            try:
                with open(readme_path, "r") as f:
                    readme = f.read()
            except Exception:
                pass

        # Get capability files
        capabilities_detail = []
        for cap in adapter.manifest.capabilities:
            cap_path = adapter_dir / cap.path
            cap_info = cap.to_dict()
            cap_info["exists"] = cap_path.exists()
            if cap_path.is_dir():
                cap_info["files"] = [f.name for f in cap_path.iterdir() if f.is_file()]
            capabilities_detail.append(cap_info)

        return {
            "name": adapter.name,
            "version": adapter.manifest.version,
            "domain": adapter.manifest.domain,
            "domains": adapter.manifest.domains,
            "description": adapter.manifest.description,
            "maintainer": adapter.manifest.maintainer,
            "enabled": adapter.enabled,
            "loaded": adapter.loaded,
            "load_error": adapter.load_error,
            "path": adapter.path,
            "capabilities": capabilities_detail,
            "dependencies": adapter.manifest.dependencies,
            "min_claude_loop_version": adapter.manifest.min_claude_loop_version,
            "keywords": adapter.manifest.keywords,
            "changelog": changelog,
            "readme": readme,
        }

    def update_adapter(self, name: str, source: Optional[str] = None) -> Tuple[bool, str]:
        """
        Update an adapter to the latest version.

        For now, this is a placeholder that checks for local updates.
        In the future, this could pull from a registry or git repository.
        """
        adapter = self.get_adapter(name)
        if adapter is None:
            return False, f"Adapter '{name}' not found"

        # Check if there's a newer version available locally (e.g., from source)
        if source:
            source_path = Path(source)
            if not source_path.exists():
                return False, f"Source path not found: {source}"

            source_manifest = self._load_manifest(source_path)
            if source_manifest is None:
                return False, f"No valid manifest in source: {source}"

            if self._compare_versions(source_manifest.version, adapter.manifest.version) <= 0:
                return False, f"Source version {source_manifest.version} is not newer than current {adapter.manifest.version}"

            # Copy adapter files (preserve current config)
            try:
                # Backup current adapter
                backup_path = Path(adapter.path).parent / f".{name}_backup_{int(datetime.now().timestamp())}"
                shutil.copytree(adapter.path, backup_path)

                # Copy new files
                shutil.rmtree(adapter.path)
                shutil.copytree(source_path, adapter.path)

                # Reload manifest
                new_manifest = self._load_manifest(Path(adapter.path))
                if new_manifest:
                    adapter.manifest = new_manifest
                    adapter.last_updated = datetime.now(timezone.utc).isoformat()

                return True, f"Updated {name} from {adapter.manifest.version} to {source_manifest.version}"
            except Exception as e:
                return False, f"Update failed: {e}"

        # No source provided - check for local updates isn't meaningful yet
        return False, f"No update source specified. Use --source <path> to update from a local directory."

    def load_for_domain(self, domain: str) -> List[AdapterState]:
        """Load all adapters that support a given domain."""
        if domain in self._loaded_for_domains:
            return [a for a in self._adapters.values()
                    if domain in a.manifest.domains and a.loaded]

        adapters = self.discover_adapters()
        loaded = []

        for adapter in adapters:
            if not adapter.enabled:
                continue
            if domain not in adapter.manifest.domains:
                continue

            # Try to load adapter
            try:
                self._load_adapter(adapter)
                loaded.append(adapter)
            except Exception as e:
                adapter.load_error = str(e)
                self._log(f"Failed to load adapter {adapter.name}: {e}")

        self._loaded_for_domains.add(domain)
        return loaded

    def _load_adapter(self, adapter: AdapterState) -> None:
        """Load an adapter's capabilities."""
        adapter_dir = Path(adapter.path)

        # Validate adapter doesn't touch core files
        for cap in adapter.manifest.capabilities:
            cap_path = adapter_dir / cap.path
            if cap_path.exists() and cap_path.is_file():
                # Check content doesn't reference core files for modification
                try:
                    content = cap_path.read_text()
                    for core_file in CORE_FILES:
                        # Look for suspicious patterns
                        if f'open("{core_file}"' in content or f"open('{core_file}'" in content:
                            if "w" in content:  # Potential write
                                raise ValueError(f"Adapter attempts to modify core file: {core_file}")
                except Exception as e:
                    if "Adapter attempts to modify" in str(e):
                        raise
                    # Ignore other errors (binary files, etc.)

        adapter.loaded = True
        adapter.load_error = None
        self._log(f"Loaded adapter: {adapter.name} v{adapter.manifest.version}")

    def get_prompts_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all prompt templates for a domain."""
        prompts = []
        loaded = self.load_for_domain(domain)

        for adapter in loaded:
            adapter_dir = Path(adapter.path)
            for cap in adapter.manifest.capabilities:
                if cap.type != "prompts":
                    continue

                prompts_dir = adapter_dir / cap.path
                if not prompts_dir.exists():
                    continue

                for prompt_file in prompts_dir.glob("*.md"):
                    try:
                        content = prompt_file.read_text()
                        prompts.append({
                            "adapter": adapter.name,
                            "name": prompt_file.stem,
                            "path": str(prompt_file),
                            "content": content,
                        })
                    except Exception as e:
                        self._log(f"Error reading prompt {prompt_file}: {e}")

        return prompts

    def get_validators_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all validators for a domain."""
        validators = []
        loaded = self.load_for_domain(domain)

        for adapter in loaded:
            adapter_dir = Path(adapter.path)
            for cap in adapter.manifest.capabilities:
                if cap.type != "validators":
                    continue

                validators_dir = adapter_dir / cap.path
                if not validators_dir.exists():
                    continue

                for validator_file in validators_dir.glob("*.py"):
                    validators.append({
                        "adapter": adapter.name,
                        "name": validator_file.stem,
                        "path": str(validator_file),
                    })

        return validators

    def get_tools_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all custom tools for a domain."""
        tools = []
        loaded = self.load_for_domain(domain)

        for adapter in loaded:
            adapter_dir = Path(adapter.path)
            for cap in adapter.manifest.capabilities:
                if cap.type != "tools":
                    continue

                tools_dir = adapter_dir / cap.path
                if not tools_dir.exists():
                    continue

                for tool_file in tools_dir.glob("*.json"):
                    try:
                        with open(tool_file, "r") as f:
                            tool_def = json.load(f)
                        tools.append({
                            "adapter": adapter.name,
                            "name": tool_file.stem,
                            "path": str(tool_file),
                            "definition": tool_def,
                        })
                    except Exception as e:
                        self._log(f"Error reading tool {tool_file}: {e}")

        return tools

    def get_embeddings_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get custom embedding configurations for a domain."""
        embeddings = []
        loaded = self.load_for_domain(domain)

        for adapter in loaded:
            adapter_dir = Path(adapter.path)
            for cap in adapter.manifest.capabilities:
                if cap.type != "embeddings":
                    continue

                embeddings_dir = adapter_dir / cap.path
                if not embeddings_dir.exists():
                    continue

                # Look for embedding config
                config_file = embeddings_dir / "config.json"
                if config_file.exists():
                    try:
                        with open(config_file, "r") as f:
                            config = json.load(f)
                        embeddings.append({
                            "adapter": adapter.name,
                            "path": str(embeddings_dir),
                            "config": config,
                        })
                    except Exception as e:
                        self._log(f"Error reading embedding config: {e}")

        return embeddings


# ============================================================================
# CLI Interface
# ============================================================================

def format_adapter_table(adapters: List[AdapterState]) -> str:
    """Format adapters as a table for display."""
    if not adapters:
        return "No adapters found."

    lines = []
    lines.append(f"{'Name':<20} {'Version':<12} {'Domain':<15} {'Status':<10} {'Loaded':<8}")
    lines.append("-" * 70)

    for adapter in adapters:
        status = "enabled" if adapter.enabled else "disabled"
        loaded = "yes" if adapter.loaded else "no"
        lines.append(
            f"{adapter.name:<20} {adapter.manifest.version:<12} "
            f"{adapter.manifest.domain:<15} {status:<10} {loaded:<8}"
        )

    return "\n".join(lines)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Domain Adapter Extension System for claude-loop"
    )

    # Global options
    parser.add_argument(
        "--adapters-dir",
        default=DEFAULT_ADAPTERS_DIR,
        help=f"Adapters directory (default: {DEFAULT_ADAPTERS_DIR})"
    )
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Base directory for config files (default: current directory)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    list_parser = subparsers.add_parser("list", help="List installed adapters")
    list_parser.add_argument("--domain", help="Filter by domain")

    # enable command
    enable_parser = subparsers.add_parser("enable", help="Enable an adapter")
    enable_parser.add_argument("name", help="Adapter name")

    # disable command
    disable_parser = subparsers.add_parser("disable", help="Disable an adapter")
    disable_parser.add_argument("name", help="Adapter name")

    # update command
    update_parser = subparsers.add_parser("update", help="Update an adapter")
    update_parser.add_argument("name", help="Adapter name")
    update_parser.add_argument("--source", help="Source directory for update")

    # info command
    info_parser = subparsers.add_parser("info", help="Show adapter info")
    info_parser.add_argument("name", help="Adapter name")

    # load-for-domain command
    load_parser = subparsers.add_parser("load-for-domain", help="Load adapters for a domain")
    load_parser.add_argument("domain", help="Domain to load adapters for")

    # prompts command
    prompts_parser = subparsers.add_parser("prompts", help="Get prompts for a domain")
    prompts_parser.add_argument("domain", help="Domain to get prompts for")

    # validators command
    validators_parser = subparsers.add_parser("validators", help="Get validators for a domain")
    validators_parser.add_argument("domain", help="Domain to get validators for")

    # tools command
    tools_parser = subparsers.add_parser("tools", help="Get tools for a domain")
    tools_parser.add_argument("domain", help="Domain to get tools for")

    args = parser.parse_args()

    manager = AdapterManager(
        adapters_dir=args.adapters_dir,
        base_dir=args.base_dir,
        verbose=args.verbose,
    )

    if args.command == "list":
        adapters = manager.list_adapters()
        if args.domain:
            adapters = [a for a in adapters if args.domain in a.manifest.domains]

        if args.json:
            print(json.dumps([a.to_dict() for a in adapters], indent=2))
        else:
            print(format_adapter_table(adapters))
        return 0

    elif args.command == "enable":
        success, message = manager.enable_adapter(args.name)
        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)
        return 0 if success else 1

    elif args.command == "disable":
        success, message = manager.disable_adapter(args.name)
        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)
        return 0 if success else 1

    elif args.command == "update":
        success, message = manager.update_adapter(args.name, source=getattr(args, 'source', None))
        if args.json:
            print(json.dumps({"success": success, "message": message}))
        else:
            print(message)
        return 0 if success else 1

    elif args.command == "info":
        info = manager.get_adapter_info(args.name)
        if info is None:
            if args.json:
                print(json.dumps({"error": f"Adapter '{args.name}' not found"}))
            else:
                print(f"Adapter '{args.name}' not found")
            return 1

        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"Name:        {info['name']}")
            print(f"Version:     {info['version']}")
            print(f"Domain:      {info['domain']}")
            print(f"Domains:     {', '.join(info['domains'])}")
            print(f"Description: {info['description']}")
            print(f"Maintainer:  {info['maintainer']}")
            print(f"Status:      {'enabled' if info['enabled'] else 'disabled'}")
            print(f"Loaded:      {'yes' if info['loaded'] else 'no'}")
            if info['load_error']:
                print(f"Load Error:  {info['load_error']}")
            print(f"Path:        {info['path']}")
            print(f"Dependencies: {', '.join(info['dependencies']) if info['dependencies'] else 'none'}")
            print(f"Keywords:    {', '.join(info['keywords']) if info['keywords'] else 'none'}")
            print()
            print("Capabilities:")
            for cap in info['capabilities']:
                status = "exists" if cap.get('exists', False) else "missing"
                files = cap.get('files', [])
                files_str = f" ({len(files)} files)" if files else ""
                print(f"  - {cap['type']}/{cap['name']}: {status}{files_str}")

            if info.get('changelog'):
                print()
                print("Changelog (first 500 chars):")
                print(info['changelog'][:500])

        return 0

    elif args.command == "load-for-domain":
        loaded = manager.load_for_domain(args.domain)
        if args.json:
            print(json.dumps([a.to_dict() for a in loaded], indent=2))
        else:
            if loaded:
                print(f"Loaded {len(loaded)} adapter(s) for domain '{args.domain}':")
                for adapter in loaded:
                    print(f"  - {adapter.name} v{adapter.manifest.version}")
            else:
                print(f"No adapters found for domain '{args.domain}'")
        return 0

    elif args.command == "prompts":
        prompts = manager.get_prompts_for_domain(args.domain)
        if args.json:
            print(json.dumps(prompts, indent=2))
        else:
            if prompts:
                print(f"Prompts for domain '{args.domain}':")
                for prompt in prompts:
                    print(f"  - [{prompt['adapter']}] {prompt['name']}")
            else:
                print(f"No prompts found for domain '{args.domain}'")
        return 0

    elif args.command == "validators":
        validators = manager.get_validators_for_domain(args.domain)
        if args.json:
            print(json.dumps(validators, indent=2))
        else:
            if validators:
                print(f"Validators for domain '{args.domain}':")
                for validator in validators:
                    print(f"  - [{validator['adapter']}] {validator['name']}")
            else:
                print(f"No validators found for domain '{args.domain}'")
        return 0

    elif args.command == "tools":
        tools = manager.get_tools_for_domain(args.domain)
        if args.json:
            print(json.dumps(tools, indent=2))
        else:
            if tools:
                print(f"Tools for domain '{args.domain}':")
                for tool in tools:
                    print(f"  - [{tool['adapter']}] {tool['name']}")
            else:
                print(f"No tools found for domain '{args.domain}'")
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
