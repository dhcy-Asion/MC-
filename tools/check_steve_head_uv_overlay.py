"""Full isolated head-UV transaction suite; production files are only snapshotted."""
from __future__ import annotations

import argparse
import copy
import inspect
import json
from pathlib import Path
import re
import shutil
import unittest
from unittest import mock

from check_asset_probe import ProbeChecks
from check_steve_head_basecolor_overlay import SteveHeadBasecolorOverlayChecks, production_snapshot
import install_asset_probe as transaction
import install_steve_probe as steve
import prepare_steve_head_uv_control as uv
import prepare_steve_head_uv_overlay as packer

helper = steve.steve
BASELINE_SHA256 = "29b813224b362f8d2e751a8ae31968846a55d96410f290ffd10deb00322078e5"
HEAD_REPORT_SHA256 = "56790fa5efb6a2b38ed5938f217d4ddc25b11d5b87c18a6640721fd15ae3a3af"


class SteveHeadUvOverlayChecks(SteveHeadBasecolorOverlayChecks):
    plan = helper.HEAD_UV_OUTPUT
    baseline_plan = helper.HEAD_BASECOLOR_OUTPUT
    expected_variant = packer.VARIANT
    control_reports = (*SteveHeadBasecolorOverlayChecks.control_reports, uv.REPORT_NAME)

    @classmethod
    def setUpClass(cls):
        path = cls.baseline_plan / "reports/overlay-report.json"
        if steve.native.file_hash(path) != BASELINE_SHA256:
            raise ValueError("Head UV checks require the fixed nine-report baseline SHA")
        indexes = json.loads(path.read_bytes())["sourceIndexes"]
        cls.production_source_paths = tuple(sorted(indexes))
        if len(indexes) != 34 or any(re.fullmatch(r"[0-9]{4}/0\.pamt", p.replace("\\", "/")) is None for p in indexes):
            raise ValueError("Head UV fixture needs exactly 34 original PAMT paths")
        installation = json.loads((steve.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))
        cls.production_game = Path(installation["gameRoot"])
        cls.production_receipt = steve.ROOT / transaction.RECEIPT
        cls.production_hasher = steve.native.file_hash
        cls.initial_production = production_snapshot(cls.production_game, cls.production_source_paths,
            cls.production_receipt, cls.production_hasher)
        cls.fixture_finished = False
        cls.addClassCleanup(cls.finish_fixture)
        # Reuse the real-PAMT-copy/fake-EXE fixture directly. Avoid the parent
        # mode's hard-coded eight-report baseline identity and PAMI assertions.
        ProbeChecks.setUpClass.__func__(cls)
        if cls.real_game.resolve() != cls.production_game.resolve() or cls.observed != cls.initial_production["indexes"]:
            raise AssertionError("Original source indexes or production identity changed during setup")
        cls.assert_production_unchanged()

    def base_options(self, **changes):
        return {**super().base_options(), "head_basecolor_path": helper.HEAD_BASECOLOR_REPORT, **changes}

    def test_21_real_fresh_overlay_rebuild_is_identical_and_never_installs(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a real fixed-local ten-report rebuild")
        self.assertNotIn("game", inspect.signature(packer.prepare).parameters)
        self.assertNotIn("game_root", inspect.signature(packer.prepare).parameters)
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_production_unchanged()
        output = self.test_root / "rebuilt-head-uv-overlay"
        real_open = Path.open
        production = self.production_game.resolve()
        def offline_open(path, *args, **kwargs):
            if path.resolve().is_relative_to(production):
                raise AssertionError("Offline packer attempted production game input")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", offline_open):
            packer.prepare(output=output, baseline=self.baseline_plan, head_report=helper.HEAD_UV_REPORT,
                source=self.source, deps=self.deps)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes(), relative)
        self.assert_production_unchanged()
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_original()

    def test_22_control_adds_exactly_one_reviewed_resource(self):
        old = steve.load_plan(self.baseline_plan)
        target = uv.PAC_PATH
        self.assertEqual(old["reportSha256"], BASELINE_SHA256)
        self.assertEqual(steve.native.file_hash(helper.HEAD_UV_REPORT), HEAD_REPORT_SHA256)
        self.assertEqual(set(old["payloads"]), set(self.reviewed["payloads"]))
        self.assertEqual(len(self.reviewed["payloads"]), 14)
        self.assertEqual({p for p in old["payloads"] if old["payloads"][p] != self.reviewed["payloads"][p]}, {target})
        self.assertEqual(steve.native.sha256(old["payloads"][target]), uv.OLD_PAC_SHA256)
        self.assertEqual(steve.native.sha256(self.reviewed["payloads"][target]), uv.NEW_PAC_SHA256)
        source, payload = old["payloads"][target], self.reviewed["payloads"][target]
        self.assertEqual((len(source), len(payload)), (96721, 96721))
        # Independent literal half-word inverse; all outside bytes must match.
        pairs = {bytes.fromhex("003a"):bytes.fromhex("0034"), bytes.fromhex("003b"):bytes.fromhex("0030"),
                 bytes.fromhex("003c"):bytes.fromhex("0000")}
        inverse, allowed = bytearray(payload), set()
        for start in (90529, 92593, 94657):
            for vertex in range(48):
                off = start + vertex * 40 + 10
                allowed.update((off, off + 1))
                self.assertEqual(payload[off:off+2], pairs[source[off:off+2]])
                inverse[off:off+2] = source[off:off+2]
        self.assertEqual(bytes(inverse), source)
        self.assertEqual(sum(a != b for a,b in zip(source,payload)), 144)
        self.assertTrue(all(a == b for i,(a,b) in enumerate(zip(source,payload)) if i not in allowed))
        self.assertEqual(uv.restore_pac(payload), source)
        for path,digest in ((uv.MATERIAL_PATH,uv.PRESERVED_MATERIAL_SHA256),(uv.DIFFUSE_PATH,uv.DIFFUSE_SHA256)):
            self.assertEqual(self.reviewed["payloads"][path], old["payloads"][path])
            self.assertEqual(steve.native.sha256(self.reviewed["payloads"][path]), digest)
        old_rows = {r["virtualPath"]:r for r in old["report"]["resources"]}
        new_rows = {r["virtualPath"]:r for r in self.reviewed["report"]["resources"]}
        self.assertEqual({p:r for p,r in new_rows.items() if p != target}, {p:r for p,r in old_rows.items() if p != target})
        self.assertEqual(self.reviewed["before"], old["before"])
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        for key in ("sourceIndexes", "absentOptionalMountedDirectories", "replacementPaths"):
            self.assertEqual(self.reviewed["report"][key], old["report"][key])
        reports = dict(old["report"]["candidateReports"])
        self.assertEqual(len(reports), 9)
        reports[str(helper.HEAD_UV_REPORT.relative_to(steve.ROOT))] = HEAD_REPORT_SHA256
        self.assertEqual(self.reviewed["report"]["candidateReports"], reports)
        self.assertEqual(len(reports), 10)
        candidate, payloads, _ = uv.load_candidate(helper.HEAD_UV_REPORT)
        row = copy.deepcopy(candidate["candidateResources"][0])
        row["localFile"] = str((helper.HEAD_UV_REPORT.parent / row["localFile"]).relative_to(steve.ROOT))
        self.assertEqual(new_rows[target], row)
        self.assertEqual(payloads[target], payload)
        original, updated = packer.encoded_entries(old["package"]), packer.encoded_entries(self.reviewed["package"])
        for path,(entry,raw) in updated.items():
            previous,previous_raw = original[path]
            if path != target:
                self.assertEqual((raw,entry.flags,entry.orig_size),(previous_raw,previous.flags,previous.orig_size),path)
        self.assertEqual((updated[target][0].flags,updated[target][0].orig_size),(1,96721))
        self.assertEqual(updated[uv.MATERIAL_PATH][0].flags,50)
        self.assertEqual(updated[uv.DIFFUSE_PATH][0].flags,0)
        self.assertEqual(self.reviewed["probeVariant"],self.expected_variant)
        self.assertIn("headUvComposition",self.reviewed["report"])
        self.assertNotIn("headUvComposition",old["report"])
        self.assertFalse(self.reviewed["report"]["headUvComposition"]["nativeShaderUvConventionVerified"])
        receipt = self.install()
        self.assertEqual(receipt["probeVariant"],self.expected_variant)
        self.assertEqual(receipt["planSha256"],self.reviewed["reportSha256"])
        self.restore()
        self.assert_original()
        self.assert_production_unchanged()

    def test_26_body_requires_all_dependencies_and_excludes_other_modes_before_io(self):
        changes = [{key:None} for key in self.base_options()]
        changes += [{"app_path":self.test_root/"unused-app.json"},
                    {"head_mesh_control_path":helper.HEAD_MESH_CONTROL_REPORT},
                    {"head_uv_path":self.test_root/"unknown-report.json"}]
        for change in changes:
            with self.subTest(change=change),mock.patch.object(helper.assembly,"load_candidate") as opened:
                with self.assertRaisesRegex(ValueError,"Head UV control"):
                    helper.candidates(helper.DEFAULT_ASSEMBLY,helper.DEFAULT_APPEARANCE,
                        **{**self.base_options(),"head_uv_path":helper.HEAD_UV_REPORT,**change})
                opened.assert_not_called()
        with mock.patch.object(uv,"load_candidate") as opened,mock.patch.object(steve.native,"file_hash") as hashed:
            with self.assertRaises(ValueError):
                packer.load_head(self.test_root/"unknown-report.json",{})
            opened.assert_not_called()
            hashed.assert_not_called()

    def test_27_body_exact_report_set_rejects_missing_or_mixed_modes_before_hash(self):
        plan,path,original = self.altered_plan()
        # Dropping UV alone produces the valid predecessor report-name set;
        # inherited test23 rejects the mismatching PAC after its ordinary read.
        names = (*self.control_reports[:-1],"steve-assembly-report.json","steve-appearance-report.json")
        for name in (*names,"steve-app-report.json","steve-head-mesh-control-report.json","unknown-report.json","duplicate-uv"):
            report = copy.deepcopy(original)
            if name in names:
                del report["candidateReports"][next(p for p in report["candidateReports"] if p.endswith(name))]
            else:
                report["candidateReports"]["build/unused/"+(uv.REPORT_NAME if name == "duplicate-uv" else name)] = "0"*64
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(name=name),mock.patch.object(steve.native,"file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        self.assert_original()

    def test_28_body_pins_prior_body_pac_and_pami_and_preserves_generic_duplicate_rejection(self):
        resources,reports,snapshot = self.body_candidates()
        for target in (uv.PAC_PATH,uv.MATERIAL_PATH,uv.DIFFUSE_PATH):
            changed = copy.deepcopy(resources)
            changed[target]["payload"] += b"tampered"
            changed[target]["row"]["sha256"] = steve.native.sha256(changed[target]["payload"])
            with self.subTest(target=target),mock.patch.object(uv,"load_candidate") as opened:
                with self.assertRaisesRegex(ValueError,"fixed prior head PAC, PAMI and DDS"):
                    helper.apply_head_uv(changed,dict(reports),dict(snapshot),helper.HEAD_UV_REPORT)
                opened.assert_not_called()
        for target in (uv.PAC_PATH,uv.MATERIAL_PATH):
            changed=copy.deepcopy(resources)
            changed[target]["row"]["archiveFlags"] = 0
            with mock.patch.object(uv,"load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.apply_head_uv(changed,dict(reports),dict(snapshot),helper.HEAD_UV_REPORT)
                opened.assert_not_called()
        earlier = dict(reports)
        del earlier[next(p for p in earlier if p.endswith("steve-head-basecolor-report.json"))]
        with mock.patch.object(uv,"load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_uv(copy.deepcopy(resources),earlier,dict(snapshot),helper.HEAD_UV_REPORT)
            opened.assert_not_called()
        updated,after_reports,after_snapshot = copy.deepcopy(resources),dict(reports),dict(snapshot)
        helper.apply_head_uv(updated,after_reports,after_snapshot,helper.HEAD_UV_REPORT)
        with mock.patch.object(uv,"load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_uv(updated,after_reports,after_snapshot,helper.HEAD_UV_REPORT)
            opened.assert_not_called()
        with self.assertRaisesRegex(ValueError,"Duplicate overlay resource"):
            helper.overlay.load_resources([helper.DEFAULT_ASSEMBLY,helper.HEAD_UV_REPORT])
        self.assert_original()

    def test_29_body_payload_tamper_rejects_updated_inner_and_outer_hashes(self):
        plan,path,original = self.altered_plan()
        key = next(p for p in original["candidateReports"] if p.endswith(uv.REPORT_NAME))
        copied = self.test_root/"tampered-uv"
        shutil.copytree(helper.HEAD_UV_REPORT.parent,copied)
        report_path = copied/uv.REPORT_NAME
        raw_report = report_path.read_bytes()
        fixed = json.loads(raw_report)
        for relative in fixed["files"]:
            file = copied/relative
            raw = file.read_bytes()
            changed = raw[:-1]+bytes([raw[-1]^1])
            file.write_bytes(changed)
            candidate = copy.deepcopy(fixed)
            digest = steve.native.sha256(changed)
            candidate["files"][relative] = digest
            for source in candidate["sources"].values():
                if source["localFile"] == relative:
                    source["sha256"] = digest
            for row in candidate["candidateResources"]:
                if row["localFile"] == relative:
                    row["sha256"] = digest
            report_path.write_bytes(uv.report_bytes(candidate))
            report = copy.deepcopy(original)
            del report["candidateReports"][key]
            report["candidateReports"][str(report_path.relative_to(steve.ROOT))] = steve.native.file_hash(report_path)
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(relative=relative),self.assertRaises(ValueError):
                steve.load_plan(plan)
            file.write_bytes(raw)
            report_path.write_bytes(raw_report)
        self.assert_original()

    def test_30_composition_outputs_reject_source_overlap_before_loading_or_mkdir(self):
        options = {"baseline":self.baseline_plan,"head_report":helper.HEAD_UV_REPORT,"source":self.source,"deps":self.deps}
        cases = [packer.DEFAULT_OUTPUT/"unused-child",packer.DEFAULT_OUTPUT.parent,packer.DEFAULT_BASELINE,
                 packer.DEFAULT_BASELINE/"unused-child",helper.HEAD_UV_REPORT.parent/"unused-child",
                 self.source/"unused-child",self.deps/"unused-child"]
        for output in cases:
            with self.subTest(output=output),mock.patch.object(packer,"fixed_cdmw") as compiled, \
                    mock.patch.object(packer,"load_baseline") as loaded,mock.patch.object(Path,"mkdir") as made:
                with self.assertRaises(ValueError):
                    packer.prepare(output=output,**options)
                compiled.assert_not_called()
                loaded.assert_not_called()
                made.assert_not_called()
        self.assert_original()

    def test_33_uv_composition_canonical_claims_and_source_race_refuse(self):
        plan,path,original = self.altered_plan()
        for change in ("missing","baseline-pin","candidate-pin","runtime-claim","old-composition"):
            report = copy.deepcopy(original)
            if change == "missing":
                del report["headUvComposition"]
            elif change == "old-composition":
                report["headBaseColorComposition"] = report.pop("headUvComposition")
            elif change == "runtime-claim":
                report["headUvComposition"]["nativeShaderUvConventionVerified"] = True
            else:
                report["headUvComposition"]["baselineReportSha256" if change == "baseline-pin" else "candidateReportSha256"] = "0"*64
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,"complete fixed-baseline reconstruction"):
                steve.load_plan(plan)
        baseline,snapshot = packer.load_baseline(self.baseline_plan)
        fixture = self.test_root/"source.bin"
        fixture.write_bytes(b"admitted source")
        raced = {**snapshot,fixture.resolve():b"admitted source"}
        real = packer.load_head
        def load(*args,**kwargs):
            result = real(*args,**kwargs)
            fixture.write_bytes(b"raced source")
            return result
        output = self.test_root/"race-output"
        with mock.patch.object(packer,"load_baseline",return_value=(baseline,raced)),mock.patch.object(packer,"load_head",side_effect=load):
            with self.assertRaisesRegex(ValueError,"changed before publication"):
                packer.prepare(output=output,head_report=helper.HEAD_UV_REPORT,source=self.source,deps=self.deps)
        self.assertFalse(output.exists())
        self.assert_production_unchanged()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,default=SteveHeadUvOverlayChecks.plan)
    parser.add_argument("--rebuild",action="store_true")
    args = parser.parse_args()
    case = SteveHeadUvOverlayChecks
    case.plan,case.rebuild = args.plan,args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
