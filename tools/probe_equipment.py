"""Observe the controlled client's typed equipment table, read-only.

Only complete opaque 0xD0 records and their u16 slot tags are observed. This is
not an item decoder, restorable loadout, equipment restriction or native call.
All address-bearing evidence stays in a fresh ignored runtime JSON file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import probe_health as health

appearance, core, roster = health.appearance, health.core, health.roster
ROOT, ProbeError = health.ROOT, health.ProbeError
process_identity = health.process_identity
image_address = health.image_address

# The first three windows are the existing reviewed controlled-actor contract.
# Equipment windows were independently read from the fixed EXE, across its PE
# executable sections (the code is not confined to the section named .text).
# Batch receives actor+68 -> table+38, reads owner+8 and consumes the +90 table.
# Pinning that consumer does not authorize calling it or suppressing its return.
WINDOWS = (
    (0x8a90ac, 317, "68a4306f61d34183b32e7687ad0902514f0ae1005094d4777bf9800c56f4501b"),
    (0x206a7a0, 223, "54504c71364411bff72c5c69092184a54f2f13b41b6deddce9b42456d730640b"),
    (0x2404a20, 138, "435f9bb5a12ab1fcd1e4408f11702fb1dcc5531a1f415d22075cfd208686a94f"),
    (0x980a50, 2074, "0d33db1d7e021b29c52269c1fa8f8a7a2be2bb82b1c0eea28d4f0fe9049343e7"),
    (0x5f8849, 56, "f7d060c8b05e3df7587c0ef1d39293ff743be84604a2e14f526ccea197de7617"),
    (0x9e640b, 54, "a87e88d812815ff7f3678c4cac22bcb1b127d3ec0f2e7062d19e2ca2a4d2c6a0"),
)
# (primary vtable, COL, type descriptor, class hierarchy, exact RTTI name)
EQUIPMENT_TYPE = (0x55bcc38, 0x5dd5468, 0x6ac17e8, 0x5dd5388,
                  ".?AVClientEquipSlotActorComponent@pa@@")
MAX_ENTRIES, ENTRY_STRIDE, SLOT_TAG_OFFSET = 64, 0xd0, 0xc8
SUCCESS_FLAGS = ("controlledEquipmentTableObserved", "stableTwoSamples")
UNVERIFIED_FLAGS = ("itemIdentitiesVerified", "equipmentRestoreVerified", "nativeEquipmentBlocked",
                    "equipmentApplied", "snapshotAtomic", "nativeFunctionsInvoked", "gameMemoryWritten", "heapScanned")


def validate_code(reader, base, length):
    appearance.pointer(base, "module base")
    if type(length) is not int or not 0 < length <= core.MAX_IMAGE_SIZE or base + length >= 2**47:
        raise ProbeError("Equipment module extent exceeds bounds")
    image_address(base, length, appearance.WORLD_GLOBAL, 8)
    for rva, size, digest in WINDOWS:
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "equipment contract code")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ProbeError("Equipment code window differs from the pinned EXE")
    for rva in appearance.WORLD_ANCHORS:
        size = len(appearance.WORLD_PATTERN.split())
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "controlled world anchor")
        if (core.pattern(appearance.WORLD_PATTERN).fullmatch(raw) is None or
                rva + 7 + struct.unpack_from("<i", raw, 3)[0] != appearance.WORLD_GLOBAL):
            raise ProbeError("Controlled world anchors differ")
    vt, col, desc, hierarchy, name = EQUIPMENT_TYPE
    image_address(base, length, vt, 8)
    image_address(base, length, hierarchy, 1)
    if (appearance.value(reader, image_address(base, length, vt - 8, 8), "equipment type locator") != base + col or
            appearance.read(reader, image_address(base, length, col, 24), 24, "equipment primary COL") !=
            struct.pack("<6I", 1, 0, 0, desc, hierarchy, col) or
            appearance.read(reader, image_address(base, length, desc + 16, len(name) + 1), len(name) + 1,
                            "equipment type name") != name.encode() + b"\0"):
        raise ProbeError("Equipment fixed primary type metadata differs")


def typed_equipment(watch, address):
    appearance.pointer(address, "client equipment")
    vt, col, desc, hierarchy, name = EQUIPMENT_TYPE
    if (watch.value(address, "client equipment vtable") != watch.base + vt or
            watch.value(watch.base + vt - 8, "client equipment locator") != watch.base + col or
            watch.get(watch.base + col, 24, "client equipment COL") != struct.pack("<6I", 1, 0, 0, desc, hierarchy, col) or
            watch.get(watch.base + desc + 16, len(name) + 1, "client equipment RTTI name") != name.encode() + b"\0"):
        raise ProbeError("Controlled equipment exact primary type differs")
    return address


def sample(reader, base, length, observed):
    watch = health.Watch(reader, base, length)
    observed["stage"] = "controlledActor"
    world = watch.link(base + appearance.WORLD_GLOBAL, "world root")
    manager = watch.typed(watch.link(world + 0x30, "client manager"), "manager")
    user = watch.typed(watch.link(manager + 0x58, "client user"), "user")
    actor = watch.typed(watch.link(manager + 0x50, "controlled actor"), "actor")
    if (watch.value(user + 0xd0, "first controlled child") != actor or
            watch.value(user + 0xd8, "second controlled child") != actor or
            watch.value(actor + 0xa0, "actor user backlink") != user):
        raise ProbeError("Controlled actor/user round trip differs")
    observed.update(controlledActor=hex(actor), stage="equipmentComponent")
    components = watch.link(actor + 0x68, "actor component table")
    equipment = typed_equipment(watch, watch.link(components + 0x38, "client equipment component"))
    if watch.value(equipment + 8, "equipment owner") != actor:
        raise ProbeError("Equipment owner differs from the controlled actor")
    observed.update(equipmentComponent=hex(equipment), stage="equipmentTable")
    descriptor = watch.link(equipment + 0x90, "equipment table descriptor")
    data, count = struct.unpack("<QI", watch.get(descriptor + 8, 12, "equipment array/count"))
    observed.update(tableDescriptor=hex(descriptor), tableArray=hex(data), entryCount=count, entries=[])
    if count > MAX_ENTRIES:
        raise ProbeError("Equipment entry count exceeds the fixed bound")
    # No capacity is invented at descriptor+14. The consumer accepts a zero
    # count; a null array is allowed only for that empty table, never dereferenced.
    if count or data:
        appearance.pointer(data, "equipment table array")
    span = count * ENTRY_STRIDE
    if count and data >= 2**47 - span:
        raise ProbeError("Equipment complete array span exceeds address bounds")
    observed["stage"] = "opaqueEntries"
    tags = set()
    for index in range(count):
        raw = watch.get(data + index * ENTRY_STRIDE, ENTRY_STRIDE, "equipment opaque record " + str(index))
        tag = struct.unpack_from("<H", raw, SLOT_TAG_OFFSET)[0]
        observed["entries"].append({"index": index, "slotTagU16": tag, "rawD0Sha256": hashlib.sha256(raw).hexdigest()})
        if tag in tags:
            raise ProbeError("Repeated equipment slot tag; no record is selected or merged")
        tags.add(tag)
    observed["stage"] = "dependencyReread"
    observed["dependencies"] = watch.finish()
    observed.update(stage="complete", stableDuringSample=True)


def empty_report():
    return {"schemaVersion": 1, "mode": "typed-equipment-table-read-only", "state": "unavailable", "samples": [],
            **{flag: False for flag in (*SUCCESS_FLAGS, *UNVERIFIED_FLAGS)},
            "limitations": [
                "Complete opaque equipment records and raw slot tags only; item identities and nested pointers are not decoded.",
                "An external double read is not an atomic snapshot or an object-lifetime guarantee.",
                "This is not a restorable loadout, an equipment ban, or proof of rendered/applied equipment.",
                "No native function, lazy load, heap scan, game memory write or fallback actor is used."]}


def reject(report, reason, state="unavailable"):
    report.update(state=state, reason=str(reason)[:2000], **{flag: False for flag in SUCCESS_FLAGS})
    return report


def collect(reader, base, length, *, identity=None, pause=time.sleep):
    identity = identity or (lambda: process_identity(reader))
    report = empty_report()
    try:
        before = identity()
        if (type(before.get("pid")) is not int or before["pid"] <= 0 or
                not str(before.get("creationTime100ns", "")).isdigit() or int(before["creationTime100ns"]) <= 0 or
                (before.get("moduleBase"), before.get("moduleSize")) != (base, length)):
            raise ProbeError("Reader process/module identity does not match the sample")
        report["process"] = before
        validate_code(reader, base, length)
        for index in range(2):
            observed = {"stableDuringSample": False}
            report["samples"].append(observed)
            sample(reader, base, length, observed)
            if index == 0:
                pause(0.05)
        validate_code(reader, base, length)
        if identity() != before or report["samples"][0] != report["samples"][1]:
            raise ProbeError("Process identity or complete typed equipment samples changed")
        report.update(state="observed", controlledEquipmentTableObserved=True, stableTwoSamples=True)
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        reject(report, error, "unstable" if any(row.get("stableDuringSample") for row in report["samples"]) else "unavailable")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/typed-equipment.json")
    args = parser.parse_args()
    output = appearance.output_path(args.output)
    pid = args.pid
    if pid is None:
        rows = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"],
                                       text=True, encoding="utf-8", errors="replace")
        pids = re.findall(r'"CrimsonDesert\.exe","(\d+)"', rows, re.I)
        if len(pids) != 1:
            raise ProbeError("Require exactly one game process or explicit --pid")
        pid = int(pids[0])
    if pid <= 0:
        raise ProbeError("Invalid PID")
    profile, _ = core.load_profile()
    report = empty_report()
    reader = core.Reader(pid)
    try:
        try:
            base, length, path = reader.module()
            version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
                "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
            digest = appearance.file_digest(path)
            roster.validate_layout_build(profile, version, digest)
            report = collect(reader, base, length)
            if (report.get("process", {}).get("pid") != pid or process_identity(reader) != report.get("process") or
                    appearance.file_digest(path) != digest):
                reject(report, "Final reader process/module/EXE identity changed", "unstable")
            report.update(gameVersion=version, supportedExeSha256=digest)
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
            reject(report, error, "unstable" if report.get("process") else "unavailable")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      contract={"codeWindowCount": len(WINDOWS), "maximumEntries": MAX_ENTRIES,
                                "entryStride": ENTRY_STRIDE, "slotTagOffset": SLOT_TAG_OFFSET})
        appearance.write_report(output, report)
        print(json.dumps({"output": str(output), **{key: report.get(key) for key in
                         ("state", "reason", *SUCCESS_FLAGS, *UNVERIFIED_FLAGS)}}, indent=2))
        return 0 if report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
