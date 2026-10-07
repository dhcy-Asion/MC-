"""Check both separately selected, byte-preserving initial-app candidates offline."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_app as app

native = app.native


class AppChecks(unittest.TestCase):
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.candidates = {}
        for variant in app.VARIANTS:
            output = app.default_output(variant)
            report, payloads, snapshot = app.load_candidate(output/app.REPORT_NAME)
            spec = app.variant_spec(variant)
            source = (output/("template/"+spec["path"])).read_bytes()
            cls.candidates[variant] = (output, report, payloads, snapshot, source)
        native.load_cdmw(native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")

    def test_01_pure_loader_has_one_exact_selected_replacement(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');import prepare_steve_app as a;"
                "r,p,s=a.load_candidate(Path(sys.argv[1]));assert len(r['targetReplacements'])==1;"
                "assert len(p)==1;assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        for variant, (output, report, payloads, _, source) in self.candidates.items():
            with self.subTest(variant=variant):
                row, = report["targetReplacements"]
                spec = app.variant_spec(variant)
                self.assertEqual(report["appearanceVariant"], variant)
                self.assertNotIn("appVariant", report)
                self.assertEqual(report["candidateResources"], [])
                self.assertEqual((row["kind"], row["virtualPath"], row["templatePath"]),
                                 ("appearanceDefinition", spec["path"], spec["path"]))
                self.assertEqual((row["archiveFlags"], row["templateArchiveFlags"]), (48, 48))
                self.assertEqual(set(payloads), {spec["path"]})
                self.assertEqual((len(source), native.sha256(source)), (spec["size"], spec["sha256"]))
                self.assertTrue(all(v is False for v in report["integration"].values()))
                self.assertFalse(report["referenceScope"]["runtimeAppearanceFileSelected"])
                self.assertFalse(report["referenceScope"]["controlledActorOnly"])
                result = subprocess.run([sys.executable, "-B", "-c", code, str(output/app.REPORT_NAME)],
                                        cwd=native.ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_02_independent_two_names_inverse_bytes_and_native_xml_retained(self):
        expected_names = {"Nude": (b"cd_phm_00_nude_01_0002_macduff", b"crimsonmc_steve_body_1_21_1"),
                          "Head": (b"cd_phm_00_head_00_0001_macduff", b"crimsonmc_steve_head_1_21_1")}
        for variant, (_, _, payloads, _, source) in self.candidates.items():
            with self.subTest(variant=variant):
                candidate, = payloads.values()
                expected, restored = source, candidate
                for old, new in expected_names.values():
                    self.assertEqual(source.count(b'Name="'+old+b'"'), 1)
                    self.assertEqual(candidate.count(b'Name="'+new+b'"'), 1)
                    expected = expected.replace(b'Name="'+old+b'"', b'Name="'+new+b'"')
                    restored = restored.replace(b'Name="'+new+b'"', b'Name="'+old+b'"')
                self.assertEqual(candidate, expected)
                self.assertEqual(restored, source)
                self.assertTrue(candidate.startswith(b"\xef\xbb\xbf<Appearance>\r\n"))
                self.assertNotIn(b"<?xml", candidate)
                self.assertEqual(source.count(b"\r\n"), candidate.count(b"\r\n"))
                original_tree, candidate_tree = ET.fromstring(source), ET.fromstring(candidate)
                for section, (old, new) in expected_names.items():
                    self.assertEqual(candidate_tree.find(section+"/Prefab").get("Name"), new.decode())
                    candidate_tree.find(section+"/Prefab").set("Name", old.decode())
                self.assertEqual(ET.tostring(candidate_tree), ET.tostring(original_tree))
                self.assertEqual(candidate_tree.find("Nude/Prefab").get("CharacterScale"), "1.02571")
                self.assertEqual(candidate_tree.find("Head/Prefab").get("HeadScale"), "0.92")
                self.assertEqual(len(candidate_tree.findall("Armor/Prefab")), 12 if variant=="macduff-00000" else 3)
                self.assertEqual(len(candidate_tree.findall("Hair/Prefab")), 2)
        from prepare_steve_parts_prefab import PARTS
        self.assertEqual(Path(PARTS["body"]["target"]).stem, "crimsonmc_steve_body_1_21_1")
        self.assertEqual(Path(PARTS["head"]["target"]).stem, "crimsonmc_steve_head_1_21_1")

    def test_03_explicit_variant_required_and_cross_source_refused(self):
        for variant, (_, _, _, _, source) in self.candidates.items():
            other = next(value for value in app.VARIANTS if value != variant)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                app.build_app(source, other)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                app.build_app(source.replace(b'HeadScale="0.92"', b'HeadScale="1.00"'), variant)
        for value in (None, "", "macduff-00001", [], "macduff-00000,macduff-00002"):
            with self.assertRaisesRegex(ValueError, "explicitly"):
                app.variant_spec(value)
        result = subprocess.run([sys.executable, "-B", "tools/prepare_steve_app.py"], cwd=native.ROOT,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--variant", result.stderr)

    def test_04_report_scope_paths_flags_hashes_and_claims_fail_closed(self):
        edits = [lambda r: r["targetReplacements"][0].update(virtualPath="../other.app_xml"),
                 lambda r: r["targetReplacements"][0].update(localFile="replacements/other.app_xml"),
                 lambda r: r["targetReplacements"][0].update(kind="meshParameters"),
                 lambda r: r["targetReplacements"][0].update(archiveFlags=0),
                 lambda r: r["targetReplacements"][0].update(sha256="0"*64),
                 lambda r: r["targetReplacements"].append(copy.deepcopy(r["targetReplacements"][0])),
                 lambda r: r["candidateResources"].append(copy.deepcopy(r["targetReplacements"][0])),
                 lambda r: r["integration"].update(runtimeAppearanceFileSelected=True),
                 lambda r: r["integration"].update(installed=0),
                 lambda r: r["referenceScope"].update(controlledActorOnly=True),
                 lambda r: r.update(supportedExeSha256="0"*64),
                 lambda r: r.update(archiveIndexSha256="0"*64),
                 lambda r: r.update(appVariant=r["appearanceVariant"])]
        with tempfile.TemporaryDirectory(prefix="steve-app-report-", dir=native.ROOT/"build") as temporary:
            for variant, (output, original, _, _, _) in self.candidates.items():
                target = Path(temporary)/variant
                shutil.copytree(output, target)
                for edit in edits:
                    report = copy.deepcopy(original)
                    edit(report)
                    (target/app.REPORT_NAME).write_bytes(app.report_bytes(report))
                    with self.assertRaisesRegex(ValueError, "contract"):
                        app.load_candidate(target/app.REPORT_NAME)

    def test_05_tampered_payload_template_and_stale_snapshot_refused(self):
        with tempfile.TemporaryDirectory(prefix="steve-app-payload-", dir=native.ROOT/"build") as temporary:
            for variant, (output, report, _, _, _) in self.candidates.items():
                target = Path(temporary)/variant
                shutil.copytree(output, target)
                for relative in report["files"]:
                    path = target/relative
                    original = path.read_bytes()
                    path.write_bytes(original[:-1]+bytes([original[-1]^1]))
                    with self.assertRaises(ValueError):
                        app.load_candidate(target/app.REPORT_NAME)
                    path.write_bytes(original)
                _, _, snapshot = app.load_candidate(target/app.REPORT_NAME)
                path = target/report["targetReplacements"][0]["localFile"]
                path.write_bytes(path.read_bytes()+b"\n")
                with self.assertRaisesRegex(ValueError, "changed"):
                    app.orientation.verify_snapshot(snapshot)

    def test_06_fresh_output_and_old_candidate_overlap_before_native_reads(self):
        game, source, deps = (native.ROOT/relative for relative in ("build/unused-game", "build/cdmw-fixed-source", "build/cdmw-deps"))
        with tempfile.TemporaryDirectory(prefix="steve-app-refuse-", dir=native.ROOT/"build") as temporary:
            output = Path(temporary)
            (output/"sentinel").write_bytes(b"preserve")
            with mock.patch.object(app, "read_source") as read, mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    app.prepare(game, "macduff-00000", output, source, deps)
                read.assert_not_called()
                load.assert_not_called()
            self.assertEqual((output/"sentinel").read_bytes(), b"preserve")
        for relative in ("build/steve-assembly/new", "build/steve-appearance/new", "build/steve-head-descriptor/new",
                         "build/steve-app-macduff-00002/new"):
            with mock.patch.object(native, "load_cdmw") as load:
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    app.prepare(game, "macduff-00000", native.ROOT/relative, source, deps)
                load.assert_not_called()

    def test_07_fixed_exe_index_flags_and_source_change_before_publication(self):
        game = native.ROOT/"build/unused-game"
        for variant, (_, _, _, _, original) in self.candidates.items():
            spec = app.variant_spec(variant)
            for failing in ("exe", "index"):
                def digest(path):
                    if path.name=="CrimsonDesert.exe":
                        return "0"*64 if failing=="exe" else native.EXE_SHA256
                    return "0"*64 if failing=="index" else app.INDEX_SHA256
                with mock.patch.object(native, "file_hash", side_effect=digest):
                    with self.assertRaisesRegex(ValueError, "EXE or original 0009"):
                        app.read_source(game, variant)
            def correct_digest(path):
                return native.EXE_SHA256 if path.name=="CrimsonDesert.exe" else app.INDEX_SHA256
            with mock.patch.object(native, "file_hash", side_effect=correct_digest), \
                    mock.patch("cdmw.core.archive_format.parse_archive_pamt", return_value=[]), \
                    mock.patch.object(native, "select_unique_entries", return_value={spec["path"]: SimpleNamespace(flags=49)}), \
                    mock.patch("cdmw.core.archive_extraction.read_archive_entry_raw_data") as payload_read:
                with self.assertRaisesRegex(ValueError, "flags"):
                    app.read_source(game, variant)
                payload_read.assert_not_called()
            with tempfile.TemporaryDirectory(prefix="steve-app-race-", dir=native.ROOT/"build") as temporary:
                output = Path(temporary)/"candidate"
                with mock.patch.object(native, "load_cdmw"), mock.patch.object(app, "read_source", side_effect=[original, original+b"x"]):
                    with self.assertRaisesRegex(ValueError, "changed before publication"):
                        app.prepare(game, variant, output, native.ROOT/"build/cdmw-fixed-source", native.ROOT/"build/cdmw-deps")
                self.assertFalse(output.exists())

    def test_08_both_real_archive_rebuilds_and_old_candidates_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild to extract both explicitly selected original apps again")
        prior = {}
        for directory in (native.ROOT/"build/steve-assembly", native.ROOT/"build/steve-appearance", native.ROOT/"build/steve-head-descriptor"):
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        native.check_links(path)
                        prior[path] = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="steve-app-rebuild-", dir=native.ROOT/"build") as temporary:
            for variant, (original_output, original_report, original_payloads, snapshot, _) in self.candidates.items():
                target = Path(temporary)/variant
                result = subprocess.run([sys.executable, "-B", str(native.ROOT/"tools/prepare_steve_app.py"),
                                         "--variant", variant, "--output", str(target)], cwd=native.ROOT,
                                        capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stderr)
                report, payloads, _ = app.load_candidate(target/app.REPORT_NAME)
                self.assertEqual((target/app.REPORT_NAME).read_bytes(), (original_output/app.REPORT_NAME).read_bytes())
                self.assertEqual((report, payloads), (original_report, original_payloads))
                app.orientation.verify_snapshot(snapshot)
        app.orientation.verify_snapshot(prior)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    AppChecks.rebuild = args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AppChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
