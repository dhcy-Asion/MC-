"""Isolated checks for the exact shared meshparam replacement and pure loader."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_appearance as appearance


class AppearanceChecks(unittest.TestCase):
    output = appearance.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = appearance.native.output_directory(cls.output)
        cls.report_path = cls.output / appearance.REPORT_NAME
        cls.report, cls.payloads, cls.snapshot = appearance.load_candidate(cls.report_path)
        cls.report_raw = cls.report_path.read_bytes()
        cls.source = (cls.output / "template" / appearance.TARGET_PATH).read_bytes()
        cls.candidate = cls.payloads[appearance.TARGET_PATH]

    def copy_candidate(self, folder):
        for relative in self.report["files"]:
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.output / relative).read_bytes())
        path = folder / appearance.REPORT_NAME
        path.write_bytes(self.report_raw)
        return path

    def test_01_exact_one_target_and_no_existing_path_in_private_resource_inventory(self):
        self.assertEqual(self.report["candidateResources"], [])
        self.assertEqual(len(self.report["targetReplacements"]), 1)
        row = self.report["targetReplacements"][0]
        self.assertEqual(set(row), {"virtualPath", "localFile", "sha256", "kind", "templatePath", "templateSha256"})
        self.assertEqual(row["virtualPath"], appearance.TARGET_PATH)
        self.assertEqual(row["templatePath"], appearance.TARGET_PATH)
        self.assertEqual(row["templateSha256"], appearance.TARGET_SHA256)
        self.assertEqual(row["kind"], "appearanceMeshParams")
        self.assertEqual(self.report["requiredPrivatePrefabBasenames"], ["crimsonmc_steve_body_1_21_1", "crimsonmc_steve_head_1_21_1"])
        for relative, digest in self.report["files"].items():
            self.assertEqual(appearance.native.file_hash(self.output / relative), digest)

    def test_02_independent_exact_attribute_byte_edits_and_inverse(self):
        source, candidate = self.source, self.candidate
        old = [b'cd_phm_00_nude_01_0002_macduff', b'cd_phm_00_head_00_0001_macduff']
        new = [b'crimsonmc_steve_body_1_21_1', b'crimsonmc_steve_head_1_21_1']
        expected, restored = source, candidate
        for a, b in zip(old, new):
            self.assertEqual(source.count(a), 1)
            self.assertEqual(candidate.count(b), 1)
            at = expected.index(b'MeshFileName="'+a+b'"')+len(b'MeshFileName="')
            expected = expected[:at]+b+expected[at+len(a):]
            restored = restored.replace(b, a)
        self.assertEqual(candidate, expected)
        self.assertEqual(restored, source)

    def test_03_all_other_xml_attributes_groups_options_and_text_remain_identical(self):
        before, after = ET.fromstring(self.source.decode()), ET.fromstring(self.candidate.decode())
        self.assertEqual(len(list(before.iter())), len(list(after.iter())))
        differences = []
        for a, b in zip(before.iter(), after.iter()):
            self.assertEqual((a.tag, a.text, a.tail), (b.tag, b.text, b.tail))
            self.assertEqual(set(a.attrib), set(b.attrib))
            for key in a.attrib:
                if a.attrib[key] != b.attrib[key]:
                    differences.append((a.tag, key, a.attrib[key], b.attrib[key]))
        self.assertEqual(differences, [("MeshList", "MeshFileName", a, b) for a, b in appearance.REPLACEMENTS])
        groups = after.findall("ParamDesc")
        self.assertEqual([len(g.findall("MeshSet")) for g in groups], [2, 2, 7, 7, 0, 0, 0])
        self.assertEqual([g.attrib["Default"] for g in groups], ["0"]*7)
        self.assertEqual([groups[i].find("MeshSet").attrib["SkeletonVariation"] for i in range(2)], appearance.VARIATIONS)
        self.assertEqual([groups[i].find("MeshSet/MeshList").attrib["MeshFileName"] for i in (2, 3)], appearance.BASELINE_SELECTED[2:])

    def test_04_appearance_consumers_scales_and_scope_are_evidence_not_actor_local(self):
        for path in appearance.APPEARANCES:
            raw = (self.output / "template" / path).read_bytes()
            appearance.validate_appearance(raw, path)
            tree = ET.fromstring(raw.decode())
            self.assertEqual(tree.find("Nude/Prefab").attrib["CharacterScale"], "1.02571")
            self.assertEqual(tree.find("Head/Prefab").attrib["HeadScale"], "0.92")
        self.assertEqual(self.report["referenceScope"]["verifiedAppearanceConsumers"], list(appearance.APPEARANCES))
        self.assertFalse(self.report["referenceScope"]["controlledActorOnly"])
        self.assertFalse(self.report["referenceScope"]["runtimeAppearanceFileSelected"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertTrue(any("FF means fallback" in row for row in self.report["limitations"]))

    def test_05_loader_is_pure_and_returns_a_complete_read_snapshot(self):
        with mock.patch.object(appearance.native, "load_cdmw", side_effect=AssertionError("Loader must not import native archive modules")):
            report, payloads, snapshot = appearance.load_candidate(self.report_path)
        self.assertEqual(report, self.report)
        self.assertEqual(payloads, {appearance.TARGET_PATH: self.candidate})
        self.assertEqual(len(snapshot), 5)
        self.assertEqual(snapshot[self.report_path], self.report_raw)
        appearance.orientation.verify_snapshot(snapshot)

    def test_06_payload_tampering_cannot_be_authorized_by_updating_report_digests(self):
        with tempfile.TemporaryDirectory(prefix="steve-app-payload-", dir=appearance.ROOT / "build") as temporary:
            folder = Path(temporary)
            path = self.copy_candidate(folder)
            local = folder / self.report["targetReplacements"][0]["localFile"]
            changed = self.candidate.replace(b'UIKey="Hair"', b'UIKey="Hide"')
            local.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "payload differs"):
                appearance.load_candidate(path)
            report = copy.deepcopy(self.report)
            report["targetReplacements"][0]["sha256"] = appearance.native.sha256(changed)
            report["files"][report["targetReplacements"][0]["localFile"]] = appearance.native.sha256(changed)
            path.write_bytes(appearance.report_bytes(report))
            with self.assertRaisesRegex(ValueError, "report differs"):
                appearance.load_candidate(path)

    def test_07_each_source_template_is_pinned_including_known_consumers(self):
        for source_path in appearance.SOURCE_HASHES:
            with self.subTest(source=source_path), tempfile.TemporaryDirectory(prefix="steve-app-template-", dir=appearance.ROOT / "build") as temporary:
                folder = Path(temporary)
                path = self.copy_candidate(folder)
                local = folder / "template" / source_path
                local.write_bytes(local.read_bytes()+b"\n")
                with self.assertRaisesRegex(ValueError, "template fingerprint"):
                    appearance.load_candidate(path)

    def test_08_report_cannot_broaden_paths_scope_claims_or_dependencies(self):
        mutations = (
            lambda r: r["targetReplacements"][0].update(virtualPath="character/descriptors/customizationmeta/meshparam_example.xml"),
            lambda r: r["targetReplacements"][0].update(localFile="../../foreign.xml"),
            lambda r: r["targetReplacements"].append(copy.deepcopy(r["targetReplacements"][0])),
            lambda r: r["targetReplacements"][0].update(kind="texture"),
            lambda r: r.update(requiredPrivatePrefabBasenames=[]),
            lambda r: r["integration"].update(installed=True),
            lambda r: r["referenceScope"].update(controlledActorOnly=True),
            lambda r: r.update(archiveIndexSha256="0"*64),
        )
        with tempfile.TemporaryDirectory(prefix="steve-app-report-", dir=appearance.ROOT / "build") as temporary:
            folder = Path(temporary)
            path = self.copy_candidate(folder)
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    report = copy.deepcopy(self.report)
                    mutate(report)
                    path.write_bytes(appearance.report_bytes(report))
                    with self.assertRaisesRegex(ValueError, "report differs"):
                        appearance.load_candidate(path)
            path.write_bytes(self.report_raw+b"\n")
            with self.assertRaisesRegex(ValueError, "report differs"):
                appearance.load_candidate(path)

    def test_09_unreviewed_source_even_comment_change_is_rejected(self):
        for data in (self.source+b"\n", self.source.replace(b'Default = "0"', b'Default = "1"', 1), self.candidate):
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                appearance.build_meshparam(data)

    def test_10_existing_output_and_outside_build_are_rejected_before_reads(self):
        with tempfile.TemporaryDirectory(prefix="steve-app-output-", dir=appearance.ROOT / "build") as temporary:
            folder = Path(temporary)
            sentinel = folder / "keep.txt"
            sentinel.write_bytes(b"keep")
            with mock.patch.object(appearance.native, "load_cdmw", side_effect=AssertionError("No archive setup expected")):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    appearance.prepare(appearance.ROOT / "build/not-mounted-game", folder, appearance.ROOT / "build/cdmw-fixed-source", appearance.ROOT / "build/cdmw-deps")
            self.assertEqual(sentinel.read_bytes(), b"keep")
        with self.assertRaises(ValueError):
            appearance.native.output_directory(appearance.ROOT / "artifacts/appearance.json")

    def test_11_loader_refuses_oversized_report_and_payload(self):
        with tempfile.TemporaryDirectory(prefix="steve-app-size-", dir=appearance.ROOT / "build") as temporary:
            folder = Path(temporary)
            path = self.copy_candidate(folder)
            path.write_bytes(b" "*(2*1024*1024+1))
            with self.assertRaisesRegex(ValueError, "bounded file size"):
                appearance.load_candidate(path)
            path.write_bytes(self.report_raw)
            (folder / self.report["targetReplacements"][0]["localFile"]).write_bytes(b"x"*131073)
            with self.assertRaisesRegex(ValueError, "bounded file size"):
                appearance.load_candidate(path)

    def test_12_real_index_reextract_and_fresh_build_match_every_byte(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for real original-index extraction")
        with tempfile.TemporaryDirectory(prefix="steve-app-rebuild-", dir=appearance.ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(appearance.ROOT / "tools/prepare_steve_appearance.py"), "--output", str(output)],
                                    cwd=appearance.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / appearance.REPORT_NAME).read_bytes(), self.report_raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
            appearance.load_candidate(output / appearance.REPORT_NAME)
        appearance.orientation.verify_snapshot(self.snapshot)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=appearance.DEFAULT_OUTPUT)
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args()
    AppearanceChecks.output, AppearanceChecks.rebuild = a.output, a.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AppearanceChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
