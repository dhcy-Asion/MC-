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


class StoredHealthCandidate(unittest.TestCase):
    @staticmethod
    def entry(current=300000, base=300000, norm=0, floor=0, field30=0, entry_id=0):
        raw = bytearray(0x38)
        struct.pack_into("<i", raw, 0, entry_id)
        for offset, value in zip((8, 0x18, 0x20, 0x28, 0x30), (current, base, norm, floor, field30)):
            struct.pack_into("<q", raw, offset, value)
        return bytes(raw)

    def test_injured_stored_current_need_not_equal_base_plus_norm(self):
        result = probe.decode_health_candidate(self.entry(current=250000))
        self.assertTrue(result["plausible"])
        self.assertEqual(result["current_stored_raw"], 250000)
        self.assertEqual(result["base_raw"], 300000)
        self.assertEqual(result["norm_raw"], 0)

    def test_zero_current_and_zero_threshold_are_reported_without_maximum(self):
        result = probe.decode_health_candidate(self.entry(current=0, floor=30000))
        self.assertTrue(result["plausible"])
        self.assertEqual(result["current_stored_raw"], 0)
        self.assertEqual(result["floor_raw"], 30000)
        self.assertEqual(result["field_30_raw"], 0)
        self.assertNotIn("maximum_candidate_raw", result)
        self.assertNotIn("cap_raw", result)

    def test_field30_is_preserved_without_becoming_a_maximum(self):
        for threshold in (100000, 900000):
            with self.subTest(threshold=threshold):
                result = probe.decode_health_candidate(self.entry(current=250000, field30=threshold))
                self.assertTrue(result["plausible"])
                self.assertEqual(result["field_30_raw"], threshold)
                self.assertFalse(result["maximum_verified"])
                self.assertNotIn("maximum_candidate_raw", result)

    def test_numeric_screen_does_not_claim_a_coherent_or_projected_snapshot(self):
        result = probe.decode_health_candidate(self.entry(current=350000))
        self.assertTrue(result["plausible"])
        self.assertEqual(result["plausibility_scope"], "bounded_raw_fields_only")
        for field in ("health_identity_verified", "projected_current_verified", "maximum_verified",
                      "units_verified", "hud_ready"):
            with self.subTest(field=field):
                self.assertIs(result[field], False)

    def test_out_of_range_raw_fields_are_retained_but_not_plausible(self):
        for name in ("current", "base", "norm", "floor", "field30"):
            for value in (-1, 10**12 + 1, -(2**63), 2**63 - 1):
                with self.subTest(name=name, value=value):
                    result = probe.decode_health_candidate(self.entry(**{name: value}))
                    self.assertFalse(result["plausible"])
                    self.assertFalse(result["hud_ready"])
        self.assertTrue(probe.decode_health_candidate(self.entry(current=10**12))["plausible"])

    def test_wrong_entry_id_is_not_decoded_as_health(self):
        for entry_id in (-1, 1, 22, 0x7fffffff):
            with self.subTest(entry_id=entry_id):
                self.assertIsNone(probe.decode_health_candidate(self.entry(entry_id=entry_id)))

    def test_incomplete_or_oversized_read_never_decodes(self):
        raw = self.entry()
        for bad in (None, b"", raw[:4], raw[:0x30], raw[:-1], raw + b"\0", "0" * 0x38):
            with self.subTest(length=len(bad) if bad is not None else None):
                self.assertIsNone(probe.decode_health_candidate(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
