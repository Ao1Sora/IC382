import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from std_msgs.msg import String


class Events:
    def __init__(self, node, run_id):
        self.node, self.run_id, self.seq = node, run_id, 0
        self.lock = threading.Lock()
        self.pending=deque()
        self.publisher = node.create_publisher(String, '/ic382/events', 100)

    def begin(self,run_id):
        with self.lock:
            self.run_id=run_id;self.seq=0;self.pending.clear()

    def pending_age(self,acknowledged,now):
        """Age of the oldest outstanding event, not age of an idle journal."""
        with self.lock:
            while self.pending and self.pending[0][0]<=acknowledged:self.pending.popleft()
            return max(0.,now-self.pending[0][1]) if self.pending else 0.

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
        self.pending.append((self.seq,time.monotonic()))
        self.publisher.publish(msg)
        self.node.get_logger().info(event + ' ' + json.dumps(data))
