"""ROS-independent checks; invalid RTX returns (-1) must not pass."""
import math


def has_valid_range(values, minimum, maximum):
    return any(math.isfinite(value) and value > 0 and minimum <= value <= maximum
               for value in values)


def healthy(counts, first_clock, last_clock, valid_scans, cmd_subscribers):
    return (all(counts.get(topic, 0) >= 3 for topic in ("clock", "odom", "scan"))
            and first_clock is not None and last_clock > first_clock
            and valid_scans >= 3 and cmd_subscribers > 0)

