"""Observe loaded character catalogs and owned identities without changing the game.

This external diagnostic reuses probe_characters.Reader (query/read rights only).
The fixed offsets below are reviewed for one EXE SHA, not a creation API. Loaded
catalog entries, owned records and scene actors are never described as F1 entries.
All pointer-bearing evidence stays in the ignored runtime directory.
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

import probe_characters as core

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0.2976"
SHA256 = "57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7"
CATALOGS = {
    "character": (0x6D69A48, ".?AVCharacterInfoManager@pa@@", 0xC0),
    "mercenary": (0x6D69A60, ".?AVMercenaryInfoManager@pa@@", 0x78),
}
MAX_RECORDS = 65535
MAX_OWNED_RECORDS = 4096


def validate_layout_build(profile, version, digest):
    core.validate_build(profile, version, digest)
    if version != VERSION or digest != SHA256:
        raise RuntimeError("Catalog layout has not been reviewed for this EXE SHA")


def output_path(path):
    requested = Path(path).absolute()
    current = requested
    while current != current.parent:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise RuntimeError("Raw roster output cannot contain symlinks or junctions")
        if current == ROOT:
            break
        current = current.parent
    path = requested.resolve()
    # ROOT is already resolved. Resolving runtime as a second trust root would
    # incorrectly authorize a runtime junction pointing into a public directory.
    if not path.is_relative_to(ROOT / "runtime") or path.suffix != ".json":
        raise RuntimeError("Raw roster observations must be a JSON file under ignored runtime")
    return path


def describe_name(reader, record):
    obj = reader.value(record + 8)
    ptr = reader.value(obj) if obj else None
    raw = reader.read(ptr, 128) if ptr else None
    if raw is None or b"\0" not in raw:
        return None
    token = raw.split(b"\0", 1)[0]
    if not token or not all(32 <= value < 127 for value in token):
        return None
    if reader.value(record + 8) != obj or reader.value(obj) != ptr or reader.read(ptr, 128) != raw:
        raise RuntimeError("Catalog name chain changed during reads")
    return token.decode("ascii")


def catalog(reader, base, length, kind):
    rva, expected, record_size = CATALOGS[kind]
    if not 0 <= rva <= length - 8:
        raise RuntimeError("Catalog global escaped the main module")
    manager = reader.value(base + rva)
    actual = reader.rtti(manager, base, length) if manager else None
    if actual != expected:
        raise RuntimeError(f"{kind} manager RTTI mismatch: {actual}")
    count, directory = reader.value(manager + 8, "<I"), reader.value(manager + 0x58)
    if count is None or not 1 <= count <= MAX_RECORDS or not directory:
        raise RuntimeError(f"{kind} count/directory outside reviewed bounds")
    raw = reader.read(directory, count * 8)
    if raw is None:
        raise RuntimeError(f"{kind} complete bounded directory unavailable")
    rows, payloads, seen = [], [], set()
    for index, record in enumerate(struct.unpack(f"<{count}Q", raw)):
        if not record:
            continue  # Never invoke a lazy-load getter for an absent record.
        if record in seen:
            raise RuntimeError(f"{kind} directory aliases a loaded record")
        seen.add(record)
        data = reader.read(record, record_size)
        if data is None:
            raise RuntimeError(f"{kind} loaded record unreadable; partial catalog rejected")
        row = {"directory_index": index, "record": hex(record), "name": describe_name(reader, record)}
        if kind == "character":
            row.update(character_key_u32=struct.unpack_from("<I", data)[0],
                       mercenary_directory_index_u16=struct.unpack_from("<H", data, 0xBE)[0])
        else:
            row.update(mercenary_key_u8=data[0], mercenary_type_u8=data[0x20],
                       is_playable_u8=data[0x22], is_select_mercenary_spawn_u8=data[0x29],
                       group_key_u16=struct.unpack_from("<H", data, 0x72)[0],
                       f1_selectability_verified=False)
        rows.append(row)
        payloads.append((record, data))
    for record, data in payloads:
        if reader.read(record, len(data)) != data:
            raise RuntimeError(f"{kind} loaded record changed during reads")
    stable = (reader.value(base + rva) == manager and reader.rtti(manager, base, length) == actual
              and reader.value(manager + 8, "<I") == count and reader.value(manager + 0x58) == directory
              and reader.read(directory, count * 8) == raw)
    if not stable:
        raise RuntimeError(f"{kind} catalog changed during reads")
    return {"global_rva": hex(rva), "manager": hex(manager), "rtti": actual,
            "count": count, "directory": hex(directory), "loaded_count": len(rows),
            "stable_during_read": True, "records": rows, "absent_records_not_loaded": True,
            "f1_roster_verified": False}


def actor_identity(reader, actor, realm, base, length, catalogs):
    if realm not in ("Client", "Server"):
        raise RuntimeError("Unsupported actor realm")
    expected = f".?AV{realm}ChildOnlyInGameActor@pa@@"
    if reader.rtti(actor, base, length) != expected:
        raise RuntimeError(f"{realm} body RTTI differs from reviewed type")
    table = reader.value(actor + 0x68)
    status = reader.value(table + 0x20) if table else None
    status_type = f".?AV{realm}StatusActorComponent@pa@@"
    if not status or reader.rtti(status, base, length) != status_type:
        raise RuntimeError(f"{realm} status RTTI differs from reviewed type")
    if reader.value(status + 8) != actor:
        raise RuntimeError(f"{realm} status owner backlink mismatch")
    index = reader.value(status + 0x30, "<H")
    if index is None or not 0 <= index < catalogs["character"]["count"]:
        raise RuntimeError(f"{realm} character directory index outside catalog")
    record = next((row for row in catalogs["character"]["records"]
                   if row["directory_index"] == index), None)
    merc_index = record.get("mercenary_directory_index_u16") if record else None
    merc_record = next((row for row in catalogs["mercenary"]["records"]
                        if row["directory_index"] == merc_index), None)
    if (reader.rtti(actor, base, length) != expected or reader.value(actor + 0x68) != table
            or reader.value(table + 0x20) != status or reader.rtti(status, base, length) != status_type
            or reader.value(status + 8) != actor or reader.value(status + 0x30, "<H") != index):
        raise RuntimeError(f"{realm} body identity chain changed during reads")
    return {"actor": hex(actor), "realm": realm, "status": hex(status),
            "character_directory_index": index, "loaded_character_record": record,
            "character_key_u32": record.get("character_key_u32") if record else None,
            "mercenary_directory_index_u16": merc_index, "loaded_mercenary_record": merc_record,
            "loaded_catalog_mapping_available": record is not None,
            "native_control_identity_verified": False, "f1_selectability_verified": False}


def owned_server_records(reader, actor, base, length, catalogs):
    """Decode only the traced server layout; this is an owned list, not an F1 menu."""
    if reader.rtti(actor, base, length) != ".?AVServerChildOnlyInGameActor@pa@@":
        raise RuntimeError("Owned layout requires the reviewed server actor type")
    table = reader.value(actor + 0x68)
    component = reader.value(table + 0x110) if table else None
    actual = reader.rtti(component, base, length) if component else None
    # Same-SHA focus worker 0x294DA9B loads table+0x110 and calls
    # 0x214E7A0 -> 0xE4B8080, which reads precisely this directory layout.
    # Actual RTTI is Clan; it is not a subclass of the previously guessed name.
    if actual != ".?AVServerMercenaryClanActorComponent@pa@@":
        return {"available": False, "reason": "Server mercenary component RTTI mismatch", "actual_type": actual}
    if reader.value(component + 8) != actor:
        return {"available": False, "reason": "Server mercenary owner backlink mismatch"}
    count, array = reader.value(component + 0x20, "<I"), reader.value(component + 0x18)
    if count is None or not 0 <= count <= MAX_OWNED_RECORDS or (count and not array):
        return {"available": False, "reason": "Owned record count/pointer outside reviewed bounds"}
    raw = reader.read(array, count * 8) if count else b""
    if raw is None:
        return {"available": False, "reason": "Complete bounded owned-record directory unavailable"}
    rows, payloads, seen = [], [], set()
    labels = {row["directory_index"]: row for row in catalogs["character"]["records"]}
    for index in range(count):
        record = struct.unpack_from("<Q", raw, index * 8)[0]
        if not record or record in seen:
            return {"available": False, "reason": "Null/aliased owned record; partial interpretation rejected"}
        seen.add(record)
        data = reader.read(record, 0x58)
        if data is None:
            return {"available": False, "reason": "Owned-record payload unavailable; partial interpretation rejected"}
        char_index = struct.unpack_from("<H", data, 0x20)[0]
        if char_index != 0xFFFF and not 0 <= char_index < catalogs["character"]["count"]:
            return {"available": False, "reason": "Owned character index outside catalog; partial interpretation rejected"}
        label = labels.get(char_index)
        rows.append({"record_index": index, "record": hex(record), "character_directory_index": char_index,
                     "character_key_u32": label.get("character_key_u32") if label else None,
                     "character_name": label.get("name") if label else None,
                     "owned_mercenary_no_i64": struct.unpack_from("<q", data, 0x28)[0],
                     "actor_handle_u32": struct.unpack_from("<I", data, 0x50)[0],
                     "invalid_character_index_sentinel": char_index == 0xFFFF})
        payloads.append((record, data))
    stable = (reader.rtti(actor, base, length) == ".?AVServerChildOnlyInGameActor@pa@@"
              and reader.value(actor + 0x68) == table and reader.value(table + 0x110) == component
              and reader.rtti(component, base, length) == actual and reader.value(component + 8) == actor
              and reader.value(component + 0x20, "<I") == count and reader.value(component + 0x18) == array
              and (reader.read(array, count * 8) if count else b"") == raw
              and all(reader.read(record, len(data)) == data for record, data in payloads))
    return {"available": stable, "stable_during_read": stable, "component": hex(component),
            "rtti": actual, "count": count, "records": rows if stable else [],
            "f1_roster_verified": False,
            **({} if stable else {"reason": "Owned directory/payload/owner changed during reads"})}


def collect(reader, base, length, scan_rows):
    catalogs = {kind: catalog(reader, base, length, kind) for kind in CATALOGS}
    found, stats = core.scan(reader, base, length, scan_rows)
    client = core.inspect_client(reader, found["world_root"], base, length)
    identities, server_observations = [], []
    if client.get("available") and client.get("root_chain_stable"):
        user, manager = int(client["client_user"], 16), int(client["client_manager"], 16)
        for child in client["client_child_candidates"]:
            actor = int(child["pointer"], 16)
            if not child["user_back_link"]:
                continue
            ident = actor_identity(reader, actor, "Client", base, length, catalogs)
            ident.update(user_offsets=[hex(offset) for offset in (0xD0, 0xD8) if reader.value(user + offset) == actor],
                         client_manager_pointer_match=reader.value(manager + 0x50) == actor,
                         user_back_link=reader.value(actor + 0xA0) == user)
            identities.append(ident)
        if (reader.value(int(client["world_root"], 16) + 0x30) != manager
                or reader.value(manager + 0x58) != user):
            raise RuntimeError("Client root changed during identity collection")
    if len(found["source_server"]) == 1:
        offset = next(row[2] for row in scan_rows if row[0] == "source_server")
        address = found["source_server"][0] + offset
        instr = reader.read(address, 7)
        if instr and instr[:3] == b"\x48\x8b\x0d":
            slot = address + 7 + struct.unpack_from("<i", instr, 3)[0]
            if not base <= slot <= base + length - 8:
                raise RuntimeError("Server manager global escaped the main module")
            server = core.inspect_manager(reader, slot, base, length)
            if server.get("available") and server.get("list_stable_during_read"):
                for body in server.get("candidates", []):
                    if body["possessor_round_trip"] and body["rtti"] == ".?AVServerChildOnlyInGameActor@pa@@":
                        actor = int(body["owner"], 16)
                        identity = actor_identity(reader, actor, "Server", base, length, catalogs)
                        identity["owned_records"] = owned_server_records(reader, actor, base, length, catalogs)
                        if reader.value(int(body["possessor"], 16) + 0xD0) != actor:
                            raise RuntimeError("Server possessor changed during identity collection")
                        server_observations.append(identity)
    return {"catalogs": catalogs, "client_chain": client, "actor_identity_observations": identities,
            "server_possessor_identity_observations": server_observations, "scan": stats,
            "native_functions_invoked": False, "game_memory_written": False,
            "native_control_identity_verified": False, "native_f1_roster_verified": False,
            "new_character_registration_verified": False,
            "snapshot_atomic": False,
            "note": "Stable external reads are observations; catalog/owned/scene counts are not F1 menu size."}


def summary(report, output):
    def identity(row):
        return {key: row.get(key) for key in ("realm", "character_directory_index", "character_key_u32",
                                             "loaded_catalog_mapping_available", "client_manager_pointer_match")}
    return {"output": str(output), "mode": "external-read-only", "game_version": report["game"]["version"],
            "game_sha256": report["game"]["sha256"],
            "catalog_counts": {key: {name: cat[name] for name in ("count", "loaded_count", "stable_during_read")}
                               for key, cat in report["catalogs"].items()},
            "client_identity_observations": [identity(row) for row in report["actor_identity_observations"]],
            "server_identity_observations": [identity(row) for row in report["server_possessor_identity_observations"]],
            "owned_list_observations": [{key: row["owned_records"].get(key) for key in ("available", "count", "reason")}
                                         for row in report["server_possessor_identity_observations"]],
            "native_control_identity_verified": False, "native_f1_roster_verified": False,
            "new_character_registration_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="running game PID; otherwise require exactly one game process")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/character-roster.json")
    args = parser.parse_args()
    output = output_path(args.output)  # Reject public output before opening a process.
    pid = args.pid
    if pid is None:
        raw = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"],
                                      text=True, encoding="utf-8", errors="replace")
        matches = re.findall(r'"CrimsonDesert\.exe","(\d+)"', raw, re.I)
        if len(matches) != 1:
            raise RuntimeError("Require exactly one running game process or explicit --pid")
        pid = int(matches[0])
    if pid <= 0:
        raise RuntimeError("Invalid process ID")
    profile, rows = core.load_profile()
    reader = core.Reader(pid)
    try:
        base, length, path = reader.module()
        if not 0 < length <= core.MAX_IMAGE_SIZE:
            raise RuntimeError("Main image exceeds reviewed bounds")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(2**20), b""):
                digest.update(block)
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-Item -LiteralPath '" + str(path).replace("'", "''") + "').VersionInfo.FileVersion"], text=True).strip()
        validate_layout_build(profile, version, digest.hexdigest())
        report = collect(reader, base, length, rows)
        report.update(time_utc=dt.datetime.now(dt.timezone.utc).isoformat(), mode="external-read-only",
                      game={"pid": pid, "path": str(path), "version": version, "sha256": digest.hexdigest()})
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(output)
        print(json.dumps(summary(report, output), ensure_ascii=False, indent=2))
    finally:
        reader.close()


if __name__ == "__main__":
    main()
