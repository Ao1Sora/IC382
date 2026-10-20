"""Validate the team's executable manifest before starting any node."""
import json
import re

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_nodes(path):
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict) or set(config) != {"nodes"}:
        raise ValueError("Manifest must contain only a nodes list")
    if not isinstance(config["nodes"], list):
        raise ValueError("nodes must be a list")
    names = set()
    for node in config["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("Each node must be an object")
        if set(node) - {"name", "package", "executable", "enabled", "arguments"}:
            raise ValueError("Unknown node property")
        for key in ("name", "package", "executable"):
            if not isinstance(node.get(key), str) or not IDENTIFIER.fullmatch(node[key]):
                raise ValueError("Invalid node " + key)
        if node["name"] in names:
            raise ValueError("Duplicate node name: " + node["name"])
        names.add(node["name"])
        if type(node.get("enabled", True)) is not bool:
            raise ValueError("enabled must be boolean")
        args = node.get("arguments", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("arguments must be a list of strings")
    return config["nodes"]

