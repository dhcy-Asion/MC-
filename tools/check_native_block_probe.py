"""Exercise the removable block diagnostic against an isolated FakeHTTP API.

Starts only an ephemeral 127.0.0.1 server, with an injected fake process identity.
Never contacts port 8765/8766, starts a game, writes game files or consumes MC.
"""
from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from urllib.parse import urlsplit, parse_qs
from unittest import mock

import probe_native_block as probe


IDENTITY = {"pid": 42123, "creationTime100ns": "134051756000000000",
            "imagePath": "C:\\FakeGame\\bin64\\CrimsonDesert.exe", "imageSha256": probe.native.EXE_SHA256,
            "access": "PROCESS_QUERY_LIMITED_INFORMATION"}


def object_row(uid=42, prefab=None, project="Untitled 1", x=-0.5, y=10.03, z=3.5) -> dict:
    return {"uid": uid, "prefab": prefab or probe.PREFABS["y"], "project": project,
            "x": x, "y": y, "z": z, "yaw": 0, "pitch": 0, "roll": 0,
            "scale": 1, "hidden": False, "group": 0}


class FakeHTTP:
    def __init__(self):
        self.calls, self.objects, self.tickets = [], {}, {}
        self.status = {"apiVersion": 1, "ready": True, "gameVersion": probe.VERSION, "buildOk": True,
                       "buildMessage": "isolated test", "pending": 0}
        self.player, self.camera = {"x": 0, "y": 10, "z": 0}, {"x": 0, "y": 12, "z": -5, "axis": {"x": 0, "y": 0, "z": 1}, "view": {"x": 0, "z": 1}}
        self.registry_delay = 0
        self.ground_pending = 1
        self.collision_ready = True
        self.miss, self.expired, self.lost_spawn, self.lost_project, self.lost_delete = False, False, False, False, False
        self.delete_stalls, self.bad_pagination, self.assign_foreign = False, False, False
        self.reject_project, self.projects_fail_after_spawn, self.autosave = False, False, False
        self.projects, self.editing_project = ["Untitled 1"], "Untitled 1"
        self.implicit_project_saves, self.implicit_settings_saves = [], 0
        self.mc_revision, self.change_mc = 7, False
        self.ground_height = lambda x, z: 10.0
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, value):
                data = json.dumps(value, allow_nan=True).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def dispatch(self):
                path = urlsplit(self.path)
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else None
                state.calls.append((self.command, self.path, body))
                if self.command == "GET" and path.path == "/api/status":
                    return self.reply(200, state.status)
                if self.command == "GET" and path.path == "/api/player":
                    return self.reply(200, state.player)
                if self.command == "GET" and path.path == "/api/camera":
                    return self.reply(200, state.camera)
                if self.command == "GET" and path.path == "/api/projects":
                    if state.projects_fail_after_spawn and 42 in state.objects:
                        return self.reply(503, {"error": "isolated project-list failure"})
                    return self.reply(200, {"items": state.projects})
                if self.command == "GET" and path.path == "/api/state":
                    if state.change_mc:
                        state.mc_revision += 1
                    return self.reply(200, {"revision": state.mc_revision, "inventory": {"minecraft:oak_log": 14}, "blocks": []})
                if self.command == "POST" and path.path == "/api/prototype/ground-probe":
                    ticket = len(state.tickets) + 1
                    state.tickets[ticket] = {"query": body, "polls": 0}
                    return self.reply(202, {"ticket": ticket})
                if self.command == "GET" and path.path == "/api/prototype/ground-result":
                    ticket = int(parse_qs(path.query)["ticket"][0])
                    query = state.tickets[ticket]
                    query["polls"] += 1
                    if state.expired:
                        return self.reply(410, {"error": "expired"})
                    if query["polls"] <= state.ground_pending:
                        return self.reply(202, {"state": "pending"})
                    if state.miss:
                        return self.reply(200, {"state": "miss"})
                    hit = {"state": "hit", "x": query["query"]["x"],
                           "y": state.ground_height(query["query"]["x"], query["query"]["z"]), "z": query["query"]["z"]}
                    for row in state.objects.values():
                        if not row["hidden"] and state.collision_ready and row["x"] <= hit["x"] <= row["x"] + 1 and row["z"] <= hit["z"] <= row["z"] + 1:
                            hit["y"] = row["y"] + 1
                    return self.reply(200, hit)
                if self.command == "GET" and path.path == "/api/objects":
                    offset = int(parse_qs(path.query)["offset"][0])
                    state.registry_delay = max(0, state.registry_delay - 1)
                    values = list(state.objects.values()) if not state.registry_delay else []
                    return self.reply(200, {"total": len(values), "offset": offset, "limit": 500,
                                            "nextOffset": offset if state.bad_pagination else None,
                                            "items": values})
                if self.command == "POST" and path.path == "/api/objects":
                    # Match core::SpawnAtLinked -> EnsureEditingProject, including
                    # the nonempty initial project that the former fixture hid.
                    if state.editing_project not in state.projects:
                        number = 1
                        while f"Untitled {number}" in state.projects:
                            number += 1
                        state.editing_project = f"Untitled {number}"
                        state.projects.append(state.editing_project)
                        state.implicit_project_saves.append(state.editing_project)
                        state.implicit_settings_saves += 1
                    state.objects[42] = object_row(prefab=body["prefab"], project=state.editing_project,
                                                  x=body["x"], y=body["y"], z=body["z"])
                    if state.lost_spawn:
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    return self.reply(202, {"uid": 42, "queued": True})
                if path.path.startswith("/api/objects/"):
                    pieces = path.path.split("/")
                    uid = int(pieces[3])
                    row = state.objects.get(uid)
                    if row is None:
                        return self.reply(404, {"error": "not found"})
                    if self.command == "POST" and pieces[-1] == "project":
                        if state.reject_project:
                            return self.reply(409, {"error": "isolated assignment refused before mutation"})
                        row["project"] = "SomeoneElse" if state.assign_foreign else body["name"]
                        if state.lost_project:
                            self.connection.shutdown(socket.SHUT_RDWR)
                            self.connection.close()
                            return
                        return self.reply(200, {"uid": uid, "project": row["project"]})
                    if self.command == "DELETE":
                        if not state.delete_stalls:
                            del state.objects[uid]
                        if state.lost_delete:
                            self.connection.shutdown(socket.SHUT_RDWR)
                            self.connection.close()
                            return
                        return self.reply(202, {"uid": uid, "queued": True})
                    if self.command == "GET":
                        return self.reply(200, row)
                return self.reply(404, {"error": "isolated unsupported endpoint"})

            do_GET = do_POST = do_DELETE = dispatch

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def settings(self, instance):
        return {"path": "fake/settings.txt", "sha256": "0" * 64,
                "projectAutoSave": self.autosave, "editingProjectOnDisk": self.editing_project,
                "observation": "injected isolated settings snapshot"}


class NativeBlockProbeChecks(unittest.TestCase):
    def setUp(self):
        self.fake = FakeHTTP()
        self.temp = tempfile.TemporaryDirectory(prefix="native-block-probe-test-", dir=probe.ROOT / "runtime")
        self.path = Path(self.temp.name) / "native-block-probe.json"
        self.identity = dict(IDENTITY)
        self.api = probe.LoopbackAPI(self.fake.base, timeout=0.2)
        self.journal = probe.Journal(self.path)
        self.subject = probe.NativeBlockProbe(self.api, self.journal, probe.LoopbackAPI(self.fake.base, "mc", 0.2),
                                              timeout=0.2, interval=0.01, identity=lambda: dict(self.identity),
                                              settings=self.fake.settings)

    def tearDown(self):
        self.fake.close()
        self.temp.cleanup()

    def mutations(self, method="POST", path="/api/objects"):
        return [row for row in self.fake.calls if row[:2] == (method, path)]

    def test_01_ticket_pending_spawn_collision_and_exact_cleanup(self):
        self.fake.registry_delay = 3
        result = self.subject.spawn()
        self.assertEqual(result["phase"], "spawned")
        self.assertTrue(result["registryConfirmed"] and result["collisionVerified"])
        self.assertFalse(result["visualVerified"] or result["nativeLiveStateExposed"])
        self.assertAlmostEqual(result["collisionAfter"]["deltaFromOriginalGround"], 1.03)
        self.assertEqual(result["gameInstance"], IDENTITY)
        self.assertEqual(result["initialProject"], "Untitled 1")
        self.assertEqual(result["initialObject"]["project"], "Untitled 1")
        self.assertTrue(result["initialOwnershipConfirmed"])
        self.assertEqual(result["newProjectNamesAfterAdmission"], [])
        self.assertTrue(result["mcStateUnchanged"])
        self.assertEqual(len(self.mutations()), 1)
        cleaned = self.subject.cleanup()
        self.assertEqual(cleaned["phase"], "cleaned")
        self.assertTrue(cleaned["registryRemoved"] and cleaned["collisionRemovedVerified"])
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)
        self.assertFalse(self.fake.objects)
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)
        self.assertTrue(all("/ui/" not in path and "/research/" not in path and "/npc" not in path for _, path, _ in self.fake.calls))

    def test_02_existing_probe_no_duplicate_mutation(self):
        self.subject.spawn("x")
        count = len(self.fake.calls)
        with self.assertRaisesRegex(probe.ProbeError, "existing probe journal"):
            self.subject.spawn("y")
        self.assertEqual(len(self.fake.calls), count)
        self.assertEqual(len(self.mutations()), 1)

    def test_03_foreign_existing_probe_retained(self):
        self.fake.objects[7] = object_row(7, project=probe.PROJECT, x=20)
        with self.assertRaisesRegex(probe.ProbeError, "Existing native asset diagnostic"):
            self.subject.spawn()
        self.assertFalse(self.mutations())
        self.assertFalse(self.mutations("DELETE", "/api/objects/7"))

    def test_04_ground_miss_invalidated_and_pending_never_spawn(self):
        for option in ("miss", "expired", "ground_pending"):
            with self.subTest(option=option):
                self.fake.miss, self.fake.expired, self.fake.ground_pending = False, False, 1
                setattr(self.fake, option, 1000000 if option == "ground_pending" else True)
                with self.assertRaises(probe.ProbeError):
                    self.subject.spawn()
                self.assertFalse(self.mutations())

    def test_05_lost_spawn_response_journal_blocks_retries_and_cleanup(self):
        self.fake.lost_spawn = True
        with self.assertRaisesRegex(probe.ProbeError, "Do not blindly repeat"):
            self.subject.spawn()
        saved = self.journal.read()
        self.assertTrue(saved["spawnSubmitted"])
        self.assertIsNone(saved["uid"])
        self.assertEqual(saved["phase"], "unresolved")
        self.assertEqual(len(self.mutations()), 1)
        with self.assertRaisesRegex(probe.ProbeError, "existing probe journal"):
            self.subject.spawn()
        with self.assertRaisesRegex(probe.ProbeError, "no known owned UID"):
            self.subject.cleanup()
        self.assertEqual(len(self.mutations()), 1)
        self.assertFalse(self.mutations("DELETE", "/api/objects/42"))

    def test_06_registry_presence_is_not_physical_live_or_visual(self):
        self.fake.collision_ready = False
        with self.assertRaisesRegex(probe.ProbeError, "Physical ground height"):
            self.subject.spawn()
        saved = self.journal.read()
        self.assertTrue(saved["registryConfirmed"])
        self.assertFalse(saved["collisionVerified"] or saved["visualVerified"])
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")

    def test_07_cleanup_refuses_each_ownership_mismatch(self):
        self.subject.spawn()
        original = copy.deepcopy(self.fake.objects[42])
        for key, value in (("prefab", "/object/foreign.prefab"), ("project", "UserProject"), ("x", 15), ("scale", 2), ("yaw", 90)):
            self.fake.objects[42] = copy.deepcopy(original)
            self.fake.objects[42][key] = value
            with self.subTest(key=key), self.assertRaises(probe.ProbeError):
                self.subject.cleanup()
            self.assertFalse(self.mutations("DELETE", "/api/objects/42"))

    def test_08_uid_reuse_after_game_restart_refuses_delete(self):
        self.subject.spawn()
        self.identity["creationTime100ns"] = "134051756000000001"
        with self.assertRaisesRegex(probe.ProbeError, "Game instance changed"):
            self.subject.cleanup()
        self.assertFalse(self.mutations("DELETE", "/api/objects/42"))

    def test_09_lost_project_response_can_cleanup_only_verified_owner(self):
        self.fake.lost_project = True
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        self.assertEqual(self.fake.objects[42]["project"], probe.PROJECT)
        self.assertEqual(self.journal.read()["uid"], 42)
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")

    def test_10_lost_delete_response_no_repeat_and_read_only_recovery(self):
        self.subject.spawn()
        self.fake.lost_delete = True
        with self.assertRaises(probe.ProbeError):
            self.subject.cleanup()
        self.assertEqual(self.journal.read()["phase"], "cleanup_unresolved")
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)

    def test_11_cleanup_pending_does_not_repeat_delete(self):
        self.subject.spawn()
        self.fake.delete_stalls = True
        with self.assertRaisesRegex(probe.ProbeError, "stayed in the registry"):
            self.subject.cleanup()
        with self.assertRaisesRegex(probe.ProbeError, "previous cleanup outcome"):
            self.subject.cleanup()
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)

    def test_12_wrong_version_unready_nonfinite_camera_and_pagination_rejected(self):
        self.fake.status["gameVersion"] = "unknown"
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        self.fake.status["gameVersion"] = probe.VERSION
        self.fake.status["ready"] = False
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        self.fake.status["ready"] = True
        self.fake.camera["view"] = {"x": 0, "z": 0}
        with self.assertRaisesRegex(probe.ProbeError, "unit direction"):
            self.subject.spawn()
        self.fake.camera["view"] = {"x": 0, "z": 1}
        self.fake.player["x"] = float("nan")
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        self.fake.player["x"] = 0
        self.fake.bad_pagination = True
        with self.assertRaisesRegex(probe.ProbeError, "pagination"):
            self.subject.spawn()
        self.assertFalse(self.mutations())

    def test_13_loopback_allowlist_proxy_redirect_and_evidence_boundary(self):
        for base in ("https://127.0.0.1:8765", "http://example.com:8765", "http://localhost:8765", "http://user@127.0.0.1:8765", "http://127.0.0.1:8765/remote"):
            with self.subTest(base=base), self.assertRaises(probe.ProbeError):
                probe.LoopbackAPI(base)
        for method, path in (("POST", "/api/research/write"), ("POST", "/api/camera"), ("POST", "/api/npc"), ("POST", "/api/scene/clear"), ("POST", "/api/projects/save")):
            with self.assertRaisesRegex(probe.ProbeError, "allowlist"):
                self.api.request(path, method, {})
        self.assertIsNone(probe.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "http://example.com"))
        with self.assertRaisesRegex(probe.ProbeError, "ignored runtime"):
            probe.Journal(probe.ROOT / "docs/probe.json")
        with self.assertRaisesRegex(probe.ProbeError, "ignored runtime"):
            probe.Journal(probe.ROOT / "runtime/../docs/probe.json")
        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda p: p == self.path):
            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                probe.Journal(self.path)

    def test_14_optional_mc_unavailable_or_changed_reports_without_revert(self):
        self.subject.mc = None
        result = self.subject.spawn("z")
        self.assertIsNone(result["mcStateUnchanged"])
        self.assertTrue(result["collisionVerified"])
        self.subject.cleanup()
        self.subject.mc = probe.LoopbackAPI(self.fake.base, "mc", 0.2)
        self.fake.change_mc = True
        result = self.subject.spawn()
        self.assertFalse(result["mcStateUnchanged"])
        self.assertTrue(all(method == "GET" for method, path, _ in self.fake.calls if path == "/api/state"))

    def test_15_instance_change_during_preflight_never_submits_spawn(self):
        identity_calls = []
        def identity():
            identity_calls.append(1)
            result = dict(IDENTITY)
            if len(identity_calls) > 1:
                result["creationTime100ns"] = "134051756000000001"
            return result
        self.subject.identity = identity
        with self.assertRaisesRegex(probe.ProbeError, "Game instance changed"):
            self.subject.spawn()
        self.assertFalse(self.mutations())
        self.assertFalse(self.journal.read()["spawnSubmitted"])

    def test_16_bad_project_ack_cannot_authorize_foreign_cleanup(self):
        self.fake.assign_foreign = True
        with self.assertRaisesRegex(probe.ProbeError, "project assignment"):
            self.subject.spawn()
        self.assertFalse(self.journal.read()["registryConfirmed"])
        with self.assertRaisesRegex(probe.ProbeError, "ownership differs"):
            self.subject.cleanup()
        self.assertFalse(self.mutations("DELETE", "/api/objects/42"))

    def test_17_existing_nonempty_editing_project_is_captured_before_assignment(self):
        self.fake.projects, self.fake.editing_project = ["Player Build"], "Player Build"
        self.fake.objects[7] = object_row(7, prefab="/object/user_asset.prefab", project="Player Build", x=20)
        user_object = copy.deepcopy(self.fake.objects[7])
        result = self.subject.spawn()
        self.assertEqual(result["initialProject"], "Player Build")
        self.assertEqual(result["projectsBefore"], ["Player Build"])
        self.assertEqual(result["initialObject"]["project"], "Player Build")
        self.assertEqual(self.fake.objects[42]["project"], probe.PROJECT)
        self.subject.cleanup()
        self.assertEqual(self.fake.projects, ["Player Build"])
        self.assertEqual(self.fake.objects, {7: user_object})
        self.assertFalse(self.fake.implicit_project_saves)
        self.assertTrue(all(method == "GET" for method, path, _ in self.fake.calls if path.startswith("/api/projects")))

    def test_18_assignment_rejected_can_cleanup_only_journalled_initial_project(self):
        self.fake.reject_project = True
        with self.assertRaisesRegex(probe.ProbeError, "project assignment"):
            self.subject.spawn()
        saved = self.journal.read()
        self.assertEqual(saved["failureAtPhase"], "project_assignment_submitted")
        self.assertTrue(saved["initialOwnershipConfirmed"])
        self.assertFalse(saved["registryConfirmed"])
        self.assertEqual(self.fake.objects[42]["project"], "Untitled 1")
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")
        self.assertEqual(self.fake.projects, ["Untitled 1"])
        self.assertEqual(len(self.mutations("DELETE", "/api/objects/42")), 1)

    def test_19_initial_project_changed_after_failed_assignment_refuses_cleanup(self):
        self.fake.reject_project = True
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        self.fake.objects[42]["project"] = "User Adopts Probe"
        with self.assertRaisesRegex(probe.ProbeError, "ownership differs"):
            self.subject.cleanup()
        self.assertFalse(self.mutations("DELETE", "/api/objects/42"))

    def test_20_implicit_untitled_saved_by_native_is_recorded_and_retained(self):
        self.fake.editing_project = ""
        result = self.subject.spawn()
        self.assertEqual(result["projectSettingsBefore"]["editingProjectOnDisk"], "")
        self.assertEqual(result["initialProject"], "Untitled 2")
        self.assertEqual(result["projectsBefore"], ["Untitled 1"])
        self.assertEqual(result["newProjectNamesAfterAdmission"], ["Untitled 2"])
        self.assertEqual(self.fake.implicit_project_saves, ["Untitled 2"])
        self.assertEqual(self.fake.implicit_settings_saves, 1)
        self.subject.cleanup()
        self.assertEqual(self.fake.projects, ["Untitled 1", "Untitled 2"])
        self.assertEqual(self.fake.editing_project, "Untitled 2")
        self.assertTrue(all(method == "GET" for method, path, _ in self.fake.calls if path.startswith("/api/projects")))

    def test_21_failure_before_assignment_preserves_initial_ownership_for_cleanup(self):
        self.fake.projects_fail_after_spawn = True
        with self.assertRaisesRegex(probe.ProbeError, "project list"):
            self.subject.spawn()
        saved = self.journal.read()
        self.assertEqual(saved["initialProject"], "Untitled 1")
        self.assertTrue(saved["initialOwnershipConfirmed"])
        self.assertFalse(saved["projectAssignmentSubmitted"])
        self.assertFalse(self.mutations("POST", "/api/objects/42/project"))
        self.assertEqual(self.subject.cleanup()["phase"], "cleaned")

    def test_22_enabled_autosave_prevents_transient_admission_without_setting_writes(self):
        self.fake.autosave = True
        with self.assertRaisesRegex(probe.ProbeError, "autosave"):
            self.subject.spawn()
        self.assertFalse(self.mutations())
        self.assertIsNone(self.journal.read())
        self.assertTrue(self.fake.autosave)
        self.assertFalse(self.fake.implicit_project_saves)

    def test_23_autosave_change_during_preflight_prevents_spawn(self):
        settings_calls = []
        def settings(instance):
            settings_calls.append(1)
            result = self.fake.settings(instance)
            result["projectAutoSave"] = len(settings_calls) > 1
            return result
        self.subject.settings = settings
        with self.assertRaisesRegex(probe.ProbeError, "autosave"):
            self.subject.spawn()
        self.assertFalse(self.mutations())
        self.assertFalse(self.journal.read()["spawnSubmitted"])

    def test_24_settings_reader_is_read_only_and_matches_native_last_exact_key(self):
        image = Path(self.temp.name) / "bin64/CrimsonDesert.exe"
        settings = image.parent / "cdmodkit/settings.txt"
        settings.parent.mkdir(parents=True)
        content = b"project_autosave=1\r\nproject_autosave=0 \r\nediting_project=Untitled 1\r\n"
        settings.write_bytes(content)
        observed = probe.project_settings({"imagePath": str(image)})
        self.assertFalse(observed["projectAutoSave"])
        self.assertEqual(observed["editingProjectOnDisk"], "Untitled 1")
        self.assertEqual(settings.read_bytes(), content)
        for invalid in (b"project_autosave=1\n", b" project_autosave=0\n", b"editing_project=Untitled 1\n"):
            settings.write_bytes(invalid)
            with self.assertRaisesRegex(probe.ProbeError, "project_autosave=0"):
                probe.project_settings({"imagePath": str(image)})
            self.assertEqual(settings.read_bytes(), invalid)

    def test_25_no_initial_capture_cannot_authorize_cleanup_by_arbitrary_project(self):
        self.fake.reject_project = True
        with self.assertRaises(probe.ProbeError):
            self.subject.spawn()
        saved = self.journal.read()
        saved["initialOwnershipConfirmed"] = False
        self.journal.write(saved)
        with self.assertRaisesRegex(probe.ProbeError, "Initial project ownership"):
            self.subject.cleanup()
        self.assertFalse(self.mutations("DELETE", "/api/objects/42"))


    def test_26_nearby_flat_candidate_is_sampled_before_one_spawn(self):
        self.fake.ground_height = lambda x, z: 10.0 if z < 3.5 else 10.0 + x
        result = self.subject.spawn()
        self.assertEqual(len(result["placementAttempts"]), 2)
        self.assertFalse(result["placementAttempts"][0]["accepted"])
        self.assertEqual(result["position"]["z"], 2.5)
        self.assertEqual(len(self.mutations()), 1)
        self.assertTrue(self.subject.cleanup()["collisionRemovedVerified"])

    def test_27_all_sloped_candidates_never_create_or_journal_an_object(self):
        self.fake.ground_height = lambda x, z: 10.0 + x
        with self.assertRaisesRegex(probe.ProbeError, "All nearby candidate"):
            self.subject.spawn()
        self.assertFalse(self.mutations())
        self.assertIsNone(self.journal.read())

    def test_28_existing_object_blocks_only_nearby_candidates_and_is_preserved(self):
        self.fake.objects[7] = object_row(7, prefab="/object/foreign.prefab", project="Player Build", x=0, z=3)
        result = self.subject.spawn()
        self.assertTrue(any(row.get("reason") == "registered object nearby" for row in result["placementAttempts"]))
        dx, dz = result["position"]["x"] + 0.5, result["position"]["z"] + 0.5 - 3
        self.assertGreaterEqual(dx * dx + dz * dz, 4)
        self.assertEqual(len(self.mutations()), 1)
        self.subject.cleanup()
        self.assertIn(7, self.fake.objects)


if __name__ == "__main__":
    unittest.main(verbosity=2)
