"""Check the single original-byte head companion control without a running game."""
from __future__ import annotations

import argparse
import copy
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

import prepare_steve_head_descriptor as head

native = head.native


class HeadDescriptorChecks(unittest.TestCase):
    output = head.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report, cls.files, cls.snapshot = head.load_candidate(cls.output/head.REPORT_NAME)
        cls.source = cls.files["template/"+head.SOURCE_PATH]
        cls.report_raw = (cls.output/head.REPORT_NAME).read_bytes()
        native.load_cdmw(native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")

    def test_01_pure_loader_exact_one_resource_and_original_bytes(self):
        row, = self.report["candidateResources"]
        self.assertEqual((row["kind"], row["virtualPath"], row["templatePath"]), ("prefabDescriptor", head.TARGET_PATH, head.SOURCE_PATH))
        self.assertEqual((row["archiveFlags"], row["templateArchiveFlags"]), (48, 48))
        self.assertEqual(len(self.source), 466)
        self.assertEqual(native.sha256(self.source), "d69be68d7e5592b40c601f98899465a69694eeff7213809b0063217a9faee56b")
        self.assertEqual(self.files[row["localFile"]], self.source)
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
                "import prepare_steve_head_descriptor as h;"
                "r,f,s=h.load_candidate(Path(sys.argv[1]));assert len(r['candidateResources'])==1;"
                "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.output/head.REPORT_NAME)],
                                cwd=native.ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_02_complete_native_fields_and_private_companion_naming(self):
        root = ET.fromstring(self.source)
        self.assertEqual(root.tag, "HeadPrefabData")
        expected = {
            "SkeletonVariationName": ("FileName", "1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"),
            "FacialAnimationIntensityMask": ("FileName", "bonemask_macduff.xml"),
            "FacialAnimationMask": ("FileName", "faceblendmask_base.xml"),
            "MorphTargetSet": ("FileName", "1_pc/1_phm/phm_kliff.pamt"),
            "SkeletonMorphMask": ("FileName", "morphmask_base.xml"),
            "EmotionAnimationSet": ("Name", "CD_Macduff_Emotion"),
            "FacialBlendShapeSet": ("SkeletonPath", "1_pc/1_phm/phm_01.pab"),
        }
        self.assertEqual(len(root), 7)
        for node in root:
            key, value = expected[node.tag]
            self.assertEqual(node.attrib, {key: value})
        from prepare_steve_parts_prefab import PARTS
        from prepare_steve_appearance import REPLACEMENTS
        self.assertEqual(head.TARGET_PREFAB, PARTS["head"]["target"])
        self.assertEqual(Path(head.TARGET_PREFAB).stem, REPLACEMENTS[1][1])
        self.assertEqual(head.TARGET_PATH, PARTS["head"]["target"].replace("/bin__/", "/", 1).replace(".prefab", ".prefabdata_xml"))
        refs = self.report["audit"]["externalReferences"]
        self.assertEqual(len(refs), 7)
        self.assertEqual(sum(r.get("originalIndexContainsPath") is True for r in refs), 6)
        self.assertTrue(all(r["runtimeResolutionVerified"] is False and r["payloadIncluded"] is False for r in refs))
        self.assertIsNone(next(r for r in refs if r["field"]=="EmotionAnimationSet")["nativePath"])
        self.assertFalse(self.report["audit"]["nativeNecessityOrFallbackBehaviorProven"])

    def test_03_fingerprint_and_semantic_changes_are_independently_rejected(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            head.validate_source(self.source+b"\n")
        variants = [self.source.replace(b"HeadPrefabData", b"NudePrefabData"),
                    self.source.replace(b"phm_kliff.pamt", b"phm_01.pamt"),
                    self.source.replace(b"CD_Macduff_Emotion", b"CD_PHM_Emotion"),
                    self.source.replace(b'</HeadPrefabData>', b'<Extra/></HeadPrefabData>')]
        for raw in variants:
            with self.assertRaisesRegex(ValueError, "fields"):
                head.descriptor_fields(raw)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                head.validate_source(raw)

    def test_04_wrong_report_paths_flags_hashes_and_claims_rejected(self):
        edits = [lambda r: r["candidateResources"][0].update(virtualPath="../head.prefabdata_xml"),
                 lambda r: r["candidateResources"][0].update(localFile="resources/other.prefabdata_xml"),
                 lambda r: r["candidateResources"][0].update(archiveFlags=0),
                 lambda r: r["candidateResources"][0].update(sha256="0"*64),
                 lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
                 lambda r: r["integration"].update(installed=True),
                 lambda r: r["integration"].update(installed=0)]
        with tempfile.TemporaryDirectory(prefix="steve-head-report-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (target/head.REPORT_NAME).write_bytes(head.report_bytes(report))
                with self.assertRaisesRegex(ValueError, "contract"):
                    head.load_candidate(target/head.REPORT_NAME)

    def test_05_payload_or_template_changes_rejected(self):
        with tempfile.TemporaryDirectory(prefix="steve-head-payload-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            for relative in self.files:
                path = target/relative
                raw = path.read_bytes()
                path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                with self.assertRaises(ValueError):
                    head.load_candidate(target/head.REPORT_NAME)
                path.write_bytes(raw)
            head.load_candidate(target/head.REPORT_NAME)

    def test_06_existing_output_or_old_asset_overlap_rejected_before_reads(self):
        with tempfile.TemporaryDirectory(prefix="steve-head-refuse-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)
            keep = output/"keep.txt"
            keep.write_bytes(b"preserve")
            with mock.patch.object(head, "read_source") as read, mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    head.prepare(native.ROOT/"build/unused-game", output, native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")
                read.assert_not_called()
                load.assert_not_called()
            self.assertEqual(keep.read_bytes(), b"preserve")
        for path in ("build/steve-assembly/new", "build/steve-appearance/new"):
            with self.assertRaisesRegex(ValueError, "overlaps"):
                head.prepare(native.ROOT/"build/unused-game", native.ROOT/path, native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")

    def test_07_fixed_exe_index_flags_and_changed_source_fail_closed(self):
        game = native.ROOT/"build/unused-game"
        with mock.patch.object(native, "file_hash", return_value="0"*64):
            with self.assertRaisesRegex(ValueError, "EXE"):
                head.read_source(game)
        def digest(path):
            return native.EXE_SHA256 if path.name=="CrimsonDesert.exe" else head.INDEX_SHA256
        with mock.patch.object(native, "file_hash", side_effect=digest), \
                mock.patch("cdmw.core.archive_format.parse_archive_pamt", return_value=[]), \
                mock.patch.object(native, "select_unique_entries", return_value={head.SOURCE_PATH: SimpleNamespace(flags=49)}), \
                mock.patch("cdmw.core.archive_extraction.read_archive_entry_raw_data") as payload_read:
            with self.assertRaisesRegex(ValueError, "flags"):
                head.read_source(game)
            payload_read.assert_not_called()
        with tempfile.TemporaryDirectory(prefix="steve-head-race-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)/"candidate"
            with mock.patch.object(native, "load_cdmw"), mock.patch.object(head, "read_source", side_effect=[self.source, self.source+b"x"]):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    head.prepare(game, output, native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")
            self.assertFalse(output.exists())

    def test_08_real_archive_rebuild_and_prior_assembly_appearance_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for actual fixed native extraction and all-byte comparison")
        # These are already-existing independent candidates, not inputs to the
        # descriptor generator. Capture them if present, without requiring old
        # ignored outputs to reproduce this standalone one-resource tool.
        prior = {}
        for directory in (native.ROOT/"build/steve-assembly", native.ROOT/"build/steve-appearance"):
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        native.check_links(path)
                        prior[path] = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="steve-head-rebuild-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT/"tools/prepare_steve_head_descriptor.py"), "--output", str(target)],
                                    cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, files, _ = head.load_candidate(target/head.REPORT_NAME)
            self.assertEqual((target/head.REPORT_NAME).read_bytes(), self.report_raw)
            self.assertEqual(report, self.report)
            self.assertEqual(files, self.files)
        head.orientation.verify_snapshot(prior)
        head.orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=head.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    HeadDescriptorChecks.output, HeadDescriptorChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeadDescriptorChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
