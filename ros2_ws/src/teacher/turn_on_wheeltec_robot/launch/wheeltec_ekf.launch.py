import os
from pathlib import Path
import yaml

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    pkg_dir = get_package_share_directory('turn_on_wheeltec_robot')

    ekf_config = Path(pkg_dir, 'config', 'ekf.yaml')
    ekf_carto_config = Path(pkg_dir, 'config', 'ekf_carto.yaml')
    ekf_nav_config = Path(pkg_dir, 'config', 'ekf_nav.yaml')

    carto_slam = LaunchConfiguration('carto_slam')
    robot_nav = LaunchConfiguration('robot_nav')

    carto_slam_dec = DeclareLaunchArgument('carto_slam',default_value='false')
    robot_nav_dec = DeclareLaunchArgument('robot_nav',default_value='false')
    use_imu_dec = DeclareLaunchArgument('use_imu',default_value='true')
    
    log_args = LogInfo(msg=['[ekf launch] carto_slam=', carto_slam, ', robot_nav=', robot_nav])

    def launch_ekf(context, *args, **kwargs):
        carto_slam_val = LaunchConfiguration('carto_slam').perform(context)
        robot_nav_val = LaunchConfiguration('robot_nav').perform(context)
        carto_slam_bool = carto_slam_val.lower() == 'true'
        robot_nav_bool = robot_nav_val.lower() == 'true'
        use_imu = LaunchConfiguration('use_imu').perform(context).lower() == 'true'

        nodes = []

        if carto_slam_bool:
            nodes.append(
                Node(
                    package='robot_localization',
                    executable='ekf_node',
                    name='carto_ekf_filter_node',
                    parameters=[ekf_carto_config],
                    remappings=[
                        ('/odometry/filtered', 'odom_combined')
                    ]
                )
            )

        elif robot_nav_bool:
            nodes.append(
                Node(
                    package='robot_localization',
                    executable='ekf_node',
                    name='nav_ekf_filter_node',
                    parameters=[ekf_nav_config],
                    remappings=[
                        ('/odometry/filtered', 'odom_combined')
                    ]
                )
            )

        else:
            parameters = ekf_config
            if not use_imu:
                parameters = yaml.safe_load(ekf_config.read_text())['ekf_filter_node']['ros__parameters']
                # Do not subscribe to the drifting IMU in laser-primary mode.
                parameters = {key:value for key,value in parameters.items() if not key.startswith('imu')}
                # PyYAML reads vendor scalars such as '1e-9' as strings, while
                # launch parameter dictionaries require homogeneous numeric arrays.
                for key in ('process_noise_covariance','initial_estimate_covariance'):
                    if key in parameters:
                        parameters[key] = [float(value) for value in parameters[key]]
                parameters.update(debug=False, use_control=False, odom0_differential=False)
            nodes.append(
                Node(
                    package='robot_localization',
                    executable='ekf_node',
                    name='ekf_filter_node',
                    parameters=[parameters],
                    remappings=[
                        ('/odometry/filtered', 'odom_combined')
                    ]
                )
            )

        return nodes

    return LaunchDescription([
        carto_slam_dec,
        robot_nav_dec,
        use_imu_dec,
        log_args,
        OpaqueFunction(function=launch_ekf),
    ])
