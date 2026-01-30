#!/usr/bin/env python3
"""
USD Prim Path Validator for Physical AI

Validates USD prim paths for common errors and conventions.
"""

import re
from typing import Any, Dict, List, Tuple


# Valid prim path pattern
# Paths must start with / and contain only valid characters
PRIM_PATH_PATTERN = re.compile(
    r'^/([a-zA-Z_][a-zA-Z0-9_]*(/[a-zA-Z_][a-zA-Z0-9_]*)*)?$'
)

# Common invalid patterns
INVALID_PATTERNS = [
    (r'\s', "Path contains whitespace"),
    (r'[^\x00-\x7F]', "Path contains non-ASCII characters"),
    (r'//', "Path contains double slashes"),
    (r'/$', "Path ends with slash (except root)"),
    (r'^[^/]', "Path must start with '/'"),
    (r'\.\.', "Path contains '..' (relative navigation not allowed)"),
]

# Reserved prim names in USD
RESERVED_NAMES = {
    'class', 'def', 'over', 'payload', 'references',
    'inherits', 'specializes', 'variantSet', 'variant',
}

# Common Physics-related prim types
PHYSICS_PRIM_TYPES = {
    'RigidBodyAPI', 'CollisionAPI', 'MassAPI',
    'ArticulationRootAPI', 'JointAPI', 'DriveAPI',
    'PhysicsScene', 'PhysicsMaterialAPI',
}


def validate_prim_path(
    path: str,
    check_reserved: bool = True
) -> Tuple[bool, str]:
    """
    Validate a USD prim path.

    Args:
        path: The prim path to validate
        check_reserved: Whether to check for reserved names

    Returns:
        Tuple of (is_valid, message)
    """
    if not path:
        return False, "Path is empty"

    # Check root path special case
    if path == "/":
        return True, "Valid root path"

    # Check for invalid patterns
    for pattern, message in INVALID_PATTERNS:
        if re.search(pattern, path):
            return False, message

    # Check overall pattern
    if not PRIM_PATH_PATTERN.match(path):
        return False, f"Invalid prim path format: '{path}'"

    # Check for reserved names
    if check_reserved:
        parts = path.strip('/').split('/')
        for part in parts:
            if part.lower() in RESERVED_NAMES:
                return False, f"Path contains reserved name: '{part}'"

    return True, "Valid prim path"


def validate_prim_hierarchy(
    paths: List[str]
) -> Tuple[bool, str, List[str]]:
    """
    Validate a hierarchy of prim paths.

    Checks that all parent paths exist for each path.

    Args:
        paths: List of prim paths

    Returns:
        Tuple of (is_valid, message, missing_parents)
    """
    path_set = set(paths)
    missing_parents = []

    for path in paths:
        if path == "/":
            continue

        # Check each parent level
        parts = path.strip('/').split('/')
        for i in range(len(parts) - 1):
            parent = '/' + '/'.join(parts[:i + 1])
            if parent not in path_set and parent not in missing_parents:
                missing_parents.append(parent)

    if missing_parents:
        return False, f"Missing parent prims: {missing_parents}", missing_parents

    return True, "All parent prims exist", []


def validate_physics_setup(
    prim_path: str,
    prim_type: str,
    attributes: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate physics configuration for a prim.

    Args:
        prim_path: The prim path
        prim_type: The prim type (e.g., 'RigidBodyAPI')
        attributes: Dictionary of attributes

    Returns:
        Tuple of (is_valid, warnings)
    """
    warnings = []

    # Validate path first
    valid, msg = validate_prim_path(prim_path)
    if not valid:
        warnings.append(f"Invalid prim path: {msg}")
        return False, warnings

    # Physics-specific validation
    if 'RigidBody' in prim_type or 'rigid_body' in str(attributes.get('APIs', [])):
        # Check for mass
        mass = attributes.get('physics:mass', attributes.get('mass'))
        if mass is None:
            warnings.append("RigidBody should have mass defined")
        elif mass <= 0:
            warnings.append(f"Invalid mass value: {mass} (must be positive)")

        # Check for collision
        if 'CollisionAPI' not in str(attributes.get('APIs', [])):
            warnings.append("RigidBody typically needs CollisionAPI")

    if 'Articulation' in prim_type:
        # Articulation-specific checks
        if not prim_path.count('/') >= 2:
            warnings.append("ArticulationRoot should be at least 2 levels deep")

    # Check for NaN or infinite values
    for key, value in attributes.items():
        if isinstance(value, (int, float)):
            if value != value:  # NaN check
                warnings.append(f"Attribute '{key}' contains NaN")
            elif abs(value) == float('inf'):
                warnings.append(f"Attribute '{key}' contains infinity")

    return len(warnings) == 0, warnings


def suggest_prim_path(
    name: str,
    parent: str = "/World",
    category: str = ""
) -> str:
    """
    Suggest a valid prim path based on inputs.

    Args:
        name: Desired prim name
        parent: Parent path
        category: Optional category (e.g., "Robot", "Sensor")

    Returns:
        Suggested valid prim path
    """
    # Clean the name
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if clean_name[0].isdigit():
        clean_name = '_' + clean_name

    # Build path
    if category:
        clean_category = re.sub(r'[^a-zA-Z0-9_]', '_', category)
        return f"{parent}/{clean_category}/{clean_name}"
    else:
        return f"{parent}/{clean_name}"


def get_validators() -> List[Dict[str, Any]]:
    """Return list of validators provided by this module."""
    return [
        {
            "name": "prim_path",
            "function": validate_prim_path,
            "description": "Validates USD prim path format and conventions"
        },
        {
            "name": "prim_hierarchy",
            "function": validate_prim_hierarchy,
            "description": "Validates that all parent prims exist in hierarchy"
        },
        {
            "name": "physics_setup",
            "function": validate_physics_setup,
            "description": "Validates physics configuration for prims"
        },
    ]


if __name__ == "__main__":
    # Test examples
    test_paths = [
        "/World/Robot/Arm",
        "/World/Robot/Joint1",
        "World/Invalid",  # Missing leading /
        "/World//Double",  # Double slash
        "/World/123Invalid",  # Starts with number
        "/World/class",  # Reserved name
        "/",  # Root
    ]

    print("USD Prim Path Validation Tests:")
    print("-" * 50)

    for path in test_paths:
        valid, msg = validate_prim_path(path)
        status = "VALID" if valid else "INVALID"
        print(f"{status}: '{path}' - {msg}")
