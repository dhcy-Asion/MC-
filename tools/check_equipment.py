"""Real MC 1.21.1 equipment transfers in an owned world on 8768/25580.

No production service, save, native game, deployment or fake player is used.
Only this runner's stopped test snapshot is edited for migration/fault fixtures.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
import tempfile
import uuid
from urllib.error import HTTPError

from check_inventory import ROOT, PORT, IsolatedServer, call, check, mutate, rejected, slot_for

SLOTS = ("head", "chest", "legs", "feet")
DAMAGED = {"id": "minecraft:diamond_helmet", "count": 1, "components": {
    "minecraft:damage": 17, "minecraft:custom_name": '"保留名字的头盔"',
    "minecraft:enchantments": {"levels": {"minecraft:protection": 2}}}}
DYED = {"id": "minecraft:leather_chestplate", "count": 1, "components": {
    "minecraft:damage": 3, "minecraft:dyed_color": {"rgb": 3368601},
    "minecraft:custom_name": '"染色胸甲"',
    "minecraft:trim": {"material": "minecraft:quartz", "pattern": "minecraft:sentry"}}}


def snapshot(version=3):
    result = {"schemaVersion": version, "selectedSlot": 2, "revision": 47,
              "slots": [None] * 36,
              "touched": [{"x": 0, "y": 64, "z": 0, "block": "minecraft:oak_log"}]}
    result["slots"][2], result["slots"][3] = deepcopy(DAMAGED), deepcopy(DYED)
    if version >= 2:
        result["touched"][0]["properties"] = {"axis": "z"}
    if version >= 3:
        result["equipment"] = dict.fromkeys(SLOTS)
    if version == 0:
        result.pop("schemaVersion")
        result.pop("selectedSlot")
    return result


def ownership(state):
    result = Counter(state["inventory"])
    for row in state["equipment"]["slots"].values():
        if not row["empty"]:
            result[row["id"]] += row["count"]
    return result


def gear(state, slot):
    return state["equipment"]["slots"][slot]


def saved(server):
    return json.loads(server.state_file.read_text(encoding="utf-8"))


def main():
    check(os.name == "nt", "This runner uses the project's Windows Gradle distribution")
    directory = ROOT / "runtime" / os.path.basename(tempfile.mkdtemp(prefix="equipment-check-", dir=ROOT / "runtime"))
    server = IsolatedServer(directory)
    evidence = {"engine": "Minecraft Java 1.21.1", "port": PORT, "world": str(directory), "checks": []}
    up = False

    def passed(message):
        evidence["checks"].append(message)
        print(f"PASS {len(evidence['checks'])}: {message}", flush=True)

    def restart(data):
        nonlocal up
        server.stop(authority=up)
        up = False
        server.write_snapshot(data)
        result = server.start()
        up = True
        return result

    def reject_snapshot(data, label):
        nonlocal up
        server.stop(authority=up)
        up = False
        server.write_snapshot(data)
        before = server.state_file.read_bytes()
        server.start(expected_failure="Authority disabled; initialization failed")
        check(server.state_file.read_bytes() == before, label + " changed the rejected save")
        server.stop(authority=False)
        passed(label + " disables API and preserves original bytes")

    try:
        for version in (0, 1, 2):
            original = snapshot(version)
            state = restart(original)
            data = saved(server)
            check(data["schemaVersion"] == 3 and data["revision"] == 47, "Migration changed revision")
            check(data["selectedSlot"] == (0 if version == 0 else 2), "Migration changed selection")
            check(data["slots"] == original["slots"], "Migration lost full ItemStack components")
            expected_cells = deepcopy(original["touched"])
            if version < 2:
                expected_cells[0]["properties"] = {"axis": "y"}
            check(data["touched"] == expected_cells, "Migration changed block state")
            check(data["equipment"] == dict.fromkeys(SLOTS), "Legacy equipment was not empty")
            check(state["equipment"] == call("equipment"), "Equipment GET disagrees with state")
            check(not state["equipment"]["nativeApplied"] and not state["equipment"]["runtimeApplied"], "False runtime claim")
            passed(f"Schema {version} migrates to 3 with 36 stacks, components, selection, touched and revision intact")

        for item, amount in (("minecraft:cobblestone", 64), ("minecraft:ender_pearl", 16), ("minecraft:diamond_sword", 1)):
            before = call()["inventory"].get(item, 0)
            state = mutate("grant", item=item)
            check(state["inventory"].get(item, 0) - before == amount, "Legacy grant count changed")
        passed("Legacy free grants still use 64 / 16 / 1 vanilla stack limits")

        state = mutate("select", slot=2)
        owned, selected = ownership(state), state["selectedSlot"]
        state = mutate("equip-selected")
        check(gear(state, "head")["stack"] == DAMAGED, "Equip changed damaged/named/enchanted stack")
        check("minecraft:diamond_helmet" not in state["inventory"], "Equipment counted twice in backpack aggregate")
        check(state["selectedSlot"] == selected and ownership(state) == owned, "Equip changed selection or lost items")
        state = mutate("unequip", slot="head")
        check(ownership(state) == owned and DAMAGED in saved(server)["slots"], "Unequip lost components")
        mutate("select", slot=slot_for(state, "minecraft:leather_chestplate"))
        state = mutate("equip-selected")
        check(gear(state, "chest")["stack"] == DYED, "Equip lost dye/trim/name/damage")
        passed("Transfers preserve damage, name, enchantments, dye and trim; backpack totals exclude equipped items")

        for material in ("leather", "chainmail", "iron", "golden", "diamond", "netherite"):
            for suffix, slot in (("helmet", "head"), ("chestplate", "chest"), ("leggings", "legs"), ("boots", "feet")):
                item = f"minecraft:{material}_{suffix}"
                state = mutate("add-item", item=item, count=1)
                mutate("select", slot=slot_for(state, item))
                before = call()
                state = mutate("equip-selected")
                check(gear(state, slot)["id"] == item and gear(state, slot)["count"] == 1, item + " went to wrong slot")
                check(ownership(state) == ownership(before), item + " swap lost items")
                state = mutate("unequip", slot=slot)
                # Dispose of only this owned test copy through the existing explicit consume action.
                mutate("select", slot=slot_for(state, item))
                mutate("consume")
        passed("All 24 conventional armor pieces use their actual four MC humanoid slots and conserve swaps")

        for path, slot in (("turtle_helmet", "head"), ("elytra", "chest"), ("carved_pumpkin", "head"),
                           *((name, "head") for name in ("skeleton_skull", "wither_skeleton_skull", "zombie_head",
                              "player_head", "creeper_head", "dragon_head", "piglin_head"))):
            item = "minecraft:" + path
            state = mutate("add-item", item=item, count=2 if path.endswith(("head", "skull")) or path == "carved_pumpkin" else 1)
            mutate("select", slot=slot_for(state, item))
            before = call()
            state = mutate("equip-selected")
            check(gear(state, slot)["id"] == item and gear(state, slot)["count"] == 1, "Nonstandard wearable rule differs")
            check(ownership(state) == ownership(before), "Stackable head lost count")
            mutate("unequip", slot=slot)
        passed("Turtle helmet, elytra, carved pumpkin and seven skull/head types use vanilla Equipment slots, one item each")

        for path in ("wolf_armor", "leather_horse_armor", "iron_horse_armor", "golden_horse_armor", "diamond_horse_armor",
                     "shield", "diamond_sword", "apple", "pumpkin", "stone"):
            item = "minecraft:" + path
            state = mutate("add-item", item=item, count=1)
            mutate("select", slot=slot_for(state, item))
            rejected("equip-selected")
        for slot in ("body", "mainhand", "offhand", "HEAD", "", 0, None):
            rejected("unequip", slot=slot)
        passed("Animal BODY armor, hands and non-wearables reject; unequip accepts only four exact slot names")

        state = restart(snapshot())
        operation = {"operationId": str(uuid.uuid4())}
        first = call("equip-selected", operation)
        check(call("equip-selected", operation) == first, "Equip retry was not idempotent")
        rejected("unequip", slot="head", operationId=operation["operationId"])
        before = call()
        operation = {"operationId": str(uuid.uuid4()), "slot": "head"}
        first = call("unequip", operation)
        check(call("unequip", operation) == first, "Unequip retry duplicated items")
        rejected("unequip", slot="chest", operationId=operation["operationId"])
        check(ownership(first) == ownership(before), "Receipt retry changed ownership")
        passed("Equip and unequip operation IDs remain idempotent and reject conflicting path/body reuse")

        mutate("select", slot=slot_for(call(), "minecraft:diamond_helmet"))
        for path, body in (("equip-selected", {}), ("unequip", {"slot": "head"})):
            if path == "unequip":
                mutate("equip-selected")
            before, before_bytes = call(), server.state_file.read_bytes()
            temp = server.state_file.with_name(server.state_file.name + ".tmp")
            check(not temp.exists(), "Unexpected save temporary path")
            temp.mkdir()
            try:
                try:
                    mutate(path, **body)
                except HTTPError as error:
                    check(error.code == 503, "Save failure should return 503")
                else:
                    raise AssertionError("Equipment save failure succeeded")
                check(call() == before and server.state_file.read_bytes() == before_bytes, "Save failure did not roll back complete state")
            finally:
                temp.rmdir()
        passed("Equip and unequip disk-write failures roll back equipment, backpack, selection, touched and revision")

        before, before_disk = call(), saved(server)
        server.stop()
        up = False
        state = server.start()
        up = True
        check(state == before and saved(server) == before_disk, "Normal restart lost equipped components")
        passed("Normal restart preserves complete equipped ItemStacks and all original state")

        full = snapshot()
        full["slots"] = [{"id": "minecraft:dirt", "count": 64} for _ in range(36)]
        full["slots"][2] = {"id": "minecraft:carved_pumpkin", "count": 2}
        full["equipment"]["head"] = deepcopy(DAMAGED)
        restart(full)
        rejected("unequip", slot="head")
        rejected("equip-selected")
        check(saved(server) == full, "Full swap/unequip changed save")
        full["slots"][2] = {"id": "minecraft:iron_helmet", "count": 1}
        before = restart(full)
        after = mutate("equip-selected")
        check(gear(after, "head")["id"] == "minecraft:iron_helmet" and ownership(after) == ownership(before), "Freed source slot did not admit swapped armor")
        check(DAMAGED in saved(server)["slots"], "Full swap lost original component stack")
        passed("Full inventory refuses unequip and stacked-head swaps atomically; one-item swap uses its freed source slot")

        cursed = snapshot()
        cursed["slots"][2]["components"]["minecraft:enchantments"] = {"levels": {"minecraft:binding_curse": 1}}
        restart(cursed)
        state = mutate("equip-selected")
        rejected("unequip", slot="head")
        state = mutate("add-item", item="minecraft:iron_helmet", count=1)
        mutate("select", slot=slot_for(state, "minecraft:iron_helmet"))
        rejected("equip-selected")
        check(gear(call(), "head")["stack"] == cursed["slots"][2], "Binding item changed")
        passed("Actual PREVENT_ARMOR_CHANGE enchantment effect blocks removal/swap without a fictional creative player")

        invalid = []
        future = snapshot(); future["schemaVersion"] = 4
        invalid.append((future, "Future schema"))
        missing = snapshot(); del missing["equipment"]["feet"]
        invalid.append((missing, "Missing equipment slot"))
        extra = snapshot(); extra["equipment"]["body"] = None
        invalid.append((extra, "Unexpected animal slot"))
        wrong = snapshot(); wrong["equipment"]["feet"] = deepcopy(DAMAGED)
        invalid.append((wrong, "Wrong humanoid slot"))
        count = snapshot(); count["equipment"]["head"] = {"id": "minecraft:carved_pumpkin", "count": 2}
        invalid.append((count, "More than one equipped item"))
        foreign = snapshot(); foreign["equipment"]["head"] = {"id": "red:helmet", "count": 1}
        invalid.append((foreign, "Non-Minecraft equipment"))
        fractional = snapshot(); fractional["equipment"]["head"] = {"id": "minecraft:carved_pumpkin", "count": 1.5}
        invalid.append((fractional, "Fractional equipped count"))
        corrupted = snapshot(); corrupted["slots"][2]["components"]["minecraft:damage"] = -1
        invalid.append((corrupted, "Corrupt ItemStack component"))
        legacy = snapshot(2); legacy["equipment"] = dict.fromkeys(SLOTS)
        invalid.append((legacy, "Legacy snapshot with unrecognized equipment"))
        for data, label in invalid:
            reject_snapshot(data, label)
        evidence["result"] = "passed"
    except Exception as error:
        evidence.update(result="failed", error=str(error))
        raise
    finally:
        server.stop(authority=up)
        evidence["forcedOwnTestProcessStop"] = server.forced_stop
        (ROOT / "runtime/equipment-checks.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
