import json
import threading
from datetime import datetime, timezone
from std_msgs.msg import String


class Events:
    def __init__(self, node, run_id):
        self.node, self.run_id, self.seq = node, run_id, 0
        self.lock = threading.Lock()
        self.publisher = node.create_publisher(String, '/ic382/events', 100)

    def emit(self, event, data):
        # Nav2 feedback and the action coroutine may emit from different threads.
        with self.lock:
            return self._emit(event, data)

    def _emit(self, event, data):
        self.seq += 1
        record = {'schema_version': 1, 'run_id': self.run_id, 'source': self.node.get_name(),
                  'seq': self.seq, 'utc': datetime.now(timezone.utc).isoformat(),
                  'sim_time': self.node.get_clock().now().nanoseconds / 1e9,
                  'event': event, 'data': data}
        msg = String()
        msg.data = json.dumps(record, allow_nan=False)
        self.publisher.publish(msg)
        self.node.get_logger().info(event + ' ' + json.dumps(data))
