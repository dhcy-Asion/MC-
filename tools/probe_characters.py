"""External, read-only character diagnostic. Never injects or writes process memory.

Anchor facts use the pinned MIT-licensed gugi97/Trinity profile in config/.
See licenses/Trinity-MIT.txt. Requires 64-bit Python on Windows.
This reports observable manager/vital-chain evidence, never roster-registration support.
"""
from __future__ import annotations

import argparse
import ctypes as c
from ctypes import wintypes as w
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess

PIN = "e0d287e002a1947a74eacedc21b95bb021d9f5fe"
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config/character-probe-2976.json"
MAX_IMAGE_SIZE = 512 * 1024**2
if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
    raise RuntimeError("This read-only diagnostic requires 64-bit Python on Windows")
k32 = c.WinDLL("kernel32", use_last_error=True)
psapi = c.WinDLL("psapi", use_last_error=True)

class MBI(c.Structure):
    _fields_ = [("BaseAddress", c.c_void_p), ("AllocationBase", c.c_void_p),
                ("AllocationProtect", w.DWORD), ("PartitionId", w.WORD),
                ("RegionSize", c.c_size_t), ("State", w.DWORD),
                ("Protect", w.DWORD), ("Type", w.DWORD)]

class ModuleInfo(c.Structure):
    _fields_ = [("lpBaseOfDll", c.c_void_p), ("SizeOfImage", w.DWORD),
                ("EntryPoint", c.c_void_p)]

k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.OpenProcess.restype = w.HANDLE
k32.CloseHandle.argtypes = [w.HANDLE]
k32.CloseHandle.restype = w.BOOL
k32.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p,
                                  c.c_size_t, c.POINTER(c.c_size_t)]
k32.ReadProcessMemory.restype = w.BOOL
k32.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(MBI), c.c_size_t]
k32.VirtualQueryEx.restype = c.c_size_t
psapi.EnumProcessModulesEx.argtypes = [w.HANDLE, c.POINTER(w.HMODULE), w.DWORD,
                                      c.POINTER(w.DWORD), w.DWORD]
psapi.EnumProcessModulesEx.restype = w.BOOL
psapi.GetModuleInformation.argtypes = [w.HANDLE, w.HMODULE, c.POINTER(ModuleInfo), w.DWORD]
psapi.GetModuleInformation.restype = w.BOOL
psapi.GetModuleFileNameExW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
psapi.GetModuleFileNameExW.restype = w.DWORD

def pattern(text: str) -> re.Pattern:
    return re.compile(b"".join(b"." if tok in ("?", "??") else
                               re.escape(bytes([int(tok, 16)]))
                               for tok in text.split()), re.DOTALL)

def load_profile():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    if profile["source"]["commit"] != PIN:
        raise RuntimeError("Character profile differs from the reviewed source pin")
    expected = {f"source_client_{i}" for i in range(4)} | {"source_server", "stat_commit", "damage_apply"}
    entries = profile["anchors"]
    if len(entries) != len(expected) or {row["name"] for row in entries} != expected:
        raise RuntimeError("Character profile anchor set changed")
    rows = []
    for row in entries:
        tokens = row["pattern"].split()
        if not 8 <= len(tokens) <= 128 or not any(tok not in ("?", "??") for tok in tokens):
            raise RuntimeError("Unbounded or empty character signature")
        pattern(row["pattern"])
        offset = row["mov_offset"]
        if offset is not None and (not isinstance(offset, int) or not 0 <= offset <= len(tokens) - 7):
            raise RuntimeError("Invalid RIP-load offset")
        rows.append((row["name"], row["pattern"], offset))
    pattern(profile["world_root"]["pattern"])
    rows.append(("world_root", profile["world_root"]["pattern"], None))
    return profile, rows

def validate_build(profile, version, digest):
    if version != profile["game_version"] or digest != profile["game_sha256"]:
        raise RuntimeError("Game version/SHA256 differs from the locally checked build; diagnostic stopped before scanning")

def agreeing_slot(slots, required=4):
    return slots[0] if len(slots) == required and len(set(slots)) == 1 else None

def position_signature(reader, body, realm, base, length):
    table = reader.value(body + 0x68)
    transform = reader.value(table + 0x1a0) if table else None
    if not transform or reader.rtti(transform, base, length) != f".?AV{realm}TransformSyncActorComponent@pa@@":
        return None
    raw = reader.read(transform + 0xb4, 0x48)
    if not raw:
        return None
    xyz = struct.unpack_from("<3f", raw)
    sectors = struct.unpack_from("<2h", raw, 12)
    if not all(math.isfinite(v) and abs(v) < 1e8 for v in xyz) or any(abs(v) > 500 for v in sectors):
        return None
    return {"local_xyz": xyz, "sector_xz": sectors, "position_bytes": raw[:16].hex(),
            "parent_world_transform_resolved": False}

class Reader:
    def __init__(self, pid):
        # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION. No write/operation/create-thread rights.
        self.handle = k32.OpenProcess(0x10 | 0x400, False, pid)
        if not self.handle:
            raise c.WinError(c.get_last_error())

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def query(self, address):
        out = MBI()
        if k32.VirtualQueryEx(self.handle, address, c.byref(out), c.sizeof(out)) != c.sizeof(out):
            return None
        return out

    @staticmethod
    def readable(info):
        return info and info.State == 0x1000 and not info.Protect & 0x100 and (
            info.Protect & 0xff) in (2, 4, 8, 32, 64, 128)

    def read(self, address, size):
        if (not isinstance(address, int) or not isinstance(size, int) or
            address < 0x10000 or size <= 0 or size > 2**20 or address + size >= 2**47):
            return None
        end, cursor = address + size, address
        while cursor < end:
            info = self.query(cursor)
            if not self.readable(info):
                return None
            next_addr = int(info.BaseAddress) + info.RegionSize
            if next_addr <= cursor:
                return None
            cursor = min(end, next_addr)
        buf, got = c.create_string_buffer(size), c.c_size_t()
        if not k32.ReadProcessMemory(self.handle, address, buf, size, c.byref(got)) or got.value != size:
            return None
        return buf.raw

    def value(self, address, fmt="<Q"):
        data = self.read(address, struct.calcsize(fmt))
        return struct.unpack(fmt, data)[0] if data else None

    def module(self):
        mods, needed = (w.HMODULE * 4096)(), w.DWORD()
        if not psapi.EnumProcessModulesEx(self.handle, mods, c.sizeof(mods), c.byref(needed), 2):
            raise c.WinError(c.get_last_error())
        if needed.value > c.sizeof(mods):
            raise RuntimeError("Module inventory exceeded bounded capacity")
        for index in range(needed.value // c.sizeof(w.HMODULE)):
            name = c.create_unicode_buffer(32768)
            if not psapi.GetModuleFileNameExW(self.handle, mods[index], name, len(name)):
                continue
            if Path(name.value).name.lower() == "crimsondesert.exe":
                info = ModuleInfo()
                if not psapi.GetModuleInformation(self.handle, mods[index], c.byref(info), c.sizeof(info)):
                    raise c.WinError(c.get_last_error())
                return int(info.lpBaseOfDll), info.SizeOfImage, Path(name.value)
        raise RuntimeError("Main game module not found")

    def rtti(self, obj, base, length):
        vt = self.value(obj)
        if not vt or not base <= vt < base + length:
            return None
        col = self.value(vt - 8)
        raw = self.read(col, 24) if col else None
        if not raw:
            return None
        sig, off, ctor, typedesc, hierarchy, selfrva = struct.unpack("<6I", raw)
        if sig != 1 or not 0 < typedesc < length or col - selfrva != base:
            return None
        out = self.read(base + typedesc + 16, 192)
        if not out:
            return None
        name = out.split(b"\0", 1)[0]
        return name.decode("ascii") if name and all(32 <= b < 127 for b in name) else None

def scan(reader, base, length, rows):
    compiled = [(name, pattern(sig), len(sig.split())) for name, sig, offset in rows]
    found = {name: [] for name, _, _ in rows}
    end, cursor, chunks, total = base + length, base, 0, 0
    max_len = max(n for _, _, n in compiled)
    while cursor < end:
        info = reader.query(cursor)
        if not info:
            cursor += 4096
            continue
        region_end = min(end, int(info.BaseAddress) + info.RegionSize)
        if region_end <= cursor:
            raise RuntimeError("Non-advancing memory region")
        if reader.readable(info):
            pos = cursor
            while pos < region_end:
                take = min(2**20, region_end - pos)
                raw = reader.read(pos, take)
                if raw:
                    chunks += 1
                    total += len(raw)
                    for name, regex, _ in compiled:
                        for match in regex.finditer(raw):
                            address = pos + match.start()
                            if address not in found[name] and len(found[name]) < 33:
                                found[name].append(address)
                if take <= max_len:
                    break
                pos += take - max_len + 1
        cursor = region_end
    return found, {"readable_bytes_scanned": total, "chunks": chunks}

def inspect_manager(reader, slot, base, length):
    handle = reader.value(slot)
    mgr = reader.value(handle) if handle else None
    if not mgr:
        return {"available": False, "reason": "manager double-pointer chain unavailable"}
    manager_type = reader.rtti(mgr, base, length)
    if manager_type != ".?AVServerActorManager@pa@@":
        return {"available": False, "rtti": manager_type,
                "reason": "Unsupported manager layout; only the checked ServerActorManager is decoded"}
    data, count = reader.value(mgr + 0xb8), reader.value(mgr + 0xc0, "<I")
    capacity = reader.value(mgr + 0xc4, "<I")
    result = {"available": False, "slot": hex(slot), "global_handle": hex(handle), "manager": hex(mgr),
              "rtti": manager_type, "count": count, "capacity": capacity}
    if not data or count is None or capacity is None or not 0 <= count <= capacity <= 8192:
        result["reason"] = "manager list bounds invalid"
        return result
    raw = reader.read(data, count * 8) if count else b""
    if raw is None:
        result["reason"] = "bounded list could not be read completely"
        return result
    records, classes = [], {}
    for idx in range(count):
        owner = struct.unpack_from("<Q", raw, idx * 8)[0]
        if owner < 0x10000000:
            continue
        cls = reader.rtti(owner, base, length) or "unknown"
        classes[cls] = classes.get(cls, 0) + 1
        type_desc = reader.value(owner + 0x88)
        tag = reader.value(type_desc + 1, "<B") if type_desc else None
        possessor = reader.value(owner + 0xa0)
        round_trip = bool(possessor and reader.value(possessor + 0xd0) == owner)
        actor = reader.value(owner + 0x68)
        marker = reader.value(actor + 0x20) if actor else None
        root = reader.value(marker + 0x18) if marker else None
        arr = reader.value(root + 0x58) if root else None
        stat = reader.read(arr, 0x38) if arr else None
        hp = None
        vital_back = bool(root and marker and reader.value(root) == marker)
        owner_back = bool(marker and reader.value(marker + 8) == owner)
        if stat and struct.unpack_from("<i", stat)[0] == 0:
            current, hp_base, norm, floor, cap = [struct.unpack_from("<q", stat, off)[0] for off in (8, 0x18, 0x20, 0x28, 0x30)]
            maximum = max(hp_base, cap)
            plausible = 0 <= current <= maximum <= 10**12 and maximum > 0 and current == hp_base + norm
            hp = {"current_raw": current, "base_raw": hp_base, "norm_raw": norm,
                  "floor_raw": floor, "cap_raw": cap, "maximum_candidate_raw": maximum,
                  "plausible": plausible}
        if round_trip or (tag in (1, 9)) or (hp and hp["plausible"] and vital_back and owner_back and "ChildOnlyInGameActor" in cls):
            records.append({"list_index": idx, "owner": hex(owner), "rtti": cls, "type_tag": tag,
                            "possessor": hex(possessor) if possessor else None,
                            "possessor_round_trip": round_trip, "actor": hex(actor) if actor else None,
                            "actor_rtti": reader.rtti(actor, base, length) if actor else None,
                            "marker_owner_back_link": owner_back, "vital_marker_back_link": vital_back,
                            "health_candidate": hp,
                            "position_signature": position_signature(reader, owner, "Server", base, length) if round_trip else None})
    result.update(available=True, class_counts=classes, candidates=records,
                  candidate_count=len(records), note="The manager lists gameplay owners, not native F1 menu entries."
                  )
    # The target keeps running: an external walk is not an atomic game-thread snapshot.
    result["list_stable_during_read"] = (
        reader.value(mgr + 0xb8) == data and reader.value(mgr + 0xc0, "<I") == count
        and reader.value(slot) == handle and reader.value(handle) == mgr)
    return result

def pointer_fields(reader, obj, size, base, length):
    raw = reader.read(obj, size) if obj else None
    if not raw:
        return []
    result = []
    for offset in range(0, size, 8):
        ptr = struct.unpack_from("<Q", raw, offset)[0]
        name = reader.rtti(ptr, base, length) if ptr >= 0x10000 else None
        if name:
            result.append({"offset": hex(offset), "pointer": hex(ptr), "rtti": name})
    return result

def one_typed_pointer(fields, exact_type):
    pointers = {int(row["pointer"], 16) for row in fields if row["rtti"] == exact_type}
    if len(pointers) != 1:
        raise RuntimeError(f"Require one distinct {exact_type}; found {len(pointers)}")
    return next(iter(pointers))

def inspect_client(reader, hits, base, length):
    result = {"available": False, "native_character_id_verified": False,
              "native_f1_roster_registration_verified": False}
    try:
        if not 2 <= len(hits) <= 32:
            raise RuntimeError("World root references did not meet bounded agreement requirement")
        slots = []
        for hit in hits:
            insn = reader.read(hit, 7)
            if not insn or insn[:3] != bytes.fromhex("48 8b 05"):
                raise RuntimeError("World root RIP-load is unreadable")
            slot = hit + 7 + struct.unpack_from("<i", insn, 3)[0]
            if not base <= slot <= base + length - 8:
                raise RuntimeError("World global escaped main module")
            slots.append(slot)
        slot = agreeing_slot(slots, required=len(hits))
        if slot is None:
            raise RuntimeError("World root references disagree")
        root = reader.value(slot)
        world_fields = pointer_fields(reader, root, 0x100, base, length)
        manager = one_typed_pointer(world_fields, ".?AVClientActorManager@pa@@")
        manager_fields = pointer_fields(reader, manager, 0x200, base, length)
        user = one_typed_pointer(manager_fields, ".?AVClientUserActor@pa@@")
        user_fields = pointer_fields(reader, user, 0x200, base, length)
        children = sorted({int(row["pointer"], 16) for row in user_fields
                           if row["rtti"] == ".?AVClientChildOnlyInGameActor@pa@@"})
        if not 1 <= len(children) <= 4:
            raise RuntimeError("Client child candidates exceeded bounded inventory")
        candidates = []
        for child in children:
            table = reader.value(child + 0x68)
            candidates.append({"pointer": hex(child),
                "user_back_link": reader.value(child + 0xa0) == user,
                "manager_pointer_match": reader.value(manager + 0x50) == child,
                "position_signature": position_signature(reader, child, "Client", base, length),
                "component_candidates": pointer_fields(reader, table, 0x300, base, length)})
        stable = (reader.value(slot) == root and reader.value(root + 0x30) == manager
                  and reader.value(manager + 0x58) == user)
        child = children[0] if len(children) == 1 else None
        unique = bool(stable and child and reader.value(user + 0xd0) == child
                      and reader.value(user + 0xd8) == child
                      and reader.value(manager + 0x50) == child and reader.value(child + 0xa0) == user)
        result.update(available=True, world_global_rva=hex(slot - base), world_root=hex(root),
            world_fields=world_fields, client_manager=hex(manager), client_manager_fields=manager_fields,
            client_user=hex(user), client_user_fields=user_fields, client_child_candidates=candidates,
            root_chain_stable=stable, unambiguous_child_chain=unique,
            note="Distinct user child pointers are reported without assigning character IDs or choosing the first match.")
    except RuntimeError as error:
        result["reason"] = str(error)
    return result

def correlate_positions(report):
    server = report["managers"].get("source_server", {})
    client = report["client_world_chain"]
    result = {"matches": [], "native_identity_verified": False,
              "note": "Same local position and sector support a body association; no parent transform or native character ID is established."}
    if not server.get("list_stable_during_read") or not client.get("root_chain_stable"):
        result["reason"] = "Managers changed during external reads or were unavailable"
        return result
    for body in server.get("candidates", []):
        sig = body.get("position_signature")
        if not (body["possessor_round_trip"] and body["marker_owner_back_link"]
                and body["vital_marker_back_link"] and sig):
            continue
        for child in client.get("client_child_candidates", []):
            other = child.get("position_signature")
            if (child["user_back_link"] and child["manager_pointer_match"] and other
                    and sig["position_bytes"] == other["position_bytes"]):
                result["matches"].append({"server_owner": body["owner"], "client_child": child["pointer"]})
    return result

def summary(report, output):
    client = report["client_world_chain"]
    return {"output": str(output), "mode": report["mode"],
            "game_version": report["game"]["version"], "game_sha256": report["game"]["sha256"],
            "anchor_matches": {name: row["count"] for name, row in report["anchors"].items()},
            "client_anchor_consensus": report["client_anchor_consensus"],
            "source_managers": {name: {"available": mgr.get("available", False), "rtti": mgr.get("rtti"),
                "scene_body_count": mgr.get("count"), "list_stable_during_read": mgr.get("list_stable_during_read"),
                "possessor_link_candidate_count": sum(bool(row["possessor_round_trip"]) for row in mgr.get("candidates", []))}
                for name, mgr in report["managers"].items()},
            "client_world_chain": {key: client.get(key) for key in
                ("available", "root_chain_stable", "unambiguous_child_chain", "reason")},
            "client_child_candidate_count": len(client.get("client_child_candidates", [])),
            "position_correlation_count": len(report["body_position_correlation"]["matches"]),
            "native_character_id_verified": False, "native_f1_roster_registration_verified": False}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/character-readonly-probe.json")
    parser.add_argument("--label", help="User-observed character name; does not establish a native character ID")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if not args.output.is_relative_to((ROOT / "runtime").resolve()) or args.output.suffix != ".json":
        raise RuntimeError("Raw diagnostic output must be a JSON file under this project's ignored runtime directory")
    pid = args.pid
    if pid is None:
        out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"], text=True, encoding="utf-8", errors="replace")
        matches = re.findall(r'"CrimsonDesert\.exe","(\d+)"', out, re.I)
        if len(matches) != 1:
            raise RuntimeError("Require exactly one running game process, or specify --pid")
        pid = int(matches[0])
    if pid <= 0:
        raise RuntimeError("Invalid process ID")
    profile, rows = load_profile()
    reader = Reader(pid)
    try:
        base, length, path = reader.module()
        if not 0 < length <= MAX_IMAGE_SIZE:
            raise RuntimeError("Unbounded main module image size")
        filehash = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(2**20), b""):
                filehash.update(block)
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
        validate_build(profile, version, filehash.hexdigest())
        found, stats = scan(reader, base, length, rows)
        report = {"time_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "pid": pid,
                  "mode": "external-read-only", "game": {"path": str(path), "version": version,
                  "sha256": filehash.hexdigest(), "module_base": hex(base), "module_size": length},
                  "source": {**profile["source"], "license_file": "licenses/Trinity-MIT.txt"}, "scan": stats,
                  "anchors": {}, "managers": {},
                  "character_label": {"value": args.label, "status": "user-observed label; native ID unverified"},
                  "roster_registration": {"verified": False, "reason": "No native creation/registration or F1 selection function is invoked by this probe."}}
        slots = []
        for name, _, offset in rows:
            hits = found[name]
            detail = {"count": len(hits), "matches_rva": [hex(addr - base) for addr in hits]}
            if offset is not None and len(hits) == 1:
                insn = reader.read(hits[0] + offset, 7)
                if insn and insn[:3] == b"\x48\x8b\x0d":
                    slot = hits[0] + offset + 7 + struct.unpack_from("<i", insn, 3)[0]
                    if base <= slot <= base + length - 8:
                        detail["global_rva"] = hex(slot - base)
                        if name.startswith("source_client_"):
                            slots.append(slot)
                        elif name == "source_server":
                            report["managers"]["source_server"] = inspect_manager(reader, slot, base, length)
            report["anchors"][name] = detail
        resolved = agreeing_slot(slots)
        if resolved:
            report["managers"]["source_client"] = inspect_manager(reader, resolved, base, length)
            report["client_anchor_consensus"] = True
        else:
            report["client_anchor_consensus"] = False
            report["managers"]["source_client"] = {"available": False, "reason": "Require all four unique agreeing anchors; no heuristic fallback."}
        report["client_world_chain"] = inspect_client(reader, found["world_root"], base, length)
        report["body_position_correlation"] = correlate_positions(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        for manager in report["managers"].values():
            manager["realm_label_from_source_only"] = True
        temp = args.output.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(args.output)
        print(json.dumps(summary(report, args.output), ensure_ascii=False, indent=2))
    finally:
        reader.close()

if __name__ == "__main__":
    main()
