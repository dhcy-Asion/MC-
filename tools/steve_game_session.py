"""Query/reuse the fixed game session or request its existing Steam launch once.

This CLI has no menu/save input capability. A native ready response establishes
scene readiness only; automatic entry into the intended save remains unverified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import native_identity as identity

STEAM_URI = "steam://rungameid/3321460"
GAME_VERSION = "1.0.0.2976"
MC_ENGINE = "Minecraft Java 1.21.1"
HTTP_LIMIT = 65536
CONFIG_LIMIT = 2 * 1024 * 1024
OUTPUT_PATTERN = re.compile(r"steve-game-session-[a-z0-9]+(?:-[a-z0-9]+)*\.json\Z")


class SessionError(RuntimeError):
    pass


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON value")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("JSON response must be an object")
    return value


def game_process_ids():
    """Bounded process-name enumeration; no VM handles or process mutation."""
    if os.name != "nt":
        raise SessionError("Windows process enumeration is required")
    import ctypes as c
    from ctypes import wintypes as w
    class Entry(c.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
            ("th32DefaultHeapID", c.c_size_t), ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
            ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD),
            ("szExeFile", w.WCHAR * 260)]
    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes, kernel.CreateToolhelp32Snapshot.restype = [w.DWORD,w.DWORD],w.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [w.HANDLE,c.POINTER(Entry)]
    kernel.Process32FirstW.restype = kernel.Process32NextW.restype = w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE],w.BOOL
    handle = kernel.CreateToolhelp32Snapshot(0x2,0)
    if not handle or handle == c.c_void_p(-1).value:
        raise SessionError("Cannot enumerate actual game processes")
    result = []
    try:
        row = Entry()
        row.dwSize = c.sizeof(row)
        found, count = kernel.Process32FirstW(handle,c.byref(row)),0
        while found:
            count += 1
            if count > 65536:
                raise SessionError("Process enumeration exceeds its bounded capacity")
            if row.szExeFile.casefold() == "crimsondesert.exe":
                result.append(int(row.th32ProcessID))
            found = kernel.Process32NextW(handle,c.byref(row))
        if c.get_last_error() != 18:
            raise SessionError("Process enumeration did not complete")
    finally:
        kernel.CloseHandle(handle)
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise SessionError("Loopback status redirects are forbidden")


def http_json(port, route, timeout=2.0):
    """Exactly two fixed read-only routes; bounded JSON and no proxies/redirects."""
    if (port,route) not in ((8765,"/api/status"),(8766,"/api/state")):
        raise SessionError("Unsupported session read endpoint")
    if not 0 < timeout <= 2:
        raise SessionError("HTTP timeout exceeds its bound")
    opener = build_opener(ProxyHandler({}),NoRedirect())
    request = Request(f"http://127.0.0.1:{port}{route}",method="GET")
    with opener.open(request,timeout=timeout) as response:
        if response.status != 200:
            raise SessionError("Status endpoint did not return HTTP 200")
        raw = response.read(HTTP_LIMIT+1)
    if len(raw) > HTTP_LIMIT:
        raise SessionError("Status JSON exceeds its byte bound")
    return strict_json(raw)


def read_endpoint(port,route,timeout):
    try:
        return {"available":True,"data":http_json(port,route,timeout)}
    except (OSError,ValueError,SessionError) as error:
        return {"available":False,"error":type(error).__name__+": "+str(error)}


def base_report(command):
    return {"schemaVersion":1,"timeUtc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "command":command,"state":"blocked","gameIdentity":None,"identityStable":False,
        "nativeBuildVerified":False,"sceneReady":False,"mcReady":False,
        "sceneReadyMeaning":"Matching fixed instance, native hooks/game-thread ready and readable fixed Minecraft backend; this does not identify the intended save.",
        "automaticWorldEntryVerified":False,"launchRequested":False,"steamUri":STEAM_URI,
        "userProvidedMenuStep":"Identify the supplied entry page, confirm the foreground game, press E once only while not scene-ready, then await matched scene readiness.",
        "visualReferencePixelsVerified":False,"guiInputAvailable":False,
        "guiCapabilities":{"providedToThisCli":False,"windowInventory":False,
            "screenshots":False,"input":False,"environmentObservationPerformed":False},
        "scope":{"processQueryOnly":True,"ownerOrMaterialSampled":False,
            "backgroundServicesChanged":False,"gameFilesOrSavesChanged":False,"menuInputAttempted":False},
        "nextRequired":"Stop until the fixed game/build identity is available."}


def status(http_timeout=2.0):
    report = base_report("status")
    try:
        pids = game_process_ids()
        report["gameProcessCount"] = len(pids)
        if not pids:
            report["nativeStatus"] = read_endpoint(8765,"/api/status",http_timeout)
            mc = read_endpoint(8766,"/api/state",http_timeout)
            data = mc.get("data",{})
            report["minecraftStatus"] = {"available":mc["available"],
                "engine":data.get("engine"),"schemaVersion":data.get("schemaVersion"),"revision":data.get("revision")}
            if not mc["available"]:
                report["minecraftStatus"]["error"] = mc["error"]
            report["mcReady"] = (mc["available"] and data.get("engine") == MC_ENGINE
                and type(data.get("schemaVersion")) is int and data["schemaVersion"] == 3
                and type(data.get("revision")) is int and data["revision"] >= 0)
            report.update(state="closed",nextRequired="Request launch, then enter the existing test save using the user or supported Windows CUA window/screenshot/input control.")
            return report
        if len(pids) != 1:
            raise SessionError("Multiple game instances; do not launch or restart")
        current = identity.session_identity()
        token = identity.session_token(current)
        if current["pid"] != pids[0]:
            raise SessionError("Game instance changed during process admission")
        report["gameIdentity"] = current
        native = read_endpoint(8765,"/api/status",http_timeout)
        mc = read_endpoint(8766,"/api/state",http_timeout)
        report["nativeStatus"] = native
        data = mc.get("data",{})
        report["minecraftStatus"] = {"available":mc["available"],
            "engine":data.get("engine"),"schemaVersion":data.get("schemaVersion"),"revision":data.get("revision")}
        if not mc["available"]:
            report["minecraftStatus"]["error"] = mc["error"]
        final = identity.session_identity()
        identity.session_token(final)
        if final != current:
            raise SessionError("Game instance changed during status observation")
        report["identityStable"] = True
        if not native["available"]:
            raise SessionError("Native build identity is unavailable")
        native_data = native["data"]
        if (type(native_data.get("apiVersion")) is not int or native_data["apiVersion"] != 1
                or native_data.get("gameVersion") != GAME_VERSION or native_data.get("buildOk") is not True
                or native_data.get("sessionPreconditions") is not True
                or native_data.get("instanceId") != token or type(native_data.get("ready")) is not bool):
            raise SessionError("Native build/session identity or readiness type differs")
        report["nativeBuildVerified"] = True
        report["mcReady"] = (mc["available"] and data.get("engine") == MC_ENGINE
            and type(data.get("schemaVersion")) is int and data["schemaVersion"] == 3
            and type(data.get("revision")) is int and data["revision"] >= 0)
        report["sceneReady"] = native_data["ready"] and report["mcReady"]
        report.update(state="scene-ready" if report["sceneReady"] else "running-not-ready",
            nextRequired=("Verify the intended existing test save using the user or supported Windows CUA window/screenshot/input control. Do not press E while scene-ready; automatic menu/save entry is unverified."
                if report["sceneReady"] else "Enter the intended existing test save using the user or supported Windows CUA window/screenshot/input control; identify the supplied entry page and foreground game before any E-once action."))
        if not report["mcReady"]:
            report["nextRequired"] += " Existing Minecraft backend readiness is unavailable; this CLI does not start or replace services."
    except (OSError,ValueError,SessionError,identity.IdentityError) as error:
        report.update(state="blocked",error=type(error).__name__+": "+str(error),sceneReady=False)
    return report


def check_links(path):
    current = Path(os.path.abspath(path))
    while current != current.parent:
        if current.is_symlink() or (hasattr(current,"is_junction") and current.is_junction()):
            raise SessionError("Session paths cannot contain links or junctions")
        current = current.parent


def verify_closed_executable():
    config = ROOT/"runtime/installation.json"
    check_links(config)
    if not config.is_file() or not 0 < config.stat().st_size <= CONFIG_LIMIT:
        raise SessionError("Existing installation configuration is unavailable")
    raw = config.read_bytes()
    if len(raw) > CONFIG_LIMIT:
        raise SessionError("Installation configuration exceeds its byte bound")
    data = strict_json(raw.decode("utf-8-sig"))
    game_root = data.get("gameRoot")
    if not isinstance(game_root,str) or not Path(game_root).is_absolute():
        raise SessionError("Existing absolute game installation is unknown")
    exe = Path(game_root)/"bin64/CrimsonDesert.exe"
    check_links(exe)
    digest = identity._verify_image(exe)
    if digest != identity.EXE_SHA256:
        raise SessionError("Existing game executable does not match the fixed EXE SHA256")
    if config.read_bytes() != raw:
        raise SessionError("Installation configuration changed before launch")
    return {"imagePath":str(exe.resolve()),"imageSha256":digest}


def request_steam_launch():
    if os.name != "nt":
        raise SessionError("Steam URI launch requires Windows")
    os.startfile(STEAM_URI)


def launch():
    before = status()
    before["command"] = "launch"
    if before["state"] != "closed":
        before["reusedRunningGame"] = before["nativeBuildVerified"] and before["identityStable"]
        return before
    if not before["mcReady"]:
        before.update(state="blocked",error="Existing Minecraft backend is not ready; Steam launch was not requested.",
            nextRequired="Start the already configured existing Minecraft backend through its existing workflow, verify readiness, then request launch. This CLI does not start, restart or replace services.")
        return before
    try:
        executable = verify_closed_executable()
        # Recheck absence after fixed-image admission; never reopen/restart a running instance.
        if game_process_ids():
            reused = status()
            reused.update(command="launch",reusedRunningGame=reused["nativeBuildVerified"] and reused["identityStable"])
            return reused
        request_steam_launch()
        before.update(state="launch-requested",launchRequested=True,reusedRunningGame=False,
            launchExecutable=executable,
            nextRequired="Run wait-ready after a game instance appears; the user or supported Windows CUA window/screenshot/input control must enter the existing test save. Steam acceptance does not verify a running game or world entry.")
    except (OSError,ValueError,SessionError,identity.IdentityError) as error:
        before.update(state="blocked",error=type(error).__name__+": "+str(error))
    return before


def wait_ready(timeout=60.0,interval=2.0):
    if (isinstance(timeout,bool) or isinstance(interval,bool) or not math.isfinite(timeout)
            or not math.isfinite(interval) or not 0 < timeout <= 120 or not 2 <= interval <= 120):
        raise SessionError("wait-ready requires timeout >0 and <=120 seconds, interval >=2 and <=120 seconds")
    started = time.monotonic()
    deadline = started+timeout
    expected, observations, report = None,0,base_report("wait-ready")
    report["state"] = "running-not-ready"
    while time.monotonic() < deadline:
        remaining = deadline-time.monotonic()
        report = status(http_timeout=min(2.0,max(0.001,remaining/3)))
        observations += 1
        report.update(command="wait-ready",observations=observations)
        if report["state"] in ("closed","blocked"):
            report.update(state="blocked",error=report.get("error","Game process disappeared or has not appeared; do not retry launch automatically."))
            break
        if expected is None:
            expected = report["gameIdentity"]
        elif report["gameIdentity"] != expected:
            report.update(state="blocked",sceneReady=False,error="Game instance changed during wait-ready")
            break
        if time.monotonic() >= deadline:
            report["state"] = "timed-out"
            report["sceneReady"] = False
            break
        if report["sceneReady"]:
            break
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval,remaining))
    if report["state"] not in ("blocked","scene-ready"):
        report.update(state="timed-out",sceneReady=False,
            nextRequired="Enter the existing test save using the user or supported Windows CUA window/screenshot/input control, then make a new bounded readiness check. No launch retry or menu input was attempted.")
    report["elapsedSeconds"] = round(time.monotonic()-started,3)
    report["automaticWorldEntryVerified"] = False
    return report


def output_path(value):
    path = Path(value)
    if ".." in path.parts:
        raise SessionError("Session output traversal is forbidden")
    path = path if path.is_absolute() else ROOT/path
    absolute = Path(os.path.abspath(path))
    if absolute.parent != ROOT/"runtime" or not OUTPUT_PATTERN.fullmatch(absolute.name):
        raise SessionError("Output must be runtime/steve-game-session-<safe-name>.json")
    check_links(absolute)
    if absolute.exists():
        raise SessionError("Session output already exists; refusing overwrite")
    return absolute


def save_report(path,report):
    path = output_path(path)
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("status","launch","wait-ready"),nargs="?",default="status")
    parser.add_argument("--timeout",type=float,default=60)
    parser.add_argument("--interval",type=float,default=2)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    destination = output_path(args.output) if args.output is not None else None
    report = status() if args.command == "status" else launch() if args.command == "launch" else wait_ready(args.timeout,args.interval)
    if destination is not None:
        save_report(destination,report)
    print(json.dumps(report,indent=2,allow_nan=False))
    return 2 if report["state"] in ("blocked","timed-out") else 0


if __name__ == "__main__":
    raise SystemExit(main())
