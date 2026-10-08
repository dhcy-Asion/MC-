"""Observe only registered controlled-owner component primary identities.

No native game call, heap scan, component layout, resource or equipment decoder.
An external double read is not an atomic snapshot or an object lifetime guarantee.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import struct
import subprocess
import time
from pathlib import Path

import probe_health as health

appearance, core, roster = health.appearance, health.core, health.roster
ROOT, ProbeError = appearance.ROOT, appearance.ProbeError
process_identity = health.process_identity
DIRECTORY_OFFSET, MEMBER_STRIDE = 0x210, 8
MAX_COMPONENTS = appearance.MAX_OWNER_COMPONENTS
MAX_CAPACITY_OBSERVATION, MAX_RTTI_BYTES = 4096, 192
MAX_REPORT_BYTES, MAX_REASON_CHARACTERS = 4 * 1024 * 1024, 512
SUCCESS_FLAGS = ("controlledOwnerComponentTableObserved", "componentEnumerationObserved",
                 "stableTwoSamples", "allPrimaryRttiObserved")
UNVERIFIED_FLAGS = ("snapshotAtomic", "componentOwnerBacklinksVerified", "backAttachmentIdentified",
                    "renderResourceIdentitiesVerified", "capacitySemanticsVerified", "nativeFunctionsInvoked",
                    "gameMemoryWritten", "heapScanned", "componentLayoutsInterpreted")


class IdentityWatch(health.Watch):
    """A caught per-slot failure must not conceal a changing dependency."""
    def __init__(self, reader, base, length):
        super().__init__(reader, base, length)
        self.invalidated, self.unavailable = False, {}

    def get(self, address, size, label):
        key = (address, size)
        previous = key in self.rows
        try:
            raw = super().get(address, size, label)
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error):
            if previous:
                self.invalidated = True
            elif type(address) is int and type(size) is int and 1 <= size <= 4096 and 0x10000 <= address < 2**47-size:
                self.unavailable[key] = label
            raise
        if key in self.unavailable:
            self.invalidated = True
        return raw

    def finish(self):
        if self.invalidated:
            raise ProbeError("An identity dependency changed or became unavailable during sample")
        dependencies = super().finish()
        for (address, size), label in self.unavailable.items():
            raw = self.reader.read(address, size)
            if raw is not None and len(raw) == size:
                raise ProbeError(label + " became readable during dependency reread")
        return dependencies


def primary_identity(watch, address, evidence):
    """Use only standard primary MSVC RTTI; unknown types never admit a layout."""
    evidence.update(pointer=hex(address), state="unavailable", identityOnly=True,
                    primaryRttiObserved=False, layoutInterpreted=False,
                    componentOwnerBacklinkVerified=False, failedChecks=[])

    def require(valid, key):
        if not valid:
            evidence["failedChecks"].append(key)
            raise ProbeError("Component primary identity rejected: " + key)

    appearance.pointer(address, "registered component primary pointer")
    vt = watch.value(address, "registered component vtable")
    evidence["vtablePointer"] = hex(vt)
    require(watch.base + 8 <= vt <= watch.base + watch.length - 8, "vtable-main-image-bounds")
    evidence["vtableRva"] = hex(vt - watch.base)
    col = watch.value(vt - 8, "registered component primary locator")
    evidence["candidateLocatorPointer"] = hex(col)
    require(watch.base <= col <= watch.base + watch.length - 24, "locator-main-image-bounds")
    raw = watch.get(col, 24, "registered component primary COL")
    sig, offset, ctor, desc, hierarchy, selfrva = struct.unpack("<6I", raw)
    evidence.update(candidateLocatorRva=hex(col - watch.base), candidateLocatorHeaderHex=raw.hex(),
                    candidateLocatorFields={"signature": sig, "primaryThisOffset": offset,
                        "constructorDisplacement": ctor, "typeDescriptorRva": hex(desc),
                        "classHierarchyRva": hex(hierarchy), "selfRva": hex(selfrva)})
    for valid, key in ((sig == 1, "signature-equals-one"), (offset == 0, "primary-this-offset-zero"),
                      (ctor == 0, "constructor-displacement-zero"),
                      (col - selfrva == watch.base, "locator-self-rva"),
                      (0 < desc <= watch.length - 16 - MAX_RTTI_BYTES, "type-descriptor-main-image-bounds"),
                      (0 < hierarchy < watch.length, "class-hierarchy-main-image-bounds")):
        require(valid, key)
    name = watch.get(watch.base + desc + 16, MAX_RTTI_BYTES, "registered component primary RTTI name")
    require(b"\0" in name, "bounded-terminated-rtti-name")
    token = name.split(b"\0", 1)[0]
    require(bool(token) and all(32 <= byte < 127 for byte in token), "ascii-rtti-name")
    evidence.update(rtti=token.decode("ascii"), state="observed", primaryRttiObserved=True)
    return evidence


def known_type(watch, address, kind):
    evidence = primary_identity(watch, address, {})
    if evidence["rtti"] != appearance.TYPES[kind]:
        raise ProbeError(kind + " RTTI differs from the reviewed controlled chain")
    if kind == "controller" and int(evidence["vtableRva"], 16) != appearance.CONTROLLER_VTABLE:
        raise ProbeError("Controller vtable differs from the fixed EXE layout")
    return {"pointer": hex(address), "rtti": evidence["rtti"], "vtableRva": evidence["vtableRva"]}


def validate_code(reader, base, length):
    appearance.pointer(base, "module base")
    if type(length) is not int or not 0 < length <= core.MAX_IMAGE_SIZE or base + length >= 2**47:
        raise ProbeError("Owner component module extent exceeds bounds")
    appearance.validate_code(reader, base, length)


def sample(reader, base, length, observed):
    watch = IdentityWatch(reader, base, length)
    root = watch.link(base + appearance.WORLD_GLOBAL, "world root")
    manager = watch.link(root + 0x30, "client manager")
    observed["manager"] = known_type(watch, manager, "manager")
    user = watch.link(manager + 0x58, "client user")
    observed["user"] = known_type(watch, user, "user")
    actor = watch.link(manager + 0x50, "controlled actor")
    observed["actor"] = known_type(watch, actor, "actor")
    if (watch.value(user + 0xD0, "user first controlled child") != actor or
            watch.value(user + 0xD8, "user second controlled child") != actor or
            watch.value(actor + 0xA0, "actor user backlink") != user):
        raise ProbeError("Controlled actor manager/user round trip differs")
    observed.update(worldRoot=hex(root), controlledActorRoundTripObserved=True)
    table = watch.link(actor + 0x68, "actor fixed component table")
    control = watch.link(table + 0x40, "character control component")
    observed["control"] = known_type(watch, control, "control")
    if watch.value(control + 8, "control actor backlink") != actor:
        raise ProbeError("Control component owner differs from the controlled actor")
    holder = watch.link(control + 0xB8, "opaque controller holder")
    controller = watch.link(holder + 0x20, "appearance controller")
    observed["controller"] = known_type(watch, controller, "controller")
    owner = watch.link(controller + 0x10, "controller owner")
    observed["owner"] = known_type(watch, owner, "owner")
    weak = watch.link(controller + 0x60, "controller weak owner holder")
    target = watch.link(weak + 8, "controller weak owner target")
    if target != owner + 0x28 or watch.value(target + 0x15, "owner weak invalidation flag", "<B") != 0:
        raise ProbeError("Controller weak owner differs or is invalidated")
    observed.update(componentTable=hex(table), opaqueHolder=hex(holder),
                    weakOwner={"holder": hex(weak), "target": hex(target), "targetFlag15": 0})
    directory = watch.get(owner + DIRECTORY_OFFSET, 16, "owner registered component directory")
    data, count, capacity = struct.unpack("<QII", directory)
    observed["ownerComponents"] = {"array": hex(data), "count": count,
        "capacityObservation": capacity, "capacitySemanticsVerified": False,
        "directoryBytesHex": directory.hex(), "memberStride": MEMBER_STRIDE}
    if not 1 <= count <= MAX_COMPONENTS or not count <= capacity <= MAX_CAPACITY_OBSERVATION:
        raise ProbeError("Owner registered component count/capacity observation exceeds bounds")
    appearance.pointer(data, "owner registered component array")
    members = watch.get(data, count * MEMBER_STRIDE, "complete ordered owner component array")
    addresses = struct.unpack(f"<{count}Q", members)
    occurrences = addresses.count(controller)
    observed["ownerComponents"].update(memberBytesHex=members.hex(), controllerOccurrences=occurrences)
    if occurrences != 1:
        raise ProbeError("Controller is not present exactly once in its owner component array")
    observed.update(controllerOwnerRoundTripObserved=True, entries=[])
    for index, address in enumerate(addresses):
        entry = {"index": index, "registeredInControlledOwnerTable": True}
        observed["entries"].append(entry)
        try:
            primary_identity(watch, address, entry)
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
            entry.update(state="unavailable", primaryRttiObserved=False, reason=str(error)[:MAX_REASON_CHARACTERS])
    # Every successful read in the chain, complete ordered table and each
    # standard identity is retained and reread after the final slot.
    observed["dependencies"] = watch.finish()
    observed["unavailableDependencies"] = [{"address": hex(at), "size": size, "field": label,
                                            "completeReadObserved": False}
                                           for (at, size), label in watch.unavailable.items()]
    observed["stableDuringSample"] = True


def empty_report():
    return {"schemaVersion": 1, "mode": "controlled-owner-component-primary-identities-read-only",
            "state": "unavailable", "samples": [],
            **{flag: False for flag in (*SUCCESS_FLAGS, *UNVERIFIED_FLAGS)},
            "limitations": [
                "Registered membership is not a verified individual component owner backlink or a back attachment.",
                "Primary RTTI names do not admit component layouts, prefab/PAC identities or native calls.",
                "The adjacent capacity word is an observation; its allocation semantics are not independently verified.",
                "Unavailable primary identities remain unavailable; no reflection, secondary-object or heap fallback.",
                "External stable double reads are not atomic and do not guarantee object lifetime."]}


def reject(report, reason, state="unavailable"):
    report.update(state=state, reason=str(reason)[:MAX_REASON_CHARACTERS], **{flag: False for flag in SUCCESS_FLAGS})
    return report


def checked_identity(identity, base, length):
    current = identity()
    if (type(current.get("pid")) is not int or current["pid"] <= 0 or
            not isinstance(current.get("creationTime100ns"), str) or
            re.fullmatch(r"[1-9][0-9]{0,19}", current["creationTime100ns"]) is None or
            (current.get("moduleBase"), current.get("moduleSize")) != (base, length) or
            not isinstance(current.get("imagePath"), str) or not current["imagePath"]):
        raise ProbeError("Reader process/module identity does not match this observation")
    return current


def collect(reader, base, length, *, identity=None, pause=time.sleep):
    identity = identity or (lambda: process_identity(reader))
    report = empty_report()
    try:
        before = checked_identity(identity, base, length)
        report["process"] = before
        validate_code(reader, base, length)
        for index in range(2):
            if index:
                if checked_identity(identity, base, length) != before:
                    raise ProbeError("Reader process identity changed between owner component samples")
            observed = {"stableDuringSample": False}
            report["samples"].append(observed)
            sample(reader, base, length, observed)
            if index == 0:
                pause(appearance.SAMPLE_GAP_SECONDS)
        validate_code(reader, base, length)
        if checked_identity(identity, base, length) != before or report["samples"][0] != report["samples"][1]:
            raise ProbeError("Process identity or complete ordered owner component observations changed")
        report.update(state="observed", controlledOwnerComponentTableObserved=True,
                      componentEnumerationObserved=True, stableTwoSamples=True,
                      allPrimaryRttiObserved=all(row["primaryRttiObserved"] for row in report["samples"][0]["entries"]))
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        reject(report, error, "unstable" if any(row.get("stableDuringSample") for row in report["samples"]) else "unavailable")
    return report


def write_report(path, report):
    """Preserve all raw evidence within this diagnostic's independent bound."""
    path = appearance.output_path(path)
    raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    # 256 slots with all 192-byte RTTI/dependency spans exceed the older
    # appearance writer's 512KiB limit. Bound this complete output separately;
    # neither directory nor dependency evidence is shortened to make it fit.
    if len(raw) > MAX_REPORT_BYTES:
        reject(report, "Complete owner component evidence exceeds the 4MiB output bound")
        raise ProbeError(report["reason"])
    path.parent.mkdir(parents=True, exist_ok=True)
    appearance.output_path(path)
    with path.open("xb") as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/owner-component-identities.json")
    args = parser.parse_args()
    output = appearance.output_path(args.output)
    pid = args.pid
    if pid is None:
        rows = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"],
                                       text=True, encoding="utf-8", errors="replace")
        matches = re.findall(r'"CrimsonDesert\.exe","(\d+)"', rows, re.I)
        if len(matches) != 1:
            raise ProbeError("Require exactly one running game or explicit --pid")
        pid = int(matches[0])
    if pid <= 0:
        raise ProbeError("Invalid process ID")
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
            if (report.get("process", {}).get("pid") != pid or
                    checked_identity(lambda: process_identity(reader), base, length) != report.get("process") or
                    appearance.file_digest(path) != digest):
                reject(report, "Final reader process/module/EXE identity changed", "unstable")
            report.update(gameVersion=version, supportedExeSha256=digest)
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
            reject(report, error, "unstable" if report.get("process") else "unavailable")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(), contract={
            "sourceCodeGate": "probe_appearance_controller.validate_code default fixed windows",
            "directoryOffset": hex(DIRECTORY_OFFSET), "memberStride": MEMBER_STRIDE,
            "maximumComponents": MAX_COMPONENTS, "maximumCapacityObservation": MAX_CAPACITY_OBSERVATION,
            "maximumRttiNameBytes": MAX_RTTI_BYTES, "capacitySemanticsVerified": False,
            "maximumReportBytes": MAX_REPORT_BYTES, "maximumReasonCharacters": MAX_REASON_CHARACTERS})
        output_written = False
        try:
            write_report(output, report)
            output_written = True
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
            reject(report, error)
        print(json.dumps({"output": str(output), "outputWritten": output_written, **{key: report.get(key) for key in
            ("state", "reason", *SUCCESS_FLAGS, *UNVERIFIED_FLAGS)}}, ensure_ascii=False, indent=2))
        return 0 if output_written and report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
