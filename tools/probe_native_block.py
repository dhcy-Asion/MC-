"""Spawn one journalled, removable native asset diagnostic, never an MC block.

After the separately reviewed asset overlay is installed, use --spawn (axis=y
by default) and --cleanup. Only the existing loopback game-thread API is used.
Registry admission, physical ground evidence and visual acceptance are separate;
the HTTP API exposes no per-object native-live flag. No NPC/player/camera writes,
production bridge calls, inventory changes, explicit project saves or autoload
changes. Native SpawnAt may create an empty Untitled project and save settings
through EnsureEditingProject; those implicit side effects are recorded, retained
and never removed by this diagnostic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
import uuid

import prepare_native_steve as native

ROOT = native.ROOT
PROJECT = "CrimsonMCAssetProbe"
VERSION = "1.0.0.2976"
PREFABS = {axis: f"/object/00_common/system/crimsonmc_oak_log_{axis}.prefab" for axis in "xyz"}
MAX_RESPONSE = 2 * 1024 * 1024
MAX_OBJECTS = 5000
ASSET_OWNER = "CrimsonMC static oak-log asset probe v1"
ASSET_MARKER = ".crimsonmc-asset-probe-owner.json"
PROBE_VARIANTS = ("static-oak-log", "blue-template-alias", "blue-material-alias")


class ProbeError(RuntimeError):
    pass


class RequestFailure(ProbeError):
    """No complete response; a mutation might already have been accepted."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def game_instance() -> dict:
    """Identify one actual game process with query-only Windows handles.

    No VM read/write, injection, remote threads or guessed engine layout.
    PID alone is insufficient because Windows and the adapter reuse IDs.
    """
    if os.name != "nt":
        raise ProbeError("A Windows game process identity is required for this diagnostic")
    import ctypes as c
    from ctypes import wintypes as w

    class ProcessEntry(c.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                    ("th32DefaultHeapID", c.c_size_t), ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                    ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD),
                    ("szExeFile", w.WCHAR * 260)]

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes, kernel.CreateToolhelp32Snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [w.HANDLE, c.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = w.BOOL
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = w.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS only.
    if not snapshot or snapshot == c.c_void_p(-1).value:
        raise ProbeError("Cannot enumerate the actual game process")
    pids = []
    try:
        entry = ProcessEntry()
        entry.dwSize = c.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, c.byref(entry))
        count = 0
        while found:
            count += 1
            if count > 65536:
                raise ProbeError("Process enumeration exceeded its bounded capacity")
            if entry.szExeFile.casefold() == "crimsondesert.exe":
                pids.append(int(entry.th32ProcessID))
            found = kernel.Process32NextW(snapshot, c.byref(entry))
        if c.get_last_error() != 18:  # ERROR_NO_MORE_FILES.
            raise ProbeError("Process enumeration did not complete")
    finally:
        kernel.CloseHandle(snapshot)
    if len(pids) != 1:
        raise ProbeError("Exactly one CrimsonDesert.exe instance must be running")
    handle = kernel.OpenProcess(0x1000, False, pids[0])  # PROCESS_QUERY_LIMITED_INFORMATION only.
    if not handle:
        raise ProbeError("Cannot open query-only game process identity")
    try:
        created, exited, kernel_time, user_time = (w.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, c.byref(created), c.byref(exited), c.byref(kernel_time), c.byref(user_time)):
            raise ProbeError("Cannot read game process creation time")
        buffer, size = c.create_unicode_buffer(32768), w.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(size)):
            raise ProbeError("Cannot verify actual game process image")
        image = Path(buffer.value)
        if image.name.casefold() != "crimsondesert.exe" or native.file_hash(image) != native.EXE_SHA256:
            raise ProbeError("Running game process image does not match the fixed EXE SHA")
        creation = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return {"pid": pids[0], "creationTime100ns": str(creation),
                "imagePath": str(image.resolve()), "imageSha256": native.EXE_SHA256,
                "access": "PROCESS_QUERY_LIMITED_INFORMATION"}
    finally:
        kernel.CloseHandle(handle)


def finite(value: object, name: str, limit: float = 1_000_000) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
        raise ProbeError(f"{name} must be a bounded finite number")
    return float(value)


def positive_int(value: object, name: str) -> int:
    if type(value) is not int or not 0 < value <= 2147483646:
        raise ProbeError(f"{name} must be a positive integer")
    return value


def strict_json(data: bytes) -> dict:
    try:
        value = json.loads(data.decode("utf-8"), parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
    except (ValueError, UnicodeError) as error:
        raise RequestFailure("API did not return strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise RequestFailure("API response must be a JSON object")
    return value


def project_settings(instance: dict) -> dict:
    """Read the running installation's settings, without changing the file.

    HTTP has no editing-project/autosave read endpoint. UI changes SaveSettings,
    so this is a disk observation, not a claim to expose live engine fields.
    Require an explicit disabled autosave setting before a transient admission.
    """
    path = Path(instance["imagePath"]).parent / "cdmodkit/settings.txt"
    native.check_links(path)
    if not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ProbeError("Cannot observe the actual installation's bounded settings file")
    data = path.read_bytes()
    # Match LoadSettings's exact key/value and trailing CR/space handling.
    values = {}
    for line in data.decode("utf-8", errors="strict").split("\n"):
        line = line.rstrip("\r ")
        if "=" in line:
            key, value = line.split("=", 1)
            if key in ("project_autosave", "editing_project"):
                values[key] = value
    if values.get("project_autosave") not in ("0", "off", "false"):
        raise ProbeError("Explicit project_autosave=0 is required before a transient native probe; settings were not changed")
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
            "projectAutoSave": False, "editingProjectOnDisk": values.get("editing_project"),
            "observation": "settings disk snapshot; HTTP does not expose the live editing project"}


def installed_assets(instance: dict, axis: str) -> dict:
    """Bind admission to the installed bytes, never a caller-supplied label.

    This is a read-only check. Restoration/cleanup deliberately do not call it.
    Import the candidate validator lazily because it reuses game_instance here.
    """
    import probe_native_resources as resources

    def decode(data: bytes) -> dict:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("Duplicate asset evidence field")
                result[key] = value
            return result
        try:
            value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                               parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
        except (ValueError, UnicodeError) as error:
            raise ProbeError("Installed asset evidence must be strict unique-field JSON") from error
        if not isinstance(value, dict):
            raise ProbeError("Installed asset evidence must be a JSON object")
        return value

    def read(path: Path, maximum: int = MAX_RESPONSE) -> bytes:
        native.check_links(path)
        if not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise ProbeError("Installed asset evidence is missing or exceeds its bounded size: " + str(path))
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        if not 0 < len(data) <= maximum:
            raise ProbeError("Installed asset evidence changed size while reading")
        return data

    def digest(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ProbeError("Installed asset SHA256 is invalid")
        return value

    def build_path(value: object) -> Path:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ProbeError("Installed asset plan/report must be an absolute build path")
        path = Path(os.path.abspath(value))
        native.check_links(path)
        if not path.is_relative_to(ROOT / "build") or path == ROOT / "build":
            raise ProbeError("Installed asset plan/report must remain inside ignored build")
        return path

    receipt_path = ROOT / "runtime/asset-probe-active.json"
    raw = read(receipt_path)
    receipt = decode(raw)
    if (receipt.get("format") != "crimsonmc_asset_probe_v1" or receipt.get("owner") != ASSET_OWNER
            or receipt.get("status") != "installed" or not isinstance(receipt.get("id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", receipt["id"])):
        raise ProbeError("A current owned installed asset receipt is required")
    image = Path(instance["imagePath"])
    if (instance.get("imageSha256") != native.EXE_SHA256 or image.name.casefold() != "crimsondesert.exe"
            or image.parent.name.casefold() != "bin64"):
        raise ProbeError("Running game installation identity is invalid")
    game = image.parent.parent.resolve()
    native.check_links(game)
    root_value = receipt.get("gameRoot")
    if not isinstance(root_value, str) or not Path(root_value).is_absolute():
        raise ProbeError("Installed receipt gameRoot is invalid")
    native.check_links(Path(root_value))
    if Path(root_value).resolve() != game:
        raise ProbeError("Installed asset receipt belongs to another gameRoot")
    plan = build_path(receipt.get("plan"))
    plan_raw = read(plan / "reports/overlay-report.json")
    plan_sha = hashlib.sha256(plan_raw).hexdigest()
    if plan_sha != digest(receipt.get("planSha256")):
        raise ProbeError("Installed overlay plan SHA256 differs from its receipt")
    overlay = decode(plan_raw)
    candidate = build_path(receipt.get("candidateReport"))
    candidate_sha = digest(receipt.get("candidateReportSha256"))
    candidate_raw = read(candidate)
    if hashlib.sha256(candidate_raw).hexdigest() != candidate_sha:
        raise ProbeError("Installed candidate report SHA256 differs from its receipt")
    declared_reports = overlay.get("candidateReports")
    expected_report = str(candidate.relative_to(ROOT))
    if declared_reports != {expected_report: candidate_sha}:
        raise ProbeError("Installed overlay must bind exactly its one candidate report")
    try:
        assets = resources.load_assets(candidate)
    except resources.ProbeError as error:
        raise ProbeError("Candidate resource validation failed: " + str(error)) from error
    variant = assets.get("probeVariant")
    if variant not in PROBE_VARIANTS or receipt.get("probeVariant") != variant:
        raise ProbeError("Installed probe variant differs from validated candidate resources")
    if variant != "static-oak-log" and axis != "y":
        raise ProbeError(f"The {variant} control supports only axis y")
    if assets.get("reportSha256") != candidate_sha:
        raise ProbeError("Candidate report changed during installed asset validation")
    name = receipt.get("directoryName")
    if (not isinstance(name, str) or not re.fullmatch(r"[0-9]{4}", name) or not 36 <= int(name) <= 9999
            or overlay.get("directoryName") != name or overlay.get("schemaVersion") != 1
            or overlay.get("supportedExeSha256") != native.EXE_SHA256):
        raise ProbeError("Installed overlay directory/version differs from its receipt")
    expected = {row["path"]: row for key, row in assets["resources"].items() if key.startswith("oak_")}
    rows = overlay.get("resources")
    if not isinstance(rows, list) or len(rows) != 21 or len(expected) != 21:
        raise ProbeError("Installed overlay needs exactly the validated 21 resources")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("virtualPath"), str)
                or row["virtualPath"] not in expected or row["virtualPath"] in seen):
            raise ProbeError("Installed overlay resource set differs from candidate resources")
        seen.add(row["virtualPath"])
        wanted = expected[row["virtualPath"]]
        local = row.get("localFile")
        if (not isinstance(local, str) or Path(local).is_absolute() or ".." in Path(local).parts
                or Path(os.path.abspath(ROOT / local)) != candidate.parent / wanted["localFile"]
                or row.get("sha256") != wanted["sha256"]):
            raise ProbeError("Installed overlay payload differs from validated candidate resources")
    files = overlay.get("files")
    package_names = (name + "/0.pamt", name + "/0.paz", name + "/" + ASSET_MARKER)
    installed = receipt.get("installedFiles")
    metadata = receipt.get("metadataAfter")
    if (not isinstance(files, dict) or not isinstance(installed, dict) or set(installed) != set(package_names)
            or not isinstance(metadata, dict) or set(metadata) != {"meta/0.pathc", "meta/0.papgt"}):
        raise ProbeError("Installed asset file inventory is incomplete or polluted")
    directory = game / name
    native.check_links(directory)
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != {"0.pamt", "0.paz", ASSET_MARKER}:
        raise ProbeError("Installed asset package contains unexpected files")
    for relative, sha in {**installed, **metadata}.items():
        path = game / relative
        native.check_links(path)
        if not path.is_file() or native.file_hash(path) != digest(sha):
            raise ProbeError("Installed package/metadata SHA256 differs: " + relative)
        if relative.endswith(ASSET_MARKER):
            continue
        source = ("package/" + relative) if relative.startswith(name + "/") else "metadata-after/" + Path(relative).name
        if files.get(source) != sha:
            raise ProbeError("Installed package/metadata is not the bound overlay plan")
    marker = decode(read(directory / ASSET_MARKER, 4096))
    if marker != {"owner": ASSET_OWNER, "id": receipt["id"], "planSha256": plan_sha}:
        raise ProbeError("Installed asset ownership marker differs from receipt")
    # Detect receipt/report changes across the read-only verification window.
    if read(receipt_path) != raw or read(candidate) != candidate_raw or read(plan / "reports/overlay-report.json") != plan_raw:
        raise ProbeError("Installed asset identity changed during verification")
    return {"probeVariant": variant, "assetReceipt": {
        "path": str(receipt_path), "sha256": hashlib.sha256(raw).hexdigest(), "id": receipt["id"],
        "gameRoot": str(game), "directoryName": name, "plan": str(plan), "planSha256": plan_sha,
        "candidateReport": str(candidate), "candidateReportSha256": candidate_sha,
        "probeVariant": variant}}


class LoopbackAPI:
    def __init__(self, base: str = "http://127.0.0.1:8765", role: str = "native", timeout: float = 4):
        parts = urlsplit(base)
        try:
            port = parts.port
        except ValueError as error:
            raise ProbeError("Invalid loopback API port") from error
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or not port
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment or role not in ("native", "mc")):
            raise ProbeError("Only a literal HTTP 127.0.0.1 loopback API is allowed")
        self.base = f"http://127.0.0.1:{port}"
        self.role, self.timeout = role, min(4.0, max(0.1, finite(timeout, "request timeout", 30)))
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
        # A closed method/path set prevents this diagnostic from becoming a
        # generic game-memory, movement, production inventory or remote client.
        allowed = self.role == "mc" and (method, path) == ("GET", "/api/state")
        if self.role == "native":
            allowed = ((method, path) in {("GET", "/api/status"), ("GET", "/api/player"), ("GET", "/api/camera"), ("GET", "/api/projects"),
                                        ("POST", "/api/prototype/ground-probe"), ("POST", "/api/objects")}
                       or method == "GET" and re.fullmatch(r"/api/prototype/ground-result\?ticket=[1-9][0-9]*", path) is not None
                       or method == "GET" and re.fullmatch(r"/api/objects\?offset=[0-9]+&limit=500", path) is not None
                       or method in ("GET", "DELETE") and re.fullmatch(r"/api/objects/[1-9][0-9]*", path) is not None
                       or method == "POST" and re.fullmatch(r"/api/objects/[1-9][0-9]*/project", path) is not None)
        if not allowed:
            raise ProbeError("Request is outside the native block diagnostic allowlist")
        data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        request = Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                payload = response.read(MAX_RESPONSE + 1)
                if len(payload) > MAX_RESPONSE:
                    raise RequestFailure("API response exceeds its bounded size")
                return response.code, strict_json(payload)
        except (OSError, URLError, TimeoutError, HTTPException) as error:
            raise RequestFailure(f"No complete response for {method} {path}; do not repeat an uncertain mutation") from error


def journal_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    runtime = ROOT / "runtime"
    if not path.is_relative_to(runtime) or path == runtime or path.suffix != ".json":
        raise ProbeError("Probe evidence must be a JSON file inside ignored runtime")
    native.check_links(path)
    native.check_links(path.with_suffix(".json.tmp"))
    for candidate in (path, path.with_suffix(".json.tmp")):
        if candidate.exists() and not candidate.is_file():
            raise ProbeError("Probe evidence path collides with a directory")
    return path


class Journal:
    def __init__(self, path: Path):
        self.path = journal_path(path)

    def read(self) -> dict | None:
        journal_path(self.path)
        if not self.path.exists():
            return None
        if self.path.stat().st_size > MAX_RESPONSE:
            raise ProbeError("Existing probe journal is too large")
        state = strict_json(self.path.read_bytes())
        if state.get("schemaVersion") != 1 or state.get("project") != PROJECT or state.get("axis") not in PREFABS:
            raise ProbeError("Existing evidence is not this native block diagnostic")
        if state.get("prefab") != PREFABS[state["axis"]] or state.get("visualVerified") is not False:
            raise ProbeError("Existing probe journal has an unreviewed prefab/visual claim")
        if "probeVariant" in state or "assetReceipt" in state:
            validate_installation_snapshot({key: state.get(key) for key in ("probeVariant", "assetReceipt")}, state["axis"])
        return state

    def write(self, state: dict) -> None:
        path = journal_path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)


def validate_installation_snapshot(value: object, axis: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"probeVariant", "assetReceipt"}:
        raise ProbeError("Validated installed probe identity is required")
    receipt = value.get("assetReceipt")
    variant = value.get("probeVariant")
    if (variant not in PROBE_VARIANTS or not isinstance(receipt, dict) or receipt.get("probeVariant") != variant
            or not isinstance(receipt.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", receipt["id"])
            or any(not isinstance(receipt.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt[key])
                   for key in ("sha256", "planSha256", "candidateReportSha256"))):
        raise ProbeError("Validated installed probe identity is required")
    if variant != "static-oak-log" and axis != "y":
        raise ProbeError(f"The {variant} control supports only axis y")
    # A validator's mutable return object must not alias the persisted snapshot.
    return strict_json(json.dumps(value, allow_nan=False).encode("utf-8"))


class NativeBlockProbe:
    def __init__(self, api: LoopbackAPI, journal: Journal, mc: LoopbackAPI | None = None,
                 timeout: float = 6, interval: float = 0.1, identity=game_instance, settings=project_settings,
                 installation_check=installed_assets):
        if api.role != "native" or mc is not None and mc.role != "mc":
            raise ProbeError("Native and MC clients have incompatible roles")
        self.api, self.journal, self.mc = api, journal, mc
        self.identity = identity
        self.settings = settings
        self.installation_check = installation_check
        self.timeout = max(0.05, min(30, finite(timeout, "poll timeout", 30)))
        self.interval = max(0.01, min(0.5, finite(interval, "poll interval", 1)))

    def same_instance(self, state: dict) -> None:
        saved = state.get("gameInstance")
        if (not isinstance(saved, dict) or type(saved.get("pid")) is not int
                or not isinstance(saved.get("creationTime100ns"), str)
                or not saved["creationTime100ns"].isdigit() or saved.get("imageSha256") != native.EXE_SHA256
                or saved != self.identity()):
            raise ProbeError("Game instance changed or cannot be proved; UID reuse must not affect another object")

    def ready(self) -> dict:
        status, result = self.api.request("/api/status")
        if status != 200 or type(result.get("apiVersion")) is not int or result.get("apiVersion") != 1 or result.get("gameVersion") != VERSION or result.get("ready") is not True or result.get("buildOk") is not True:
            raise ProbeError("Expected ready/buildOk native API 1 on Crimson Desert 1.0.0.2976")
        pending = result.get("pending")
        if type(pending) is not int or not 0 <= pending <= MAX_OBJECTS:
            raise ProbeError("Native pending count is invalid")
        return result

    def projects(self) -> list[str]:
        code, page = self.api.request("/api/projects")
        names = page.get("items")
        if (code != 200 or not isinstance(names, list) or len(names) > MAX_OBJECTS
                or any(not isinstance(name, str) or not name or len(name) > 600 for name in names)
                or len({name.casefold() for name in names}) != len(names)):
            raise ProbeError("Saved project list is invalid")
        return names

    def settings_snapshot(self, instance: dict) -> dict:
        result = self.settings(instance)
        if not isinstance(result, dict) or result.get("projectAutoSave") is not False:
            raise ProbeError("Project autosave must be explicitly disabled before a transient probe")
        return result

    def objects(self) -> list[dict]:
        result, offset = [], 0
        while True:
            status, page = self.api.request(f"/api/objects?offset={offset}&limit=500")
            if (status != 200 or page.get("offset") != offset or page.get("limit") != 500
                    or type(page.get("total")) is not int or not 0 <= page["total"] <= MAX_OBJECTS
                    or not isinstance(page.get("items"), list) or len(page["items"]) > 500):
                raise ProbeError("Native object pagination is invalid")
            for row in page["items"]:
                if not isinstance(row, dict):
                    raise ProbeError("Native registry object must be a JSON object")
                positive_int(row.get("uid"), "object uid")
                for name in "xyz":
                    finite(row.get(name), "object " + name)
            result.extend(page["items"])
            if len(result) > MAX_OBJECTS or len({row["uid"] for row in result}) != len(result):
                raise ProbeError("Native registry is too large or changed while paginating")
            next_offset = page.get("nextOffset")
            if next_offset is None:
                if len(result) != page["total"]:
                    raise ProbeError("Native registry changed while paginating")
                return result
            if type(next_offset) is not int or next_offset != offset + 500 or next_offset >= page["total"]:
                raise ProbeError("Native object pagination is cyclic or inconsistent")
            offset = next_offset

    def position(self) -> tuple[dict, dict, float, float]:
        code, player = self.api.request("/api/player")
        camera_code, camera = self.api.request("/api/camera")
        if code != 200 or camera_code != 200 or not isinstance(camera.get("view"), dict):
            raise ProbeError("Actual player/camera view is unavailable")
        for name in "xyz":
            finite(player.get(name), "player " + name)
            finite(camera.get(name), "camera " + name)
        if math.dist([player[k] for k in "xyz"], [camera[k] for k in "xyz"]) > 25:
            raise ProbeError("Camera is too far from the actual player for this nearby diagnostic")
        vx, vz = (finite(camera["view"].get(name), "view " + name, 2) for name in "xz")
        length = math.hypot(vx, vz)
        if not 0.9 <= length <= 1.1:
            raise ProbeError("Horizontal camera view is not a validated unit direction")
        return player, camera, vx / length, vz / length

    def ground(self, query: dict) -> dict:
        xyz = {k: finite(query.get(k), "ground " + k) for k in "xyz"}
        length = finite(query.get("length"), "ground length", 100)
        if not 0 < length <= 100:
            raise ProbeError("Ground length must be in (0,100]")
        status, admitted = self.api.request("/api/prototype/ground-probe", "POST", {**xyz, "length": length})
        if status != 202:
            raise ProbeError("Ground probe was not admitted; no object was spawned")
        ticket = positive_int(admitted.get("ticket"), "ground ticket")
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            status, hit = self.api.request(f"/api/prototype/ground-result?ticket={ticket}")
            if status == 202 and hit.get("state") == "pending":
                time.sleep(self.interval)
                continue
            if status != 200 or hit.get("state") != "hit":
                raise ProbeError("Ground probe missed, expired or was invalidated; discard the placement")
            for name in "xyz":
                finite(hit.get(name), "ground hit " + name)
            if math.hypot(hit["x"] - xyz["x"], hit["z"] - xyz["z"]) > 0.6 or not xyz["y"] - length - 0.5 <= hit["y"] <= xyz["y"] + 0.5:
                raise ProbeError("Ground hit is outside the validated probe segment")
            return {**hit, "ticket": ticket, "query": {**xyz, "length": length}}
        raise ProbeError("Ground ticket remained pending; placement discarded")

    def mc_state(self) -> dict:
        if self.mc is None:
            return {"available": False, "reason": "optional MC observation disabled"}
        try:
            code, state = self.mc.request("/api/state")
            if code != 200:
                return {"available": False, "reason": f"optional MC GET returned {code}"}
            encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            return {"available": True, "sha256": hashlib.sha256(encoded).hexdigest(), "state": state}
        except ProbeError as error:
            return {"available": False, "reason": str(error)}

    def mc_after(self, state: dict) -> None:
        state["mcAfter"] = self.mc_state()
        before, after = state["mcBefore"], state["mcAfter"]
        state["mcStateUnchanged"] = before["sha256"] == after["sha256"] if before["available"] and after["available"] else None
        # A concurrent user/backend change is reported, never reverted.

    def object_identity(self, row: dict, state: dict, allow_hidden: bool = False) -> None:
        if (row.get("uid") != state.get("uid") or row.get("prefab") != state.get("prefab")
                or state.get("admissionConfirmed") is not True or row.get("uid") in state.get("beforeUids", [])):
            raise ProbeError("UID/prefab/project ownership differs; refusing to modify or clean up the object")
        if not allow_hidden and row.get("hidden") is not False:
            raise ProbeError("Diagnostic registry row is already hidden")
        for name in "xyz":
            if abs(finite(row.get(name), "object " + name) - finite(state["position"].get(name), "saved " + name)) > 0.015:
                raise ProbeError("Diagnostic position changed; cleanup ownership is ambiguous")
        for name, expected in (("scale", 1), ("yaw", 0), ("pitch", 0), ("roll", 0)):
            if abs(finite(row.get(name), name, 360) - expected) > 0.001:
                raise ProbeError("Diagnostic transform changed; cleanup ownership is ambiguous")

    def owned(self, row: dict, state: dict, require_project: bool = True, allow_hidden: bool = False) -> None:
        self.object_identity(row, state, allow_hidden)
        if state.get("initialOwnershipConfirmed") is not True:
            raise ProbeError("Initial project ownership was not journalled; automatic cleanup is ambiguous")
        permitted = {PROJECT} if require_project else {state.get("initialProject")}
        # A lost assignment response can leave either the observed initial
        # project or the requested diagnostic project. Never adopt a third name.
        if not require_project and state.get("projectAssignmentSubmitted") is True:
            permitted.add(PROJECT)
        if row.get("project") not in permitted:
            raise ProbeError("UID/prefab/project ownership differs; refusing to modify or clean up the object")

    def capture_initial_project(self, row: dict, state: dict) -> None:
        self.same_instance(state)
        self.object_identity(row, state)
        name = row.get("project")
        if not isinstance(name, str) or len(name) > 600 or any(ord(char) < 32 for char in name):
            raise ProbeError("Initial project name is invalid")
        # SpawnAt calls EnsureEditingProject. Its nonempty current/Untitled
        # name is not our project, but this admitted new UID is still ours.
        state.update(initialProject=name, initialObject=dict(row), initialOwnershipConfirmed=True,
                     initialProjectCapturedUtc=dt.datetime.now(dt.timezone.utc).isoformat())
        self.journal.write(state)  # Must precede both subsequent reads and assignment.

    def wait_registry(self, state: dict, require_project: bool) -> dict:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            rows = [row for row in self.objects() if row["uid"] == state["uid"]]
            if rows:
                if not require_project and not state.get("initialOwnershipConfirmed"):
                    self.capture_initial_project(rows[0], state)
                self.owned(rows[0], state, require_project)
                return rows[0]
            time.sleep(self.interval)
        raise ProbeError("Admitted UID did not appear in the native registry; spawn was not retried")

    def collision(self, state: dict, removed: bool = False) -> dict:
        observations = {"count": 0, "first": None, "last": None, "minDelta": None, "maxDelta": None}
        state["collisionRemovedObservations" if removed else "collisionObservations"] = observations
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            hit = self.ground(state["groundBefore"]["query"])
            delta = hit["y"] - state["groundBefore"]["y"]
            # Keep constant-size evidence even when the loop raises on timeout.
            observation = {"hit": {key: hit[key] for key in ("x", "y", "z", "ticket")},
                           "deltaFromOriginalGround": delta}
            observations["count"] += 1
            if observations["first"] is None:
                observations["first"] = observation
            observations["last"] = observation
            observations["minDelta"] = delta if observations["minDelta"] is None else min(observations["minDelta"], delta)
            observations["maxDelta"] = delta if observations["maxDelta"] is None else max(observations["maxDelta"], delta)
            if (abs(delta) < 0.15 if removed else 0.75 < delta < 1.25):
                return {"hit": hit, "deltaFromOriginalGround": delta,
                        "expectedBlueCubeHeight": 1.0, "verified": True}
            time.sleep(self.interval)
        raise ProbeError("Physical ground height did not confirm the expected one-metre collision change")

    def placement(self, player: dict, vx: float, vz: float, before: list) -> tuple:
        """Sample a bounded set of nearby positions without creating objects."""
        attempts = []
        for forward, side in ((4, 0), (3, 0), (5, 0), (4, -1.5), (4, 1.5), (5, -1.5), (5, 1.5)):
            cx = player["x"] + vx * forward - vz * side
            cz = player["z"] + vz * forward + vx * side
            if any(math.hypot(row["x"] - cx, row["z"] - cz) < 2 for row in before):
                attempts.append({"forward": forward, "side": side, "accepted": False, "reason": "registered object nearby"})
                continue
            query = {"x": cx, "y": player["y"] + 5, "z": cz, "length": 12}
            ground = self.ground(query)
            sample = [ground]
            for dx, dz in ((-0.35, -0.35), (-0.35, 0.35), (0.35, -0.35), (0.35, 0.35)):
                sample.append(self.ground({**query, "x": cx + dx, "z": cz + dz}))
            highest = max(hit["y"] for hit in sample)
            spread = highest - min(hit["y"] for hit in sample)
            accepted = spread <= 0.15 and abs(ground["y"] - player["y"]) <= 3
            attempts.append({"forward": forward, "side": side, "heightSpread": spread, "accepted": accepted})
            if accepted:
                return cx, cz, ground, sample, highest, attempts
        raise ProbeError("All nearby candidate positions are occupied, too sloped or too far from the player's level")

    def spawn(self, axis: str = "y") -> dict:
        if axis not in PREFABS:
            raise ProbeError("Only the three reviewed oak-log axes are supported")
        old = self.journal.read()
        if old is not None and old.get("phase") != "cleaned":
            raise ProbeError("An existing probe journal remains unresolved; inspect/clean up it before spawning again")
        instance = self.identity()
        installation = validate_installation_snapshot(self.installation_check(instance, axis), axis)
        ready = self.ready()
        settings = self.settings_snapshot(instance)
        projects = self.projects()
        before = self.objects()
        if any(row.get("project") == PROJECT or row.get("prefab") in PREFABS.values() for row in before):
            raise ProbeError("Existing native asset diagnostic retained; automatic duplicate spawn refused")
        player, camera, vx, vz = self.position()
        cx, cz, ground, sample, highest, attempts = self.placement(player, vx, vz, before)
        state = {"schemaVersion": 1, "runId": str(uuid.uuid4()), "createdUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
                 **installation,
                 "project": PROJECT, "axis": axis, "prefab": PREFABS[axis], "apiBase": self.api.base,
                 "gameInstance": instance,
                 "projectSettingsBefore": settings, "projectsBefore": projects,
                 "statusBefore": ready, "playerBefore": player, "cameraBefore": camera,
                 "position": {"x": cx - 0.5, "y": highest + 0.03, "z": cz - 0.5},
                 "groundBefore": ground, "flatGroundSamples": sample, "placementAttempts": attempts,
                 "beforeUids": [row["uid"] for row in before],
                 "uid": None, "phase": "prepared", "spawnSubmitted": False, "cleanupSubmitted": False,
                 "admissionConfirmed": False, "initialOwnershipConfirmed": False, "projectAssignmentSubmitted": False,
                 "registryConfirmed": False, "collisionVerified": False, "visualVerified": False,
                 "nativeLiveStateExposed": False, "mcBefore": self.mc_state(),
                 "limitations": ["Registry admission contains no per-UID engine-live flag; global pending is auxiliary only.",
                                 "Ground delta proves physical collision at the sampled point, not texture appearance.",
                                 "SpawnAt implicitly ensures an editing project: it may load an existing project, save an empty Untitled project, and save settings; those files are retained.",
                                 "SpawnAt marks its initial editing project dirty; this probe never explicitly saves or deletes any project or changes settings.",
                                 "Autosave observations are read-only settings snapshots; concurrent UI changes are outside this diagnostic.",
                                 "Visual acceptance requires separate actual game screenshots."]}
        self.journal.write(state)
        try:
            # Persist intent before the one allowed spawn request. A lost HTTP
            # response leaves this journal unresolved, preventing duplicates.
            self.same_instance(state)
            if validate_installation_snapshot(self.installation_check(instance, axis), axis) != installation:
                raise ProbeError("Installed asset receipt changed during preflight; spawn was not submitted")
            state["projectSettingsAtAdmission"] = self.settings_snapshot(instance)
            state.update(phase="spawn_submitted", spawnSubmitted=True)
            self.journal.write(state)
            code, admission = self.api.request("/api/objects", "POST", {"prefab": state["prefab"], **state["position"],
                                                                        "yaw": 0, "pitch": 0, "roll": 0, "scale": 1})
            state["uid"] = positive_int(admission.get("uid"), "admitted uid")
            self.journal.write(state)
            if code != 202 or admission.get("queued") is not True or state["uid"] in state["beforeUids"]:
                raise ProbeError("Invalid/new UID admission; creation outcome is unresolved")
            state["admissionConfirmed"] = True
            self.journal.write(state)
            self.wait_registry(state, False)
            state["projectsAfterAdmission"] = self.projects()
            prior_names = {name.casefold() for name in state["projectsBefore"]}
            state["newProjectNamesAfterAdmission"] = [name for name in state["projectsAfterAdmission"] if name.casefold() not in prior_names]
            state["projectSettingsAfterAdmission"] = self.settings_snapshot(instance)
            self.journal.write(state)
            self.same_instance(state)
            code, row = self.api.request(f"/api/objects/{state['uid']}")
            if code != 200:
                raise ProbeError("Admitted UID is unavailable before project assignment")
            self.owned(row, state, False)
            state.update(phase="project_assignment_submitted", projectAssignmentSubmitted=True)
            self.journal.write(state)
            code, assigned = self.api.request(f"/api/objects/{state['uid']}/project", "POST", {"name": PROJECT})
            if code != 200 or assigned.get("uid") != state["uid"] or assigned.get("project") != PROJECT:
                raise ProbeError("Diagnostic project assignment was not confirmed")
            state["nativeObject"] = self.wait_registry(state, True)
            state.update(phase="registry_confirmed", registryConfirmed=True)
            state["statusAfterAdmission"] = self.ready()
            self.journal.write(state)
            # The user may move while the probe runs. Reject a character/body
            # directly at the sample instead of misattributing its collision.
            current, _, _, _ = self.position()
            if math.hypot(current["x"] - cx, current["z"] - cz) < 1.5:
                raise ProbeError("Player entered the collision sample area; physical evidence is ambiguous")
            state["collisionAfter"] = self.collision(state)
            self.same_instance(state)
            state.update(phase="spawned", collisionVerified=True, collisionVerifiedVariant=state["probeVariant"])
            self.mc_after(state)
            self.journal.write(state)
            return state
        except (ProbeError, OSError, ValueError) as error:
            state["failureAtPhase"] = state["phase"]
            state.update(phase="unresolved", error=str(error))
            self.mc_after(state)
            self.journal.write(state)
            raise ProbeError(f"{error}; journal retained, UID={state['uid']}. Do not blindly repeat --spawn") from error

    def cleanup(self) -> dict:
        state = self.journal.read()
        if state is None:
            raise ProbeError("No native asset probe journal exists")
        if state.get("phase") == "cleaned":
            return state
        if state.get("apiBase") != self.api.base:
            raise ProbeError("Cleanup API differs from the journal's loopback endpoint")
        if state.get("uid") is None:
            if state.get("spawnSubmitted"):
                raise ProbeError("Spawn response was lost; no known owned UID exists for automatic cleanup")
            state["phase"] = "cleaned"
            self.journal.write(state)
            return state
        positive_int(state["uid"], "saved uid")
        self.same_instance(state)
        self.ready()
        code, row = self.api.request(f"/api/objects/{state['uid']}")
        if code == 200:
            self.owned(row, state, bool(state.get("registryConfirmed")), allow_hidden=True)
            if state.get("cleanupSubmitted"):
                raise ProbeError("A previous cleanup outcome is unresolved; do not repeat the DELETE")
            state.update(phase="cleanup_submitted", cleanupSubmitted=True)
            self.same_instance(state)
            state["projectSettingsAtCleanup"] = self.settings_snapshot(state["gameInstance"])
            self.journal.write(state)
            try:
                code, result = self.api.request(f"/api/objects/{state['uid']}", "DELETE")
                if code != 202 or result.get("uid") != state["uid"] or result.get("queued") is not True:
                    raise ProbeError("Native cleanup was not admitted")
            except ProbeError as error:
                state.update(phase="cleanup_unresolved", cleanupError=str(error))
                self.journal.write(state)
                raise
        elif code != 404:
            raise ProbeError("Owned native UID cannot be safely inspected for cleanup")
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            code, row = self.api.request(f"/api/objects/{state['uid']}")
            if code == 404:
                state["registryRemoved"] = True
                self.journal.write(state)
                try:
                    state["collisionRemoved"] = self.collision(state, removed=True)
                except (ProbeError, OSError, ValueError) as error:
                    state.update(phase="cleanup_unresolved", cleanupError=str(error))
                    self.journal.write(state)
                    raise
                state.update(phase="cleaned", collisionRemovedVerified=True)
                self.mc_after(state)
                self.journal.write(state)
                return state
            if code != 200:
                raise ProbeError("Cleanup registry confirmation returned an unexpected response")
            self.owned(row, state, bool(state.get("registryConfirmed")), allow_hidden=True)
            time.sleep(self.interval)
        raise ProbeError("Cleanup stayed in the registry; no repeated DELETE was issued")


def summary(state: dict) -> dict:
    keys = ("runId", "phase", "uid", "prefab", "probeVariant", "assetReceipt", "project", "initialProject", "newProjectNamesAfterAdmission", "position", "registryConfirmed", "collisionVerified", "collisionVerifiedVariant",
            "visualVerified", "registryRemoved", "collisionRemovedVerified", "mcStateUnchanged", "error")
    return {key: state[key] for key in keys if key in state}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--spawn", nargs="?", const="axis=y", choices=("axis=x", "axis=y", "axis=z"))
    mode.add_argument("--cleanup", action="store_true")
    mode.add_argument("--status", action="store_true", help="Read saved evidence only; no game request")
    parser.add_argument("--api", default="http://127.0.0.1:8765")
    parser.add_argument("--mc-api", default="http://127.0.0.1:8766")
    parser.add_argument("--journal", type=Path, default=ROOT / "runtime/native-block-probe.json")
    parser.add_argument("--timeout", type=float, default=6)
    args = parser.parse_args()
    try:
        journal = Journal(args.journal)
        if args.status:
            state = journal.read()
            if state is None:
                raise ProbeError("No native asset probe journal exists")
        else:
            probe = NativeBlockProbe(LoopbackAPI(args.api), journal, LoopbackAPI(args.mc_api, "mc"), args.timeout)
            state = probe.spawn(args.spawn[-1]) if args.spawn else probe.cleanup()
    except (ProbeError, OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Native block probe stopped: {error}") from error
    print(json.dumps({"journal": str(journal.path), **summary(state)}, indent=2))


if __name__ == "__main__":
    main()
