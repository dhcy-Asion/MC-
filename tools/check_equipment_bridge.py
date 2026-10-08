"""Equipment transport checks against owned HTTP fixtures, never production MC/game.

Real Minecraft equip/unequip rules are covered by check_equipment.py. These tests
verify routing, validation, loss of replies and truthful application status only.
"""
from copy import deepcopy
import json
import unittest
from urllib.request import urlopen

import check_inventory_bridge as inventory_fixture
from bridge.red_side import GameAPIError


class EquipmentMC(inventory_fixture.FakeMC):
    def __init__(self):
        super().__init__()
        self.gear = {name: {"slot": name, "empty": True} for name in ("head", "chest", "legs", "feet")}

    def equipment(self):
        return deepcopy({"engine": "Minecraft Java 1.21.1", "revision": self.revision,
                         "nativeApplied": False, "runtimeApplied": False, "slots": self.gear})

    def __call__(self, path="/api/state", body=None):
        if path == "/api/equipment" and body is None:
            self.calls.append((path, None))
            return self.equipment()
        if path in {"/api/equip-selected", "/api/unequip"} and body is not None:
            self.calls.append((path, deepcopy(body)))
            self.revision += 1  # A transport receipt, not a reimplementation of MC equipment rules.
            if self.timeout_after_commit:
                raise TimeoutError("Fake equipment reply lost after commit")
            return self.state()
        return super().__call__(path, body)


class EquipmentBridgeChecks(unittest.TestCase):
    setUp = inventory_fixture.BridgeHTTPChecks.setUp
    tearDown = inventory_fixture.BridgeHTTPChecks.tearDown
    request = inventory_fixture.BridgeHTTPChecks.request

    def install_fixture(self):
        self.mc = EquipmentMC()
        self.patch.stop()
        from unittest.mock import patch
        from bridge import service
        self.patch = patch.object(service, "mc", self.mc)
        self.patch.start()

    def test_equipment_read_preserves_mc_stacks_and_false_application_flags(self):
        self.install_fixture()
        item = {"slot": "head", "empty": False, "id": "minecraft:diamond_helmet",
                "name": "命名头盔\t\n", "count": 1, "maxCount": 1,
                "stack": {"id": "minecraft:diamond_helmet", "count": 1,
                          "components": {"minecraft:damage": 7, "minecraft:custom_name": '"护甲"'}}}
        self.mc.gear["head"] = item
        with urlopen(self.base + "/ui/equipment", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "application/json")
            value = json.load(response)
        self.assertEqual(value, self.mc.equipment())
        self.assertEqual(value["slots"]["head"]["stack"], item["stack"])
        self.assertIs(value["nativeApplied"], False)
        self.assertIs(value["runtimeApplied"], False)
        self.assertEqual(self.mc.calls, [("/api/equipment", None)])
        self.assertEqual(self.red.calls, [])
        self.assertIsNone(self.bridge.origin)

    def test_equipment_routes_forward_one_mc_operation_without_native_calls(self):
        self.install_fixture()
        for route, body in (("/ui/equip-selected", {}), ("/ui/unequip", {"slot": "chest"})):
            with self.subTest(route=route):
                self.mc.calls.clear()
                code, text = self.request(route, body)
                self.assertEqual(code, 200)
                self.assertIn("not connected", text)
                self.assertEqual(len(self.mc.calls), 1)
                path, forwarded = self.mc.calls[0]
                self.assertEqual(path, "/api/" + route.rsplit("/", 1)[1])
                self.assertEqual({k: v for k, v in forwarded.items() if k != "operationId"}, body)
                import uuid
                uuid.UUID(forwarded["operationId"])
                self.assertEqual(self.red.calls, [])

    def test_unequip_all_four_slots_keep_names_exact(self):
        self.install_fixture()
        for name in ("head", "chest", "legs", "feet"):
            self.assertEqual(self.request("/ui/unequip", {"slot": name})[0], 200)
            self.assertEqual(self.mc.calls[-1][1]["slot"], name)
        self.assertEqual(self.red.calls, [])

    def test_invalid_requests_reject_before_mc_mutation(self):
        self.install_fixture()
        for body in ({}, {"slot": "body"}, {"slot": "HEAD"}, {"slot": 0}, {"slot": True},
                     {"slot": "head", "item": "minecraft:diamond_helmet"}, {"slot": None}):
            self.assertEqual(self.request("/ui/unequip", body)[0], 400)
        for body in ({"slot": 0}, {"item": "minecraft:diamond_helmet"}, {"operationId": "reused"}):
            self.assertEqual(self.request("/ui/equip-selected", body)[0], 400)
        self.assertEqual(self.request("/ui/equipment?slot=head")[0], 404)
        self.assertEqual(self.mc.calls, [])
        self.assertEqual(self.red.calls, [])

    def test_lost_equipment_reply_is_not_retried_or_marked_applied(self):
        self.install_fixture()
        self.mc.timeout_after_commit = True
        for route, body in (("/ui/equip-selected", {}), ("/ui/unequip", {"slot": "feet"})):
            with self.subTest(route=route):
                self.mc.calls.clear()
                code, text = self.request(route, body)
                self.assertEqual(code, 400)
                self.assertIn("result unknown", text)
                self.assertIn("reply lost", text)
                self.assertEqual(len(self.mc.calls), 1)
                self.assertEqual(self.red.calls, [])

    def test_mc_rule_rejection_is_forwarded_once_without_local_equipment_rules(self):
        self.install_fixture()
        from unittest.mock import patch
        from bridge import service
        submitted = []

        def rejecting(path="/api/state", body=None):
            submitted.append((path, deepcopy(body)))
            raise GameAPIError("Minecraft rejected armor change: binding enchantment")

        with patch.object(service, "mc", rejecting):
            code, text = self.request("/ui/unequip", {"slot": "head"})
        self.assertEqual(code, 400)
        self.assertIn("binding enchantment", text)
        self.assertEqual(len(submitted), 1)
        self.assertEqual(self.red.calls, [])

    def test_corrupt_equipment_response_is_not_exposed_as_valid(self):
        self.install_fixture()
        from unittest.mock import patch
        from bridge import service
        base = self.mc.equipment()
        bad = []
        for key, value in (("nativeApplied", True), ("runtimeApplied", True), ("revision", True),
                           ("revision", -1), ("engine", "fixture"), ("slots", [])):
            row = deepcopy(base)
            row[key] = value
            bad.append(row)
        row = deepcopy(base)
        del row["slots"]["head"]
        bad.append(row)
        row = deepcopy(base)
        row["slots"]["body"] = {"slot": "body", "empty": True}
        bad.append(row)
        for extra in ({"slot": "head", "empty": True, "id": "minecraft:diamond_helmet"},
                      {"slot": "feet", "empty": True}, {"slot": "head", "empty": 1},
                      {"slot": "head", "empty": False, "id": "red:helmet", "count": 1,
                       "maxCount": 1, "name": "helmet", "stack": {}},
                      {"slot": "head", "empty": False, "id": "minecraft:diamond_helmet", "count": 2,
                       "maxCount": 1, "name": "helmet", "stack": {"id": "minecraft:diamond_helmet"}},
                      {"slot": "head", "empty": False, "id": "minecraft:diamond_helmet", "count": 1,
                       "maxCount": 1, "name": "helmet", "stack": {"id": "minecraft:diamond_boots"}},
                      {"slot": "head", "empty": False, "id": "minecraft:diamond_helmet", "count": 1,
                       "maxCount": 1, "name": "helmet", "stack": {"id": "minecraft:diamond_helmet", "count": True}}):
            row = deepcopy(base)
            row["slots"]["head"] = extra
            bad.append(row)
        for value in bad:
            with self.subTest(value=value), patch.object(service, "mc", lambda *_: deepcopy(value)):
                self.assertEqual(self.request("/ui/equipment")[0], 400)
        self.assertEqual(self.red.calls, [])

    def test_unavailable_equipment_backend_returns_error_without_fake_empty_gear(self):
        self.install_fixture()
        from unittest.mock import patch
        from bridge import service
        with patch.object(service, "mc", side_effect=GameAPIError("Minecraft request failed (HTTP 404)")):
            code, text = self.request("/ui/equipment")
        self.assertEqual(code, 400)
        self.assertIn("HTTP 404", text)
        self.assertEqual(self.red.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
