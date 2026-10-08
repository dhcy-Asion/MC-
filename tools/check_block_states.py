"""Check real MC block properties, migration, restart and rollback in an owned world.

Uses check_inventory's isolated 8768/25580 server; never calls production 8766
or Crimson Desert. Do not run concurrently with check_inventory.py.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import uuid
from urllib.error import HTTPError

from check_inventory import ROOT, PORT, IsolatedServer, call, check, delta, mutate, rejected
from build_block_registry import BLOCKS_SHA256


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block_at(state, x):
    return next((b for b in state["blocks"] if (b["x"], b["y"], b["z"]) == (x, 65, 0)), None)


def main():
    registry_path = ROOT / "build/block-registry-1.21.1/reports/blocks.json"
    check(digest(registry_path) == BLOCKS_SHA256, "Build the pinned vanilla block registry first")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    log_ids = {s["properties"]["axis"]: s["id"] for s in registry["minecraft:oak_log"]["states"]}
    directory = Path(tempfile.mkdtemp(prefix="block-state-check-", dir=ROOT / "runtime"))
    server = IsolatedServer(directory)
    evidence = {"engine": "Minecraft Java 1.21.1", "port": PORT, "world": str(directory),
                "schemaVersion": 3, "registrySha256": BLOCKS_SHA256, "checks": []}
    slots = [None] * 36
    slots[0] = {"id": "minecraft:oak_log", "count": 8}
    slots[1] = {"id": "minecraft:oak_planks", "count": 4}
    slots[2] = {"id": "minecraft:iron_sword", "count": 1,
                "components": {"minecraft:damage": 7, "minecraft:custom_name": '"朝向测试剑"'}}
    legacy = {"schemaVersion": 1, "selectedSlot": 2, "revision": 71, "slots": slots,
              "touched": [{"x": -2, "y": 65, "z": 0, "block": "minecraft:oak_log"},
                          {"x": -1, "y": 65, "z": 0, "block": "minecraft:air"}]}
    server.write_snapshot(legacy)
    try:
        initial = server.start()
        saved = json.loads(server.state_file.read_text(encoding="utf-8"))
        check(saved["schemaVersion"] == 3 and saved["selectedSlot"] == 2 and saved["revision"] == 71,
              "Schema 1 migration lost selection/revision")
        check(saved["slots"] == slots, "Migration changed inventory/components")
        check(saved["touched"] == [{**legacy["touched"][0], "properties": {"axis": "y"}},
                                   {**legacy["touched"][1], "properties": {}}], "Legacy defaults/tombstone lost")
        check(block_at(initial, -2)["properties"] == {"axis": "y"}
              and block_at(initial, -2)["stateId"] == log_ids["y"] and block_at(initial, -1) is None,
              "Migration did not reconcile actual Minecraft world states")
        evidence["checks"].append("Schema 1 migrates full default properties and air tombstones, preserving slots/components/revision/selection")

        before = call()
        body = {"operationId": str(uuid.uuid4()), "block": "minecraft:oak_log", "x": 0, "y": 65,
                "z": 0, "properties": {"axis": "x"}}
        placed = call("place", body)
        delta(before, placed, {"minecraft:oak_log": -1})
        check(call("place", dict(reversed(list(body.items())))) == placed, "Property placement retry consumed twice")
        rejected("place", **{**body, "properties": {"axis": "z"}})
        mutate("select", slot=0)
        mutate("place-selected", x=1, y=65, z=0, properties={"axis": "z"})
        mutate("place-selected", x=2, y=65, z=0)
        current = call()
        for x, axis in ((0, "x"), (1, "z"), (2, "y")):
            check(block_at(current, x)["properties"] == {"axis": axis}
                  and block_at(current, x)["stateId"] == log_ids[axis], "Actual MC state differs from vanilla registry")
        evidence["checks"].append("Both placement routes use real MC x/y/z log states; omitted properties use default; retry/conflicting state obey receipts")

        main_hash = digest(server.state_file)
        for properties in (None, [], 1, True, {"axis": 1}, {"axis": None}, {"axis": "north"},
                           {"axis": "X"}, {"facing": "north"}, {"axis": "x", "unknown": "z"}):
            rejected("place-selected", x=3, y=65, z=0, properties=properties)
        rejected("place", block="minecraft:oak_planks", x=3, y=65, z=0, properties={"axis": "x"})
        check(digest(server.state_file) == main_hash, "Rejected properties changed disk snapshot")
        evidence["checks"].append("Malformed/unknown/domain-invalid properties reject without changing actual world, inventory, revision or disk")

        # A real failed atomic snapshot write must undo world changes, not just its journal.
        temporary = server.state_file.with_name(server.state_file.name + ".tmp")
        check(not temporary.exists(), "Unexpected pre-existing temporary snapshot")
        temporary.mkdir()
        try:
            for path, args in (("place-selected", {"x": 3, "y": 65, "z": 0, "properties": {"axis": "x"}}),
                               ("break", {"x": 0, "y": 65, "z": 0})):
                before_failure = call()
                try:
                    mutate(path, **args)
                except HTTPError as error:
                    check(error.code == 503, "Storage failure must report 503")
                else:
                    raise AssertionError("Storage failure unexpectedly committed")
                check(call() == before_failure, "Storage failure failed to restore exact real-world block states")
                check(digest(server.state_file) == main_hash, "Storage failure changed main snapshot")
        finally:
            temporary.rmdir()
        # A new successful placement in that cell also proves the failed placement left actual air.
        mutate("place-selected", x=3, y=65, z=0, properties={"axis": "x"})
        before_break = call()
        broken = mutate("break", x=3, y=65, z=0)
        delta(before_break, broken, {"minecraft:oak_log": 1})
        check(block_at(broken, 3) is None, "Break retained an actual non-air block")
        evidence["checks"].append("Failed place/break storage writes restore real x/z orientation and materials; failed placement leaves reusable air; real drops work")

        before_restart = call()
        server.stop()
        after_restart = server.start()
        check(after_restart == before_restart, "Normal restart lost exact actual states/IDs/inventory/revision")
        saved = json.loads(server.state_file.read_text(encoding="utf-8"))
        check(all("stateId" not in cell and "properties" in cell for cell in saved["touched"]),
              "Disk must store portable full properties, never raw state IDs")
        check(saved["slots"][2] == slots[2], "Restart lost item components")
        evidence["checks"].append("Normal restart restores exact full properties and vanilla state IDs; disk stores no raw state IDs; item components remain intact")
        server.stop()

        # Simulate journal newer than chunk: the chunk still has x-axis log at 0.
        tombstone = deepcopy(saved)
        cell = next(c for c in tombstone["touched"] if c["x"] == 0)
        cell.update(block="minecraft:air", properties={})
        server.write_snapshot(tombstone)
        repaired = server.start()
        check(block_at(repaired, 0) is None and block_at(repaired, 1)["properties"] == {"axis": "z"},
              "Air tombstone failed to repair stale real chunk without losing neighbor orientation")
        mutate("place-selected", x=0, y=65, z=0, properties={"axis": "z"})
        check(block_at(call(), 0)["stateId"] == log_ids["z"], "Tombstone did not leave actual placeable air")
        server.stop()
        evidence["checks"].append("An air journal tombstone clears stale saved chunk geometry and preserves neighboring states")

        # Startup validates the entire snapshot before enabling HTTP or rewriting it.
        for properties, message in ((None, "properties must be an object"),
                                    ({}, "saved block properties must be complete"),
                                    ({"axis": "wrong"}, "invalid block property axis")):
            corrupt = deepcopy(saved)
            corrupt["touched"][0]["properties"] = properties
            server.write_snapshot(corrupt)
            corrupt_hash = digest(server.state_file)
            server.start(expected_failure=message)
            check(digest(server.state_file) == corrupt_hash, "Invalid schema 2 file was overwritten")
            server.stop(authority=False)
        evidence["checks"].append("Incomplete/malformed/invalid schema 2 saved properties disable authority and preserve original bytes")
        evidence["result"] = "passed"
    except Exception as error:
        evidence.update(result="failed", error=str(error))
        raise
    finally:
        server.stop()
        evidence["forcedOwnTestProcessStop"] = server.forced_stop
        (ROOT / "runtime/block-state-checks.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    main()
