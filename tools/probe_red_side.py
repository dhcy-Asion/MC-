"""Measure native collision before/after a single one-metre test cube."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.red_side import RedSide

EVIDENCE = ROOT / "runtime/red-side-probe.json"
PREFAB = "/object/00_common/system/cd_testfield_grid_box_1m.prefab"


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--remove", action="store_true")
    opts = args.parse_args()
    api = RedSide()
    if opts.remove:
        evidence = json.loads(EVIDENCE.read_text())
        uid = evidence["object_uid"]
        _, obj = api.request(f"/api/objects/{uid}")
        if obj["prefab"] != PREFAB:
            raise RuntimeError("Object UID belongs to a different prefab; removal refused")
        for axis in "xyz":
            if abs(obj[axis] - evidence["position"][axis]) > 0.01:
                raise RuntimeError("Object was moved; removal refused")
        api.request(f"/api/objects/{uid}", "DELETE")
        time.sleep(0.25)
        pos = evidence["position"]
        after = api.ground(pos["x"], pos["y"] + 5, pos["z"])
        evidence["after_removal"] = after
        evidence["collision_removed"] = abs(after["y"] - evidence["before"]["y"]) < 0.15
        EVIDENCE.write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
        return
    if EVIDENCE.exists():
        old = json.loads(EVIDENCE.read_text())
        if "after_removal" not in old:
            raise RuntimeError("A test cube may still exist; inspect/remove it first")
    _, status = api.request("/api/status")
    if not status.get("ready") or not status.get("buildOk"):
        raise RuntimeError(f"Adapter is not ready: {status}")
    _, player = api.request("/api/player")
    _, camera = api.request("/api/camera")
    view = camera.get("view")
    if not view:
        raise RuntimeError("No validated view direction; placement discarded")
    x, z = player["x"] + view["x"] * 4, player["z"] + view["z"] * 4
    before = api.ground(x, player["y"] + 5, z)
    pos = {"x": x, "y": before["y"] + 0.03, "z": z}
    _, spawn = api.request("/api/objects", "POST", {"prefab": PREFAB, **pos, "scale": 1})
    evidence = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "adapter": status,
                "player": player, "camera": camera, "before": before, "position": pos,
                "object_uid": spawn["uid"], "prefab": PREFAB}
    EVIDENCE.parent.mkdir(exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2))
    # The UID denotes queue admission. Wait for the native spawn before measuring.
    time.sleep(0.8)
    after = api.ground(x, pos["y"] + 5, z)
    evidence["after_spawn"] = after
    evidence["height_delta"] = after["y"] - before["y"]
    evidence["collision_added"] = 0.75 < evidence["height_delta"] < 1.25
    try:
        _, evidence["render_camera"] = api.request("/api/prototype/render-camera")
    except RuntimeError as error:
        evidence["render_camera_error"] = str(error)
    EVIDENCE.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
