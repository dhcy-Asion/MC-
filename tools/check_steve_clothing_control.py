"""Check the exact reversible empty default-Armor app in isolated build copies.

Rebuild reads one pinned original archive entry. No test installs a package,
accesses a process, starts a service or changes inventory or personal saves.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_clothing_control as clothing

native, ROOT = clothing.native, clothing.ROOT
SOURCE_SHA256 = "945e25586db2d50a83b4dd5227ab89a8e5db8c7937abd404470e52ae5b9edffe"
PAYLOAD_SHA256 = "2b172fc5e2287b9cb7afde9c1e03a0842f99d1ed15cd3518ee269f9a42cb17d2"


class ClothingChecks(unittest.TestCase):
    output = clothing.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output)
        cls.report_path = cls.output / clothing.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = clothing.load_candidate(cls.report_path)
        cls.source = (cls.output / ("template/" + clothing.TARGET_PATH)).read_bytes()
        cls.payload = cls.payloads[clothing.TARGET_PATH]
        native.load_cdmw(ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps")

    def copied_candidate(self, temporary):
        output = Path(temporary) / "copy"
        shutil.copytree(self.output, output)
        return output

    def test_01_one_fixed_original_app_and_exact_eight_field_replacement(self):
        self.assertEqual((len(self.source), hashlib.sha256(self.source).hexdigest()), (1117, SOURCE_SHA256))
        self.assertEqual((len(self.payload), hashlib.sha256(self.payload).hexdigest()), (523, PAYLOAD_SHA256))
        path = "character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml"
        self.assertEqual(self.report["candidateResources"], [])
        self.assertEqual(self.report["targetReplacements"], [{"virtualPath": path,
            "localFile": "replacements/" + path, "sha256": PAYLOAD_SHA256,
            "kind": "appearanceDefinition", "templatePath": path, "templateSha256": SOURCE_SHA256,
            "templateArchiveFlags": 48, "archiveFlags": 48}])
        self.assertEqual(set(self.payloads), {path})
        self.assertTrue(all(type(value) is bool and value is False for value in self.report["integration"].values()))
        self.assertFalse(self.report["referenceScope"]["controlledActorOnly"])
        self.assertFalse(self.report["referenceScope"]["dynamicEquipmentStateDecoded"])

    def test_02_independent_contiguous_deletion_inverse_and_remaining_xml_bytes(self):
        # The independent fixed offsets include only twelve original Prefab lines.
        removed = self.source[499:1093]
        self.assertEqual(len(removed), 594)
        self.assertEqual(len(removed.splitlines()), 12)
        self.assertEqual(self.payload, self.source[:499] + self.source[1093:])
        self.assertEqual(self.payload[:499] + removed + self.payload[499:], self.source)
        self.assertTrue(self.payload.startswith(b"\xef\xbb\xbf<Appearance>\r\n"))
        self.assertEqual(self.payload.count(b"\r\n"), self.source.count(b"\r\n") - 12)
        self.assertNotIn(b"<?xml", self.payload)
        original, candidate = ET.fromstring(self.source), ET.fromstring(self.payload)
        self.assertEqual([node.tag for node in candidate], ["Customization", "Nude", "Head", "Hair", "Armor"])
        self.assertEqual(len(original.findall("Armor/Prefab")), 12)
        self.assertEqual(sum(node.get("Preview") == "true" for node in original.findall("Armor/Prefab")), 4)
        self.assertEqual(len(candidate.find("Armor")), 0)
        self.assertEqual(candidate.find("Armor").attrib, {})
        for section in ("Customization", "Nude", "Head", "Hair"):
            self.assertEqual(ET.tostring(original.find(section)), ET.tostring(candidate.find(section)))
        self.assertEqual(candidate.find("Nude/Prefab").attrib,
                         {"Name": "cd_phm_00_nude_01_0002_macduff", "CharacterScale": "1.02571"})
        self.assertEqual(candidate.find("Head/Prefab").attrib,
                         {"Name": "cd_phm_00_head_00_0001_macduff", "HeadScale": "0.92"})
        self.assertEqual([node.get("Name") for node in candidate.findall("Hair/Prefab")],
                         ["cd_phm_00_hair_00_0022_player", "cd_phm_00_beard_00_0005_06_player"])

    def test_03_pure_loader_reads_only_package_with_absolute_path_snapshots(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "import prepare_steve_clothing_control as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('native read'));"
            "c.read_source=forbidden;c.native.load_cdmw=forbidden;"
            "r,p,s=c.load_candidate(Path(sys.argv[1]));assert len(p)==1 and len(s)==3;"
            "assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.report_path)],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.snapshot), 3)
        clothing.orientation.verify_snapshot(self.snapshot)

    def test_04_other_app_already_rewritten_app_and_outside_changes_refused(self):
        other = clothing.app.default_output("macduff-00002") / ("template/" + clothing.app.VARIANTS["macduff-00002"]["path"])
        for raw in (other.read_bytes(), clothing.app.build_app(self.source, "macduff-00000"),
                    self.source.replace(b'HeadScale="0.92"', b'HeadScale="1.00"'),
                    self.source.replace(b'cd_phm_00_hair_00_0022_player', b'cd_phm_00_hair_00_0008_player')):
            with self.subTest(digest=hashlib.sha256(raw).hexdigest()), self.assertRaisesRegex(ValueError, "fingerprint"):
                clothing.build_app(raw)

    def test_05_manifest_paths_flags_scope_claims_and_duplicate_keys_fail_closed(self):
        edits = [lambda r: r.update(unreviewedField=True), lambda r: r.update(appearanceVariant="macduff-00002"),
            lambda r: r["targetReplacements"][0].update(localFile="../escape"),
            lambda r: r["targetReplacements"][0].update(virtualPath="character/another.app_xml"),
            lambda r: r["targetReplacements"][0].update(templatePath="../escape"),
            lambda r: r["targetReplacements"][0].update(templateArchiveFlags=50),
            lambda r: r["targetReplacements"][0].update(archiveFlags=50),
            lambda r: r["targetReplacements"][0].update(kind="partPrefabTable"),
            lambda r: r["targetReplacements"].append(copy.deepcopy(r["targetReplacements"][0])),
            lambda r: r["candidateResources"].append(copy.deepcopy(r["targetReplacements"][0])),
            lambda r: r["sourceHashes"].update({clothing.TARGET_PATH: "0" * 64}),
            lambda r: r["referenceScope"].update(controlledActorOnly=True),
            lambda r: r["integration"].update(dynamicEquipmentSuppressed=True),
            lambda r: r["integration"].update(installed=0),
            lambda r: r["audit"].update(removedPrefabCount=8)]
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-manifest-") as temporary:
            output = self.copied_candidate(temporary)
            report_path = output / clothing.REPORT_NAME
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                report_path.write_bytes(clothing.report_bytes(report))
                with self.subTest(edit=repr(edit)), self.assertRaises(ValueError):
                    clothing.load_candidate(report_path)
            report_path.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}')
            with self.assertRaises(ValueError):
                clothing.load_candidate(report_path)
        with self.assertRaises(ValueError):
            clothing.load_candidate(ROOT / "docs" / clothing.REPORT_NAME)

    def test_06_payload_template_and_updated_inner_hashes_cannot_relabel_tamper(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-payload-") as temporary:
            output = self.copied_candidate(temporary)
            report_path = output / clothing.REPORT_NAME
            for relative in self.report["files"]:
                target = output / relative
                old = target.read_bytes()
                target.write_bytes(old[:-1] + bytes([old[-1] ^ 1]))
                altered = copy.deepcopy(self.report)
                altered["files"][relative] = native.file_hash(target)
                if relative.startswith("replacements/"):
                    altered["targetReplacements"][0]["sha256"] = native.file_hash(target)
                else:
                    altered["sourceHashes"][clothing.TARGET_PATH] = native.file_hash(target)
                    altered["targetReplacements"][0]["templateSha256"] = native.file_hash(target)
                report_path.write_bytes(clothing.report_bytes(altered))
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    clothing.load_candidate(report_path)
                target.write_bytes(old)
                report_path.write_bytes(self.report_raw)
            report_path.write_bytes(json.dumps(self.report, separators=(",", ":")).encode())
            with self.assertRaises(ValueError):
                clothing.load_candidate(report_path)

    def test_07_stale_snapshot_and_oversized_report_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-snapshot-") as temporary:
            output = self.copied_candidate(temporary)
            _, _, snapshot = clothing.load_candidate(output / clothing.REPORT_NAME)
            target = output / self.report["targetReplacements"][0]["localFile"]
            old = target.read_bytes()
            target.write_bytes(old[:-1] + bytes([old[-1] ^ 1]))
            with self.assertRaisesRegex(ValueError, "changed"):
                clothing.orientation.verify_snapshot(snapshot)
            (output / clothing.REPORT_NAME).write_bytes(b"x" * (131072 + 1))
            with self.assertRaisesRegex(ValueError, "size"):
                clothing.load_candidate(output / clothing.REPORT_NAME)

    def test_08_existing_and_input_overlapping_outputs_refused_before_native_reads(self):
        source, deps, game = (ROOT / relative for relative in
                            ("build/cdmw-fixed-source", "build/cdmw-deps", "build/unused-game"))
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-refuse-") as temporary:
            output = Path(temporary)
            sentinel = output / "keep"
            sentinel.write_bytes(b"preserve")
            with mock.patch.object(clothing, "read_source") as read, mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    clothing.prepare(output, source, deps, game)
                read.assert_not_called()
                load.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertEqual({path.name for path in output.iterdir()}, {"keep"})
        for relative in ("build/steve-appearance/new", "build/steve-assembly/new", "build/steve-head-descriptor/new",
                         "build/steve-part-table-v2/new", "build/steve-app-macduff-00000/new",
                         "build/steve-head-native-material-probe-overlay/new", "build/cdmw-deps/new",
                         "build/unused-game/new"):
            with mock.patch.object(clothing, "read_source") as read, mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    clothing.prepare(ROOT / relative, source, deps, game)
                read.assert_not_called()
                load.assert_not_called()

    def test_09_source_reader_fixed_gates_and_prepublication_source_race(self):
        from cdmw.core import archive_format, archive_extraction
        game = ROOT / "build/unused-game"
        for failing in ("exe", "index"):
            def bad_digest(path):
                if Path(path).name == "CrimsonDesert.exe":
                    return "0" * 64 if failing == "exe" else native.EXE_SHA256
                return "0" * 64 if failing == "index" else clothing.INDEX_SHA256
            with mock.patch.object(native, "file_hash", side_effect=bad_digest), self.assertRaisesRegex(ValueError, "EXE or original 0009"):
                clothing.read_source(game)
        good_digest = lambda path: native.EXE_SHA256 if Path(path).name == "CrimsonDesert.exe" else clothing.INDEX_SHA256
        with mock.patch.object(native, "file_hash", side_effect=good_digest), \
             mock.patch.object(archive_format, "parse_archive_pamt", return_value=[]), \
             mock.patch.object(native, "select_unique_entries", return_value={clothing.TARGET_PATH: SimpleNamespace(flags=50)}), \
             mock.patch.object(archive_extraction, "read_archive_entry_raw_data") as payload_read:
            with self.assertRaisesRegex(ValueError, "flags"):
                clothing.read_source(game)
            payload_read.assert_not_called()
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-race-") as temporary:
            output = Path(temporary) / "fresh"
            with mock.patch.object(native, "load_cdmw"), mock.patch.object(clothing, "read_source", side_effect=[self.source, self.source + b"changed"]):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    clothing.prepare(output, ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps", game)
            self.assertFalse(output.exists())

    def test_10_real_fixed_archive_rebuild_is_identical_and_old_inputs_stay_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for the gated original 00000 archive generation")
        protected = {}
        for directory in (clothing.app.default_output("macduff-00000"), clothing.app.default_output("macduff-00002"),
                          ROOT / "build/steve-appearance", ROOT / "build/steve-head-native-material"):
            for path in directory.rglob("*"):
                if path.is_file():
                    native.check_links(path)
                    protected[path] = path.read_bytes()
        with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="clothing-rebuild-") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/prepare_steve_clothing_control.py"),
                                     "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, payloads, _ = clothing.load_candidate(output / clothing.REPORT_NAME)
            self.assertEqual((output / clothing.REPORT_NAME).read_bytes(), self.report_raw)
            self.assertEqual((report, payloads), (self.report, self.payloads))
        clothing.orientation.verify_snapshot(self.snapshot)
        clothing.orientation.verify_snapshot(protected)
        native.verify_source(ROOT / "build/cdmw-fixed-source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=clothing.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    ClothingChecks.output, ClothingChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClothingChecks))
    if result.wasSuccessful():
        print(json.dumps({"targetReplacements": ClothingChecks.report["targetReplacements"],
                          "removedPrefabCount": 12, "clothingVisibilityVerified": False,
                          "dynamicEquipmentProhibited": False}, indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
