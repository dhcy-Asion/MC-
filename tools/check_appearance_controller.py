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
NESTED_HEADERS = (0x230000, 0x231000)
INPUT_PATHS = ({"property": 0x240000, "holder": 0x242000, "chars": 0x244003,
                "text": "synthetic/controlled/declared_body.pac"},
               {"property": 0x241000, "holder": 0x243000, "chars": 0x245005,
                "text": "synthetic/controlled/declared_skeleton.pab"})
INITIAL_APPEARANCE_PATH = {"holder": 0x246000, "chars": 0x247003,
                           "text": "synthetic/initial/declared_appearance.app_xml"}


def input_path_scene_fixture():
    reader = skinned_scene_fixture()
    for rva, raw in probe.INPUT_PATH_WINDOWS.items():
        reader.segments[BASE + rva] = bytearray(raw)
    for row, (kind, (offset, vtable)) in zip(INPUT_PATHS, probe.RENDER_INPUT_PROPERTIES.items()):
        prop, holder, chars = row["property"], row["holder"], row["chars"]
        reader.put(0x220000 + offset, prop)
        # Unreviewed property fields and holder suffix are deliberately absent.
        reader.put(prop, BASE + vtable)
        reader.put(prop + 0x10, 0x220000)
        reader.put(prop + 0x1A, 0, "<B")
        reader.put(prop + 0x28, holder)
        reader.put(holder, chars)
        reader.segments[chars] = bytearray(row["text"].encode("ascii") + b"\0")
    initial = INITIAL_APPEARANCE_PATH
    reader.put(0x220000 + probe.INITIAL_APPEARANCE_INPUT_OFFSET, initial["holder"])
    # Only the producer-proven held pointer and holder[0] are available. A
    # fabricated property vtable/owner or resource prefix must not be read.
    reader.put(initial["holder"], initial["chars"])
    reader.segments[initial["chars"]] = bytearray(initial["text"].encode("ascii") + b"\0")
    reader.reads.clear()
    return reader


def collect_input_paths(reader, pause=lambda _: None):
    return probe.collect(reader, BASE, LENGTH, pause, render_input_paths=True)


def linked_scene_fixture():
    reader = skinned_scene_fixture()
    for rva, raw in probe.RESOURCE_LINK_WINDOWS.items():
        reader.segments[BASE + rva] = bytearray(raw)
    for slot, nested in enumerate(NESTED_HEADERS):
        primary = SCENE[f"buffer{slot}"]
        # Only the two reviewed parent fields and nested primary header exist.
        reader.block(primary, 8)
        reader.put(primary, BASE + probe.ANONYMOUS_RESOURCE_VTABLE)
        reader.put(primary + 0x68, nested)
        reader.block(nested, 8)
        reader.put(nested, BASE + 0x99000 + slot * 0x100)
    # Actual kind of non-COL prefix: linked mode must never follow this qword.
    reader.put(BASE + probe.ANONYMOUS_RESOURCE_VTABLE - 8, BASE + 0x3600C0)
    reader.segments[BASE + 0x3600C0] = bytearray.fromhex("b001c3cccccccccccccccccccccccccc488b4108c3cccccc")
    reader.reads.clear()
    return reader


def collect_resource_links(reader, pause=lambda _: None):
    return probe.collect(reader, BASE, LENGTH, pause, render_resource_links=True)


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


    def test_63_anonymous_links_read_only_three_qwords_with_two_complete_samples(self):
        reader = linked_scene_fixture()
        result = collect_resource_links(reader)
        self.assertEqual(result["schemaVersion"], 5)
        self.assertEqual(result["state"], "observed")
        self.assertTrue(result["renderResourceLinksRequested"] and result["renderResourceLinksObserved"])
        self.assertTrue(result["stableTwoSamples"] and result["controlledControllerChainObserved"])
        self.assertEqual(result["samples"][0], result["samples"][1])
        for sample in result["samples"]:
            links = sample["characterScene"]["renderSelector"]["resourceLinks"]
            self.assertEqual(len(links), 2)
            for slot, row in enumerate(links):
                self.assertTrue(row["anonymousParentVtableVerified"] and row["linkFieldObserved"]
                                and row["nestedPrimaryHeaderObserved"])
                self.assertEqual(row["nestedPointer"], hex(NESTED_HEADERS[slot]))
                self.assertEqual(row["nestedVtableRva"], hex(0x99000 + slot * 0x100))
                for flag in ("primaryMsvcRttiVerified", "nestedClassVerified", "nestedLayoutInterpreted", "descriptorVerified"):
                    self.assertIs(row[flag], False)
        for slot in range(2):
            primary, nested = SCENE[f"buffer{slot}"], NESTED_HEADERS[slot]
            reads = {(address, size) for address, size in reader.reads if primary <= address < primary + 0x100}
            self.assertEqual(reads, {(primary, 8), (primary + 0x68, 8)})
            self.assertEqual({(address, size) for address, size in reader.reads if nested <= address < nested + 0x100}, {(nested, 8)})
        self.assertNotIn((BASE + probe.ANONYMOUS_RESOURCE_VTABLE - 8, 8), reader.reads)
        for flag in ("renderResourceIdentitiesObserved", "renderedDescriptorVerified", "nativeFunctionsInvoked",
                     "gameMemoryWritten", "appearanceApplicationVerified", "appearanceRestoreVerified", "steveModelLoaded"):
            self.assertIs(result[flag], False)

    def test_64_link_mode_is_independent_from_col_identity_and_default(self):
        reader = linked_scene_fixture()
        self.assertEqual(collect_resource_identities(reader)["state"], "rejected")
        reader.reads.clear()
        self.assertEqual(collect_resource_links(reader)["state"], "observed")
        reader.reads.clear()
        result = collect(reader)
        self.assertEqual(result["schemaVersion"], 4)
        self.assertEqual(result["state"], "observed")
        self.assertFalse(result["renderResourceLinksRequested"] or result["renderResourceLinksObserved"])
        self.assertFalse(any(SCENE["buffer0"] <= address < SCENE["buffer1"] + 0x1000 for address, _ in reader.reads))
        self.assertFalse(any(address in {BASE + rva for rva in probe.RESOURCE_LINK_WINDOWS} for address, _ in reader.reads))

    def test_65_unknown_parent_vtable_stops_its_layout_and_records_sibling(self):
        reader = linked_scene_fixture()
        reader.put(SCENE["buffer0"], BASE + probe.ANONYMOUS_RESOURCE_VTABLE + 8)
        result = collect_resource_links(reader)
        self.assertEqual(result["state"], "rejected")
        links = result["samples"][0]["characterScene"]["renderSelector"]["resourceLinks"]
        self.assertEqual(links[0]["failedChecks"], ["exact-anonymous-constructor-vtable"])
        self.assertFalse(links[0]["anonymousParentVtableVerified"])
        self.assertTrue(links[1]["nestedPrimaryHeaderObserved"])
        self.assertNotIn((SCENE["buffer0"] + 0x68, 8), reader.reads)
        self.assertFalse(result["renderResourceLinksObserved"] or result["stableTwoSamples"])

    def test_66_unreadable_link_or_nested_header_preserves_failure_and_sibling(self):
        for address in (SCENE["buffer0"] + 0x68, NESTED_HEADERS[0]):
            with self.subTest(address=address):
                reader = linked_scene_fixture()
                del reader.segments[address]
                result = collect_resource_links(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertIn("complete readable span", result["reason"])
                links = result["samples"][0]["characterScene"]["renderSelector"]["resourceLinks"]
                self.assertEqual(links[0]["state"], "rejected")
                self.assertTrue(links[1]["nestedPrimaryHeaderObserved"])
                self.assertFalse(result["stableTwoSamples"] or result["renderResourceLinksObserved"])

    def test_67_null_parent_or_nested_reference_is_not_ready_without_null_read(self):
        for address in (SCENE["selector"] + 0x18, SCENE["buffer0"] + 0x68,
                        SCENE["selector"] + 0x20, SCENE["buffer1"] + 0x68):
            with self.subTest(address=address):
                reader = linked_scene_fixture(); reader.put(address, 0)
                result = collect_resource_links(reader)
                self.assertEqual(result["state"], "notReady")
                self.assertTrue(result["stableTwoSamples"])
                self.assertFalse(result["renderResourceLinksObserved"])
                self.assertFalse(any(at < 0x10000 for at, _ in reader.reads))
                self.assertFalse(result["renderedDescriptorVerified"] or result["appearanceApplicationVerified"])

    def test_68_nested_pointer_and_vtable_bounds_do_not_authorize_unknown_fields(self):
        for replacement in (1, 0x10003, 2**47):
            reader = linked_scene_fixture(); reader.put(SCENE["buffer0"] + 0x68, replacement)
            result = collect_resource_links(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["renderResourceLinksObserved"])
            self.assertFalse(any(at == replacement for at, _ in reader.reads))
        for vt in (0, BASE, BASE + LENGTH, 2**47):
            reader = linked_scene_fixture(); reader.put(NESTED_HEADERS[0], vt)
            result = collect_resource_links(reader)
            self.assertEqual(result["state"], "rejected")
            row = result["samples"][0]["characterScene"]["renderSelector"]["resourceLinks"][0]
            self.assertEqual(row["nestedVtablePointer"], hex(vt))
            self.assertEqual(row["failedChecks"], ["nested-vtable-main-image-bounds"])
            self.assertFalse(row["nestedPrimaryHeaderObserved"])
            self.assertNotIn((vt, 8), reader.reads)

    def test_69_link_header_three_independent_rereads_detect_mid_sample_drift(self):
        for address, replacement in ((SCENE["buffer0"], BASE + 0x99100),
                    (SCENE["buffer0"] + 0x68, NESTED_HEADERS[1]), (NESTED_HEADERS[0], BASE + 0x99100)):
            with self.subTest(address=address):
                reader = linked_scene_fixture(); original = reader.read
                def changing(at, size):
                    raw = original(at, size)
                    if at == address:
                        reader.put(address, replacement)
                    return raw
                reader.read = changing
                result = collect_resource_links(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertIn("interpreted fields changed", result["reason"])
                row = result["samples"][0]["characterScene"]["renderSelector"]["resourceLinks"][0]
                self.assertEqual(row["failedChecks"], ["stable-linked-header-bytes"])
                self.assertFalse(result["stableTwoSamples"] or result["renderResourceLinksObserved"])

    def test_70_nested_vtable_changes_between_samples_remain_unstable(self):
        reader = linked_scene_fixture()
        result = collect_resource_links(reader, lambda _: reader.put(NESTED_HEADERS[1], BASE + 0x99200))
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertFalse(result["stableTwoSamples"] or result["renderResourceLinksObserved"])

    def test_71_pair_and_control_owner_rereads_still_gate_link_observation(self):
        for address, replacement in ((SCENE["selector"] + 0x28, 0),
                (ADDR["manager"] + 0x50, ADDR["user"]),
                (ADDR["owner"] + 0x218, 1)):
            with self.subTest(address=address):
                reader = linked_scene_fixture(); original = reader.read; changed = False
                def changing(at, size):
                    nonlocal changed
                    raw = original(at, size)
                    if at == NESTED_HEADERS[1] and not changed:
                        changed = True
                        reader.put(address, replacement, "<B" if address == SCENE["selector"] + 0x28
                                   else "<I" if address == ADDR["owner"] + 0x218 else "<Q")
                    return raw
                reader.read = changing
                result = collect_resource_links(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertFalse(result["stableTwoSamples"] or result["renderResourceLinksObserved"])

    def test_72_link_code_pins_and_global_vtable_bounds_reject_before_any_heap_read(self):
        for rva in probe.RESOURCE_LINK_WINDOWS:
            reader = linked_scene_fixture(); reader.segments[BASE + rva][0] ^= 1
            result = collect_resource_links(reader)
            self.assertEqual(result["samples"], [])
            self.assertIn("code bytes", result["reason"])
        reader = linked_scene_fixture()
        with mock.patch.object(probe, "ANONYMOUS_RESOURCE_VTABLE", LENGTH):
            result = collect_resource_links(reader)
        self.assertEqual(result["samples"], [])
        self.assertEqual(reader.reads, [])
        reader = linked_scene_fixture()
        self.assertEqual(probe.collect(reader, BASE, 0x109DB74F + 9, lambda _: None,
                        render_resource_links=True)["samples"], [])

    def test_73_modes_cannot_accidentally_mix_rtti_with_anonymous_contract(self):
        reader = linked_scene_fixture()
        result = probe.collect(reader, BASE, LENGTH, lambda _: None,
                               render_resource_identities=True, render_resource_links=True)
        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["samples"], [])
        self.assertEqual(reader.reads, [])
        self.assertIn("independent", result["reason"])

    def test_74_final_peer_read_cannot_hide_prior_parent_link_change(self):
        reader = linked_scene_fixture(); original = probe.linked_resource_header
        calls = 0
        def changing(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 4:
                reader.put(SCENE["buffer0"] + 0x68, NESTED_HEADERS[1])
            return result
        with mock.patch.object(probe, "linked_resource_header", side_effect=changing):
            result = collect_resource_links(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("interpreted fields changed", result["reason"])
        self.assertFalse(result["renderResourceLinksObserved"] or result["stableTwoSamples"])

    def test_75_link_cli_final_module_or_digest_change_clears_link_success_and_closes_reader(self):
        for changed in ("module", "digest"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
                reader = linked_scene_fixture()
                exe, output = Path(temp) / "CrimsonDesert.exe", Path(temp) / "linked.json"
                reader.module = mock.Mock(side_effect=[(BASE, LENGTH, exe),
                    (BASE + (0x1000 if changed == "module" else 0), LENGTH, exe)])
                reader.close = mock.Mock()
                with mock.patch("sys.argv", ["probe", "--pid", "42123", "--render-resource-links", "--output", str(output)]), \
                        mock.patch.object(probe.core, "Reader", return_value=reader), \
                        mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION), \
                        mock.patch.object(probe, "file_digest", side_effect=[probe.roster.SHA256,
                            probe.roster.SHA256 if changed == "module" else "0" * 64]), \
                        mock.patch("builtins.print"):
                    self.assertEqual(probe.main(), 1)
                report = json.loads(output.read_bytes())
                self.assertEqual(report["state"], "unstable")
                self.assertFalse(report["renderResourceLinksObserved"] or report["stableTwoSamples"])
                self.assertTrue(report["samples"][0]["characterScene"]["renderResourceLinksObserved"])
                self.assertEqual(report["source"]["staticChainRvas"], [hex(x) for x in {**probe.CODE_WINDOWS, **probe.RESOURCE_LINK_WINDOWS}])
                reader.close.assert_called_once()

    def test_76_cli_rejects_two_modes_before_opening_any_process(self):
        with mock.patch("sys.argv", ["probe", "--render-resource-links", "--render-resource-identities"]), \
                mock.patch.object(probe.core, "Reader") as open_reader, \
                mock.patch.object(probe.subprocess, "check_output") as command, \
                mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                probe.main()
            self.assertEqual(error.exception.code, 2)
            open_reader.assert_not_called()
            command.assert_not_called()


    def test_77_declared_inputs_have_exact_owner_paths_and_no_rendered_equivalence(self):
        reader = input_path_scene_fixture()
        result = collect_input_paths(reader)
        self.assertEqual((result["schemaVersion"], result["state"]), (7, "observed"))
        self.assertTrue(result["renderInputPathsRequested"] and result["renderInputPathsObserved"]
                        and result["stableTwoSamples"])
        self.assertEqual(result["samples"][0], result["samples"][1])
        for sample in result["samples"]:
            info = sample["characterScene"]["renderInputPaths"]
            self.assertEqual(info["state"], "observed")
            for row, expected in zip(info["inputs"], INPUT_PATHS):
                self.assertEqual(row["path"], expected["text"])
                self.assertTrue(row["propertyIdentityVerified"] and row["directOwnerRoundTripObserved"]
                                and row["declaredPathObserved"] and row["nulTerminated"])
                self.assertEqual(row["pathBytesIncludingNulHex"], (expected["text"].encode() + b"\0").hex())
                self.assertEqual(row["bytesRead"], len(expected["text"]) + 1)
                self.assertTrue(row["extensionMatchesNativeInput"])
            self.assertFalse(info["selectedRenderResourceEquivalenceVerified"])
            self.assertFalse(sample["characterScene"]["renderSelector"]["selectedResourceDereferenced"])
        for row in INPUT_PATHS:
            prop, holder, chars = row["property"], row["holder"], row["chars"]
            self.assertEqual({(at, size) for at, size in reader.reads if prop <= at < prop + 0x38},
                             {(prop, 8), (prop + 0x10, 8), (prop + 0x1A, 1), (prop + 0x28, 8)})
            self.assertEqual({(at, size) for at, size in reader.reads if holder <= at < holder + 0x38}, {(holder, 8)})
            reads = {(at, size) for at, size in reader.reads if chars <= at < chars + 512}
            self.assertEqual(reads, {(chars + i, 1) for i in range(len(row["text"]) + 1)})
        self.assertFalse(any(SCENE["buffer0"] <= at < SCENE["buffer1"] + 0x1000 for at, _ in reader.reads))
        for flag in ("renderResourceLinksObserved", "renderResourceIdentitiesObserved", "renderedDescriptorVerified",
                     "nativeFunctionsInvoked", "gameMemoryWritten", "appearanceApplicationVerified",
                     "appearanceRestoreVerified", "steveModelLoaded"):
            self.assertIs(result[flag], False, flag)

    def test_78_default_does_not_read_declared_input_fields_or_extra_pins(self):
        reader = input_path_scene_fixture()
        result = collect(reader)
        self.assertEqual((result["schemaVersion"], result["state"]), (4, "observed"))
        self.assertFalse(result["renderInputPathsRequested"] or result["renderInputPathsObserved"]
                         or result["initialAppearanceInputObserved"])
        self.assertNotIn("renderInputPaths", result["samples"][0]["characterScene"])
        excluded = {BASE + rva for rva in probe.INPUT_PATH_WINDOWS}
        excluded.update((0x220000 + 0xD8, 0x220000 + 0xE8, 0x220000 + probe.INITIAL_APPEARANCE_INPUT_OFFSET))
        self.assertFalse(any(at in excluded or 0x240000 <= at < 0x248000 for at, _ in reader.reads))

    def test_79_unknown_property_vtable_stops_its_fields_and_retains_peer(self):
        reader = input_path_scene_fixture(); prop = INPUT_PATHS[0]["property"]
        reader.put(prop, BASE + probe.RENDER_INPUT_PROPERTIES["pac"][1] + 8)
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        rows = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"]
        self.assertEqual(rows[0]["failedChecks"], ["exact-declared-property-constructor-vtable"])
        self.assertTrue(rows[1]["declaredPathObserved"])
        self.assertFalse(any(prop < at < prop + 0x38 for at, _ in reader.reads))
        self.assertFalse(result["renderInputPathsObserved"] or result["stableTwoSamples"])

    def test_80_weak_owner_and_wrong_direct_owner_stop_before_string_holder(self):
        for weak in (False, True):
            with self.subTest(weak=weak):
                reader = input_path_scene_fixture(); prop = INPUT_PATHS[0]["property"]
                reader.put(prop + (0x1A if weak else 0x10), 8 if weak else ADDR["owner"], "<B" if weak else "<Q")
                result = collect_input_paths(reader)
                self.assertEqual(result["state"], "rejected")
                row = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"][0]
                self.assertEqual(row["failedChecks"], ["direct-property-owner-required" if weak
                                 else "exact-Skinned-property-owner-backlink"])
                self.assertNotIn((prop + 0x28, 8), reader.reads)
                if weak:
                    self.assertNotIn((prop + 0x10, 8), reader.reads)
                self.assertFalse(result["renderInputPathsObserved"] or result["stableTwoSamples"])

    def test_81_absent_property_holder_chars_or_empty_input_is_not_ready(self):
        first = INPUT_PATHS[0]
        for absent in ("property", "holder", "chars", "text"):
            with self.subTest(absent=absent):
                reader = input_path_scene_fixture()
                if absent == "property": reader.put(0x220000 + 0xD8, 0)
                elif absent == "holder": reader.put(first["property"] + 0x28, 0)
                elif absent == "chars": reader.put(first["holder"], 0)
                else: reader.segments[first["chars"]][:] = b"\0"
                result = collect_input_paths(reader)
                self.assertEqual(result["state"], "notReady")
                self.assertTrue(result["stableTwoSamples"])
                self.assertFalse(result["renderInputPathsObserved"])
                rows = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"]
                self.assertFalse(rows[0]["declaredPathObserved"])
                self.assertTrue(rows[1]["declaredPathObserved"])
                self.assertFalse(any(at < 0x10000 for at, _ in reader.reads))

    def test_82_property_holder_alignment_and_character_byte_bounds(self):
        for field in (0x220000 + 0xD8, INPUT_PATHS[0]["property"] + 0x28):
            for invalid in (1, 0x10003, 2**47):
                reader = input_path_scene_fixture(); reader.put(field, invalid)
                result = collect_input_paths(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertNotIn((invalid, 8), reader.reads)
        for invalid in (1, 2**47):
            reader = input_path_scene_fixture(); reader.put(INPUT_PATHS[0]["holder"], invalid)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            row = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"][0]
            self.assertEqual(row["failedChecks"], ["character-byte-address-bounds"])
            self.assertNotIn((invalid, 1), reader.reads)
        # The successful fixture deliberately uses two unaligned char pointers.
        self.assertEqual(collect_input_paths(input_path_scene_fixture())["state"], "observed")

    def test_83_string_read_is_bounded_terminated_printable_and_complete(self):
        first = INPUT_PATHS[0]; chars = first["chars"]
        for raw, expected in ((b"x" * 512, "bounded-NUL-termination"),
                              (b"x\x01\0", "printable-ASCII-declared-input"),
                              (b"x\xff\0", "printable-ASCII-declared-input")):
            reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(raw)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            row = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"][0]
            self.assertEqual(row["failedChecks"], [expected])
            self.assertFalse(row["declaredPathObserved"] or result["renderInputPathsObserved"])
            self.assertNotIn((chars + 512, 1), reader.reads)
        reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(b"x" * 511 + b"\0")
        self.assertEqual(collect_input_paths(reader)["state"], "observed")
        reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(b"x")
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("complete readable span", result["reason"])

    def test_84_all_interpreted_property_fields_are_reread(self):
        row = INPUT_PATHS[0]
        for address, replacement, fmt in ((0x220000 + 0xD8, INPUT_PATHS[1]["property"], "<Q"),
                (row["property"], BASE + probe.RENDER_INPUT_PROPERTIES["pab"][1], "<Q"),
                (row["property"] + 0x10, ADDR["owner"], "<Q"),
                (row["property"] + 0x1A, 8, "<B"),
                (row["property"] + 0x28, INPUT_PATHS[1]["holder"], "<Q"),
                (row["holder"], INPUT_PATHS[1]["chars"], "<Q")):
            with self.subTest(address=address):
                reader = input_path_scene_fixture(); original = reader.read; changed = False
                def changing(at, size):
                    nonlocal changed
                    raw = original(at, size)
                    if at == address and not changed:
                        changed = True; reader.put(address, replacement, fmt)
                    return raw
                reader.read = changing
                result = collect_input_paths(reader)
                self.assertEqual(result["state"], "rejected")
                self.assertIn("interpreted fields changed", result["reason"])
                self.assertFalse(result["stableTwoSamples"] or result["renderInputPathsObserved"])

    def test_85_path_and_nul_bytes_reread_after_peer_detect_late_mutation(self):
        first, second = INPUT_PATHS
        for offset in (0, len(first["text"])):
            reader = input_path_scene_fixture(); original = reader.read; changed = False
            def changing(at, size):
                nonlocal changed
                raw = original(at, size)
                if at == second["chars"] + len(second["text"]) and not changed:
                    changed = True; reader.segments[first["chars"]][offset] = ord("X")
                return raw
            reader.read = changing
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertIn("interpreted fields changed", result["reason"])
            self.assertFalse(result["renderInputPathsObserved"] or result["stableTwoSamples"])

    def test_86_declared_input_changes_between_samples_are_unstable(self):
        reader = input_path_scene_fixture()
        result = collect_input_paths(reader, lambda _: reader.segments[INPUT_PATHS[1]["chars"]].__setitem__(0, ord("X")))
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertNotEqual(result["samples"][0], result["samples"][1])
        self.assertFalse(result["renderInputPathsObserved"] or result["stableTwoSamples"])

    def test_87_exact_skinned_type_remains_required_before_any_input_read(self):
        reader = input_path_scene_fixture()
        reader.put(SCENE["renderWeak"] + 8, ADDR["owner"] + 0x28)
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertIn("exact SkinnedMeshComponent", result["reason"])
        self.assertFalse(any(at in (ADDR["owner"] + 0xD8, ADDR["owner"] + 0xE8)
                             or 0x240000 <= at < 0x246000 for at, _ in reader.reads))

    def test_88_full_controlled_scene_owner_rechecks_gate_input_observation(self):
        for address, replacement, fmt in ((ADDR["manager"] + 0x50, ADDR["user"], "<Q"),
                (SCENE["ownerWeak"] + 8, ADDR["actor"] + 0x28, "<Q"),
                (ADDR["owner"] + 0x218, 1, "<I")):
            reader = input_path_scene_fixture(); original = reader.read; changed = False
            def changing(at, size):
                nonlocal changed
                raw = original(at, size)
                if at == INPUT_PATHS[1]["chars"] + len(INPUT_PATHS[1]["text"]) and not changed:
                    changed = True; reader.put(address, replacement, fmt)
                return raw
            reader.read = changing
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertFalse(result["stableTwoSamples"] or result["renderInputPathsObserved"])

    def test_89_input_pins_and_property_vtable_image_bounds_fail_before_heap_reads(self):
        for rva in probe.INPUT_PATH_WINDOWS:
            reader = input_path_scene_fixture(); reader.segments[BASE + rva][0] ^= 1
            result = collect_input_paths(reader)
            self.assertEqual(result["samples"], [])
            self.assertIn("code bytes", result["reason"])
        reader = input_path_scene_fixture()
        with mock.patch.object(probe, "RENDER_INPUT_PROPERTIES", {"pac": (0xD8, LENGTH), "pab": (0xE8, LENGTH)}):
            result = collect_input_paths(reader)
        self.assertEqual(result["samples"], [])
        self.assertEqual(reader.reads, [])

    def test_90_three_modes_are_pairwise_exclusive_before_any_read_or_process(self):
        flags = ("--render-resource-identities", "--render-resource-links", "--render-input-paths")
        for index, first in enumerate(flags):
            for second in flags[index + 1:]:
                kwargs = {first[2:].replace("-", "_"): True, second[2:].replace("-", "_"): True}
                reader = input_path_scene_fixture()
                result = probe.collect(reader, BASE, LENGTH, lambda _: None, **kwargs)
                self.assertEqual(result["state"], "rejected")
                self.assertEqual(result["samples"], [])
                self.assertEqual(reader.reads, [])
                with mock.patch("sys.argv", ["probe", first, second]), \
                        mock.patch.object(probe.core, "Reader") as open_reader, \
                        mock.patch.object(probe.subprocess, "check_output") as command, mock.patch("sys.stderr"):
                    with self.assertRaises(SystemExit) as error: probe.main()
                    self.assertEqual(error.exception.code, 2)
                    open_reader.assert_not_called(); command.assert_not_called()

    def test_91_input_cli_module_digest_change_clears_flag_and_preserves_original_samples(self):
        for changed in ("module", "digest"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=probe.ROOT / "runtime") as temp:
                reader = input_path_scene_fixture()
                exe, output = Path(temp) / "CrimsonDesert.exe", Path(temp) / "paths.json"
                reader.module = mock.Mock(side_effect=[(BASE, LENGTH, exe),
                    (BASE + (0x1000 if changed == "module" else 0), LENGTH, exe)])
                reader.close = mock.Mock()
                with mock.patch("sys.argv", ["probe", "--pid", "42123", "--render-input-paths", "--output", str(output)]), \
                        mock.patch.object(probe.core, "Reader", return_value=reader), \
                        mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION), \
                        mock.patch.object(probe, "file_digest", side_effect=[probe.roster.SHA256,
                            probe.roster.SHA256 if changed == "module" else "0" * 64]), mock.patch("builtins.print"):
                    self.assertEqual(probe.main(), 1)
                report = json.loads(output.read_bytes())
                self.assertEqual(report["state"], "unstable")
                self.assertFalse(report["renderInputPathsObserved"] or report["stableTwoSamples"]
                                 or report["initialAppearanceInputObserved"])
                self.assertTrue(report["samples"][0]["characterScene"]["renderInputPathsObserved"])
                self.assertEqual(report["source"]["staticChainRvas"], [hex(x) for x in probe.code_windows(render_input_paths=True)])
                reader.close.assert_called_once()

    def test_92_declared_path_content_is_reported_without_selected_type_or_suffix_guess(self):
        reader = input_path_scene_fixture(); chars = INPUT_PATHS[0]["chars"]
        reader.segments[chars] = bytearray(b"synthetic/declared.input\0")
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "observed")
        row = result["samples"][0]["characterScene"]["renderInputPaths"]["inputs"][0]
        self.assertEqual(row["path"], "synthetic/declared.input")
        self.assertFalse(row["extensionMatchesNativeInput"])
        self.assertFalse(result["renderedDescriptorVerified"] or result["appearanceApplicationVerified"])

    def test_93_missing_base_scene_fields_cannot_promote_complete_input_paths(self):
        for field in (SCENE["scene"] + 0xA0, 0x220000 + 0xA8, SCENE["scene"] + 0x78):
            reader = input_path_scene_fixture(); reader.put(field, 0)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "notReady")
            self.assertFalse(result["renderInputPathsObserved"] or result["initialAppearanceInputObserved"])

    def test_94_initial_appearance_key_has_only_producer_proven_reads_and_no_render_claim(self):
        reader = input_path_scene_fixture(); expected = INITIAL_APPEARANCE_PATH
        result = collect_input_paths(reader)
        self.assertEqual((result["schemaVersion"], result["state"]), (7, "observed"))
        self.assertTrue(result["initialAppearanceInputObserved"] and result["stableTwoSamples"])
        for sample in result["samples"]:
            row = sample["characterScene"]["renderInputPaths"]["initialAppearanceInput"]
            self.assertEqual((row["componentOffset"], row["path"]), ("0x168", expected["text"]))
            self.assertTrue(row["initialAppearanceInputObserved"] and row["nulTerminated"])
            self.assertEqual(row["pathBytesIncludingNulHex"], (expected["text"].encode() + b"\0").hex())
            self.assertEqual(row["bytesRead"], len(expected["text"]) + 1)
            for flag in ("loadedAppearanceResourceVerified", "selectedRenderResourceEquivalenceVerified",
                         "renderedDescriptorVerified", "appearanceApplicationVerified"):
                self.assertIs(row[flag], False)
        holder, chars = expected["holder"], expected["chars"]
        self.assertIn((0x220000 + 0x168, 8), reader.reads)
        self.assertEqual({(at, size) for at, size in reader.reads if holder <= at < holder + 0x40}, {(holder, 8)})
        self.assertEqual({(at, size) for at, size in reader.reads if chars <= at < chars + 512},
                         {(chars + i, 1) for i in range(len(expected["text"]) + 1)})
        self.assertFalse(result["renderedDescriptorVerified"] or result["steveModelLoaded"])
        self.assertTrue(probe.summary(result, Path("synthetic.json"))["initialAppearanceInputObserved"])

    def test_95_initial_key_observation_survives_empty_declared_pac_without_promoting_mode(self):
        reader = input_path_scene_fixture()
        reader.segments[INPUT_PATHS[0]["chars"]][:] = b"\0"
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "notReady")
        self.assertTrue(result["stableTwoSamples"] and result["initialAppearanceInputObserved"])
        self.assertFalse(result["renderInputPathsObserved"] or result["renderedDescriptorVerified"])
        self.assertEqual(result["samples"][0]["characterScene"]["renderInputPaths"][
            "initialAppearanceInput"]["path"], INITIAL_APPEARANCE_PATH["text"])

    def test_96_absent_initial_holder_chars_or_empty_key_preserves_not_ready(self):
        for absent in ("holder", "chars", "text"):
            with self.subTest(absent=absent):
                reader = input_path_scene_fixture(); row = INITIAL_APPEARANCE_PATH
                if absent == "holder": reader.put(0x220000 + 0x168, 0)
                elif absent == "chars": reader.put(row["holder"], 0)
                else: reader.segments[row["chars"]][:] = b"\0"
                result = collect_input_paths(reader)
                self.assertEqual(result["state"], "notReady")
                self.assertTrue(result["stableTwoSamples"])
                self.assertFalse(result["initialAppearanceInputObserved"] or result["renderInputPathsObserved"])
                evidence = result["samples"][0]["characterScene"]["renderInputPaths"]
                self.assertTrue(all(item["declaredPathObserved"] for item in evidence["inputs"]))
                self.assertEqual(evidence["initialAppearanceInput"]["state"], "notReady")
                self.assertFalse(any(at < 0x10000 for at, _ in reader.reads))

    def test_97_initial_holder_and_character_pointer_bounds_fail_closed(self):
        row = INITIAL_APPEARANCE_PATH
        for invalid in (1, 0x10003, 2**47):
            reader = input_path_scene_fixture(); reader.put(0x220000 + 0x168, invalid)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertNotIn((invalid, 8), reader.reads)
            self.assertFalse(result["initialAppearanceInputObserved"] or result["stableTwoSamples"])
        for invalid in (1, 2**47):
            reader = input_path_scene_fixture(); reader.put(row["holder"], invalid)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            evidence = result["samples"][0]["characterScene"]["renderInputPaths"]["initialAppearanceInput"]
            self.assertEqual(evidence["failedChecks"], ["character-byte-address-bounds"])
            self.assertNotIn((invalid, 1), reader.reads)

    def test_98_initial_key_termination_ascii_and_byte_span_are_bounded(self):
        row = INITIAL_APPEARANCE_PATH; chars = row["chars"]
        for raw, failure in ((b"x" * 512, "bounded-NUL-termination"),
                             (b"x\xff\0", "printable-ASCII-initial-Appearance-input"),
                             (b"x\x01\0", "printable-ASCII-initial-Appearance-input")):
            reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(raw)
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            evidence = result["samples"][0]["characterScene"]["renderInputPaths"]["initialAppearanceInput"]
            self.assertEqual(evidence["failedChecks"], [failure])
            self.assertFalse(result["initialAppearanceInputObserved"] or result["renderInputPathsObserved"])
            self.assertNotIn((chars + 512, 1), reader.reads)
        reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(b"x" * 511 + b"\0")
        self.assertEqual(collect_input_paths(reader)["state"], "observed")
        reader = input_path_scene_fixture(); reader.segments[chars] = bytearray(b"x")
        self.assertIn("complete readable span", collect_input_paths(reader)["reason"])
        reader = input_path_scene_fixture(); reader.put(row["holder"], 2**47 - 1)
        reader.segments[2**47 - 1] = bytearray(b"x")
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertNotIn((2**47, 1), reader.reads)

    def test_99_initial_held_pointer_and_character_pointer_are_reread(self):
        for field, replacement in ((0x220000 + 0x168, INPUT_PATHS[0]["holder"]),
                                   (INITIAL_APPEARANCE_PATH["holder"], INPUT_PATHS[0]["chars"])):
            reader = input_path_scene_fixture(); original = reader.read; changed = False
            def changing(at, size):
                nonlocal changed
                raw = original(at, size)
                if at == field and not changed:
                    changed = True; reader.put(field, replacement)
                return raw
            reader.read = changing
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertIn("interpreted fields changed", result["reason"])
            self.assertFalse(result["initialAppearanceInputObserved"] or result["stableTwoSamples"])

    def test_100_initial_characters_and_nul_are_reread_before_promotion(self):
        row = INITIAL_APPEARANCE_PATH
        for offset in (0, len(row["text"])):
            reader = input_path_scene_fixture(); original = reader.read; changed = False
            def changing(at, size):
                nonlocal changed
                raw = original(at, size)
                if at == row["chars"] + len(row["text"]) and not changed:
                    changed = True; reader.segments[row["chars"]][offset] = ord("X")
                return raw
            reader.read = changing
            result = collect_input_paths(reader)
            self.assertEqual(result["state"], "rejected")
            self.assertIn("interpreted fields changed", result["reason"])
            self.assertFalse(result["initialAppearanceInputObserved"] or result["stableTwoSamples"])

    def test_101_initial_key_change_between_samples_stays_unstable(self):
        reader = input_path_scene_fixture()
        result = collect_input_paths(reader, lambda _: reader.segments[INITIAL_APPEARANCE_PATH[
            "chars"]].__setitem__(0, ord("X")))
        self.assertEqual(result["state"], "unstable")
        self.assertEqual(len(result["samples"]), 2)
        self.assertFalse(result["initialAppearanceInputObserved"] or result["stableTwoSamples"])
        self.assertNotEqual(result["samples"][0], result["samples"][1])

    def test_102_initial_key_never_relaxes_type_control_or_content_contracts(self):
        reader = input_path_scene_fixture()
        reader.put(SCENE["renderWeak"] + 8, ADDR["owner"] + 0x28)
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertNotIn((ADDR["owner"] + 0x168, 8), reader.reads)
        self.assertFalse(any(INITIAL_APPEARANCE_PATH["holder"] <= at < 0x248000 for at, _ in reader.reads))
        reader = input_path_scene_fixture()
        reader.segments[INITIAL_APPEARANCE_PATH["chars"]] = bytearray(b"synthetic/opaque.input-key\0")
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "observed")
        evidence = result["samples"][0]["characterScene"]["renderInputPaths"]["initialAppearanceInput"]
        self.assertEqual(evidence["path"], "synthetic/opaque.input-key")
        self.assertNotIn("expectedNativeExtension", evidence)
        self.assertFalse(evidence["loadedAppearanceResourceVerified"])

    def test_103_initial_key_late_control_owner_change_prevents_success(self):
        reader = input_path_scene_fixture(); original = reader.read; changed = False
        row = INITIAL_APPEARANCE_PATH
        def changing(at, size):
            nonlocal changed
            raw = original(at, size)
            if at == row["chars"] + len(row["text"]) and not changed:
                changed = True; reader.put(SCENE["ownerWeak"] + 8, ADDR["actor"] + 0x28)
            return raw
        reader.read = changing
        result = collect_input_paths(reader)
        self.assertEqual(result["state"], "rejected")
        self.assertFalse(result["initialAppearanceInputObserved"] or result["stableTwoSamples"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
