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
SCENE = {"scene": 0x200000, "ownerWeak": 0x201000, "parameter": 0x202000,
         "sceneWeak": 0x203000, "renderWeak": 0x204000, "selector": 0x205000,
         "buffer0": 0x206000, "buffer1": 0x207000}
RENDER_IDENTITIES = ({"vtable": BASE + 0x91000, "col": BASE + 0x92000,
                      "descriptor": BASE + 0x93000, "hierarchy": BASE + 0x94000},
                     {"vtable": BASE + 0x95000, "col": BASE + 0x96000,
                      "descriptor": BASE + 0x97000, "hierarchy": BASE + 0x98000})


def resource_scene_fixture(skinned=True):
    reader = skinned_scene_fixture() if skinned else scene_fixture()
    for slot, layout in enumerate(RENDER_IDENTITIES):
        primary = SCENE[f"buffer{slot}"]
        # Exactly eight readable heap bytes: any descriptor/member read fails.
        reader.block(primary, 8)
        reader.put(primary, layout["vtable"])
        reader.put(layout["vtable"] - 8, layout["col"])
        reader.segments[layout["col"]] = bytearray(struct.pack("<6I", 1, 0, 0,
            layout["descriptor"] - BASE, layout["hierarchy"] - BASE, layout["col"] - BASE))
        reader.block(layout["descriptor"] + 16, 192)
        name = f".?AVSyntheticRenderInput{slot}@fixture@@".encode("ascii")
        reader.segments[layout["descriptor"] + 16][:len(name)] = name
    reader.reads.clear()
    return reader


def collect_resource_identities(reader, pause=lambda _: None):
    return probe.collect(reader, BASE, LENGTH, pause, render_resource_identities=True)


def scene_fixture():
    reader = fixture()
    for name, address in SCENE.items():
        if name not in ("buffer0", "buffer1"):
            reader.block(address, 0x200)
    reader.put(ADDR["owner"] + 0x218, 2, "<I")
    reader.put(ADDR["owner"] + 0x21C, 2, "<I")
    reader.put(ADDR["members"] + 8, SCENE["scene"])
    reader.put(SCENE["scene"], BASE + probe.SCENE_VTABLE)
    reader.put(BASE + probe.SCENE_VTABLE + 8, BASE + probe.SCENE_GETTER)
    meta, col = BASE + probe.SCENE_META, BASE + 0x60000
    reader.block(meta, 32)
    reader.put(meta, BASE + probe.SCENE_META_VTABLE)
    reader.put(BASE + probe.SCENE_META_VTABLE - 8, col)
    reader.segments[col] = bytearray(struct.pack("<6I", 1, 0, 0, 0x61000, 0x62000, col - BASE))
    reader.names[meta] = probe.SCENE_META_TYPE
    for field, holder, target in ((SCENE["scene"] + 0x60, SCENE["ownerWeak"], ADDR["owner"] + 0x28),
                   (SCENE["parameter"] + 0x50, SCENE["sceneWeak"], SCENE["scene"] + 0x28),
                   (SCENE["scene"] + 0x78, SCENE["renderWeak"], ADDR["owner"] + 0x28)):
        reader.put(field, holder); reader.put(holder + 8, target)
    reader.put(SCENE["scene"] + 0xA0, SCENE["parameter"])
    reader.put(SCENE["parameter"], BASE + probe.SCENE_PARAM_VTABLE)
    reader.put(ADDR["owner"] + 0xA8, SCENE["selector"])
    reader.put(SCENE["selector"] + 0x18, SCENE["buffer0"])
    reader.put(SCENE["selector"] + 0x20, SCENE["buffer1"])
    reader.put(SCENE["selector"] + 0x28, 1, "<B")
    return reader


def skinned_scene_fixture():
    reader = scene_fixture()
    component, meta, col = 0x220000, BASE + probe.SKINNED_MESH_META, BASE + 0x80000
    reader.block(component, 0x300); reader.put(component, BASE + probe.SKINNED_MESH_VTABLE)
    reader.put(component + 0xA8, SCENE["selector"])
    reader.put(SCENE["renderWeak"] + 8, component + 0x28)
    reader.put(BASE + probe.SKINNED_MESH_VTABLE + 8, BASE + probe.SKINNED_MESH_GETTER)
    reader.block(meta, 24); reader.put(meta, BASE + probe.SKINNED_MESH_META_VTABLE)
    reader.put(BASE + probe.SKINNED_MESH_META_VTABLE - 8, col)
    reader.segments[col] = bytearray(struct.pack("<6I", 1, 0, 0, 0x81000, 0x82000, col - BASE))
    reader.names[meta] = probe.SKINNED_MESH_META_TYPE
    return reader


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

    def test_29_scene_uses_reflection_constructor_and_two_owner_round_trips(self):
        reader = scene_fixture()
        result = collect(reader)
        self.assertEqual(result["state"], "observed")
        self.assertEqual(result["schemaVersion"], 4)
        self.assertTrue(result["stableTwoSamples"] and result["characterSceneObserved"])
        self.assertTrue(result["sceneRenderSelectorObserved"])
        scene = result["samples"][0]["characterScene"]
        self.assertEqual(scene["sceneOccurrences"], 1)
        self.assertFalse(scene["primaryMsvcRttiVerified"])
        self.assertEqual(scene["reflectionMetadata"]["rtti"], probe.SCENE_META_TYPE)
        self.assertTrue(scene["sceneOwnerRoundTripObserved"] and scene["parameterOwnerRoundTripObserved"])
        self.assertEqual(scene["parameterResource"]["constructorAllocationBytes"], 0x200)
        self.assertTrue(scene["renderObject"]["equalsControlledOwner"])
        selector = scene["renderSelector"]
        self.assertEqual(selector["selectedResourcePointer"], hex(SCENE["buffer1"]))
        self.assertFalse(selector["typeInterpreted"] or selector["selectedResourceDereferenced"])
        self.assertFalse(result["renderedDescriptorVerified"] or result["appearanceApplicationVerified"])
        self.assertFalse(any(SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x200 for address, _ in reader.reads))
        self.assertNotIn((SCENE["scene"] + 0x10, 8), reader.reads)  # Not an invented owner field.

    def test_30_scene_missing_is_distinct_from_controller_observation(self):
        result = collect(fixture())
        self.assertEqual(result["state"], "observed")
        self.assertTrue(result["controlledControllerChainObserved"])
        self.assertFalse(result["characterSceneObserved"] or result["sceneRenderSelectorObserved"])
        self.assertEqual(result["samples"][0]["characterScene"]["sceneOccurrences"], 0)

    def test_31_scene_is_exact_unique_component_not_a_name_or_pointer_scan(self):
        reader = scene_fixture()
        reader.put(ADDR["owner"] + 0x218, 3, "<I"); reader.put(ADDR["owner"] + 0x21C, 3, "<I")
        reader.put(ADDR["members"] + 16, SCENE["scene"])
        result = collect(reader)
        self.assertIn("not unique", result["reason"])
        self.assertNotIn((SCENE["scene"] + 0x60, 8), reader.reads)
        reader = scene_fixture(); reader.put(SCENE["scene"], BASE + probe.SCENE_VTABLE + 8)
        result = collect(reader)
        self.assertFalse(result["characterSceneObserved"])
        self.assertNotIn((SCENE["scene"] + 0x60, 8), reader.reads)
        reader = scene_fixture(); reader.put(ADDR["members"] + 8, 0)
        self.assertIn("owner component member", collect(reader)["reason"])

    def test_32_scene_getter_and_reflection_metadata_must_agree(self):
        for field in ("getter", "type", "vt", "offset"):
            reader = scene_fixture()
            meta = BASE + probe.SCENE_META
            if field == "getter":
                reader.put(BASE + probe.SCENE_VTABLE + 8, BASE + 0x1379980)
            elif field == "type":
                reader.names[meta] = ".?AVUnsupported@pa@@"
            elif field == "offset":
                reader.put(BASE + 0x60000 + 4, 0x28, "<I")
            else:
                reader.put(BASE + 0x70000 - 8, BASE + 0x60000)
                reader.put(meta, BASE + 0x70000)
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["characterSceneObserved"])
            self.assertNotIn((SCENE["scene"] + 0x60, 8), reader.reads)

    def test_33_scene_parameter_and_weak_round_trips_reject_before_descendants(self):
        for address, value, fmt in ((SCENE["ownerWeak"] + 8, SCENE["scene"] + 0x28, "<Q"),
                (SCENE["sceneWeak"] + 8, ADDR["owner"] + 0x28, "<Q"),
                (SCENE["scene"] + 0x3D, 1, "<B"), (SCENE["parameter"] + 0x15, 2, "<B"),
                (SCENE["parameter"], BASE + probe.SCENE_PARAM_VTABLE + 8, "<Q"),
                (SCENE["parameter"] + 0x50, 0, "<Q")):
            reader = scene_fixture(); reader.put(address, value, fmt)
            result = collect(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["sceneRenderSelectorObserved"])
            self.assertNotIn((SCENE["selector"] + 0x18, 17), reader.reads)

    def test_34_missing_scene_resources_retain_partial_readiness_without_false_claims(self):
        for address in (SCENE["scene"] + 0xA0, SCENE["scene"] + 0x78,
                        SCENE["renderWeak"] + 8, ADDR["owner"] + 0xA8):
            reader = scene_fixture(); reader.put(address, 0)
            result = collect(reader)
            self.assertEqual(result["state"], "observed")  # Existing controller contract remains observed.
            self.assertTrue(result["characterSceneObserved"])
            self.assertFalse(result["sceneRenderSelectorObserved"])
            self.assertEqual(result["samples"][0]["characterScene"]["state"], "notReady")

    def test_35_render_type_and_selector_bounds_stop_unknown_layout(self):
        reader = scene_fixture(); reader.put(SCENE["selector"] + 0x28, 2, "<B")
        result = collect(reader)
        self.assertIn("two-entry pair", result["reason"])
        self.assertFalse(result["sceneRenderSelectorObserved"])
        reader = scene_fixture()
        other = 0x220000
        reader.block(other, 0x300); reader.put(other, reader.value(ADDR["owner"]))
        reader.names[other] = ".?AVSceneObjectBase@pa@@"
        reader.put(SCENE["renderWeak"] + 8, other + 0x28)
        result = collect(reader)
        self.assertIn("RTTI differs", result["reason"])
        self.assertNotIn((other + 0xA8, 8), reader.reads)
        reader = scene_fixture()
        reader.segments[SCENE["selector"]] = reader.segments[SCENE["selector"]][:0x28]
        self.assertIn("resource pair/index complete", collect(reader)["reason"])

    def test_36_render_buffers_remain_opaque_even_with_valid_selection(self):
        for index in (0, 1):
            reader = scene_fixture(); reader.put(SCENE["selector"] + 0x28, index, "<B")
            reader.put(SCENE["selector"] + 0x18 + index * 8, 0)
            result = collect(reader)
            self.assertTrue(result["sceneRenderSelectorObserved"])
            selector = result["samples"][0]["characterScene"]["renderSelector"]
            self.assertEqual(selector["selectedResourcePointer"], "0x0")
            self.assertFalse(selector["selectedResourceDereferenced"])
            self.assertFalse(result["renderedDescriptorVerified"])

    def test_37_scene_fields_reread_and_second_sample_changes_are_preserved(self):
        reader = scene_fixture(); original = reader.read; seen = []
        def changing(address, size):
            if address == SCENE["selector"] + 0x18 and size == 17:
                seen.append(1)
                if len(seen) > 1:
                    return original(address, size)[:-1] + b"\0"
            return original(address, size)
        reader.read = changing
        result = collect(reader)
        self.assertIn("Scene interpreted fields changed", result["reason"])
        self.assertFalse(result["controlledControllerChainObserved"])
        self.assertIn("renderSelector", result["samples"][0]["characterScene"])
        reader = scene_fixture()
        def unload(_):
            reader.put(SCENE["scene"] + 0x78, 0)
        result = collect(reader, unload)
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertTrue(result["samples"][0]["characterScene"]["renderLinkObserved"])
        self.assertFalse(result["samples"][1]["characterScene"]["renderLinkObserved"])

    def test_38_scene_contract_bytes_and_global_bounds_are_preflight_only(self):
        for rva in (0x2D091C0, 0x2D0AB12, 0x2C7D324, 0x7268A3):
            reader = scene_fixture(); reader.segments[BASE + rva][0] ^= 1
            result = collect(reader)
            self.assertEqual(result["samples"], [])
            self.assertIn("code bytes", result["reason"])
        for length in (probe.SCENE_META + 23, probe.SCENE_VTABLE + 15):
            reader = scene_fixture(); reader.reads.clear()
            result = probe.collect(reader, BASE, length, lambda _: None)
            self.assertEqual(result["samples"], [])
            self.assertEqual(reader.reads, [])

    def test_39_wrong_scene_weak_backlinks_are_rejected_before_target_dereference(self):
        foreign, target = 0x240000, 0x240028
        for holder in (SCENE["ownerWeak"], SCENE["sceneWeak"]):
            with self.subTest(holder=hex(holder)):
                reader = scene_fixture()
                # Even a readable, apparently valid flag must not authorize
                # interpreting a target outside the already verified backlink.
                reader.block(foreign, 0x200)
                reader.put(holder + 8, target)
                result = collect(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertIn("weak target differs from the reviewed primary owner", result["reason"])
                self.assertFalse(result["characterSceneObserved"] or result["sceneRenderSelectorObserved"])
                self.assertFalse(any(foreign <= address < foreign + 0x200 for address, _ in reader.reads))

    def test_40_final_module_or_digest_change_clears_scene_success_flags(self):
        for changed in ("module", "digest"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
                reader = scene_fixture()
                exe, output = Path(temp) / "CrimsonDesert.exe", Path(temp) / "changed.json"
                reader.module = mock.Mock(side_effect=[(BASE, LENGTH, exe),
                                                       (BASE + (0x1000 if changed == "module" else 0), LENGTH, exe)])
                reader.close = mock.Mock()
                digests = [probe.roster.SHA256, "0" * 64]
                with mock.patch("sys.argv", ["probe", "--pid", "42123", "--output", str(output)]),\
                        mock.patch.object(probe.core, "Reader", return_value=reader),\
                        mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION),\
                        mock.patch.object(probe, "file_digest", side_effect=digests),\
                        mock.patch("builtins.print"):
                    self.assertEqual(probe.main(), 1)
                result = json.loads(output.read_bytes())
                self.assertEqual(result["state"], "unstable")
                self.assertIn("Game module changed", result["reason"])
                for flag in ("stableTwoSamples", "controlledControllerChainObserved", "characterSceneObserved",
                             "sceneRenderSelectorObserved", "renderedDescriptorVerified"):
                    self.assertFalse(result[flag], flag)
                self.assertEqual(len(result["samples"]), 2)
                self.assertTrue(all(sample["characterScene"]["state"] == "observed" for sample in result["samples"]))
                reader.close.assert_called_once()

    def test_41_render_locator_failure_preserves_exact_existing_header_reads(self):
        foreign, vt, col = 0x220000, BASE + 0x70000, BASE + 0x71000
        cases = ((0, 2, "signature-equals-one"), (1, 0x28, "primary-this-offset-zero"),
                 (3, 0, "type-descriptor-main-image-bounds"),
                 (4, LENGTH, "class-hierarchy-main-image-bounds"), (5, 0, "locator-self-rva"))
        for index, bad, failed in cases:
            with self.subTest(failed=failed):
                reader = scene_fixture()
                reader.block(foreign, 0x300); reader.put(foreign, vt)
                reader.put(SCENE["renderWeak"] + 8, foreign + 0x28)
                reader.put(vt - 8, col)
                fields = [1, 0, 37, 0x72000, 0x73000, col - BASE]
                fields[index] = bad
                header = struct.pack("<6I", *fields)
                reader.segments[col] = bytearray(header)
                reader.rtti = mock.Mock(wraps=reader.rtti)
                result = collect(reader)
                identity = result["samples"][0]["characterScene"]["renderObjectIdentity"]
                self.assertEqual(result["state"], "rejected")
                self.assertEqual(len(result["samples"]), 1)
                self.assertFalse(result["stableTwoSamples"] or result["characterSceneObserved"])
                self.assertEqual(identity["context"], "render-linked primary object")
                self.assertEqual(identity["vtablePointer"], hex(vt))
                self.assertEqual(identity["candidateLocatorPointer"], hex(col))
                self.assertEqual(identity["candidateLocatorHeaderHex"], header.hex())
                self.assertEqual(identity["candidateLocatorFields"]["constructorDisplacement"], 37)
                self.assertEqual(identity["failedChecks"], [failed])
                self.assertEqual(identity["failureReason"], result["reason"])
                self.assertIn("render-linked primary object", result["reason"])
                self.assertFalse(identity["typeGatePassed"] or identity["completePrimaryLocatorVerified"]
                                 or identity["candidateLocatorFieldsInterpretedAsVerifiedRtti"])
                self.assertNotIn("observedRtti", identity)
                self.assertFalse(any(call.args[0] == foreign for call in reader.rtti.call_args_list))
                self.assertNotIn((foreign + 0xA8, 8), reader.reads)

    def test_42_render_identity_bounds_and_unreadable_header_keep_only_read_evidence(self):
        foreign, vt, col = 0x220000, BASE + 0x70000, BASE + 0x71000
        for case in ("vtable", "locator", "header"):
            with self.subTest(case=case):
                reader = scene_fixture()
                reader.block(foreign, 0x300)
                actual_vt = BASE + LENGTH if case == "vtable" else vt
                actual_col = BASE + LENGTH if case == "locator" else col
                reader.put(foreign, actual_vt)
                reader.put(SCENE["renderWeak"] + 8, foreign + 0x28)
                reader.put(vt - 8, actual_col)
                # No header is readable for any of these cases.
                result = collect(reader)
                identity = result["samples"][0]["characterScene"]["renderObjectIdentity"]
                self.assertEqual(identity["vtablePointer"], hex(actual_vt))
                self.assertNotIn("candidateLocatorHeaderHex", identity)
                self.assertNotIn("candidateLocatorFields", identity)
                self.assertFalse(identity["typeGatePassed"])
                self.assertEqual(identity["failureReason"], result["reason"])
                if case == "vtable":
                    self.assertEqual(identity["failedChecks"], ["vtable-main-image-bounds"])
                    self.assertNotIn("candidateLocatorPointer", identity)
                    self.assertNotIn((actual_vt - 8, 8), reader.reads)
                else:
                    self.assertEqual(identity["candidateLocatorPointer"], hex(actual_col))
                    if case == "locator":
                        self.assertEqual(identity["failedChecks"], ["locator-main-image-bounds"])
                        self.assertNotIn((actual_col, 24), reader.reads)
                    else:
                        self.assertIn("complete readable span is unavailable", result["reason"])
                self.assertNotIn((foreign + 0xA8, 8), reader.reads)

    def test_43_render_valid_locator_unreviewed_rtti_still_stops_before_layout(self):
        foreign = 0x220000
        reader = scene_fixture()
        reader.block(foreign, 0x300); reader.put(foreign, reader.value(ADDR["owner"]))
        reader.names[foreign] = ".?AVSceneObjectBase@pa@@"
        reader.put(SCENE["renderWeak"] + 8, foreign + 0x28)
        result = collect(reader)
        identity = result["samples"][0]["characterScene"]["renderObjectIdentity"]
        self.assertTrue(identity["completePrimaryLocatorVerified"])
        self.assertFalse(identity["typeGatePassed"])
        self.assertEqual(identity["expectedRtti"], probe.TYPES["owner"])
        self.assertEqual(identity["observedRtti"], reader.names[foreign])
        self.assertEqual(identity["failedChecks"], ["exact-reviewed-rtti"])
        self.assertNotIn((foreign + 0xA8, 8), reader.reads)
        self.assertFalse(result["characterSceneObserved"] or result["sceneRenderSelectorObserved"])

    def test_44_render_identity_evidence_retains_successful_two_sample_contract(self):
        reader = scene_fixture()
        result = collect(reader)
        self.assertTrue(result["stableTwoSamples"] and result["sceneRenderSelectorObserved"])
        self.assertEqual(len(result["samples"]), 2)
        for sample in result["samples"]:
            identity = sample["characterScene"]["renderObjectIdentity"]
            self.assertTrue(identity["typeGatePassed"] and identity["completePrimaryLocatorVerified"])
            self.assertEqual(identity["failedChecks"], [])
            self.assertEqual(identity["observedRtti"], probe.TYPES["owner"])
            self.assertNotIn("failureReason", identity)
            self.assertFalse(sample["characterScene"]["selectedResourceTypeVerified"])
        self.assertFalse(result["renderedDescriptorVerified"] or result["appearanceApplicationVerified"])

    def test_45_exact_skinned_mesh_reflection_contract_observes_only_opaque_selector(self):
        reader = skinned_scene_fixture()
        result = collect(reader)
        self.assertTrue(result["stableTwoSamples"] and result["sceneRenderSelectorObserved"])
        for sample in result["samples"]:
            scene = sample["characterScene"]
            self.assertEqual(scene["renderObject"]["reflectionType"], "SkinnedMeshComponent")
            self.assertFalse(scene["renderObject"]["primaryMsvcRttiVerified"])
            self.assertTrue(scene["renderObjectIdentity"]["typeGatePassed"])
            self.assertEqual(scene["renderObjectIdentity"]["reflectionMetadata"]["rtti"], probe.SKINNED_MESH_META_TYPE)
            self.assertFalse(scene["renderSelector"]["selectedResourceDereferenced"])
        self.assertFalse(any(SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x200 for address, _ in reader.reads))
        self.assertNotIn((0x220000 + 0x10, 8), reader.reads)

    def test_46_skinned_mesh_getter_metadata_and_locator_fail_before_selector(self):
        for field in ("getter", "rtti", "vtable", "locator"):
            with self.subTest(field=field):
                reader = skinned_scene_fixture()
                if field == "getter":
                    reader.put(BASE + probe.SKINNED_MESH_VTABLE + 8, BASE + probe.SCENE_GETTER)
                elif field == "rtti":
                    reader.names[BASE + probe.SKINNED_MESH_META] = probe.SCENE_META_TYPE
                elif field == "vtable":
                    reader.put(BASE + probe.SKINNED_MESH_META, BASE + probe.SKINNED_MESH_META_VTABLE + 8)
                else:
                    reader.put(BASE + 0x80000 + 4, 0x28, "<I")
                result = collect(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertFalse(result["characterSceneObserved"] or result["stableTwoSamples"])
                identity = result["samples"][0]["characterScene"]["renderObjectIdentity"]
                self.assertFalse(identity["typeGatePassed"])
                self.assertEqual(identity["failureReason"], result["reason"])
                self.assertNotIn((0x220000 + 0xA8, 8), reader.reads)

    def test_47_skinned_mesh_exact_code_and_global_bounds_gate_before_chain(self):
        for rva in (0x2D96D6A, 0x2D88B10, 0x36026F, 0x3602B3):
            reader = skinned_scene_fixture(); reader.segments[BASE + rva][0] ^= 1
            result = collect(reader)
            self.assertEqual(result["samples"], [])
            self.assertIn("code bytes", result["reason"])
        reader = skinned_scene_fixture(); reader.reads.clear()
        with mock.patch.object(probe, "SKINNED_MESH_META", LENGTH):
            result = collect(reader)
        self.assertEqual(result["samples"], [])
        self.assertEqual(reader.reads, [])

    def test_48_skinned_mesh_metadata_reread_cannot_promote_partial_success(self):
        reader = skinned_scene_fixture(); original = reader.rtti; seen = []
        def changing(address, base, length):
            if address == BASE + probe.SKINNED_MESH_META:
                seen.append(1)
                if len(seen) > 1:
                    return probe.SCENE_META_TYPE
            return original(address, base, length)
        reader.rtti = changing
        result = collect(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertFalse(result["stableTwoSamples"] or result["sceneRenderSelectorObserved"])
        self.assertEqual(len(result["samples"]), 1)

    def test_49_render_resource_success_is_two_bounded_identity_reads_not_a_layout(self):
        for skinned in (False, True):
            with self.subTest(skinned=skinned):
                reader = resource_scene_fixture(skinned)
                original_rtti = reader.rtti
                def rtti(address, base, length):
                    self.assertNotIn(address, (SCENE["buffer0"], SCENE["buffer1"]))
                    return original_rtti(address, base, length)
                reader.rtti = rtti
                result = collect_resource_identities(reader)
                self.assertEqual(result["state"], "observed")
                self.assertEqual(result["schemaVersion"], 4)
                self.assertTrue(result["stableTwoSamples"] and result["renderResourceIdentitiesRequested"]
                                and result["renderResourceIdentitiesObserved"])
                for sample in result["samples"]:
                    scene = sample["characterScene"]
                    selector = scene["renderSelector"]
                    self.assertTrue(selector["resourceReadsIdentityOnly"] and selector["selectedResourceDereferenced"])
                    self.assertEqual(len(selector["resourceIdentities"]), 2)
                    self.assertFalse(scene["selectedResourceTypeVerified"] or scene["renderedDescriptorVerified"])
                    for slot, identity in enumerate(selector["resourceIdentities"]):
                        self.assertEqual(identity["rtti"], f".?AVSyntheticRenderInput{slot}@fixture@@")
                        self.assertEqual(identity["pointer"], hex(SCENE[f"buffer{slot}"]))
                        self.assertTrue(identity["identityOnly"] and identity["rttiNameObserved"])
                        self.assertFalse(identity["layoutInterpreted"] or identity["exactResourceClassVerified"])
                        self.assertEqual(identity["failedChecks"], [])
                reads = [(address, size) for address, size in reader.reads
                         if SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x1000]
                self.assertEqual(set(reads), {(SCENE["buffer0"], 8), (SCENE["buffer1"], 8)})
                self.assertFalse(any(address in (SCENE["buffer0"] + 0x68, SCENE["buffer1"] + 0x68)
                                     for address, _ in reader.reads))
                for field in ("nativeFunctionsInvoked", "gameMemoryWritten", "heapScanned", "renderedDescriptorVerified",
                              "appearanceApplicationVerified", "appearanceRestoreVerified", "steveModelLoaded", "snapshotAtomic"):
                    self.assertIs(result[field], False)

    def test_50_resource_identity_mode_is_opt_in_and_default_never_dereferences_pair(self):
        reader = resource_scene_fixture()
        result = collect(reader)
        self.assertEqual(result["state"], "observed")
        self.assertFalse(result["renderResourceIdentitiesRequested"] or result["renderResourceIdentitiesObserved"])
        self.assertNotIn("resourceIdentities", result["samples"][0]["characterScene"]["renderSelector"])
        self.assertFalse(any(SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x1000 for address, _ in reader.reads))

    def test_51_null_resource_slots_are_recorded_without_identity_or_null_reads(self):
        for nulls in ((0,), (1,), (0, 1)):
            with self.subTest(nulls=nulls):
                reader = resource_scene_fixture()
                for slot in nulls:
                    reader.put(SCENE["selector"] + 0x18 + slot * 8, 0)
                result = collect_resource_identities(reader)
                self.assertEqual(result["state"], "observed")
                self.assertEqual(result["renderResourceIdentitiesObserved"], len(nulls) < 2)
                selector = result["samples"][0]["characterScene"]["renderSelector"]
                self.assertEqual(selector["selectedResourceDereferenced"], 1 not in nulls)
                self.assertEqual(len(selector["resourceIdentities"]), 2)
                for slot in nulls:
                    self.assertEqual(selector["resourceIdentities"][slot], {"slot": slot, "present": False})
                    self.assertNotIn((SCENE[f"buffer{slot}"], 8), reader.reads)
                self.assertFalse(any(address == 0 for address, _ in reader.reads))

    def test_52_resource_vtable_and_locator_bounds_stop_before_descendant_reads(self):
        layout = RENDER_IDENTITIES[0]
        for field, value, failed in (
                ("vtable", BASE, "vtable-main-image-bounds"),
                ("vtable", BASE + LENGTH - 7, "vtable-main-image-bounds"),
                ("col", BASE - 8, "locator-main-image-bounds"),
                ("col", BASE + LENGTH - 23, "locator-main-image-bounds")):
            with self.subTest(field=field, value=hex(value)):
                reader = resource_scene_fixture(); evidence = {}
                reader.put(SCENE["buffer0"] if field == "vtable" else layout["vtable"] - 8, value)
                with self.assertRaisesRegex(probe.ProbeError, failed):
                    probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
                self.assertEqual(evidence["failedChecks"], [failed])
                self.assertFalse(evidence["rttiNameObserved"] or evidence["layoutInterpreted"])
                self.assertNotIn((layout["descriptor"] + 16, 192), reader.reads)
                if field == "vtable":
                    self.assertEqual(reader.reads, [(SCENE["buffer0"], 8)])
                else:
                    self.assertEqual(reader.reads, [(SCENE["buffer0"], 8), (layout["vtable"] - 8, 8)])

    def test_53_resource_col_signature_primary_offset_self_and_image_rvas_fail_closed(self):
        layout = RENDER_IDENTITIES[0]
        cases = ((0, 0, "signature-equals-one"), (1, 0x28, "primary-this-offset-zero"),
                 (5, 0, "locator-self-rva"), (3, 0, "type-descriptor-main-image-bounds"),
                 (3, LENGTH - 207, "type-descriptor-main-image-bounds"),
                 (4, 0, "class-hierarchy-main-image-bounds"),
                 (4, LENGTH, "class-hierarchy-main-image-bounds"))
        for field, value, failed in cases:
            with self.subTest(field=field, value=value):
                reader = resource_scene_fixture(); evidence = {}
                reader.put(layout["col"] + field * 4, value, "<I")
                header = bytes(reader.segments[layout["col"]])
                with self.assertRaisesRegex(probe.ProbeError, failed):
                    probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
                self.assertEqual(evidence["candidateLocatorHeaderHex"], header.hex())
                self.assertEqual(evidence["failedChecks"], [failed])
                self.assertNotIn((layout["descriptor"] + 16, 192), reader.reads)
                self.assertEqual(len(reader.reads), 3)

    def test_54_resource_rtti_requires_complete_bounded_terminated_printable_ascii(self):
        chars = RENDER_IDENTITIES[0]["descriptor"] + 16
        for raw, failed in ((b"A" * 192, "bounded-terminated-rtti-name"),
                            (b"bad\xff\0", "ascii-rtti-name"), (b"bad\n\0", "ascii-rtti-name"),
                            (b"\0", "ascii-rtti-name")):
            with self.subTest(raw=raw[:12]):
                reader = resource_scene_fixture(); evidence = {}
                reader.segments[chars][:len(raw)] = raw
                with self.assertRaisesRegex(probe.ProbeError, failed):
                    probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
                self.assertFalse(evidence["rttiNameObserved"])
                self.assertEqual(evidence["failedChecks"], [failed])
        reader = resource_scene_fixture(); evidence = {}
        reader.segments[chars] = bytearray(b"X" * 191 + b"\0")
        result = probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
        self.assertEqual(result["rtti"], "X" * 191)
        reader = resource_scene_fixture(); evidence = {}
        reader.segments[chars] = reader.segments[chars][:191]
        with self.assertRaisesRegex(probe.ProbeError, "complete readable span"):
            probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
        self.assertIn("failureReason", evidence)
        self.assertFalse(evidence["rttiNameObserved"])

    def test_55_every_interpreted_resource_identity_byte_is_rechecked(self):
        layout = RENDER_IDENTITIES[0]
        for watched in ((SCENE["buffer0"], 8), (layout["vtable"] - 8, 8),
                        (layout["col"], 24), (layout["descriptor"] + 16, 192)):
            with self.subTest(watched=watched):
                reader = resource_scene_fixture(); original = reader.read; seen = []
                def changed(address, size):
                    raw = original(address, size)
                    if (address, size) == watched:
                        seen.append(1)
                        if len(seen) == 2:
                            return bytes([raw[0] ^ 1]) + raw[1:]
                    return raw
                reader.read = changed; evidence = {}
                with self.assertRaisesRegex(probe.ProbeError, "stable-identity-bytes"):
                    probe.resource_identity(reader, SCENE["buffer0"], BASE, LENGTH, evidence)
                self.assertFalse(evidence["rttiNameObserved"])
                self.assertEqual(evidence["failedChecks"], ["stable-identity-bytes"])

    def test_56_resource_reidentification_catches_new_but_individually_stable_identity(self):
        reader = resource_scene_fixture(); original = reader.read; seen = []
        def changed(address, size):
            raw = original(address, size)
            if address == SCENE["buffer0"] and size == 8:
                seen.append(1)
                if len(seen) >= 3:
                    return struct.pack("<Q", RENDER_IDENTITIES[1]["vtable"])
            return raw
        reader.read = changed
        result = collect_resource_identities(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("identity changed within", result["reason"])
        self.assertFalse(result["renderResourceIdentitiesObserved"] or result["stableTwoSamples"])
        first = result["samples"][0]["characterScene"]["renderSelector"]["resourceIdentities"][0]
        self.assertTrue(first["rttiNameObserved"])
        self.assertEqual(first["rtti"], ".?AVSyntheticRenderInput0@fixture@@")

    def test_57_pair_is_rechecked_after_the_final_identity_reads(self):
        reader = resource_scene_fixture(); original = reader.read; seen = []
        chars = RENDER_IDENTITIES[1]["descriptor"] + 16
        def changed(address, size):
            raw = original(address, size)
            if address == chars and size == 192:
                seen.append(1)
                if len(seen) == 4:
                    reader.put(SCENE["selector"] + 0x28, 0, "<B")
            return raw
        reader.read = changed
        result = collect_resource_identities(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("Scene interpreted fields changed", result["reason"])
        self.assertFalse(result["renderResourceIdentitiesObserved"] or result["sceneRenderSelectorObserved"])
        self.assertEqual(len(result["samples"]), 1)

    def test_58_two_sample_pair_or_identity_change_preserves_both_without_global_success(self):
        for change in ("pair", "identity"):
            with self.subTest(change=change):
                reader = resource_scene_fixture()
                def changed(_):
                    if change == "pair":
                        reader.put(SCENE["selector"] + 0x18, SCENE["buffer1"])
                        reader.put(SCENE["selector"] + 0x20, SCENE["buffer0"])
                    else:
                        reader.segments[RENDER_IDENTITIES[1]["descriptor"] + 16][5] = ord("Z")
                result = collect_resource_identities(reader, changed)
                self.assertEqual(result["state"], "unstable")
                self.assertFalse(result["renderResourceIdentitiesObserved"] or result["stableTwoSamples"])
                self.assertEqual(len(result["samples"]), 2)
                self.assertTrue(all(s["characterScene"]["renderResourceIdentitiesObserved"] for s in result["samples"]))
                self.assertNotEqual(result["samples"][0]["characterScene"]["renderSelector"],
                                    result["samples"][1]["characterScene"]["renderSelector"])

    def test_59_cli_final_module_or_digest_change_clears_new_observation_flag(self):
        for changed in ("module", "digest"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
                reader = resource_scene_fixture()
                exe, output = Path(temp) / "CrimsonDesert.exe", Path(temp) / "changed.json"
                reader.module = mock.Mock(side_effect=[(BASE, LENGTH, exe),
                    (BASE + (0x1000 if changed == "module" else 0), LENGTH, exe)])
                reader.close = mock.Mock()
                with mock.patch("sys.argv", ["probe", "--pid", "42123", "--render-resource-identities", "--output", str(output)]),\
                        mock.patch.object(probe.core, "Reader", return_value=reader),\
                        mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION),\
                        mock.patch.object(probe, "file_digest", side_effect=[probe.roster.SHA256, "0" * 64]),\
                        mock.patch("builtins.print"):
                    self.assertEqual(probe.main(), 1)
                result = json.loads(output.read_bytes())
                self.assertTrue(result["renderResourceIdentitiesRequested"])
                self.assertEqual(result["state"], "unstable")
                for flag in ("renderResourceIdentitiesObserved", "stableTwoSamples", "controlledControllerChainObserved",
                             "characterSceneObserved", "sceneRenderSelectorObserved", "renderedDescriptorVerified",
                             "appearanceApplicationVerified", "appearanceRestoreVerified", "steveModelLoaded"):
                    self.assertIs(result[flag], False)
                self.assertTrue(all(s["characterScene"]["renderResourceIdentitiesObserved"] for s in result["samples"]))
                reader.close.assert_called_once()

    def test_60_second_resource_failure_keeps_first_and_exact_failure_evidence_in_report(self):
        reader = resource_scene_fixture()
        reader.put(RENDER_IDENTITIES[1]["col"] + 4, 0x28, "<I")
        result = collect_resource_identities(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertFalse(result["renderResourceIdentitiesObserved"] or result["renderedDescriptorVerified"]
                         or result["appearanceApplicationVerified"])
        identities = result["samples"][0]["characterScene"]["renderSelector"]["resourceIdentities"]
        self.assertEqual(len(identities), 2)
        self.assertTrue(identities[0]["rttiNameObserved"])
        self.assertFalse(identities[1]["rttiNameObserved"])
        self.assertEqual(identities[1]["failedChecks"], ["primary-this-offset-zero"])
        self.assertEqual(identities[1]["failureReason"], result["reason"])
        self.assertEqual(identities[1]["candidateLocatorFields"]["primaryThisOffset"], 0x28)
        self.assertNotIn((RENDER_IDENTITIES[1]["descriptor"] + 16, 192), reader.reads)
        with tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
            path = Path(temp) / "resource-identity-failure.json"
            probe.write_report(path, result)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), result)

    def test_61_first_resource_non_col_does_not_hide_second_identity_or_promote_partial_scene(self):
        reader = resource_scene_fixture()
        # Simulate a vtable predecessor pointing at in-image code, not a COL.
        code_address = BASE + 0xA1000
        raw_code = bytes.fromhex("4883e928e900000000") + b"\xcc" * 15
        reader.put(RENDER_IDENTITIES[0]["vtable"] - 8, code_address)
        reader.segments[code_address] = bytearray(raw_code)
        result = collect_resource_identities(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertEqual(len(result["samples"]), 1)
        scene = result["samples"][0]["characterScene"]
        identities = scene["renderSelector"]["resourceIdentities"]
        self.assertEqual(len(identities), 2)
        self.assertEqual(identities[0]["slot"], 0)
        self.assertEqual(identities[0]["candidateLocatorHeaderHex"], raw_code.hex())
        self.assertEqual(identities[0]["failedChecks"], ["signature-equals-one"])
        self.assertFalse(identities[0]["rttiNameObserved"])
        self.assertEqual(result["reason"], identities[0]["failureReason"])
        self.assertEqual(identities[1]["slot"], 1)
        self.assertTrue(identities[1]["rttiNameObserved"])
        self.assertEqual(identities[1]["rtti"], ".?AVSyntheticRenderInput1@fixture@@")
        self.assertNotIn((RENDER_IDENTITIES[0]["descriptor"] + 16, 192), reader.reads)
        self.assertIn((RENDER_IDENTITIES[1]["descriptor"] + 16, 192), reader.reads)
        self.assertFalse(scene["renderResourceIdentitiesObserved"] or scene["renderedDescriptorVerified"]
                         or scene["selectedResourceTypeVerified"] or scene["appearanceApplicationVerified"])
        for flag in ("stableTwoSamples", "controlledControllerChainObserved", "characterSceneObserved",
                     "sceneRenderSelectorObserved", "renderResourceIdentitiesObserved", "renderedDescriptorVerified",
                     "appearanceApplicationVerified", "appearanceRestoreVerified", "steveModelLoaded",
                     "nativeFunctionsInvoked", "gameMemoryWritten", "snapshotAtomic"):
            self.assertIs(result[flag], False, flag)
        reads = [(address, size) for address, size in reader.reads
                 if SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x1000]
        self.assertEqual(set(reads), {(SCENE["buffer0"], 8), (SCENE["buffer1"], 8)})

    def test_62_both_resource_rejections_keep_independent_failures_and_no_layout_reads(self):
        reader = resource_scene_fixture()
        reader.put(RENDER_IDENTITIES[0]["col"], 0xCCCCCCCC, "<I")
        reader.put(RENDER_IDENTITIES[1]["col"] + 4, 0x28, "<I")
        result = collect_resource_identities(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertEqual(len(result["samples"]), 1)
        scene = result["samples"][0]["characterScene"]
        identities = scene["renderSelector"]["resourceIdentities"]
        self.assertEqual(len(identities), 2)
        for slot, failed in enumerate(("signature-equals-one", "primary-this-offset-zero")):
            identity = identities[slot]
            self.assertEqual(identity["slot"], slot)
            self.assertEqual(identity["pointer"], hex(SCENE[f"buffer{slot}"]))
            self.assertEqual(identity["failedChecks"], [failed])
            self.assertIn(failed, identity["failureReason"])
            self.assertEqual(identity["candidateLocatorHeaderHex"], bytes(reader.segments[RENDER_IDENTITIES[slot]["col"]]).hex())
            self.assertFalse(identity["rttiNameObserved"] or identity["layoutInterpreted"] or identity["exactResourceClassVerified"])
            self.assertNotIn((RENDER_IDENTITIES[slot]["descriptor"] + 16, 192), reader.reads)
        self.assertNotEqual(identities[0]["failureReason"], identities[1]["failureReason"])
        self.assertEqual(result["reason"], identities[0]["failureReason"])
        self.assertFalse(scene["renderResourceIdentitiesObserved"] or scene["selectedResourceTypeVerified"]
                         or scene["renderedDescriptorVerified"] or scene["appearanceApplicationVerified"])
        for flag in ("stableTwoSamples", "controlledControllerChainObserved", "characterSceneObserved",
                     "sceneRenderSelectorObserved", "renderResourceIdentitiesObserved", "renderedDescriptorVerified",
                     "appearanceApplicationVerified", "appearanceRestoreVerified", "steveModelLoaded",
                     "nativeFunctionsInvoked", "gameMemoryWritten", "snapshotAtomic"):
            self.assertIs(result[flag], False, flag)
        reads = [(address, size) for address, size in reader.reads
                 if SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x1000]
        self.assertEqual(set(reads), {(SCENE["buffer0"], 8), (SCENE["buffer1"], 8)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
