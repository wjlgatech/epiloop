# Physical AI Domain Adapter

Specialized adapter for Physical AI development workflows including Isaac Sim, ROS2, Unity XR, NVIDIA Omniverse, and robotics applications.

## Overview

This adapter provides domain-specific capabilities for developing and debugging Physical AI applications:

- **Prompts**: Best practices for USD handling, URDF parsing, sensor simulation, ROS2 patterns, and Unity XR automation
- **Validators**: Validation for USD prim paths, ROS2 topic types, and URDF structure
- **Tools**: CLI integrations for Isaac Sim, ROS2, Unity Editor, and URDF tools
- **Embeddings**: Domain-optimized embedding configuration for experience retrieval
- **Experiences**: Bootstrap experiences for common Physical AI problems

## Supported Domains

| Domain | Description |
|--------|-------------|
| `isaac_sim` | NVIDIA Isaac Sim robotics simulator |
| `ros2` | Robot Operating System 2 |
| `unity_xr` | Unity XR development (VR/AR/MR) |
| `nvidia_omniverse` | NVIDIA Omniverse platform |
| `robotics` | General robotics development |

## Installation

The adapter is included with claude-loop. To enable it:

```bash
# List available adapters
python3 lib/domain-adapter.py list

# Enable the Physical AI adapter
python3 lib/domain-adapter.py enable physical-ai

# Verify it's enabled
python3 lib/domain-adapter.py info physical-ai
```

## Capabilities

### Prompts

Domain-specific guidance located in `prompts/`:

| File | Description |
|------|-------------|
| `usd-handling.md` | USD prim paths, composition, physics setup |
| `urdf-parsing.md` | URDF structure, validation, conversion |
| `sensor-simulation.md` | Camera, LiDAR, IMU sensor setup |
| `ros2-patterns.md` | ROS2 node patterns, topics, services |
| `unity-xr-automation.md` | Unity XR setup and automation |

### Validators

Python validators in `validators/`:

| Module | Validators |
|--------|------------|
| `usd_prim_validator.py` | `prim_path`, `prim_hierarchy`, `physics_setup` |
| `ros2_topic_validator.py` | `topic_name`, `message_type`, `topic_type_match`, `qos_compatibility`, `namespace` |
| `urdf_structure_validator.py` | `urdf_structure`, `urdf_file`, `link_name`, `joint_name`, `inertia_matrix` |

Usage example:

```python
from adapters.physical_ai.validators.usd_prim_validator import validate_prim_path

valid, msg = validate_prim_path("/World/Robot/Arm")
print(f"Valid: {valid}, Message: {msg}")
```

### Tools

Tool definitions in `tools/`:

| Tool | Description |
|------|-------------|
| `isaac-sim-cli.json` | Run Isaac Sim scripts and commands |
| `ros2-commands.json` | Execute ROS2 CLI commands |
| `unity-editor-automation.json` | Automate Unity Editor operations |
| `urdf-tools.json` | URDF validation and conversion |

### Embeddings

Optimized embedding configuration in `embeddings/config.json`:

- Domain-specific prefixes for embedding isolation
- Boost patterns for common error types
- Cross-domain similarity thresholds
- Synonym mappings for domain terminology

### Bootstrap Experiences

Pre-loaded experiences in `experiences/bootstrap_experiences.json`:

15 common Physical AI problems and solutions covering:
- USD stage and prim issues
- Physics simulation stability
- ROS2 communication problems
- XR tracking issues
- URDF import errors

## Usage Examples

### Validating USD Prim Paths

```bash
python3 -c "
from adapters.physical_ai.validators.usd_prim_validator import validate_prim_path
paths = ['/World/Robot', '/invalid path', '//double/slash']
for p in paths:
    valid, msg = validate_prim_path(p)
    print(f'{p}: {msg}')
"
```

### Validating URDF Files

```bash
python3 -c "
from adapters.physical_ai.validators.urdf_structure_validator import validate_urdf_file
valid, errors, warnings = validate_urdf_file('robot.urdf')
print(f'Valid: {valid}')
for e in errors: print(f'Error: {e}')
for w in warnings: print(f'Warning: {w}')
"
```

### Checking ROS2 Topic Names

```bash
python3 -c "
from adapters.physical_ai.validators.ros2_topic_validator import validate_topic_name
topics = ['/cmd_vel', 'invalid_topic', '/robot1/camera/image_raw']
for t in topics:
    valid, msg = validate_topic_name(t)
    print(f'{t}: {msg}')
"
```

## Domain Detection

The adapter is automatically loaded when claude-loop detects a Physical AI project. Detection signals include:

- `*.usd`, `*.usda`, `*.usdc` files (USD)
- `*.urdf`, `*.xacro` files (URDF)
- `package.xml` with robotics dependencies (ROS2)
- `Assets/XR` directories (Unity XR)
- `.isaacsim` or `exts/` directories (Isaac Sim)

## Contributing

To add new capabilities to this adapter:

1. **Prompts**: Add `.md` files to `prompts/`
2. **Validators**: Add `.py` files to `validators/` with `get_validators()` function
3. **Tools**: Add `.json` tool definitions to `tools/`
4. **Experiences**: Add to `experiences/bootstrap_experiences.json`

### Validator Template

```python
def my_validator(input: str) -> Tuple[bool, str]:
    """Validate something."""
    if valid:
        return True, "Valid"
    return False, "Error message"

def get_validators():
    return [{"name": "my_validator", "function": my_validator, "description": "..."}]
```

## Requirements

- Python 3.8+
- Optional: pxr (USD), rclpy (ROS2), urdf_parser_py (URDF)

## License

Same license as claude-loop.
