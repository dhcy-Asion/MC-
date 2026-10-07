"""Install/restore the reviewed static oak-log probe with exact ownership checks.

Only an explicit --install writes the game. It requires the game to be closed,
the same EXE/archive snapshot, an empty overlay slot and complete local backups.
This is a temporary rendering probe, not the Minecraft/Steve integration.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import datetime as dt
import json
import os
from pathlib import Path
import re
import uuid

import prepare_asset_overlay as overlay
import prepare_native_steve as native

ROOT = native.ROOT
OWNER = "CrimsonMC static oak-log asset probe v1"
STEVE_OWNER = "CrimsonMC temporary Steve mesh-parameter probe v1"
RECEIPT = "runtime/asset-probe-active.json"
MARKER = ".crimsonmc-asset-probe-owner.json"
METADATA = ("meta/0.pathc", "meta/0.papgt")
MAX_SAVE_BYTES = 512 * 1024 * 1024
MAX_SAVE_FILES = 10000


def probe_owner(kind: str) -> str:
    if kind == "oak-log":
        return OWNER
    if kind == "steve-mesh-parameters":
        return STEVE_OWNER
    raise ValueError("Unsupported asset probe kind")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def game_running() -> bool:
    """Enumerate process names with Toolhelp; no process is opened or modified."""
    if os.name != "nt":
        raise ValueError("The game-process safety check requires Windows")
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Entry(); entry.dwSize = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(handle, ctypes.byref(entry))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        while ok:
            if entry.szExeFile.casefold() == "crimsondesert.exe":
                return True
            ok = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        return False
    finally:
        kernel.CloseHandle(handle)


def relative(value: object) -> str:
    path = overlay.virtual_path(value)
    if not re.fullmatch(r"[a-zA-Z0-9_./-]+", path):
        raise ValueError("Unsafe filesystem/virtual path in probe plan")
    return path


def target(root: Path, value: str) -> Path:
    path = root / relative(value)
    native.check_links(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Probe path escaped its root")
    return path


def atomic_write(path: Path, data: bytes, identity: str) -> None:
    native.check_links(path)
    temporary = path.with_name(path.name + f".crimsonmc-{identity}.tmp")
    native.check_links(temporary)
    if temporary.exists():
        raise ValueError("Probe temporary path already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if created and temporary.exists():
            native.check_links(temporary)
            temporary.unlink()


def static_paths() -> dict[str, str]:
    paths = {f"object/texture/crimsonmc_oak_log_atlas{suffix}.dds": "texture"
             for suffix in ("", "_n", "_sp")}
    for axis in "xyz":
        base = f"object/00_common/system/crimsonmc_oak_log_{axis}"
        binary = f"object/bin__/00_common/system/crimsonmc_oak_log_{axis}"
        paths.update({base + ".pam": "staticMesh", base + ".pamlod": "staticMeshLod",
                      base + ".pami": "material", base + ".hkx": "collision",
                      binary + ".meshinfo": "meshInfo", binary + ".prefab": "prefab"})
    return paths


def load_plan(plan: Path) -> dict:
    plan = native.output_directory(plan)
    report_path = target(plan, "reports/overlay-report.json")
    raw = report_path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Probe report is too large")
    report = json.loads(raw)
    if (report.get("schemaVersion") != 1 or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("cdmw", {}).get("commit") != native.CDMW_COMMIT):
        raise ValueError("Probe plan/source version is unsupported")
    name = report.get("directoryName")
    if not isinstance(name, str) or not re.fullmatch(r"[0-9]{4}", name) or not 36 <= int(name) <= 9999:
        raise ValueError("Unsafe overlay directory")
    rows = report.get("resources")
    expected = static_paths()
    if (not isinstance(rows, list) or len(rows) != 21
            or {r.get("virtualPath"): r.get("kind") for r in rows} != expected):
        raise ValueError("Probe accepts only the complete 21-resource static oak-log slice")
    wanted_files = {f"package/{name}/0.pamt", f"package/{name}/0.paz",
                    "metadata-before/0.papgt", "metadata-before/0.pathc",
                    "metadata-after/0.papgt", "metadata-after/0.pathc"}
    if set(report.get("files", {})) != wanted_files:
        raise ValueError("Probe package file set is unexpected")
    for path, digest in report["files"].items():
        if native.file_hash(target(plan, path)) != digest:
            raise ValueError(f"Probe package checksum changed: {path}")
    payloads = {}
    for row in rows:
        path = native.output_directory(ROOT / row["localFile"])
        data = path.read_bytes()
        if native.sha256(data) != row["sha256"]:
            raise ValueError("Probe candidate checksum changed")
        payloads[row["virtualPath"]] = data
    candidates = report.get("candidateReports", {})
    if not isinstance(candidates, dict) or len(candidates) != 1:
        raise ValueError("A static asset probe requires one exact candidate report")
    for path, digest in candidates.items():
        if native.file_hash(native.output_directory(ROOT / path)) != digest:
            raise ValueError("Probe candidate report changed")
    from probe_native_resources import load_assets
    candidate_path, candidate_digest = next(iter(candidates.items()))
    assets = load_assets(native.output_directory(ROOT / candidate_path))
    if assets["reportSha256"] != candidate_digest:
        raise ValueError("Probe candidate report changed during validation")
    verified = {r["path"]: r for r in assets["resources"].values() if r["path"] in expected}
    for row in rows:
        item = verified[row["virtualPath"]]
        if (item["sha256"] != row["sha256"] or
                (ROOT / row["localFile"]).resolve() != (Path(assets["reportPath"]).parent / item["localFile"]).resolve()):
            raise ValueError("Overlay resources differ from their verified candidate report")
    package = plan / "package" / name
    overlay.audit_package(package, rows, payloads)
    from cdmw.core.archive_format import parse_archive_pamt
    flags = {r["virtualPath"]: r["archiveFlags"] for r in rows}
    if any(e.flags != flags[e.path] for e in parse_archive_pamt(package / "0.pamt")):
        raise ValueError("Probe storage flags differ from the reviewed resource plan")
    before = {p: (plan / "metadata-before" / Path(p).name).read_bytes() for p in METADATA}
    after = {p: (plan / "metadata-after" / Path(p).name).read_bytes() for p in METADATA}
    overlay.audit_mounts(before["meta/0.papgt"], after["meta/0.papgt"], name,
                         (package / "0.pamt").read_bytes())
    textures = {p: d for p, d in payloads.items() if expected[p] == "texture"}
    for data in textures.values():
        overlay.validate_candidate_dds(data)
    overlay.audit_registry(before["meta/0.pathc"], after["meta/0.pathc"], textures)
    return {"plan": plan, "report": report, "reportSha256": native.sha256(raw),
            "probeVariant": assets["probeVariant"], "candidateReport": assets["reportPath"],
            "candidateReportSha256": assets["reportSha256"],
            "name": name, "package": package, "payloads": payloads,
            "before": before, "after": after}


def require_closed(game: Path, running) -> None:
    native.check_links(game)
    if running():
        raise ValueError("Close Crimson Desert before changing the asset probe")
    if native.file_hash(target(game, "bin64/CrimsonDesert.exe")) != native.EXE_SHA256:
        raise ValueError("Unsupported Crimson Desert EXE SHA")


def audit_sources(game: Path, report: dict) -> None:
    from cdmw.core.papgt_format import parse_papgt
    raw_sources = report["sourceIndexes"]
    if not isinstance(raw_sources, dict):
        raise ValueError("Invalid source index inventory")
    sources = {path.replace("\\", "/"): digest for path, digest in raw_sources.items()}
    if len(sources) != len(raw_sources):
        raise ValueError("Source index paths alias one another")
    absent = report.get("absentOptionalMountedDirectories", [])
    if not isinstance(absent, list) or len(set(absent)) != len(absent):
        raise ValueError("Invalid source index inventory")
    mount = parse_papgt((game / "meta/0.papgt").read_bytes())
    # The installed probe may now be mounted first. It is not a vanilla source.
    mount = tuple(r for r in mount if r.name != report["directoryName"])
    expected = {r.name + "/0.pamt" for r in mount if r.name not in absent}
    if set(sources) != expected or set(absent) - {r.name for r in mount if r.flags & 255 == 1}:
        raise ValueError("Source index inventory does not match the mounted archives")
    for path, digest in sources.items():
        if not re.fullmatch(r"[0-9]{4}/0\.pamt", path) or native.file_hash(target(game, path)) != digest:
            raise ValueError(f"Original source index changed: {path}")
    if any(target(game, name + "/0.pamt").exists() for name in absent):
        raise ValueError("An optional archive changed since rehearsal")


def tree_files(root: Path) -> list[Path]:
    native.check_links(root)
    if not root.is_dir():
        raise ValueError(f"Save directory is unavailable: {root}")
    result = []
    def refuse_walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=refuse_walk_error):
        for name in (*dirs, *files):
            native.check_links(Path(directory) / name)
        result.extend(Path(directory) / name for name in files)
    if len(result) > MAX_SAVE_FILES or sum(p.stat().st_size for p in result) > MAX_SAVE_BYTES:
        raise ValueError("Save backup exceeds the bounded probe limit")
    return sorted(result)


def discover_saves() -> list[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise ValueError("LOCALAPPDATA is unavailable; cannot locate the game saves")
    primary = Path(local) / "Pearl Abyss/CD/save"
    tree_files(primary)  # Missing primary save must stop rather than silently skip.
    roots = [primary]
    steam = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam/userdata"
    native.check_links(steam)
    if steam.exists():
        for account in sorted(steam.iterdir()):
            native.check_links(account)
            if account.is_dir() and account.name.isdigit():
                app = account / "3321460"
                if app.exists():
                    tree_files(app); roots.append(app)
    return roots


def backup_saves(roots: list[Path], backup: Path) -> list[dict]:
    records = []
    for index, root in enumerate(roots):
        paths = tree_files(root)
        before = {p.relative_to(root).as_posix(): native.file_hash(p) for p in paths}
        for path in paths:
            relative_name = path.relative_to(root).as_posix()
            destination = backup / "saves" / str(index) / relative_name
            native.check_links(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
            if native.file_hash(destination) != before[relative_name]:
                raise ValueError("Save backup differs from its source")
        if {p.relative_to(root).as_posix(): native.file_hash(p) for p in tree_files(root)} != before:
            raise ValueError("Saves changed during the probe backup")
        records.append({"source": str(root.resolve()), "files": before,
                        "backupDirectory": f"saves/{index}"})
    return records


def state_path(state_root: Path, path: str) -> Path:
    native.check_links(state_root)
    # Test-only state roots are isolated under build; no CLI changes this root.
    if state_root.resolve() != ROOT and not state_root.resolve().is_relative_to(ROOT / "build"):
        raise ValueError("Probe state must remain in this project or its build tests")
    return target(state_root, path)


def unchanged_game_files(game: Path) -> dict:
    result = {}
    for path in ("meta/0.papk", "meta/0.paver"):
        file = target(game, path)
        result[path] = native.file_hash(file) if file.exists() else None
    return result


def verify_owned_directory(game: Path, receipt: dict, *, partial: bool = False) -> None:
    directory = game / receipt["directoryName"]
    native.check_links(directory)
    wanted = {"0.pamt", "0.paz", MARKER}
    if directory.exists():
        contents = {p.name for p in directory.iterdir()}
        if contents - wanted or (not partial and contents != wanted):
            raise ValueError("Owned probe directory contains unexpected files")
    elif not partial:
        raise ValueError("Installed probe directory is missing")
    for path, digest in receipt["installedFiles"].items():
        file = target(game, path)
        if not file.exists() and partial:
            continue
        if not file.is_file() or native.file_hash(file) != digest:
            raise ValueError(f"Probe file was edited externally: {path}")


def archive_receipt(state_root: Path, receipt: dict, status: str) -> None:
    receipt = {**receipt, "status": status, "finishedAt": dt.datetime.now(dt.timezone.utc).isoformat()}
    history = state_path(state_root, "runtime/asset-probe-history/" + receipt["id"] + ".json")
    if history.exists():
        raise ValueError("Probe history already exists")
    active = state_path(state_root, RECEIPT)
    previous = active.read_bytes()
    final_data = json_bytes(receipt)
    history.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write(active, final_data, receipt["id"])
        # One same-volume rename removes active state and publishes history.
        # No separate history-write/active-unlink window can strand a retry.
        active.rename(history)
    except BaseException:
        if not active.exists() and history.is_file() and history.read_bytes() == final_data:
            # The rename committed, but interruption arrived before its caller
            # observed success. Do not re-install a completed removal.
            return
        if active.exists():
            atomic_write(active, previous, receipt["id"])
        raise


def _install_unlocked(plan_path: Path, game: Path, *, state_root: Path = ROOT,
            save_roots: list[Path] | None = None, running=game_running, _fault=None,
            probe_kind: str = "oak-log") -> dict:
    owner = probe_owner(probe_kind)
    game = game.absolute()
    require_closed(game, running)
    receipt_path = state_path(state_root, RECEIPT)
    if receipt_path.exists():
        raise ValueError("An active probe receipt exists; restore or inspect it first")
    if probe_kind == "oak-log":
        prepared = load_plan(plan_path)
    else:
        from install_steve_probe import load_plan as load_steve_plan
        prepared = load_steve_plan(plan_path)
    report, name = prepared["report"], prepared["name"]
    if (game / name).exists() or (game / ".cdmw").exists():
        raise ValueError("Probe directory or external CDMW management already exists")
    for path in METADATA:
        if target(game, path).read_bytes() != prepared["before"][path]:
            raise ValueError("Game metadata changed since the offline rehearsal")
    audit_sources(game, report)
    identity = uuid.uuid4().hex
    backup = state_path(state_root, "backups/asset-probe-" + identity)
    backup.mkdir(parents=True, exist_ok=False)
    marker_data = json_bytes({"owner": owner, "id": identity,
                              "planSha256": prepared["reportSha256"]})
    package_files = {name + "/0.pamt": (prepared["package"] / "0.pamt").read_bytes(),
                     name + "/0.paz": (prepared["package"] / "0.paz").read_bytes(),
                     name + "/" + MARKER: marker_data}
    backup_files = {}
    for path in METADATA:
        saved = target(backup, path)
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(prepared["before"][path])
        backup_files[path] = native.file_hash(saved)
        if backup_files[path] != native.sha256(prepared["before"][path]):
            raise ValueError("Metadata backup verification failed")
    saves = backup_saves(save_roots if save_roots is not None else discover_saves(), backup)
    receipt = {"format": "crimsonmc_asset_probe_v1", "owner": owner, "id": identity,
               "probeKind": probe_kind,
               "status": "installing", "gameRoot": str(game.resolve()), "directoryName": name,
               "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
               "plan": str(prepared["plan"]), "planSha256": prepared["reportSha256"],
               "probeVariant": prepared["probeVariant"], "candidateReport": prepared["candidateReport"],
               "candidateReportSha256": prepared["candidateReportSha256"],
               "backupRoot": str(backup.resolve()), "metadataBefore": backup_files,
               "metadataAfter": {p: native.sha256(d) for p, d in prepared["after"].items()},
               "installedFiles": {p: native.sha256(d) for p, d in package_files.items()},
               "sourceIndexes": report["sourceIndexes"],
               "absentOptionalMountedDirectories": report.get("absentOptionalMountedDirectories", []),
               "untouchedGameFiles": unchanged_game_files(game), "saveBackups": saves}
    atomic_write(receipt_path, json_bytes(receipt), identity)
    def fault(phase):
        if _fault is not None:
            _fault(phase)
    changed = {}
    directory_created = False
    try:
        require_closed(game, running)
        audit_sources(game, report)
        if (game / name).exists() or (game / ".cdmw").exists():
            raise ValueError("Probe namespace changed during backup")
        for path in METADATA:
            if target(game, path).read_bytes() != prepared["before"][path]:
                raise ValueError("Game metadata changed during backup")
        directory = game / name
        directory.mkdir(exist_ok=False)
        directory_created = True
        for path, data in package_files.items():
            atomic_write(target(game, path), data, identity)
            fault("package:" + Path(path).name)
        verify_owned_directory(game, receipt)
        overlay.audit_package(directory, report["resources"], prepared["payloads"])
        fault("package_verified")
        for path in METADATA:  # Publish the mount list last.
            require_closed(game, running)
            if target(game, path).read_bytes() != prepared["before"][path]:
                raise ValueError("Game metadata changed before publication")
            atomic_write(target(game, path), prepared["after"][path], identity)
            changed[path] = prepared["after"][path]
            fault("published:" + path)
        if any(target(game, p).read_bytes() != data for p, data in changed.items()):
            raise ValueError("Installed metadata failed read-back verification")
        receipt["status"] = "installed"
        atomic_write(receipt_path, json_bytes(receipt), identity)
        return receipt
    except BaseException as error:
        try:
            require_closed(game, running)
            # Never clobber an external edit even during recovery.
            actual_metadata = {p: target(game, p).read_bytes() for p in METADATA}
            for path, data in actual_metadata.items():
                if data not in (prepared["before"][path], prepared["after"][path]):
                    raise ValueError("Metadata changed externally during rollback")
            if directory_created:
                verify_owned_directory(game, receipt, partial=True)
            for path in reversed(METADATA):
                if actual_metadata[path] != prepared["before"][path]:
                    atomic_write(target(game, path), prepared["before"][path], identity)
            directory = game / name
            if directory_created and directory.exists():
                for child in directory.iterdir():
                    child.unlink()
                directory.rmdir()
            archive_receipt(state_root, receipt, "rolled_back")
        except BaseException as recovery:
            raise RuntimeError(f"Probe recovery stopped; preserve receipt and backup {backup}: {recovery}") from error
        raise


def _restore_unlocked(game: Path | None = None, *, state_root: Path = ROOT, running=game_running,
            _fault=None, probe_kind: str = "oak-log") -> dict:
    expected_owner = probe_owner(probe_kind)
    receipt_path = state_path(state_root, RECEIPT)
    data = receipt_path.read_bytes()
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Probe receipt is too large")
    receipt = json.loads(data)
    if (receipt.get("format") != "crimsonmc_asset_probe_v1" or receipt.get("owner") != expected_owner
            or receipt.get("probeKind", "oak-log") != probe_kind
            or not re.fullmatch(r"[0-9a-f]{32}", receipt.get("id", ""))
            or receipt.get("status") not in ("installed", "installing", "restored", "rolled_back")):
        raise ValueError("Probe receipt ownership or state is invalid")
    original_game = Path(receipt["gameRoot"])
    game = original_game if game is None else game
    if game.resolve() != original_game.resolve():
        raise ValueError("Probe receipt belongs to another game installation")
    require_closed(game, running)
    name = receipt["directoryName"]
    if not re.fullmatch(r"[0-9]{4}", name) or not 36 <= int(name) <= 9999:
        raise ValueError("Probe receipt directory is invalid")
    expected_files = {name + "/0.pamt", name + "/0.paz", name + "/" + MARKER}
    if set(receipt["installedFiles"]) != expected_files or set(receipt["metadataBefore"]) != set(METADATA):
        raise ValueError("Probe receipt file inventory is invalid")
    if set(receipt["metadataAfter"]) != set(METADATA):
        raise ValueError("Probe receipt metadata inventory is invalid")
    backup = state_path(state_root, "backups/asset-probe-" + receipt["id"])
    if backup.resolve() != Path(receipt["backupRoot"]).resolve():
        raise ValueError("Probe receipt backup ownership is invalid")
    before = {}
    terminal = receipt["status"] in ("restored", "rolled_back")
    for path in METADATA:
        saved = target(backup, path)
        if native.file_hash(saved) != receipt["metadataBefore"][path]:
            raise ValueError("Original metadata backup changed")
        before[path] = saved.read_bytes()
        actual = native.file_hash(target(game, path))
        permitted = {receipt["metadataBefore"][path]} if terminal else {receipt["metadataAfter"][path]}
        if receipt["status"] == "installing":
            permitted.add(receipt["metadataBefore"][path])
        if actual not in permitted:
            raise ValueError("Installed metadata was edited by another mod or game update")
    audit_sources(game, receipt)
    if unchanged_game_files(game) != receipt["untouchedGameFiles"] or (game / ".cdmw").exists():
        raise ValueError("Game metadata/management changed outside this probe")
    if terminal:
        if (game / name).exists():
            raise ValueError("Completed probe receipt still has a game directory")
        archive_receipt(state_root, receipt, receipt["status"])
        return {"status": "restored", "backupRoot": str(backup), "directoryName": name,
                "savesRestored": False, "note": "Completed the interrupted receipt archival."}
    verify_owned_directory(game, receipt, partial=receipt["status"] == "installing")
    marker = target(game, name + "/" + MARKER)
    if marker.exists():
        owner = json.loads(marker.read_bytes())
        if owner != {"owner": expected_owner, "id": receipt["id"], "planSha256": receipt["planSha256"]}:
            raise ValueError("Probe directory owner does not match its receipt")
    require_closed(game, running)
    old_metadata = {p: target(game, p).read_bytes() for p in METADATA}
    old_files = {p: target(game, p).read_bytes() for p in expected_files if target(game, p).exists()}
    original_status = receipt["status"]
    def fault(phase):
        if _fault is not None:
            _fault(phase)
    # Mark recovery state before unmounting; a hard stop can then be resumed.
    receipt["status"] = "installing"
    atomic_write(receipt_path, json_bytes(receipt), receipt["id"])
    deleted = []
    changed = {}
    try:
        # Unmount first, then remove texture registrations and owned payloads.
        for path in reversed(METADATA):
            require_closed(game, running)
            if target(game, path).read_bytes() != old_metadata[path]:
                raise ValueError("Metadata changed during restore")
            atomic_write(target(game, path), before[path], receipt["id"])
            changed[path] = before[path]
            fault("restored:" + path)
        directory = game / name
        if directory.exists():
            verify_owned_directory(game, receipt, partial=True)
            for path in old_files:
                target(game, path).unlink(); deleted.append(path)
                fault("removed:" + Path(path).name)
            directory.rmdir()
        if any(target(game, p).read_bytes() != value for p, value in before.items()):
            raise RuntimeError("Restored metadata does not match its backup")
        archive_receipt(state_root, receipt, "restored")
    except BaseException as error:
        try:
            require_closed(game, running)
            # Recreate only files deleted by this transaction, before remounting.
            verify_owned_directory(game, receipt, partial=True)
            for path, value in old_files.items():
                file = target(game, path)
                if not file.exists():
                    atomic_write(file, value, receipt["id"])
            for path in METADATA:
                actual = target(game, path).read_bytes()
                if actual not in (before[path], old_metadata[path]):
                    raise ValueError("Metadata changed externally during restore recovery")
                if actual != old_metadata[path]:
                    atomic_write(target(game, path), old_metadata[path], receipt["id"])
            receipt["status"] = original_status
            atomic_write(receipt_path, json_bytes(receipt), receipt["id"])
        except BaseException as recovery:
            raise RuntimeError(f"Restore recovery stopped; preserve receipt and backup {backup}: {recovery}") from error
        raise
    return {"status": "restored", "backupRoot": str(backup), "directoryName": name,
            "savesRestored": False, "note": "Probe removal does not overwrite later game saves."}


@contextmanager
def state_lock(state_root: Path):
    """An OS-held lock releases automatically after a hard process stop."""
    path = state_path(state_root, "runtime/asset-probe.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError("Another asset probe operation is active") from error
            unlock = lambda: (stream.seek(0), msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1))
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise ValueError("Another asset probe operation is active") from error
            unlock = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
        try:
            stream.seek(0)
            contents = stream.read()
            if contents not in (b"", b"CrimsonMC asset probe lock v1\n"):
                raise ValueError("Probe lock file is not owned by this project")
            if not contents:
                stream.write(b"CrimsonMC asset probe lock v1\n"); stream.flush()
            yield
        finally:
            unlock()


def install(plan_path: Path, game: Path, *, state_root: Path = ROOT,
            save_roots: list[Path] | None = None, running=game_running, _fault=None,
            probe_kind: str = "oak-log") -> dict:
    probe_owner(probe_kind)
    require_closed(game, running)
    with state_lock(state_root):
        return _install_unlocked(plan_path, game, state_root=state_root,
                                 save_roots=save_roots, running=running, _fault=_fault, probe_kind=probe_kind)


def restore(game: Path | None = None, *, state_root: Path = ROOT,
            running=game_running, _fault=None, probe_kind: str = "oak-log") -> dict:
    probe_owner(probe_kind)
    with state_lock(state_root):
        return _restore_unlocked(game, state_root=state_root, running=running, _fault=_fault, probe_kind=probe_kind)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true")
    action.add_argument("--restore", action="store_true")
    parser.add_argument("--plan", type=Path, default=ROOT / "build/native-asset-overlay")
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    native.load_cdmw(args.cdmw_source, args.deps)
    game = args.game_root
    if args.install and game is None:
        game = Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    result = install(args.plan, game) if args.install else restore(game)
    print(json.dumps({k: result[k] for k in ("status", "backupRoot", "directoryName")}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        raise SystemExit(f"Asset probe stopped: {error}") from error
