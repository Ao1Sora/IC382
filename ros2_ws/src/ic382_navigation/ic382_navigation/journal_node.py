"""Persist mission events before acknowledging them; never treat stubs as real results."""
import json
import os
from pathlib import Path
import re
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from std_msgs.msg import Bool, String


class Journal(Node):
    def __init__(self):
        super().__init__('mission_journal')
        folder = self.declare_parameter('log_directory', '~/.local/state/ic382/missions').value
        self.folder = Path(folder).expanduser()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.ok = True
        self.files = {}
        self.ready = self.create_publisher(Bool, '/ic382/logger_ready', 10)
        self.ack = self.create_publisher(String, '/ic382/log_ack', 100)
        self.create_subscription(String, '/ic382/events', self.record, 100)
        self.create_timer(0.5, self.heartbeat, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def heartbeat(self):
        self.ready.publish(Bool(data=self.ok))

    def record(self, msg):
        try:
            entry = json.loads(msg.data)
            run = entry['run_id']
            if not isinstance(run, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run):
                raise ValueError('Invalid run_id')
            if run not in self.files:
                self.files[run] = (self.folder / (run + '.jsonl')).open('a', encoding='utf-8')
            f = self.files[run]
            f.write(json.dumps(entry, allow_nan=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
            self.ack.publish(String(data=json.dumps({k: entry[k] for k in ('run_id', 'source', 'seq')})))
        except (KeyError, ValueError, OSError, TypeError) as exc:
            self.ok = False
            self.heartbeat()
            self.get_logger().error('Journal failure: ' + str(exc))

    def destroy_node(self):
        for f in self.files.values():
            f.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Journal()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
