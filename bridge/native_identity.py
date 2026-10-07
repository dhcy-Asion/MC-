"""Query a fresh Windows game-session identity without opening VM access.

Only the executable digest is cached, keyed by its current filesystem identity.
Process creation time and liveness are queried on every call; PID alone is never
used as a durable identity. This does not prove a scene or HTTP request completed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading

EXE_SHA256 = "57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7"
_digest_cache: dict[tuple, str] = {}
_digest_lock = threading.Lock()


class IdentityError(RuntimeError):
    pass


def session_token(identity: dict) -> str:
    """Encode the native precondition, never a PID-only or client-chosen nonce."""
    if not isinstance(identity, dict):
        raise IdentityError("Invalid native session precondition")
    pid, created = identity.get("pid"), identity.get("creationTime100ns")
    if (type(pid) is not int or not 1 <= pid <= 0xFFFFFFFF
            or not isinstance(created, str) or not created.isascii()
            or not created.isdigit() or len(created) > 20
            or not 0 < int(created) <= 0xFFFFFFFFFFFFFFFF
            or str(int(created)) != created
            or not isinstance(identity.get("imagePath"), str) or not identity["imagePath"]
            or identity.get("imageSha256") != EXE_SHA256
            or identity.get("access") != "PROCESS_QUERY_LIMITED_INFORMATION"):
        raise IdentityError("Invalid native session precondition")
    return f"{pid}:{created}"


def _file_key(path: Path) -> tuple:
    stat = path.stat()
    return (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _verify_image(path: Path) -> str:
    path = path.resolve(strict=True)
    if path.name.casefold() != "crimsondesert.exe" or not path.is_file():
        raise IdentityError("Running process image is not CrimsonDesert.exe")
    with _digest_lock:
        before = _file_key(path)
        digest = _digest_cache.get(before)
        if digest is None:
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(data)
            digest = hasher.hexdigest()
        if before != _file_key(path):
            raise IdentityError("Game executable changed while verifying its identity")
        if digest != EXE_SHA256:
            raise IdentityError("Running game image differs from the supported EXE SHA256")
        _digest_cache.clear()
        _digest_cache[before] = digest
        return digest


def session_identity() -> dict:
    """Return exactly one live, pinned game instance using query-only handles."""
    if os.name != "nt":
        raise IdentityError("Native synchronization requires a Windows game process")
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
    kernel.GetExitCodeProcess.argtypes, kernel.GetExitCodeProcess.restype = [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = w.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)
    if not snapshot or snapshot == c.c_void_p(-1).value:
        raise IdentityError("Cannot enumerate the actual game process")
    pids = []
    try:
        entry = ProcessEntry()
        entry.dwSize = c.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, c.byref(entry))
        count = 0
        while found:
            count += 1
            if count > 65536:
                raise IdentityError("Process enumeration exceeded its bounded capacity")
            if entry.szExeFile.casefold() == "crimsondesert.exe":
                pids.append(int(entry.th32ProcessID))
            found = kernel.Process32NextW(snapshot, c.byref(entry))
        if c.get_last_error() != 18:
            raise IdentityError("Process enumeration did not complete")
    finally:
        kernel.CloseHandle(snapshot)
    if len(pids) != 1:
        raise IdentityError("Exactly one CrimsonDesert.exe instance must be running")
    handle = kernel.OpenProcess(0x1000, False, pids[0])
    if not handle:
        raise IdentityError("Cannot open query-only game process identity")
    try:
        def ensure_live():
            code = w.DWORD()
            if not kernel.GetExitCodeProcess(handle, c.byref(code)) or code.value != 259:
                raise IdentityError("Game process ended during the identity observation")
        ensure_live()
        created, exited, kernel_time, user_time = (w.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, c.byref(created), c.byref(exited), c.byref(kernel_time), c.byref(user_time)):
            raise IdentityError("Cannot read game process creation time")
        buffer, size = c.create_unicode_buffer(32768), w.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(size)):
            raise IdentityError("Cannot verify actual game process image")
        image = Path(buffer.value).resolve(strict=True)
        digest = _verify_image(image)
        ensure_live()
        creation = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        if creation <= 0:
            raise IdentityError("Game process creation time is unavailable")
        return {"pid": pids[0], "creationTime100ns": str(creation),
                "imagePath": str(image), "imageSha256": digest,
                "access": "PROCESS_QUERY_LIMITED_INFORMATION"}
    except OSError as error:
        raise IdentityError("Cannot verify the running game executable: " + str(error)) from error
    finally:
        kernel.CloseHandle(handle)
