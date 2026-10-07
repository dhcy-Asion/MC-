"""Isolated fixed-chain tests; never opens a game process or native API."""
from __future__ import annotations

from pathlib import Path
import json
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
OPTIONS = {"meshParams": 0x100000, "preset": 0x101000, "decorationParams": 0x102000,
           "meshRows": 0x110000, "decorationRows": 0x120000, "options": 0x140000,
           "presetMesh": 0x150000, "presetDecoration": 0x151000}


def option_fixture(reader):
    """Synthetic resource inputs; no game resources or process are accessed."""
    def text(holder, chars, name):
        reader.block(holder, 0x20)
        reader.put(holder, chars)
        reader.block(chars, 512)
        reader.segments[chars][:len(name)] = name.encode("utf-8")
    for index, (name, (offset, size, vtable, rtti)) in enumerate(probe.RESOURCE_TYPES.items()):
        address = OPTIONS[name]
        reader.block(address, size)
        reader.put(ADDR["controller"] + offset, address)
        vt, col = BASE + vtable, BASE + 0x50000 + index * 0x100
        reader.put(address, vt)
        reader.put(vt - 8, col)
        reader.segments[col] = bytearray(struct.pack("<6I", 1, 0, 0, 0x51000 + index * 0x100,
                                                  0x52000 + index * 0x100, col - BASE))
        reader.names[address] = rtti
        holder, chars = 0x160000 + index * 0x1000, 0x160100 + index * 0x1000
        text(holder, chars, "synthetic/" + name)
        reader.put(address + 0x20, holder)
    reader.block(OPTIONS["presetMesh"], 16)
    reader.segments[OPTIONS["presetMesh"]][:] = b"\xff\x01" + b"\xff" * 14
    reader.block(OPTIONS["presetDecoration"], 250)
    reader.segments[OPTIONS["presetDecoration"]][:] = b"\xff" * 250
    for offset, array, count in ((0x38, OPTIONS["presetMesh"], 16), (0x28, OPTIONS["presetDecoration"], 250)):
        reader.put(OPTIONS["preset"] + offset, array)
        reader.put(OPTIONS["preset"] + offset + 8, count, "<I")
        reader.put(OPTIONS["preset"] + offset + 12, count, "<I")
    reader.segments[ADDR["mesh"]][:16] = b"\x00" + b"\xff" * 15
    for name, offset, array, count, stride in (("meshParams", 0x28, OPTIONS["meshRows"], 2, 0x58),
                                             ("decorationParams", 0x48, OPTIONS["decorationRows"], 3, 0x98)):
        reader.block(array, 250 * stride if name == "decorationParams" else count * stride)
        reader.put(OPTIONS[name] + offset, array)
        reader.put(OPTIONS[name] + offset + 8, count, "<I")
        reader.put(OPTIONS[name] + offset + 12, count, "<I")
    for group in range(2):
        row, array = OPTIONS["meshRows"] + group * 0x58, OPTIONS["options"] + group * 0x1000
        reader.block(array, 2 * 0x120)
        reader.put(row, array)
        reader.put(row + 8, 2, "<I"); reader.put(row + 12, 2, "<I")
        reader.put(row + 0x10, 0, "<B")
        for choice in range(2):
            refs = 0x180000 + (group * 2 + choice) * 0x1000
            holder, chars = refs + 0x100, refs + 0x200
            reader.block(refs, 8)
            reader.put(refs, holder)
            text(holder, chars, f"synthetic/group{group}/choice{choice}.prefab")
            option = array + choice * 0x120
            reader.put(option, refs)
            reader.put(option + 8, 1, "<I"); reader.put(option + 12, 1, "<I")
    for index in range(250):
        row = OPTIONS["decorationRows"] + index * 0x98
        reader.put(row + 0x3C, -1, "<i")
        for off, value in ((0x7E, 7), (0x7F, 4), (0x80, 10), (0x81, 20), (0x82, 12), (0x83, 0xFF)):
            reader.put(row + off, value, "<B")


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
    option_fixture(reader)
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
            self.assertEqual(json.loads(target.read_bytes())["state"], "observed")
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

    def test_18_loaded_resources_require_exact_primary_types_and_vtables(self):
        for name in probe.RESOURCE_TYPES:
            for bad_type in (True, False):
                reader = fixture()
                if bad_type:
                    reader.names[OPTIONS[name]] = ".?AVUnsupported@pa@@"
                else:
                    original_vt = reader.value(OPTIONS[name])
                    vt = BASE + 0x9000
                    reader.put(vt - 8, reader.value(original_vt - 8))
                    reader.put(OPTIONS[name], vt)
                result = collect(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertIn(name, result["reason"])
                self.assertNotIn((OPTIONS["meshRows"], 16), reader.reads)

    def test_19_mesh_ff_uses_non_ff_preset_then_real_group_default(self):
        reader = fixture()
        result = collect(reader)
        groups = result["samples"][0]["loadedOptions"]["meshGroups"]
        self.assertEqual(groups[0]["fallbackSource"], "selection")
        self.assertEqual(groups[1]["fallbackSource"], "preset")
        self.assertEqual(groups[1]["prefabNames"], ["synthetic/group1/choice1.prefab"])
        self.assertTrue(result["meshGroupChoiceBoundsVerified"])
        coverage = result["samples"][0]["loadedOptions"]["meshSelectionCoverage"]
        self.assertEqual(coverage["unmappedSelectionCount"], 14)
        self.assertFalse(coverage["selectionGroupCountsMatch"])
        self.assertFalse(result["samples"][0]["selections"]["mesh"]["loadedOptionBoundsVerified"])
        reader = fixture()
        reader.put(ADDR["controller"] + 0xA8, 2, "<I")
        self.assertTrue(collect(reader)["samples"][0]["selections"]["mesh"]["loadedOptionBoundsVerified"])
        for null_preset in (False, True):
            reader = fixture()
            if null_preset:
                reader.put(ADDR["controller"] + 0x110, 0)
            else:
                reader.put(OPTIONS["presetMesh"] + 1, 0xFF, "<B")
            result = collect(reader)
            group = result["samples"][0]["loadedOptions"]["meshGroups"][1]
            self.assertEqual(result["state"], "observed")
            self.assertEqual(group["fallbackSource"], "groupDefault")
            self.assertEqual(group["prefabNames"], ["synthetic/group1/choice0.prefab"])

    def test_20_resource_vectors_stop_at_fixed_count_and_capacity_bounds(self):
        for name, offset, count, capacity in (("meshParams", 0x28, 17, 17),
                    ("decorationParams", 0x48, 251, 251), ("preset", 0x38, 17, 17),
                    ("preset", 0x28, 251, 251), ("meshParams", 0x28, 2, 1),
                    ("decorationParams", 0x48, 3, 4097)):
            reader = fixture()
            reader.put(OPTIONS[name] + offset + 8, count, "<I")
            reader.put(OPTIONS[name] + offset + 12, capacity, "<I")
            result = collect(reader)
            self.assertIn("count/capacity", result["reason"])
            self.assertTrue(all(size <= 4096 for _, size in reader.reads))
        for offset, replacement in ((8, 257), (12, 1)):
            reader = fixture()
            reader.put(OPTIONS["meshRows"] + offset, replacement, "<I")
            self.assertIn("count/capacity", collect(reader)["reason"])
            self.assertFalse(any(address == OPTIONS["options"] for address, _ in reader.reads))

    def test_21_mesh_actual_group_bounds_stop_direct_invalid_choices(self):
        reader = fixture()
        reader.put(ADDR["mesh"], 2, "<B")
        result = collect(reader)
        self.assertIn("real group's option count", result["reason"])
        self.assertFalse(any(address == OPTIONS["options"] + 2 * 0x120 for address, _ in reader.reads))
        group = result["samples"][0]["loadedOptions"]["meshGroups"][0]
        self.assertTrue(group["nativeWouldSkipOutOfBoundsCandidate"])
        reader = fixture()
        reader.put(OPTIONS["presetMesh"] + 1, 8, "<B")
        result = collect(reader)
        self.assertEqual(result["state"], "observed")
        self.assertFalse(result["meshGroupChoiceBoundsVerified"])
        self.assertEqual(result["samples"][0]["loadedOptions"]["meshGroups"][1]["prefabNames"], [])

    def test_22_only_bounded_current_option_prefab_references_are_read(self):
        reader = fixture()
        reader.put(OPTIONS["options"] + 8, 33, "<I")
        reader.put(OPTIONS["options"] + 12, 33, "<I")
        self.assertIn("prefab references count/capacity", collect(reader)["reason"])
        reader = fixture()
        reader.segments[0x180000] = reader.segments[0x180000][:7]
        self.assertIn("prefab references complete", collect(reader)["reason"])
        reader = fixture()
        reader.put(0x180000, 0x70000)
        self.assertIn("chars pointer complete readable span", collect(reader)["reason"])
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))

    def test_23_names_are_bounded_untrusted_strings_and_never_files(self):
        for raw in (b"A" * 512, b"\xff\0", b"a\nb\0"):
            reader = fixture()
            reader.segments[0x180200][:len(raw)] = raw
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["appearanceApplicationVerified"])
        reader = fixture()
        reader.segments[0x180200] = reader.segments[0x180200][:3]
        self.assertIn("complete readable span", collect(reader)["reason"])

    def test_24_interpreted_resource_fields_are_reread_and_preserve_failure(self):
        reader = fixture()
        original = reader.read
        times = []
        def changing(address, size):
            if address == OPTIONS["meshRows"] and size == 16:
                times.append(1)
                if len(times) > 1:
                    changed = bytearray(original(address, size))
                    changed[8] = 1
                    return bytes(changed)
            return original(address, size)
        reader.read = changing
        result = collect(reader)
        self.assertIn("resource fields changed", result["reason"])
        self.assertFalse(result["controlledControllerChainObserved"])
        self.assertEqual(len(result["samples"][0]["loadedOptions"]["meshGroups"]), 2)
        reader = fixture()
        def unloading(_):
            reader.put(OPTIONS["meshParams"] + 0x15, 1, "<B")
        result = collect(reader, unloading)
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertTrue(result["samples"][0]["stableDuringSample"])

    def test_25_loaded_resource_invalidation_stops_unknown_state(self):
        for name in probe.RESOURCE_TYPES:
            for flag in (1, 2):
                reader = fixture()
                reader.put(OPTIONS[name] + 0x15, flag, "<B")
                result = collect(reader)
                self.assertIn("unknown resource flag", result["reason"])
                self.assertFalse(result["controlledControllerChainObserved"])

    def test_26_missing_loaded_parameter_resources_preserve_not_ready_chain(self):
        for name in ("meshParams", "decorationParams"):
            reader = fixture()
            reader.put(ADDR["controller"] + probe.RESOURCE_TYPES[name][0], 0)
            result = collect(reader)
            self.assertEqual(result["state"], "notReady")
            self.assertTrue(result["controlledControllerChainObserved"])
            self.assertFalse(result["loadedOptionsObserved"])

    def test_27_decoration_records_declared_inputs_without_claiming_final_bounds(self):
        reader = fixture()
        reader.put(ADDR["decoration"], 0xFF, "<B")
        reader.put(ADDR["decoration"] + 1, 0xFF, "<B")
        reader.put(OPTIONS["presetDecoration"] + 1, 18, "<B")
        result = collect(reader)
        groups = result["samples"][0]["loadedOptions"]["decorationGroups"]
        self.assertEqual(groups[0]["fallbackCandidate"], 12)
        self.assertEqual(groups[0]["fallbackSource"], "groupDefault")
        self.assertEqual(groups[1]["fallbackCandidate"], 18)
        self.assertEqual(groups[1]["fallbackSource"], "preset")
        self.assertEqual(groups[2]["rawChoice"], 2)  # Below declared min is not a final-bound failure.
        self.assertEqual(groups[2]["declaredMin"], 10)
        self.assertEqual(groups[2]["modeByte"], 4)
        self.assertFalse(result["decorationComputedBoundsVerified"])
        self.assertTrue(all(not g["nativeComputedBoundsVerified"] for g in groups))
        self.assertFalse(result["samples"][0]["loadedOptions"]["slotSemanticsVerified"])

    def test_28_full_decoration_input_remains_bounded_and_output_is_representative(self):
        reader = fixture()
        reader.put(OPTIONS["decorationParams"] + 0x50, 250, "<I")
        reader.put(OPTIONS["decorationParams"] + 0x54, 250, "<I")
        result = collect(reader)
        self.assertEqual(result["state"], "observed")
        self.assertEqual(len(result["samples"][0]["loadedOptions"]["decorationGroups"]), 250)
        self.assertLess(len(json.dumps(result, ensure_ascii=False, indent=2).encode()), 512 * 1024)
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))


if __name__ == "__main__":
    unittest.main(verbosity=2)
