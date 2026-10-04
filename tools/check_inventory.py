"""Real MC inventory integration checks in an owned, isolated world on port 8768.

This script starts its own Fabric dev server and never sends requests to 8766.
The test run directory/logs remain under ignored runtime/inventory-check-*.
Normal shutdown is used; only a failed test's own process tree may be force-stopped.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORT = 8768
GAME_PORT = 25580
BASE = f"http://127.0.0.1:{PORT}/api/"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def call(path="state", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def mutate(path, **body):
    return call(path, {"operationId": str(uuid.uuid4()), **body})


def rejected(path, **body):
    before = call()
    try:
        mutate(path, **body)
    except HTTPError as error:
        check(error.code == 400, f"{path} should reject with 400, got {error.code}")
        message = json.load(error).get("error", "")
    else:
        raise AssertionError(f"{path} accepted an invalid operation")
    check(call() == before, f"{path} rejection changed inventory, selection, blocks or revision")
    return message


def delta(before, after, expected):
    ids = set(before["inventory"]) | set(after["inventory"])
    actual = {item: after["inventory"].get(item, 0) - before["inventory"].get(item, 0) for item in ids}
    check({item: count for item, count in actual.items() if count} == expected, "Vanilla inventory change is incorrect")


def slot_for(state, item):
    return next(s["slot"] for s in state["slots"] if s.get("id") == item)


def port_free(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"Test port {port} is already in use; existing services are left alone") from error


class IsolatedServer:
    def __init__(self, directory):
        self.directory = directory.resolve()
        check(self.directory.parent == (ROOT / "runtime").resolve(), "Test directory must be an owned runtime child")
        self.process = None
        self.log_file = None
        self.run_count = 0
        self.forced_stop = False
        self.state_file = self.directory / "crimsonmc-lab" / "crimsonmc-state.json"
        self.state_file.parent.mkdir()
        properties = (ROOT / "config/minecraft-server.properties").read_text(encoding="utf-8")
        properties = properties.replace("server-port=25579", f"server-port={GAME_PORT}")
        (self.directory / "server.properties").write_text(properties, encoding="utf-8")
        # The prototype's Minecraft EULA acceptance is already required by its setup.
        original_eula = ROOT / "runtime/minecraft-server/eula.txt"
        if not original_eula.exists() or "eula=true" not in original_eula.read_text(encoding="utf-8").lower():
            raise RuntimeError("Prepare the prototype and accept the Minecraft EULA before running this check")
        (self.directory / "eula.txt").write_text("eula=true\n", encoding="utf-8")
        self.init_script = self.directory / "isolated-run.gradle"
        self.init_script.write_text("""allprojects { project ->
    project.afterEvaluate {
        def run = project.extensions.getByName('loom').runs.getByName('server')
        run.runDir(System.getenv('CRIMSONMC_INVENTORY_TEST_DIR'))
        run.vmArgs.removeAll { it.startsWith('-Dcrimsonmc.port=') }
        run.vmArg('-Dcrimsonmc.port=8768')
        project.tasks.named('runServer') { standardInput = System.in }
    }
}
""", encoding="utf-8")

    def write_snapshot(self, data):
        check(self.process is None, "Stop the owned test server before changing a test fixture")
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def start(self, expected_failure=None):
        port_free(PORT)
        port_free(GAME_PORT)
        self.run_count += 1
        self.log_path = self.directory / f"server-{self.run_count}.log"
        self.log_file = self.log_path.open("wb")
        jdks = sorted((ROOT / "downloads/jdk21").glob("*/bin/java.exe"))
        gradle = ROOT / "downloads/gradle/gradle-8.10.2/bin/gradle.bat"
        if not jdks or not gradle.exists():
            raise RuntimeError("Run tools/prepare_environment.ps1 first; portable Java/Gradle are missing")
        env = os.environ.copy()
        env["JAVA_HOME"] = str(jdks[0].parents[1])
        env["GRADLE_USER_HOME"] = str(Path.home() / ".gradle-crimsonmc")
        # Loom resolves runDir relative to minecraft/projectDir at execution time.
        env["CRIMSONMC_INVENTORY_TEST_DIR"] = os.path.relpath(self.directory, ROOT / "minecraft").replace("\\", "/")
        args = [str(gradle), "--no-daemon", "--no-watch-fs", "--console=plain",
                "-Dorg.gradle.internal.instrumentation.agent=false", "--init-script", str(self.init_script), "runServer"]
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *args] if os.name == "nt" else args
        self.process = subprocess.Popen(command, cwd=ROOT / "minecraft", env=env, stdin=subprocess.PIPE,
                                        stdout=self.log_file, stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            log = self.log_path.read_text(encoding="utf-8", errors="replace")
            if expected_failure and expected_failure in log:
                try:
                    call()
                except (URLError, OSError):
                    return None
                raise AssertionError("Invalid inventory format unexpectedly enabled the authority API")
            if self.process.poll() is not None:
                raise RuntimeError(f"Isolated server exited; see {self.log_path}")
            if not expected_failure and f"loopback HTTP port {PORT}" in log:
                try:
                    state = call()
                except (URLError, OSError, ValueError):
                    pass
                else:
                    check(state.get("engine") == "Minecraft Java 1.21.1", "Wrong server on test port")
                    return state
            time.sleep(0.5)
        raise TimeoutError(f"Isolated server did not reach expected state; see {self.log_path}")

    def stop(self, authority=True):
        process = self.process
        if process is None:
            return
        try:
            if authority and process.poll() is None:
                call("shutdown", {})
            elif process.poll() is None and process.stdin:
                process.stdin.write(b"stop\n")
                process.stdin.flush()
            process.wait(timeout=45)
        except (URLError, OSError, subprocess.TimeoutExpired):
            # This PID was started above by this object. Never kill any pre-existing MC/game process.
            self.forced_stop = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                process.kill()
            process.wait(timeout=15)
        finally:
            if process.stdin:
                process.stdin.close()
            if self.log_file:
                self.log_file.close()
            self.process = None


def main():
    if os.name != "nt":
        raise RuntimeError("This integration runner uses the project's Windows Gradle distribution")
    (ROOT / "runtime").mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="inventory-check-", dir=ROOT / "runtime"))
    server = IsolatedServer(directory)
    evidence = {"engine": "Minecraft Java 1.21.1", "port": PORT, "world": str(directory), "checks": []}
    old_slots = [None] * 36
    old_slots[0] = {"id": "minecraft:oak_planks", "count": 1}
    old_slots[1] = {"id": "minecraft:oak_planks", "count": 5}
    old_slots[2] = {"id": "minecraft:iron_sword", "count": 1, "components": {"minecraft:damage": 7}}
    legacy = {"revision": 23, "slots": old_slots,
              "touched": [{"x": 0, "y": 64, "z": 0, "block": "minecraft:stone"}]}
    server.write_snapshot(legacy)
    try:
        initial = server.start()
        migrated = json.loads(server.state_file.read_text(encoding="utf-8"))
        check(migrated["schemaVersion"] == 1 and migrated["selectedSlot"] == 0, "Legacy snapshot was not migrated")
        check(migrated["slots"] == old_slots and migrated["touched"] == legacy["touched"], "Legacy migration lost existing materials/blocks")
        check(initial["revision"] == 23 and initial["inventory"] == {"minecraft:oak_planks": 6, "minecraft:iron_sword": 1}, "Legacy state changed")
        check(len(initial["slots"]) == 36 and [s["slot"] for s in initial["slots"]] == list(range(36)), "Slot contract invalid")
        evidence["checks"].append("Legacy 36-slot inventory and touched blocks migrate without losses or revision change")

        catalog = call("catalog")["items"]
        by_id = {item["id"]: item for item in catalog}
        check(len(by_id) == len(catalog) and len(catalog) > 1000, "Registry catalog is incomplete or has duplicates")
        check("minecraft:air" not in by_id, "Air should not be grantable")
        for item, expected in [("minecraft:oak_planks", 64), ("minecraft:ender_pearl", 16), ("minecraft:diamond_sword", 1)]:
            check(by_id[item]["maxCount"] == expected and by_id[item]["name"], f"Wrong vanilla item catalog entry {item}")
        check({i["id"] for i in catalog if i["placeSupported"]} == {
            "minecraft:oak_log", "minecraft:oak_planks", "minecraft:cobblestone", "minecraft:dirt", "minecraft:stone", "minecraft:crafting_table"}, "Catalog overstates supported placement")
        evidence["catalogCount"] = len(catalog)
        evidence["checks"].append("Complete non-air MC registry catalog reports native maximum stacks 64/16/1 and actual placement limits")

        rejected("grant", item="minecraft:does_not_exist")
        rejected("grant", item="minecraft:air")
        rejected("grant", item="minecraft:dirt", operationId="")
        for slot in [-1, 36, 1.5]:
            rejected("select", slot=slot)
        evidence["checks"].append("Unknown items, air and invalid selections leave state unchanged")

        placed = mutate("place-selected", x=0, y=65, z=0)
        check(placed["slots"][0] == {"slot": 0, "empty": True} and placed["selectedItem"] is None, "Last selected block did not become empty")
        check(placed["selectedSlot"] == 0 and placed["slots"][1]["count"] == 5, "Placement switched to another slot")
        check(any(b["x"] == 0 and b["y"] == 65 and b["z"] == 0 for b in placed["blocks"]), "Block absent from actual world state")
        rejected("place-selected", x=1, y=65, z=0)
        rejected("consume")
        empty = mutate("select", slot=35)
        check(empty["selectedItem"] is None and "count" not in empty["slots"][35], "Empty selection reports a phantom count")
        evidence["checks"].append("Selected-slot placement consumes its last block, preserves other stacks and keeps an empty selection")

        grants = {}
        for item, count in [("minecraft:cobblestone", 64), ("minecraft:ender_pearl", 16), ("minecraft:diamond_sword", 1)]:
            before = call()["inventory"].get(item, 0)
            state = mutate("grant", item=item)
            check(state["inventory"].get(item, 0) - before == count, f"Grant did not use vanilla stack count for {item}")
            grants[item] = slot_for(state, item)
        evidence["checks"].append("Free grants insert one whole original MC stack for blocks, pearls and unstackable tools")

        state = mutate("grant", item="minecraft:diamond_sword")
        swords = [s for s in state["slots"] if s.get("id") == "minecraft:diamond_sword"]
        check(len(swords) == 2 and all(s["count"] == 1 for s in swords), "Unstackable items merged")
        mutate("select", slot=swords[0]["slot"])
        consumed = mutate("consume")
        check(consumed["selectedItem"] is None and consumed["selectedSlot"] == swords[0]["slot"], "Consuming final item changed selection")
        check(consumed["inventory"]["minecraft:diamond_sword"] == 1 and consumed["slots"][swords[1]["slot"]]["count"] == 1, "Consume pulled from a different slot")
        rejected("consume")
        evidence["checks"].append("Explicit item consumption empties only selected slot and never pulls from another stack")

        state = mutate("grant", item="minecraft:stone_bricks")
        mutate("select", slot=slot_for(state, "minecraft:stone_bricks"))
        rejected("place-selected", x=1, y=65, z=0)
        rejected("consume")
        mutate("select", slot=grants["minecraft:cobblestone"])
        rejected("consume")
        rejected("place-selected", x=0, y=64, z=0)
        evidence["checks"].append("Unsupported blocks and occupied cells reject placement before any consumption")

        before_craft = mutate("grant", item="minecraft:oak_log")
        planks = mutate("craft", recipe="minecraft:oak_planks")
        delta(before_craft, planks, {"minecraft:oak_log": -1, "minecraft:oak_planks": 4})
        sticks = mutate("craft", recipe="minecraft:stick")
        delta(planks, sticks, {"minecraft:oak_planks": -2, "minecraft:stick": 4})
        table = mutate("craft", recipe="minecraft:crafting_table")
        delta(sticks, table, {"minecraft:oak_planks": -4, "minecraft:crafting_table": 1})
        broken = mutate("break", x=0, y=65, z=0)
        delta(table, broken, {"minecraft:oak_planks": 1})
        check(not any(b["x"] == 0 and b["y"] == 65 and b["z"] == 0 for b in broken["blocks"]), "Break did not remove test block")
        evidence["checks"].append("All three existing vanilla recipes and diamond-pickaxe block drops still work")

        before_save_failure = call()
        disk_hash = hashlib.sha256(server.state_file.read_bytes()).hexdigest()
        temporary = server.state_file.with_name(server.state_file.name + ".tmp")
        check(temporary.parent == server.state_file.parent and not temporary.exists(), "Unsafe save-failure fixture")
        temporary.mkdir()
        try:
            try:
                mutate("grant", item="minecraft:ender_pearl")
            except HTTPError as error:
                check(error.code == 503, "A storage failure should be reported as 503")
            else:
                raise AssertionError("Storage failure unexpectedly succeeded")
            check(call() == before_save_failure, "Storage failure did not roll back live state")
            check(hashlib.sha256(server.state_file.read_bytes()).hexdigest() == disk_hash, "Storage failure altered main snapshot")
        finally:
            temporary.rmdir()
        evidence["checks"].append("A real snapshot-write failure rolls back inventory, selection, touched cells and revision without changing the saved file")

        operation = str(uuid.uuid4())
        body = {"operationId": operation, "slot": grants["minecraft:ender_pearl"]}
        selected = call("select", body)
        check(call("select", dict(reversed(list(body.items())))) == selected, "Identical semantic retry is not idempotent")
        for path, changed in [("select", {**body, "slot": 35}), ("consume", {"operationId": operation})]:
            before = call()
            try:
                call(path, changed)
            except HTTPError as error:
                check(error.code == 400, "Receipt conflict should return 400")
            else:
                raise AssertionError("Same operation ID accepted another path/body")
            check(call() == before, "Conflicting retry changed state")
        evidence["checks"].append("Receipts bind operation IDs to path/body and reject conflicting retries")

        # Fill the owned test world, then create a 63-plank edge case from MC's own serialized snapshot.
        while any(s["empty"] for s in call()["slots"]):
            mutate("grant", item="minecraft:dirt")
        server.stop()
        full_snapshot = json.loads(server.state_file.read_text(encoding="utf-8"))
        plank_stacks = [s for s in full_snapshot["slots"] if s and s["id"] == "minecraft:oak_planks"]
        check(len(plank_stacks) == 1, "Partial-capacity fixture requires exactly one plank stack")
        plank_stacks[0]["count"] = 63
        server.write_snapshot(full_snapshot)
        server.start()
        before_full = call()
        check(before_full["inventory"]["minecraft:oak_planks"] == 63, "Partial-capacity fixture was lost")
        rejected("grant", item="minecraft:oak_planks")
        check(call() == before_full, "Full grant kept a partial insertion")
        evidence["checks"].append("A whole-stack grant rolls back its one inserted plank when only one of 64 can fit")

        before_restart = call()
        server.stop()
        after_restart = server.start()
        check(after_restart == before_restart, "Normal restart lost slot contents, selected slot, revision or blocks")
        saved_restart = json.loads(server.state_file.read_text(encoding="utf-8"))
        damaged_swords = [s for s in saved_restart["slots"] if s and s["id"] == "minecraft:iron_sword"]
        check(damaged_swords[0]["components"]["minecraft:damage"] == 7, "Restart lost real item damage component")
        evidence["checks"].append("Normal restart preserves all 36 slots, selection, inventory components and touched blocks")
        server.stop()

        future = json.loads(server.state_file.read_text(encoding="utf-8"))
        future["schemaVersion"] = 2
        server.write_snapshot(future)
        expected_hash = hashlib.sha256(server.state_file.read_bytes()).hexdigest()
        server.start(expected_failure="unsupported future inventory schema 2")
        check(hashlib.sha256(server.state_file.read_bytes()).hexdigest() == expected_hash, "Unknown future format was overwritten")
        server.stop(authority=False)
        evidence["checks"].append("Unknown future schema disables authority without truncating or overwriting its file")
        evidence["result"] = "passed"
    except Exception as error:
        evidence["result"] = "failed"
        evidence["error"] = str(error)
        raise
    finally:
        server.stop()
        evidence["forcedOwnTestProcessStop"] = server.forced_stop
        (ROOT / "runtime/inventory-checks.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    main()
