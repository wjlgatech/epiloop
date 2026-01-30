#!/usr/bin/env python3
"""
ROS2 Topic Type Validator for Physical AI

Validates ROS2 topic names, types, and common patterns.
"""

import re
from typing import Any, Dict, List, Tuple, Optional


# Valid ROS2 topic name pattern
# Topics must match: /namespace/topic_name or ~/relative_topic
TOPIC_NAME_PATTERN = re.compile(
    r'^(/|~)([a-zA-Z][a-zA-Z0-9_]*(/[a-zA-Z][a-zA-Z0-9_]*)*)?$'
)

# Standard ROS2 message types for common topics
STANDARD_TOPICS = {
    '/cmd_vel': 'geometry_msgs/msg/Twist',
    '/odom': 'nav_msgs/msg/Odometry',
    '/scan': 'sensor_msgs/msg/LaserScan',
    '/tf': 'tf2_msgs/msg/TFMessage',
    '/tf_static': 'tf2_msgs/msg/TFMessage',
    '/joint_states': 'sensor_msgs/msg/JointState',
    '/imu/data': 'sensor_msgs/msg/Imu',
    '/clock': 'rosgraph_msgs/msg/Clock',
    '/rosout': 'rcl_interfaces/msg/Log',
    '/parameter_events': 'rcl_interfaces/msg/ParameterEvent',
}

# Common message type patterns
MESSAGE_TYPE_PATTERN = re.compile(
    r'^[a-zA-Z][a-zA-Z0-9_]*/msg/[A-Z][a-zA-Z0-9]*$'
)

# Sensor-related topics and their expected types
SENSOR_TOPICS = {
    'image_raw': 'sensor_msgs/msg/Image',
    'image_rect': 'sensor_msgs/msg/Image',
    'camera_info': 'sensor_msgs/msg/CameraInfo',
    'depth': 'sensor_msgs/msg/Image',
    'points': 'sensor_msgs/msg/PointCloud2',
    'pointcloud': 'sensor_msgs/msg/PointCloud2',
    'imu': 'sensor_msgs/msg/Imu',
    'scan': 'sensor_msgs/msg/LaserScan',
}

# QoS profile presets
QOS_PRESETS = {
    'sensor_data': {
        'reliability': 'best_effort',
        'durability': 'volatile',
        'history': 'keep_last',
        'depth': 5,
    },
    'parameters': {
        'reliability': 'reliable',
        'durability': 'volatile',
        'history': 'keep_last',
        'depth': 1,
    },
    'services': {
        'reliability': 'reliable',
        'durability': 'volatile',
        'history': 'keep_last',
        'depth': 10,
    },
}


def validate_topic_name(
    topic: str,
    allow_private: bool = True
) -> Tuple[bool, str]:
    """
    Validate a ROS2 topic name.

    Args:
        topic: The topic name to validate
        allow_private: Whether to allow private (~) topics

    Returns:
        Tuple of (is_valid, message)
    """
    if not topic:
        return False, "Topic name is empty"

    # Check for private topic
    if topic.startswith('~') and not allow_private:
        return False, "Private topics (~) not allowed"

    # Check for invalid characters
    if re.search(r'[^a-zA-Z0-9_/~]', topic):
        return False, "Topic contains invalid characters"

    # Check for double slashes
    if '//' in topic:
        return False, "Topic contains double slashes"

    # Check pattern
    if not TOPIC_NAME_PATTERN.match(topic):
        return False, f"Invalid topic name format: '{topic}'"

    # Check for reserved namespaces
    if topic.startswith('/_'):
        return False, "Topics starting with /_ are reserved"

    return True, "Valid topic name"


def validate_message_type(
    msg_type: str
) -> Tuple[bool, str]:
    """
    Validate a ROS2 message type.

    Args:
        msg_type: The message type (e.g., 'geometry_msgs/msg/Twist')

    Returns:
        Tuple of (is_valid, message)
    """
    if not msg_type:
        return False, "Message type is empty"

    if not MESSAGE_TYPE_PATTERN.match(msg_type):
        return False, f"Invalid message type format: '{msg_type}'"

    return True, "Valid message type"


def validate_topic_type_match(
    topic: str,
    msg_type: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Validate that a topic uses the expected message type.

    Args:
        topic: The topic name
        msg_type: The message type being used

    Returns:
        Tuple of (is_valid, message, expected_type)
    """
    # Check standard topics
    if topic in STANDARD_TOPICS:
        expected = STANDARD_TOPICS[topic]
        if msg_type != expected:
            return False, f"Standard topic '{topic}' should use '{expected}'", expected

    # Check sensor topic patterns
    topic_suffix = topic.split('/')[-1]
    if topic_suffix in SENSOR_TOPICS:
        expected = SENSOR_TOPICS[topic_suffix]
        if msg_type != expected:
            return False, f"Sensor topic ending in '{topic_suffix}' typically uses '{expected}'", expected

    return True, "Topic-type match is valid", None


def validate_qos_compatibility(
    pub_qos: Dict[str, Any],
    sub_qos: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate QoS compatibility between publisher and subscriber.

    Args:
        pub_qos: Publisher QoS settings
        sub_qos: Subscriber QoS settings

    Returns:
        Tuple of (is_compatible, incompatibilities)
    """
    incompatibilities = []

    # Reliability check
    pub_rel = pub_qos.get('reliability', 'reliable')
    sub_rel = sub_qos.get('reliability', 'reliable')

    if pub_rel == 'best_effort' and sub_rel == 'reliable':
        incompatibilities.append(
            "Publisher uses best_effort but subscriber expects reliable"
        )

    # Durability check
    pub_dur = pub_qos.get('durability', 'volatile')
    sub_dur = sub_qos.get('durability', 'volatile')

    if pub_dur == 'volatile' and sub_dur == 'transient_local':
        incompatibilities.append(
            "Publisher uses volatile but subscriber expects transient_local"
        )

    # Liveliness check (if specified)
    pub_live = pub_qos.get('liveliness')
    sub_live = sub_qos.get('liveliness')

    if pub_live and sub_live:
        if pub_live == 'automatic' and sub_live == 'manual_by_topic':
            incompatibilities.append(
                "Liveliness mismatch: automatic vs manual_by_topic"
            )

    return len(incompatibilities) == 0, incompatibilities


def suggest_qos_for_topic(topic: str) -> Dict[str, Any]:
    """
    Suggest appropriate QoS settings for a topic.

    Args:
        topic: The topic name

    Returns:
        Suggested QoS settings
    """
    topic_suffix = topic.split('/')[-1]

    # Sensor data topics
    if topic_suffix in SENSOR_TOPICS or 'image' in topic or 'scan' in topic:
        return QOS_PRESETS['sensor_data'].copy()

    # Parameter/service-like topics
    if 'parameter' in topic or 'service' in topic:
        return QOS_PRESETS['parameters'].copy()

    # Default for command/state topics
    return {
        'reliability': 'reliable',
        'durability': 'volatile',
        'history': 'keep_last',
        'depth': 10,
    }


def validate_namespace(
    namespace: str
) -> Tuple[bool, str]:
    """
    Validate a ROS2 namespace.

    Args:
        namespace: The namespace to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not namespace:
        return True, "Empty namespace is valid (uses default)"

    if not namespace.startswith('/'):
        return False, "Namespace must start with '/'"

    if '//' in namespace:
        return False, "Namespace contains double slashes"

    # Check for valid characters
    parts = namespace.strip('/').split('/')
    for part in parts:
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', part):
            return False, f"Invalid namespace component: '{part}'"

    return True, "Valid namespace"


def get_validators() -> List[Dict[str, Any]]:
    """Return list of validators provided by this module."""
    return [
        {
            "name": "topic_name",
            "function": validate_topic_name,
            "description": "Validates ROS2 topic name format"
        },
        {
            "name": "message_type",
            "function": validate_message_type,
            "description": "Validates ROS2 message type format"
        },
        {
            "name": "topic_type_match",
            "function": validate_topic_type_match,
            "description": "Validates topic uses expected message type"
        },
        {
            "name": "qos_compatibility",
            "function": validate_qos_compatibility,
            "description": "Validates QoS compatibility between pub/sub"
        },
        {
            "name": "namespace",
            "function": validate_namespace,
            "description": "Validates ROS2 namespace format"
        },
    ]


if __name__ == "__main__":
    # Test examples
    test_topics = [
        "/cmd_vel",
        "/robot1/camera/image_raw",
        "~/private_topic",
        "invalid_topic",  # Missing leading /
        "/robot//double",  # Double slash
        "/_reserved",  # Reserved namespace
    ]

    print("ROS2 Topic Name Validation Tests:")
    print("-" * 50)

    for topic in test_topics:
        valid, msg = validate_topic_name(topic)
        status = "VALID" if valid else "INVALID"
        print(f"{status}: '{topic}' - {msg}")

    print("\n" + "=" * 50)
    print("Topic-Type Match Tests:")
    print("-" * 50)

    test_matches = [
        ("/cmd_vel", "geometry_msgs/msg/Twist"),
        ("/cmd_vel", "std_msgs/msg/String"),  # Wrong type
        ("/camera/image_raw", "sensor_msgs/msg/Image"),
    ]

    for topic, msg_type in test_matches:
        valid, msg, expected = validate_topic_type_match(topic, msg_type)
        status = "MATCH" if valid else "MISMATCH"
        print(f"{status}: {topic} -> {msg_type}")
        if not valid and expected:
            print(f"  Expected: {expected}")
