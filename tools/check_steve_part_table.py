"""Check bounded parsing, additive native registration and actual archive rebuild."""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import prepare_steve_part_table as table

native = table.native


class PartTableChecks(unittest.TestCase):
    output = table.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report, cls.payloads, cls.snapshot = table.load_candidate(cls.output/table.REPORT_NAME)
        cls.source = (cls.output/("template/"+table.TABLE_PATH)).read_bytes()
        cls.candidate = cls.payloads[table.TABLE_PATH]
        cls.original = table.parse_table(cls.source)
        cls.added = table.parse_table(cls.candidate)
        native.load_cdmw(native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")

    def test_01_pure_exact_single_resource_and_unverified_flags(self):
        row, = self.report["targetReplacements"]
        self.assertEqual(self.report["candidateResources"], [])
        self.assertEqual((row["virtualPath"], row["templatePath"], row["kind"]),
                         ("character/bin__/partprefabtable.pappt",)*2+("partPrefabTable",))
        self.assertEqual((row["archiveFlags"], row["templateArchiveFlags"]), (50, 50))
        self.assertEqual(len(self.source), 2130295)
        self.assertEqual(native.sha256(self.source), "d6947dcb57d32e0503704da28edf4645baaa8faad8fbd47d09a8a8832686abed")
        self.assertEqual(set(self.payloads), {table.TABLE_PATH})
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');import prepare_steve_part_table as t;"
                "r,p,s=t.load_candidate(Path(sys.argv[1]));assert len(p)==1;"
                "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.output/table.REPORT_NAME)], cwd=native.ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_02_every_original_row_byte_and_order_preserved_and_inverse_exact(self):
        self.assertEqual((len(self.original["records"]), len(self.original["headRecords"])), (15566, 2630))
        self.assertEqual((len(self.added["records"]), len(self.added["headRecords"])), (15568, 2632))
        self.assertEqual(self.source[:8], b"\0"*8)
        self.assertEqual(self.candidate[:8], self.source[:8])
        for section in ("records", "headRecords"):
            for original, candidate in zip(self.original[section], self.added[section]):
                self.assertEqual(self.source[original["start"]:original["end"]], self.candidate[candidate["start"]:candidate["end"]])
        restored = (self.candidate[:8]+struct.pack("<I", 15566)+self.candidate[12:self.added["records"][-2]["start"]]
                    +struct.pack("<I", 2630)+self.candidate[self.added["headCountOffset"]+4:self.added["headRecords"][-2]["start"]])
        self.assertEqual(restored, self.source)

    def test_03_cdmw_independently_decodes_and_generates_full_expected_table(self):
        from cdmw.core.pappt_format import parse_pappt, encode_pappt
        original, actual = parse_pappt(self.source), parse_pappt(self.candidate)
        self.assertEqual(original.tag_prefix, b"\x01")
        self.assertEqual(actual.records[:-2], original.records)
        self.assertEqual(actual.head_records[:-2], original.head_records)
        expected_pairs = [("cd_phm_00_nude_01_0002_macduff", "crimsonmc_steve_body_1_21_1", "1_pc/01_phm/nude"),
                          ("cd_phm_00_head_00_0001_macduff", "crimsonmc_steve_head_1_21_1", "1_pc/01_phm/head/head")]
        from prepare_steve_parts_prefab import PARTS
        for (old, new, folder), part in zip(expected_pairs, ("body", "head")):
            original_part = next(row for row in original.records if row.stem==old)
            original_head = next(row for row in original.head_records if row.stem==old)
            actual_part = [row for row in actual.records if row.stem==new]
            actual_head = [row for row in actual.head_records if row.stem==new]
            self.assertEqual(actual_part, [replace(original_part, stem=new)])
            self.assertEqual(actual_head, [replace(original_head, stem=new)])
            self.assertEqual(actual_part[0].folder, folder)
            self.assertEqual(actual_part[0].prefab_path, PARTS[part]["target"])
            self.assertEqual(actual_part[0].sockets_path, "")
            self.assertEqual(actual_part[0].extra, "")
            self.assertEqual(actual_part[0].flag, 0)
        self.assertEqual([slot.name for slot in actual.records[-2].parts], ["CD_Nude", "CD_Underwear"])
        self.assertEqual([slot.name for slot in actual.records[-1].parts],
                         ["CD_Head", "CD_EyeLeft", "CD_EyeRight", "CD_Eyebrows", "CD_Eyelashes", "CD_Tooth", "CD_Nude_Hair"])
        self.assertEqual(encode_pappt(original), self.source)
        self.assertEqual(encode_pappt(actual), self.candidate)
        table.verify_cdmw(self.source, self.candidate)

    def test_04_bounded_parser_rejects_bad_lengths_counts_tags_and_trailing_data(self):
        def changed(offset, value):
            return self.source[:offset]+value+self.source[offset+len(value):]
        first = self.original["records"][0]
        reader = table.Reader(self.source)
        reader.pos = first["start"]
        for _ in range(3):
            reader.string()
        bad = [b"", self.source[:15], self.source[:-1], self.source+b"x", b"x"*(table.SOURCE_SIZE+4097),
               changed(0, b"\x01"), changed(8, struct.pack("<I", 20001)), changed(8, b"\0"*4),
               changed(self.original["headCountOffset"], struct.pack("<I", 4097)),
               changed(first["start"], b"\0"), changed(first["stemEnd"]-1, b"x"),
               changed(first["start"]+1, b"\xff"), changed(reader.pos, b"\0")]
        for index, payload in enumerate(bad):
            with self.subTest(case=index), self.assertRaises(ValueError):
                table.parse_table(payload)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            table.validate_source(self.candidate)
        for stem in ("", "../bad", "bad\\stem", "x\0y", "x"*255):
            with self.assertRaisesRegex(ValueError, "stem"):
                table.clone_row(self.source, first, stem)

    def test_05_report_paths_claims_counts_metadata_and_duplicate_resources_refused(self):
        edits = [lambda r: r["targetReplacements"][0].update(virtualPath="../other.pappt"),
                 lambda r: r["targetReplacements"][0].update(localFile="replacements/other.pappt"),
                 lambda r: r["targetReplacements"][0].update(archiveFlags=48),
                 lambda r: r["targetReplacements"][0].update(sha256="0"*64),
                 lambda r: r["targetReplacements"].append(copy.deepcopy(r["targetReplacements"][0])),
                 lambda r: r["candidateResources"].append(copy.deepcopy(r["targetReplacements"][0])),
                 lambda r: r["integration"].update(runtimePartTableLoaded=True),
                 lambda r: r["integration"].update(installed=0),
                 lambda r: r["audit"]["partCounts"].update(after=15567),
                 lambda r: r["audit"]["addedRegistrations"][0]["partRecord"].update(sockets_path="fabricated.xml"),
                 lambda r: r.update(supportedExeSha256="0"*64)]
        with tempfile.TemporaryDirectory(prefix="steve-table-report-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (target/table.REPORT_NAME).write_bytes(table.report_bytes(report))
                with self.assertRaisesRegex(ValueError, "contract"):
                    table.load_candidate(target/table.REPORT_NAME)

    def test_06_payload_original_row_or_added_metadata_tampering_refused(self):
        with tempfile.TemporaryDirectory(prefix="steve-table-payload-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            payload_path = target/("replacements/"+table.TABLE_PATH)
            # Mutations include an original row and the appended body part flag.
            for offset in (12, self.added["records"][-2]["end"]-1, self.added["headRecords"][-1]["stemEnd"]-2):
                changed = bytearray(self.candidate)
                changed[offset] ^= 1
                payload_path.write_bytes(changed)
                with self.assertRaisesRegex(ValueError, "four appended rows"):
                    table.load_candidate(target/table.REPORT_NAME)
            payload_path.write_bytes(self.candidate)
            template_path = target/("template/"+table.TABLE_PATH)
            template_path.write_bytes(self.source[:-1]+bytes([self.source[-1]^1]))
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                table.load_candidate(target/table.REPORT_NAME)

    def test_07_fresh_output_overlap_and_archive_gates_before_publication(self):
        source, deps, game = (native.ROOT/relative for relative in ("build/cdmw-fixed-source", "build/cdmw-deps", "build/unused-game"))
        with tempfile.TemporaryDirectory(prefix="steve-table-existing-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)
            (output/"sentinel").write_bytes(b"retain")
            with mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    table.prepare(game, output, source, deps)
                load.assert_not_called()
            self.assertEqual((output/"sentinel").read_bytes(), b"retain")
        for directory in ("steve-assembly", "steve-appearance", "steve-head-descriptor", "steve-app-macduff-00000", "steve-app-macduff-00002"):
            with mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    table.prepare(game, native.ROOT/("build/"+directory+"/new"), source, deps)
                load.assert_not_called()
        for failing in ("exe", "index"):
            def digest(path):
                if path.name=="CrimsonDesert.exe":
                    return "0"*64 if failing=="exe" else native.EXE_SHA256
                return "0"*64 if failing=="index" else table.INDEX_SHA256
            with mock.patch.object(native, "file_hash", side_effect=digest):
                with self.assertRaisesRegex(ValueError, "EXE or original 0009"):
                    table.read_source(game)
        def correct_digest(path):
            return native.EXE_SHA256 if path.name=="CrimsonDesert.exe" else table.INDEX_SHA256
        with mock.patch.object(native, "file_hash", side_effect=correct_digest), \
                mock.patch("cdmw.core.archive_format.parse_archive_pamt", return_value=[]), \
                mock.patch.object(native, "select_unique_entries", return_value={table.TABLE_PATH: SimpleNamespace(flags=48)}), \
                mock.patch("cdmw.core.archive_extraction.read_archive_entry_raw_data") as read:
            with self.assertRaisesRegex(ValueError, "flags"):
                table.read_source(game)
            read.assert_not_called()
        with tempfile.TemporaryDirectory(prefix="steve-table-change-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)/"fresh"
            with mock.patch.object(native, "load_cdmw"), mock.patch.object(table, "read_source", side_effect=[self.source, self.source+b"x"]):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    table.prepare(game, output, source, deps)
            self.assertFalse(output.exists())

    def test_08_real_rebuild_and_prior_candidates_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for fixed archive extraction and deterministic full-byte rebuild")
        prior = {}
        for name in ("steve-assembly", "steve-appearance", "steve-head-descriptor", "steve-app-macduff-00000", "steve-app-macduff-00002"):
            directory = native.ROOT/("build/"+name)
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        native.check_links(path)
                        prior[path] = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="steve-table-rebuild-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT/"tools/prepare_steve_part_table.py"), "--output", str(target)],
                                    cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, payloads, _ = table.load_candidate(target/table.REPORT_NAME)
            self.assertEqual((target/table.REPORT_NAME).read_bytes(), (self.output/table.REPORT_NAME).read_bytes())
            self.assertEqual((report, payloads), (self.report, self.payloads))
        table.orientation.verify_snapshot(prior)
        table.orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=table.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    PartTableChecks.output, PartTableChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PartTableChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
