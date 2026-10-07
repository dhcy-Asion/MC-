"""Fault-inject the production reconciler using temporary journals and mock APIs.

No live HTTP endpoint, game, inventory, anchor, or native asset is accessed.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.native_reconcile import NativeReconciler, PROJECT, BLUE_PREFAB, EXE_SHA256
from bridge.red_side import GameAPIError

ORIGIN = {"x": 10, "y": 20.03, "z": -5}
CONDITION_FIELDS = {"expectedProject": "project", "expectedPrefab": "prefab", "expectedHidden": "hidden",
                    "expectedX": "x", "expectedY": "y", "expectedZ": "z", "expectedYaw": "yaw",
                    "expectedPitch": "pitch", "expectedRoll": "roll", "expectedScale": "scale"}


def block(x=0, axis="y"):
    return {"block": "minecraft:oak_log", "properties": {"axis": axis}, "x": x, "y": 64, "z": 0, "stateId": 130}


def native(uid=1, x=0, **extra):
    return {"uid": uid, "prefab": BLUE_PREFAB, "project": PROJECT, "hidden": False,
            "x": ORIGIN["x"]+x, "y": ORIGIN["y"], "z": ORIGIN["z"],
            "yaw": 0, "pitch": 0, "roll": 0, "scale": 1, **extra}


class FakeRed:
    def __init__(self):
        self.identity = {"pid": 123, "creationTime100ns": "100000", "imagePath": "C:/fixture/CrimsonDesert.exe",
                         "imageSha256": EXE_SHA256, "access": "PROCESS_QUERY_LIMITED_INFORMATION"}
        self.rows, self.calls, self.next_uid = {}, [], 1
        self.expected_sessions = []
        self.before, self.after = lambda *_: None, lambda *args: args[-1]
        self.invisible = set()

    def add(self, row):
        self.rows[row["uid"]] = deepcopy(row)
        self.next_uid = max(self.next_uid, row["uid"]+1)

    def session_identity(self):
        return deepcopy(self.identity)

    def writes(self, suffix=None):
        return [call for call in self.calls if call[1] in {"POST", "DELETE"}
                and (suffix is None or call[0] == suffix)]

    def request(self, path, method="GET", body=None, *, expected_session=None):
        self.calls.append((path, method, deepcopy(body)))
        self.before(path, method, body)
        if method in {"POST", "DELETE"}:
            self.expected_sessions.append(deepcopy(expected_session))
            if expected_session != self.identity:
                raise GameAPIError("native session precondition failed", status=409,
                                   details={"sessionMismatch": True,
                                            "instanceId": f"{self.identity['pid']}:{self.identity['creationTime100ns']}"})
        if path == "/api/status":
            result = 200, {"apiVersion": 1, "gameVersion": "1.0.0.2976", "ready": True, "buildOk": True,
                           "sessionPreconditions": True, "objectPreconditions": True,
                           "instanceId": f"{self.identity['pid']}:{self.identity['creationTime100ns']}"}
        elif path.startswith("/api/objects?"):
            offset = int(parse_qs(urlsplit(path).query)["offset"][0])
            rows = list(self.rows.values())
            result = 200, {"items": deepcopy(rows[offset:offset+500]), "offset": offset, "limit": 500,
                           "total": len(rows), "nextOffset": offset+500 if offset+500 < len(rows) else None}
        elif path == "/api/objects" and method == "POST":
            uid = self.next_uid
            self.add({"uid": uid, **body, "hidden": False, "project": "Current editing project"})
            result = 202, {"uid": uid, "queued": True}
        elif path.startswith("/api/objects/"):
            uid = int(path.split("/")[3])
            row = self.rows.get(uid)
            if row is None or (method == "GET" and uid in self.invisible):
                raise GameAPIError("object not found", status=404)
            if method == "GET":
                result = 200, deepcopy(row)
            else:
                if any(key not in body or body[key] != row[field] for key, field in CONDITION_FIELDS.items()):
                    raise GameAPIError("Object precondition failed", status=409,
                                       details={"objectMismatch": True, "mutationApplied": False, "reason": "object_changed"})
                if path.endswith("/project") and method == "POST":
                    row["project"] = body["name"]
                    result = 200, {"uid": uid, "project": body["name"], "conditional": True}
                elif method == "DELETE":
                    del self.rows[uid]
                    result = 202, {"uid": uid, "queued": True, "conditional": True}
                else:
                    raise AssertionError((path, method))
        else:
            raise AssertionError((path, method))
        return self.after(path, method, body, result)


class ReconcileChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="crimsonmc-native-reconcile-")
        self.path = Path(self.directory.name) / "journal.json"
        self.red = FakeRed()
        self.state = {"revision": 4, "blocks": [block()]}
        self.reopen()

    def tearDown(self):
        self.directory.cleanup()

    def reopen(self):
        self.reconciler = NativeReconciler(self.red, self.path, timeout=0, poll_interval=0)

    def sync(self):
        return self.reconciler.reconcile(deepcopy(self.state), ORIGIN, lambda: deepcopy(self.state))

    def journal(self):
        return json.loads(self.path.read_text())

    def test_complete_replacement_before_delete_and_reuse_without_spawn(self):
        self.red.add(native(1, x=3))
        self.state["blocks"] += [block(1, "x")]
        self.sync()
        writes = self.red.writes()
        self.assertEqual([method for _, method, _ in writes], ["POST", "POST", "POST", "POST", "DELETE"])
        self.assertEqual([r["project"] for r in self.red.rows.values()], [PROJECT, PROJECT])
        self.assertTrue(self.journal()["plan"]["complete"])
        self.assertEqual(self.journal()["plan"]["desired"][1]["properties"], {"axis": "x"})
        before = len(writes)
        self.reopen()
        self.sync()
        self.assertEqual(len(self.red.writes()), before)
        self.assertEqual(len(list((self.path.parent / "journal-history").glob("*.json"))), 1)
        self.assertEqual(self.red.expected_sessions, [self.red.identity]*5)

    def test_partial_spawn_success_keeps_old_and_does_not_retry_unknown(self):
        self.red.add(native(1, x=3))
        self.state["blocks"] += [block(1)]
        def before(path, method, body):
            if path == "/api/objects" and len(self.red.writes(path)) == 2:
                raise TimeoutError("response unavailable")
        self.red.before = before
        with self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        self.assertIn(1, self.red.rows)
        self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "confirmed")
        self.red.before = lambda *_: None
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        self.assertEqual(len(self.red.writes("/api/objects")), 2)
        self.assertFalse(any(method == "DELETE" for _, method, _ in self.red.calls))

    def test_lost_spawn_response_never_guesses_similar_new_object(self):
        def after(path, method, body, result):
            if path == "/api/objects":
                raise TimeoutError("lost after successful submission")
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        self.assertEqual(len(self.red.rows), 1)
        self.red.after = lambda *args: args[-1]
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        with self.assertRaisesRegex(GameAPIError, "unresolved"):
            self.reconciler.ensure_build_allowed()
        self.assertEqual(len(self.red.writes()), 1)

    def test_admitted_registry_timeout_resumes_without_second_spawn(self):
        self.red.invisible.add(1)
        with self.assertRaisesRegex(GameAPIError, "confirmation timed out"):
            self.sync()
        self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "admitted")
        self.red.invisible.clear()
        self.reopen()
        self.sync()
        self.assertEqual(len(self.red.writes("/api/objects")), 1)

    def test_project_assignment_lost_response_recovered_by_readback(self):
        def after(path, method, body, result):
            if path.endswith("/project"):
                raise ValueError("truncated JSON")
            return result
        self.red.after = after
        with self.assertRaises(ValueError):
            self.sync()
        self.red.after = lambda *args: args[-1]
        self.reopen()
        self.sync()
        self.assertEqual(len(self.red.writes()), 2)

    def test_initial_project_is_persisted_before_assignment_and_foreign_change_rejected(self):
        def before(path, method, body):
            if path.endswith("/project"):
                op = self.journal()["plan"]["operations"][0]
                self.assertEqual(op["initialProject"], "Current editing project")
                self.assertEqual(op["phase"], "assigning")
                raise TimeoutError("assignment response lost before commit")
        self.red.before = before
        with self.assertRaises(TimeoutError):
            self.sync()
        self.red.rows[1]["project"] = "Someone else's project"
        self.red.before = lambda *_: None
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "changed project ownership"):
            self.sync()
        self.assertEqual(len(self.red.writes()), 2)

    def test_exact_uid_prefab_transform_hidden_and_admission_guards(self):
        for field, value in (("uid", 99), ("prefab", "/different.prefab"), ("yaw", 1),
                             ("pitch", 1), ("roll", 1), ("scale", 2), ("x", 99),
                             ("y", 99), ("z", 99), ("hidden", True)):
            with self.subTest(field=field):
                self.path.unlink(missing_ok=True)
                self.red = FakeRed()
                def after(path, method, body, result):
                    if path == "/api/objects/1" and method == "GET":
                        result[1][field] = value
                    return result
                self.red.after = after
                self.reopen()
                with self.assertRaises(GameAPIError):
                    self.sync()
                self.assertEqual(len(self.red.writes()), 1)

    def test_malformed_spawn_ack_cannot_authorize_project_or_cleanup(self):
        for ack in ({"uid": 2}, {"uid": True, "queued": True}, {"uid": 1, "queued": True}, {"uid": 2, "queued": False}):
            with self.subTest(ack=ack):
                self.path.unlink(missing_ok=True)
                self.red = FakeRed()
                self.red.add(native(1, x=3))
                self.red.after = lambda path, method, body, result: (202, ack) if path == "/api/objects" else result
                self.reopen()
                with self.assertRaisesRegex(GameAPIError, "unknown"):
                    self.sync()
                self.assertEqual(len(self.red.writes()), 1)
                self.assertIn(1, self.red.rows)

    def test_mc_property_change_stops_stale_cleanup_then_recovers(self):
        self.red.add(native(1, x=3))
        def after(path, method, body, result):
            if path.endswith("/project"):
                self.state["blocks"][0]["properties"]["axis"] = "x"
                self.state["revision"] += 1
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "Minecraft blocks changed"):
            self.sync()
        self.assertIn(1, self.red.rows)
        self.red.after = lambda *args: args[-1]
        self.sync()
        self.assertNotIn(1, self.red.rows)
        self.assertEqual(len(self.red.writes("/api/objects")), 1)
        self.assertEqual(self.journal()["plan"]["desired"][0]["properties"], {"axis": "x"})

    def test_new_mc_target_does_not_trigger_replay_of_unsubmitted_old_target(self):
        self.state["blocks"].append(block(1))
        def after(path, method, body, result):
            if path.endswith("/project"):
                self.state["blocks"] = [block()]
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "Minecraft blocks changed"):
            self.sync()
        self.red.after = lambda *args: args[-1]
        self.sync()
        self.assertEqual(len(self.red.writes("/api/objects")), 1)

    def test_inventory_revision_change_does_not_invalidate_unchanged_build(self):
        def after(path, method, body, result):
            self.state["revision"] += 1
            return result
        self.red.after = after
        self.sync()
        self.assertTrue(self.journal()["plan"]["complete"])

    def test_delete_failure_retry_is_owned_and_after_current_target_confirmation(self):
        self.red.add(native(1, x=3))
        def before(path, method, body):
            if method == "DELETE":
                raise TimeoutError("delete was not sent")
        self.red.before = before
        with self.assertRaises(TimeoutError):
            self.sync()
        self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "submitted")
        self.red.before = lambda *_: None
        self.reopen()
        self.sync()
        self.assertNotIn(1, self.red.rows)
        self.assertEqual(len(self.red.writes("/api/objects")), 1)

    def test_lost_delete_response_confirmed_by_404_without_duplicate_delete(self):
        self.red.add(native(1, x=3))
        def after(path, method, body, result):
            if method == "DELETE":
                raise TimeoutError("lost delete response")
            return result
        self.red.after = after
        with self.assertRaises(TimeoutError):
            self.sync()
        self.red.after = lambda *args: args[-1]
        self.reopen()
        self.sync()
        self.assertEqual(len([call for call in self.red.calls if call[1] == "DELETE"]), 1)

    def test_pending_delete_now_needed_by_mc_is_not_replayed(self):
        self.red.add(native(1, x=3))
        self.red.before = lambda p, m, b: (_ for _ in ()).throw(TimeoutError()) if m == "DELETE" else None
        with self.assertRaises(TimeoutError):
            self.sync()
        self.state["blocks"] += [block(3)]
        self.red.before = lambda *_: None
        self.reopen()
        self.sync()
        self.assertIn(1, self.red.rows)
        self.assertEqual(len([call for call in self.red.calls if call[1] == "DELETE"]), 1)

    def test_new_process_never_uses_old_delete_uid_even_if_reused(self):
        self.red.add(native(1, x=3))
        self.red.before = lambda p, m, b: (_ for _ in ()).throw(TimeoutError()) if m == "DELETE" else None
        with self.assertRaises(TimeoutError):
            self.sync()
        self.red.identity["creationTime100ns"] = "200000"  # Same PID is a new process.
        self.red.rows = {1: native(1, x=3, project="Unrelated current object")}
        self.red.next_uid = 2
        self.red.calls.clear()
        self.red.before = lambda *_: None
        self.reopen()
        self.sync()
        self.assertIn(1, self.red.rows)
        self.assertFalse(any(call[0] == "/api/objects/1" for call in self.red.calls))
        self.assertEqual(self.journal()["plan"]["session"]["creationTime100ns"], "200000")

    def test_new_process_unresolved_spawn_is_not_guessed_from_old_uid(self):
        self.red.invisible.add(1)
        with self.assertRaises(GameAPIError):
            self.sync()
        self.red.identity["creationTime100ns"] = "200000"
        self.red.invisible.clear()
        self.red.calls.clear()
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "restarted with an unresolved spawn"):
            self.sync()
        self.assertFalse(self.red.writes())
        self.assertFalse(any(call[0] == "/api/objects/1" for call in self.red.calls))

    def test_process_change_during_spawn_cannot_authorize_assignment(self):
        def after(path, method, body, result):
            if path == "/api/objects":
                self.red.identity["creationTime100ns"] = "200000"
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "process changed"):
            self.sync()
        self.assertEqual(len(self.red.writes()), 1)
        self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "submitted")

    def test_server_session_precondition_rejects_restart_between_check_and_spawn(self):
        def before(path, method, body):
            if path == "/api/objects":
                self.red.identity["creationTime100ns"] = "200000"
        self.red.before = before
        with self.assertRaisesRegex(GameAPIError, "rejected before enqueue"):
            self.sync()
        self.assertEqual(self.red.rows, {})
        self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "rejected")
        self.red.before = lambda *_: None
        self.reopen()
        self.sync()
        self.assertEqual(len(self.red.rows), 1)

    def test_server_session_precondition_protects_reused_uid_on_delete_and_assign(self):
        for action in ("DELETE", "project"):
            with self.subTest(action=action):
                self.path.unlink(missing_ok=True)
                self.red = FakeRed()
                self.reopen()
                self.red.add(native(1, x=3))
                def before(path, method, body):
                    if method == action or (action == "project" and path.endswith("/project")):
                        self.red.identity["creationTime100ns"] = "200000"
                        uid = int(path.split("/")[3])
                        self.red.rows[uid] = native(uid, project="New process unrelated object")
                self.red.before = before
                with self.assertRaisesRegex(GameAPIError, "precondition failed"):
                    self.sync()
                self.assertTrue(any(row["project"] == "New process unrelated object" for row in self.red.rows.values()))
                if action == "DELETE":
                    self.assertEqual(self.red.rows[1]["project"], "New process unrelated object")
                    self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "rejected")
                else:
                    self.assertEqual(self.red.rows[2]["project"], "New process unrelated object")
                    self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "assigning")

    def test_object_conditions_use_all_last_get_values_including_native_rounding(self):
        self.red.add(native(1, x=3))
        observed = {}
        def after(path, method, body, result):
            if path == "/api/objects" and method == "POST":
                self.red.rows[result[1]["uid"]].update(project="", x=10.004, y=20.030002, z=-4.998,
                                                     yaw=0.0004, pitch=-0.0003, roll=0.0002, scale=1.0001)
            elif path == "/api/objects/1" and method == "GET":
                self.red.rows[1]["x"] = 13.003
                result = 200, deepcopy(self.red.rows[1])
            if method == "GET" and path.startswith("/api/objects/"):
                observed[path] = deepcopy(result[1])
            return result
        def before(path, method, body):
            if method == "DELETE" or path.endswith("/project"):
                query = path.removesuffix("/project")
                expected = {key: observed[query][field] for key, field in CONDITION_FIELDS.items()}
                self.assertEqual({key: body[key] for key in CONDITION_FIELDS}, expected)
                self.assertEqual(len(expected), 10)
        self.red.after, self.red.before = after, before
        self.sync()
        create, deleted = self.journal()["plan"]["operations"]
        self.assertEqual(create["objectPrecondition"]["expectedProject"], "")
        self.assertEqual(create["objectPrecondition"]["expectedX"], 10.004)
        self.assertEqual(deleted["objectPrecondition"]["expectedX"], 13.003)
        self.assertTrue(self.journal()["plan"]["complete"])

    def test_same_process_object_race_preserves_external_change_and_conflict_journal(self):
        for action in ("project", "DELETE"):
            for field, changed in (("project", "ExternallyOwned"), ("x", 13.004), ("yaw", 0.0004),
                                   ("hidden", True), ("prefab", "/external.prefab")):
                with self.subTest(action=action, field=field):
                    self.path.unlink(missing_ok=True)
                    self.red = FakeRed()
                    self.red.add(native(1, x=3))
                    self.reopen()
                    raced = []
                    def before(path, method, body):
                        if method == action or (action == "project" and path.endswith("/project")):
                            uid = int(path.split("/")[3])
                            self.red.rows[uid][field] = changed
                            raced.append(uid)
                    self.red.before = before
                    with self.assertRaisesRegex(GameAPIError, "Object precondition failed"):
                        self.sync()
                    self.assertEqual(len(raced), 1)
                    self.assertEqual(self.red.rows[raced[0]][field], changed)
                    self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "conflict")
                    self.assertEqual(self.journal()["plan"]["operations"][-1]["objectRejection"]["reason"], "object_changed")
                    self.assertFalse(self.journal()["plan"]["complete"])
                    count = len(self.red.writes())
                    self.red.before = lambda *_: None
                    self.reopen()
                    with self.assertRaisesRegex(GameAPIError, "precondition conflict"):
                        self.sync()
                    self.assertEqual(len(self.red.writes()), count)

    def test_busy_object_rejection_recovers_with_fresh_conditions_without_respawn(self):
        for action, reason in (("project", "busy"), ("DELETE", "busy"), ("DELETE", "unsupported")):
            with self.subTest(action=action, reason=reason):
                self.path.unlink(missing_ok=True)
                self.red = FakeRed()
                self.red.add(native(1, x=3))
                self.reopen()
                def before(path, method, body):
                    if method == action or (action == "project" and path.endswith("/project")):
                        raise GameAPIError("Object precondition failed", status=409,
                                           details={"objectMismatch": False, "mutationApplied": False, "reason": reason})
                self.red.before = before
                with self.assertRaises(GameAPIError):
                    self.sync()
                op = self.journal()["plan"]["operations"][-1]
                self.assertEqual(op["phase"], "assigning" if action == "project" else "submitted")
                self.assertEqual(op["objectRejection"]["reason"], reason)
                self.red.before = lambda *_: None
                self.reopen()
                self.sync()
                self.assertTrue(self.journal()["plan"]["complete"])
                self.assertEqual(len(self.red.writes("/api/objects")), 1)
                self.assertNotIn(1, self.red.rows)

    def test_conditional_success_flag_is_required_for_project_and_delete(self):
        for action in ("project", "DELETE"):
            for conditional in (None, False, 1):
                with self.subTest(action=action, conditional=conditional):
                    self.path.unlink(missing_ok=True)
                    self.red = FakeRed()
                    self.red.add(native(1, x=3))
                    self.reopen()
                    def after(path, method, body, result):
                        if method == action or (action == "project" and path.endswith("/project")):
                            if conditional is None:
                                result[1].pop("conditional")
                            else:
                                result[1]["conditional"] = conditional
                        return result
                    self.red.after = after
                    with self.assertRaisesRegex(GameAPIError, "response is unknown"):
                        self.sync()
                    self.assertFalse(self.journal()["plan"]["complete"])
                    self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"],
                                     "assigning" if action == "project" else "submitted")

    def test_missing_object_precondition_capability_prevents_mc_intent_and_native_writes(self):
        def after(path, method, body, result):
            if path == "/api/status":
                result[1].pop("objectPreconditions")
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "Unsupported"):
            self.reconciler.begin_mc(self.state, ORIGIN, "/api/place-selected", {"operationId": "not-submitted"})
        self.assertFalse(self.path.exists())
        with self.assertRaisesRegex(GameAPIError, "Unsupported"):
            self.sync()
        self.assertFalse(self.red.writes())

    def test_ambiguous_session_rejection_does_not_mark_create_safe_to_retry(self):
        for details in ({"sessionMismatch": True}, {"sessionMismatch": 1, "instanceId": "123:200000"},
                        {"sessionMismatch": True, "instanceId": "123:100000"},
                        {"sessionMismatch": True, "instanceId": "invalid"},
                        {"sessionMismatch": True, "instanceId": "0:200000"}):
            with self.subTest(details=details):
                self.path.unlink(missing_ok=True)
                self.red = FakeRed()
                self.reopen()
                def before(path, method, body):
                    if path == "/api/objects":
                        raise GameAPIError("ambiguous failure", status=409, details=details)
                self.red.before = before
                with self.assertRaisesRegex(GameAPIError, "unknown"):
                    self.sync()
                self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "submitted")

    def test_old_asi_without_session_capability_cannot_consume_or_spawn(self):
        def after(path, method, body, result):
            if path == "/api/status":
                del result[1]["sessionPreconditions"]
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "Unsupported"):
            self.reconciler.begin_mc(self.state, ORIGIN, "/api/place-selected", {"operationId": "blocked"})
        self.assertFalse(self.path.exists())
        with self.assertRaisesRegex(GameAPIError, "Unsupported"):
            self.sync()
        self.assertFalse(self.red.writes())

    def test_missing_query_is_distinct_from_network_failure_on_delete_recovery(self):
        self.red.add(native(1, x=3))
        self.red.before = lambda p, m, b: (_ for _ in ()).throw(TimeoutError()) if m == "DELETE" else None
        with self.assertRaises(TimeoutError):
            self.sync()
        self.red.before = lambda p, m, b: (_ for _ in ()).throw(TimeoutError()) if p == "/api/objects/1" else None
        self.reopen()
        with self.assertRaises(TimeoutError):
            self.sync()
        self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "submitted")

    def test_process_change_during_delete_recovery_query_is_not_old_session_confirmation(self):
        self.red.add(native(1, x=3))
        self.red.before = lambda p, m, b: (_ for _ in ()).throw(TimeoutError()) if m == "DELETE" else None
        with self.assertRaises(TimeoutError):
            self.sync()
        def before(path, method, body):
            if path == "/api/objects/1" and method == "GET":
                self.red.identity["creationTime100ns"] = "200000"
                self.red.rows.pop(1)
        self.red.before = before
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "process changed"):
            self.sync()
        self.assertEqual(self.journal()["plan"]["operations"][-1]["phase"], "submitted")

    def test_write_failure_before_submit_prevents_all_native_writes(self):
        original = self.reconciler._write
        def failing(journal, path=None):
            if journal["plan"] and journal["plan"]["operations"]:
                raise OSError("disk full")
            return original(journal, path)
        with patch.object(self.reconciler, "_write", failing), self.assertRaises(OSError):
            self.sync()
        self.assertEqual(self.red.writes(), [])

    def test_write_failure_after_admission_does_not_allow_spawn_retry(self):
        original = self.reconciler._write
        def failing(journal, path=None):
            operations = journal["plan"]["operations"] if journal["plan"] else []
            if operations and operations[-1]["phase"] == "admitted":
                raise OSError("disk full after spawn")
            return original(journal, path)
        with patch.object(self.reconciler, "_write", failing), self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        self.assertEqual(self.journal()["plan"]["operations"][0]["phase"], "submitted")
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "unknown"):
            self.sync()
        self.assertEqual(len(self.red.writes()), 1)

    def test_archive_reentry_after_current_journal_write_failure(self):
        self.sync()
        original_id = self.journal()["plan"]["id"]
        original = self.reconciler._write
        def failing(journal, path=None):
            if path is None and journal["plan"]["id"] != original_id:
                raise OSError("replacement journal publication failed")
            return original(journal, path)
        with patch.object(self.reconciler, "_write", failing), self.assertRaises(OSError):
            self.sync()
        self.assertEqual(self.journal()["plan"]["id"], original_id)
        history = self.path.parent / "journal-history" / (original_id + ".json")
        archived = history.read_bytes()
        # A new explicit MC operation may begin while the old completed plan
        # remains current. Its intent must not conflict with immutable history.
        self.reconciler.begin_mc(self.state, ORIGIN, "/api/place-selected", {"operationId": "later-intent"})
        self.reopen()
        self.sync()
        self.assertEqual(history.read_bytes(), archived)
        self.assertIsNone(self.journal()["mcPending"])
        self.assertEqual(len(self.red.writes("/api/objects")), 1)

    def test_confirmed_new_object_changed_before_cleanup_preserves_old(self):
        self.red.add(native(1, x=3))
        seen = 0
        def after(path, method, body, result):
            nonlocal seen
            if path == "/api/objects/2" and method == "GET":
                seen += 1
                if seen == 3:  # Admission read, assignment read, cohort read.
                    result[1]["project"] = "Changed externally"
            return result
        self.red.after = after
        with self.assertRaisesRegex(GameAPIError, "ownership/prefab/transform changed"):
            self.sync()
        self.assertIn(1, self.red.rows)
        self.assertFalse(any(call[1] == "DELETE" for call in self.red.calls))

    def test_valid_multiple_registry_pages_and_managed_recovery_bound(self):
        for uid in range(1, 503):
            self.red.add(native(uid, project="Foreign"))
        self.sync()
        self.assertTrue(any("offset=500" in call[0] for call in self.red.calls))
        self.assertEqual(len(self.red.rows), 503)
        self.assertEqual(self.journal()["plan"]["operations"][0]["beforeUidMax"], 502)
        for uid in range(504, 761):
            self.red.add(native(uid))
        before = len(self.red.writes())
        with self.assertRaisesRegex(GameAPIError, "recovery limit"):
            self.sync()
        self.assertEqual(len(self.red.writes()), before)

    def test_pending_mc_intent_survives_restart_and_restore_never_replays_mc(self):
        mutation = {"operationId": "fixture-operation", "x": 1, "y": 64, "z": 0}
        self.reconciler.begin_mc(self.state, ORIGIN, "/api/place-selected", mutation)
        self.state["blocks"].append(block(1))  # MC committed, response was lost.
        self.reopen()
        with self.assertRaisesRegex(GameAPIError, "unresolved"):
            self.reconciler.ensure_build_allowed()
        self.sync()
        self.assertIsNone(self.journal()["mcPending"])
        self.reconciler.ensure_build_allowed()
        self.assertEqual(len(self.red.rows), 2)

    def test_foreign_project_and_unrecognized_project_prefab_are_never_deleted(self):
        self.red.add(native(1, x=3, project="Foreign"))
        self.sync()
        self.assertIn(1, self.red.rows)
        self.red.add(native(3, prefab="/other.prefab"))
        count = len(self.red.writes())
        with self.assertRaisesRegex(GameAPIError, "unrecognized"):
            self.sync()
        self.assertEqual(len(self.red.writes()), count)

    def test_malformed_journal_and_duplicate_keys_fail_without_native_writes(self):
        for content in ('{"schemaVersion":1,"schemaVersion":1}', '{"schemaVersion":99}', '{broken'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(GameAPIError):
                    self.sync()
                self.assertEqual(self.path.read_text(), content)
                self.assertFalse(self.red.writes())

    def test_invalid_mc_state_and_duplicate_cell_fail_without_writes(self):
        for blocks in ([block(), block()], [{**block(), "properties": {}}],
                       [{**block(), "properties": {"axis": "wrong"}}], [{**block(), "x": True}]):
            with self.subTest(blocks=blocks):
                self.state["blocks"] = blocks
                with self.assertRaises(GameAPIError):
                    self.sync()
                self.assertFalse(self.red.writes())

    def test_status_identity_and_pagination_validation_prevent_mutations(self):
        def after(path, method, body, result):
            if path == "/api/status":
                result[1]["apiVersion"] = 2
            return result
        self.red.after = after
        with self.assertRaises(GameAPIError):
            self.sync()
        self.red.after = lambda p, m, b, r: (200, {**r[1], "nextOffset": 0}) if p.startswith("/api/objects?") else r
        with self.assertRaises(GameAPIError):
            self.sync()
        self.assertFalse(self.red.writes())
        self.red.identity["imageSha256"] = "0"*64
        with self.assertRaisesRegex(GameAPIError, "identity"):
            self.sync()


if __name__ == "__main__":
    unittest.main(verbosity=2)
