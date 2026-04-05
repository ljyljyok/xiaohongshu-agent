#!/usr/bin/env python3
"""Run a one-off xhs-mcp publish command using params from publish_params.json."""

import json
import os
import subprocess
import sys


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    params_file = os.path.join(script_dir, "publish_params.json")
    if not os.path.exists(params_file):
        print("Missing publish params file:", params_file)
        return 1

    with open(params_file, "r", encoding="utf-8") as fh:
        params = json.load(fh)

    xhs_mcp = r"C:\Users\ljy\AppData\Roaming\npm\node_modules\xhs-mcp\dist\xhs-mcp.cjs"
    cmd = [
        "node",
        xhs_mcp,
        "publish",
        "--type",
        str(params.get("type", "image")),
        "--title",
        str(params.get("title", "")),
        "--content",
        str(params.get("content", "")),
        "--media",
        str(params.get("media", "")),
        "--tags",
        str(params.get("tags", "")),
    ]

    print("Starting publish...")
    print("CMD:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("EXIT:", result.returncode)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
