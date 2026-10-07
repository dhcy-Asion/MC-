"""Isolated typed-Hp fault checks plus fixed-EXE disk pins; never opens a process."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import probe_health as probe
from check_character_roster import FakeReader

BASE = 0x140000000
ADDR = {name: 0x20000+i*0x2000 for i, name in enumerate(("world", "manager", "user", "actor", "components", "status", "root",
        "characterMetadata", "groupMetadata", "statusMetadata", "characterTable", "groupTable", "statusTable",
        "characterRecord", "groupRecord", "statusRecord", "regen", "map"))}
HP, CHARACTER, GROUP, MAP_SLOT, MAPPED, ROOT_DATA = 37, 101, 11, 7, 3, 0x400000
ENTRY = ROOT_DATA+MAPPED*0x90
STRING_HOLDER, STRING_CHARS = 0x500000, 0x510003


class DiskImage:
    def file_key(self):
        value = self.path.stat()
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    def __init__(self, path):
        self.path = path
        self.fingerprint = self.file_key()
        self.digest = probe.appearance.file_digest(path)
        if self.digest != probe.roster.SHA256:
            raise ValueError("Static health checks require the fixed supported EXE")
        with path.open("rb") as stream:
            stream.seek(0x3c)
            pe = struct.unpack("<I", stream.read(4))[0]
            stream.seek(pe)
            header = stream.read(24)
            if header[:4] != b"PE\0\0":
                raise ValueError("Not a PE image")
            count, optional_size = struct.unpack_from("<H", header, 6)[0], struct.unpack_from("<H", header, 20)[0]
            optional = stream.read(optional_size)
            self.base, self.length = struct.unpack_from("<Q", optional, 24)[0], struct.unpack_from("<I", optional, 56)[0]
            self.sections = []
            for _ in range(count):
                row = stream.read(40)
                _, rva, size, start = struct.unpack_from("<4I", row, 8)
                self.sections.append((rva, size, start))

    def read(self, rva, size):
        section = next((row for row in self.sections if row[0] <= rva and rva+size <= row[0]+row[1]), None)
        if not section:
            raise ValueError("Pinned RVA has no complete file-backed span")
        with self.path.open("rb") as stream:
            stream.seek(section[2]+rva-section[0])
            raw = stream.read(size)
        if len(raw) != size or self.file_key() != self.fingerprint:
            raise ValueError("Static EXE changed while checking health pins")
        return raw


def install_type(reader, address, kind, fixed=None, index=0):
    if fixed:
        vt, col, desc, hierarchy, name = fixed
    else:
        vt, col, desc, hierarchy = (0x100000+index*0x1000+offset for offset in (0, 0x100, 0x200, 0x300))
        name = probe.appearance.TYPES[kind]
    reader.put(address, BASE+vt)
    reader.put(BASE+vt-8, BASE+col)
    reader.segments[BASE+col] = bytearray(struct.pack("<6I", 1, 0, 0, desc, hierarchy, col))
    reader.segments[BASE+desc+16] = bytearray(name.encode()+b"\0")


def fixture(disk):
    reader = FakeReader()
    for address in ADDR.values():
        reader.block(address, 0x700)
    for rva, size, _ in probe.WINDOWS:
        reader.segments[BASE+rva] = bytearray(disk.read(rva, size))
    rva, raw = probe.COUNTER_WINDOW
    reader.segments[BASE+rva] = bytearray(raw)
    for rva in probe.appearance.WORLD_ANCHORS:
        reader.segments[BASE+rva] = bytearray(disk.read(rva, len(probe.appearance.WORLD_PATTERN.split())))
    reader.put(BASE+probe.HP_NAME_SLOT, BASE+probe.HP_NAME)
    reader.segments[BASE+probe.HP_NAME] = bytearray(b"Hp\0")
    for index, kind in enumerate(("manager", "user", "actor")):
        install_type(reader, ADDR[kind], kind, index=index)
    for kind, fixed in probe.TYPES.items():
        install_type(reader, ADDR[kind], kind, fixed)
    for address, target in ((BASE+probe.appearance.WORLD_GLOBAL, "world"), (ADDR["world"]+0x30, "manager"),
            (ADDR["manager"]+0x58, "user"), (ADDR["manager"]+0x50, "actor"), (ADDR["user"]+0xd0, "actor"),
            (ADDR["user"]+0xd8, "actor"), (ADDR["actor"]+0xa0, "user"), (ADDR["actor"]+0x68, "components"),
            (ADDR["components"]+0x20, "status"), (ADDR["status"]+8, "actor"), (ADDR["status"]+0x18, "root"),
            (ADDR["root"], "status")):
        reader.put(address, ADDR[target])
    for kind, key, prefix, count in (("characterMetadata", CHARACTER, "character", 200),
                                   ("groupMetadata", GROUP, "group", 20), ("statusMetadata", HP, "status", 80)):
        reader.put(BASE+probe.GLOBALS[kind], ADDR[kind])
        reader.put(ADDR[kind]+8, count, "<I")
        reader.put(ADDR[kind]+0x58, ADDR[prefix+"Table"])
        # Only the selected pointer is readable. There is no record table scan.
        del reader.segments[ADDR[prefix+"Table"]]
        reader.put(ADDR[prefix+"Table"]+key*8, ADDR[prefix+"Record"])
    reader.put(ADDR["statusMetadata"]+0xa0, HP, "<H")
    reader.put(ADDR["status"]+0x30, CHARACTER, "<H")
    reader.put(ADDR["characterRecord"]+0x5b8, GROUP, "<H")
    reader.put(ADDR["statusRecord"], 0x12345678, "<I")  # Serialized key is not the uint16 loaded ordinal.
    reader.put(ADDR["statusRecord"]+8, STRING_HOLDER)
    reader.put(STRING_HOLDER, STRING_CHARS)
    reader.segments[STRING_CHARS] = bytearray(b"Hp\0")
    reader.put(ADDR["statusRecord"]+0x11, 2, "<B")
    reader.put(ADDR["statusRecord"]+0x14, MAP_SLOT, "<I")
    for offset, data, count in ((0x18, "regen", 5), (0x58, "map", 9)):
        reader.put(ADDR["groupRecord"]+offset, ADDR[data])
        reader.put(ADDR["groupRecord"]+offset+8, count, "<I")
        reader.put(ADDR["groupRecord"]+offset+12, count+1, "<I")
        del reader.segments[ADDR[data]]
    reader.put(ADDR["map"]+MAP_SLOT*4, MAPPED, "<i")
    reader.put(ADDR["regen"]+MAPPED*2, HP, "<H")
    reader.put(ADDR["root"]+0x58, ROOT_DATA)
    reader.put(ADDR["root"]+0x60, 7, "<I")  # Deliberately differs from regen count 5.
    reader.block(ENTRY, 0x90)
    reader.put(ENTRY, HP, "<H")
    reader.put(ENTRY+2, 0xbeef, "<H")  # Entry identity is uint16, not int32==0.
    for offset, value in ((8, 250000), (0x18, 300000), (0x20, 0), (0x28, 1000), (0x30, 700000), (0x48, 17)):
        reader.put(ENTRY+offset, value, "<q")
    reader.put(ENTRY+0x10, 123456789)
    reader.put(ENTRY+0x53, 2, "<B")
    reader.module = mock.Mock(return_value=(BASE, disk.length, disk.path))
    reader.handle, reader.close = 12345, mock.Mock()
    reader.reads.clear()
    return reader


def identity(disk, **changes):
    return {"pid": 43210, "creationTime100ns": "1234567890123456", "moduleBase": BASE,
            "moduleSize": disk.length, "imagePath": str(disk.path), **changes}


class HealthChecks(unittest.TestCase):
    exe = None

    @classmethod
    def setUpClass(cls):
        cls.disk = DiskImage(cls.exe)

    def collect(self, reader, pause=lambda _: None, identities=None):
        callback = mock.Mock(side_effect=identities) if identities is not None else lambda: identity(self.disk)
        return probe.collect(reader, BASE, self.disk.length, identity=callback, pause=pause)

    def assert_unavailable(self, report):
        self.assertNotEqual(report["state"], "observed", report)
        for flag in (*probe.SUCCESS_FLAGS, "hudReady", "snapshotAtomic", "gameMemoryWritten", "nativeFunctionsInvoked"):
            self.assertIs(report[flag], False, flag)

    def test_01_fixed_disk_code_types_names_and_counter_pins(self):
        self.assertEqual(len(probe.WINDOWS), 20)
        for rva, size, digest in probe.WINDOWS:
            self.assertEqual(hashlib.sha256(self.disk.read(rva, size)).hexdigest(), digest, hex(rva))
        rva, raw = probe.COUNTER_WINDOW
        self.assertEqual(self.disk.read(rva, len(raw)), raw)
        self.assertTrue(raw.startswith(bytes.fromhex("48ff4748")))  # inc qword [rdi+48]
        for vt, col, desc, hierarchy, name in probe.TYPES.values():
            self.assertEqual(struct.unpack("<Q", self.disk.read(vt-8, 8))[0], self.disk.base+col)
            self.assertEqual(self.disk.read(col, 24), struct.pack("<6I", 1, 0, 0, desc, hierarchy, col))
            self.assertEqual(self.disk.read(desc+16, len(name)+1), name.encode()+b"\0")
        self.assertEqual(self.disk.read(probe.HP_NAME, 3), b"Hp\0")
        self.assertEqual(struct.unpack("<Q", self.disk.read(probe.HP_NAME_SLOT, 8))[0], self.disk.base+probe.HP_NAME)
        probe.validate_code(fixture(self.disk), BASE, self.disk.length)

    def test_02_nonzero_named_hp_and_nonzero_mapped_index_stored_raw_only(self):
        reader = fixture(self.disk)
        report = self.collect(reader)
        self.assertEqual(report["state"], "observed", report.get("reason"))
        self.assertTrue(report["typedHpIdentityObserved"] and report["stableTwoSamples"])
        first, second = report["samples"]
        self.assertEqual(first, second)
        self.assertEqual((first["hpKey"], first["mappedIndex"], first["metadataRegenerateType"]), (37, 3, 2))
        self.assertEqual((first["rawMetadataKeyU32"], first["rawStringKey"]), (0x12345678, "Hp"))
        self.assertEqual(first["entry"]["currentStoredI64"], 250000)
        self.assertEqual(first["entry"]["baseI64"], 300000)
        self.assertEqual(first["entry"]["normI64"], 0)
        self.assertEqual(first["entry"]["field30I64"], 700000)
        self.assertEqual(first["entry"]["updateCounterU64"], 17)
        self.assertEqual(len(bytes.fromhex(first["entry"]["raw90Hex"])), 0x90)
        self.assertFalse(report["hudReady"] or report["projectedCurrentVerified"] or report["maximumVerified"] or report["unitsVerified"])
        self.assertFalse(any("ratio" in key.lower() or key in ("current", "maximum") for key in first["entry"]))
        records = [(at, size) for at, size in reader.reads if ROOT_DATA <= at < ROOT_DATA+7*0x90]
        self.assertEqual({at for at, size in records if size==0x90}, {ENTRY})
        self.assertEqual(sum(size==0x90 for _, size in records), 4)
        self.assertNotIn((ADDR["root"]+0x64, 4), reader.reads)

    def test_03_every_code_window_and_named_category_fail_before_heap(self):
        locations = [rva for rva, _, _ in probe.WINDOWS]+[probe.COUNTER_WINDOW[0], probe.HP_NAME]
        for rva in locations:
            reader = fixture(self.disk)
            reader.segments[BASE+rva][0] ^= 1
            report = self.collect(reader)
            self.assert_unavailable(report)
            self.assertEqual(report["samples"], [])
            self.assertFalse(any(at < BASE for at, _ in reader.reads))

    def test_04_wrong_status_or_manager_types_stop_before_member_interpretation(self):
        for kind, forbidden in (("status", ADDR["status"]+0x18), ("characterMetadata", ADDR["characterMetadata"]+0x58),
                                ("statusMetadata", ADDR["statusMetadata"]+0xa0), ("groupMetadata", ADDR["groupMetadata"]+0x58)):
            reader = fixture(self.disk)
            reader.put(ADDR[kind], BASE+0x800000)
            self.assert_unavailable(self.collect(reader))
            self.assertFalse(any(at==forbidden for at, _ in reader.reads))

    def test_05_primary_locator_and_controlled_actor_rtti_fail_closed(self):
        for offset, value in ((0, 0), (4, 8), (8, 1), (12, self.disk.length), (20, 0)):
            reader = fixture(self.disk)
            reader.put(BASE+0x102100+offset, value, "<I")
            self.assert_unavailable(self.collect(reader))
        reader = fixture(self.disk)
        reader.segments[BASE+0x102200+16][5] ^= 1
        self.assert_unavailable(self.collect(reader))

    def test_06_all_control_status_root_backlinks_are_required(self):
        for address in (ADDR["user"]+0xd0, ADDR["user"]+0xd8, ADDR["actor"]+0xa0, ADDR["status"]+8, ADDR["root"]):
            reader = fixture(self.disk)
            reader.put(address, 0x50000)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ENTRY, 0x90), reader.reads)

    def test_07_null_and_sentinel_loaded_metadata_do_not_fallback(self):
        changes = [(ADDR["statusMetadata"]+0xa0, 0xffff, "<H"), (ADDR["status"]+0x30, 0xffff, "<H"),
                   (ADDR["characterRecord"]+0x5b8, 0xffff, "<H"),
                   (ADDR["statusTable"]+HP*8, 0, "<Q"), (ADDR["characterTable"]+CHARACTER*8, 0, "<Q"),
                   (ADDR["groupTable"]+GROUP*8, 0, "<Q")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            reader.put(address, value, fmt)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ENTRY, 0x90), reader.reads)

    def test_08_manager_key_bounds_and_serialized_key_is_not_ordinal(self):
        for kind, key in (("statusMetadata", HP), ("characterMetadata", CHARACTER), ("groupMetadata", GROUP)):
            for count in (0, key, 65537):
                reader = fixture(self.disk)
                reader.put(ADDR[kind]+8, count, "<I")
                self.assert_unavailable(self.collect(reader))
        for raw_key in (0, HP, HP+0x10000, 0xffffffff):
            reader = fixture(self.disk)
            reader.put(ADDR["statusRecord"], raw_key, "<I")
            report = self.collect(reader)
            self.assertEqual(report["state"], "observed", report.get("reason"))
            self.assertEqual(report["samples"][0]["rawMetadataKeyU32"], raw_key)

    def test_09_regenerate_mode_and_qii_bounds(self):
        changes = [(ADDR["statusRecord"]+0x11, 0, "<B"), (ADDR["statusRecord"]+0x14, 9, "<I")]
        for offset in (0x18, 0x58):
            changes += [(ADDR["groupRecord"]+offset+8, 0, "<I"), (ADDR["groupRecord"]+offset+12, 0, "<I"),
                        (ADDR["groupRecord"]+offset+12, 65537, "<I")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            reader.put(address, value, fmt)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ENTRY, 0x90), reader.reads)

    def test_10_signed_mapping_root_bounds_and_regenerate_key(self):
        changes = [(ADDR["map"]+MAP_SLOT*4, value, "<i") for value in (-1, -2147483648, 7, 65536)]
        changes += [(ADDR["root"]+0x60, value, "<I") for value in (0, 3, 65537)]
        changes += [(ADDR["regen"]+MAPPED*2, HP+1, "<H"), (ADDR["groupRecord"]+0x20, MAPPED, "<I")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            reader.put(address, value, fmt)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ENTRY, 0x90), reader.reads)

    def test_11_entry_key_short_record_and_canonical_arithmetic(self):
        reader = fixture(self.disk)
        reader.put(ENTRY, HP+1, "<H")
        self.assert_unavailable(self.collect(reader))
        reader = fixture(self.disk)
        reader.segments[ENTRY] = reader.segments[ENTRY][:-1]
        self.assert_unavailable(self.collect(reader))
        for pointer in (0, 0x400003, 2**47, 2**47-8):
            reader = fixture(self.disk)
            reader.put(ADDR["root"]+0x58, pointer)
            self.assert_unavailable(self.collect(reader))
            self.assertFalse(any(at >= 2**47 for at, _ in reader.reads))

    def test_12_each_dependency_mutated_on_reread_invalidates_sample(self):
        baseline = self.collect(fixture(self.disk))
        for dependency in baseline["samples"][0]["dependencies"]:
            reader = fixture(self.disk)
            target, size = int(dependency["address"], 16), dependency["size"]
            original_read, seen = reader.read, 0
            def changing(address, count):
                nonlocal seen
                raw = original_read(address, count)
                if (address, count)==(target, size):
                    seen += 1
                    if seen == 2 and raw:
                        return bytes([raw[0]^1])+raw[1:]
                return raw
            reader.read = changing
            with self.subTest(field=dependency["field"]):
                self.assert_unavailable(self.collect(reader))

    def test_13_two_samples_detect_owner_metadata_stored_timing_and_counter_changes(self):
        changes = [(ADDR["actor"]+0xa0, 0x90000, "<Q"), (ADDR["statusMetadata"]+0xa0, HP+1, "<H"),
                   (ADDR["statusRecord"]+0x11, 1, "<B"), (ENTRY+8, 249000, "<q"),
                   (ENTRY+0x10, 123456790, "<Q"), (ENTRY+0x48, 18, "<Q"), (ENTRY+0x53, 1, "<B")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            report = self.collect(reader, pause=lambda _: reader.put(address, value, fmt))
            self.assert_unavailable(report)
            self.assertEqual(report["state"], "unstable")

    def test_14_process_creation_module_change_and_exit_clear_success(self):
        before = identity(self.disk)
        for after in (identity(self.disk, pid=43211), identity(self.disk, creationTime100ns="1234567890123457"),
                      identity(self.disk, moduleBase=BASE+0x1000), identity(self.disk, imagePath="other.exe"),
                      probe.ProbeError("Process exited")):
            self.assert_unavailable(self.collect(fixture(self.disk), identities=[before, after]))

    def test_15_read_failures_at_every_record_field_never_claim_observed(self):
        for target in ((ENTRY, 0x90), (ENTRY+0x48, 8), (ADDR["statusRecord"]+0x11, 1),
                       (ADDR["map"]+MAP_SLOT*4, 4), (ADDR["regen"]+MAPPED*2, 2)):
            for replacement in (None, b"", OSError("unavailable")):
                reader = fixture(self.disk)
                original = reader.read
                def failing(address, size):
                    if (address, size)==target:
                        if isinstance(replacement, Exception):
                            raise replacement
                        return replacement
                    return original(address, size)
                reader.read = failing
                self.assert_unavailable(self.collect(reader))

    def test_16_same_reader_handle_process_times_liveness_and_no_open(self):
        reader = fixture(self.disk)
        kernel = mock.Mock()
        def live(handle, result):
            self.assertEqual(handle, 12345)
            result._obj.value = 259
            return 1
        def times(handle, created, exited, kt, ut):
            self.assertEqual(handle, 12345)
            created._obj.dwLowDateTime, created._obj.dwHighDateTime = 7, 1
            return 1
        kernel.GetExitCodeProcess.side_effect = live
        kernel.GetProcessTimes.side_effect = times
        kernel.GetProcessId.return_value = 43210
        with mock.patch.object(probe.core, "k32", kernel):
            result = probe.process_identity(reader)
        self.assertEqual(result["creationTime100ns"], str(2**32+7))
        self.assertEqual(kernel.GetExitCodeProcess.call_count, 2)
        kernel.OpenProcess.assert_not_called()
        for failure in ("exit", "times", "pid", "creation"):
            kernel.GetProcessTimes.side_effect = times
            kernel.GetProcessTimes.return_value = 1
            kernel.GetProcessId.return_value = 43210
            kernel.GetExitCodeProcess.side_effect = live
            if failure=="exit":
                kernel.GetExitCodeProcess.side_effect = lambda handle, out: setattr(out._obj, "value", 0) or 1
            elif failure=="times":
                kernel.GetProcessTimes.side_effect = lambda *args: 0
            elif failure=="pid":
                kernel.GetProcessId.return_value = 0
            else:
                kernel.GetProcessTimes.side_effect = lambda *args: 1
            with mock.patch.object(probe.core, "k32", kernel), self.assertRaises(probe.ProbeError):
                probe.process_identity(reader)

    def test_17_main_final_exe_or_session_loss_retains_failure_and_closes_reader(self):
        for last in ("digest", "session", "exit"):
            reader = fixture(self.disk)
            with tempfile.TemporaryDirectory(prefix="health-main-", dir=probe.ROOT/"runtime") as temporary:
                output = Path(temporary)/"new.json"
                identities = [identity(self.disk), identity(self.disk), identity(self.disk)]
                digests = [probe.roster.SHA256]*2
                if last=="digest":
                    digests[1] = "0"*64
                elif last=="session":
                    identities[2] = identity(self.disk, creationTime100ns="999")
                else:
                    identities[2] = probe.ProbeError("Reader exited")
                with mock.patch("sys.argv", ["probe_health", "--pid", "43210", "--output", str(output)]), \
                        mock.patch.object(probe.core, "Reader", return_value=reader), \
                        mock.patch.object(probe, "process_identity", side_effect=identities), \
                        mock.patch.object(probe.subprocess, "check_output", return_value=probe.roster.VERSION), \
                        mock.patch.object(probe.appearance, "file_digest", side_effect=digests), mock.patch("builtins.print"):
                    self.assertEqual(probe.main(), 1)
                self.assert_unavailable(json.loads(output.read_bytes()))
                reader.close.assert_called_once()

    def test_18_fresh_runtime_output_required_before_process_open(self):
        with tempfile.TemporaryDirectory(prefix="health-output-", dir=probe.ROOT/"runtime") as temporary:
            output = Path(temporary)/"existing.json"
            output.write_bytes(b"preserve")
            for path in (output, probe.ROOT/"build/health-private.json"):
                with mock.patch("sys.argv", ["probe_health", "--pid", "43210", "--output", str(path)]), \
                        mock.patch.object(probe.core, "Reader") as opened, self.assertRaises(RuntimeError):
                    probe.main()
                opened.assert_not_called()
            self.assertEqual(output.read_bytes(), b"preserve")

    def test_19_only_exact_hp_string_key_and_bounded_nul_are_admitted(self):
        for raw in (b"hp\0", b"HP\0", b"Fatal\0", b"HpExtra\0", b"\0", b"Hp", b"H"*64, b"\xff\0"):
            reader = fixture(self.disk)
            reader.segments[STRING_CHARS] = bytearray(raw)
            report = self.collect(reader)
            self.assert_unavailable(report)
            self.assertNotIn((ENTRY, 0x90), reader.reads)
            self.assertNotIn((ADDR["statusRecord"]+0x11, 1), reader.reads)
            self.assertFalse(any(STRING_CHARS+64 <= at < STRING_CHARS+1000 for at, _ in reader.reads))
        reader = fixture(self.disk)
        reader.segments[STRING_CHARS] = bytearray(b"Hp\0UNREAD")
        self.assertEqual(self.collect(reader)["state"], "observed")
        self.assertFalse(any(STRING_CHARS+3 <= at < STRING_CHARS+10 for at, _ in reader.reads))

    def test_20_string_key_missing_holder_chars_and_address_overflow(self):
        for address, value in ((ADDR["statusRecord"]+8, 0), (ADDR["statusRecord"]+8, STRING_HOLDER+3),
                               (STRING_HOLDER, 0), (STRING_HOLDER, 2**47), (STRING_HOLDER, 2**47-1)):
            reader = fixture(self.disk)
            reader.put(address, value)
            self.assert_unavailable(self.collect(reader))
            self.assertNotIn((ENTRY, 0x90), reader.reads)
        reader = fixture(self.disk)
        del reader.segments[STRING_HOLDER]
        self.assert_unavailable(self.collect(reader))

    def test_21_full_string_key_dependencies_and_raw_key_resampled(self):
        changes = [(ADDR["statusRecord"], 0x23456789, "<I"), (ADDR["statusRecord"]+8, STRING_HOLDER+8, "<Q"),
                   (STRING_HOLDER, STRING_CHARS+1, "<Q"), (STRING_CHARS, ord('h'), "<B"), (STRING_CHARS+2, ord('x'), "<B")]
        for address, value, fmt in changes:
            reader = fixture(self.disk)
            report = self.collect(reader, pause=lambda _: reader.put(address, value, fmt))
            self.assert_unavailable(report)
            self.assertEqual(report["state"], "unstable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="fixed original EXE; otherwise use runtime installation gameRoot")
    args = parser.parse_args()
    path = args.exe
    if path is None:
        installation = json.loads((probe.ROOT/"runtime/installation.json").read_text(encoding="utf-8-sig"))
        path = Path(installation["gameRoot"])/"bin64/CrimsonDesert.exe"
    HealthChecks.exe = path
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HealthChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
