# Sensor Simulation in Physical AI

When working with simulated sensors in Isaac Sim, Omniverse, and ROS2:

## Common Sensor Types

### Camera Sensors

#### RGB Camera
```python
from omni.isaac.sensor import Camera

# Create camera
camera = Camera(
    prim_path="/World/Robot/Camera",
    resolution=(1280, 720),
    frequency=30
)

# Initialize sensor
camera.initialize()

# Get RGB data
rgb = camera.get_rgba()  # Returns numpy array (H, W, 4)
```

#### Depth Camera
```python
# Get depth data (in meters)
depth = camera.get_depth()  # Returns numpy array (H, W)

# Get point cloud
points = camera.get_pointcloud()  # Returns (N, 3) array
```

#### Segmentation
```python
# Instance segmentation
instance_seg = camera.get_instance_segmentation()

# Semantic segmentation
semantic_seg = camera.get_semantic_segmentation()
```

### LiDAR Sensors

```python
from omni.isaac.sensor import LidarRtx

lidar = LidarRtx(
    prim_path="/World/Robot/Lidar",
    rotation_frequency=10,
    horizontal_fov=360,
    vertical_fov=30,
    horizontal_resolution=0.2,
    vertical_resolution=0.2,
    max_range=100.0
)

# Get point cloud data
point_cloud = lidar.get_pointcloud()  # (N, 3) xyz points
intensities = lidar.get_intensities()  # (N,) intensity values
```

### IMU Sensors

```python
from omni.isaac.sensor import IMUSensor

imu = IMUSensor(
    prim_path="/World/Robot/IMU",
    frequency=100
)

# Get IMU readings
linear_acceleration = imu.get_linear_acceleration()  # (3,) m/s^2
angular_velocity = imu.get_angular_velocity()  # (3,) rad/s
orientation = imu.get_orientation()  # (4,) quaternion wxyz
```

### Contact Sensors

```python
from omni.isaac.sensor import ContactSensor

contact = ContactSensor(
    prim_path="/World/Robot/Gripper/Contact",
    radius=0.01,
    min_threshold=0,
    max_threshold=1000000
)

# Get contact forces
forces = contact.get_current_frame()
is_touching = forces["in_contact"]
contact_force = forces["force"]
```

## ROS2 Sensor Integration

### Camera to ROS2
```python
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import rclpy

# Publish camera data to ROS2
def publish_camera(camera_data):
    bridge = CvBridge()
    img_msg = bridge.cv2_to_imgmsg(camera_data, encoding="rgb8")
    img_msg.header.stamp = node.get_clock().now().to_msg()
    img_msg.header.frame_id = "camera_frame"
    pub.publish(img_msg)
```

### LiDAR to ROS2
```python
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2

def publish_pointcloud(points):
    header = Header()
    header.stamp = node.get_clock().now().to_msg()
    header.frame_id = "lidar_frame"

    cloud_msg = pc2.create_cloud_xyz32(header, points)
    pub.publish(cloud_msg)
```

### IMU to ROS2
```python
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Quaternion, Vector3

def publish_imu(accel, gyro, orientation):
    msg = Imu()
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.header.frame_id = "imu_frame"

    msg.linear_acceleration = Vector3(x=accel[0], y=accel[1], z=accel[2])
    msg.angular_velocity = Vector3(x=gyro[0], y=gyro[1], z=gyro[2])
    msg.orientation = Quaternion(x=orientation[1], y=orientation[2],
                                  z=orientation[3], w=orientation[0])
    pub.publish(msg)
```

## Common Error Patterns

### Frame Rate Issues
- **Error**: Sensor data timestamps are irregular
- **Cause**: Simulation frame rate doesn't match sensor frequency
- **Solution**: Use fixed time stepping
```python
from omni.isaac.core import World
world = World(physics_dt=1/60, rendering_dt=1/60)
```

### Coordinate Frame Mismatch
- **Error**: Sensor data appears rotated or flipped
- **Cause**: Different coordinate conventions (ROS vs USD)
- **Solution**: Apply proper transforms
```python
# USD uses Y-up, ROS uses Z-up
# Convert: swap Y and Z, negate new Y
ros_point = [usd_point[0], -usd_point[2], usd_point[1]]
```

### Missing Sensor Data
- **Error**: `None` or empty arrays returned
- **Cause**: Sensor not properly initialized or not stepped
- **Solution**: Ensure sensor.initialize() is called and simulation stepped

### Noise Configuration
- **Error**: Sensor data is too clean/unrealistic
- **Cause**: No noise models applied
- **Solution**: Add appropriate noise
```python
camera.add_noise(
    noise_type="gaussian",
    mean=0,
    std=0.01
)
```

## Best Practices

1. **Match sensor specs to real hardware**
   - Resolution, FOV, noise characteristics
   - Update rates and latency

2. **Use appropriate coordinate frames**
   - Define sensor frames in URDF/USD
   - Publish TF transforms for ROS integration

3. **Apply realistic noise models**
   - Gaussian noise for most sensors
   - Salt-and-pepper for depth sensors
   - IMU bias and drift models

4. **Synchronize sensor data**
   - Use consistent timestamps
   - Consider time synchronization protocols

5. **Validate sensor output**
   - Compare with real sensor data when available
   - Use visualization tools (RViz, Rerun, etc.)
