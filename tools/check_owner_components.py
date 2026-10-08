"""Pure synthetic checks; never opens a game process or calls a native API."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import probe_owner_components as probe
from check_character_roster import FakeReader

BASE, LENGTH = 0x140000000, 0x173AB000
ADDR = {name: 0x20000 + index * 0x1000 for index, name in enumerate(
    ("root", "manager", "user", "actor", "table", "control", "holder", "controller", "owner", "weak", "members"))}
EXTRA_BASE = 0x100000


def install_type(reader, address, name, index, *, controller=False):
    vt = BASE + (probe.appearance.CONTROLLER_VTABLE if controller else 0x1000 + index * 0x100)
    col, desc, hierarchy = (0x20000 + index * 0x100, 0x80000 + index * 0x100, 0xF0000 + index * 0x100)
    reader.put(address, vt)
    reader.put(vt - 8, BASE + col)
    reader.segments[BASE + col] = bytearray(struct.pack("<6I", 1, 0, 0, desc, hierarchy, col))
    reader.block(BASE + desc + 16, probe.MAX_RTTI_BYTES)
    token = name.encode("ascii") + b"\0"
    reader.segments[BASE + desc + 16][:len(token)] = token
    return {"vtable": vt, "col": BASE + col, "name": BASE + desc + 16, "hierarchy": BASE + hierarchy}


def fixture(count=20):
    reader = FakeReader()
    for name, address in ADDR.items():
        reader.block(address, 0x220 if name == "owner" else 0xD8 + 8)
    types = {}
    for index, kind in enumerate(probe.appearance.TYPES):
        types[kind] = install_type(reader, ADDR[kind], probe.appearance.TYPES[kind], index,
                                   controller=kind == "controller")
    for rva, raw in probe.appearance.CODE_WINDOWS.items():
        reader.segments[BASE + rva] = bytearray(raw)
    tokens = probe.appearance.WORLD_PATTERN.split()
    for rva in probe.appearance.WORLD_ANCHORS:
        raw = bytearray(0 if token == "??" else int(token, 16) for token in tokens)
        struct.pack_into("<i", raw, 3, probe.appearance.WORLD_GLOBAL - rva - 7)
        reader.segments[BASE + rva] = raw
    for at, name in ((BASE + probe.appearance.WORLD_GLOBAL, "root"), (ADDR["root"] + 0x30, "manager"),
                    (ADDR["manager"] + 0x58, "user"), (ADDR["manager"] + 0x50, "actor"),
                    (ADDR["user"] + 0xD0, "actor"), (ADDR["user"] + 0xD8, "actor"),
                    (ADDR["actor"] + 0xA0, "user"), (ADDR["actor"] + 0x68, "table"),
                    (ADDR["table"] + 0x40, "control"), (ADDR["control"] + 8, "actor"),
                    (ADDR["control"] + 0xB8, "holder"), (ADDR["holder"] + 0x20, "controller"),
                    (ADDR["controller"] + 0x10, "owner"), (ADDR["controller"] + 0x60, "weak")):
        reader.put(at, ADDR[name])
    reader.put(ADDR["weak"] + 8, ADDR["owner"] + 0x28)
    reader.put(ADDR["owner"] + 0x3D, 0, "<B")
    reader.put(ADDR["owner"] + 0x210, ADDR["members"])
    reader.put(ADDR["owner"] + 0x218, count, "<I")
    reader.put(ADDR["owner"] + 0x21C, max(count, 32), "<I")
    reader.block(ADDR["members"], max(1, count) * 8)
    reader.put(ADDR["members"], ADDR["controller"])
    extra = []
    for index in range(1, count):
        address = EXTRA_BASE + index * 0x1000
        # Only a primary vtable is readable, never a putative component owner.
        reader.block(address, 8)
        layout = install_type(reader, address, f".?AVSyntheticRegisteredComponent{index}@fixture@@", 16 + index)
        reader.put(ADDR["members"] + index * 8, address)
        extra.append({"address": address, **layout})
    reader.layouts, reader.extras = types, extra
    reader.module = mock.Mock(return_value=(BASE, LENGTH, Path("synthetic/CrimsonDesert.exe")))
    reader.handle, reader.close = 12345, mock.Mock()
    reader.rtti = mock.Mock(side_effect=AssertionError("Unwatched RTTI traversal is forbidden"))
    reader.reads.clear()
    return reader


def identity(**changes):
    return {"pid": 43210, "creationTime100ns": "1234567890123456", "moduleBase": BASE,
            "moduleSize": LENGTH, "imagePath": "synthetic/CrimsonDesert.exe", **changes}


class OwnerComponentChecks(unittest.TestCase):
    def setUp(self):
        self.reader_guard = mock.patch.object(probe.core, "Reader", side_effect=AssertionError("Process opens forbidden"))
        self.identity_guard = mock.patch.object(probe, "process_identity", side_effect=AssertionError("Native API forbidden"))
        self.reader_guard.start()
        self.identity_guard.start()
        self.addCleanup(self.reader_guard.stop)
        self.addCleanup(self.identity_guard.stop)

    def collect(self, reader, *, pause=lambda _: None, identities=None, base=BASE, length=LENGTH):
        callback = mock.Mock(side_effect=identities) if identities is not None else lambda: identity()
        return probe.collect(reader, base, length, identity=callback, pause=pause)

    def rejected(self, report):
        self.assertNotEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(all(report[flag] is False for flag in (*probe.SUCCESS_FLAGS, *probe.UNVERIFIED_FLAGS)))

    def test_01_twenty_ordered_identities_are_membership_only(self):
        reader = fixture()
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(all(report[flag] for flag in probe.SUCCESS_FLAGS))
        self.assertTrue(all(report[flag] is False for flag in probe.UNVERIFIED_FLAGS))
        self.assertEqual(report["samples"][0], report["samples"][1])
        sample = report["samples"][0]
        self.assertEqual([row["index"] for row in sample["entries"]], list(range(20)))
        self.assertEqual(sample["ownerComponents"]["memberBytesHex"], bytes(reader.segments[ADDR["members"]]).hex())
        self.assertEqual(sample["ownerComponents"]["count"], 20)
        self.assertIs(sample["ownerComponents"]["capacitySemanticsVerified"], False)
        for row in sample["entries"]:
            self.assertTrue(row["primaryRttiObserved"] and row["identityOnly"])
            self.assertFalse(row["layoutInterpreted"] or row["componentOwnerBacklinkVerified"])
        for layout in reader.extras:
            self.assertEqual(set((at, size) for at, size in reader.reads
                                 if layout["address"] <= at < layout["address"] + 0x1000), {(layout["address"], 8)})
        self.assertNotIn((ADDR["controller"], 0x140), reader.reads)
        self.assertEqual(reader.reads.count((ADDR["members"], 160)), 4)
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))
        reader.rtti.assert_not_called()

    def test_02_capacity_slots_are_never_read(self):
        reader = fixture(2)
        reader.put(ADDR["owner"] + 0x21C, 4096, "<I")
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed")
        self.assertFalse(any(ADDR["members"] + 16 <= at < ADDR["members"] + 4096 * 8 for at, _ in reader.reads))

    def test_03_count_capacity_bounds_refuse_before_members(self):
        for count, capacity in ((0, 32), (257, 257), (20, 19), (20, 4097)):
            reader = fixture()
            reader.put(ADDR["owner"] + 0x218, count, "<I")
            reader.put(ADDR["owner"] + 0x21C, capacity, "<I")
            self.rejected(self.collect(reader))
            self.assertFalse(any(at == ADDR["members"] for at, _ in reader.reads))

    def test_04_incomplete_member_span_is_never_interpreted(self):
        reader = fixture()
        reader.segments[ADDR["members"]] = reader.segments[ADDR["members"]][:-1]
        report = self.collect(reader)
        self.rejected(report)
        self.assertNotIn("entries", report["samples"][0])

    def test_05_missing_or_duplicate_controller_refuses_before_slots(self):
        for replacement in (0, ADDR["controller"]):
            reader = fixture(2)
            reader.put(ADDR["members"] + (0 if replacement == 0 else 8), replacement)
            self.rejected(self.collect(reader))
            self.assertFalse(any(at == reader.extras[0]["address"] for at, _ in reader.reads))

    def test_06_owner_round_trips_and_known_types_fail_closed(self):
        for at, value, fmt in ((ADDR["user"] + 0xD0, ADDR["actor"] + 8, "<Q"),
                              (ADDR["actor"] + 0xA0, ADDR["user"] + 8, "<Q"),
                              (ADDR["control"] + 8, ADDR["actor"] + 8, "<Q"),
                              (ADDR["weak"] + 8, ADDR["owner"] + 0x30, "<Q"),
                              (ADDR["owner"] + 0x3D, 1, "<B")):
            reader = fixture()
            reader.put(at, value, fmt)
            self.rejected(self.collect(reader))
        reader = fixture()
        reader.segments[reader.layouts["owner"]["name"]][0] = ord("X")
        self.rejected(self.collect(reader))

    def test_07_unknown_or_missing_primary_col_keeps_slot_unavailable(self):
        for alter in (lambda r, p: r.put(p["vtable"] - 8, 0),
                      lambda r, p: r.put(p["col"] + 8, 37, "<I"),
                      lambda r, p: r.put(p["address"], BASE + probe.appearance.SCENE_VTABLE),
                      lambda r, p: r.segments.pop(p["address"])):
            reader = fixture(3)
            alter(reader, reader.extras[0])
            report = self.collect(reader)
            self.assertEqual(report["state"], "observed", report.get("reason"))
            self.assertFalse(report["allPrimaryRttiObserved"])
            rows = report["samples"][0]["entries"]
            self.assertEqual(rows[1]["state"], "unavailable")
            self.assertTrue(rows[2]["primaryRttiObserved"])
            self.assertNotIn("rtti", rows[1])
            self.assertFalse(any(at == reader.extras[0]["address"] + 8 for at, _ in reader.reads))

    def test_08_primary_header_and_name_bounds_have_no_fallback(self):
        alterations = (lambda r, p: r.put(p["address"], BASE - 8),
            lambda r, p: r.put(p["vtable"] - 8, BASE + LENGTH - 16),
            lambda r, p: r.put(p["col"], 2, "<I"), lambda r, p: r.put(p["col"] + 4, 8, "<I"),
            lambda r, p: r.put(p["col"] + 12, LENGTH - 1, "<I"),
            lambda r, p: r.put(p["col"] + 16, LENGTH, "<I"),
            lambda r, p: r.put(p["col"] + 20, 0, "<I"),
            lambda r, p: r.segments.__setitem__(p["name"], bytearray(b"X" * probe.MAX_RTTI_BYTES)),
            lambda r, p: r.segments[p["name"]].__setitem__(0, 255))
        for alter in alterations:
            reader = fixture(2)
            alter(reader, reader.extras[0])
            report = self.collect(reader)
            self.assertEqual(report["state"], "observed")
            self.assertFalse(report["allPrimaryRttiObserved"])
            self.assertFalse(report["samples"][0]["entries"][1]["primaryRttiObserved"])

    def test_09_maximum_bound_still_reads_only_count_entries(self):
        reader = fixture(probe.MAX_COMPONENTS)
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertEqual(len(report["samples"][0]["entries"]), probe.MAX_COMPONENTS)
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))

    def test_10_cross_sample_member_order_and_identity_changes_reject(self):
        for mode in ("members", "directory", "name", "header"):
            reader = fixture(3)
            def change(_):
                if mode == "members":
                    raw = reader.segments[ADDR["members"]]
                    raw[8:16], raw[16:24] = raw[16:24], raw[8:16]
                elif mode == "directory":
                    reader.put(ADDR["owner"] + 0x21C, 33, "<I")
                elif mode == "name":
                    reader.segments[reader.extras[0]["name"]][5] ^= 1
                else:
                    reader.put(reader.extras[0]["col"] + 8, 1, "<I")
            report = self.collect(reader, pause=change)
            self.rejected(report)
            self.assertEqual(report["state"], "unstable")

    def test_11_table_change_after_read_is_caught_by_dependency_reread(self):
        reader = fixture(3)
        original, changed = reader.read, False
        def reading(at, size):
            nonlocal changed
            result = original(at, size)
            if not changed and at == reader.extras[-1]["address"]:
                changed = True
                reader.put(ADDR["members"] + 8, reader.extras[-1]["address"])
            return result
        reader.read = reading
        report = self.collect(reader)
        self.rejected(report)
        self.assertIn("dependency reread", report["reason"])

    def test_12_earlier_identity_change_after_last_slot_is_rejected(self):
        reader = fixture(3)
        original, changed = reader.read, False
        def reading(at, size):
            nonlocal changed
            result = original(at, size)
            if not changed and at == reader.extras[-1]["name"]:
                changed = True
                reader.segments[reader.extras[0]["name"]][4] ^= 1
            return result
        reader.read = reading
        report = self.collect(reader)
        self.rejected(report)
        self.assertIn("dependency reread", report["reason"])

    def test_13_final_code_recheck_refuses_changed_source(self):
        reader = fixture()
        rva = next(iter(probe.appearance.CODE_WINDOWS))
        report = self.collect(reader, pause=lambda _: reader.segments[BASE + rva].__setitem__(0, 0))
        self.rejected(report)
        self.assertEqual(report["state"], "unstable")

    def test_14_process_identity_middle_and_end_gate_clear_success(self):
        for stage in (1, 2):
            for last in (identity(pid=999), identity(creationTime100ns="999"), identity(imagePath="other.exe"),
                         identity(moduleBase=BASE + 8), identity(moduleSize=LENGTH + 8), probe.ProbeError("Reader exited")):
                ids = [identity()] * 3
                ids[stage] = last
                report = self.collect(fixture(), identities=ids)
                self.rejected(report)
                self.assertEqual(report["state"], "unstable")

    def test_15_invalid_initial_identity_and_module_bounds_do_not_read_heap(self):
        for changes in ({"pid": False}, {"pid": 0}, {"creationTime100ns": ""}, {"creationTime100ns": "0"},
                        {"creationTime100ns": "１２３"}, {"moduleBase": BASE + 8}, {"imagePath": ""}):
            reader = fixture()
            self.rejected(self.collect(reader, identities=[identity(**changes)]))
            self.assertEqual(reader.reads, [])
        for base, length in ((0, LENGTH), (BASE, 0), (BASE, True), (2**47 - 8, LENGTH),
                             (BASE, probe.core.MAX_IMAGE_SIZE + 1)):
            reader = fixture()
            self.rejected(self.collect(reader, identities=[identity(moduleBase=base, moduleSize=length)], base=base, length=length))
            self.assertFalse(any(at < BASE for at, _ in reader.reads))

    def run_main(self, reader, output, *, version=None, identities=None, digests=None):
        profile = {"game_version": probe.roster.VERSION, "game_sha256": probe.roster.SHA256}
        with mock.patch("sys.argv", ["probe_owner_components", "--pid", "43210", "--output", str(output)]), \
                mock.patch.object(probe.core, "Reader", return_value=reader) as opened, \
                mock.patch.object(probe.core, "load_profile", return_value=(profile, [])), \
                mock.patch.object(probe, "process_identity", side_effect=identities or [identity()] * 4), \
                mock.patch.object(probe.subprocess, "check_output", return_value=version or probe.roster.VERSION), \
                mock.patch.object(probe.appearance, "file_digest", side_effect=digests or [probe.roster.SHA256] * 2), \
                mock.patch("builtins.print"):
            result = probe.main()
            opened.assert_called_once_with(43210)
        reader.close.assert_called_once()
        return result, json.loads(output.read_bytes())

    def test_16_main_version_hash_gate_refuses_before_observation(self):
        for version, digest in (("wrong", probe.roster.SHA256), (probe.roster.VERSION, "0" * 64)):
            reader = fixture()
            with tempfile.TemporaryDirectory(prefix="owner-components-version-", dir=probe.ROOT / "runtime") as temporary:
                result, report = self.run_main(reader, Path(temporary) / "new.json", version=version, digests=[digest])
            self.assertEqual(result, 1)
            self.rejected(report)
            self.assertEqual(reader.reads, [])

    def test_17_main_final_creation_exit_and_exe_gate_clear_success(self):
        for failure in ("creation", "exit", "digest"):
            ids, hashes = [identity()] * 4, [probe.roster.SHA256] * 2
            if failure == "creation":
                ids[-1] = identity(creationTime100ns="999")
            elif failure == "exit":
                ids[-1] = probe.ProbeError("Reader exited")
            else:
                hashes[-1] = "0" * 64
            with tempfile.TemporaryDirectory(prefix="owner-components-final-", dir=probe.ROOT / "runtime") as temporary:
                result, report = self.run_main(fixture(), Path(temporary) / "new.json", identities=ids, digests=hashes)
            self.assertEqual(result, 1)
            self.rejected(report)

    def test_18_successful_main_preserves_independent_limits_and_fresh_output(self):
        with tempfile.TemporaryDirectory(prefix="owner-components-main-", dir=probe.ROOT / "runtime") as temporary:
            result, report = self.run_main(fixture(), Path(temporary) / "new.json")
        self.assertEqual(result, 0)
        self.assertEqual(report["contract"]["memberStride"], 8)
        self.assertEqual(report["contract"]["directoryOffset"], "0x210")
        self.assertTrue(all(report[flag] is False for flag in probe.UNVERIFIED_FLAGS))

    def test_19_bad_or_existing_output_refuses_before_process_open(self):
        with tempfile.TemporaryDirectory(prefix="owner-components-output-", dir=probe.ROOT / "runtime") as temporary:
            existing = Path(temporary) / "existing.json"
            existing.write_bytes(b"preserve")
            for output in (existing, probe.ROOT / "tools/out.json", Path(temporary) / "wrong.txt"):
                with mock.patch("sys.argv", ["probe_owner_components", "--pid", "43210", "--output", str(output)]), \
                        mock.patch.object(probe.core, "Reader") as opened:
                    with self.assertRaises((probe.ProbeError, RuntimeError)):
                        probe.main()
                    opened.assert_not_called()
            self.assertEqual(existing.read_bytes(), b"preserve")

    def test_20_caught_slot_change_cannot_hide_a_restored_dependency(self):
        reader = fixture(3)
        first, second = reader.extras
        reader.put(second["address"], first["vtable"])
        original_read = reader.read
        original_bytes = bytes(reader.segments[first["name"]])
        calls = 0
        def reading(at, size):
            nonlocal calls
            raw = original_read(at, size)
            if at == first["name"]:
                calls += 1
                if calls == 1:
                    reader.segments[first["name"]][4] ^= 1
                elif calls == 2:
                    reader.segments[first["name"]][:] = original_bytes
            return raw
        reader.read = reading
        report = self.collect(reader)
        self.rejected(report)
        self.assertEqual(len(report["samples"]), 1)
        self.assertIn("identity dependency changed", report["reason"])

    def test_21_unavailable_identity_span_is_rechecked_after_final_slot(self):
        reader = fixture(3)
        first, second = reader.extras
        reader.segments.pop(first["address"])
        original_read, changed = reader.read, False
        def reading(at, size):
            nonlocal changed
            raw = original_read(at, size)
            if not changed and at == second["name"]:
                changed = True
                reader.put(first["address"], first["vtable"])
            return raw
        reader.read = reading
        report = self.collect(reader)
        self.rejected(report)
        self.assertIn("became readable during dependency reread", report["reason"])

    def test_22_maximum_count_and_longest_rtti_names_persist_complete_cli_report(self):
        reader = fixture(probe.MAX_COMPONENTS)
        for layout in reader.extras:
            reader.segments[layout["name"]][:] = b"X" * (probe.MAX_RTTI_BYTES - 1) + b"\0"
        with tempfile.TemporaryDirectory(prefix="owner-components-maximum-", dir=probe.ROOT / "runtime") as temporary:
            output = Path(temporary) / "new.json"
            result, report = self.run_main(reader, output)
            raw_bytes = output.stat().st_size
        self.assertEqual(result, 0)
        self.assertEqual(report["state"], "observed")
        self.assertTrue(all(report[flag] for flag in probe.SUCCESS_FLAGS))
        self.assertGreater(raw_bytes, 512 * 1024)
        self.assertLess(raw_bytes, probe.MAX_REPORT_BYTES)
        self.assertEqual(report["contract"]["maximumReportBytes"], probe.MAX_REPORT_BYTES)
        self.assertEqual(len(report["samples"][0]["entries"]), probe.MAX_COMPONENTS)
        self.assertEqual(len(bytes.fromhex(report["samples"][0]["ownerComponents"]["memberBytesHex"])), 256 * 8)
        self.assertEqual(report["samples"][0], report["samples"][1])
        self.assertTrue(all(len(row["rtti"]) == 191 for row in report["samples"][0]["entries"][1:]))
        # Also exercise the bounded worst per-slot JSON error escaping without
        # dropping any original evidence from the maximum-count report.
        for sample in report["samples"]:
            for row in sample["entries"]:
                row["reason"] = "\0" * probe.MAX_REASON_CHARACTERS
        with tempfile.TemporaryDirectory(prefix="owner-components-error-bound-", dir=probe.ROOT / "runtime") as temporary:
            output = Path(temporary) / "full.json"
            probe.write_report(output, report)
            self.assertLess(output.stat().st_size, probe.MAX_REPORT_BYTES)
            self.assertEqual(json.loads(output.read_bytes()), report)

    def test_23_oversized_cli_report_clears_flags_and_leaves_no_partial_output(self):
        report = self.collect(fixture())
        report["oversizedSyntheticFault"] = "X" * probe.MAX_REPORT_BYTES
        reader = fixture()
        profile = {"game_version": probe.roster.VERSION, "game_sha256": probe.roster.SHA256}
        with tempfile.TemporaryDirectory(prefix="owner-components-oversize-", dir=probe.ROOT / "runtime") as temporary:
            output = Path(temporary) / "new.json"
            with mock.patch("sys.argv", ["probe_owner_components", "--pid", "43210", "--output", str(output)]), \
                    mock.patch.object(probe.core, "Reader", return_value=reader), \
                    mock.patch.object(probe.core, "load_profile", return_value=(profile, [])), \
                    mock.patch.object(probe, "collect", return_value=report), \
                    mock.patch.object(probe, "process_identity", return_value=identity()), \
                    mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION), \
                    mock.patch.object(probe.appearance, "file_digest", return_value=probe.roster.SHA256), \
                    mock.patch("builtins.print") as printed:
                result = probe.main()
            summary = json.loads(printed.call_args.args[0])
            self.assertEqual(result, 1)
            self.assertFalse(output.exists())
            self.assertFalse(summary["outputWritten"])
            self.assertIn("4MiB output bound", summary["reason"])
            self.assertTrue(all(summary[flag] is False for flag in probe.SUCCESS_FLAGS))
            self.rejected(report)
        reader.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
