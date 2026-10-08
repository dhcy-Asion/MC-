"""Isolated typed-equipment fault checks and fixed-EXE disk pins; no process opens."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import probe_equipment as probe
from check_health_probe import DiskImage, install_type
from check_character_roster import FakeReader

BASE = 0x140000000
ADDR = {name: 0x20000 + index * 0x2000 for index, name in enumerate(
    ("world", "manager", "user", "actor", "components", "equipment", "descriptor"))}
ARRAY = 0x400000


def fixture(disk, tags=(0, 3, 4)):
    reader = FakeReader()
    for key, address in ADDR.items():
        reader.block(address, 0x14 if key == "descriptor" else 0x100)
    for rva, size, _ in probe.WINDOWS:
        reader.segments[BASE + rva] = bytearray(disk.read(rva, size))
    for rva in probe.appearance.WORLD_ANCHORS:
        reader.segments[BASE + rva] = bytearray(disk.read(rva, len(probe.appearance.WORLD_PATTERN.split())))
    for index, name in enumerate(("manager", "user", "actor")):
        install_type(reader, ADDR[name], name, index=index)
    install_type(reader, ADDR["equipment"], "equipment", fixed=probe.EQUIPMENT_TYPE)
    for address, name in ((BASE + probe.appearance.WORLD_GLOBAL, "world"), (ADDR["world"] + 0x30, "manager"),
            (ADDR["manager"] + 0x58, "user"), (ADDR["manager"] + 0x50, "actor"),
            (ADDR["user"] + 0xd0, "actor"), (ADDR["user"] + 0xd8, "actor"), (ADDR["actor"] + 0xa0, "user"),
            (ADDR["actor"] + 0x68, "components"), (ADDR["components"] + 0x38, "equipment"),
            (ADDR["equipment"] + 8, "actor"), (ADDR["equipment"] + 0x90, "descriptor")):
        reader.put(address, ADDR[name])
    reader.put(ADDR["descriptor"] + 8, ARRAY if tags else 0)
    reader.put(ADDR["descriptor"] + 0x10, len(tags), "<I")
    # Complete records contain arbitrary opaque bytes; no nested pointer is
    # readable and no item identifier is installed for a decoder to rely on.
    for index, tag in enumerate(tags):
        raw = bytearray((index * 37 + offset) % 256 for offset in range(probe.ENTRY_STRIDE))
        struct.pack_into("<H", raw, probe.SLOT_TAG_OFFSET, tag)
        reader.segments[ARRAY + index * probe.ENTRY_STRIDE] = raw
    reader.module = mock.Mock(return_value=(BASE, disk.length, disk.path))
    reader.handle, reader.close = 12345, mock.Mock()
    reader.reads.clear()
    return reader


def identity(disk, **changes):
    return {"pid": 43210, "creationTime100ns": "1234567890123456", "moduleBase": BASE,
            "moduleSize": disk.length, "imagePath": str(disk.path), **changes}


class EquipmentChecks(unittest.TestCase):
    exe = None

    @classmethod
    def setUpClass(cls):
        cls.disk = DiskImage(cls.exe)

    def collect(self, reader, *, pause=lambda _: None, identities=None, base=BASE, length=None):
        callback = mock.Mock(side_effect=identities) if identities is not None else lambda: identity(self.disk)
        return probe.collect(reader, base, self.disk.length if length is None else length, identity=callback, pause=pause)

    def assert_unavailable(self, report):
        self.assertNotEqual(report["state"], "observed", report)
        for flag in (*probe.SUCCESS_FLAGS, *probe.UNVERIFIED_FLAGS):
            self.assertIs(report[flag], False, flag)

    def run_main(self, reader, output, *, version=None, identities=None, digests=None):
        with mock.patch("sys.argv", ["probe_equipment", "--pid", "43210", "--output", str(output)]), \
                mock.patch.object(probe.core, "Reader", return_value=reader) as opened, \
                mock.patch.object(probe, "process_identity", side_effect=identities or [identity(self.disk)] * 3), \
                mock.patch.object(probe.subprocess, "check_output", return_value=version or probe.roster.VERSION), \
                mock.patch.object(probe.appearance, "file_digest", side_effect=digests or [probe.roster.SHA256] * 2), \
                mock.patch("builtins.print"):
            result = probe.main()
            opened.assert_called_once_with(43210)
        reader.close.assert_called_once()
        return result, json.loads(output.read_bytes())

    def test_01_fixed_disk_windows_primary_type_and_layout_bytes(self):
        self.assertEqual(len(probe.WINDOWS), 6)
        for rva, size, digest in probe.WINDOWS:
            self.assertEqual(hashlib.sha256(self.disk.read(rva, size)).hexdigest(), digest, hex(rva))
        vt, col, desc, hierarchy, name = probe.EQUIPMENT_TYPE
        self.assertEqual(struct.unpack("<Q", self.disk.read(vt - 8, 8))[0], self.disk.base + col)
        self.assertEqual(self.disk.read(col, 24), struct.pack("<6I", 1, 0, 0, desc, hierarchy, col))
        self.assertEqual(self.disk.read(desc + 16, len(name) + 1), name.encode() + b"\0")
        # Independent fixed consumers: table+90, QI at descriptor+8, D0
        # stride, C8 tag; two native actor+68/table+38 callsites, owner+8.
        for rva, expected in ((0x980a7e, "4c8b7108"), (0x980af1, "488b8690000000488b50088b40104869c8d0000000"),
                              (0x980b15, "663982c8000000"), (0x5f8867, "498b4f68"),
                              (0x5f8878, "488b4938"), (0x9e6427, "488b4b68"), (0x9e6438, "488b4938")):
            raw = bytes.fromhex(expected)
            self.assertEqual(self.disk.read(rva, len(raw)), raw, hex(rva))
        probe.validate_code(fixture(self.disk), BASE, self.disk.length)

    def test_02_complete_table_is_raw_only_and_has_no_extra_reads(self):
        reader = fixture(self.disk)
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(all(report[flag] for flag in probe.SUCCESS_FLAGS))
        self.assertTrue(all(report[flag] is False for flag in probe.UNVERIFIED_FLAGS))
        self.assertEqual(report["samples"][0], report["samples"][1])
        sample = report["samples"][0]
        self.assertEqual([row["slotTagU16"] for row in sample["entries"]], [0, 3, 4])
        for index, entry in enumerate(sample["entries"]):
            self.assertEqual(set(entry), {"index", "slotTagU16", "rawD0Sha256"})
            raw = bytes(reader.segments[ARRAY + index * probe.ENTRY_STRIDE])
            self.assertEqual(entry["rawD0Sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(reader.reads.count((ARRAY + index * probe.ENTRY_STRIDE, probe.ENTRY_STRIDE)), 4)
            self.assertTrue(any(row["address"] == hex(ARRAY + index * probe.ENTRY_STRIDE) and
                                row["bytesHex"] == raw.hex() for row in sample["dependencies"]))
        self.assertNotIn((ADDR["descriptor"] + 0x14, 4), reader.reads)  # No invented capacity.
        self.assertTrue(all(size <= 4096 for _, size in reader.reads))
        allowed = {int(row["address"], 16) for row in sample["dependencies"]}
        self.assertFalse(any(address < BASE and address not in allowed for address, _ in reader.reads))

    def test_03_empty_maximum_table_and_unknown_raw_tag_are_observable(self):
        for tags in ((), (65535,), tuple(range(probe.MAX_ENTRIES))):
            reader = fixture(self.disk, tags)
            report = self.collect(reader)
            self.assertEqual(report["state"], "observed", report.get("reason"))
            self.assertEqual(report["samples"][0]["entryCount"], len(tags))
            self.assertFalse(any(address == 0 for address, _ in reader.reads))
        reader = fixture(self.disk, ())
        reader.put(ADDR["descriptor"] + 8, ARRAY)
        self.assertEqual(self.collect(reader)["state"], "observed")

    def test_04_count_over_bound_stops_before_records(self):
        for count in (65, 65536, 2**32 - 1):
            reader = fixture(self.disk)
            reader.put(ADDR["descriptor"] + 0x10, count, "<I")
            self.assert_unavailable(self.collect(reader))
            self.assertFalse(any(ARRAY <= address < ARRAY + 64 * probe.ENTRY_STRIDE for address, _ in reader.reads))

    def test_05_array_pointer_and_complete_span_bounds_stop_before_records(self):
        for data in (0, ARRAY + 1, 0xfff8, 2**47, 2**47 - 8, 2**47 - 2 * probe.ENTRY_STRIDE):
            reader = fixture(self.disk)
            reader.put(ADDR["descriptor"] + 8, data)
            self.assert_unavailable(self.collect(reader))
            self.assertFalse(any(size == probe.ENTRY_STRIDE for _, size in reader.reads))
        reader = fixture(self.disk, ())
        reader.put(ADDR["descriptor"] + 8, 3)
        self.assert_unavailable(self.collect(reader))

    def test_06_duplicate_slot_never_selects_or_merges_a_record(self):
        for tags in ((3, 3), (0, 65535, 65535)):
            report = self.collect(fixture(self.disk, tags))
            self.assert_unavailable(report)
            self.assertIn("Repeated", report["reason"])

    def test_07_each_code_window_rejects_before_heap(self):
        for rva, _, _ in probe.WINDOWS:
            reader = fixture(self.disk)
            reader.segments[BASE + rva][0] ^= 1
            report = self.collect(reader)
            self.assert_unavailable(report)
            self.assertEqual(report["samples"], [])
            self.assertFalse(any(address < BASE for address, _ in reader.reads))

    def test_08_world_anchor_and_fixed_type_pins_reject_before_heap(self):
        vt, col, desc, _, _ = probe.EQUIPMENT_TYPE
        changes = [(BASE + rva, 0, "<B") for rva in probe.appearance.WORLD_ANCHORS]
        changes += [(BASE + vt - 8, BASE + col + 8, "<Q"), (BASE + col, 0, "<I"),
                    (BASE + col + 4, 8, "<I"), (BASE + col + 8, 1, "<I"),
                    (BASE + col + 20, col + 8, "<I"), (BASE + desc + 16, 0, "<B")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            reader.put(address, value, fmt)
            self.assert_unavailable(self.collect(reader))
            self.assertFalse(any(at < BASE for at, _ in reader.reads))

    def test_09_exact_component_type_and_owner_before_descriptor(self):
        for address, value in ((ADDR["equipment"], BASE + 0x5b29178), (ADDR["equipment"], 0),
                               (ADDR["equipment"] + 8, ADDR["actor"] + 8), (ADDR["equipment"] + 8, 0)):
            reader = fixture(self.disk)
            reader.put(address, value)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ADDR["equipment"] + 0x90, 8), reader.reads)

    def test_10_controlled_actor_type_and_all_round_trips_are_required(self):
        for kind in ("manager", "user", "actor"):
            reader = fixture(self.disk)
            reader.put(ADDR[kind], BASE + 0x800000)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ADDR["components"] + 0x38, 8), reader.reads)
        for address in (ADDR["manager"] + 0x50, ADDR["user"] + 0xd0, ADDR["user"] + 0xd8, ADDR["actor"] + 0xa0):
            reader = fixture(self.disk)
            reader.put(address, 0)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ADDR["components"] + 0x38, 8), reader.reads)
        # Reject non-primary COL and altered name for each controlled type.
        for index, kind in enumerate(("manager", "user", "actor")):
            for address, value in ((BASE + 0x100100 + index * 0x1000 + 4, 8),
                                   (BASE + 0x100210 + index * 0x1000, 0)):
                reader = fixture(self.disk)
                reader.put(address, value, "<B")
                self.assert_unavailable(self.collect(reader))

    def test_11_broken_component_descriptor_and_short_table_record_fail(self):
        for address in (ADDR["actor"] + 0x68, ADDR["components"] + 0x38, ADDR["equipment"] + 0x90):
            for value in (0, 3, 2**47, 2**47 - 8):
                reader = fixture(self.disk)
                reader.put(address, value)
                self.assert_unavailable(self.collect(reader))
        for address in (ADDR["descriptor"], ARRAY, ARRAY + 2 * probe.ENTRY_STRIDE):
            reader = fixture(self.disk)
            reader.segments[address] = reader.segments[address][:-1]
            self.assert_unavailable(self.collect(reader))

    def test_12_read_failures_at_each_table_field_and_record(self):
        for target in ((ADDR["equipment"] + 8, 8), (ADDR["equipment"] + 0x90, 8),
                       (ADDR["descriptor"] + 8, 12), (ARRAY, probe.ENTRY_STRIDE)):
            for replacement in (None, b"", OSError("inaccessible")):
                reader = fixture(self.disk)
                original = reader.read
                def failing(address, size):
                    if (address, size) == target:
                        if isinstance(replacement, Exception):
                            raise replacement
                        return replacement
                    return original(address, size)
                reader.read = failing
                self.assert_unavailable(self.collect(reader))

    def test_13_every_dependency_is_reread_and_changes_invalidate(self):
        baseline = self.collect(fixture(self.disk))
        for dependency in baseline["samples"][0]["dependencies"]:
            reader = fixture(self.disk)
            target = (int(dependency["address"], 16), dependency["size"])
            original, seen = reader.read, 0
            def changing(address, size):
                nonlocal seen
                raw = original(address, size)
                if (address, size) == target:
                    seen += 1
                    if seen == 2 and raw:
                        return bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            reader.read = changing
            self.assert_unavailable(self.collect(reader))

    def test_14_two_samples_include_opaque_bytes_not_just_tag_and_hash(self):
        for address, value, fmt in ((ADDR["equipment"] + 8, ADDR["actor"] + 8, "<Q"),
                (ADDR["descriptor"] + 8, ARRAY + probe.ENTRY_STRIDE, "<Q"), (ADDR["descriptor"] + 0x10, 1, "<I"),
                (ARRAY, 100, "<B"), (ARRAY + 0xb0, 100, "<B"), (ARRAY + 0xc8, 20, "<H")):
            reader = fixture(self.disk)
            report = self.collect(reader, pause=lambda _: reader.put(address, value, fmt))
            self.assert_unavailable(report)
            self.assertEqual(report["state"], "unstable")

    def test_15_final_code_recheck_clears_success(self):
        for rva, _, _ in probe.WINDOWS:
            reader = fixture(self.disk)
            def mutate(_):
                reader.segments[BASE + rva][0] ^= 1
            report = self.collect(reader, pause=mutate)
            self.assert_unavailable(report)
            self.assertEqual(report["state"], "unstable")

    def test_16_process_identity_changes_and_exit_clear_success(self):
        before = identity(self.disk)
        for changes in ({"pid": 999}, {"creationTime100ns": "999"}, {"moduleBase": BASE + 0x1000},
                        {"moduleSize": self.disk.length + 8}, {"imagePath": "different.exe"}):
            self.assert_unavailable(self.collect(fixture(self.disk), identities=[before, identity(self.disk, **changes)]))
        self.assert_unavailable(self.collect(fixture(self.disk), identities=[before, probe.ProbeError("Reader exited")]))
        self.assertIs(probe.process_identity, probe.health.process_identity)

    def test_17_invalid_initial_identity_and_module_bounds_fail_before_heap(self):
        for changes in ({"pid": False}, {"pid": 0}, {"creationTime100ns": ""}, {"creationTime100ns": "0"},
                        {"moduleBase": BASE + 8}, {"moduleSize": self.disk.length - 1}):
            reader = fixture(self.disk)
            self.assert_unavailable(self.collect(reader, identities=[identity(self.disk, **changes)]))
            self.assertEqual(reader.reads, [])
        for base, length in ((0, self.disk.length), (BASE, 0), (BASE, -1), (BASE, True),
                              (BASE, probe.core.MAX_IMAGE_SIZE + 1), (2**47 - 8, self.disk.length), (BASE, 0x6000000)):
            reader = fixture(self.disk)
            current = identity(self.disk, moduleBase=base, moduleSize=length)
            self.assert_unavailable(self.collect(reader, identities=[current], base=base, length=length))
            self.assertFalse(any(address < BASE for address, _ in reader.reads))

    def test_18_main_wrong_version_or_digest_is_unavailable_without_memory_reads(self):
        for version, digest in (("wrong", probe.roster.SHA256), (probe.roster.VERSION, "0" * 64)):
            reader = fixture(self.disk)
            with tempfile.TemporaryDirectory(prefix="equipment-version-", dir=probe.ROOT / "runtime") as temporary:
                result, report = self.run_main(reader, Path(temporary) / "new.json", version=version, digests=[digest])
            self.assertEqual(result, 1)
            self.assert_unavailable(report)
            self.assertEqual(reader.reads, [])

    def test_19_main_final_identity_exe_change_or_exit_clears_success(self):
        for last in ("digest", "session", "exit"):
            reader = fixture(self.disk)
            identities = [identity(self.disk)] * 3
            digests = [probe.roster.SHA256] * 2
            if last == "digest":
                digests[-1] = "0" * 64
            elif last == "session":
                identities[-1] = identity(self.disk, creationTime100ns="999")
            else:
                identities[-1] = probe.ProbeError("Reader exited")
            with tempfile.TemporaryDirectory(prefix="equipment-final-", dir=probe.ROOT / "runtime") as temporary:
                result, report = self.run_main(reader, Path(temporary) / "new.json", identities=identities, digests=digests)
            self.assertEqual(result, 1)
            self.assert_unavailable(report)

    def test_20_successful_main_writes_fresh_runtime_report(self):
        reader = fixture(self.disk)
        with tempfile.TemporaryDirectory(prefix="equipment-main-", dir=probe.ROOT / "runtime") as temporary:
            result, report = self.run_main(reader, Path(temporary) / "new.json")
        self.assertEqual(result, 0)
        self.assertEqual(report["state"], "observed")
        self.assertEqual(report["contract"]["maximumEntries"], 64)
        self.assertTrue(all(report[flag] is False for flag in probe.UNVERIFIED_FLAGS))

    def test_21_bad_or_existing_output_rejected_before_process_open(self):
        with tempfile.TemporaryDirectory(prefix="equipment-output-", dir=probe.ROOT / "runtime") as temporary:
            existing = Path(temporary) / "existing.json"
            existing.write_bytes(b"preserve")
            paths = (existing, probe.ROOT / "build/equipment-private.json", Path(temporary) / "bad.txt",
                     Path(temporary) / "../../equipment-public.json")
            for path in paths:
                with mock.patch("sys.argv", ["probe_equipment", "--pid", "43210", "--output", str(path)]), \
                        mock.patch.object(probe.core, "Reader") as opened, self.assertRaises(RuntimeError):
                    probe.main()
                opened.assert_not_called()
            self.assertEqual(existing.read_bytes(), b"preserve")

    def test_22_output_created_after_preflight_is_not_overwritten(self):
        reader = fixture(self.disk)
        with tempfile.TemporaryDirectory(prefix="equipment-race-", dir=probe.ROOT / "runtime") as temporary:
            path = Path(temporary) / "new.json"
            real_collect = probe.collect
            def collecting(*args, **kwargs):
                result = real_collect(*args, **kwargs)
                path.write_bytes(b"keep raced file")
                return result
            with mock.patch.object(probe, "collect", side_effect=collecting), self.assertRaises(RuntimeError):
                self.run_main(reader, path)
            self.assertEqual(path.read_bytes(), b"keep raced file")
        reader.close.assert_called_once()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="fixed original EXE; otherwise use runtime installation gameRoot")
    args = parser.parse_args()
    path = args.exe
    if path is None:
        installation = json.loads((probe.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))
        path = Path(installation["gameRoot"]) / "bin64/CrimsonDesert.exe"
    EquipmentChecks.exe = path
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EquipmentChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
