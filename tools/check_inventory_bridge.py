"""Exercise the bridge HTTP contract against isolated fake MC/red services.

No installed game, Minecraft authority, inventory, anchor, or scene is changed.
Tests cover routing and failure boundaries rather than reproduce MC recipes.
"""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import tempfile
import unittest
import uuid
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import service
from bridge.red_side import GameAPIError
from bridge.native_identity import EXE_SHA256
from bridge.native_reconcile import NativeReconciler

PLACEMENT_ROUTES = ("/ui/place", "/ui/front", "/ui/place-selected", "/ui/front-selected")
CONDITION_FIELDS = {"expectedProject": "project", "expectedPrefab": "prefab", "expectedHidden": "hidden",
                    "expectedX": "x", "expectedY": "y", "expectedZ": "z", "expectedYaw": "yaw",
                    "expectedPitch": "pitch", "expectedRoll": "roll", "expectedScale": "scale"}


class FakeMC:
    def __init__(self):
        self.calls, self.revision, self.selected = [], 4, 0
        self.items = [
            {"id": "minecraft:oak_planks", "name": "橡木木板", "maxCount": 64, "isBlock": True, "placeSupported": True},
            {"id": "minecraft:ender_pearl", "name": "末影\t珍珠\n", "maxCount": 16, "isBlock": False, "placeSupported": False},
            {"id": "minecraft:diamond_sword", "name": "钻石剑", "maxCount": 1, "isBlock": False, "placeSupported": False},
            {"id": "minecraft:torch", "name": "火把", "maxCount": 64, "isBlock": True, "placeSupported": False},
        ]
        self.slots = [{"slot": index, "empty": True} for index in range(36)]
        self.fill(0, self.items[0], 2)
        self.fill(1, self.items[1], 1)
        self.blocks = []
        self.placement_metadata = {"properties": {}}
        self.timeout_after_commit = False

    def fill(self, index, item, count):
        self.slots[index] = {"slot": index, "empty": False, **deepcopy(item), "count": count}

    def state(self):
        inventory = {}
        for slot in self.slots:
            if not slot["empty"]:
                inventory[slot["id"]] = inventory.get(slot["id"], 0) + slot["count"]
        return deepcopy({"engine": "Minecraft Java 1.21.1", "schemaVersion": 2, "revision": self.revision,
                         "slots": self.slots, "selectedSlot": self.selected,
                         "selectedItem": None if self.slots[self.selected]["empty"] else self.slots[self.selected],
                         "inventory": inventory, "blocks": self.blocks})

    def __call__(self, path="/api/state", body=None):
        self.calls.append((path, deepcopy(body)))
        if body is None:
            if path == "/api/catalog": return {"items": deepcopy(self.items)}
            if path == "/api/state": return self.state()
            raise GameAPIError("Unknown fake MC read endpoint")
        if path == "/api/grant":
            item = next((row for row in self.items if row["id"] == body["item"]), None)
            if item is None: raise GameAPIError("Unknown Minecraft item")
            empty = next((row["slot"] for row in self.slots if row["empty"]), None)
            if empty is None: raise GameAPIError("Minecraft inventory is full")
            self.fill(empty, item, item["maxCount"])
        elif path == "/api/add-item":
            if body.get("player") != "console": raise GameAPIError("Unknown player")
            if body["count"] < 1: raise GameAPIError("count must be positive")
            item = next((row for row in self.items if row["id"] == body["item"]), None)
            if item is None: raise GameAPIError("Unknown Minecraft item")
            empty = next((row["slot"] for row in self.slots if row["empty"]), None)
            if empty is None: raise GameAPIError("Minecraft inventory is full")
            self.fill(empty, item, min(body["count"], item["maxCount"]))
            # Fixture only tests forwarding; real split/rollback is checked against MC.
        elif path == "/api/select":
            self.selected = body["slot"]
        elif path in {"/api/consume", "/api/place", "/api/place-selected"}:
            index = self.selected
            if path == "/api/place":
                index = next((row["slot"] for row in self.slots
                              if not row["empty"] and row["id"] == body["block"]), None)
                if index is None: raise GameAPIError("No fixture material")
            slot = self.slots[index]
            if slot["empty"]: raise GameAPIError("Selected slot empty")
            if path == "/api/consume" and slot["isBlock"]:
                raise GameAPIError("Place block items instead of consuming them")
            if path in {"/api/place", "/api/place-selected"}:
                if not slot["placeSupported"]: raise GameAPIError("Unsupported block")
                # Supplied response metadata tests transport, not Minecraft state rules.
                self.blocks.append({"block": slot["id"], **{axis: body[axis] for axis in "xyz"},
                                    **deepcopy(self.placement_metadata)})
            slot["count"] -= 1
            if not slot["count"]: self.slots[index] = {"slot": index, "empty": True}
        else:
            raise GameAPIError("Unexpected fake MC mutation")
        self.revision += 1
        if self.timeout_after_commit:
            raise TimeoutError("Fake response lost after Minecraft commit")
        return self.state()


class FakeRed:
    def __init__(self):
        self.calls, self.objects = [], []
        self.available, self.fail_spawn = False, False

    def session_identity(self):
        if not self.available:
            raise GameAPIError("Game closed")
        return {"pid": 123, "creationTime100ns": "123456", "imagePath": "C:/fixture/CrimsonDesert.exe",
                "imageSha256": EXE_SHA256, "access": "PROCESS_QUERY_LIMITED_INFORMATION"}

    def request(self, path, method="GET", body=None, *, expected_session=None):
        self.calls.append((path, method, deepcopy(body)))
        if method in {"POST", "DELETE"} and expected_session != self.session_identity():
            raise GameAPIError("fixture session precondition failed", status=409)
        if path == "/api/status":
            if not self.available: raise GameAPIError("Game closed")
            return 200, {"apiVersion": 1, "ready": True, "buildOk": True, "gameVersion": "1.0.0.2976",
                         "sessionPreconditions": True, "objectPreconditions": True, "instanceId": "123:123456"}
        if path == "/api/player": return 200, {"x": 0, "y": 0, "z": 0}
        if path == "/api/camera": return 200, {"view": {"x": 1, "z": 0}}
        if path.startswith("/api/objects?"):
            return 200, {"items": deepcopy(self.objects), "nextOffset": None,
                         "offset": 0, "limit": 500, "total": len(self.objects)}
        if path == "/api/objects" and method == "POST":
            if self.fail_spawn: raise GameAPIError("Native object creation failed")
            uid = len(self.objects) + 1
            self.objects.append({"uid": uid, "hidden": False, "project": "Fixture", **body})
            return 202, {"uid": uid, "queued": True}
        if path.endswith("/project"):
            uid = int(path.split("/")[-2])
            row = next(row for row in self.objects if row["uid"] == uid)
            self.check_condition(row, body)
            row["project"] = body["name"]
            return 200, {"uid": uid, "project": body["name"], "conditional": True}
        if path.startswith("/api/objects/"):
            uid = int(path.rsplit("/", 1)[-1])
            row = next((row for row in self.objects if row["uid"] == uid), None)
            if row is None:
                raise GameAPIError("object not found", status=404)
            if method == "GET":
                return 200, deepcopy(row)
            if method == "DELETE":
                self.check_condition(row, body)
                self.objects.remove(row)
                return 202, {"uid": uid, "queued": True, "conditional": True}
        raise GameAPIError("Unexpected fake red request")

    @staticmethod
    def check_condition(row, body):
        if any(key not in body or body[key] != row[field] for key, field in CONDITION_FIELDS.items()):
            raise GameAPIError("Object precondition failed", status=409,
                               details={"objectMismatch": True, "mutationApplied": False, "reason": "object_changed"})

    def ground(self, x, y, z):
        self.calls.append(("ground", "READ", {"x": x, "y": y, "z": z}))
        return {"x": x, "y": 0, "z": z}


class BridgeHTTPChecks(unittest.TestCase):
    def setUp(self):
        self.mc, self.red = FakeMC(), FakeRed()
        self.bridge = service.Bridge.__new__(service.Bridge)
        self.bridge.red, self.bridge.origin = self.red, None
        self.bridge.lock, self.bridge.message = threading.Lock(), "Isolated bridge fixture"
        self.directory = tempfile.TemporaryDirectory(prefix="crimsonmc-bridge-check-")
        self.bridge.reconciler = NativeReconciler(self.red, Path(self.directory.name) / "journal.json", timeout=0)
        self.patch = patch.object(service, "mc", self.mc)
        self.patch.start()
        handler = type("IsolatedHandler", (service.Handler,), {"bridge": self.bridge, "log_message": lambda *_: None})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.patch.stop()
        self.directory.cleanup()

    def request(self, path, body=None, method=None):
        request = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"}, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8")

    def enable_building(self):
        self.red.available = True
        self.bridge.origin = {"x": 0, "y": 0.03, "z": 0}

    def prepare_property_placement(self):
        # Every subtest is an independent fake world/process, including its journal.
        self.bridge.reconciler = NativeReconciler(self.red, Path(self.directory.name) / (str(uuid.uuid4()) + ".json"), timeout=0)
        self.enable_building()
        self.mc.calls.clear()
        self.mc.blocks.clear()
        self.mc.revision, self.mc.selected = 4, 0
        self.mc.timeout_after_commit = False
        self.mc.fill(0, {"id": "minecraft:oak_log", "name": "橡木原木", "maxCount": 64,
                         "isBlock": True, "placeSupported": True}, 64)
        self.mc.placement_metadata = {"properties": {"axis": "x"}, "stateId": 130}
        self.red.calls.clear()
        self.red.objects.clear()
        self.red.fail_spawn = False

    @staticmethod
    def property_placement_body(path, **extra):
        body = {"x": 1, "y": 2, "z": -1, **extra}
        if path in {"/ui/place", "/ui/front"}:
            body["block"] = "minecraft:oak_log"
        return body

    def test_add_item_needs_neither_red_nor_anchor(self):
        # Console-style direct add: item, explicit count and a target player.
        code, text = self.request("/ui/add-item", {"item": "minecraft:diamond_sword", "count": 3, "player": "console"})
        self.assertEqual(code, 200)
        self.assertIn("diamond_sword", text)
        self.assertEqual(self.mc.slots[2]["id"], "minecraft:diamond_sword")
        forwarded = next(body for path, body in self.mc.calls if path == "/api/add-item")
        self.assertEqual(forwarded["count"], 3)
        self.assertEqual(forwarded["player"], "console")
        self.assertEqual(self.red.calls, [])
        self.assertIsNone(self.bridge.origin)

    def test_add_item_validates_count_and_player(self):
        for body in ({"item": "minecraft:diamond_sword"},
                     {"item": "minecraft:diamond_sword", "count": 0, "player": "console"},
                     {"item": "minecraft:diamond_sword", "count": 1.5, "player": "console"},
                     {"item": "minecraft:diamond_sword", "count": 1, "player": "someone_else"},
                     {"item": 1, "count": 1, "player": "console"}):
            self.assertEqual(self.request("/ui/add-item", body)[0], 400)
        # Rejected bodies must never reach Minecraft with a mutation.
        self.assertFalse(any(body is not None for _, body in self.mc.calls))

    def test_crafting_route_is_gone(self):
        self.assertEqual(self.request("/ui/craft", {"recipe": "minecraft:oak_planks"})[0], 404)
        self.assertFalse(any(body is not None for _, body in self.mc.calls))

    def test_inventory_mutations_need_neither_red_nor_anchor(self):
        code, text = self.request("/ui/grant", {"item": "minecraft:diamond_sword"})
        self.assertEqual(code, 200)
        self.assertIn("钻石剑 (minecraft:diamond_sword): 1", text)
        self.assertIn("inventory actions require Minecraft only", text)
        self.assertEqual(self.request("/ui/select", {"slot": 2})[0], 200)
        self.assertEqual(self.request("/ui/consume", {})[0], 200)
        self.assertTrue(self.mc.slots[2]["empty"])
        self.assertEqual(self.red.calls, [])
        self.assertIsNone(self.bridge.origin)

    def test_catalog_pagination_search_and_tsv_sanitization(self):
        code, text = self.request("/ui/catalog?offset=0&limit=2")
        self.assertEqual(code, 200)
        rows = [line.split("\t") for line in text.splitlines()]
        self.assertEqual(rows[0], ["catalog", "4", "0", "2"])
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(row) == 6 for row in rows[1:]))
        self.assertEqual(rows[2][2], "末影 珍珠 ")
        code, text = self.request("/ui/catalog?search=SWORD&offset=0&limit=50")
        self.assertEqual(code, 200)
        self.assertEqual(text.splitlines()[0], "catalog\t1\t0\t-1")
        self.assertIn("minecraft:diamond_sword", text)
        # Search also matches the Chinese name MC now reports.
        code, text = self.request("/ui/catalog?search=%E9%92%BB%E7%9F%B3&offset=0&limit=50")
        self.assertEqual(code, 200)
        self.assertIn("minecraft:diamond_sword", text)
        self.assertEqual(self.request("/ui/catalog?search=missing")[1], "catalog\t0\t0\t-1")
        self.assertEqual(self.red.calls, [])

    def test_inventory_tsv_has_all_slots_and_fixed_columns(self):
        code, text = self.request("/ui/inventory")
        self.assertEqual(code, 200)
        rows = [line.split("\t") for line in text.splitlines()]
        self.assertEqual(rows[0], ["inventory", "4", "0"])
        self.assertEqual(len(rows), 37)
        self.assertEqual({int(row[1]) for row in rows[1:]}, set(range(36)))
        self.assertTrue(all(len(row) == 6 for row in rows[1:]))
        self.assertEqual(rows[-1], ["slot", "35", "-", "0", "0", ""])
        self.assertEqual(self.red.calls, [])

    def test_summary_reports_mc_inventory_while_game_is_closed(self):
        code, text = self.request("/ui/state")
        self.assertEqual(code, 200)
        self.assertIn("橡木木板 (minecraft:oak_planks): 2", text)
        self.assertIn("Red-side building unavailable", text)
        self.assertNotIn("Minecraft backend not ready", text)

    def test_invalid_slot_values_and_unknown_routes_do_not_mutate(self):
        for value in (True, False, -1, 36, "0", 0.0, None):
            self.assertEqual(self.request("/ui/select", {"slot": value})[0], 400)
        for body in ([], "slot", 1):
            self.assertEqual(self.request("/ui/select", body)[0], 400)
        self.assertEqual(self.request("/ui/not-an-action", {})[0], 404)
        self.assertEqual(self.request("/ui/grant", {"item": 1})[0], 400)
        self.assertEqual(self.mc.calls, [])
        self.assertEqual(self.red.calls, [])

    def test_catalog_bad_pagination_rejected_without_red(self):
        for query in ("offset=-1", "offset=1.0", "limit=0", "limit=101", "offset=0&offset=1", "unknown=yes"):
            self.assertEqual(self.request("/ui/catalog?" + query)[0], 400)
        self.assertEqual(self.request("/ui/catalog?offset=5")[0], 400)
        self.assertEqual(self.red.calls, [])

    def test_unknown_mc_item_is_rejected_without_native_side_effects(self):
        before = self.mc.state()
        code, text = self.request("/ui/grant", {"item": "minecraft:does_not_exist"})
        self.assertEqual(code, 400)
        self.assertIn("Unknown Minecraft item", text)
        self.assertEqual(self.mc.state(), before)
        self.assertEqual(self.red.calls, [])

    def test_corrupt_inventory_shape_and_counts_are_not_exposed_as_valid_tsv(self):
        self.mc.slots.pop()
        self.assertEqual(self.request("/ui/inventory")[0], 400)
        self.mc.slots.append({"slot": 35, "empty": True})
        self.mc.slots[0]["count"] = 65
        self.assertEqual(self.request("/ui/inventory")[0], 400)
        self.assertEqual(self.red.calls, [])

    def test_bad_selected_placement_coordinates_do_not_mutate_mc(self):
        self.enable_building()
        for coordinates in ({"x": True}, {"y": 32}, {"z": "0"}, {"x": 0.2}):
            self.assertEqual(self.request("/ui/place-selected", coordinates)[0], 400)
        self.assertFalse(any(body is not None for _, body in self.mc.calls))

    def test_unsupported_selected_block_does_not_consume(self):
        self.enable_building()
        self.mc.fill(0, self.mc.items[3], 64)
        before = self.mc.state()
        code, text = self.request("/ui/place-selected", {"x": 0, "y": 0, "z": 0})
        self.assertEqual(code, 400)
        self.assertIn("no native block placement support", text)
        self.assertEqual(self.mc.state(), before)
        self.assertFalse(any(body is not None for _, body in self.mc.calls))

    def test_selected_placement_uses_mc_coordinates_and_single_mutation(self):
        self.enable_building()
        code, _ = self.request("/ui/place-selected", {"x": 1, "y": 2, "z": -1})
        self.assertEqual(code, 200)
        writes = [(path, body) for path, body in self.mc.calls if body is not None]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "/api/place-selected")
        self.assertEqual({key: writes[0][1][key] for key in "xyz"}, {"x": 1, "y": 66, "z": -1})
        self.assertEqual(self.mc.slots[0]["count"], 1)
        self.assertEqual(len(self.red.objects), 1)

    def test_native_failure_after_mc_commit_never_retries_placement(self):
        self.enable_building()
        self.red.fail_spawn = True
        code, text = self.request("/ui/place-selected", {"x": 0, "y": 0, "z": 0})
        self.assertEqual(code, 400)
        self.assertIn("Minecraft committed revision", text)
        self.assertIn("Restore blocks", text)
        self.assertIn("do not repeat", text)
        self.assertEqual(self.mc.slots[0]["count"], 1)
        self.assertEqual(len([path for path, body in self.mc.calls if body is not None]), 1)

    def test_unresolved_native_spawn_blocks_next_click_but_inventory_remains_independent(self):
        self.enable_building()
        self.red.fail_spawn = True
        self.assertEqual(self.request("/ui/place-selected", {"x": 0})[0], 400)
        before = self.mc.slots[0]["count"]
        self.red.fail_spawn = False
        self.assertEqual(self.request("/ui/place-selected", {"x": 1})[0], 400)
        self.assertEqual(self.mc.slots[0]["count"], before)
        self.assertEqual(len([p for p, b in self.mc.calls if b is not None]), 1)
        self.red.calls.clear()
        self.assertEqual(self.request("/ui/grant", {"item": "minecraft:diamond_sword"})[0], 200)
        self.assertEqual(self.red.calls, [])
        self.assertEqual(self.request("/ui/reconnect", {})[0], 400)
        self.assertFalse(any(method == "POST" for _, method, _ in self.red.calls))

    def test_lost_mc_response_requires_read_only_restore_before_next_build(self):
        self.enable_building()
        self.mc.timeout_after_commit = True
        self.assertEqual(self.request("/ui/place-selected", {"x": 0})[0], 400)
        self.mc.timeout_after_commit = False
        # Reconstruct the persistent component as after a bridge restart.
        self.bridge.reconciler = NativeReconciler(self.red, self.bridge.reconciler.path, timeout=0)
        self.assertEqual(self.request("/ui/place-selected", {"x": 1})[0], 400)
        self.assertEqual(self.mc.slots[0]["count"], 1)
        self.assertEqual(self.request("/ui/reconnect", {})[0], 200)
        self.assertEqual(len([p for p, b in self.mc.calls if b is not None]), 1)
        self.assertEqual(len(self.red.objects), 1)
        self.assertIsNone(self.bridge.reconciler._load()["mcPending"])
        self.assertEqual(self.request("/ui/place-selected", {"x": 1})[0], 200)
        self.assertEqual(len(self.red.objects), 2)

    def test_all_placement_routes_forward_properties_and_preserve_mc_state(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                body = self.property_placement_body(route, properties={"axis": "x"})
                with patch.object(self.bridge, "sync", wraps=self.bridge.sync) as sync:
                    code, text = self.request(route, body)
                self.assertEqual(code, 200, text)
                writes = [(path, body) for path, body in self.mc.calls if body is not None]
                self.assertEqual(len(writes), 1)
                expected = "/api/place-selected" if route.endswith("-selected") else "/api/place"
                self.assertEqual(writes[0][0], expected)
                forwarded = writes[0][1]
                self.assertEqual(forwarded["properties"], {"axis": "x"})
                self.assertIsInstance(forwarded["operationId"], str)
                self.assertTrue(forwarded["operationId"])
                self.assertEqual("block" in forwarded, expected == "/api/place")
                if "block" in forwarded:
                    self.assertEqual(forwarded["block"], "minecraft:oak_log")
                expected_cell = {"x": 3, "y": 64, "z": 0} if "/front" in route else {"x": 1, "y": 66, "z": -1}
                self.assertEqual({key: forwarded[key] for key in "xyz"}, expected_cell)
                sync.assert_called_once()
                self.assertEqual(sync.call_args.args[0], self.mc.state())
                self.assertEqual(sync.call_args.args[0]["blocks"][0],
                                 {"block": "minecraft:oak_log", **expected_cell,
                                  "properties": {"axis": "x"}, "stateId": 130})
                self.assertEqual(self.mc.slots[0]["count"], 63)
                self.assertEqual(self.mc.revision, 5)
                self.assertEqual(len(self.red.objects), 1)

    def test_empty_placement_properties_are_forwarded(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                self.mc.placement_metadata = {"properties": {"axis": "y"}, "stateId": 131}
                code, text = self.request(route, self.property_placement_body(route, properties={}))
                self.assertEqual(code, 200, text)
                writes = [body for _, body in self.mc.calls if body is not None]
                self.assertEqual(len(writes), 1)
                self.assertIn("properties", writes[0])
                self.assertEqual(writes[0]["properties"], {})
                self.assertEqual(self.mc.blocks[0]["properties"], {"axis": "y"})

    def test_omitted_placement_properties_are_not_invented(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                self.mc.placement_metadata = {"properties": {"axis": "y"}, "stateId": 131}
                code, text = self.request(route, self.property_placement_body(route))
                self.assertEqual(code, 200, text)
                writes = [body for _, body in self.mc.calls if body is not None]
                self.assertEqual(len(writes), 1)
                self.assertNotIn("properties", writes[0])
                self.assertEqual(self.mc.blocks[0]["properties"], {"axis": "y"})

    def test_malformed_properties_never_mutate_mc_or_native(self):
        invalid = (None, [], "axis=x", True, 1, 1.5,
                   {"axis": None}, {"axis": True}, {"axis": 1}, {"axis": []}, {"axis": {}},
                   {"": "x"}, {"x" * 65: "x"}, {"axis": ""}, {"axis": "x" * 129},
                   {f"key{index}": "x" for index in range(33)})
        for route in PLACEMENT_ROUTES:
            for properties in invalid:
                with self.subTest(route=route, properties=properties):
                    self.prepare_property_placement()
                    before = self.mc.state()
                    code, text = self.request(route, self.property_placement_body(route, properties=properties))
                    self.assertEqual(code, 400, text)
                    self.assertIn("properties must be an object", text)
                    self.assertFalse(any(body is not None for _, body in self.mc.calls))
                    self.assertEqual(self.mc.state(), before)
                    self.assertFalse(any(method in {"POST", "DELETE", "PUT", "PATCH"}
                                         for _, method, _ in self.red.calls))
                    self.assertEqual(self.red.objects, [])

    def test_native_failure_preserves_property_commit_and_does_not_retry(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                self.red.fail_spawn = True
                code, text = self.request(route, self.property_placement_body(route, properties={"axis": "x"}))
                self.assertEqual(code, 400)
                self.assertIn("Minecraft committed revision 5", text)
                self.assertIn("Restore blocks", text)
                self.assertIn("do not repeat", text)
                writes = [body for _, body in self.mc.calls if body is not None]
                self.assertEqual(len(writes), 1)
                self.assertEqual(writes[0]["properties"], {"axis": "x"})
                self.assertEqual(self.mc.blocks[0]["properties"], {"axis": "x"})
                self.assertEqual(self.mc.blocks[0]["stateId"], 130)
                self.assertEqual(self.mc.slots[0]["count"], 63)
                self.assertEqual(self.mc.revision, 5)
                self.assertEqual(self.red.objects, [])

    def test_lost_property_placement_response_is_not_retried(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                self.mc.timeout_after_commit = True
                code, text = self.request(route, self.property_placement_body(route, properties={"axis": "x"}))
                self.assertEqual(code, 400)
                self.assertIn("result unknown", text)
                self.assertEqual(len([body for _, body in self.mc.calls if body is not None]), 1)
                self.assertEqual(self.mc.blocks[0]["properties"], {"axis": "x"})
                self.assertEqual(self.mc.slots[0]["count"], 63)
                self.assertEqual(self.mc.revision, 5)
                self.assertFalse(any(method == "POST" for _, method, _ in self.red.calls))

    def test_mc_property_rejection_has_no_native_writes_or_substitution(self):
        for route in PLACEMENT_ROUTES:
            with self.subTest(route=route):
                self.prepare_property_placement()
                before = self.mc.state()
                submitted = []

                def rejecting_mc(path="/api/state", body=None):
                    if body is not None:
                        submitted.append((path, deepcopy(body)))
                        raise GameAPIError("Minecraft rejected invalid block property axis")
                    return self.mc(path, body)

                with patch.object(service, "mc", rejecting_mc):
                    code, text = self.request(route, self.property_placement_body(route, properties={"axis": "invalid"}))
                self.assertEqual(code, 400)
                self.assertIn("Minecraft rejected invalid block property axis", text)
                self.assertEqual(len(submitted), 1)
                self.assertEqual(submitted[0][1]["properties"], {"axis": "invalid"})
                self.assertEqual(self.mc.state(), before)
                self.assertFalse(any(method == "POST" for _, method, _ in self.red.calls))

    def test_lost_mc_response_is_not_retried(self):
        self.mc.timeout_after_commit = True
        code, text = self.request("/ui/grant", {"item": "minecraft:diamond_sword"})
        self.assertEqual(code, 400)
        self.assertIn("response lost", text)
        self.assertIn("result unknown", text)
        self.assertEqual(len(self.mc.calls), 1)
        self.assertEqual(self.mc.slots[2]["count"], 1)
        self.assertEqual(self.red.calls, [])

    def test_front_selected_and_last_item_disappears(self):
        self.enable_building()
        self.mc.slots[0]["count"] = 1
        code, _ = self.request("/ui/front-selected", {})
        self.assertEqual(code, 200)
        self.assertTrue(self.mc.slots[0]["empty"])
        self.assertEqual(self.mc.selected, 0)
        self.assertEqual(self.mc.blocks[0]["x"], 3)
        self.assertEqual(self.mc.blocks[0]["y"], 64)

    def test_selected_placement_still_requires_game_and_anchor(self):
        self.assertEqual(self.request("/ui/place-selected", {})[0], 400)
        self.red.available = True
        self.assertEqual(self.request("/ui/place-selected", {})[0], 400)
        self.assertFalse(any(body is not None for _, body in self.mc.calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
