"""Observe one metadata-mapped Hp record of the controlled client, read-only.

No stat scan, native getter, lazy loader, write, health projection or HUD value.
Two stable external reads detect changes; they do not provide object lifetime or
an atomic game-thread snapshot. Pointer-bearing output stays in ignored runtime.
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

import probe_appearance_controller as appearance

core, roster = appearance.core, appearance.roster
ROOT, ProbeError = appearance.ROOT, appearance.ProbeError
# Fixed on-disk EXE evidence; no ignored research JSON is loaded at runtime.
WINDOWS = (
    (0x8a90ac, 317, "68a4306f61d34183b32e7687ad0902514f0ae1005094d4777bf9800c56f4501b"),
    (0x206a7a0, 223, "54504c71364411bff72c5c69092184a54f2f13b41b6deddce9b42456d730640b"),
    (0x2404a20, 138, "435f9bb5a12ab1fcd1e4408f11702fb1dcc5531a1f415d22075cfd208686a94f"),
    (0x178f1d0, 87, "0e07d31a36994b9a4ac7e01eadce97763333482da291b1ed5724629d24ef74b5"),
    (0x178f4ea, 335, "d8d6312a2c7bd670dcb640ce1eb579581fccf87af4f47f2effa855e2dbe6114b"),
    (0x17adcc0, 134, "2fd239b089cc14e18885ba10e25e43195af818ef1aabdb59a99dea14c16e456d"),
    (0x17b05d0, 143, "85c80154aa99a099965765b30c334849102ec9e176232aa81a5f1ece3d43e4cf"),
    (0x389570, 296, "80a22b0f6a8a0058be3f2026986ae0fdd52dbf9de6117f1c6183ae22a63ee9c3"),
    (0x6365e0, 296, "df0b3b44640746e36d5d56678db92eed3831d554d72da12cea3bb17ebe2ff895"),
    (0x5835f0, 296, "0ea5e1f8bf620f91576c535f7402b9ee16ac76fd37ef54b4c31ccaf60c38a2d6"),
    (0x6373b0, 273, "b9048640958a382b606a6ac58e5a752f1088c8f65dbb831e26251ef44b6a5297"),
    (0x15137a0, 325, "72242c5fccdb7766627bbee82b30fbd7688d49bfe24ee385a59cf2970838b0c2"),
    (0x151f310, 197, "8b2cf4364dd79df128b129509f6e9235dc10ee2830a74ad4b82dc0310b7a8168"),
    (0x1527190, 59, "9dab2cd8ef064382195f31a42c974fbd4b1d400c8551bd5be29f7ceac033d0de"),
    # Full allocation/name-hash/loaded-slot publication: serialized _key is
    # independent of the caller's uint16 ordinal. +8 holds _stringKey; [held]
    # gives chars. Native lowercases a separate copy before hashing that name.
    (0x584c70, 564, "21c4c3911afc9919558ac3854e983046f9ec01cc1a1e9b9c2528dcc256b7734b"),
    (0x1513c80, 262, "bcdd8ef73569ee2988b7d787632eba8033f4b413a87cffa49e3d4ffc8229aee7"),
    (0x17b2e40, 211, "f3d477be63b6f7394b659c0fa66fa86a4a1bce1176e42c33e0ea76ed2dd23f03"),
    (0x17b30c9, 30, "838135748247702336f92eb3bf8c7e6a313d5708e41321480de6113ceb6d149a"),
    (0xc7b1580, 46, "971c09db41b86210b5435fe2c22658ffb7644d0c8c68b8cae5e502fb76fdcec4"),
    (0x25c6c00, 377, "4616e8c2283b2392fc6cd8fb8050d7b6e0b94bc3325b02044cc5d2d1106d4e12"),
)
COUNTER_WINDOW = (0xc7eff02, bytes.fromhex("48ff4748488947380fb78424880000006689475048895f08"))
# (vtable, complete object locator, type descriptor, class hierarchy, exact name)
TYPES = {
    "status": (0x558d868, 0x5db8d00, 0x6aad288, 0x5db8c30, ".?AVClientStatusActorComponent@pa@@"),
    "characterMetadata": (0x58fe780, 0x5ee2810, 0x6b76180, 0x5ee27d0, ".?AVCharacterInfoManager@pa@@"),
    "groupMetadata": (0x5a9ae18, 0x5f59898, 0x6bc5f98, 0x5f59858, ".?AVStatusGroupInfoManager@pa@@"),
    "statusMetadata": (0x5a9b6b8, 0x5f599d8, 0x6bc6038, 0x5f59998, ".?AVStatusInfoManager@pa@@"),
}
GLOBALS = {"characterMetadata": 0x6d69a48, "groupMetadata": 0x6d71b68, "statusMetadata": 0x6d69ae8}
HP_NAME_SLOT, HP_NAME = 0x59b86c0, 0x558d780
SUCCESS_FLAGS = ("typedHpIdentityObserved", "stableTwoSamples")
MAX_STRING_KEY_BYTES = 64


def image_address(base, length, rva, size):
    if not 0 <= rva <= length-size:
        raise ProbeError("HP fixed contract escaped the main image")
    return base+rva


def validate_code(reader, base, length):
    appearance.pointer(base, "module base")
    if type(length) is not int or not 0 < length <= core.MAX_IMAGE_SIZE or base+length >= 2**47:
        raise ProbeError("HP module extent exceeds bounds")
    for rva, size, digest in WINDOWS:
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "HP contract code")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ProbeError("HP code window differs from the pinned EXE")
    rva, expected = COUNTER_WINDOW
    if appearance.read(reader, image_address(base, length, rva, len(expected)), len(expected), "commit counter") != expected:
        raise ProbeError("HP commit-counter window differs")
    for rva in appearance.WORLD_ANCHORS:
        size = len(appearance.WORLD_PATTERN.split())
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "controlled world anchor")
        if (core.pattern(appearance.WORLD_PATTERN).fullmatch(raw) is None or
                rva+7+struct.unpack_from("<i", raw, 3)[0] != appearance.WORLD_GLOBAL):
            raise ProbeError("Controlled world anchors differ")
    for vt, col, desc, hierarchy, name in TYPES.values():
        expected_col = struct.pack("<6I", 1, 0, 0, desc, hierarchy, col)
        if (appearance.value(reader, image_address(base, length, vt-8, 8), "fixed type locator") != base+col or
                appearance.read(reader, image_address(base, length, col, 24), 24, "fixed primary COL") != expected_col or
                appearance.read(reader, image_address(base, length, desc+16, len(name)+1), len(name)+1, "fixed type name") != name.encode()+b"\0"):
            raise ProbeError("HP fixed type/primary locator differs")
        image_address(base, length, hierarchy, 1)
    if (appearance.value(reader, image_address(base, length, HP_NAME_SLOT, 8), "Hp name slot") != base+HP_NAME or
            appearance.read(reader, image_address(base, length, HP_NAME, 3), 3, "Hp name") != b"Hp\0"):
        raise ProbeError("Named Hp category evidence differs")


class Watch:
    def __init__(self, reader, base, length):
        self.reader, self.base, self.length, self.rows = reader, base, length, {}

    def get(self, address, size, label):
        if type(address) is not int or not 0x10000 <= address < 2**47-size:
            raise ProbeError(label+" address exceeds bounds")
        raw = appearance.read(self.reader, address, size, label)
        key = (address, size)
        if key in self.rows and self.rows[key][1] != raw:
            raise ProbeError(label+" changed during sample")
        self.rows[key] = (label, raw)
        return raw

    def value(self, address, label, fmt="<Q"):
        return struct.unpack(fmt, self.get(address, struct.calcsize(fmt), label))[0]

    def link(self, address, label):
        return appearance.pointer(self.value(address, label), label)

    def typed(self, address, kind):
        appearance.pointer(address, kind)
        vt = self.value(address, kind+" vtable")
        fixed = TYPES.get(kind)
        if fixed and vt != self.base+fixed[0]:
            raise ProbeError(kind+" exact vtable differs")
        image_address(self.base, self.length, vt-self.base-8, 16)
        col = self.value(vt-8, kind+" locator")
        image_address(self.base, self.length, col-self.base, 24)
        sig, off, cd, desc, hierarchy, selfrva = struct.unpack("<6I", self.get(col, 24, kind+" COL"))
        if (sig, off, cd, selfrva) != (1, 0, 0, col-self.base):
            raise ProbeError(kind+" complete primary locator differs")
        if fixed and (col-self.base, desc, hierarchy) != fixed[1:4]:
            raise ProbeError(kind+" exact type metadata differs")
        image_address(self.base, self.length, hierarchy, 1)
        name = fixed[4] if fixed else appearance.TYPES[kind]
        at = image_address(self.base, self.length, desc+16, len(name)+1)
        if self.get(at, len(name)+1, kind+" RTTI name") != name.encode()+b"\0":
            raise ProbeError(kind+" exact RTTI differs")
        return address

    def selected(self, data, index, count, stride, width, label):
        appearance.pointer(data, label+" array")
        if not 0 <= index < count <= 65536:
            raise ProbeError(label+" selected index exceeds bounds")
        return self.get(data+index*stride, width, label+" selected entry")

    def metadata(self, manager, key, label):
        count = self.value(manager+8, label+" key count", "<I")
        data = self.link(manager+0x58, label+" loaded table")
        if key == 0xffff:
            raise ProbeError(label+" key is the unavailable sentinel")
        raw = self.selected(data, key, count, 8, 8, label)
        return appearance.pointer(struct.unpack("<Q", raw)[0], label+" loaded record")

    def vector(self, address, label):
        data, count, cap = struct.unpack("<QII", self.get(address, 16, label+" descriptor"))
        if not 0 < count <= cap <= 65536:
            raise ProbeError(label+" count/capacity unavailable or exceeds bounds")
        appearance.pointer(data, label+" data")
        return data, count

    def finish(self):
        for (address, size), (label, raw) in self.rows.items():
            if appearance.read(self.reader, address, size, label+" reread") != raw:
                raise ProbeError(label+" changed during dependency reread")
        return [{"address": hex(at), "size": size, "field": label, "bytesHex": raw.hex()}
                for (at, size), (label, raw) in self.rows.items()]


def raw_string_key(watch, record, observed):
    holder = watch.link(record+8, "StatusInfo _stringKey holder")
    chars = watch.value(holder, "StatusInfo _stringKey chars")
    observed.update(rawStringKeyHolder=hex(holder), rawStringKeyAddress=hex(chars), rawStringKey=None,
                    rawStringKeyBytesHex="", rawStringKeyTerminated=False)
    raw = bytearray()
    for index in range(MAX_STRING_KEY_BYTES):
        value = watch.get(chars+index, 1, "StatusInfo _stringKey byte")
        if value == b"\0":
            observed["rawStringKeyTerminated"] = True
            observed["rawStringKey"] = raw.decode("ascii")
            if raw != b"Hp":
                raise ProbeError("Selected StatusInfo raw _stringKey is not exact Hp")
            return
        raw.extend(value)
        observed["rawStringKeyBytesHex"] = raw.hex()
    raise ProbeError("StatusInfo _stringKey has no NUL within the fixed bound")


def sample(reader, base, length, observed):
    watch = Watch(reader, base, length)
    observed["stage"] = "controlledActor"
    world = watch.link(base+appearance.WORLD_GLOBAL, "world root")
    manager = watch.typed(watch.link(world+0x30, "client manager"), "manager")
    user = watch.typed(watch.link(manager+0x58, "client user"), "user")
    actor = watch.typed(watch.link(manager+0x50, "controlled actor"), "actor")
    if (watch.value(user+0xd0, "first controlled child") != actor or watch.value(user+0xd8, "second controlled child") != actor
            or watch.value(actor+0xa0, "actor user backlink") != user):
        raise ProbeError("Controlled actor/user round trip differs")
    observed.update(controlledActor=hex(actor), stage="statusRoot")
    components = watch.link(actor+0x68, "actor component table")
    status = watch.typed(watch.link(components+0x20, "client status"), "status")
    if watch.value(status+8, "status owner") != actor:
        raise ProbeError("Status owner differs from the controlled actor")
    root = watch.link(status+0x18, "status root")
    if watch.value(root, "root owner") != status:
        raise ProbeError("Status root backlink differs")
    observed.update(status=hex(status), root=hex(root), stage="loadedMetadata")
    managers = {kind: watch.typed(watch.link(base+rva, kind+" global"), kind) for kind, rva in GLOBALS.items()}
    hp = watch.value(managers["statusMetadata"]+0xa0, "named Hp key", "<H")
    stat = watch.metadata(managers["statusMetadata"], hp, "Hp metadata")
    # _key is serialized separately from the manager ordinal. Identity instead
    # follows the exact loaded slot and its producer-proven _stringKey path.
    # Deliberately do not copy the native case normalization into this reader:
    # only the fixed literal Hp is admitted; other spellings stay unavailable.
    observed.update(hpKey=hp, statusMetadataRecord=hex(stat),
                    rawMetadataKeyU32=watch.value(stat, "StatusInfo serialized _key", "<I"))
    raw_string_key(watch, stat, observed)
    mode = watch.value(stat+0x11, "regenerate type", "<B")
    if mode == 0:
        raise ProbeError("Hp does not use the reviewed regenerate mapping")
    slot = watch.value(stat+0x14, "status map slot", "<I")
    character_key = watch.value(status+0x30, "status character key", "<H")
    character = watch.metadata(managers["characterMetadata"], character_key, "character metadata")
    group_key = watch.value(character+0x5b8, "character group key", "<H")
    group = watch.metadata(managers["groupMetadata"], group_key, "status group metadata")
    observed.update(hpKey=hp, characterKey=character_key, groupKey=group_key, metadataRegenerateType=mode, stage="mappedEntry")
    regen_data, regen_count = watch.vector(group+0x18, "regenerate key list")
    map_data, map_count = watch.vector(group+0x58, "regenerate index map")
    mapped = struct.unpack("<i", watch.selected(map_data, slot, map_count, 4, 4, "Hp profile map"))[0]
    root_data = watch.link(root+0x58, "root entries")
    root_count = watch.value(root+0x60, "root entry count", "<I")  # No invented capacity at +64.
    if not 0 <= mapped < root_count <= 65536:
        raise ProbeError("Mapped Hp root index is unavailable or outside bounds")
    if struct.unpack("<H", watch.selected(regen_data, mapped, regen_count, 2, 2, "regenerate Hp key"))[0] != hp:
        raise ProbeError("Regenerate list key differs from Hp")
    entry_address = root_data+mapped*0x90
    counter = watch.value(entry_address+0x48, "entry update counter")
    raw = watch.selected(root_data, mapped, root_count, 0x90, 0x90, "Hp root record")
    if struct.unpack_from("<H", raw)[0] != hp or struct.unpack_from("<Q", raw, 0x48)[0] != counter:
        raise ProbeError("Hp entry key or update counter differs")
    observed.update(mappedIndex=mapped, entryAddress=hex(entry_address), stage="dependencyReread")
    observed["entry"] = {"keyU16": hp, "raw90Hex": raw.hex(), "updateCounterU64": counter,
        **{name: struct.unpack_from("<q", raw, offset)[0] for name, offset in
           (("currentStoredI64", 8), ("baseI64", 0x18), ("normI64", 0x20), ("floorI64", 0x28), ("field30I64", 0x30))},
        "timingAndModeRaw": {hex(offset): raw[offset:offset+size].hex() for offset, size in
                             ((0x10, 8), (0x38, 8), (0x40, 8), (0x50, 2), (0x52, 1), (0x53, 1))}}
    observed["dependencies"] = watch.finish()
    if watch.value(entry_address+0x48, "entry update counter") != counter:
        raise ProbeError("Hp update counter changed after reread")
    observed.update(stage="complete", stableDuringSample=True)


def process_identity(reader):
    """Read creation/liveness from the existing VM_READ/query handle, no new handle."""
    c, w, kernel = core.c, core.w, core.k32
    kernel.GetProcessTimes.argtypes, kernel.GetProcessTimes.restype = [w.HANDLE]+[c.POINTER(w.FILETIME)]*4, w.BOOL
    kernel.GetExitCodeProcess.argtypes, kernel.GetExitCodeProcess.restype = [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL
    kernel.GetProcessId.argtypes, kernel.GetProcessId.restype = [w.HANDLE], w.DWORD
    def live():
        code = w.DWORD()
        if not kernel.GetExitCodeProcess(reader.handle, c.byref(code)) or code.value != 259:
            raise ProbeError("Reader's game process is no longer live")
    live()
    created, exited, kt, ut = (w.FILETIME() for _ in range(4))
    pid = kernel.GetProcessId(reader.handle)
    if not pid or not kernel.GetProcessTimes(reader.handle, *(c.byref(x) for x in (created, exited, kt, ut))):
        raise ProbeError("Reader process creation identity is unavailable")
    creation = (int(created.dwHighDateTime)<<32)|int(created.dwLowDateTime)
    if not creation or exited.dwHighDateTime or exited.dwLowDateTime:
        raise ProbeError("Reader process creation/exit timestamps are invalid")
    base, length, path = reader.module()
    live()
    return {"pid": int(pid), "creationTime100ns": str(creation), "moduleBase": base, "moduleSize": length, "imagePath": str(path)}


def reject(report, reason, state="unavailable"):
    report.update(state=state, reason=str(reason)[:2000], **{flag: False for flag in SUCCESS_FLAGS})
    return report


def collect(reader, base, length, *, identity=None, pause=time.sleep):
    identity = identity or (lambda: process_identity(reader))
    report = {"schemaVersion": 2, "mode": "typed-hp-single-entry-read-only", "state": "unavailable", "samples": [],
              **{flag: False for flag in SUCCESS_FLAGS}, "snapshotAtomic": False, "nativeFunctionsInvoked": False,
              "gameMemoryWritten": False, "heapScanned": False, "projectedCurrentVerified": False,
              "maximumVerified": False, "unitsVerified": False, "hudReady": False,
              "limitations": ["This is a bounded external observation, not an atomic game-thread snapshot or object-lifetime guarantee.",
                  "Only one metadata-mapped Hp record is read; unavailable records are not lazy-loaded or replaced by another actor.",
                  "Stored/timing/mode fields do not establish projected current, a HUD maximum, unit conversion or heart ratio.",
                  "Loading, death, mount/script states and changing entries can legitimately make this strict diagnostic unavailable."]}
    try:
        before = identity()
        if (type(before.get("pid")) is not int or before["pid"] <= 0 or not str(before.get("creationTime100ns", "")).isdigit()
                or int(before["creationTime100ns"]) <= 0 or (before.get("moduleBase"), before.get("moduleSize")) != (base, length)):
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
            raise ProbeError("Process identity or complete typed Hp samples changed")
        report.update(state="observed", typedHpIdentityObserved=True, stableTwoSamples=True)
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        reject(report, error, "unstable" if any(row.get("stableDuringSample") for row in report["samples"]) else "unavailable")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT/"runtime/typed-health.json")
    args = parser.parse_args()
    output = appearance.output_path(args.output)
    pid = args.pid
    if pid is None:
        rows = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"], text=True, encoding="utf-8", errors="replace")
        pids = re.findall(r'"CrimsonDesert\.exe","(\d+)"', rows, re.I)
        if len(pids) != 1:
            raise ProbeError("Require exactly one game process or explicit --pid")
        pid = int(pids[0])
    if pid <= 0:
        raise ProbeError("Invalid PID")
    profile, _ = core.load_profile()
    reader = core.Reader(pid)
    try:
        base, length, path = reader.module()
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-Item -LiteralPath '"+str(path).replace("'", "''")+"').VersionInfo.FileVersion"], text=True).strip()
        digest = appearance.file_digest(path)
        roster.validate_layout_build(profile, version, digest)
        report = collect(reader, base, length)
        try:
            if (report.get("process", {}).get("pid") != pid or process_identity(reader) != report.get("process")
                    or appearance.file_digest(path) != digest):
                reject(report, "Final reader process/module/EXE identity changed", "unstable")
        except (ProbeError, RuntimeError, OSError, ValueError) as error:
            reject(report, error, "unstable")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(), gameVersion=version, supportedExeSha256=digest,
                      contract={"codeWindowCount": len(WINDOWS)+1, "fixedTypeCount": len(TYPES), "namedCategory": "Hp"})
        appearance.write_report(output, report)
        print(json.dumps({"output": str(output), **{key: report.get(key) for key in
                         ("state", "reason", *SUCCESS_FLAGS, "hudReady", "gameMemoryWritten", "nativeFunctionsInvoked")}}, indent=2))
        return 0 if report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
