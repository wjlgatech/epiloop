# URDF (Unified Robot Description Format) Parsing

When working with URDF files for robot definitions, follow these guidelines:

## URDF Structure

```xml
<?xml version="1.0"?>
<robot name="my_robot">
  <!-- Links define rigid bodies -->
  <link name="base_link">
    <visual>...</visual>
    <collision>...</collision>
    <inertial>...</inertial>
  </link>

  <!-- Joints connect links -->
  <joint name="joint1" type="revolute">
    <parent link="base_link"/>
    <child link="link1"/>
    <origin xyz="0 0 0.1" rpy="0 0 0"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14" upper="3.14" effort="100" velocity="1.0"/>
  </joint>
</robot>
```

## Joint Types

| Type | Description | Degrees of Freedom |
|------|-------------|-------------------|
| `revolute` | Rotational with limits | 1 (rotation) |
| `continuous` | Rotational, no limits | 1 (rotation) |
| `prismatic` | Linear sliding | 1 (translation) |
| `fixed` | No movement | 0 |
| `floating` | 6-DOF free motion | 6 |
| `planar` | 2D plane motion | 3 |

## Common Error Patterns

### Missing Link Reference
- **Error**: `Link 'xyz' not found`
- **Cause**: Joint references a link that doesn't exist
- **Solution**: Ensure all parent/child links are defined before joints

### Broken Kinematic Chain
- **Error**: `Kinematic chain disconnected`
- **Cause**: Links not properly connected through joints
- **Solution**: Verify every link (except root) has exactly one parent joint

### Invalid Inertia Matrix
- **Error**: `Non-positive-definite inertia matrix`
- **Cause**: Inertia values are physically impossible
- **Solution**: Use mesh_inertia_calculator or estimate from geometry
```xml
<inertial>
  <mass value="1.0"/>
  <inertia ixx="0.01" ixy="0" ixz="0"
           iyy="0.01" iyz="0" izz="0.01"/>
</inertial>
```

### Mesh File Not Found
- **Error**: `Cannot find mesh: package://...`
- **Cause**: Package path not resolved or file missing
- **Solution**: Use absolute paths or ensure package is sourced
```xml
<mesh filename="package://my_robot/meshes/base.stl"/>
<!-- Or use file:// for absolute paths -->
<mesh filename="file:///home/user/meshes/base.stl"/>
```

## URDF to USD Conversion

### Isaac Sim URDF Importer
```python
from omni.isaac.urdf import _urdf
import omni.kit.commands

urdf_interface = _urdf.acquire_urdf_interface()

# Configure import settings
import_config = _urdf.ImportConfig()
import_config.merge_fixed_joints = True
import_config.fix_base = False
import_config.make_default_prim = True
import_config.create_physics_scene = True

# Import URDF
result = urdf_interface.parse_urdf("/path/to/robot.urdf", import_config)
```

### ROS2 Integration
```bash
# Check URDF validity
check_urdf robot.urdf

# View robot in RViz
ros2 launch urdf_tutorial display.launch.py model:=robot.urdf

# Convert URDF to SDF (Gazebo)
gz sdf -p robot.urdf > robot.sdf
```

## Best Practices

1. **Always validate URDF before using**
   ```bash
   check_urdf robot.urdf
   ```

2. **Use xacro for parameterized URDFs**
   ```xml
   <xacro:property name="wheel_radius" value="0.05"/>
   <xacro:macro name="wheel" params="prefix">
     <link name="${prefix}_wheel">...</link>
   </xacro:macro>
   ```

3. **Include collision geometry for physics**
   - Simplified collision meshes (convex hulls)
   - Primitive shapes when possible (faster)

4. **Set proper joint limits**
   - Match actual robot capabilities
   - Include effort and velocity limits

5. **Define accurate inertial properties**
   - Use CAD software to calculate
   - Or estimate from geometry and mass

## Python URDF Parsing

```python
import xml.etree.ElementTree as ET
from urdf_parser_py.urdf import URDF

# Parse URDF file
robot = URDF.from_xml_file("robot.urdf")

# Access robot properties
print(f"Robot name: {robot.name}")
print(f"Links: {[link.name for link in robot.links]}")
print(f"Joints: {[joint.name for joint in robot.joints]}")

# Get kinematic chain
chain = robot.get_chain("base_link", "end_effector")
```
