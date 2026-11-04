from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def build_nodes(context):
    config = Path(get_package_share_directory("ic382_perception")) / "config"
    raw = lambda key: LaunchConfiguration(key).perform(context).strip()

    shared = raw("config_file")
    safety_config = shared or str(config / "safety_monitor.yaml")
    classifier_config = shared or str(config / "object_classifier.yaml")
    manager_config = shared or str(config / "fair_chance_manager.yaml")

    use_sim_time = raw("use_sim_time").lower() == "true"
    common = {"use_sim_time": use_sim_time}
    for key in ("base_frame", "camera_frame", "map_frame"):
        if raw(key):
            common[key] = raw(key)
    if raw("depth_scale"):
        common["depth_scale"] = float(raw("depth_scale"))

    camera = {}
    for key in ("image_topic", "depth_topic", "camera_info_topic"):
        if raw(key):
            camera[key] = raw(key)

    safety_overrides = dict(camera)
    if raw("model_path"):
        safety_overrides["model_path"] = raw("model_path")
    if raw("model_profile"):
        safety_overrides["model_profile"] = raw("model_profile")
    if raw("fail_safe_on_stale"):
        safety_overrides["fail_safe_on_stale"] = (
            raw("fail_safe_on_stale").lower() == "true")

    classifier_overrides = dict(common)
    if raw("camera_info_topic"):
        classifier_overrides["camera_info_topic"] = raw("camera_info_topic")
    if raw("tagging_enabled"):
        classifier_overrides["tagging_enabled"] = (
            raw("tagging_enabled").lower() == "true")

    manager_overrides = dict(common)
    if raw("tagging_enabled"):
        manager_overrides["tagging_enabled"] = (
            raw("tagging_enabled").lower() == "true")
    if raw("perception_required"):
        manager_overrides["perception_required"] = (
            raw("perception_required").lower() == "true")
    if raw("spec_log_path"):
        manager_overrides["spec_log_path"] = raw("spec_log_path")

    return [
        Node(
            package="ic382_perception",
            executable="safety_monitor",
            name="safety_monitor",
            parameters=[safety_config, common, safety_overrides],
            output="screen",
        ),
        Node(
            package="ic382_perception",
            executable="object_classifier",
            name="object_classifier",
            parameters=[classifier_config, classifier_overrides],
            output="screen",
        ),
        Node(
            package="ic382_perception",
            executable="fair_chance_manager",
            name="fair_chance_manager",
            parameters=[manager_config, manager_overrides],
            output="screen",
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("config_file", default_value="",
                              description="one YAML with all three node sections"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("model_path", default_value=""),
        DeclareLaunchArgument("model_profile", default_value=""),
        DeclareLaunchArgument("tagging_enabled", default_value=""),
        DeclareLaunchArgument("perception_required", default_value=""),
        DeclareLaunchArgument("fail_safe_on_stale", default_value=""),
        DeclareLaunchArgument("image_topic", default_value=""),
        DeclareLaunchArgument("depth_topic", default_value=""),
        DeclareLaunchArgument("camera_info_topic", default_value=""),
        DeclareLaunchArgument("depth_scale", default_value=""),
        DeclareLaunchArgument("base_frame", default_value=""),
        DeclareLaunchArgument("camera_frame", default_value=""),
        DeclareLaunchArgument("map_frame", default_value=""),
        DeclareLaunchArgument("spec_log_path", default_value=""),
        OpaqueFunction(function=build_nodes),
    ])
