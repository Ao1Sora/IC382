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
        if set(node) - {"name", "package", "executable", "enabled",
                        "arguments", "parameters"}:
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
        parameters = node.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be an object")
        for key, value in parameters.items():
            if not isinstance(key, str) or not IDENTIFIER.fullmatch(key):
                raise ValueError("Invalid parameter name")
            if isinstance(value, list):
                if not all(isinstance(item, (str, int, float, bool)) for item in value):
                    raise ValueError("Invalid parameter list value")
            elif not isinstance(value, (str, int, float, bool)):
                raise ValueError("Invalid parameter value")
    return config["nodes"]

