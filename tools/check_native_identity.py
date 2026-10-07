"""Isolated process-query and HTTP-error checks; no real process is opened."""
from __future__ import annotations

import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import native_identity as identity
from bridge.red_side import RedSide, GameAPIError


class Function:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name
    def __call__(self, *args):
        self.owner.calls.append((self.name, args))
        if self.owner.fail == self.name:
            return 0
        return getattr(self.owner, "do_" + self.name)(*args)


class FakeKernel:
    def __init__(self, image):
        self.image, self.calls = image, []
        self.rows, self.index = [(41, "unrelated.exe"), (42, "CrimsonDesert.exe")], 0
        self.creation, self.error, self.fail = 134358162934331038, 0, None
        self.exit_codes = [259, 259]
        for name in ("CreateToolhelp32Snapshot", "Process32FirstW", "Process32NextW", "OpenProcess",
                     "CloseHandle", "GetProcessTimes", "GetExitCodeProcess", "QueryFullProcessImageNameW"):
            setattr(self, name, Function(self, name))
    def do_CreateToolhelp32Snapshot(self, flags, pid): return 100
    def do_CloseHandle(self, handle): return 1
    def row(self, pointer):
        if self.index == len(self.rows):
            self.error = 18
            return 0
        pointer._obj.th32ProcessID, pointer._obj.szExeFile = self.rows[self.index]
        self.index += 1
        return 1
    def do_Process32FirstW(self, handle, pointer):
        self.index = 0
        return self.row(pointer)
    def do_Process32NextW(self, handle, pointer): return self.row(pointer)
    def do_OpenProcess(self, access, inherit, pid): return 200
    def do_GetProcessTimes(self, handle, created, exited, kernel_time, user_time):
        created._obj.dwHighDateTime = self.creation >> 32
        created._obj.dwLowDateTime = self.creation & 0xFFFFFFFF
        return 1
    def do_GetExitCodeProcess(self, handle, pointer):
        pointer._obj.value = self.exit_codes.pop(0) if self.exit_codes else 259
        return 1
    def do_QueryFullProcessImageNameW(self, handle, flags, buffer, size):
        buffer.value = str(self.image)
        return 1


class IdentityChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.image = Path(self.folder.name) / "CrimsonDesert.exe"
        self.image.write_bytes(b"isolated fixture; not an executable")
        self.sha = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.fake = FakeKernel(self.image)
        identity._digest_cache.clear()
        self.addCleanup(identity._digest_cache.clear)

    def observe(self):
        with patch.object(ctypes, "WinDLL", return_value=self.fake), \
             patch.object(ctypes, "get_last_error", side_effect=lambda: self.fake.error), \
             patch.object(identity, "EXE_SHA256", self.sha):
            return identity.session_identity()

    def test_01_query_only_access_fresh_creation_and_balanced_handles(self):
        first = self.observe()
        self.assertEqual(first["pid"], 42)
        self.assertEqual(first["creationTime100ns"], str(self.fake.creation))
        self.assertEqual(first["imageSha256"], self.sha)
        self.assertEqual(first["access"], "PROCESS_QUERY_LIMITED_INFORMATION")
        self.assertIn(("OpenProcess", (0x1000, False, 42)), self.fake.calls)
        self.assertEqual([args[0] for name, args in self.fake.calls if name == "CloseHandle"], [100, 200])
        self.fake.creation += 1  # Same PID is insufficient after process reuse.
        second = self.observe()
        self.assertNotEqual(first, second)

    def test_02_absent_or_multiple_game_processes_never_open_a_handle(self):
        for rows in ([], [(42, "CrimsonDesert.exe"), (43, "CrimsonDesert.exe")]):
            self.fake = FakeKernel(self.image)
            self.fake.rows = rows
            with self.assertRaisesRegex(identity.IdentityError, "Exactly one"):
                self.observe()
            self.assertFalse(any(name == "OpenProcess" for name, _ in self.fake.calls))

    def test_03_query_failures_close_all_successfully_opened_handles(self):
        for function in ("CreateToolhelp32Snapshot", "OpenProcess", "GetProcessTimes", "GetExitCodeProcess", "QueryFullProcessImageNameW"):
            with self.subTest(function=function):
                self.fake = FakeKernel(self.image)
                self.fake.fail = function
                with self.assertRaises(identity.IdentityError): self.observe()
                closed = [args[0] for name, args in self.fake.calls if name == "CloseHandle"]
                self.assertEqual(closed, [] if function == "CreateToolhelp32Snapshot" else [100] if function == "OpenProcess" else [100, 200])

    def test_04_exit_before_or_during_digest_is_not_a_live_session(self):
        for codes in ([0], [259, 0]):
            self.fake = FakeKernel(self.image)
            self.fake.exit_codes = codes
            with self.assertRaisesRegex(identity.IdentityError, "ended"):
                self.observe()
            self.assertIn(("CloseHandle", (200,)), self.fake.calls)

    def test_05_cached_digest_reuses_bytes_but_rechecks_changed_file(self):
        with patch.object(hashlib, "sha256", wraps=hashlib.sha256) as hasher:
            self.observe()
            self.observe()
            self.assertEqual(hasher.call_count, 1)
            self.image.write_bytes(b"different fixture bytes with changed length")
            with self.assertRaisesRegex(identity.IdentityError, "SHA256"):
                self.observe()
            self.assertEqual(hasher.call_count, 2)

    def test_06_digest_rejects_mid_read_file_identity_change(self):
        original = identity._file_key(self.image.resolve())
        changed = (*original[:-1], original[-1] + 1)
        with patch.object(identity, "_file_key", side_effect=[original, changed]), \
             patch.object(identity, "EXE_SHA256", self.sha):
            with self.assertRaisesRegex(identity.IdentityError, "changed"):
                identity._verify_image(self.image)
        self.assertFalse(identity._digest_cache)

    def test_07_wrong_name_missing_file_and_invalid_creation_stop(self):
        wrong = self.image.with_name("other.exe")
        wrong.write_bytes(self.image.read_bytes())
        self.fake.image = wrong
        with self.assertRaisesRegex(identity.IdentityError, "not Crimson"):
            self.observe()
        self.fake.image = self.image.with_name("absent.exe")
        with self.assertRaises(identity.IdentityError): self.observe()
        self.fake.image, self.fake.creation = self.image, 0
        with self.assertRaisesRegex(identity.IdentityError, "creation time"):
            self.observe()

    def test_08_http_not_found_retains_status_and_unknown_failures_are_distinct(self):
        body = io.BytesIO(json.dumps({"error": "not found"}).encode())
        error = HTTPError("http://127.0.0.1:1", 404, "Not Found", {}, body)
        with patch("bridge.red_side.urlopen", side_effect=error):
            with self.assertRaises(GameAPIError) as result:
                RedSide("http://127.0.0.1:1").request("/api/objects/1")
        self.assertEqual(result.exception.status, 404)
        self.assertEqual(result.exception.details, {"error": "not found"})
        self.assertTrue(body.closed)
        with patch("bridge.red_side.urlopen", side_effect=TimeoutError("unknown")):
            with self.assertRaises(TimeoutError): RedSide().request("/api/objects/1")
        self.assertIsNone(GameAPIError("legacy message").status)

    def test_09_red_side_preserves_identity_failure_without_game_calls(self):
        with patch.object(identity, "session_identity", side_effect=identity.IdentityError("no game")):
            with self.assertRaisesRegex(GameAPIError, "no game") as error:
                RedSide().session_identity()
        self.assertIsNone(error.exception.status)

    def precondition(self):
        return {"pid": 42, "creationTime100ns": "134358162934331038",
                "imagePath": str(self.image), "imageSha256": identity.EXE_SHA256,
                "access": "PROCESS_QUERY_LIMITED_INFORMATION"}

    def test_10_session_token_rejects_ambiguous_or_unverified_identity(self):
        valid = self.precondition()
        self.assertEqual(identity.session_token(valid), "42:134358162934331038")
        variants = [("pid", True), ("pid", 0), ("pid", 2**32),
                    ("creationTime100ns", "0"), ("creationTime100ns", "01"),
                    ("creationTime100ns", "１２"), ("creationTime100ns", str(2**64)),
                    ("creationTime100ns", "1" * 1000), ("creationTime100ns", 1),
                    ("imagePath", ""), ("imageSha256", "0" * 64), ("access", "VM_WRITE")]
        for key, value in variants:
            with self.subTest(key=key, value=str(value)[:25]):
                with self.assertRaises(identity.IdentityError):
                    identity.session_token({**valid, key: value})
        with self.assertRaises(identity.IdentityError): identity.session_token(None)

    def test_11_http_wire_carries_exact_session_and_retains_rejection(self):
        valid, records = self.precondition(), []
        token = identity.session_token(valid)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def handle_request(self):
                records.append((self.command, self.path, self.headers.get("X-CrimsonMC-Session")))
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                mismatch = self.headers.get("X-CrimsonMC-Session") not in (None, token)
                body = {"sessionMismatch": True, "instanceId": token} if mismatch else {"queued": True}
                data = json.dumps(body).encode()
                self.send_response(409 if mismatch else 202)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            do_POST = do_DELETE = handle_request
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            client = RedSide(f"http://127.0.0.1:{server.server_port}")
            for method, path in (("POST", "/api/objects"), ("POST", "/api/objects/7/project"),
                                 ("DELETE", "/api/objects/7")):
                self.assertEqual(client.request(path, method, {}, expected_session=valid)[0], 202)
            self.assertEqual([row[2] for row in records], [token] * 3)
            client.request("/api/objects", "POST", {})
            self.assertIsNone(records[-1][2])  # Existing diagnostic clients remain compatible.
            with self.assertRaises(GameAPIError) as error:
                client.request("/api/objects/7", "DELETE", expected_session={**valid, "creationTime100ns": "134358162934331039"})
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(error.exception.details, {"sessionMismatch": True, "instanceId": token})
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_12_invalid_precondition_never_reaches_http(self):
        with patch("bridge.red_side.urlopen") as request:
            with self.assertRaises(GameAPIError):
                RedSide().request("/api/objects/7", "DELETE", expected_session={"pid": 42})
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
