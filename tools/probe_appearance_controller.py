"""Observe the controlled actor's fixed appearance-controller chain, read-only.

No native function is called, no HTTP endpoint is contacted and no heap scan is
performed. Unknown types, incomplete reads and unstable links stop interpretation.
Pointer-bearing output is confined to ignored runtime JSON files.
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

import probe_characters as core
import probe_character_roster as roster

ROOT = Path(__file__).resolve().parents[1]
WORLD_GLOBAL = 0x6D69190
WORLD_ANCHORS = (0x361B87, 0x36256A, 0x36DCEC)
WORLD_PATTERN = "48 8B 05 ?? ?? ?? ?? 48 8B 48 30 48 8B 83 A0 00 00 00 48 39 41 58"
CONTROLLER_VTABLE = 0x559DD98
CODE_WINDOWS = {
    # Existing native callers, not entry points for this diagnostic to invoke.
    0x6298DD: bytes.fromhex("488b4708488b4868488b4140488b88b8000000488b5920488d542430488bcbe8cf2c1000488d542440488bcbe892271000488bcbe83ad30f00"),
    0x726C7D: bytes.fromhex("488b416033ff4885c075048bcfeb0f488b4008488d48d84885c0480f44cfe800cad4ff4885c00f848a010000"),
}
TYPES = {
    "manager": ".?AVClientActorManager@pa@@",
    "user": ".?AVClientUserActor@pa@@",
    "actor": ".?AVClientChildOnlyInGameActor@pa@@",
    "control": ".?AVClientCharacterControlActorComponent@pa@@",
    "controller": ".?AVCharacterCustomizationController@pa@@",
    "owner": ".?AVSceneObjectClient@pa@@",
}
MAX_OWNER_COMPONENTS = 256
SAMPLE_GAP_SECONDS = 0.05


class ProbeError(RuntimeError):
    pass


def pointer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0x10000 <= value < 2**47 or value % 8:
        raise ProbeError(f"{name} is null, unaligned or outside the reviewed address bounds")
    return value


def read(reader, address, size, name):
    if not isinstance(size, int) or not 1 <= size <= 4096:
        raise ProbeError(f"{name} read exceeds the fixed diagnostic bound")
    raw = reader.read(address, size)
    if raw is None or len(raw) != size:
        raise ProbeError(f"{name} complete readable span is unavailable")
    return raw


def value(reader, address, name, fmt="<Q"):
    return struct.unpack(fmt, read(reader, address, struct.calcsize(fmt), name))[0]


def typed(reader, address, base, length, name):
    pointer(address, name)
    vt = value(reader, address, name + " vtable")
    if not base + 8 <= vt <= base + length - 8:
        raise ProbeError(f"{name} vtable escaped the main image")
    col = value(reader, vt - 8, name + " RTTI locator")
    if not base <= col <= base + length - 24:
        raise ProbeError(f"{name} RTTI locator escaped the main image")
    sig, offset, ctor, desc, hierarchy, selfrva = struct.unpack("<6I", read(reader, col, 24, name + " RTTI locator"))
    if (sig != 1 or offset != 0 or col - selfrva != base or not 0 < desc <= length - 208
            or not 0 < hierarchy < length):
        raise ProbeError(f"{name} RTTI does not describe a complete primary object")
    actual = reader.rtti(address, base, length)
    if actual != TYPES[name]:
        raise ProbeError(f"{name} RTTI differs from the reviewed type: {actual}")
    if name == "controller" and vt - base != CONTROLLER_VTABLE:
        raise ProbeError("Controller vtable differs from the fixed EXE layout")
    return {"pointer": hex(address), "rtti": actual, "vtableRva": hex(vt - base)}


def validate_code(reader, base, length):
    if not 0 < length <= core.MAX_IMAGE_SIZE:
        raise ProbeError("Main image exceeds the reviewed bounds")
    if WORLD_GLOBAL > length - 8 or CONTROLLER_VTABLE > length - 8:
        raise ProbeError("Fixed world global or controller vtable escaped the main image")
    for rva, expected in CODE_WINDOWS.items():
        if rva > length - len(expected) or read(reader, base + rva, len(expected), "native chain code") != expected:
            raise ProbeError("Native chain code bytes differ from the fixed EXE contract")
    pattern = core.pattern(WORLD_PATTERN)
    size = len(WORLD_PATTERN.split())
    for rva in WORLD_ANCHORS:
        if rva > length - size:
            raise ProbeError("World anchor escaped the main image")
        raw = read(reader, base + rva, size, "world anchor")
        if pattern.fullmatch(raw) is None:
            raise ProbeError("World anchor differs from the fixed source signature")
        if rva + 7 + struct.unpack_from("<i", raw, 3)[0] != WORLD_GLOBAL:
            raise ProbeError("The three fixed world anchors do not agree")


def sample(reader, base, length, observed):
    def link(address, name):
        return pointer(value(reader, address, name), name)
    root = link(base + WORLD_GLOBAL, "world root")
    observed["worldRoot"] = hex(root)
    manager = link(root + 0x30, "client manager")
    observed["manager"] = typed(reader, manager, base, length, "manager")
    user = link(manager + 0x58, "client user")
    observed["user"] = typed(reader, user, base, length, "user")
    actor = link(manager + 0x50, "controlled actor")
    observed["actor"] = typed(reader, actor, base, length, "actor")
    if (value(reader, user + 0xD0, "user first child") != actor or
            value(reader, user + 0xD8, "user second child") != actor or
            value(reader, actor + 0xA0, "actor user backlink") != user):
        raise ProbeError("Controlled actor manager/user round trip does not agree")
    observed["controlledActorRoundTripObserved"] = True
    table = link(actor + 0x68, "actor component table")
    observed["componentTable"] = hex(table)
    control = link(table + 0x40, "character control component")
    observed["control"] = typed(reader, control, base, length, "control")
    if value(reader, control + 8, "control actor backlink") != actor:
        raise ProbeError("Character control owner backlink differs from the controlled actor")
    middle = link(control + 0xB8, "opaque controller holder")
    header = read(reader, middle, 0x28, "opaque controller holder")
    observed["opaqueHolder"] = {"pointer": hex(middle), "readableHeaderBytes": 0x28,
                                "typeOrOtherFieldsInterpreted": False}
    controller = pointer(struct.unpack_from("<Q", header, 0x20)[0], "appearance controller")
    observed["controller"] = typed(reader, controller, base, length, "controller")
    raw = read(reader, controller, 0x140, "complete controller allocation")
    owner = pointer(struct.unpack_from("<Q", raw, 0x10)[0], "controller owner")
    observed["owner"] = typed(reader, owner, base, length, "owner")
    weak = pointer(struct.unpack_from("<Q", raw, 0x60)[0], "controller weak owner holder")
    target = pointer(value(reader, weak + 8, "weak owner target"), "weak owner target")
    if target != owner + 0x28:
        raise ProbeError("Controller weak-owner unwrap differs from the primary owner")
    flag = value(reader, target + 0x15, "weak target invalidation flag", "<B")
    observed["weakOwner"] = {"holder": hex(weak), "target": hex(target), "targetFlag15": flag,
                             "unwrapMatchesOwner": True}
    if flag != 0:
        raise ProbeError("Controller weak owner is invalidated or has an unknown flag")
    directory = read(reader, owner + 0x210, 16, "owner component directory")
    owner_array, count, capacity = struct.unpack("<QII", directory)
    if not 1 <= count <= MAX_OWNER_COMPONENTS or not count <= capacity <= 4096:
        raise ProbeError("Owner component count/capacity exceeds the reviewed bounds")
    pointer(owner_array, "owner component array")
    members = read(reader, owner_array, count * 8, "complete owner component array")
    occurrences = list(struct.unpack(f"<{count}Q", members)).count(controller)
    observed["ownerComponents"] = {"array": hex(owner_array), "count": count, "capacity": capacity,
                                   "controllerOccurrences": occurrences}
    if occurrences != 1:
        raise ProbeError("Controller is not present exactly once in its owner's component array")
    observed["controllerOwnerRoundTripObserved"] = True
    selections = {}
    for name, offset, maximum in (("mesh", 0xA0, 16), ("decoration", 0xB0, 250)):
        array, count, capacity = struct.unpack_from("<QII", raw, offset)
        if not 0 <= count <= maximum or not count <= capacity <= 4096:
            raise ProbeError(f"{name} selection count/capacity exceeds the reviewed bounds")
        if count:
            pointer(array, name + " selection array")
            choices = read(reader, array, count, name + " selections")
        else:
            choices = b""
        selections[name] = {"array": hex(array), "count": count, "capacity": capacity,
                            "selectionBytesHex": choices.hex(), "loadedOptionBoundsVerified": False}
    observed["selections"] = selections
    # Re-read only structural bytes that have a known contract, not unknown
    # holder fields or values which may legitimately change while moving.
    expected_links = ((base + WORLD_GLOBAL, root), (root + 0x30, manager), (manager + 0x58, user),
                      (manager + 0x50, actor), (user + 0xD0, actor), (user + 0xD8, actor),
                      (actor + 0xA0, user), (actor + 0x68, table), (table + 0x40, control),
                      (control + 8, actor), (control + 0xB8, middle), (middle + 0x20, controller),
                      (controller + 0x10, owner), (controller + 0x60, weak), (weak + 8, target))
    if any(value(reader, address, "structural link reread") != expected for address, expected in expected_links):
        raise ProbeError("Structural controller links changed during reads")
    if (read(reader, owner + 0x210, 16, "owner directory reread") != directory or
            read(reader, owner_array, len(members), "owner array reread") != members or
            read(reader, controller + 0xA0, 32, "selection directory reread") != raw[0xA0:0xC0] or
            value(reader, target + 0x15, "weak flag reread", "<B") != flag):
        raise ProbeError("Controller owner or selection directory changed during reads")
    for name, entry in selections.items():
        if entry["count"] and read(reader, int(entry["array"], 16), entry["count"], name + " selection reread").hex() != entry["selectionBytesHex"]:
            raise ProbeError("Controller selections changed during reads")
    for name, address in (("manager", manager), ("user", user), ("actor", actor),
                          ("control", control), ("controller", controller), ("owner", owner)):
        if typed(reader, address, base, length, name) != observed[name]:
            raise ProbeError("Typed controller chain changed during reads")
    observed["stableDuringSample"] = True


def collect(reader, base, length, pause=time.sleep):
    report = {"schemaVersion": 1, "mode": "external-read-only", "state": "rejected", "samples": [],
              "nativeFunctionsInvoked": False, "gameMemoryWritten": False, "heapScanned": False,
              "appearanceApplicationVerified": False, "appearanceRestoreVerified": False,
              "steveModelLoaded": False, "snapshotAtomic": False,
              "controlledControllerChainObserved": False, "stableTwoSamples": False,
              "limitations": ["Stable pointer ownership is an observation, not a native appearance application contract.",
                              "Mesh/decor byte selections do not verify loaded option tables or permit mesh writes.",
                              "The intermediate holder's type and unused fields are not interpreted."]}
    try:
        validate_code(reader, base, length)
        for index in range(2):
            observed = {}
            report["samples"].append(observed)
            sample(reader, base, length, observed)
            if index == 0:
                pause(SAMPLE_GAP_SECONDS)
        validate_code(reader, base, length)
        if report["samples"][0] != report["samples"][1]:
            report["state"] = "unstable"
            raise ProbeError("The two fixed controller samples do not agree")
        report["stableTwoSamples"] = True
        report["controlledControllerChainObserved"] = True
        selections = report["samples"][0]["selections"]
        report["selectionBuffersPresent"] = all(entry["count"] > 0 for entry in selections.values())
        report["state"] = "observed" if report["selectionBuffersPresent"] else "notReady"
        if report["state"] == "notReady":
            report["reason"] = "Controller ownership was observed but one or more selection buffers are empty"
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        if len(report["samples"]) > 1 and report["samples"][0].get("stableDuringSample"):
            report["state"] = "unstable"
        report["reason"] = str(error)[:2000]
    return report


def output_path(path):
    path = roster.output_path(path)
    if path.exists():
        raise ProbeError("Appearance evidence output already exists; use a new runtime JSON path")
    return path


def write_report(path, report):
    path = output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_path(path)
    raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > 256 * 1024:
        raise ProbeError("Appearance evidence exceeds the bounded report size")
    with path.open("xb") as stream:
        stream.write(raw)


def summary(report, output):
    return {"output": str(output), **{key: report.get(key) for key in
            ("state", "reason", "stableTwoSamples", "controlledControllerChainObserved", "selectionBuffersPresent",
             "nativeFunctionsInvoked", "gameMemoryWritten", "appearanceApplicationVerified", "steveModelLoaded")}}


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="otherwise require exactly one running CrimsonDesert.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/appearance-controller.json")
    args = parser.parse_args()
    output = output_path(args.output)
    pid = args.pid
    if pid is None:
        text = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"],
                                       text=True, encoding="utf-8", errors="replace")
        matches = re.findall(r'"CrimsonDesert\.exe","(\d+)"', text, re.I)
        if len(matches) != 1:
            raise ProbeError("Require exactly one running game or explicit --pid")
        pid = int(matches[0])
    if pid <= 0:
        raise ProbeError("Invalid process ID")
    profile, _ = core.load_profile()
    reader = core.Reader(pid)
    try:
        base, length, path = reader.module()
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
        digest = file_digest(path)
        roster.validate_layout_build(profile, version, digest)
        report = collect(reader, base, length)
        if reader.module() != (base, length, path) or file_digest(path) != digest:
            report.update(state="unstable", stableTwoSamples=False, controlledControllerChainObserved=False,
                          reason="Game module changed during the read-only observation")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      game={"pid": pid, "path": str(path), "version": version, "sha256": digest,
                            "moduleBase": hex(base), "moduleSize": length},
                      source={"worldAnchor": profile["world_root"]["source"], "license": "MIT",
                              "staticChainRvas": [hex(rva) for rva in CODE_WINDOWS]})
        write_report(output, report)
        print(json.dumps(summary(report, output), ensure_ascii=False, indent=2))
        return 0 if report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
