"""Check resource diagnostics on ephemeral FakeHTTP, never a running game.

Real local native-block template hashes are checked, but all process identities
and engine/MC HTTP are isolated. No call reaches ports 8765/8766 or game files.
"""
from __future__ import annotations

import copy
from functools import reduce
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest import mock

import probe_native_resources as probe

IDENTITY = {"pid": 42123, "creationTime100ns": "134051756000000000",
            "imagePath": "C:\\FakeGame\\bin64\\CrimsonDesert.exe", "imageSha256": probe.native.EXE_SHA256,
            "access": "PROCESS_QUERY_LIMITED_INFORMATION"}


def reference_summary(data: bytes) -> dict:
    digest = reduce(lambda acc, byte: (acc ^ byte) * 1099511628211 % (1 << 64), data, 14695981039346656037)
    return {"length": len(data), "head16hex": data[:16].hex(), "fnv1a64": format(digest, "016x")}


class FakeHTTP:
    def __init__(self, assets: dict):
        self.calls, self.tickets = [], {}
        self.assets = assets
        self.status = {"apiVersion": 1, "gameVersion": probe.VERSION, "ready": True, "buildOk": True, "pending": 0}
        self.mc_state = {"revision": 7, "inventory": {"minecraft:oak_log": 14}, "blocks": [],
                         "slots": [{"slot": 0, "empty": False, "id": "minecraft:oak_log", "count": 14}], "selectedSlot": 0}
        self.pending = 0
        self.state_by_name = {}
        self.mutate_result = lambda value: value
        self.mutate_post = lambda value: value
        self.change_mc = self.fail_mc = self.lost_post = self.bad_post = self.redirect = False
        self.mc_reads = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, value):
                data = json.dumps(value).encode("utf-8") if isinstance(value, dict) else value
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def dispatch(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else None
                owner.calls.append((self.command, self.path, body))
                path = urlsplit(self.path)
                if self.command == "GET" and path.path == "/api/status":
                    if owner.redirect:
                        self.send_response(302)
                        self.send_header("Location", owner.base + "/redirect-forbidden")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    return self.reply(200, owner.status)
                if self.command == "GET" and path.path == "/api/state":
                    owner.mc_reads += 1
                    if owner.fail_mc:
                        return self.reply(503, {"error": "isolated MC unavailable"})
                    value = copy.deepcopy(owner.mc_state)
                    if owner.change_mc and owner.mc_reads > 1:
                        value["revision"] += 1
                    return self.reply(200, value)
                if self.command == "POST" and path.path == "/api/prototype/resource-probe":
                    if not isinstance(body, dict) or set(body) != {"resource"} or body["resource"] not in probe.RESOURCES:
                        return self.reply(400, {"error": "invalid fixed enum"})
                    ticket = len(owner.tickets) + 1
                    owner.tickets[ticket] = {"resource": body["resource"], "polls": 0}
                    if owner.lost_post:
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    if owner.bad_post:
                        return self.reply(202, b'{"ticket":1,"ticket":2}')
                    return self.reply(202, owner.mutate_post({"ticket": ticket, "resource": body["resource"], "state": "pending"}))
                if self.command == "GET" and path.path == "/api/prototype/resource-result":
                    ticket = int(parse_qs(path.query)["ticket"][0])
                    item = owner.tickets.get(ticket)
                    if item is None:
                        return self.reply(410, {"error": "isolated unknown ticket"})
                    item["polls"] += 1
                    name = item["resource"]
                    state = "pending" if item["polls"] <= owner.pending else owner.state_by_name.get(name, "read")
                    expected = owner.assets["resources"][name]
                    local = Path(owner.assets["reportPath"]).parent / expected["localFile"]
                    value = {"ticket": ticket, "resource": name, "path": probe.RESOURCES[name], "state": state,
                             "attempts": 0 if state in ("pending", "expired") else 1,
                             "length": 0, "head16hex": "", "fnv1a64": "", "hashAlgorithm": probe.HASH_ALGORITHM,
                             "storedSize": 0, "decodedSize": 0, "storageFlags": 0, "handlerPresent": False,
                             "handlerReleased": False, "maxBytes": 16384}
                    if state == "read":
                        value.update(reference_summary(local.read_bytes()))
                        value.update(storedSize=value["length"], decodedSize=value["length"], handlerPresent=True, handlerReleased=True)
                    return self.reply(202 if state == "pending" else 200, owner.mutate_result(value))
                return self.reply(404, {"error": "isolated forbidden endpoint"})

            do_GET = do_POST = do_DELETE = dispatch

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        if self.server.server_port in (8765, 8766):
            self.server.server_close()
            raise RuntimeError("FakeHTTP unexpectedly selected a production port")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ResourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = probe.load_assets(probe.ROOT / "build/native-block/native-block-report.json")
        (probe.ROOT / "runtime").mkdir(exist_ok=True)
        cls.sandbox = tempfile.TemporaryDirectory(prefix="resource-probe-check-", dir=probe.ROOT / "runtime")

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def setUp(self):
        self.fake = FakeHTTP(self.assets)
        self.addCleanup(self.fake.close)
        self.base_patches = [mock.patch.object(probe, "NATIVE_BASE", self.fake.base), mock.patch.object(probe, "MC_BASE", self.fake.base)]
        for patch in self.base_patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.folder = Path(tempfile.mkdtemp(prefix="case-", dir=self.sandbox.name))
        self.before_mc = copy.deepcopy(self.fake.mc_state)

    def run_probe(self, group="default", identity=None, timeout=0.1):
        output = self.folder / "result.json"
        runner = probe.ResourceProbe(probe.LoopbackAPI(timeout=0.2), probe.LoopbackAPI("mc", timeout=0.2),
                                     probe.Evidence(output), identity=identity or (lambda: copy.deepcopy(IDENTITY)),
                                     timeout=timeout, interval=0.005)
        result = runner.run(self.assets, group)
        self.assertEqual(probe.strict_json(output.read_bytes()), result)
        self.assertEqual(self.fake.mc_state, self.before_mc)
        self.assertTrue(all(method == "GET" or method == "POST" and path == "/api/prototype/resource-probe" for method, path, body in self.fake.calls))
        self.assertTrue(all(body is None or set(body) == {"resource"} for _, _, body in self.fake.calls))
        return result

    def posts(self):
        return [row for row in self.fake.calls if row[0] == "POST"]

    def test_01_default_real_templates_candidate_digest(self):
        result = self.run_probe()
        self.assertTrue(result["success"])
        self.assertEqual(len(self.posts()), 15)
        self.assertEqual(tuple(row[2]["resource"] for row in self.posts()), probe.GROUPS["default"])
        self.assertFalse(result["visualAcceptance"])
        self.assertFalse(result["collisionAcceptance"])

    def test_02_groups_and_27_unique_ticket_paths(self):
        for group, count in (("blue", 6), ("oak", 9), ("all", 27)):
            with self.subTest(group=group):
                self.folder = Path(tempfile.mkdtemp(prefix=group, dir=self.sandbox.name))
                self.fake.calls.clear()
                result = self.run_probe(group)
                self.assertTrue(result["success"])
                self.assertEqual(len(self.posts()), count)
                self.assertEqual(len({row["ticket"] for row in result["results"]}), count)
                self.assertTrue(all(row["nativeResult"]["path"] == probe.RESOURCES[row["expected"]["resource"]] for row in result["results"]))

    def test_03_pending_then_read_no_duplicate_posts(self):
        self.fake.pending = 2
        result = self.run_probe("blue")
        self.assertTrue(result["success"])
        self.assertTrue(all(row["polls"] == 3 for row in result["results"]))
        self.assertEqual(len(self.posts()), 6)

    def test_04_terminal_failure_collects_remaining_resources(self):
        for state in probe.TERMINAL - {"read"}:
            with self.subTest(state=state):
                self.folder = Path(tempfile.mkdtemp(prefix=state, dir=self.sandbox.name))
                self.fake.calls.clear()
                self.fake.state_by_name[probe.BLUE[0]] = state
                result = self.run_probe("blue")
                self.assertFalse(result["success"])
                self.assertEqual(result["results"][0]["state"], state)
                self.assertEqual(len(self.posts()), 6)
                self.assertTrue(result["mcStateUnchanged"])

    def test_05_timeout_preserves_original_ticket_without_resubmit(self):
        self.fake.pending = 100000
        result = self.run_probe("blue", timeout=0.05)
        self.assertFalse(result["success"])
        self.assertEqual(result["results"][0]["state"], "timeout")
        self.assertEqual(result["results"][0]["ticket"], 1)
        self.assertEqual(len(self.posts()), 1)

    def test_06_lost_post_response_preserves_unknown_submission(self):
        self.fake.lost_post = True
        result = self.run_probe("blue")
        self.assertFalse(result["success"])
        self.assertEqual(len(self.posts()), 1)
        self.assertEqual(len(self.fake.tickets), 1)
        self.assertEqual(result["results"][0]["state"], "submissionUnknown")

    def test_07_duplicate_json_post_keys_no_retry(self):
        self.fake.bad_post = True
        result = self.run_probe("blue")
        self.assertFalse(result["success"])
        self.assertEqual(len(self.posts()), 1)

    def test_08_resource_path_ticket_mismatch_stops(self):
        for key, value in (("ticket", 999), ("resource", "oak_y_prefab"), ("path", "object/../foreign.prefab")):
            with self.subTest(field=key):
                self.folder = Path(tempfile.mkdtemp(prefix=key, dir=self.sandbox.name))
                self.fake.calls.clear()
                self.fake.mutate_result = lambda row, key=key, value=value: {**row, key: value}
                result = self.run_probe("blue")
                self.assertFalse(result["success"])
                self.assertEqual(len(self.posts()), 1)

    def test_09_digest_length_head_mismatch_fails(self):
        for key in ("length", "head16hex", "fnv1a64"):
            with self.subTest(field=key):
                self.folder = Path(tempfile.mkdtemp(prefix=key, dir=self.sandbox.name))
                self.fake.calls.clear()
                def mutate(row, key=key):
                    row = copy.deepcopy(row)
                    if key == "length":
                        row["length"] += 1
                        row["storedSize"] = row["decodedSize"] = row["length"]
                    else:
                        row[key] = ("0" if row[key][0] != "0" else "1") + row[key][1:]
                    return row
                self.fake.mutate_result = mutate
                result = self.run_probe("blue")
                self.assertFalse(result["success"])
                self.assertFalse(result["allReadAndMatched"])
                self.assertEqual(len(self.posts()), 6)

    def test_10_storage_flags_one_selects_stored_size(self):
        self.fake.mutate_result = lambda row: {**row, "storageFlags": 1, "decodedSize": 0}
        self.assertTrue(self.run_probe("blue")["success"])

    def test_11_read_handler_or_bound_failure(self):
        for key, value in (("handlerReleased", False), ("handlerPresent", False), ("storedSize", 16385),
                           ("head16hex", "FF"), ("fnv1a64", ""), ("maxBytes", 0), ("attempts", 4)):
            with self.subTest(field=key):
                self.folder = Path(tempfile.mkdtemp(prefix=key, dir=self.sandbox.name))
                self.fake.calls.clear()
                self.fake.mutate_result = lambda row, key=key, value=value: {**row, key: value}
                result = self.run_probe("blue")
                self.assertFalse(result["success"])
                self.assertEqual(len(self.posts()), 1)

    def test_12_readiness_and_exe_preflight(self):
        for key, value in (("gameVersion", "1.0.0.2977"), ("apiVersion", True), ("buildOk", False), ("ready", False)):
            with self.subTest(field=key):
                self.folder = Path(tempfile.mkdtemp(prefix=key, dir=self.sandbox.name))
                self.fake.calls.clear()
                self.fake.status[key] = value
                self.assertFalse(self.run_probe("blue")["success"])
                self.assertEqual(self.posts(), [])
                self.fake.status[key] = {"gameVersion": probe.VERSION, "apiVersion": 1, "buildOk": True, "ready": True}[key]
        self.folder = Path(tempfile.mkdtemp(prefix="exe", dir=self.sandbox.name))
        self.assertFalse(self.run_probe("blue", identity=lambda: {**IDENTITY, "imageSha256": "0" * 64})["success"])
        self.assertEqual(self.posts(), [])

    def test_13_instance_restart_stops_before_next_request(self):
        count = 0
        def identity():
            nonlocal count
            count += 1
            return {**IDENTITY, "creationTime100ns": str(int(IDENTITY["creationTime100ns"]) + (count > 4))}
        result = self.run_probe("blue", identity=identity)
        self.assertFalse(result["success"])
        self.assertFalse(result["gameInstanceUnchanged"])
        self.assertEqual(len(self.posts()), 1)

    def test_14_mc_changes_or_unavailable_are_failures_without_writes(self):
        self.fake.change_mc = True
        result = self.run_probe("blue")
        self.assertFalse(result["success"])
        self.assertFalse(result["mcStateUnchanged"])
        self.fake.change_mc, self.fake.fail_mc = False, True
        self.folder = Path(tempfile.mkdtemp(prefix="mcfail", dir=self.sandbox.name))
        self.fake.calls.clear()
        self.assertFalse(self.run_probe("blue")["success"])
        self.assertEqual(self.posts(), [])

    def test_15_closed_http_allowlist_no_network_for_rejected_inputs(self):
        api, mc = probe.LoopbackAPI(), probe.LoopbackAPI("mc")
        rejected = [(api, "/api/objects", "POST", {"prefab": "x"}),
                    (api, "/api/prototype/resource-probe", "POST", {"resource": "oak_y_prefab", "path": "x"}),
                    (api, "/api/prototype/resource-probe", "POST", {"resource": "../x"}),
                    (api, "/api/prototype/resource-probe", "POST", {"resource": []}),
                    (api, "/api/prototype/resource-result?ticket=01", "GET", None),
                    (api, "/api/prototype/resource-result?ticket=2147483647", "GET", None),
                    (mc, "/api/select", "POST", {"slot": 0}), (mc, "/api/state", "DELETE", None)]
        for client, path, method, body in rejected:
            with self.assertRaises(probe.ProbeError):
                client.request(path, method, body)
        self.assertEqual(self.fake.calls, [])

    def test_16_redirect_not_followed(self):
        self.fake.redirect = True
        self.assertFalse(self.run_probe("blue")["success"])
        self.assertFalse(any(path == "/redirect-forbidden" for _, path, _ in self.fake.calls))
        self.assertEqual(self.posts(), [])

    def test_17_fnv_known_vectors_and_strict_json(self):
        for data, digest in ((b"", "cbf29ce484222325"), (b"a", "af63dc4c8601ec8c"), (b"foobar", "85944171f73967e8")):
            self.assertEqual(probe.fnv1a64(data), digest)
            self.assertEqual(reference_summary(data)["fnv1a64"], digest)
        for raw in (b'{"x":1,"x":2}', b'{"n":NaN}', b'[]', b'\xff'):
            with self.assertRaises(probe.ProbeError):
                probe.strict_json(raw)

    def copy_inputs(self):
        folder = Path(tempfile.mkdtemp(prefix="resource-input-check-", dir=probe.ROOT / "build"))
        self.addCleanup(shutil.rmtree, folder)
        source = Path(self.assets["reportPath"])
        report = probe.strict_json(source.read_bytes())
        for name in report["files"]:
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source.parent / name, target)
        output = folder / source.name
        output.write_bytes(source.read_bytes())
        return folder, output, report

    def test_18_local_sha_tamper_and_polluted_candidate_paths(self):
        folder, output, report = self.copy_inputs()
        target = folder / report["candidateResources"][0]["localFile"]
        target.write_bytes(target.read_bytes() + b"tamper")
        with self.assertRaisesRegex(probe.ProbeError, "SHA256"):
            probe.load_assets(output)
        source = Path(self.assets["reportPath"]).parent / report["candidateResources"][0]["localFile"]
        target.write_bytes(source.read_bytes())
        for value in ("../outside", "C:/foreign", "candidate/../../outside", "candidate\\object\\x"):
            changed = copy.deepcopy(report)
            changed["candidateResources"][0]["localFile"] = value
            output.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(probe.ProbeError, "path"):
                probe.load_assets(output)
        self.assertEqual(self.fake.calls, [])

    def test_19_provenance_duplicates_extra_files_and_false_claims(self):
        _, output, report = self.copy_inputs()
        changes = []
        changed = copy.deepcopy(report); changed["candidateResources"][0]["templateSha256"] = "0" * 64; changes.append(changed)
        changed = copy.deepcopy(report); changed["candidateResources"][1] = changed["candidateResources"][0]; changes.append(changed)
        changed = copy.deepcopy(report); changed["files"]["candidate/foreign"] = "0" * 64; changes.append(changed)
        changed = copy.deepcopy(report); changed["integration"]["nativeRenderable"] = True; changes.append(changed)
        changed = copy.deepcopy(report); changed["cdmw"]["commit"] = "foreign"; changes.append(changed)
        for changed in changes:
            output.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(probe.ProbeError):
                probe.load_assets(output)
        self.assertEqual(self.fake.calls, [])

    def test_20_output_scope_existing_evidence_and_ownership(self):
        for path in (probe.ROOT / "build/not-runtime.json", probe.ROOT / "runtime", self.folder / "bad.txt"):
            with self.assertRaises(probe.ProbeError):
                probe.Evidence(path)
        output = self.folder / "result.json"
        output.write_text("user evidence", encoding="utf-8")
        with self.assertRaises(probe.ProbeError):
            probe.Evidence(output)
        self.assertEqual(output.read_text(), "user evidence")
        journal = probe.Evidence(self.folder / "owned.json")
        journal.write({"value": "first"})
        journal.path.write_text("foreign change", encoding="utf-8")
        with self.assertRaisesRegex(probe.ProbeError, "ownership"):
            journal.write({"value": "second"})
        self.assertEqual(journal.path.read_text(), "foreign change")
        self.assertEqual(self.fake.calls, [])

    def test_21_real_junction_inputs_and_outputs_rejected(self):
        # NTFS junctions are created only below this test's owned ignored folder.
        if not hasattr(Path, "is_junction"):
            self.fail("Python 3.12+ Path.is_junction is required for this Windows protection check")
        real = self.folder / "real"
        real.mkdir()
        alias = self.folder / "alias"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(real)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            with self.assertRaisesRegex(ValueError, "junction"):
                probe.Evidence(alias / "out.json")
            # Junction outside build is rejected by scope first; build alias tests ancestry.
            build_alias = probe.ROOT / "build" / ("resource-check-link-" + self.folder.name)
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(build_alias), str(real)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            try:
                with self.assertRaisesRegex(ValueError, "junction"):
                    probe.load_assets(build_alias / "native-block-report.json")
            finally:
                build_alias.rmdir()
        finally:
            alias.rmdir()
        self.assertEqual(self.fake.calls, [])

    def test_22_cli_failure_exit_and_default_fixed_ports_without_real_http(self):
        with mock.patch("sys.argv", ["probe_native_resources.py", "--assets", self.assets["reportPath"], "--output", str(self.folder / "cli.json")]):
            with mock.patch.object(probe, "game_instance", return_value=IDENTITY), mock.patch.object(probe.ResourceProbe, "instance", return_value=IDENTITY):
                self.fake.state_by_name[probe.BLUE[0]] = "notFound"
                self.assertEqual(probe.main(), 1)
        self.assertEqual(len(self.posts()), 15)
        self.assertEqual(probe.LoopbackAPI().base, self.fake.base)
        with mock.patch.object(probe, "NATIVE_BASE", "http://127.0.0.1:8765"), mock.patch.object(probe, "MC_BASE", "http://127.0.0.1:8766"):
            self.assertEqual(probe.LoopbackAPI().base, "http://127.0.0.1:8765")
            self.assertEqual(probe.LoopbackAPI("mc").base, "http://127.0.0.1:8766")


if __name__ == "__main__":
    unittest.main(verbosity=2)
