"""Print the RunPod network volume id for a given volume name.

Usage:
    export RUNPOD_API_KEY=...
    python -m tools.find_runpod_volume rbox
"""

from __future__ import annotations

import os
import sys

import runpod


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m tools.find_runpod_volume <volume_name>", file=sys.stderr)
        return 2
    name = sys.argv[1]
    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        print("ERROR: RUNPOD_API_KEY not set", file=sys.stderr)
        return 2
    runpod.api_key = api_key
    user = runpod.get_user()
    for v in user.get("networkVolumes") or []:
        if v["name"] == name:
            print(v["id"])
            return 0
    print(f"ERROR: no volume named {name!r} found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
