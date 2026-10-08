"""Check the fixed native-head reference control without game/process access."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import prepare_steve_head_mesh_control as head

native = head.native


class HeadMeshControlChecks(unittest.TestCase):
    output = head.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report, cls.payloads, cls.snapshot = head.load_candidate(cls.output/head.REPORT_NAME)
        cls.raw_report = (cls.output/head.REPORT_NAME).read_bytes()
        cls.source = (cls.output/("template/"+head.TARGET_PATH)).read_bytes()
        cls.candidate = cls.payloads[head.TARGET_PATH]
        native.load_cdmw(native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")

    def test_01_pure_loader_one_resource_exact_identity_and_flags(self):
        row, = self.report["candidateResources"]
        self.assertEqual(set(self.payloads), {head.TARGET_PATH})
        self.assertEqual(row["virtualPath"], head.TARGET_PATH)
        self.assertEqual(row["kind"], "prefab")
        self.assertEqual((row["templatePath"], row["templateSha256"]), (head.TEMPLATE_PATH, head.TEMPLATE_SHA256))
        self.assertEqual((row["templateArchiveFlags"], row["archiveFlags"]), (0, 0))
        self.assertEqual((len(self.source), len(self.candidate)), (1918, 1921))
        self.assertEqual(native.sha256(self.source), "36aef15ab3d1b085846a8b7837ab8108d79073e7379899f85ea69fe5ca2d6df0")
        self.assertEqual(native.sha256(self.candidate), "c2d0af7e8bd3b90cc394545c852266356a7f48f0753052d536988698fab01601")
        self.assertEqual(set(self.report["files"]), {"template/"+head.TARGET_PATH, "resources/"+head.TARGET_PATH})
        self.assertTrue(self.report["audit"]["only_reference_change"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
                "import prepare_steve_head_mesh_control as h;r,p,s=h.load_candidate(Path(sys.argv[1]));"
                "assert set(p)=={h.TARGET_PATH};assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.output/head.REPORT_NAME)],
                                cwd=native.ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_02_cdmw_full_component_and_footer_semantics_and_inverse(self):
        from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
        from prepare_steve_parts_prefab import contract, strict_layout
        before, old_footers = strict_layout(self.source)
        after, new_footers = strict_layout(self.candidate)
        self.assertEqual([obj.name for obj in before.objects], ["CD_Head"])
        self.assertEqual([obj.name for obj in after.objects], ["CD_Head"])
        source_contract = contract(before.objects[0])
        target_contract = contract(after.objects[0])
        self.assertEqual(target_contract["resources"], [head.NATIVE_MESH])
        self.assertEqual(target_contract["values"], [("_skinnedMeshFile", head.NATIVE_MESH), ("_shrinkTag", "Nude"),
                                                      ("_modelBoneAnimationScriptKey", "breath_effect_basic")])
        for field in set(source_contract)-{"resources", "values"}:
            self.assertEqual(source_contract[field], target_contract[field])
        self.assertEqual(old_footers[0]["length"], 178)
        self.assertEqual(new_footers[0]["length"], 181)
        self.assertEqual(rewrite_prefab_paths(self.source, {head.SOURCE_MESH: head.NATIVE_MESH}).data, self.candidate)
        self.assertEqual(rewrite_prefab_paths(self.candidate, {head.NATIVE_MESH: head.SOURCE_MESH}).data, self.source)
        self.assertEqual(head.restore_private_prefab(self.candidate), self.source)
        head.verify_cdmw(self.source, self.candidate)

    def test_03_result_matches_original_donor_first_component_exactly(self):
        from prepare_steve_parts_prefab import keep_first
        donor_path = native.ROOT/"build/steve-assembly/template"/head.TEMPLATE_PATH
        native.check_links(donor_path)
        donor = donor_path.read_bytes()
        self.assertEqual(native.sha256(donor), head.TEMPLATE_SHA256)
        original_first, audit = keep_first(donor)
        self.assertEqual(original_first, self.candidate)
        self.assertEqual(audit["originalComponentCount"], 7)
        self.assertEqual(audit["keptComponentCount"], 1)

    def test_04_changed_source_payload_and_stale_footer_rejected(self):
        from prepare_steve_parts_prefab import strict_layout
        for offset in (0, 1665, 1779, 1850, 1869, 1916):
            raw = bytearray(self.candidate)
            raw[offset] ^= 1
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                head.restore_private_prefab(bytes(raw))
        for raw in (self.source+b"x", self.source[:-1], self.candidate, self.source.replace(b"CD_Head", b"CD_Nude")):
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                head.build_prefab(raw)
        stale = bytearray(self.candidate)
        struct.pack_into("<I", stale, 1916, 178)
        with self.assertRaisesRegex(ValueError, "footer"):
            strict_layout(bytes(stale))
        with tempfile.TemporaryDirectory(prefix="steve-head-control-payload-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            for relative in self.report["files"]:
                path = target/relative
                saved = path.read_bytes()
                path.write_bytes(saved[:-1]+bytes([saved[-1]^1]))
                with self.assertRaises(ValueError):
                    head.load_candidate(target/head.REPORT_NAME)
                path.write_bytes(saved)

    def test_05_report_paths_flags_hashes_claims_and_extra_resources_rejected(self):
        edits = [lambda r: r["candidateResources"][0].update(virtualPath=head.TEMPLATE_PATH),
                 lambda r: r["candidateResources"][0].update(localFile="../foreign.prefab"),
                 lambda r: r["candidateResources"][0].update(templateSha256=head.SOURCE_SHA256),
                 lambda r: r["candidateResources"][0].update(archiveFlags=1),
                 lambda r: r["candidateResources"][0].update(templateArchiveFlags=1),
                 lambda r: r["candidateResources"][0].update(sha256="0"*64),
                 lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
                 lambda r: r["files"].update({"resources/extra.pac": "0"*64}),
                 lambda r: r["integration"].update(steveFixed=True),
                 lambda r: r["integration"].update(installed=0),
                 lambda r: r["audit"].update(only_reference_change=False),
                 lambda r: r.update(variant="different-control")]
        with tempfile.TemporaryDirectory(prefix="steve-head-control-report-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (target/head.REPORT_NAME).write_bytes(head.report_bytes(report))
                with self.assertRaisesRegex(ValueError, "contract"):
                    head.load_candidate(target/head.REPORT_NAME)

    def test_06_matching_forged_hash_does_not_admit_a_changed_prefab(self):
        with tempfile.TemporaryDirectory(prefix="steve-head-control-forged-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"copy"
            shutil.copytree(self.output, target)
            changed = self.candidate.replace(b"breath_effect_basic", b"breath_effect_other")
            self.assertNotEqual(changed, self.candidate)
            relative = "resources/"+head.TARGET_PATH
            (target/relative).write_bytes(changed)
            report = copy.deepcopy(self.report)
            report["candidateResources"][0]["sha256"] = native.sha256(changed)
            report["files"][relative] = native.sha256(changed)
            (target/head.REPORT_NAME).write_bytes(head.report_bytes(report))
            with self.assertRaisesRegex(ValueError, "contract"):
                head.load_candidate(target/head.REPORT_NAME)

    def test_07_output_protection_precedes_source_loading(self):
        source, deps = native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps"
        with tempfile.TemporaryDirectory(prefix="steve-head-control-existing-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)
            (output/"sentinel").write_bytes(b"preserve")
            with mock.patch.object(native, "load_cdmw") as load, mock.patch.object(head, "bounded_read") as read:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    head.prepare(head.DEFAULT_INPUT, output, source, deps)
                load.assert_not_called()
                read.assert_not_called()
            self.assertEqual((output/"sentinel").read_bytes(), b"preserve")
        for name in head.PROTECTED_BUILDS:
            with mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    head.prepare(head.DEFAULT_INPUT, native.ROOT/"build"/name/"new", source, deps)
                load.assert_not_called()
        with self.assertRaisesRegex(ValueError, "ignored build"):
            head.prepare(head.DEFAULT_INPUT, native.ROOT/"artifacts/control", source, deps)

    def test_08_input_drift_rejected_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="steve-head-control-drift-", dir=native.ROOT/"build") as temporary:
            root = Path(temporary)
            input_path = root/"input/head.prefab"
            input_path.parent.mkdir()
            input_path.write_bytes(self.source)
            output = root/"fresh"
            def mutate(_):
                input_path.write_bytes(self.source+b"x")
            with mock.patch.object(native, "load_cdmw"), mock.patch.object(native, "verify_source", side_effect=mutate):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    head.prepare(input_path, output, native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")
            self.assertFalse(output.exists())

    def test_09_real_rebuild_and_prior_candidates_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a fresh fixed-CDMW preparation and byte comparison")
        prior = {}
        for name in head.PROTECTED_BUILDS:
            directory = native.ROOT/"build"/name
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        native.check_links(path)
                        prior[path] = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="steve-head-control-rebuild-", dir=native.ROOT/"build") as temporary:
            target = Path(temporary)/"fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT/"tools/prepare_steve_head_mesh_control.py"),
                                     "--output", str(target)], cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, payloads, _ = head.load_candidate(target/head.REPORT_NAME)
            self.assertEqual((target/head.REPORT_NAME).read_bytes(), self.raw_report)
            self.assertEqual((report, payloads), (self.report, self.payloads))
        head.orientation.verify_snapshot(prior)
        head.orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=head.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    HeadMeshControlChecks.output, HeadMeshControlChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeadMeshControlChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
