"""Check the fixed head-material diagnostic against isolated HTTP/processes.

Production candidate admission and real PAMI bytes are used. All installed files,
receipts, native responses and process identities belong to this temporary fixture.
No call reaches production API ports or a game installation.
"""
from __future__ import annotations

import copy
from functools import reduce
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import probe_steve_head_material as probe


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest(data):
    value = reduce(lambda acc, byte: ((acc ^ byte) * 1099511628211) % (1 << 64), data, 14695981039346656037)
    return {"length": len(data), "head16hex": data[:16].hex(), "fnv1a64": f"{value:016x}"}


class FakeHTTP:
    def __init__(self, payload, identity, evidence):
        self.payload, self.identity, self.evidence = payload, identity, evidence
        self.calls, self.posts, self.polls, self.mc_reads = [], 0, 0, 0
        self.status = {"apiVersion": 1, "gameVersion": probe.base.VERSION, "ready": True, "buildOk": True,
                       "pending": 0, "instanceId": f'{identity["pid"]}:{identity["creationTime100ns"]}',
                       "sessionPreconditions": True, "objectPreconditions": True}
        self.mc = {"engine": "Minecraft Java 1.21.1", "schemaVersion": 3, "revision": 25, "inventory": {},
                   "slots": [{"slot": i, "empty": True} for i in range(36)], "selectedSlot": 0,
                   "equipment": {"nativeApplied": False, "runtimeApplied": False, "slots": {}}, "blocks": []}
        self.pending = 0
        self.lost_post = self.bad_post = self.redirect = self.change_mc = False
        self.state = "read"
        self.mutate_result = lambda value: value
        self.mutate_post = lambda value: value
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, value):
                data = encoded(value) if isinstance(value, dict) else value
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
                if self.command == "GET" and self.path == "/api/status":
                    if owner.redirect:
                        self.send_response(302)
                        self.send_header("Location", owner.base + "/forbidden-redirect")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    return self.reply(200, owner.status)
                if self.command == "GET" and self.path == "/api/state":
                    owner.mc_reads += 1
                    value = copy.deepcopy(owner.mc)
                    if owner.change_mc and owner.mc_reads > 1:
                        value["revision"] += 1
                    return self.reply(200, value)
                if self.command == "POST" and self.path == "/api/prototype/resource-probe":
                    if body != {"resource": probe.RESOURCE}:
                        return self.reply(400, {"error": "unknown resource"})
                    intent = probe.base.strict_json(owner.evidence.read_bytes())
                    assert intent["result"]["state"] == "submissionUnknown" and intent["result"]["postAttempts"] == 1
                    owner.posts += 1
                    if owner.lost_post:
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    if owner.bad_post:
                        return self.reply(202, b'{"ticket":1,"ticket":2}')
                    return self.reply(202, owner.mutate_post({"ticket": 1, "resource": probe.RESOURCE, "state": "pending"}))
                if self.command == "GET" and path.path == "/api/prototype/resource-result":
                    assert parse_qs(path.query) == {"ticket": ["1"]}
                    owner.polls += 1
                    state = "pending" if owner.polls <= owner.pending else owner.state
                    value = {"ticket": 1, "resource": probe.RESOURCE, "path": probe.VIRTUAL_PATH, "state": state,
                             "attempts": 0 if state in ("pending", "expired") else 1,
                             "length": 0, "head16hex": "", "fnv1a64": "", "hashAlgorithm": probe.base.HASH_ALGORITHM,
                             "storedSize": 0, "decodedSize": 0, "storageFlags": 50,
                             "handlerPresent": False, "handlerReleased": False, "maxBytes": 16384}
                    if state == "read":
                        value.update(digest(owner.payload), storedSize=2500, decodedSize=len(owner.payload),
                                     handlerPresent=True, handlerReleased=True)
                    return self.reply(202 if state == "pending" else 200, owner.mutate_result(value))
                return self.reply(404, {"error": "forbidden endpoint"})

            do_GET = do_POST = do_DELETE = dispatch

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        if self.server.server_port in (8765, 8766):
            self.server.server_close()
            raise RuntimeError("Fixture accidentally selected a production port")
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class HeadMaterialChecks(unittest.TestCase):
    plan = probe.composition.DEFAULT_OUTPUT
    plan_digests = (probe.PLAN_SHA256, probe.UV_PLAN_SHA256, probe.VISIBLE_LAYER_PLAN_SHA256)

    @classmethod
    def setUpClass(cls):
        cls.assets = probe.load_assets(cls.plan)
        row = next(row for row in cls.assets["report"]["resources"] if row["virtualPath"] == probe.VIRTUAL_PATH)
        cls.payload = probe.installer.build_path(row["localFile"]).read_bytes()
        cls.root = tempfile.TemporaryDirectory(prefix="steve-head-material-check-", dir=probe.ROOT / "runtime")
        cls.addClassCleanup(cls.root.cleanup)
        cls.game_static = Path(cls.root.name) / "game"
        cls.game_static.mkdir()
        installation = json.loads((probe.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))
        cls.original_game = Path(installation["gameRoot"])
        cls.original_hashes = {**cls.assets["report"]["sourceIndexes"], **probe.UNTOUCHED_FILES}
        # Read-only copies of the pinned original files. All mutation tests use
        # these independent copies; no hardlinks or production writes exist.
        for relative, expected in cls.original_hashes.items():
            source = probe.installer.transaction.target(cls.original_game, relative.replace("\\", "/"))
            if probe.base.native.file_hash(source) != expected:
                raise ValueError("Original fixture source differs from its fixed pin")
            destination = probe.installer.transaction.target(cls.game_static, relative.replace("\\", "/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if probe.base.native.file_hash(destination) != expected:
                raise ValueError("Independent original index fixture copy differs")

    @classmethod
    def tearDownClass(cls):
        try:
            for relative, expected in cls.original_hashes.items():
                if probe.base.native.file_hash(probe.installer.transaction.target(cls.original_game, relative.replace("\\", "/"))) != expected:
                    raise AssertionError("Production source changed during isolated checks")
        finally:
            cls.root.cleanup()

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="case-", dir=self.root.name))
        self.game = self.game_static
        (self.game / "0041").mkdir(parents=True, exist_ok=True)
        (self.game / "meta").mkdir(exist_ok=True)
        (self.folder / "runtime").mkdir()
        self.output = self.folder / "runtime/evidence.json"
        self.receipt_path = self.folder / "runtime/asset-probe-active.json"
        self.identity = {"pid": 42123, "creationTime100ns": "134051756000000000",
                         "imagePath": str(self.game / "bin64/CrimsonDesert.exe"),
                         "imageSha256": probe.base.native.EXE_SHA256, "access": "PROCESS_QUERY_LIMITED_INFORMATION"}
        marker = {"owner": probe.installer.transaction.STEVE_OWNER, "id": "a" * 32, "planSha256": self.assets["planSha256"]}
        marker_raw = encoded(marker)
        (self.game / "0041/.crimsonmc-asset-probe-owner.json").write_bytes(marker_raw)
        for name in ("0.pamt", "0.paz"):
            shutil.copyfile(self.assets["plan"] / "package/0041" / name, self.game / "0041" / name)
        for name in ("0.pathc", "0.papgt"):
            shutil.copyfile(self.assets["plan"] / "metadata-after" / name, self.game / "meta" / name)
        files = {"0041/0.pamt": self.assets["report"]["files"]["package/0041/0.pamt"],
                 "0041/0.paz": self.assets["report"]["files"]["package/0041/0.paz"],
                 "0041/.crimsonmc-asset-probe-owner.json": probe.base.native.sha256(marker_raw)}
        self.receipt = {"format": "crimsonmc_asset_probe_v1", "owner": marker["owner"], "id": marker["id"],
                        "probeKind": probe.installer.KIND, "probeVariant": self.assets["probeVariant"], "status": "installed",
                        "gameRoot": str(self.game), "plan": str(self.assets["plan"]), "planSha256": self.assets["planSha256"],
                        "directoryName": "0041", "installedFiles": files,
                        "metadataAfter": {"meta/" + name: self.assets["report"]["files"]["metadata-after/" + name]
                                          for name in ("0.pathc", "0.papgt")},
                        "sourceIndexes": self.assets["report"]["sourceIndexes"],
                        "untouchedGameFiles": dict(probe.UNTOUCHED_FILES),
                        "absentOptionalMountedDirectories": self.assets["report"]["absentOptionalMountedDirectories"]}
        self.receipt_path.write_bytes(encoded(self.receipt))
        (self.folder / "runtime/installation.json").write_bytes(encoded({"gameRoot": str(self.game)}))
        self.fake = FakeHTTP(self.payload, self.identity, self.output)
        self.addCleanup(self.fake.close)

    def run_probe(self, *, assets=None, identity=None, timeout=0.1):
        api, mc = probe.HeadAPI(timeout=0.2), probe.HeadAPI("mc", timeout=0.2)
        api.base = mc.base = self.fake.base
        runner = probe.HeadProbe(api, mc, probe.base.Evidence(self.output), state_root=self.folder,
                                 identity=identity or (lambda: copy.deepcopy(self.identity)), timeout=timeout, interval=0.005)
        before_mc = copy.deepcopy(self.fake.mc)
        report = runner.run(assets or self.assets)
        self.assertEqual(probe.base.strict_json(self.output.read_bytes()), report)
        self.assertEqual(self.fake.mc, before_mc)
        self.assertTrue(all(method == "GET" or method == "POST" and path == "/api/prototype/resource-probe"
                            for method, path, _ in self.fake.calls))
        self.assertLessEqual(self.fake.posts, 1)
        for name in ("rendererMaterialSelected", "textureSamplingVerified", "steveSkinVerified", "appearanceApplied", "gameMemoryWritten"):
            self.assertFalse(report[name])
        return report

    def test_01_real_canonical_payload_resolves_only_file_bytes(self):
        report = self.run_probe()
        self.assertTrue(report["success"] and report["fileResolvableReadMatched"])
        self.assertEqual(report["result"]["nativeResult"]["length"], 16134)
        self.assertEqual(report["expectedResource"], {"resource": probe.RESOURCE, "path": probe.VIRTUAL_PATH,
                                                    "sha256": probe.PAYLOAD_SHA256, **digest(self.payload)})
        self.assertEqual(self.fake.posts, 1)
        self.assertEqual(report["sourcePlanSha256"], self.assets["planSha256"])
        self.assertEqual(report["probeVariant"], self.assets["probeVariant"])

    def test_02_exact_api_allowlist_no_arbitrary_paths_or_mc_writes(self):
        api, mc = probe.HeadAPI(), probe.HeadAPI("mc")
        for method, path, body in (("POST", "/api/prototype/resource-probe", {"resource": "steve_head_dds"}),
                                  ("POST", "/api/prototype/resource-probe", {"resource": probe.RESOURCE, "path": probe.VIRTUAL_PATH}),
                                  ("DELETE", "/api/prototype/resource-result?ticket=1", None),
                                  ("GET", "/api/prototype/resource-result?ticket=1&ticket=2", None)):
            with self.assertRaises(probe.ProbeError):
                api.request(path, method, body)
        with self.assertRaises(probe.ProbeError):
            mc.request("/api/add-item", "POST", {"item": "minecraft:stone"})
        self.assertFalse(self.fake.calls)

    def test_03_receipt_scope_and_ownership_tampering_rejected(self):
        mutations = (("owner", "foreign"), ("status", "restored"), ("probeKind", "oak-log"),
                     ("probeVariant", "old-body"), ("planSha256", "0" * 64), ("plan", str(self.folder)),
                     ("directoryName", "0042"), ("gameRoot", str(self.folder)), ("id", "x" * 32),
                     ("installedFiles", {}), ("metadataAfter", {}), ("sourceIndexes", {}))
        for key, value in mutations:
            with self.subTest(field=key):
                changed = copy.deepcopy(self.receipt)
                changed[key] = value
                self.receipt_path.write_bytes(encoded(changed))
                with self.assertRaises((probe.ProbeError, ValueError, OSError)):
                    probe.read_receipt(self.assets, self.folder)

    def test_04_installed_bytes_and_marker_must_match(self):
        for relative in ("0041/0.paz", "meta/0.pathc", "0041/.crimsonmc-asset-probe-owner.json"):
            with self.subTest(path=relative):
                path = self.game / relative
                original = path.read_bytes()
                path.write_bytes(b"changed")
                try:
                    with self.assertRaises((probe.ProbeError, ValueError)):
                        probe.read_receipt(self.assets, self.folder)
                finally:
                    path.write_bytes(original)

    def test_05_plan_manifest_and_archive_tampering_rejected(self):
        plan = probe.ROOT / "build" / ("steve-head-material-tamper-" + self.folder.name)
        self.assertFalse(plan.exists())
        shutil.copytree(self.assets["plan"], plan)
        try:
            manifest = plan / probe.composition.REPORT_NAME
            original = manifest.read_bytes()
            value = probe.base.strict_json(original)
            value["resources"][0]["sha256"] = "0" * 64
            manifest.write_bytes(encoded(value))
            with self.assertRaises(probe.ProbeError):
                probe.load_assets(plan)
            manifest.write_bytes(original)
            paz = plan / "package/0041/0.paz"
            data = bytearray(paz.read_bytes())
            data[10] ^= 1
            paz.write_bytes(data)
            with self.assertRaises((probe.ProbeError, ValueError)):
                probe.load_assets(plan)
        finally:
            self.assertTrue(plan.resolve().is_relative_to((probe.ROOT / "build").resolve()))
            shutil.rmtree(plan)

    def test_06_pami_source_changes_block_submission(self):
        local = self.folder / "head.pami"
        local.write_bytes(self.payload)
        assets = {**self.assets, "sourceHashes": {**self.assets["sourceHashes"], local: probe.PAYLOAD_SHA256}}
        local.write_bytes(self.payload[:-1] + bytes([self.payload[-1] ^ 1]))
        self.assertFalse(self.run_probe(assets=assets)["success"])
        self.assertEqual(self.fake.posts, 0)

    def test_07_ticket_path_resource_mismatch_stops(self):
        self.fake.mutate_result = lambda value: {**value, "ticket": 2}
        self.assertFalse(self.run_probe()["success"])
        self.assertEqual(self.fake.posts, 1)

    def test_08_native_sizes_and_handler_contract_rejected(self):
        # Validate every rejected combination without creating extra servers.
        api, mc = probe.HeadAPI(), probe.HeadAPI("mc")
        runner = probe.HeadProbe(api, mc, probe.base.Evidence(self.output), state_root=self.folder)
        valid = {"ticket": 1, "resource": probe.RESOURCE, "path": probe.VIRTUAL_PATH, "state": "read", "attempts": 1,
                 **digest(self.payload), "storedSize": 2500, "decodedSize": len(self.payload), "storageFlags": 50,
                 "handlerPresent": True, "handlerReleased": True, "maxBytes": 16384, "hashAlgorithm": probe.base.HASH_ALGORITHM}
        for key, value in (("storedSize", 16385), ("decodedSize", 16385), ("handlerPresent", False),
                           ("handlerReleased", False), ("maxBytes", 65536), ("storageFlags", 1),
                           ("length", True), ("path", "foreign/path"), ("resource", "oak_y_pami")):
            with self.subTest(field=key):
                with self.assertRaises(probe.ProbeError):
                    runner.validate_result(200, {**valid, key: value}, 1, self.assets["resource"])

    def test_09_lost_post_preserves_durable_unknown_and_never_retries(self):
        self.fake.lost_post = True
        report = self.run_probe()
        self.assertFalse(report["success"])
        self.assertEqual(report["result"]["state"], "submissionUnknown")
        self.assertEqual(self.fake.posts, 1)

    def test_10_duplicate_post_json_keys_never_retried(self):
        self.fake.bad_post = True
        self.assertFalse(self.run_probe()["success"])
        self.assertEqual(self.fake.posts, 1)

    def test_11_pending_then_read_has_one_post(self):
        self.fake.pending = 2
        report = self.run_probe()
        self.assertTrue(report["success"])
        self.assertEqual(report["result"]["polls"], 3)

    def test_12_timeout_retains_ticket_without_resubmission(self):
        self.fake.pending = 100000
        report = self.run_probe(timeout=0.05)
        self.assertFalse(report["success"])
        self.assertEqual(report["result"]["state"], "timeout")
        self.assertEqual(report["result"]["ticket"], 1)

    def test_13_mc_change_denies_success_and_client_never_mutates(self):
        self.fake.change_mc = True
        report = self.run_probe()
        self.assertFalse(report["success"] or report["mcStateUnchanged"])

    def test_14_process_reuse_and_native_instance_mismatch_rejected(self):
        def change(value):
            self.identity["creationTime100ns"] = "134051756000000001"
            return value
        self.fake.mutate_result = change
        report = self.run_probe()
        self.assertFalse(report["success"] or report["gameInstanceUnchanged"])

    def test_15_native_status_other_instance_blocks_post(self):
        self.fake.status["instanceId"] = "999:134051756000000000"
        self.assertFalse(self.run_probe()["success"])
        self.assertEqual(self.fake.posts, 0)

    def test_16_redirect_is_not_followed(self):
        self.fake.redirect = True
        self.assertFalse(self.run_probe()["success"])
        self.assertEqual(self.fake.posts, 0)
        self.assertFalse(any("redirect" in path for _, path, _ in self.fake.calls))

    def test_17_digest_mismatch_never_claims_resolved_match(self):
        self.fake.mutate_result = lambda value: {**value, "fnv1a64": "0" * 16}
        report = self.run_probe()
        self.assertFalse(report["success"] or report["fileResolvableReadMatched"])

    def test_18_receipt_changes_after_read_revoke_success(self):
        def change(value):
            receipt = copy.deepcopy(self.receipt)
            receipt["status"] = "restored"
            self.receipt_path.write_bytes(encoded(receipt))
            return value
        self.fake.mutate_result = change
        report = self.run_probe()
        self.assertFalse(report["success"] or report["installedContextUnchanged"])

    def test_19_foreign_external_override_blocks_post(self):
        (self.game / ".cdmw").mkdir()
        self.addCleanup((self.game / ".cdmw").rmdir)
        self.assertFalse(self.run_probe()["success"])
        self.assertEqual(self.fake.posts, 0)

    def test_20_original_source_index_and_untouched_file_bytes_checked(self):
        for relative in (next(iter(self.assets["report"]["sourceIndexes"])), "meta/0.papk", "meta/0.paver"):
            with self.subTest(path=relative):
                path = probe.installer.transaction.target(self.game, relative.replace("\\", "/"))
                original = path.read_bytes()
                path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
                try:
                    with self.assertRaises(probe.ProbeError):
                        probe.read_receipt(self.assets, self.folder)
                finally:
                    path.write_bytes(original)

    def test_21_untouched_receipt_hashes_cannot_legitimize_foreign_bytes(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["untouchedGameFiles"]["meta/0.papk"] = "0" * 64
        self.receipt_path.write_bytes(encoded(receipt))
        with self.assertRaises(probe.ProbeError):
            probe.read_receipt(self.assets, self.folder)

    def other_plan_contracts(self):
        return [(digest, probe.plan_contract(digest)[0]) for digest in self.plan_digests
                if digest != self.assets["planSha256"]]

    def test_22_pinned_plans_cannot_cross_receipts_or_variants(self):
        for other_sha, other_variant in self.other_plan_contracts():
            for mutation in ({"planSha256": other_sha}, {"probeVariant": other_variant},
                             {"planSha256": other_sha, "probeVariant": other_variant}):
                with self.subTest(fields=mutation):
                    self.receipt_path.write_bytes(encoded({**self.receipt, **mutation}))
                    with self.assertRaises(probe.ProbeError):
                        probe.read_receipt(self.assets, self.folder)
            with self.assertRaises(probe.ProbeError):
                probe.verify_assets({**self.assets, "probeVariant": other_variant})
        with self.assertRaises(probe.ProbeError):
            probe.plan_contract("0" * 64)

    def test_23_swapped_plan_manifest_blocks_post(self):
        for other_sha, other_variant in self.other_plan_contracts():
            with self.subTest(plan=other_sha):
                self.output = self.folder / "runtime" / ("wrong-plan-" + other_sha + ".json")
                self.fake.evidence = self.output
                assets = {**self.assets, "planSha256": other_sha, "probeVariant": other_variant}
                self.assertFalse(self.run_probe(assets=assets)["success"])
                self.assertEqual(self.fake.posts, 0)


class HeadUvMaterialChecks(HeadMaterialChecks):
    plan = probe.ROOT / "build/steve-head-uv-probe-overlay"


class HeadVisibleLayerMaterialChecks(HeadMaterialChecks):
    plan = probe.ROOT / "build/steve-head-visible-layer-probe-overlay"


if __name__ == "__main__":
    unittest.main(verbosity=2)
