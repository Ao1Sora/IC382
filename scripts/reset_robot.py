#!/usr/bin/env python3
"""Stop this user's IC382 ROS stack and reset discovery; preserve map/config data."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {'robot_console.py', 'manual_drive.py', 'keyboard_drive.py', 'demo-inspect-desk.py'}
PACKAGES = {'turn_on_wheeltec_robot', 'wheeltec_nav2', 'wheeltec_slam_toolbox',
            'wheeltec_robot_keyboard', 'ic382_navigation'}
EXECUTABLES = {'wheeltec_robot_node', 'lslidar_driver_node', 'joint_state_publisher',
               'robot_state_publisher', 'static_transform_publisher', 'ekf_node',
               'controller_server', 'planner_server', 'smoother_server', 'behavior_server',
               'bt_navigator', 'waypoint_follower', 'velocity_smoother', 'map_server',
               'amcl', 'lifecycle_manager', 'async_slam_toolbox_node', 'sync_slam_toolbox_node',
               'desk_navigation', 'velocity_gate', 'journal', 'wheeltec_keyboard', 'local_alignment'}


def is_robot_command(args):
    if not args: return False
    for value in args[:3]:
        path = Path(value)
        if path.name in SCRIPTS and path.parent == ROOT/'scripts': return True
    if Path(args[0]).name == 'rviz2' and '-d' in args:
        return any(value == str(ROOT/'scripts/robot_navigation.rviz') for value in args)
    # ros2 is normally executed via /usr/bin/python3, with absolute script argv[1].
    names = [Path(value).name for value in args[:2]]
    if 'ros2' in names:
        offset = names.index('ros2')+1
        if len(args) > offset+2 and args[offset] in ('launch', 'run'):
            target = args[offset+1]
            return target in PACKAGES or target.startswith(str(ROOT/'scripts')+'/')
    executable = Path(args[0])
    if executable.name in EXECUTABLES:
        roots = (str(ROOT/'ros2_ws/install')+'/', str(Path.home()/'wheeltec_ros2/install')+'/', '/opt/ros/humble/')
        return str(executable).startswith(roots)
    return False


def snapshot():
    result = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            if entry.stat().st_uid != os.getuid(): continue
            stat = (entry/'stat').read_text().rsplit(')', 1)[1].split()
            if stat[0] == 'Z': continue
            args = [v.decode(errors='replace') for v in (entry/'cmdline').read_bytes().split(b'\0') if v]
            result[int(entry.name)] = dict(args=args, parent=int(stat[1]), birth=stat[19])
        except (OSError, ValueError, IndexError): pass
    return result


def targets():
    processes = snapshot()
    selected = {pid:info for pid,info in processes.items() if is_robot_command(info['args'])}
    # Include children (also arbitrary driver processes launched by the known launchers).
    while True:
        children = {pid:info for pid,info in processes.items() if info['parent'] in selected and pid not in selected}
        if not children: break
        selected.update(children)
    selected.pop(os.getpid(), None)
    return selected


def send(processes, sig):
    current = snapshot()
    for pid,info in processes.items():
        if pid in current and current[pid]['birth'] == info['birth']:
            try: os.kill(pid, sig)
            except ProcessLookupError: pass


def restore_repeat():
    env = os.environ.copy()
    env.setdefault('DISPLAY', ':0')
    auth = Path('/run/user')/str(os.getuid())/'gdm/Xauthority'
    if auth.exists(): env.setdefault('XAUTHORITY', str(auth))
    for command in (['x11vnc','-R','repeat'], ['x11vnc','-Q','repeat'],
                    ['xset','r','on'], ['xset','r','rate','250','20']):
        try: subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        except (OSError, subprocess.TimeoutExpired): pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='List matching processes without changing anything')
    args = parser.parse_args()
    chosen = targets()
    print('IC382 reset targets:', len(chosen), flush=True)
    for pid,info in sorted(chosen.items()): print(pid, ' '.join(info['args']), flush=True)
    if args.dry_run: return 0
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from geometry_msgs.msg import Twist
    from std_msgs.msg import Bool
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('ic382_reset')
    zero = node.create_publisher(Twist, '/cmd_vel', 10)
    deny = node.create_publisher(Bool, '/ic382/allow_motion', 10)
    def stopped_for(seconds):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            zero.publish(Twist()); deny.publish(Bool(data=False))
            rclpy.spin_once(node, timeout_sec=.05)
    try:
        stopped_for(1.)
        # Stop controllers and launchers first, while the serial driver can receive zeros.
        controllers = {pid:info for pid,info in chosen.items() if Path(info['args'][0]).name != 'wheeltec_robot_node'}
        send(controllers, signal.SIGINT)
        stopped_for(3.)
        chosen.update(targets())
        send(chosen, signal.SIGINT)
        stopped_for(2.)
        remaining = targets()
        if remaining:
            send(remaining, signal.SIGTERM)
            stopped_for(2.)
        remaining = targets()
        if remaining:
            # Only processes already identified as this robot's ROS stack are escalated.
            send(remaining, signal.SIGKILL)
            stopped_for(.5)
        # Wait for DDS endpoint removal; this probe does not use ros2 daemon's cache.
        end = time.monotonic()+8
        while time.monotonic() < end:
            stopped_for(.25)
            others = [p.node_name for p in node.get_publishers_info_by_topic('/cmd_vel') if p.node_name != node.get_name()]
            subscribers = node.count_subscribers('/cmd_vel')
            nav_publishers = node.count_publishers('/ic382/nav2_cmd_vel')
            if not others and not subscribers and not nav_publishers: break
        remaining = targets()
        report = dict(remaining_processes=remaining, cmd_vel_publishers=others,
                      cmd_vel_subscribers=subscribers, nav_publishers=nav_publishers)
    finally:
        node.destroy_node(); rclpy.try_shutdown()
    try:
        subprocess.run(['ros2','daemon','stop'], timeout=8, check=False)
    except subprocess.TimeoutExpired:
        print('Warning: ROS daemon stop timed out.', flush=True)
    restore_repeat()
    directory = Path.home()/'.local/state/ic382'
    directory.mkdir(parents=True, exist_ok=True)
    log = directory/('reset-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    log.write_text(json.dumps(report, indent=2))
    print('Report:', log, flush=True)
    if remaining or others or subscribers or nav_publishers:
        print('RESET INCOMPLETE: an endpoint/process remains; do not start a second controller.', report, flush=True)
        return 1
    print('RESET OK. Maps and scene settings preserved. Run: bash run.sh', flush=True)
    return 0


if __name__ == '__main__': raise SystemExit(main())
