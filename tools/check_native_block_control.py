"""Check the offline blue-template-alias against real, pinned local templates.

All generated/refusal test products stay in owned temporary build directories.
This check never installs, spawns, calls HTTP or accesses a game process.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_native_block_control as control
import probe_native_resources as resource


class BlueAliasChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = control.ROOT / "build/native-block" / control.REPORT_NAME
        cls.verified = resource.load_assets(cls.source)
        cls.source_report = resource.strict_json(cls.source.read_bytes())
        cls.temporary = tempfile.TemporaryDirectory(prefix="blue-alias-check-", dir=control.ROOT / "build")
        cls.root = Path(cls.temporary.name)
        cls.output = cls.root / "verified-control"
        cls.report = control.build_control(cls.source, cls.output)
        cls.material_output = cls.root / "verified-material-control"
        cls.material_report = control.build_control(cls.source, cls.material_output, control.MATERIAL_VARIANT)
        cls.no_declaration_output = cls.root / "verified-no-declaration-control"
        cls.no_declaration_report = control.build_control(cls.source, cls.no_declaration_output, control.NO_DECLARATION_VARIANT)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))

    def duplicate(self):
        source = self.case / "source"
        source.mkdir()
        for relative in self.source_report["files"]:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source.parent / relative, target)
        report_path = source / control.REPORT_NAME
        report_path.write_bytes(self.source.read_bytes())
        output = self.case / "control"
        report = control.build_control(report_path, output)
        return report_path, output, report

    @staticmethod
    def save(output: Path, report: dict):
        (output / control.REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def test_01_exact_blue_prefab_and_twenty_unchanged_candidates(self):
        changed, unchanged = [], 0
        for row in self.source_report["candidateResources"]:
            original = (self.source.parent / row["localFile"]).read_bytes()
            candidate = (self.output / row["localFile"]).read_bytes()
            if original == candidate:
                unchanged += 1
            else:
                changed.append(row["virtualPath"])
        self.assertEqual(changed, [control.TARGET])
        self.assertEqual(unchanged, 20)
        original = (self.source.parent / ("template/" + control.TEMPLATE)).read_bytes()
        alias = (self.output / ("candidate/" + control.TARGET)).read_bytes()
        self.assertEqual(alias, original)
        self.assertEqual(len(alias), 1845)
        self.assertEqual(control.native.sha256(alias), "e05cf4bab0cfc7c59398ea45cb0b62f955c7c6f5dc9e2c5d17d59fef5658f56c")
        self.assertIn(b"object/00_common/system/cd_testfield_grid_box_1m.pami", alias)
        self.assertNotIn(b"crimsonmc_oak_log_y.pami", alias)

    def test_02_templates_files_and_minimal_honest_report(self):
        self.assertEqual(set(self.report), set(control.SOURCE_FIELDS) | {"probeVariant", "control"})
        self.assertEqual(self.report["probeVariant"], "blue-template-alias")
        self.assertEqual(self.report["integration"], self.source_report["integration"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        for relative, digest in self.report["files"].items():
            self.assertEqual(control.native.file_hash(self.output / relative), digest)
            if relative.startswith("template/"):
                self.assertEqual((self.output / relative).read_bytes(), (self.source.parent / relative).read_bytes())
        evidence = control.validate_control(self.output / control.REPORT_NAME, self.report)
        self.assertEqual(evidence["sourceReport"], "build/native-block/native-block-report.json")
        self.assertEqual(evidence["sourceReportSha256"], control.native.file_hash(self.source))
        self.assertEqual(evidence["unchangedCandidateCount"], 20)
        self.assertIn("not an oak", evidence["purpose"])

    def test_03_rebuild_is_byte_reproducible_and_resource_loader_compatible(self):
        second = self.case / "rebuilt"
        rebuilt = control.build_control(self.source, second)
        self.assertEqual(rebuilt, self.report)
        for name in (*self.report["files"], control.REPORT_NAME):
            self.assertEqual((second / name).read_bytes(), (self.output / name).read_bytes())
        accepted = resource.load_assets(second / control.REPORT_NAME)
        self.assertEqual(accepted["resources"]["oak_y_prefab"]["sha256"], control.TEMPLATE_SHA256)
        self.assertEqual(accepted["resources"]["oak_y_prefab"]["length"], 1845)

    def test_04_second_payload_change_even_with_coherent_report_hashes(self):
        _, output, report = self.duplicate()
        row = next(row for row in report["candidateResources"] if row["virtualPath"].endswith("crimsonmc_oak_log_y.pam"))
        path = output / row["localFile"]
        path.write_bytes(path.read_bytes() + b"additional change")
        row["sha256"] = control.native.file_hash(path)
        report["files"][row["localFile"]] = row["sha256"]
        self.save(output, report)
        with self.assertRaisesRegex(control.ControlError, "exactly one"):
            control.validate_control(output / control.REPORT_NAME, report)

    def test_05_payload_change_without_updating_report_is_rejected(self):
        _, output, report = self.duplicate()
        row = next(row for row in report["candidateResources"] if row["virtualPath"] != control.TARGET)
        path = output / row["localFile"]
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(control.ControlError, "byte diff"):
            control.validate_control(output / control.REPORT_NAME, report)

    def test_06_blue_alias_and_template_corruption_rejected(self):
        _, output, report = self.duplicate()
        alias = output / ("candidate/" + control.TARGET)
        original = alias.read_bytes()
        alias.write_bytes(original + b"changed")
        with self.assertRaisesRegex(control.ControlError, "SHA256"):
            control.validate_control(output / control.REPORT_NAME, report)
        alias.write_bytes(original)
        path = output / ("template/" + control.TEMPLATE)
        path.write_bytes(original + b"changed")
        with self.assertRaisesRegex(control.ControlError, "SHA256"):
            control.validate_control(output / control.REPORT_NAME, report)

    def test_07_control_variant_cannot_be_removed_or_disguised(self):
        _, output, report = self.duplicate()
        for variant in (None, control.DEFAULT_VARIANT, "unknown"):
            changed = copy.deepcopy(report)
            if variant is None:
                del changed["probeVariant"]
            else:
                changed["probeVariant"] = variant
            self.save(output, changed)
            with self.assertRaisesRegex(control.ControlError, "explicit"):
                control.validate_control(output / control.REPORT_NAME, changed)
        changed = copy.deepcopy(report)
        del changed["control"]
        self.save(output, changed)
        with self.assertRaises(control.ControlError):
            control.validate_control(output / control.REPORT_NAME, changed)

    def test_08_bad_metadata_extra_claims_or_paths_are_rejected(self):
        _, output, report = self.duplicate()
        for field, value in (("sourceReport", "../outside/native-block-report.json"),
                             ("sourceReport", "build/../native-block/native-block-report.json"),
                             ("sourceReport", "C:/foreign/native-block-report.json"),
                             ("sourceReport", "build\\native-block\\native-block-report.json"),
                             ("sourceReportSha256", "0" * 64), ("changedResource", "object/foreign.prefab"),
                             ("unchangedCandidateCount", 19), ("templateSha256", "0" * 64), ("purpose", "oak success")):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(report)
                changed["control"][field] = value
                self.save(output, changed)
                with self.assertRaises(ValueError):
                    control.validate_control(output / control.REPORT_NAME, changed)
        changed = copy.deepcopy(report)
        changed["geometryVerified"] = True
        self.save(output, changed)
        with self.assertRaisesRegex(control.ControlError, "extra claims"):
            control.validate_control(output / control.REPORT_NAME, changed)

    def test_09_source_report_change_after_build_is_rejected(self):
        source, output, report = self.duplicate()
        original = source.read_bytes()
        source.write_bytes(original + b"\n")  # Same JSON/asset semantics, different pinned provenance.
        with self.assertRaisesRegex(control.ControlError, "source report SHA256 changed"):
            control.validate_control(output / control.REPORT_NAME, report)

    def test_10_source_candidate_change_and_source_control_refused(self):
        source, output, report = self.duplicate()
        source_doc = resource.strict_json(source.read_bytes())
        row = next(row for row in source_doc["candidateResources"] if row["virtualPath"] != control.TARGET)
        path = source.parent / row["localFile"]
        path.write_bytes(path.read_bytes() + b"source changed")
        with self.assertRaisesRegex(resource.ProbeError, "SHA256"):
            control.validate_control(output / control.REPORT_NAME, report)
        with self.assertRaisesRegex(control.ControlError, "ordinary"):
            control.build_control(self.output / control.REPORT_NAME, self.case / "nested-control")
        disguised = copy.deepcopy(self.report)
        del disguised["probeVariant"]
        del disguised["control"]
        hidden = self.case / "hidden"
        shutil.copytree(self.output, hidden)
        self.save(hidden, disguised)
        with self.assertRaisesRegex((control.ControlError, resource.ProbeError), "disguised|labelled as a control"):
            control.build_control(hidden / control.REPORT_NAME, self.case / "from-hidden")

    def test_11_wrong_supplied_report_does_not_validate_saved_evidence(self):
        changed = copy.deepcopy(self.report)
        changed["control"]["purpose"] = "changed in memory only"
        with self.assertRaisesRegex(control.ControlError, "saved report"):
            control.validate_control(self.output / control.REPORT_NAME, changed)

    def test_12_source_and_output_scope_overlap_and_existing_products(self):
        source, _, _ = self.duplicate()
        for output in (source.parent, source.parent / "child", self.case,
                       control.ROOT / "runtime/blue-alias", control.ROOT.parent / "not-build"):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    control.build_control(source, output)
        existing = self.case / "existing"
        existing.mkdir()
        keep = existing / "user.txt"
        keep.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(control.ControlError, "already exists"):
            control.build_control(source, existing)
        self.assertEqual(keep.read_text(), "preserve")
        collision = self.case / "file"
        collision.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(control.ControlError, "already exists"):
            control.build_control(source, collision)
        self.assertEqual(collision.read_text(), "preserve")

    def test_13_real_junction_source_and_output_rejected(self):
        if not hasattr(Path, "is_junction"):
            self.fail("Python 3.12+ is required for this Windows junction protection check")
        alias = self.case / "source-link"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(self.source.parent)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            with self.assertRaisesRegex(ValueError, "junction"):
                control.build_control(alias / control.REPORT_NAME, self.case / "out")
            with self.assertRaisesRegex(ValueError, "junction"):
                control.build_control(self.source, alias / "out")
        finally:
            alias.rmdir()

    def test_14_control_localfile_pollution_and_actual_input_pins(self):
        source, output, report = self.duplicate()
        row = report["candidateResources"][0]
        row["localFile"] = "candidate/../../foreign"
        self.save(output, report)
        with self.assertRaisesRegex(control.ControlError, "exactly one"):
            control.validate_control(output / control.REPORT_NAME, report)
        original = source.read_bytes()
        source_doc = resource.strict_json(original)
        source_doc["supportedExeSha256"] = "0" * 64
        source.write_text(json.dumps(source_doc), encoding="utf-8")
        with self.assertRaisesRegex(resource.ProbeError, "EXE"):
            control.build_control(source, self.case / "wrong-exe")
        source_doc = resource.strict_json(original)
        source_doc["cdmw"]["commit"] = "foreign"
        source.write_text(json.dumps(source_doc), encoding="utf-8")
        with self.assertRaisesRegex(resource.ProbeError, "CDMW"):
            control.build_control(source, self.case / "wrong-cdmw")

    def test_15_mid_build_source_change_refused_before_report_publication(self):
        source, _, _ = self.duplicate()
        destination = self.case / "mid-build"
        original = control._ordinary_source
        calls = 0
        def verify(path, expected_sha256=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(path.read_bytes() + b"\n")
            return original(path, expected_sha256)
        with mock.patch.object(control, "_ordinary_source", side_effect=verify):
            with self.assertRaisesRegex(control.ControlError, "source report SHA256 changed"):
                control.build_control(source, destination)
        self.assertFalse((destination / control.REPORT_NAME).exists())
        self.assertTrue((destination / ("candidate/" + control.TARGET)).exists())

    def test_16_explicit_default_variant_and_cli_existing_output_exit(self):
        source, _, _ = self.duplicate()
        doc = resource.strict_json(source.read_bytes())
        doc["probeVariant"] = control.DEFAULT_VARIANT
        source.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        output = self.case / "explicit-default"
        report = control.build_control(source, output)
        self.assertEqual(control.validate_control(output / control.REPORT_NAME, report), report["control"])
        with mock.patch("sys.argv", ["prepare_native_block_control.py", "--source", str(source), "--output", str(output)]):
            self.assertEqual(control.main(), 1)

    def test_17_material_alias_changes_only_pami_keeps_normal_prefab(self):
        spec = control.VARIANTS[control.MATERIAL_VARIANT]
        differences = []
        for row in self.source_report["candidateResources"]:
            if (self.source.parent / row["localFile"]).read_bytes() != (self.material_output / row["localFile"]).read_bytes():
                differences.append(row["virtualPath"])
        self.assertEqual(differences, [spec["target"]])
        alias = (self.material_output / ("candidate/" + spec["target"])).read_bytes()
        self.assertEqual(alias, (self.source.parent / ("template/" + spec["template"])).read_bytes())
        self.assertEqual(len(alias), 727)
        self.assertEqual(control.native.sha256(alias), "a8c6dac4dc64a78af8acee4430bd200130a74300ffe4d0a71941399a6745e77e")
        self.assertIn(b'<StaticMesh Path="object/00_common/system/cd_testfield_grid_box_1m.pam"/>', alias)
        self.assertIn(b"object/texture/cd_testfield_grid_03.dds", alias)
        normal_prefab = (self.material_output / ("candidate/" + control.TARGET)).read_bytes()
        self.assertEqual(normal_prefab, (self.source.parent / ("candidate/" + control.TARGET)).read_bytes())
        self.assertIn(b"object/00_common/system/crimsonmc_oak_log_y.pami", normal_prefab)
        self.assertEqual(control.validate_control(self.material_output / control.REPORT_NAME, self.material_report), self.material_report["control"])

    def test_18_material_rebuild_loader_and_a_report_byte_compatibility(self):
        rebuilt = self.case / "material-rebuild"
        report = control.build_control(self.source, rebuilt, control.MATERIAL_VARIANT)
        for relative in (*report["files"], control.REPORT_NAME):
            self.assertEqual((rebuilt / relative).read_bytes(), (self.material_output / relative).read_bytes())
        accepted = resource.load_assets(rebuilt / control.REPORT_NAME)
        self.assertEqual(accepted["resources"]["oak_y_pami"]["length"], 727)
        self.assertEqual(accepted["resources"]["oak_y_prefab"]["sha256"], self.verified["resources"]["oak_y_prefab"]["sha256"])
        # The existing production A report must still have its original identity.
        legacy = control.ROOT / "build/native-block-blue-alias" / control.REPORT_NAME
        self.assertEqual(control.native.file_hash(legacy), "1852b7507aec52d6ca22d1cff58736f9bda5cc358fb78fbad7c337c0867ee016")
        saved = resource.strict_json(legacy.read_bytes())
        self.assertEqual(control.validate_control(legacy, saved), saved["control"])
        self.assertEqual((self.output / control.REPORT_NAME).read_bytes(), legacy.read_bytes())

    def test_19_wrong_variant_and_mixed_a_b_assets_rejected(self):
        output = self.case / "mixed"
        shutil.copytree(self.material_output, output)
        report = copy.deepcopy(self.material_report)
        report["probeVariant"] = control.VARIANT
        self.save(output, report)
        with self.assertRaisesRegex(control.ControlError, "exactly one"):
            control.validate_control(output / control.REPORT_NAME, report)
        for variant in ("unknown", control.DEFAULT_VARIANT, "../arbitrary", [], {}, None):
            with self.assertRaisesRegex(control.ControlError, "Unknown fixed"):
                control.build_control(self.source, self.case / "unsupported", variant)
        report = copy.deepcopy(self.material_report)
        self.save(output, report)
        prefab_path = output / ("candidate/" + control.TARGET)
        prefab_path.write_bytes((self.output / ("candidate/" + control.TARGET)).read_bytes())
        with self.assertRaisesRegex(control.ControlError, "byte diff"):
            control.validate_control(output / control.REPORT_NAME, report)

    def test_20_material_control_disguised_as_ordinary_source_rejected(self):
        hidden = self.case / "hidden-material"
        shutil.copytree(self.material_output, hidden)
        report = copy.deepcopy(self.material_report)
        del report["control"]
        del report["probeVariant"]
        self.save(hidden, report)
        with self.assertRaisesRegex((control.ControlError, resource.ProbeError), "disguised|labelled as a control"):
            control.build_control(hidden / control.REPORT_NAME, self.case / "from-hidden", control.MATERIAL_VARIANT)

    def test_21_material_cli_default_directory_and_explicit_output(self):
        output = self.case / "cli-material"
        with mock.patch("sys.argv", ["prepare_native_block_control.py", "--variant", control.MATERIAL_VARIANT,
                                    "--source", str(self.source), "--output", str(output)]):
            self.assertEqual(control.main(), 0)
        saved = resource.strict_json((output / control.REPORT_NAME).read_bytes())
        self.assertEqual(saved["probeVariant"], control.MATERIAL_VARIANT)
        with mock.patch("sys.argv", ["prepare_native_block_control.py", "--variant", control.MATERIAL_VARIANT]):
            with mock.patch.object(control, "build_control", return_value=saved) as build:
                self.assertEqual(control.main(), 0)
                self.assertEqual(build.call_args.args, (self.source, control.ROOT / "build/native-block-blue-material-alias", control.MATERIAL_VARIANT))

    def test_22_no_declaration_exact_source_suffix_and_independent_xml_semantics(self):
        spec = control.VARIANTS[control.NO_DECLARATION_VARIANT]
        original = (self.source.parent / ("candidate/" + spec["target"])).read_bytes()
        actual = (self.no_declaration_output / ("candidate/" + spec["target"])).read_bytes()
        self.assertEqual(len(control.PAMI_DECLARATION), 39)
        self.assertEqual(original[:39], control.PAMI_DECLARATION)
        self.assertEqual(actual, original[39:])
        self.assertEqual(len(actual), 721)
        self.assertNotEqual(actual, (self.source.parent / ("template/" + spec["template"])).read_bytes())
        self.assertEqual(ET.canonicalize(original.decode(), strip_text=True), ET.canonicalize(actual.decode(), strip_text=True))
        differences = [row["virtualPath"] for row in self.source_report["candidateResources"]
                       if (self.source.parent / row["localFile"]).read_bytes() != (self.no_declaration_output / row["localFile"]).read_bytes()]
        self.assertEqual(differences, [spec["target"]])
        proof = self.no_declaration_report["control"]
        self.assertEqual(proof["sourceResourceSha256"], control.native.sha256(original))
        self.assertEqual(proof["removedPrefixHex"], original[:39].hex())
        self.assertIs(proof["xmlSemanticEquivalent"], True)

    def test_23_c_rebuild_loader_and_b_legacy_identity(self):
        output = self.case / "c-rebuild"
        report = control.build_control(self.source, output, control.NO_DECLARATION_VARIANT)
        for relative in (*report["files"], control.REPORT_NAME):
            self.assertEqual((output / relative).read_bytes(), (self.no_declaration_output / relative).read_bytes())
        loaded = resource.load_assets(output / control.REPORT_NAME)
        self.assertEqual(loaded["resources"]["oak_y_pami"]["length"], 721)
        self.assertEqual(loaded["probeVariant"], control.NO_DECLARATION_VARIANT)
        legacy = control.ROOT / "build/native-block-blue-material-alias" / control.REPORT_NAME
        self.assertEqual(control.native.file_hash(legacy), "61dceae254482c25180c16df7b3756d4d049477dbf8fa3d74c1826e6915a84eb")
        saved = resource.strict_json(legacy.read_bytes())
        self.assertEqual(control.validate_control(legacy, saved), saved["control"])
        self.assertEqual((self.material_output / control.REPORT_NAME).read_bytes(), legacy.read_bytes())

    def test_24_c_wrong_suffix_extra_edit_and_wrong_proof_rejected(self):
        output = self.case / "wrong-c"
        shutil.copytree(self.no_declaration_output, output)
        original_report = self.no_declaration_report
        spec = control.VARIANTS[control.NO_DECLARATION_VARIANT]
        target = output / ("candidate/" + spec["target"])
        exact = target.read_bytes()
        target.write_bytes(exact.replace(b" />", b"/>", 1))
        with self.assertRaisesRegex(control.ControlError, "SHA256"):
            control.validate_control(output / control.REPORT_NAME, original_report)
        target.write_bytes(exact)
        for field, value in (("removedPrefixHex", "00" * 39), ("sourceResourceSha256", "0" * 64),
                             ("xmlSemanticEquivalent", False), ("xmlSemanticEquivalent", 1)):
            changed = copy.deepcopy(original_report)
            changed["control"][field] = value
            self.save(output, changed)
            with self.assertRaises(control.ControlError):
                control.validate_control(output / control.REPORT_NAME, changed)
        changed = copy.deepcopy(original_report)
        changed["probeVariant"] = control.MATERIAL_VARIANT
        self.save(output, changed)
        with self.assertRaisesRegex(control.ControlError, "provenance"):
            control.validate_control(output / control.REPORT_NAME, changed)

    def test_25_wrong_source_declaration_refused_before_output(self):
        source, _, _ = self.duplicate()
        report = resource.strict_json(source.read_bytes())
        row = next(row for row in report["candidateResources"] if row["virtualPath"] == control.VARIANTS[control.NO_DECLARATION_VARIANT]["target"])
        target = source.parent / row["localFile"]
        target.write_bytes(target.read_bytes().replace(b"version='1.0'", b'version="1.0"', 1))
        row["sha256"] = control.native.file_hash(target)
        report["files"][row["localFile"]] = row["sha256"]
        source.write_text(json.dumps(report), encoding="utf-8")
        destination = self.case / "wrong-prefix"
        with self.assertRaisesRegex(control.ControlError, "exact 39-byte"):
            control.build_control(source, destination, control.NO_DECLARATION_VARIANT)
        self.assertFalse(destination.exists())

    def test_26_c_labels_cannot_be_removed_or_used_as_ordinary_source(self):
        hidden = self.case / "hidden-c"
        shutil.copytree(self.no_declaration_output, hidden)
        report = copy.deepcopy(self.no_declaration_report)
        del report["control"]
        del report["probeVariant"]
        self.save(hidden, report)
        with self.assertRaisesRegex((control.ControlError, resource.ProbeError), "disguised|labelled as a control"):
            control.build_control(hidden / control.REPORT_NAME, self.case / "from-hidden-c", control.NO_DECLARATION_VARIANT)
        with self.assertRaisesRegex(control.ControlError, "explicit"):
            control.validate_control(hidden / control.REPORT_NAME, report)

    def test_27_c_cli_default_output(self):
        saved = self.no_declaration_report
        with mock.patch("sys.argv", ["prepare_native_block_control.py", "--variant", control.NO_DECLARATION_VARIANT]):
            with mock.patch.object(control, "build_control", return_value=saved) as build:
                self.assertEqual(control.main(), 0)
                self.assertEqual(build.call_args.args, (self.source, control.ROOT / "build/native-block-oak-no-declaration", control.NO_DECLARATION_VARIANT))


if __name__ == "__main__":
    unittest.main(verbosity=2)
