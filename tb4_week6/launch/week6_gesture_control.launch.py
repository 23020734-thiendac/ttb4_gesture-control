"""Launch Small House simulation and Week 6 gesture control nodes."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    week6_share = get_package_share_directory('tb4_week6')
    week5_share = get_package_share_directory('tb4_week5')
    sim_launch = PathJoinSubstitution([
        week5_share, 'launch', 'small_house_sim.launch.py'])
    default_model = str(Path(week6_share) / 'models' / 'gesture_recognizer.task')
    rviz_config = PathJoinSubstitution([
        week6_share, 'rviz', 'gesture_control.rviz'])

    # Resolve the repository root when the package is built with
    # --symlink-install. This keeps the GitHub copy portable instead of
    # depending on one developer's absolute home path.
    repository_root = Path(__file__).resolve().parents[2]
    world_root = repository_root / 'aws-robomaker-small-house-world'
    if not world_root.is_dir():
        world_root = Path(
            '/home/thiendac/ros2_ws/src/TuongTacNguoi_Robot/'
            'aws-robomaker-small-house-world')

    return LaunchDescription([
        DeclareLaunchArgument('ros_domain_id', default_value='68'),
        DeclareLaunchArgument('model', default_value='standard'),
        DeclareLaunchArgument('world', default_value='warehouse'),
        DeclareLaunchArgument(
            'world_file',
            default_value=str(world_root / 'worlds' / 'small_house.world')),
        DeclareLaunchArgument(
            'models_path',
            default_value=str(world_root / 'models')),
        DeclareLaunchArgument(
            'world_path',
            default_value=str(world_root / 'worlds')),
        # Start in the open central kitchen floor, away from the original
        # dock/spawn area. The map check shows a clear buffer around this pose.
        DeclareLaunchArgument('x', default_value='5.5'),
        DeclareLaunchArgument('y', default_value='-1.8'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument(
            'week6_rviz',
            default_value='true',
            choices=['true', 'false'],
            description='Start the Week 6 RViz view after the simulation is ready.'),
        DeclareLaunchArgument(
            'rviz_delay_sec',
            default_value='26.0',
            description=(
                'Wait for Gazebo, robot_description and TF before starting RViz.')),
        DeclareLaunchArgument(
            'remove_dock',
            default_value='true',
            choices=['true', 'false'],
            description='Remove the stock charging dock model in Week 6.'),
        DeclareLaunchArgument(
            'dock_remove_delay_sec',
            default_value='24.0',
            description=(
                'Wait until the robot/world are spawned before removing the dock.')),
        DeclareLaunchArgument('run_sim', default_value='true'),
        DeclareLaunchArgument('camera_index', default_value='0'),
        DeclareLaunchArgument('model_path', default_value=default_model),
        DeclareLaunchArgument('show_window', default_value='true'),
        DeclareLaunchArgument('min_confidence', default_value='0.70'),
        DeclareLaunchArgument('publish_hz', default_value='20.0'),
        DeclareLaunchArgument('stable_frames', default_value='3'),
        DeclareLaunchArgument('camera_width', default_value='640'),
        DeclareLaunchArgument('camera_height', default_value='480'),
        DeclareLaunchArgument('show_landmarks', default_value='true'),
        DeclareLaunchArgument('confirmation_timeout_sec', default_value='5.0'),
        DeclareLaunchArgument('straight_segment_sec', default_value='3.00'),
        DeclareLaunchArgument('wave_repetitions', default_value='3'),
        DeclareLaunchArgument(
            'wave_segment_sec',
            default_value='0.90',
            description='Duration of each wider left/right salute phase.'),
        DeclareLaunchArgument('circle_turns', default_value='1.0'),
        DeclareLaunchArgument('odom_topic', default_value='/odom'),
        DeclareLaunchArgument(
            'circle_timeout_sec',
            default_value='60.0',
            description=(
                'Safety timeout; the circle ends earlier only after odometry '
                'confirms 2*pi radians.')),
        DeclareLaunchArgument(
            'circle_timeout_grace_sec',
            default_value='45.0',
            description=(
                'One bounded extension when odometry already passed 75% of '
                'the circle.')),
        DeclareLaunchArgument(
            'figure_eight_timeout_sec',
            default_value='70.0',
            description=(
                'Safety timeout for each odometry-verified 360-degree loop.')),
        DeclareLaunchArgument(
            'figure_eight_timeout_grace_sec',
            default_value='45.0',
            description=(
                'One bounded extension for a figure-eight loop already '
                'past 75 percent.')),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(sim_launch),
            condition=IfCondition(LaunchConfiguration('run_sim')),
            launch_arguments={
                'ros_domain_id': LaunchConfiguration('ros_domain_id'),
                'model': LaunchConfiguration('model'),
                'world_file': LaunchConfiguration('world_file'),
                'models_path': LaunchConfiguration('models_path'),
                'world_path': LaunchConfiguration('world_path'),
                'bridge_world_name': LaunchConfiguration('world'),
                'x': LaunchConfiguration('x'),
                'y': LaunchConfiguration('y'),
                'z': LaunchConfiguration('z'),
                'yaw': LaunchConfiguration('yaw'),
                # The stock TurtleBot 4 RViz config is for AMCL/Nav2 and uses
                # map as fixed frame. Week 6 has no map or Nav2, so start the
                # dedicated RViz config below instead.
                'rviz': 'false',
                # Let Gazebo finish loading the small-house world before the
                # robot and its controller spawners are started.
                'spawn_delay_sec': '14.0',
            }.items()),
        # The stock TurtleBot 4 spawn launch also inserts standard_dock.
        # Week 6 does not use docking, so remove only that Gazebo model after
        # the world and robot have finished spawning. Retry because the
        # remove service may appear a little later than Gazebo itself.
        TimerAction(
            period=LaunchConfiguration('dock_remove_delay_sec'),
            condition=IfCondition(LaunchConfiguration('run_sim')),
            actions=[ExecuteProcess(
                cmd=[
                    'bash', '-lc',
                    (
                        'world_name="$1"; '
                        'for attempt in $(seq 1 20); do '
                        'if ign service '
                        '-s "/world/${world_name}/remove" '
                        '--reqtype ignition.msgs.Entity '
                        '--reptype ignition.msgs.Boolean '
                        '--timeout 1000 '
                        '--req \'name: "standard_dock" type: MODEL\' '
                        '> /tmp/tb4_week6_remove_dock.log 2>&1; then '
                        'echo "[tb4_week6] Da xoa dock sac standard_dock."; '
                        'exit 0; fi; '
                        'sleep 1; '
                        'done; '
                        'echo "[tb4_week6] Canh bao: khong xoa duoc dock '
                        'sac; xem /tmp/tb4_week6_remove_dock.log."; '
                        'exit 1'
                    ),
                    'remove_dock',
                    LaunchConfiguration('world'),
                ],
                output='screen',
                condition=IfCondition(LaunchConfiguration('remove_dock')),
            )],
        ),
        TimerAction(
            period=LaunchConfiguration('rviz_delay_sec'),
            actions=[
                Node(
                    package='rviz2',
                    executable='rviz2',
                    name='rviz2_week6',
                    output='screen',
                    arguments=[
                        '-d', rviz_config,
                        '--ros-args', '-p', 'use_sim_time:=true',
                    ],
                    condition=IfCondition(LaunchConfiguration('week6_rviz')),
                ),
            ],
        ),
        Node(
            package='tb4_week6',
            executable='gesture_recognition_node',
            name='gesture_recognition_node',
            output='screen',
            parameters=[{
                'camera_index': ParameterValue(
                    LaunchConfiguration('camera_index'), value_type=int),
                'model_path': LaunchConfiguration('model_path'),
                'show_window': LaunchConfiguration('show_window'),
                'min_confidence': ParameterValue(
                    LaunchConfiguration('min_confidence'), value_type=float),
                'publish_hz': ParameterValue(
                    LaunchConfiguration('publish_hz'), value_type=float),
                'stable_frames': ParameterValue(
                    LaunchConfiguration('stable_frames'), value_type=int),
                'camera_width': ParameterValue(
                    LaunchConfiguration('camera_width'), value_type=int),
                'camera_height': ParameterValue(
                    LaunchConfiguration('camera_height'), value_type=int),
                'show_landmarks': ParameterValue(
                    LaunchConfiguration('show_landmarks'), value_type=bool),
            }]),
        Node(
            package='tb4_week6',
            executable='robot_behavior_node',
            name='robot_behavior_node',
            output='screen',
            parameters=[{
                'confirmation_timeout_sec': ParameterValue(
                    LaunchConfiguration('confirmation_timeout_sec'),
                    value_type=float),
                'straight_segment_sec': ParameterValue(
                    LaunchConfiguration('straight_segment_sec'),
                    value_type=float),
                'wave_repetitions': ParameterValue(
                    LaunchConfiguration('wave_repetitions'),
                    value_type=int),
                'wave_segment_sec': ParameterValue(
                    LaunchConfiguration('wave_segment_sec'),
                    value_type=float),
                'circle_turns': ParameterValue(
                    LaunchConfiguration('circle_turns'), value_type=float),
                'odom_topic': LaunchConfiguration('odom_topic'),
                'circle_timeout_sec': ParameterValue(
                    LaunchConfiguration('circle_timeout_sec'),
                    value_type=float),
                'circle_timeout_grace_sec': ParameterValue(
                    LaunchConfiguration('circle_timeout_grace_sec'),
                    value_type=float),
                'figure_eight_timeout_sec': ParameterValue(
                    LaunchConfiguration('figure_eight_timeout_sec'),
                    value_type=float),
                'figure_eight_timeout_grace_sec': ParameterValue(
                    LaunchConfiguration('figure_eight_timeout_grace_sec'),
                    value_type=float),
            }]),
    ])
