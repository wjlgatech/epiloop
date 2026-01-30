# Changelog

All notable changes to the Physical AI adapter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-12

### Added

- Initial release of the Physical AI domain adapter

#### Prompts
- `usd-handling.md` - USD prim path conventions, composition arcs, physics setup
- `urdf-parsing.md` - URDF structure, joint types, validation, conversion
- `sensor-simulation.md` - Camera, LiDAR, IMU setup for Isaac Sim and ROS2
- `ros2-patterns.md` - Node architecture, topics, services, launch files
- `unity-xr-automation.md` - Unity XR setup, OpenXR configuration, testing

#### Validators
- `usd_prim_validator.py`
  - `validate_prim_path()` - Validates USD prim path format
  - `validate_prim_hierarchy()` - Checks all parent prims exist
  - `validate_physics_setup()` - Validates physics configuration
- `ros2_topic_validator.py`
  - `validate_topic_name()` - Validates ROS2 topic name format
  - `validate_message_type()` - Validates ROS2 message type format
  - `validate_topic_type_match()` - Checks topic uses expected type
  - `validate_qos_compatibility()` - Checks QoS compatibility
  - `validate_namespace()` - Validates ROS2 namespace format
- `urdf_structure_validator.py`
  - `validate_urdf_string()` - Full URDF structure validation
  - `validate_urdf_file()` - File-based URDF validation
  - `validate_link_name()` - Link name format validation
  - `validate_joint_name()` - Joint name format validation
  - `validate_inertia_matrix()` - Physical validity of inertia

#### Tools
- `isaac-sim-cli.json` - Isaac Sim command execution
- `ros2-commands.json` - ROS2 CLI operations
- `unity-editor-automation.json` - Unity Editor batch operations
- `urdf-tools.json` - URDF validation and conversion

#### Embeddings
- Domain-specific prefixes for each Physical AI domain
- Boost patterns for common error types
- Synonym mappings for domain terminology
- Cross-domain similarity thresholds

#### Experiences
- 15 bootstrap experiences covering:
  - USD prim and stage issues
  - Physics simulation stability
  - ROS2 topic/TF/service problems
  - URDF import and validation
  - Unity XR tracking and input
  - Sensor configuration issues
  - Gripper and manipulation

### Domains Supported
- `isaac_sim` - NVIDIA Isaac Sim
- `ros2` - Robot Operating System 2
- `unity_xr` - Unity XR (VR/AR/MR)
- `nvidia_omniverse` - NVIDIA Omniverse
- `robotics` - General robotics
