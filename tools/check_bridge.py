"""End-to-end check: genuine MC inventory/world -> red-side native collision."""
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.red_side import RedSide, GameAPIError


def state():
    with urlopen("http://127.0.0.1:8766/api/state", timeout=8) as response:
        return json.load(response)


def action(path, body=None):
    req = Request("http://127.0.0.1:8767/ui/" + path,
                  data=json.dumps(body or {}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=20) as response:
        return response.read().decode()


def check_write_preconditions(red, obj):
    """Use only this check's own block; rejected writes must leave it untouched."""
    identity = red.session_identity()
    _, status = red.request("/api/status")
    assert status.get("sessionPreconditions") is True and status.get("objectPreconditions") is True
    expected = {"expected" + key[0].upper() + key[1:]: obj[key]
                for key in ("project", "prefab", "x", "y", "z", "yaw", "pitch", "roll", "scale", "hidden")}
    path = f"/api/objects/{obj['uid']}"
    stale = {**identity, "creationTime100ns": str(int(identity["creationTime100ns"]) + 1)}
    cases = [
        ("old session delete", path, "DELETE", expected, stale, 409, "sessionMismatch"),
        ("changed project delete", path, "DELETE", {**expected, "expectedProject": "CrimsonMCUnownedCondition"}, identity, 409, "objectMismatch"),
        ("changed pose assignment", path + "/project", "POST", {**expected, "expectedX": obj["x"] + 1, "name": obj["project"]}, identity, 409, "objectMismatch"),
        ("missing condition delete", path, "DELETE", {}, identity, 400, None),
    ]
    mc_before, results = state(), []
    for label, url, method, body, session, wanted_status, flag in cases:
        try:
            red.request(url, method, body, expected_session=session)
        except GameAPIError as error:
            assert error.status == wanted_status, (label, str(error))
            if flag is not None:
                assert error.details.get(flag) is True, (label, error.details)
            if flag == "objectMismatch":
                assert error.details.get("mutationApplied") is False, (label, error.details)
            results.append({"case": label, "status": error.status, "details": error.details})
        else:
            raise AssertionError("Native precondition unexpectedly admitted: " + label)
        assert red.session_identity() == identity, "Game changed during conditional-write check"
        _, after = red.request(path)
        assert after == obj, (label, after)
        assert state() == mc_before, "Conditional native checks changed Minecraft state"
    return results


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
    preconditions = check_write_preconditions(red, owned[0])
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
                "native_precondition_checks": preconditions,
                "checks": ["MC item consumed", "MC real block placed", "native collision added",
                           "stale session and changed ownership/pose refused without effects",
                           "reconnect reuses owned object", "MC loot returns plank", "native collision removed"]}
    (ROOT / "runtime/bridge-checks.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
