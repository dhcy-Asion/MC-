"""End-to-end check: genuine MC inventory/world -> red-side native collision."""
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.red_side import RedSide


def state():
    with urlopen("http://127.0.0.1:8766/api/state", timeout=8) as response:
        return json.load(response)


def action(path, body=None):
    req = Request("http://127.0.0.1:8767/ui/" + path,
                  data=json.dumps(body or {}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=20) as response:
        return response.read().decode()


def main():
    before = state()
    assert not before["blocks"], "Existing build retained; automatic check refused"
    assert before["inventory"].get("minecraft:oak_planks", 0) >= 1
    action("anchor")
    origin = json.loads((ROOT / "runtime/bridge-origin.json").read_text())
    red = RedSide()
    ground_before = red.ground(origin["x"], origin["y"]+5, origin["z"])
    action("place", {"block": "minecraft:oak_planks", "x": 0, "y": 0, "z": 0})
    placed = state()
    assert placed["inventory"]["minecraft:oak_planks"] == before["inventory"]["minecraft:oak_planks"] - 1
    assert len(placed["blocks"]) == 1
    time.sleep(0.8)
    ground_after = red.ground(origin["x"], origin["y"]+5, origin["z"])
    assert 0.75 < ground_after["y"]-ground_before["y"] < 1.25
    _, objects = red.request("/api/objects?offset=0&limit=500")
    owned = [o for o in objects["items"] if o.get("project") == "CrimsonMCPrototype"]
    assert len(owned) == 1, owned
    action("reconnect")
    _, reconnected = red.request("/api/objects?offset=0&limit=500")
    assert [o["uid"] for o in reconnected["items"] if o.get("project") == "CrimsonMCPrototype"] == [owned[0]["uid"]]
    action("break", {"x": 0, "y": 0, "z": 0})
    broken = state()
    assert broken["inventory"] == before["inventory"] and not broken["blocks"]
    time.sleep(0.3)
    ground_removed = red.ground(origin["x"], origin["y"]+5, origin["z"])
    assert abs(ground_removed["y"]-ground_before["y"]) < 0.15
    evidence = {"before": before, "placed": placed, "broken": broken, "origin": origin,
                "ground_before": ground_before, "ground_after": ground_after,
                "ground_removed": ground_removed, "native_object": owned[0],
                "checks": ["MC item consumed", "MC real block placed", "native collision added",
                           "reconnect reuses owned object", "MC loot returns plank", "native collision removed"]}
    (ROOT / "runtime/bridge-checks.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
