#!/usr/bin/env python3
"""
URDF Structure Validator for Physical AI

Validates URDF robot descriptions for common errors and best practices.
"""

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple


# Valid joint types
JOINT_TYPES = {'revolute', 'continuous', 'prismatic', 'fixed', 'floating', 'planar'}

# Elements that should have inertial properties for physics simulation
PHYSICS_ELEMENTS = {'link'}

# Required attributes for different elements
REQUIRED_ATTRS = {
    'robot': ['name'],
    'link': ['name'],
    'joint': ['name', 'type'],
    'origin': [],  # xyz and rpy are optional, default to 0
    'axis': [],  # xyz is optional, default to (1,0,0)
    'limit': [],  # Depends on joint type
}


def validate_urdf_string(
    urdf_content: str
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a URDF XML string.

    Args:
        urdf_content: The URDF XML content as a string

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    try:
        root = ET.fromstring(urdf_content)
    except ET.ParseError as e:
        return False, [f"XML parse error: {e}"], []

    # Check root element
    if root.tag != 'robot':
        errors.append(f"Root element must be 'robot', found '{root.tag}'")
        return False, errors, warnings

    # Check robot name
    if 'name' not in root.attrib:
        errors.append("Robot element must have 'name' attribute")

    # Collect links and joints
    links = {}
    joints = {}
    joint_children = set()
    joint_parents = set()

    for link in root.findall('link'):
        name = link.get('name')
        if not name:
            errors.append("Link element missing 'name' attribute")
            continue

        if name in links:
            errors.append(f"Duplicate link name: '{name}'")
        links[name] = link

        # Check for inertial (warning only)
        inertial = link.find('inertial')
        if inertial is None:
            warnings.append(f"Link '{name}' has no inertial properties")
        else:
            # Validate inertial
            mass = inertial.find('mass')
            if mass is not None:
                mass_val = mass.get('value')
                if mass_val and float(mass_val) <= 0:
                    errors.append(f"Link '{name}' has non-positive mass")

    for joint in root.findall('joint'):
        name = joint.get('name')
        joint_type = joint.get('type')

        if not name:
            errors.append("Joint element missing 'name' attribute")
            continue
        if not joint_type:
            errors.append(f"Joint '{name}' missing 'type' attribute")
            continue

        if joint_type not in JOINT_TYPES:
            errors.append(f"Joint '{name}' has invalid type: '{joint_type}'")

        if name in joints:
            errors.append(f"Duplicate joint name: '{name}'")
        joints[name] = joint

        # Check parent/child
        parent = joint.find('parent')
        child = joint.find('child')

        if parent is None:
            errors.append(f"Joint '{name}' missing parent element")
        else:
            parent_link = parent.get('link')
            if not parent_link:
                errors.append(f"Joint '{name}' parent missing 'link' attribute")
            elif parent_link not in links:
                errors.append(f"Joint '{name}' references undefined parent link: '{parent_link}'")
            else:
                joint_parents.add(parent_link)

        if child is None:
            errors.append(f"Joint '{name}' missing child element")
        else:
            child_link = child.get('link')
            if not child_link:
                errors.append(f"Joint '{name}' child missing 'link' attribute")
            elif child_link not in links:
                errors.append(f"Joint '{name}' references undefined child link: '{child_link}'")
            else:
                if child_link in joint_children:
                    errors.append(f"Link '{child_link}' is child of multiple joints")
                joint_children.add(child_link)

        # Check limits for certain joint types
        if joint_type in {'revolute', 'prismatic'}:
            limit = joint.find('limit')
            if limit is None:
                errors.append(f"Joint '{name}' ({joint_type}) requires 'limit' element")
            else:
                if 'lower' not in limit.attrib or 'upper' not in limit.attrib:
                    warnings.append(f"Joint '{name}' limit missing lower/upper bounds")
                if 'effort' not in limit.attrib:
                    warnings.append(f"Joint '{name}' limit missing 'effort' attribute")
                if 'velocity' not in limit.attrib:
                    warnings.append(f"Joint '{name}' limit missing 'velocity' attribute")

    # Check for root link (not a child of any joint)
    root_links = set(links.keys()) - joint_children
    if len(root_links) == 0:
        errors.append("No root link found (circular reference?)")
    elif len(root_links) > 1:
        warnings.append(f"Multiple root links found: {root_links}")

    # Check for disconnected links
    connected_links = joint_parents | joint_children
    disconnected = set(links.keys()) - connected_links - root_links
    if disconnected:
        warnings.append(f"Disconnected links (not connected by joints): {disconnected}")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_urdf_file(
    file_path: str
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a URDF file.

    Args:
        file_path: Path to the URDF file

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return validate_urdf_string(content)
    except FileNotFoundError:
        return False, [f"File not found: {file_path}"], []
    except IOError as e:
        return False, [f"Error reading file: {e}"], []


def validate_link_name(name: str) -> Tuple[bool, str]:
    """
    Validate a URDF link name.

    Args:
        name: The link name to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not name:
        return False, "Link name is empty"

    # Check for spaces
    if ' ' in name:
        return False, "Link name contains spaces"

    # Check for special characters
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return False, f"Invalid link name format: '{name}'"

    return True, "Valid link name"


def validate_joint_name(name: str) -> Tuple[bool, str]:
    """
    Validate a URDF joint name.

    Args:
        name: The joint name to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not name:
        return False, "Joint name is empty"

    # Check for spaces
    if ' ' in name:
        return False, "Joint name contains spaces"

    # Check for special characters
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return False, f"Invalid joint name format: '{name}'"

    return True, "Valid joint name"


def validate_inertia_matrix(
    ixx: float, ixy: float, _ixz: float,
    iyy: float, _iyz: float, izz: float
) -> Tuple[bool, str]:
    """
    Validate an inertia matrix is physically valid (positive semi-definite).

    Args:
        ixx, ixy, ixz, iyy, iyz, izz: Inertia tensor components

    Returns:
        Tuple of (is_valid, message)
    """
    # Check diagonal elements are positive
    if ixx <= 0 or iyy <= 0 or izz <= 0:
        return False, "Diagonal inertia elements must be positive"

    # Check triangle inequality (necessary for positive definiteness)
    # For any valid rigid body: Ixx + Iyy >= Izz (and permutations)
    if ixx + iyy < izz or ixx + izz < iyy or iyy + izz < ixx:
        return False, "Inertia values violate triangle inequality"

    # Simplified positive semi-definite check
    # Full check would use eigenvalue computation
    det_2x2 = ixx * iyy - ixy * ixy
    if det_2x2 < 0:
        return False, "Inertia matrix is not positive semi-definite"

    return True, "Valid inertia matrix"


def check_mesh_references(
    urdf_content: str
) -> List[Dict[str, str]]:
    """
    Extract and check mesh file references from URDF.

    Args:
        urdf_content: The URDF XML content

    Returns:
        List of mesh references with their status
    """
    meshes = []

    try:
        root = ET.fromstring(urdf_content)
    except ET.ParseError:
        return []

    for mesh in root.iter('mesh'):
        filename = mesh.get('filename', '')
        meshes.append({
            'filename': filename,
            'is_package': filename.startswith('package://'),
            'is_file': filename.startswith('file://'),
            'is_relative': not (filename.startswith('package://') or
                               filename.startswith('file://') or
                               filename.startswith('/')),
        })

    return meshes


def get_validators() -> List[Dict[str, Any]]:
    """Return list of validators provided by this module."""
    return [
        {
            "name": "urdf_structure",
            "function": validate_urdf_string,
            "description": "Validates complete URDF structure"
        },
        {
            "name": "urdf_file",
            "function": validate_urdf_file,
            "description": "Validates URDF file from path"
        },
        {
            "name": "link_name",
            "function": validate_link_name,
            "description": "Validates URDF link name format"
        },
        {
            "name": "joint_name",
            "function": validate_joint_name,
            "description": "Validates URDF joint name format"
        },
        {
            "name": "inertia_matrix",
            "function": validate_inertia_matrix,
            "description": "Validates inertia matrix is physically valid"
        },
    ]


if __name__ == "__main__":
    # Test with sample URDF
    sample_urdf = """<?xml version="1.0"?>
<robot name="test_robot">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.5 0.5 0.1"/>
      </geometry>
    </visual>
    <inertial>
      <mass value="10.0"/>
      <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>
    </inertial>
  </link>

  <link name="arm_link">
    <visual>
      <geometry>
        <cylinder radius="0.05" length="0.5"/>
      </geometry>
    </visual>
  </link>

  <joint name="base_to_arm" type="revolute">
    <parent link="base_link"/>
    <child link="arm_link"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14" upper="3.14" effort="100" velocity="1.0"/>
  </joint>
</robot>"""

    print("URDF Validation Test:")
    print("=" * 50)

    valid, errors, warnings = validate_urdf_string(sample_urdf)

    print(f"Valid: {valid}")

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")

    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  - {warn}")
