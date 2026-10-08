"""Read one unnamed owner-keyed Skinned object identity and owner links.

No animation/palette decoder, native game call, memory write or fallback. The
existing controlled appearance chain is reused with every byte watched. Stable
external samples do not make an atomic snapshot or retain an object's lifetime.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import probe_owner_components as owner_probe

appearance, core, roster = owner_probe.appearance, owner_probe.core, owner_probe.roster
ROOT, ProbeError = appearance.ROOT, appearance.ProbeError
process_identity = owner_probe.process_identity
CONTEXT_VTABLE, CONTEXT_PRIMARY_SLOT_ZERO = 0x5B4D168, 0x2DBB170
SKINNED_OWNER_OFFSET, CONTEXT_OFFSET = 0x60, 0x1C0
CONTEXT_HEADER_BYTES, CONTEXT_ALLOCATION_BYTES = 0x40, 0x200
MAX_NEW_SEMANTIC_BYTES = 97
MAX_REPORT_BYTES, MAX_REASON_CHARACTERS = 4 * 1024 * 1024, 512
SUCCESS_FLAGS = ("controlledControllerChainObserved", "characterSceneObserved", "controlledSkinnedChainObserved",
                 "candidateConstructorIdentityObserved", "candidateOwnerRoundTripsObserved", "stableTwoSamples")
UNVERIFIED_FLAGS = ("snapshotAtomic", "primaryRttiVerified", "formalClassNameKnown", "animationObjectIdentified",
                    "poseControllerObserved", "bonePaletteObserved", "threadIdentityVerified", "nativeAbiVerified",
                    "nativeFunctionsInvoked", "gameMemoryWritten", "heapScanned", "nativeApplied", "animationSystemComplete")
# Fixed disk evidence from the SHA256-pinned 1.0.0.2976 executable. Runtime
# admission does not load ignored research reports or reuse recorded instances.
WINDOWS = (
    (0x2D99EA7, bytes.fromhex("498b476033ff4885c07505448bc7eb0f488b40084c8d40d84885c04c0f44c74c8d4d40488d5550e8bd32f8ff488bf0498d9fc0010000483bc37411488bcbe8d674f7ff488b0e48890b48893e")),
    (0x2D13C45, bytes.fromhex("45395cd1087513418b4cd10c488b47484c8b04c8493958087429ffc2413bd272df")),
    (0x10BDD5DC, bytes.fromhex("bafd01000065488b042558000000488b08803c0a00ba10000000b9000200007407e87624c1f3eb05e8a723c1f34889c34885c0751be85ab873f04531c94531c0ba01000000b9020000a0ff151cdb60f448895c24384885db741d4889f24889d9e8afd11df2")),
    (0x2DBA815, bytes.fromhex("488d0574957b024889014c8971084489711066c74114010044887116")),
    (0x2DBA831, bytes.fromhex("488d053029d9024889014c8971184c8971204c8971284c8971304885d274254438723d751f488d4a28e811a961fd488947304885c0740d443870047405f0ff00eb02ff0048895f38")),
    (0x2D99B2D, bytes.fromhex("488b8ec00100004881c11001000041b9080000004c8d45d8488d96c8010000e88fa20100")),
    (0x2D9894D, bytes.fromhex("488d8bc8010000e837245ffd90488d8bc0010000e85a8af7ff")),
    (0x2DBB59C, bytes.fromhex("498b4e304885c9743849897e30807904007408f00fc119ffcbeb04ff098b1985db751e65488b042558000000488b10381c167407e8e74da301eb06e8e04ca30190")),
    (0x2DBB51C, bytes.fromhex("498d9e1001000048895c2468488d4b08e89fbb79fd90488bcbe856f85cfd90")),
    (0x10BC2530, bytes.fromhex("45395cd1087513458b44d10c488b43484a8b0cc0483969087409ffc24439d272dfeb0d4489c2488d4b30e841e384ef")),
    (0x10BDD65B, bytes.fromhex("4885db7428807b1500740a4c89fb48895c2438eb18")),
)
FIELD_EVIDENCE = (
    {"field": "Skinned+60", "bytes": 8, "source": "2D99EA7 owner-key producer weak-holder load"},
    {"field": "Skinned weak holder+8", "bytes": 8, "source": "2D99EB7..2D99EC2 weak target minus28 becomes owner argument"},
    {"field": "owner+3D", "bytes": 1, "source": "2DBA850 owner invalidation test; existing appearance weak_at target+15"},
    {"field": "Skinned+1C0", "bytes": 8, "source": "2D99ED6..2D99EF3 object transfer;2D99B2D object consumer"},
    {"field": "candidate[0,40)", "bytes": 64,
     "source": "10BDD5F6 allocates200 bytes;2DBA831..2DBA879 initializes this prefix",
     "interpretedOffsets": {"0": "2DBA838 exact constructor vtable",
                             "15": "2DBA827 word14=1 sets15=0;10BDD660 getter rejects flag15!=0",
                             "30": "2DBA856 passesowner+28 to weak-handle creator3D5170;2DBA85F stores handle",
                             "38": "2DBA875 stores exact original primary owner"}},
    {"field": "candidate weak holder+8", "bytes": 8, "source": "Same owner+28 weak-handle creator/unwrap contract; only exact fresh-owner target admitted"},
)


class WatchedReader:
    """Reuse the appearance chain while capturing its RTTI/header reads too."""
    def __init__(self, watch):
        self.watch = watch

    def read(self, address, size):
        return self.watch.get(address, size, "controlled appearance dependency")

    def rtti(self, address, base, length):
        if (base, length) != (self.watch.base, self.watch.length):
            raise ProbeError("RTTI reader module changed")
        # Same standard primary COL/name contract, including cd==0. No call to
        # an unwatched Reader.rtti and no alternate/reflection name fallback.
        return owner_probe.primary_identity(self.watch, address, {})["rtti"]


class NewFields:
    """Count the six admitted semantic spans before each read, excluding rereads."""
    def __init__(self, watch, observed):
        self.watch, self.observed, self.total = watch, observed, 0
        observed.update(newSemanticReadBytes=0, maximumNewSemanticReadBytes=MAX_NEW_SEMANTIC_BYTES,
                        newReadSpans=[], dependencyRereadsAlsoPerformed=True)

    def get(self, address, size, label):
        if type(size) is not int or size <= 0 or self.total + size > MAX_NEW_SEMANTIC_BYTES:
            raise ProbeError("New unnamed-object fields exceed the 97-byte semantic read bound")
        self.total += size
        self.observed["newSemanticReadBytes"] = self.total
        raw = self.watch.get(address, size, label)
        self.observed["newReadSpans"].append({"address": hex(address), "size": size,
                                               "field": label, "bytesHex": raw.hex()})
        return raw

    def link(self, address, label):
        return appearance.pointer(struct.unpack("<Q", self.get(address, 8, label))[0], label)


def validate_extent(base, length):
    appearance.pointer(base, "module base")
    if type(length) is not int or not 0 < length <= core.MAX_IMAGE_SIZE or base + length >= 2**47:
        raise ProbeError("Unnamed-object module extent exceeds bounds")
    if CONTEXT_VTABLE > length - 8:
        raise ProbeError("Unnamed-object fixed vtable escapes main image")


def validate_code(reader, base, length):
    validate_extent(base, length)
    appearance.validate_code(reader, base, length)
    for rva, expected in WINDOWS:
        if not 0 <= rva <= length - len(expected):
            raise ProbeError("Unnamed-object code evidence escapes main image")
        if appearance.read(reader, base + rva, len(expected), "unnamed-object fixed code") != expected:
            raise ProbeError("Unnamed-object code bytes differ from the fixed EXE")
    if appearance.value(reader, base + CONTEXT_VTABLE, "unnamed-object primary slot zero") != base + CONTEXT_PRIMARY_SLOT_ZERO:
        raise ProbeError("Unnamed-object constructor vtable primary slot zero differs")


def sample(reader, base, length, observed):
    watch = owner_probe.IdentityWatch(reader, base, length)
    appearance.sample(WatchedReader(watch), base, length, observed)
    # The inherited flag ends before our new fields; only our complete finish
    # may set it back to true. Empty selections/resources do not select a fallback.
    observed["stableDuringSample"] = False
    scene = observed.get("characterScene", {})
    render = scene.get("renderObject", {})
    identity = scene.get("renderObjectIdentity", {})
    if not (scene.get("sceneOwnerRoundTripObserved") is True and scene.get("sceneOccurrences") == 1
            and scene.get("renderLinkObserved") is True and identity.get("typeGatePassed") is True
            and render.get("reflectionType") == "SkinnedMeshComponent"
            and render.get("vtableRva") == hex(appearance.SKINNED_MESH_VTABLE)):
        raise ProbeError("Require the fresh unique controlled Scene to exact SkinnedMeshComponent chain")
    owner = appearance.pointer(int(observed["owner"]["pointer"], 16), "fresh controlled owner")
    skinned = appearance.pointer(int(render["pointer"], 16), "fresh exact Skinned primary")
    fields = NewFields(watch, observed)
    holder = fields.link(skinned + SKINNED_OWNER_OFFSET, "Skinned owner weak holder")
    target = fields.link(holder + 8, "Skinned owner weak target")
    if target != owner + 0x28:
        raise ProbeError("Skinned weak owner differs from the fresh controlled owner")
    if fields.get(owner + 0x3D, 1, "controlled owner invalidation flag") != b"\0":
        raise ProbeError("Skinned controlled owner is invalidated")
    candidate = fields.link(skinned + CONTEXT_OFFSET, "Skinned unnamed owner-keyed object")
    evidence = {"pointer": hex(candidate), "name": "unnamed owner-keyed object",
                "state": "unavailable", "constructorAllocationBytes": CONTEXT_ALLOCATION_BYTES,
                "rawHeaderBytes": CONTEXT_HEADER_BYTES, "primaryRttiVerified": False,
                "formalClassNameKnown": False, "animationObjectIdentified": False,
                "candidateConstructorIdentityObserved": False, "candidateOwnerRoundTripsObserved": False,
                "interpretedHeaderOffsets": ["0x0", "0x15", "0x30", "0x38"]}
    observed["candidate"] = evidence
    raw = fields.get(candidate, CONTEXT_HEADER_BYTES, "unnamed object bounded raw header")
    evidence["raw40Hex"] = raw.hex()
    vt = struct.unpack_from("<Q", raw)[0]
    evidence["vtablePointer"] = hex(vt)
    if vt != base + CONTEXT_VTABLE:
        raise ProbeError("Unnamed object vtable differs from its fixed constructor")
    evidence["vtableRva"] = hex(CONTEXT_VTABLE)
    if raw[0x15] != 0:
        raise ProbeError("Unnamed object invalidation flag is nonzero")
    direct = struct.unpack_from("<Q", raw, 0x38)[0]
    evidence["directOwnerPointer"] = hex(direct)
    if direct != owner:
        raise ProbeError("Unnamed object direct owner differs from the fresh controlled owner")
    weak = appearance.pointer(struct.unpack_from("<Q", raw, 0x30)[0], "unnamed object owner weak holder")
    weak_target = fields.link(weak + 8, "unnamed object owner weak target")
    evidence["weakOwner"] = {"holder": hex(weak), "target": hex(weak_target)}
    if weak_target != owner + 0x28:
        raise ProbeError("Unnamed object weak owner differs from the fresh controlled owner")
    evidence["weakOwner"]["targetFlag15"] = 0
    observed["skinnedWeakOwner"] = {"holder": hex(holder), "target": hex(target), "targetFlag15": 0}
    observed["dependencies"] = watch.finish()
    observed["stableDuringSample"] = True
    evidence.update(state="observed", candidateConstructorIdentityObserved=True, candidateOwnerRoundTripsObserved=True)


def empty_report():
    return {"schemaVersion": 1, "mode": "controlled-skinned-unnamed-owner-object-read-only",
            "state": "unavailable", "samples": [],
            **{key: False for key in (*SUCCESS_FLAGS, *UNVERIFIED_FLAGS)},
            "limitations": ["The constructor identity does not provide a formal class name or prove animation/pose storage.",
                "Only the bounded header and owner links are decoded; no children, callback queue or palette is traversed.",
                "External full dependency double reads do not retain object lifetime or make an atomic game-thread snapshot."]}


def reject(report, reason, state="unavailable"):
    report.update(state=state, reason=str(reason)[:MAX_REASON_CHARACTERS], **{key: False for key in SUCCESS_FLAGS})
    # Retain raw partial evidence, but invalidate every sample-level success too.
    def clear_successes(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if type(item) is bool and (key.endswith(("Observed", "Verified", "Passed")) or key == "stableDuringSample"):
                    value[key] = False
                elif key == "state" and item == "observed":
                    value[key] = "rejected"
                else:
                    clear_successes(item)
        elif isinstance(value, list):
            for item in value:
                clear_successes(item)
    for observed in report.get("samples", []):
        clear_successes(observed)
    return report


def collect(reader, base, length, *, identity=None, pause=time.sleep):
    identity = identity or (lambda: process_identity(reader))
    report = empty_report()
    try:
        validate_extent(base, length)
        before = owner_probe.checked_identity(identity, base, length)
        report["process"] = before
        validate_code(reader, base, length)
        for index in range(2):
            if index and owner_probe.checked_identity(identity, base, length) != before:
                raise ProbeError("Reader identity changed before the second complete sample")
            observed = {"stableDuringSample": False}
            report["samples"].append(observed)
            sample(reader, base, length, observed)
            if owner_probe.checked_identity(identity, base, length) != before:
                raise ProbeError("Reader identity changed after a complete sample")
            if index == 0:
                pause(appearance.SAMPLE_GAP_SECONDS)
        validate_code(reader, base, length)
        if owner_probe.checked_identity(identity, base, length) != before:
            raise ProbeError("Reader identity changed at the final complete-chain gate")
        if report["samples"][0] != report["samples"][1]:
            raise ProbeError("Complete controlled chain or unnamed-object bytes differ between samples")
        report.update(state="observed", **{key: True for key in SUCCESS_FLAGS})
    except (ProbeError, RuntimeError, OSError, ValueError, KeyError, struct.error) as error:
        state = "unstable" if any(row.get("stableDuringSample") for row in report["samples"]) else "unavailable"
        reject(report, error, state)
    return report


def write_report(path, report):
    path = appearance.output_path(path)
    raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_REPORT_BYTES:
        reject(report, "Complete unnamed-object evidence exceeds the 4MiB output bound")
        raise ProbeError(report["reason"])
    path.parent.mkdir(parents=True, exist_ok=True)
    appearance.output_path(path)
    with path.open("xb") as stream:
        stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/owner-skinned-object.json")
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
    reader = core.Reader(pid)
    report = empty_report()
    try:
        try:
            base, length, path = reader.module()
            version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
                "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
            digest = appearance.file_digest(path)
            roster.validate_layout_build(profile, version, digest)
            report = collect(reader, base, length)
            if appearance.file_digest(path) != digest:
                raise ProbeError("Final on-disk EXE identity changed")
            if (report.get("process", {}).get("pid") != pid or
                    owner_probe.checked_identity(lambda: process_identity(reader), base, length) != report.get("process")):
                raise ProbeError("Final same-handle process/module identity changed")
            report.update(gameVersion=version, supportedExeSha256=digest)
        except (ProbeError, RuntimeError, OSError, ValueError, KeyError, struct.error) as error:
            reject(report, error, "unstable" if report.get("process") else "unavailable")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(), contract={
            "sourceCodeGate": "existing appearance default windows plus eleven fixed unnamed-object windows",
            "fixedExeSha256": roster.SHA256, "fixedGameVersion": roster.VERSION,
            "staticWindowRvas": [hex(at) for at, _ in WINDOWS], "candidateVtableRva": hex(CONTEXT_VTABLE),
            "candidateHeaderBytes": CONTEXT_HEADER_BYTES, "constructorAllocationBytes": CONTEXT_ALLOCATION_BYTES,
            "maximumNewSemanticBytesPerSample": MAX_NEW_SEMANTIC_BYTES, "dependencyRereadsAlsoPerformed": True,
            "fieldEvidence": FIELD_EVIDENCE,
            "maximumReportBytes": MAX_REPORT_BYTES, "formalClassNameKnown": False,
            "readLimit": "stop after header and owner links; no+110,+1B8,+1C8 or pose/palette decoding"})
        output_written = False
        try:
            write_report(output, report)
            output_written = True
        except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
            reject(report, error)
        print(json.dumps({"output": str(output), "outputWritten": output_written,
                         **{key: report.get(key) for key in ("state", "reason", *SUCCESS_FLAGS, *UNVERIFIED_FLAGS)}},
                         ensure_ascii=False, indent=2))
        return 0 if output_written and report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
