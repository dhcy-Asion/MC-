"""Verify fail-closed diagnostic cases without opening or modifying a game process."""
import struct
import unittest

import probe_characters as probe


class FakeReader:
    def __init__(self, values=None, names=None):
        self.values = values or {}
        self.names = names or {}
        self.reads = []

    def value(self, address, fmt="<Q"):
        self.reads.append(address)
        return self.values.get(address)

    def rtti(self, address, base, length):
        return self.names.get(address)

    def read(self, address, size):
        raise AssertionError("Malformed list must be rejected before bulk memory reads")


class DiagnosticGuards(unittest.TestCase):
    def test_changed_game_build_is_rejected(self):
        profile, _ = probe.load_profile()
        probe.validate_build(profile, profile["game_version"], profile["game_sha256"])
        for version, digest in (("1.0.0.2977", profile["game_sha256"]),
                                (profile["game_version"], "0" * 64)):
            with self.assertRaises(RuntimeError):
                probe.validate_build(profile, version, digest)

    def test_ambiguous_or_missing_anchor_does_not_pick_first(self):
        self.assertIsNone(probe.agreeing_slot([0x10000, 0x10000, 0x10000, 0x20000]))
        self.assertIsNone(probe.agreeing_slot([0x10000] * 3))
        self.assertEqual(probe.agreeing_slot([0x10000] * 4), 0x10000)

    def test_client_manager_never_uses_server_vector_layout(self):
        reader = FakeReader({0x10000: 0x20000, 0x20000: 0x30000},
                            {0x30000: ".?AVClientActorManager@pa@@"})
        result = probe.inspect_manager(reader, 0x10000, 0x140000000, 0x100000)
        self.assertFalse(result["available"])
        self.assertNotIn(0x300b8, reader.reads)

    def test_corrupt_vector_capacity_stops_before_bulk_read(self):
        for count, capacity in ((4, 3), (8193, 8193), (1, 0xffffffff)):
            reader = FakeReader({0x10000: 0x20000, 0x20000: 0x30000,
                                 0x300b8: 0x40000, 0x300c0: count, 0x300c4: capacity},
                                {0x30000: ".?AVServerActorManager@pa@@"})
            self.assertFalse(probe.inspect_manager(reader, 0x10000, 0x140000000, 0x100000)["available"])

    def test_distinct_child_objects_remain_ambiguous(self):
        fields = [{"pointer": "0x10000", "rtti": ".?AVClientUserActor@pa@@"},
                  {"pointer": "0x20000", "rtti": ".?AVClientUserActor@pa@@"}]
        with self.assertRaises(RuntimeError):
            probe.one_typed_pointer(fields, ".?AVClientUserActor@pa@@")

    def test_same_position_does_not_establish_identity(self):
        sig = {"position_bytes": struct.pack("<3f2h", 1, 2, 3, -4, 5).hex()}
        report = {"managers": {"source_server": {"list_stable_during_read": True,
            "candidates": [{"owner": "0x10000", "possessor_round_trip": True,
                "marker_owner_back_link": True, "vital_marker_back_link": True, "position_signature": sig}]}},
            "client_world_chain": {"root_chain_stable": True,
                "client_child_candidates": [{"pointer": "0x20000", "user_back_link": True,
                    "manager_pointer_match": True, "position_signature": sig}]}}
        result = probe.correlate_positions(report)
        self.assertEqual(len(result["matches"]), 1)
        self.assertFalse(result["native_identity_verified"])
        report["client_world_chain"]["root_chain_stable"] = False
        self.assertEqual(probe.correlate_positions(report)["matches"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
