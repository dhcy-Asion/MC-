"""Pure complete-chain fixtures; never opens a process or calls a native API."""
from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import check_appearance_controller as old_checks
import probe_owner_skinned_object as probe

BASE, LENGTH = old_checks.BASE, old_checks.LENGTH
ADDR, SCENE = old_checks.ADDR, old_checks.SCENE
SKINNED, SKINNED_WEAK, CANDIDATE, CANDIDATE_WEAK = 0x220000, 0x250000, 0x251000, 0x252000


def identity(**changes):
    return {"pid": 43210, "creationTime100ns": "1234567890123456", "moduleBase": BASE,
            "moduleSize": LENGTH, "imagePath": "synthetic/CrimsonDesert.exe", **changes}


def fixture(count=2):
    reader = old_checks.skinned_scene_fixture()
    # The original fixture's name map is insufficient for this stronger full
    # byte watch. Materialize each known primary RTTI name in synthetic memory.
    for address, name in reader.names.items():
        vt = reader.value(address)
        col = reader.value(vt - 8)
        desc = struct.unpack_from("<6I", reader.read(col, 24))[3]
        reader.block(BASE + desc + 16, probe.owner_probe.MAX_RTTI_BYTES)
        token = name.encode("ascii") + b"\0"
        reader.segments[BASE + desc + 16][:len(token)] = token
    for rva, raw in probe.WINDOWS:
        reader.segments[BASE + rva] = bytearray(raw)
    reader.put(BASE + probe.CONTEXT_VTABLE, BASE + probe.CONTEXT_PRIMARY_SLOT_ZERO)
    for address in (SKINNED_WEAK, CANDIDATE_WEAK):
        reader.block(address, 16)
        reader.put(address + 8, ADDR["owner"] + 0x28)
    reader.put(SKINNED + 0x60, SKINNED_WEAK)
    reader.put(SKINNED + 0x1C0, CANDIDATE)
    # Exactly 64 candidate bytes. Any child/queue/array interpretation fails.
    reader.block(CANDIDATE, probe.CONTEXT_HEADER_BYTES)
    reader.put(CANDIDATE, BASE + probe.CONTEXT_VTABLE)
    reader.put(CANDIDATE + 0x15, 0, "<B")
    reader.put(CANDIDATE + 0x30, CANDIDATE_WEAK)
    reader.put(CANDIDATE + 0x38, ADDR["owner"])
    reader.put(ADDR["owner"] + 0x218, count, "<I")
    reader.put(ADDR["owner"] + 0x21C, max(count, 2), "<I")
    if count > 2:
        reader.block(ADDR["members"], count * 8)
        reader.put(ADDR["members"], ADDR["controller"])
        reader.put(ADDR["members"] + 8, SCENE["scene"])
        for index in range(2, count):
            address = 0x300000 + index * 0x1000
            reader.put(address, BASE + 0x100000 + index * 8)
            reader.put(ADDR["members"] + index * 8, address)
    reader.rtti = mock.Mock(side_effect=AssertionError("Unwatched RTTI is forbidden"))
    reader.module = mock.Mock(return_value=(BASE, LENGTH, Path("synthetic/CrimsonDesert.exe")))
    reader.handle, reader.close = 12345, mock.Mock()
    reader.reads.clear()
    return reader


class OwnerSkinnedObjectChecks(unittest.TestCase):
    def setUp(self):
        for target, field in ((probe.core, "Reader"), (probe, "process_identity"),
                              (probe.core, "scan"), (probe.subprocess, "check_output")):
            guard = mock.patch.object(target, field, side_effect=AssertionError("Live process/API forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def collect(self, reader, *, pause=lambda _: None, identities=None, base=BASE, length=LENGTH):
        callback = mock.Mock(side_effect=identities) if identities is not None else lambda: identity()
        return probe.collect(reader, base, length, identity=callback, pause=pause)

    def rejected(self, report):
        self.assertNotEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(all(report[key] is False for key in (*probe.SUCCESS_FLAGS, *probe.UNVERIFIED_FLAGS)))
        def no_successes(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if type(item) is bool and (key.endswith(("Observed", "Verified", "Passed")) or key == "stableDuringSample"):
                        self.assertFalse(item, key)
                    else:
                        no_successes(item)
            elif isinstance(value, list):
                for item in value:
                    no_successes(item)
        for sample in report["samples"]:
            no_successes(sample)
            self.assertFalse(sample["stableDuringSample"])
            if "candidate" in sample:
                self.assertFalse(sample["candidate"]["candidateConstructorIdentityObserved"])
                self.assertFalse(sample["candidate"]["candidateOwnerRoundTripsObserved"])

    def test_01_complete_chain_and_exact97_bytes_observe_identity_only(self):
        reader = fixture()
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(all(report[key] for key in probe.SUCCESS_FLAGS))
        self.assertTrue(all(report[key] is False for key in probe.UNVERIFIED_FLAGS))
        self.assertEqual(report["samples"][0], report["samples"][1])
        row = report["samples"][0]
        self.assertEqual(row["newSemanticReadBytes"], 97)
        self.assertEqual([span["size"] for span in row["newReadSpans"]], [8, 8, 1, 8, 64, 8])
        self.assertEqual(row["candidate"]["interpretedHeaderOffsets"], ["0x0", "0x15", "0x30", "0x38"])
        self.assertFalse(row["candidate"]["primaryRttiVerified"])
        self.assertEqual(set((at, size) for at, size in reader.reads if CANDIDATE <= at < CANDIDATE + 0x1000), {(CANDIDATE, 64)})
        self.assertEqual(reader.reads.count((CANDIDATE, 64)), 4)
        self.assertNotIn((BASE + probe.CONTEXT_VTABLE - 8, 8), reader.reads)
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))
        reader.rtti.assert_not_called()

    def test_02_actual_rtti_bytes_and_primary_constructor_displacement_gate(self):
        for mode in ("name", "constructor-displacement"):
            reader = fixture()
            vt = reader.value(ADDR["owner"])
            col = reader.value(vt - 8)
            if mode == "name":
                desc = struct.unpack_from("<6I", reader.read(col, 24))[3]
                reader.segments[BASE + desc + 16][0] = ord("X")
            else:
                reader.put(col + 8, 1, "<I")
            reader.reads.clear()
            self.rejected(self.collect(reader))
            self.assertNotIn((SKINNED + 0x1C0, 8), reader.reads)
        reader = fixture()
        reader.names.clear()  # Names are obtained from the watched bytes only.
        self.assertEqual(self.collect(reader)["state"], "observed")

    def test_03_all_eleven_code_windows_and_primary_slot_zero_are_early_gates(self):
        for rva, _ in probe.WINDOWS:
            reader = fixture()
            reader.segments[BASE + rva][0] ^= 1
            report = self.collect(reader)
            self.rejected(report)
            self.assertEqual(report["samples"], [])
            self.assertFalse(any(at < BASE for at, _ in reader.reads))
        reader = fixture()
        reader.put(BASE + probe.CONTEXT_VTABLE, BASE + probe.CONTEXT_PRIMARY_SLOT_ZERO + 8)
        self.rejected(self.collect(reader))
        self.assertFalse(any(at < BASE for at, _ in reader.reads))

    def test_04_final_code_reread_clears_both_complete_samples(self):
        reader = fixture()
        rva, _ = probe.WINDOWS[0]
        report = self.collect(reader, pause=lambda _: reader.segments[BASE + rva].__setitem__(0, 0))
        self.rejected(report)
        self.assertEqual(report["state"], "unstable")
        self.assertEqual(len(report["samples"]), 2)

    def test_05_missing_duplicate_or_non_skinned_scene_has_no_candidate_fallback(self):
        for mode in ("missing-scene", "duplicate-scene", "owner-render", "unknown-render"):
            reader = fixture()
            if mode == "missing-scene":
                reader.put(ADDR["members"] + 8, ADDR["controller"])
            elif mode == "duplicate-scene":
                reader.put(ADDR["owner"] + 0x218, 3, "<I")
                reader.put(ADDR["owner"] + 0x21C, 3, "<I")
                reader.put(ADDR["members"] + 16, SCENE["scene"])
            elif mode == "owner-render":
                reader.put(SCENE["renderWeak"] + 8, ADDR["owner"] + 0x28)
            else:
                reader.put(SKINNED, BASE + 0xFFFFFF)
            report = self.collect(reader)
            self.rejected(report)
            self.assertFalse(any(at == CANDIDATE for at, _ in reader.reads))

    def test_06_empty_selectors_and_options_do_not_select_another_owner(self):
        reader = fixture()
        reader.put(SKINNED + 0xA8, 0)
        for offset in (0xA0, 0xB0):
            reader.put(ADDR["controller"] + offset + 8, 0, "<I")
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertEqual(report["samples"][0]["candidate"]["directOwnerPointer"], hex(ADDR["owner"]))

    def test_07_skinned_owner_link_empty_wrong_and_invalid_refuse_early(self):
        for at, value, fmt in ((SKINNED + 0x60, 0, "<Q"), (SKINNED_WEAK + 8, 0, "<Q"),
                              (SKINNED_WEAK + 8, 0x700000, "<Q"),
                              (ADDR["owner"] + 0x3D, 1, "<B")):
            reader = fixture()
            reader.put(at, value, fmt)
            self.rejected(self.collect(reader))
            self.assertNotIn((SKINNED + 0x1C0, 8), reader.reads)
            self.assertFalse(any(0x700000 <= pos < 0x701000 for pos, _ in reader.reads))

    def test_08_candidate_pointer_and_complete_header_bounds_have_no_fallback(self):
        for value in (0, CANDIDATE + 1, 2**47, 0x700000):
            reader = fixture()
            reader.put(SKINNED + 0x1C0, value)
            self.rejected(self.collect(reader))
            reader.rtti.assert_not_called()
        reader = fixture()
        reader.segments[CANDIDATE] = reader.segments[CANDIDATE][:-1]
        report = self.collect(reader)
        self.rejected(report)
        self.assertNotIn((CANDIDATE_WEAK + 8, 8), reader.reads)

    def test_09_wrong_vtable_invalidation_direct_owner_or_weak_holder_refuse(self):
        for at, value, fmt in ((CANDIDATE, BASE + probe.CONTEXT_VTABLE + 8, "<Q"),
                              (CANDIDATE + 0x15, 1, "<B"), (CANDIDATE + 0x38, 0x700000, "<Q"),
                              (CANDIDATE + 0x30, 0, "<Q"), (CANDIDATE + 0x30, CANDIDATE_WEAK + 1, "<Q")):
            reader = fixture()
            reader.put(at, value, fmt)
            self.rejected(self.collect(reader))
            self.assertNotIn((CANDIDATE_WEAK + 8, 8), reader.reads)

    def test_10_wrong_candidate_weak_target_never_dereferences_unknown_owner(self):
        for value in (0, ADDR["owner"] + 0x30, 0x700000):
            reader = fixture()
            reader.put(CANDIDATE_WEAK + 8, value)
            report = self.collect(reader)
            self.rejected(report)
            if value:
                self.assertNotIn("targetFlag15", report["samples"][0]["candidate"].get("weakOwner", {}))
            self.assertFalse(any(0x700000 <= pos < 0x701000 for pos, _ in reader.reads))

    def test_11_uninterpreted_header_fields_are_only_raw_bytes(self):
        reader = fixture()
        reader.segments[CANDIDATE][8:0x15] = b"opaque-fields"
        reader.segments[CANDIDATE][0x18:0x30] = bytes(range(24))
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertEqual(report["samples"][0]["candidate"]["raw40Hex"], bytes(reader.segments[CANDIDATE]).hex())
        self.assertNotIn("referenceCount", report["samples"][0]["candidate"])

    def test_12_semantic_budget_rejects_before_extra_io(self):
        watch = mock.Mock()
        watch.get.side_effect = lambda at, size, label: bytes(size)
        fields = probe.NewFields(watch, {})
        fields.get(CANDIDATE, 64, "header")
        with self.assertRaises(probe.ProbeError):
            fields.get(CANDIDATE + 64, 34, "unadmitted suffix")
        self.assertEqual(watch.get.call_count, 1)
        self.assertEqual(fields.total, 64)

    def test_13_cross_sample_raw_byte_and_candidate_replacements_reject(self):
        for mode in ("raw", "candidate"):
            reader = fixture()
            def change(_):
                if mode == "raw":
                    reader.segments[CANDIDATE][0x18] ^= 1
                else:
                    reader.segments[CANDIDATE + 0x100000] = bytearray(reader.segments[CANDIDATE])
                    reader.put(SKINNED + 0x1C0, CANDIDATE + 0x100000)
            report = self.collect(reader, pause=change)
            self.rejected(report)
            self.assertEqual(report["state"], "unstable")

    def test_14_old_rtti_parameter_header_and_ordered_members_are_final_dependencies(self):
        for mode in ("rtti", "parameter", "members"):
            reader = fixture()
            original, changed = reader.read, False
            vt = reader.value(ADDR["manager"])
            col = reader.value(vt - 8)
            name = BASE + struct.unpack_from("<6I", reader.read(col, 24))[3] + 16
            def reading(at, size):
                nonlocal changed
                result = original(at, size)
                if not changed and (at, size) == (CANDIDATE_WEAK + 8, 8):
                    changed = True
                    if mode == "rtti":
                        reader.segments[name][8] ^= 1
                    elif mode == "parameter":
                        reader.segments[SCENE["parameter"]][0x20] ^= 1
                    else:
                        reader.put(ADDR["members"], SCENE["scene"])
                return result
            reader.read = reading
            report = self.collect(reader)
            self.rejected(report)
            self.assertIn("dependency reread", report["reason"])

    def test_15_new_header_and_weak_dependency_changes_or_disappearance_refuse(self):
        for mode in ("header", "weak", "missing"):
            reader = fixture()
            original, changed = reader.read, False
            def reading(at, size):
                nonlocal changed
                result = original(at, size)
                if not changed and (at, size) == (CANDIDATE_WEAK + 8, 8):
                    changed = True
                    if mode == "header":
                        reader.segments[CANDIDATE][0x18] ^= 1
                    elif mode == "weak":
                        reader.put(SKINNED_WEAK + 8, ADDR["owner"] + 0x30)
                    else:
                        reader.segments.pop(SKINNED_WEAK)
                return result
            reader.read = reading
            self.rejected(self.collect(reader))

    def test_16_all_middle_and_end_same_handle_identity_gates_clear_success(self):
        for stage in range(1, 5):
            for altered in (identity(pid=999), identity(creationTime100ns="999"), identity(imagePath="other.exe"),
                            identity(moduleBase=BASE + 8), identity(moduleSize=LENGTH + 8), probe.ProbeError("Reader exited")):
                ids = [identity()] * 5
                ids[stage] = altered
                self.rejected(self.collect(fixture(), identities=ids))

    def test_17_invalid_initial_identity_and_image_extent_do_not_read_heap(self):
        for altered in (identity(pid=False), identity(pid=0), identity(creationTime100ns=""),
                        identity(creationTime100ns="0"), identity(creationTime100ns="１２３"), identity(imagePath="")):
            reader = fixture()
            self.rejected(self.collect(reader, identities=[altered]))
            self.assertEqual(reader.reads, [])
        for base, length in ((0, LENGTH), (BASE, False), (BASE, 0), (BASE, probe.core.MAX_IMAGE_SIZE + 1),
                             (BASE, probe.CONTEXT_VTABLE), (2**47 - 8, LENGTH)):
            reader = fixture()
            self.rejected(self.collect(reader, identities=[identity(moduleBase=base, moduleSize=length)], base=base, length=length))
            self.assertEqual(reader.reads, [])

    def run_main(self, reader, output, *, version=None, digests=None, identities=None):
        profile = {"game_version": probe.roster.VERSION, "game_sha256": probe.roster.SHA256}
        with mock.patch("sys.argv", ["probe_owner_skinned_object", "--pid", "43210", "--output", str(output)]), \
                mock.patch.object(probe.core, "Reader", return_value=reader), \
                mock.patch.object(probe.core, "load_profile", return_value=(profile, [])), \
                mock.patch.object(probe.subprocess, "check_output", return_value=version or probe.roster.VERSION), \
                mock.patch.object(probe.appearance, "file_digest", side_effect=digests or [probe.roster.SHA256] * 2), \
                mock.patch.object(probe, "process_identity", side_effect=identities or [identity()] * 6), \
                contextlib.redirect_stdout(io.StringIO()) as text:
            code = probe.main()
        reader.close.assert_called_once()
        return code, json.loads(text.getvalue())

    def test_18_cli_complete_maximum_directory_persists_and_closes_reader(self):
        with tempfile.TemporaryDirectory(prefix="owner-skinned-check-", dir=probe.ROOT / "runtime") as temp:
            path = Path(temp) / "maximum.json"
            code, summary = self.run_main(fixture(probe.appearance.MAX_OWNER_COMPONENTS), path)
            self.assertEqual(code, 0)
            self.assertTrue(summary["outputWritten"])
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["state"], "observed")
            self.assertLess(path.stat().st_size, probe.MAX_REPORT_BYTES)
            self.assertEqual(report["samples"][0]["ownerComponents"]["count"], 256)
            self.assertEqual(report["samples"][0]["newSemanticReadBytes"], 97)

    def test_19_cli_final_creation_liveness_module_and_exe_gates_clear_success(self):
        cases = [(None, [identity()] * 5 + [identity(creationTime100ns="999")]),
                 (None, [identity()] * 5 + [probe.ProbeError("Reader exited")]),
                 (None, [identity()] * 5 + [identity(moduleSize=LENGTH + 8)]),
                 ([probe.roster.SHA256, "0" * 64], None)]
        for digests, identities in cases:
            with tempfile.TemporaryDirectory(prefix="owner-skinned-check-", dir=probe.ROOT / "runtime") as temp:
                path = Path(temp) / "final.json"
                code, summary = self.run_main(fixture(), path, digests=digests, identities=identities)
                self.assertEqual(code, 1)
                self.assertTrue(summary["outputWritten"])
                self.rejected(json.loads(path.read_text(encoding="utf-8")))

    def test_20_wrong_build_existing_output_and_non_runtime_paths_reject(self):
        with tempfile.TemporaryDirectory(prefix="owner-skinned-check-", dir=probe.ROOT / "runtime") as temp:
            path = Path(temp) / "wrong-build.json"
            reader = fixture()
            code, _ = self.run_main(reader, path, version="0.0.0.0")
            self.assertEqual(code, 1)
            report = json.loads(path.read_text(encoding="utf-8"))
            self.rejected(report)
            self.assertEqual(reader.reads, [])
            existing = Path(temp) / "existing.json"
            existing.write_bytes(b"preserve")
            with mock.patch("sys.argv", ["probe_owner_skinned_object", "--pid", "43210", "--output", str(existing)]), \
                    mock.patch.object(probe.core, "Reader") as opened:
                with self.assertRaises(probe.ProbeError):
                    probe.main()
                opened.assert_not_called()
            self.assertEqual(existing.read_bytes(), b"preserve")
        with self.assertRaises((probe.ProbeError, RuntimeError)):
            probe.write_report(probe.ROOT / "build/forbidden-owner-skinned.json", probe.empty_report())

    def test_21_oversized_output_refuses_without_file_or_success(self):
        report = self.collect(fixture())
        report["syntheticOversize"] = "X" * probe.MAX_REPORT_BYTES
        with tempfile.TemporaryDirectory(prefix="owner-skinned-check-", dir=probe.ROOT / "runtime") as temp:
            path = Path(temp) / "oversize.json"
            with self.assertRaises(probe.ProbeError):
                probe.write_report(path, report)
            self.assertFalse(path.exists())
            self.rejected(report)

    def test_22_owner_directory_bounds_and_tamper_still_use_inherited_contract(self):
        for count, capacity in ((0, 2), (257, 257), (2, 1), (2, 4097)):
            reader = fixture()
            reader.put(ADDR["owner"] + 0x218, count, "<I")
            reader.put(ADDR["owner"] + 0x21C, capacity, "<I")
            self.rejected(self.collect(reader))
            self.assertNotIn((SKINNED + 0x1C0, 8), reader.reads)

    def test_23_owned_sources_parse_and_contract_keeps_no_animation_claims(self):
        for name in ("probe_owner_skinned_object.py", "check_owner_skinned_object.py"):
            path = Path(__file__).with_name(name)
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.assertEqual(len(probe.WINDOWS), 11)
        self.assertEqual(probe.CONTEXT_HEADER_BYTES, 64)
        self.assertEqual(probe.MAX_NEW_SEMANTIC_BYTES, 97)
        self.assertFalse(probe.empty_report()["animationSystemComplete"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
