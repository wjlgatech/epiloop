# ROS2 Development Patterns

When working with ROS2 in Physical AI applications:

## Node Architecture

### Basic Node Structure
```python
import rclpy
from rclpy.node import Node

class MyRobotNode(Node):
    def __init__(self):
        super().__init__('my_robot_node')

        # Declare parameters
        self.declare_parameter('robot_name', 'default_robot')

        # Create publishers
        self.cmd_pub = self.create_publisher(Twist, 'cmd_vel', 10)

        # Create subscribers
        self.odom_sub = self.create_subscription(
            Odometry, 'odom', self.odom_callback, 10)

        # Create services
        self.srv = self.create_service(
            SetBool, 'enable_motor', self.enable_motor_callback)

        # Create timers
        self.timer = self.create_timer(0.1, self.control_loop)

def main():
    rclpy.init()
    node = MyRobotNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
```

## Topic Naming Conventions

### Standard Topics
| Topic | Type | Description |
|-------|------|-------------|
| `/cmd_vel` | Twist | Velocity commands |
| `/odom` | Odometry | Odometry data |
| `/scan` | LaserScan | LiDAR data |
| `/camera/image_raw` | Image | Raw camera image |
| `/camera/depth` | Image | Depth image |
| `/imu/data` | Imu | IMU readings |
| `/joint_states` | JointState | Joint positions/velocities |
| `/tf` | TFMessage | Transform tree |

### Namespacing
```bash
# Robot-specific namespace
/robot1/cmd_vel
/robot1/odom

# Sensor-specific namespace
/robot1/camera/front/image_raw
/robot1/lidar/top/points
```

## Common Error Patterns

### Topic Type Mismatch
- **Error**: `Incompatible type for topic`
- **Cause**: Publisher/subscriber using different message types
- **Solution**: Check topic type with `ros2 topic info /topic_name`

### QoS Incompatibility
- **Error**: `Subscription with incompatible QoS`
- **Cause**: Publisher and subscriber have incompatible QoS settings
- **Solution**: Match QoS profiles
```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

qos = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=10
)
```

### TF Transform Issues
- **Error**: `Could not transform`
- **Cause**: Missing or outdated transform in TF tree
- **Solution**: Ensure all transforms are published
```python
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster

# Dynamic transform
tf_broadcaster = TransformBroadcaster(self)

# Static transform
static_tf = StaticTransformBroadcaster(self)
```

### Callback Not Executing
- **Error**: Callbacks never called
- **Cause**: Not spinning the node or executor
- **Solution**: Ensure `rclpy.spin()` is called

## Launch File Patterns

### Python Launch File
```python
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('robot_name', default_value='robot1'),

        Node(
            package='my_robot',
            executable='robot_node',
            name='robot_controller',
            parameters=[{
                'robot_name': LaunchConfiguration('robot_name'),
            }],
            remappings=[
                ('/cmd_vel', '/robot1/cmd_vel'),
            ],
        ),
    ])
```

### Composable Nodes (for performance)
```python
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

container = ComposableNodeContainer(
    name='robot_container',
    namespace='',
    package='rclcpp_components',
    executable='component_container',
    composable_node_descriptions=[
        ComposableNode(
            package='my_package',
            plugin='my_package::MyNode',
            name='my_node',
        ),
    ],
)
```

## Service/Action Patterns

### Service Client
```python
from example_interfaces.srv import SetBool

client = self.create_client(SetBool, 'enable_motor')
while not client.wait_for_service(timeout_sec=1.0):
    self.get_logger().info('Service not available, waiting...')

request = SetBool.Request()
request.data = True
future = client.call_async(request)
```

### Action Server
```python
from rclpy.action import ActionServer
from nav2_msgs.action import NavigateToPose

action_server = ActionServer(
    self,
    NavigateToPose,
    'navigate_to_pose',
    execute_callback=self.navigate_callback,
    goal_callback=self.goal_callback,
    cancel_callback=self.cancel_callback,
)
```

## Isaac Sim ROS2 Bridge

### Enable ROS2 Bridge
```python
from omni.isaac.ros2_bridge import ROS2BridgeExtension

# Enable ROS2 bridge extension
ros2_bridge = ROS2BridgeExtension()
ros2_bridge.startup()
```

### Create ROS2-enabled Sensors
```python
from omni.isaac.ros2_bridge import ROS2CameraHelper

# Camera with automatic ROS2 publishing
camera_helper = ROS2CameraHelper(
    camera_prim_path="/World/Robot/Camera",
    topic_name="/camera/image_raw",
    frame_id="camera_frame"
)
```

## Best Practices

1. **Use lifecycle nodes for production**
   ```python
   from rclpy.lifecycle import LifecycleNode
   ```

2. **Handle cleanup properly**
   ```python
   def __del__(self):
       self.destroy_node()
   ```

3. **Use parameters for configuration**
   - Avoid hardcoded values
   - Support runtime parameter changes

4. **Log appropriately**
   ```python
   self.get_logger().info('Starting node')
   self.get_logger().warn('Low battery')
   self.get_logger().error('Motor failure')
   ```

5. **Use executors for concurrent callbacks**
   ```python
   from rclpy.executors import MultiThreadedExecutor
   executor = MultiThreadedExecutor()
   executor.add_node(node)
   ```
