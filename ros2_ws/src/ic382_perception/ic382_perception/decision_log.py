"""Append decision-log entries as JSON Lines."""
import json
from pathlib import Path


def write_entry(path, entry):
    """Append one JSON entry to the decision log, creating parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
