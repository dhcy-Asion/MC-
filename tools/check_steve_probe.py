"""Run the complete transaction fault suite on real Steve package bytes, in copies.

The shared fixture snapshots original indexes but writes only an owned build
directory, with fake executable/saves. No running game or personal save changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from check_asset_probe import ProbeChecks
import install_asset_probe as transaction
import install_steve_probe as steve


class SteveProbeChecks(ProbeChecks):
    plan = steve.steve.DEFAULT_OUTPUT
    plan_loader = staticmethod(steve.load_plan)
    rebuild = False
    resource_count = 11
    rebuild_args = ()
    expected_replacements = (steve.steve.appearance.TARGET_PATH,)

    def install(self, **kwargs):
        return steve.install(self.plan, self.game, state_root=self.state, save_roots=[self.save],
                             running=kwargs.pop("running", lambda: False), **kwargs)

    def restore(self, **kwargs):
        return steve.restore(self.game, state_root=self.state, running=kwargs.pop("running", lambda: False), **kwargs)

    def altered_plan(self):
        result = self.test_root / "altered-plan"
        shutil.copytree(self.plan, result)
        path = result / "reports/overlay-report.json"
        return result, path, json.loads(path.read_bytes())

    def test_16_plan_provenance_matches_resource_set(self):
        # Override oak's single-report rule with the exact selected Steve set.
        plan, path, original = self.altered_plan()
        for change in ("reports", "target", "flags", "kind", "payload-path", "report-traversal", "payload-traversal", "template"):
            report = json.loads(json.dumps(original))
            if change == "reports":
                report["candidateReports"].pop(next(iter(report["candidateReports"])))
            elif change == "target":
                report["replacementPaths"] = ["character/descriptors/another.xml"]
            elif change == "flags":
                report["resources"][0]["archiveFlags"] ^= 1
            elif change == "kind":
                report["resources"][0]["kind"] = "unknown"
            elif change == "payload-path":
                report["resources"][0]["localFile"] = "build/another.dds"
            elif change == "report-traversal":
                original_path, digest = report["candidateReports"].popitem()
                report["candidateReports"]["build\\..\\" + original_path] = digest
            elif change == "payload-traversal":
                report["resources"][0]["localFile"] = "build\\..\\" + report["resources"][0]["localFile"]
            else:
                report["resources"][0]["templatePath"] = "character/another.dds"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        path.write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(len(steve.load_plan(plan)["payloads"]), self.resource_count)

    def test_17_oak_entrypoint_cannot_load_or_restore_steve_receipt(self):
        with self.assertRaisesRegex(ValueError, "21-resource"):
            transaction.load_plan(self.plan)
        receipt = self.install()
        self.assertEqual(receipt["owner"], transaction.STEVE_OWNER)
        self.assertEqual(receipt["probeKind"], steve.KIND)
        before = (self.state / transaction.RECEIPT).read_bytes()
        with self.assertRaisesRegex(ValueError, "ownership"):
            transaction.restore(self.game, state_root=self.state, running=lambda: False)
        self.assertEqual((self.state / transaction.RECEIPT).read_bytes(), before)
        self.restore()
        self.assert_original()

    def test_18_unknown_probe_kind_is_rejected_before_any_backup(self):
        with self.assertRaisesRegex(ValueError, "Unsupported asset probe kind"):
            transaction.install(self.plan, self.game, state_root=self.state, running=lambda: False, probe_kind="anything")
        self.assertFalse((self.state / "backups").exists())
        self.assert_original()

    def test_19_general_new_asset_loader_still_refuses_the_old_path(self):
        from prepare_asset_overlay import load_resources
        from prepare_steve_probe_overlay import appearance, DEFAULT_APPEARANCE
        with self.assertRaisesRegex(ValueError, "No candidateResources"):
            load_resources([DEFAULT_APPEARANCE])
        report, _, _ = appearance.load_candidate(DEFAULT_APPEARANCE)
        fake = {"candidateResources": report["targetReplacements"]}
        file = self.test_root / "old-path-as-addition.json"
        file.write_text(json.dumps(fake), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "crimsonmc_"):
            load_resources([file])

    def test_20_exact_package_shadow_and_private_resources(self):
        from cdmw.core.archive_format import parse_archive_pamt
        target = steve.steve.appearance.TARGET_PATH
        entries = parse_archive_pamt(self.reviewed["package"] / "0.pamt")
        self.assertEqual(len(entries), self.resource_count)
        self.assertEqual(sorted(e.path for e in entries if not Path(e.path).name.startswith("crimsonmc_")),
                         sorted(self.expected_replacements))
        old = (steve.steve.DEFAULT_APPEARANCE.parent / "template" / target).read_bytes()
        new = self.reviewed["payloads"][target]
        for a, b in steve.steve.appearance.REPLACEMENTS:
            new = new.replace(f'MeshFileName="{b}"'.encode(), f'MeshFileName="{a}"'.encode())
        self.assertEqual(new, old)
        self.assertTrue(all((self.game / path).read_bytes() == (self.base / path).read_bytes() for path in self.observed))

    def test_21_real_fresh_overlay_rebuild_is_identical_and_never_installs(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild to compose from the original installed indexes")
        output = self.test_root / "rebuilt-overlay"
        result = subprocess.run([sys.executable, "-B", str(steve.ROOT / "tools/prepare_steve_probe_overlay.py"), "--output", str(output), *self.rebuild_args],
                                cwd=steve.ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes())
        self.assertFalse((steve.ROOT / transaction.RECEIPT).exists())
        self.assert_original()


class SteveHeadDescriptorProbeChecks(SteveProbeChecks):
    plan = steve.steve.HEAD_DESCRIPTOR_OUTPUT
    resource_count = 12
    rebuild_args = ("--head-descriptor-report", str(steve.steve.HEAD_DESCRIPTOR_REPORT))

    def test_22_control_adds_only_original_byte_head_descriptor(self):
        old = steve.load_plan(steve.steve.DEFAULT_OUTPUT)
        expected_path = "character/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefabdata_xml"
        expected_sha = "d69be68d7e5592b40c601f98899465a69694eeff7213809b0063217a9faee56b"
        self.assertEqual(set(self.reviewed["payloads"]) - set(old["payloads"]), {expected_path})
        for path, data in old["payloads"].items():
            self.assertEqual(self.reviewed["payloads"][path], data)
        self.assertEqual(steve.native.sha256(self.reviewed["payloads"][expected_path]), expected_sha)
        self.assertEqual(self.reviewed["probeVariant"], "steve-kliff-head-descriptor-v1")
        self.assertEqual(old["probeVariant"], "steve-kliff-meshparams-v1")
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        receipt = self.install()
        self.assertEqual(receipt["probeVariant"], self.reviewed["probeVariant"])
        self.restore()
        self.assert_original()

    def test_23_descriptor_resource_and_provenance_cannot_be_separated(self):
        plan, path, original = self.altered_plan()
        for change in ("report", "resource", "unknown-report"):
            report = json.loads(json.dumps(original))
            if change == "report":
                name = next(k for k in report["candidateReports"] if k.endswith("steve-head-descriptor-report.json"))
                del report["candidateReports"][name]
            elif change == "resource":
                report["resources"] = [r for r in report["resources"] if not r["virtualPath"].endswith("head/crimsonmc_steve_head_1_21_1.prefabdata_xml")]
            else:
                report["candidateReports"]["build/unknown-report.json"] = "0" * 64
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        self.assert_original()


class StevePartTableProbeChecks(SteveProbeChecks):
    plan = steve.steve.PART_TABLE_OUTPUT
    baseline_plan = steve.steve.HEAD_DESCRIPTOR_OUTPUT
    resource_count = 13
    extra_path = "character/bin__/partprefabtable.pappt"
    expected_variant = "steve-kliff-part-table-v2"
    control_reports = ("steve-head-descriptor-report.json", "steve-part-table-report.json")
    expected_replacements = (steve.steve.appearance.TARGET_PATH, extra_path)
    rebuild_args = ("--head-descriptor-report", str(steve.steve.HEAD_DESCRIPTOR_REPORT),
                    "--part-table-report", str(steve.steve.PART_TABLE_REPORT))

    def test_22_control_adds_exactly_one_reviewed_resource(self):
        old = steve.load_plan(self.baseline_plan)
        self.assertEqual(set(self.reviewed["payloads"]) - set(old["payloads"]), {self.extra_path})
        self.assertTrue(set(old["payloads"]).issubset(self.reviewed["payloads"]))
        for path, data in old["payloads"].items():
            self.assertEqual(self.reviewed["payloads"][path], data)
        self.assertEqual(self.reviewed["probeVariant"], self.expected_variant)
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        receipt = self.install()
        self.assertEqual(receipt["probeVariant"], self.expected_variant)
        self.assertEqual(receipt["planSha256"], self.reviewed["reportSha256"])
        self.restore()
        self.assert_original()

    def test_23_required_controls_and_replacement_declarations_are_inseparable(self):
        plan, path, original = self.altered_plan()
        for change in (*self.control_reports, "resource", "replacement-list", "unknown-report"):
            report = json.loads(json.dumps(original))
            if change in self.control_reports:
                name = next(k for k in report["candidateReports"] if k.endswith(change))
                del report["candidateReports"][name]
            elif change == "resource":
                report["resources"] = [r for r in report["resources"] if r["virtualPath"] != self.extra_path]
            elif change == "replacement-list":
                report["replacementPaths"].remove(self.extra_path)
            else:
                report["candidateReports"]["build/unknown-report.json"] = "0" * 64
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        self.assert_original()

    def test_25_registration_slots_match_real_prefab_components(self):
        from dataclasses import replace
        from cdmw.core.pappt_format import parse_pappt, encode_pappt
        from prepare_steve_parts_prefab import PARTS
        path = "character/bin__/partprefabtable.pappt"
        payloads = dict(self.reviewed["payloads"])
        self.assertEqual(steve.steve.audit_part_components(payloads),
                         {"body": ["CD_Nude"], "head": ["CD_Head"]})
        table = parse_pappt(payloads[path])
        for kind, donor_name in (("body", "cd_phm_00_nude_01_0002_macduff"),
                                 ("head", "cd_phm_00_head_00_0001_macduff")):
            # Recreate the failed v1 mistake from the independently decoded
            # original row: advertise components removed from the new prefab.
            donor = next(row for row in table.records if row.stem == donor_name)
            private_name = Path(PARTS[kind]["target"]).stem
            changed = replace(table, records=tuple(
                replace(row, parts=donor.parts) if row.stem == private_name else row
                for row in table.records))
            bad = dict(payloads, **{path: encode_pappt(changed)})
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "components differ"):
                steve.steve.audit_part_components(bad)
            missing = dict(payloads)
            del missing[PARTS[kind]["target"]]
            with self.assertRaisesRegex(ValueError, "no matching private prefab"):
                steve.steve.audit_part_components(missing)


class SteveInitialAppProbeChecks(StevePartTableProbeChecks):
    resource_count = 14
    baseline_plan = steve.steve.PART_TABLE_OUTPUT
    control_reports = (*StevePartTableProbeChecks.control_reports, "steve-app-report.json")
    app_variant = "macduff-00000"

    @classmethod
    def select_variant(cls, variant):
        import prepare_steve_app as app
        spec = app.variant_spec(variant)
        cls.app_variant = variant
        cls.extra_path = spec["path"]
        report = app.default_output(variant) / app.REPORT_NAME
        cls.plan = steve.steve.app_output(report)
        cls.expected_variant = "steve-kliff-app-" + variant.removeprefix("macduff-") + "-part-table-v2"
        cls.expected_replacements = (*StevePartTableProbeChecks.expected_replacements, cls.extra_path)
        cls.rebuild_args = (*StevePartTableProbeChecks.rebuild_args, "--app-report", str(report))

    def test_24_cannot_add_the_other_app_or_use_old_paths_as_new_assets(self):
        import prepare_steve_app as app
        from prepare_asset_overlay import load_resources
        plan, path, report = self.altered_plan()
        other = next(variant for variant in app.VARIANTS if variant != self.app_variant)
        other_report = app.default_output(other) / app.REPORT_NAME
        report["candidateReports"][str(other_report.relative_to(steve.ROOT))] = steve.native.file_hash(other_report)
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(ValueError):
            steve.load_plan(plan)
        for candidate in (other_report, steve.steve.PART_TABLE_REPORT):
            with self.assertRaisesRegex(ValueError, "No candidateResources"):
                load_resources([candidate])
        self.assertNotIn(app.variant_spec(other)["path"], self.reviewed["payloads"])
        self.assert_original()


class SteveNativeHeadProbeChecks(StevePartTableProbeChecks):
    plan = steve.steve.NATIVE_HEAD_OUTPUT
    baseline_plan = steve.steve.PART_TABLE_OUTPUT
    expected_variant = "steve-kliff-native-head-part-table-v2"
    control_reports = (*StevePartTableProbeChecks.control_reports, "steve-head-mesh-control-report.json")
    rebuild_args = (*StevePartTableProbeChecks.rebuild_args,
                    "--head-mesh-control-report", str(steve.steve.HEAD_MESH_CONTROL_REPORT))

    def test_22_control_adds_exactly_one_reviewed_resource(self):
        old = steve.load_plan(self.baseline_plan)
        target = steve.steve.NATIVE_HEAD_PREFAB
        self.assertEqual(set(self.reviewed["payloads"]), set(old["payloads"]))
        self.assertEqual(len(self.reviewed["payloads"]), 13)
        self.assertEqual({path for path, data in old["payloads"].items()
                          if self.reviewed["payloads"][path] != data}, {target})
        self.assertEqual(steve.native.sha256(old["payloads"][target]), steve.steve.ASSEMBLY_HEAD_SHA256)
        self.assertEqual(self.reviewed["before"], old["before"])
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        expected_inputs = dict(old["report"]["candidateReports"])
        control = steve.steve.HEAD_MESH_CONTROL_REPORT
        expected_inputs[str(control.relative_to(steve.ROOT))] = steve.native.file_hash(control)
        self.assertEqual(self.reviewed["report"]["candidateReports"], expected_inputs)
        before_row = next(row for row in old["report"]["resources"] if row["virtualPath"] == target)
        after_row = next(row for row in self.reviewed["report"]["resources"] if row["virtualPath"] == target)
        self.assertEqual(after_row["archiveFlags"], 0)
        for key in ("virtualPath", "kind", "templatePath", "templateSha256"):
            self.assertEqual(after_row[key], before_row[key])
        self.assertEqual(self.reviewed["probeVariant"], self.expected_variant)
        self.assertEqual(steve.steve.audit_part_components(self.reviewed["payloads"]),
                         {"body": ["CD_Nude"], "head": ["CD_Head"]})
        receipt = self.install()
        self.assertEqual(receipt["probeVariant"], self.expected_variant)
        self.assertEqual(receipt["planSha256"], self.reviewed["reportSha256"])
        self.restore()
        self.assert_original()

    def test_26_native_head_requires_both_controls_and_excludes_app_before_io(self):
        helper = steve.steve
        for changes in ({"head_descriptor_path": None}, {"part_table_path": None},
                        {"app_path": self.test_root / "unused-app-report.json"}):
            options = {"head_descriptor_path": helper.HEAD_DESCRIPTOR_REPORT,
                       "part_table_path": helper.PART_TABLE_REPORT,
                       "head_mesh_control_path": helper.HEAD_MESH_CONTROL_REPORT, **changes}
            with self.subTest(changes=changes), mock.patch.object(helper.assembly, "load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE, **options)
                opened.assert_not_called()
        for reports, changes in (([helper.DEFAULT_ASSEMBLY], {}),
                                 ([helper.DEFAULT_ASSEMBLY, helper.HEAD_DESCRIPTOR_REPORT], {"part_table_report": None}),
                                 ([helper.DEFAULT_ASSEMBLY, helper.HEAD_DESCRIPTOR_REPORT],
                                  {"initial_appearance_report": self.test_root / "unused-app-report.json"})):
            options = {"replacement_report": helper.DEFAULT_APPEARANCE,
                       "part_table_report": helper.PART_TABLE_REPORT,
                       "head_mesh_control_report": helper.HEAD_MESH_CONTROL_REPORT, **changes}
            with self.subTest(changes=changes, reports=reports), mock.patch.object(steve.native, "load_cdmw") as opened:
                with self.assertRaises(ValueError):
                    helper.overlay.prepare(self.game, reports, self.test_root / "rejected-overlay",
                                           self.source, self.deps, **options)
                opened.assert_not_called()

    def test_27_native_head_exact_report_set_rejects_app_and_replaced_dependencies(self):
        plan, path, original = self.altered_plan()
        app_path = "build/unused-app/steve-app-report.json"
        for missing in (None, "steve-head-descriptor-report.json", "steve-part-table-report.json"):
            report = json.loads(json.dumps(original))
            report["candidateReports"][app_path] = "0" * 64
            if missing:
                name = next(name for name in report["candidateReports"] if name.endswith(missing))
                del report["candidateReports"][name]
            path.write_text(json.dumps(report), encoding="utf-8")
            # Invalid combinations must be rejected before even reading the
            # fictitious app report, including the six-report mixed control.
            with self.subTest(missing=missing), mock.patch.object(steve.native, "file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        self.assert_original()

    def test_28_native_head_pins_original_assembly_and_keeps_generic_duplicates_rejected(self):
        helper = steve.steve
        model, files, snapshot = helper.assembly.load_candidate(helper.DEFAULT_ASSEMBLY)
        head = next(row for row in model["candidateResources"] if row["virtualPath"] == helper.NATIVE_HEAD_PREFAB)
        for change in ("digest", "payload"):
            changed_model = json.loads(json.dumps(model))
            changed_files = dict(files)
            if change == "digest":
                next(row for row in changed_model["candidateResources"]
                     if row["virtualPath"] == helper.NATIVE_HEAD_PREFAB)["sha256"] = "0" * 64
            else:
                changed_files[head["localFile"]] += b"altered"
            with self.subTest(change=change), mock.patch.object(helper.assembly, "load_candidate",
                    return_value=(changed_model, changed_files, snapshot)):
                with self.assertRaisesRegex(ValueError, "fixed original assembly head"):
                    helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE,
                                      helper.HEAD_DESCRIPTOR_REPORT, part_table_path=helper.PART_TABLE_REPORT,
                                      head_mesh_control_path=helper.HEAD_MESH_CONTROL_REPORT)
        with self.assertRaisesRegex(ValueError, "Duplicate overlay resource"):
            helper.overlay.load_resources([helper.DEFAULT_ASSEMBLY, helper.HEAD_MESH_CONTROL_REPORT])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--head-descriptor", action="store_true")
    mode.add_argument("--part-table", action="store_true")
    mode.add_argument("--native-head", action="store_true")
    mode.add_argument("--app-variant", choices=("macduff-00000", "macduff-00002"))
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.app_variant:
        case = SteveInitialAppProbeChecks
        case.select_variant(args.app_variant)
    else:
        case = SteveNativeHeadProbeChecks if args.native_head else StevePartTableProbeChecks if args.part_table else SteveHeadDescriptorProbeChecks if args.head_descriptor else SteveProbeChecks
    case.plan, case.rebuild = args.plan or case.plan, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
