"""Isolated fixed-chain tests; never opens a game process or native API."""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import probe_appearance_controller as probe
from check_character_roster import FakeReader

BASE = 0x140000000
LENGTH = 0x173AB000
ADDR = {name: 0x20000 + i * 0x1000 for i, name in enumerate(
    ("root", "manager", "user", "actor", "table", "control", "middle", "controller", "owner", "weak", "members", "mesh", "decoration"))}


def fixture():
    reader = FakeReader()
    for name, address in ADDR.items():
        reader.block(address, 0x300)
    for index, name in enumerate(probe.TYPES):
        address = ADDR[name]
        vt = BASE + (probe.CONTROLLER_VTABLE if name == "controller" else 0x1000 + index * 0x100)
        col = BASE + 0x20000 + index * 0x100
        reader.put(address, vt)
        reader.put(vt - 8, col)
        reader.segments[col] = bytearray(struct.pack("<6I", 1, 0, 0, 0x30000 + index * 0x100,
                                                  0x40000 + index * 0x100, col - BASE))
        reader.names[address] = probe.TYPES[name]
    for rva, raw in probe.CODE_WINDOWS.items():
        reader.segments[BASE + rva] = bytearray(raw)
    tokens = probe.WORLD_PATTERN.split()
    raw = bytearray(int(t, 16) if t != "??" else 0 for t in tokens)
    for rva in probe.WORLD_ANCHORS:
        anchor = bytearray(raw)
        struct.pack_into("<i", anchor, 3, probe.WORLD_GLOBAL - rva - 7)
        reader.segments[BASE + rva] = anchor
    links = ((BASE + probe.WORLD_GLOBAL, "root"), (ADDR["root"] + 0x30, "manager"),
             (ADDR["manager"] + 0x58, "user"), (ADDR["manager"] + 0x50, "actor"),
             (ADDR["user"] + 0xD0, "actor"), (ADDR["user"] + 0xD8, "actor"),
             (ADDR["actor"] + 0xA0, "user"), (ADDR["actor"] + 0x68, "table"),
             (ADDR["table"] + 0x40, "control"), (ADDR["control"] + 8, "actor"),
             (ADDR["control"] + 0xB8, "middle"), (ADDR["middle"] + 0x20, "controller"),
             (ADDR["controller"] + 0x10, "owner"), (ADDR["controller"] + 0x60, "weak"))
    for address, target in links:
        reader.put(address, ADDR[target])
    reader.put(ADDR["weak"] + 8, ADDR["owner"] + 0x28)
    reader.put(ADDR["owner"] + 0x3D, 0, "<B")
    reader.put(ADDR["owner"] + 0x210, ADDR["members"])
    reader.put(ADDR["owner"] + 0x218, 1, "<I")
    reader.put(ADDR["owner"] + 0x21C, 1, "<I")
    reader.put(ADDR["members"], ADDR["controller"])
    for name, off, count in (("mesh", 0xA0, 16), ("decoration", 0xB0, 250)):
        reader.put(ADDR["controller"] + off, ADDR[name])
        reader.put(ADDR["controller"] + off + 8, count, "<I")
        reader.put(ADDR["controller"] + off + 12, count, "<I")
        reader.segments[ADDR[name]][:count] = bytes(range(count))
    return reader


def collect(reader, pause=lambda _: None):
    return probe.collect(reader, BASE, LENGTH, pause)


class AppearanceControllerChecks(unittest.TestCase):
    def test_01_fixed_controlled_chain_and_three_owner_links_are_observations(self):
        reader = fixture()
        result = collect(reader)
        self.assertEqual(result["state"], "observed")
        self.assertTrue(result["stableTwoSamples"] and result["controlledControllerChainObserved"])
        first, second = result["samples"]
        self.assertEqual(first, second)
        self.assertTrue(first["controlledActorRoundTripObserved"] and first["controllerOwnerRoundTripObserved"])
        self.assertEqual(first["ownerComponents"]["controllerOccurrences"], 1)
        self.assertEqual(first["selections"]["mesh"]["count"], 16)
        self.assertEqual(first["selections"]["decoration"]["count"], 250)
        self.assertFalse(first["opaqueHolder"]["typeOrOtherFieldsInterpreted"])
        for field in ("nativeFunctionsInvoked", "gameMemoryWritten", "heapScanned", "appearanceApplicationVerified",
                      "appearanceRestoreVerified", "steveModelLoaded", "snapshotAtomic"):
            self.assertIs(result[field], False)
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))

    def test_02_each_exact_rtti_gate_rejects_before_interpretation(self):
        for name in probe.TYPES:
            with self.subTest(name=name):
                reader = fixture()
                reader.names[ADDR[name]] = ".?AVUnsupported@pa@@"
                result = collect(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertFalse(result["controlledControllerChainObserved"])
                self.assertIn(name + " RTTI", result["reason"])
                if name in ("manager", "user", "actor", "control"):
                    self.assertNotIn((ADDR["middle"], 0x28), reader.reads)

    def test_03_three_world_anchors_and_native_code_windows_are_mandatory(self):
        for address in (BASE + probe.WORLD_ANCHORS[0], BASE + next(iter(probe.CODE_WINDOWS))):
            reader = fixture()
            reader.segments[address][0] ^= 1
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertEqual(result["samples"], [])
        reader = fixture()
        struct.pack_into("<i", reader.segments[BASE + probe.WORLD_ANCHORS[1]], 3, 0)
        self.assertIn("do not agree", collect(reader)["reason"])
        for length in (0, probe.core.MAX_IMAGE_SIZE + 1, probe.WORLD_GLOBAL + 7,
                       probe.CONTROLLER_VTABLE + 7):
            reader = fixture()
            result = probe.collect(reader, BASE, length, lambda _: None)
            self.assertEqual(result["state"], "rejected")
            self.assertEqual(result["samples"], [])
            self.assertEqual(reader.reads, [])

    def test_04_control_identity_and_component_owner_round_trips_fail_closed(self):
        for address in (ADDR["user"] + 0xD0, ADDR["user"] + 0xD8, ADDR["actor"] + 0xA0, ADDR["control"] + 8):
            reader = fixture()
            reader.put(address, 0x70000)
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["controlledControllerChainObserved"])
            self.assertNotIn((ADDR["middle"], 0x28), reader.reads)

    def test_05_opaque_header_is_complete_and_no_other_fields_are_followed(self):
        reader = fixture()
        reader.segments[ADDR["middle"]] = reader.segments[ADDR["middle"]][:0x27]
        result = collect(reader)
        self.assertIn("opaque controller holder complete", result["reason"])
        self.assertNotIn((ADDR["controller"], 0x140), reader.reads)
        reader = fixture()
        reader.put(ADDR["middle"], 0x70000)
        self.assertEqual(collect(reader)["state"], "observed")
        self.assertFalse(any(address == 0x70000 for address, _ in reader.reads))

    def test_06_controller_vtable_and_complete_primary_rtti_are_pinned(self):
        for name, field, replacement in (("controller", "vtable", BASE + 0x1000),
                                          ("owner", "offset", 0x28), ("control", "self", 0)):
            reader = fixture()
            if field == "vtable":
                reader.put(ADDR[name], replacement)
            else:
                vt = reader.value(ADDR[name]); col = reader.value(vt - 8)
                reader.put(col + (4 if field == "offset" else 20), replacement, "<I")
            self.assertEqual(collect(reader)["state"], "rejected")

    def test_07_weak_owner_primary_target_and_invalidation_must_agree(self):
        for address, value, fmt in ((ADDR["weak"] + 8, ADDR["owner"], "<Q"),
                                    (ADDR["owner"] + 0x3D, 1, "<B"),
                                    (ADDR["owner"] + 0x3D, 2, "<B")):
            reader = fixture(); reader.put(address, value, fmt)
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["controlledControllerChainObserved"])

    def test_08_owner_array_bounds_and_exactly_one_controller_are_required(self):
        for count, capacity, entries in ((0, 1, []), (257, 257, []), (2, 1, []), (1, 4097, []),
                                         (1, 1, [0x70000]), (2, 2, [ADDR["controller"], ADDR["controller"]])):
            reader = fixture()
            reader.put(ADDR["owner"] + 0x218, count, "<I")
            reader.put(ADDR["owner"] + 0x21C, capacity, "<I")
            for i, entry in enumerate(entries):
                reader.put(ADDR["members"] + i * 8, entry)
            self.assertEqual(collect(reader)["state"], "rejected")
            self.assertFalse(any(address == 0x70000 for address, _ in reader.reads))

    def test_09_partial_owner_array_is_never_interpreted(self):
        reader = fixture()
        reader.segments[ADDR["members"]] = reader.segments[ADDR["members"]][:7]
        result = collect(reader)
        self.assertIn("complete owner component array", result["reason"])
        self.assertNotIn("controllerOwnerRoundTripObserved", result["samples"][0])

    def test_10_selection_bounds_reject_before_oversized_reads(self):
        for off, count, capacity in ((0xA0, 17, 17), (0xB0, 251, 251), (0xA0, 16, 15), (0xB0, 250, 4097)):
            reader = fixture()
            reader.put(ADDR["controller"] + off + 8, count, "<I")
            reader.put(ADDR["controller"] + off + 12, capacity, "<I")
            result = collect(reader)
            self.assertIn("selection count/capacity", result["reason"])
            self.assertFalse(result["controlledControllerChainObserved"])
            self.assertTrue(all(size <= 4096 for _, size in reader.reads))

    def test_11_empty_selection_buffers_preserve_not_ready_chain_evidence(self):
        reader = fixture()
        reader.put(ADDR["controller"] + 0xA0, 0)
        reader.put(ADDR["controller"] + 0xA8, 0, "<I")
        result = collect(reader)
        self.assertEqual(result["state"], "notReady")
        self.assertTrue(result["stableTwoSamples"] and result["controlledControllerChainObserved"])
        self.assertEqual(result["samples"][0]["selections"]["mesh"]["selectionBytesHex"], "")
        self.assertFalse(result["selectionBuffersPresent"] or result["appearanceApplicationVerified"])

    def test_12_two_samples_differ_and_both_actual_snapshots_are_retained(self):
        reader = fixture()
        def change(_):
            reader.segments[ADDR["mesh"]][0] = 99
        result = collect(reader, change)
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertNotEqual(result["samples"][0]["selections"], result["samples"][1]["selections"])
        self.assertFalse(result["stableTwoSamples"] or result["controlledControllerChainObserved"])

    def test_13_mid_sample_root_changes_stop_interpretation_and_keep_failure(self):
        reader = fixture()
        original = reader.read
        seen = []
        def read(address, size):
            if address == BASE + probe.WORLD_GLOBAL:
                seen.append(1)
                if len(seen) > 1:
                    return struct.pack("<Q", 0x70000)
            return original(address, size)
        reader.read = read
        result = collect(reader)
        self.assertIn("links changed during reads", result["reason"])
        self.assertEqual(len(result["samples"]), 1)
        self.assertFalse(result["controlledControllerChainObserved"])

    def test_14_output_is_exclusive_runtime_json_and_rejects_links(self):
        with tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
            folder = Path(temp)
            target = folder / "result.json"
            result = collect(fixture())
            probe.write_report(target, result)
            self.assertEqual(target.read_bytes().count(b'"state"'), 1)
            before = target.read_bytes()
            with self.assertRaisesRegex(probe.ProbeError, "already exists"):
                probe.write_report(target, result)
            self.assertEqual(target.read_bytes(), before)
            for other in (probe.ROOT / "build/public.json", folder / "result.txt"):
                with self.assertRaisesRegex(RuntimeError, "ignored runtime"):
                    probe.output_path(other)
            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == folder):
                with self.assertRaisesRegex(RuntimeError, "symlinks or junctions"):
                    probe.output_path(folder / "linked.json")

    def test_15_preflight_exe_gate_runs_before_any_chain_reads_and_closes_handle(self):
        reader = fixture()
        reader.reads.clear()
        with tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
            exe = Path(temp) / "CrimsonDesert.exe"
            exe.write_bytes(b"unreviewed test executable")
            reader.module = lambda: (BASE, LENGTH, exe)
            reader.close = mock.Mock()
            output = Path(temp) / "failure.json"
            with mock.patch("sys.argv", ["probe", "--pid", "42123", "--output", str(output)]),\
                    mock.patch.object(probe.core, "Reader", return_value=reader),\
                    mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION):
                with self.assertRaisesRegex(RuntimeError, "SHA256"):
                    probe.main()
            self.assertEqual(reader.reads, [])
            reader.close.assert_called_once()
            self.assertFalse(output.exists())

    def test_16_no_arbitrary_address_cli_is_admitted(self):
        with mock.patch("sys.argv", ["probe", "--address", "0x70000"]),\
                mock.patch.object(probe.core, "Reader") as reader:
            with self.assertRaises(SystemExit):
                probe.main()
            reader.assert_not_called()

    def test_17_second_sample_readiness_failure_keeps_first_and_partial_second(self):
        reader = fixture()
        def unload(_):
            reader.put(ADDR["control"] + 0xB8, 0)
        result = collect(reader, unload)
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertTrue(result["samples"][0]["stableDuringSample"])
        self.assertIn("opaque controller holder", result["reason"])
        self.assertNotIn("controller", result["samples"][1])
        self.assertFalse(result["controlledControllerChainObserved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
