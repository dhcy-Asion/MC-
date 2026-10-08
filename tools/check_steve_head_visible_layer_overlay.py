"""Full isolated head-visible-layer transaction suite; production files are only snapshotted."""
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
from check_steve_head_uv_overlay import SteveHeadUvOverlayChecks, production_snapshot
import install_asset_probe as transaction
import install_steve_probe as steve
import prepare_steve_head_visible_layer as layer
import prepare_steve_head_visible_layer_overlay as packer

helper = steve.steve
BASELINE_SHA256 = "b27484b952059015920635a23cf489a2881d23ba86e554b0b80f7157a03e7c10"
HEAD_REPORT_SHA256 = "6d68aa3eff9428fe9f7c63838fdbed10097a4c17ef0da940648b24ea972e6501"


class SteveHeadVisibleLayerOverlayChecks(SteveHeadUvOverlayChecks):
    plan = helper.HEAD_VISIBLE_LAYER_OUTPUT
    baseline_plan = helper.HEAD_UV_OUTPUT
    expected_variant = packer.VARIANT
    control_reports = (*SteveHeadUvOverlayChecks.control_reports, layer.REPORT_NAME)

    @classmethod
    def setUpClass(cls):
        path = cls.baseline_plan / "reports/overlay-report.json"
        if steve.native.file_hash(path) != BASELINE_SHA256:
            raise ValueError("Head visible-layer checks require the fixed ten-report baseline SHA")
        indexes = json.loads(path.read_bytes())["sourceIndexes"]
        cls.production_source_paths = tuple(sorted(indexes))
        if len(indexes) != 34 or any(re.fullmatch(r"[0-9]{4}/0\.pamt", p.replace("\\", "/")) is None for p in indexes):
            raise ValueError("Head visible-layer fixture needs exactly 34 original PAMT paths")
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
        return {**super().base_options(), "head_uv_path": helper.HEAD_UV_REPORT, **changes}

    def test_21_real_fresh_overlay_rebuild_is_identical_and_never_installs(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a real fixed-local eleven-report rebuild")
        self.assertNotIn("game", inspect.signature(packer.prepare).parameters)
        self.assertNotIn("game_root", inspect.signature(packer.prepare).parameters)
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_production_unchanged()
        output = self.test_root / "rebuilt-head-visible-layer-overlay"
        real_open = Path.open
        production = self.production_game.resolve()
        def offline_open(path, *args, **kwargs):
            if path.resolve().is_relative_to(production):
                raise AssertionError("Offline packer attempted production game input")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", offline_open):
            packer.prepare(output=output, baseline=self.baseline_plan, head_report=helper.HEAD_VISIBLE_LAYER_REPORT,
                source=self.source, deps=self.deps)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes(), relative)
        self.assert_production_unchanged()
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_original()

    def test_22_control_adds_exactly_one_reviewed_resource(self):
        old = steve.load_plan(self.baseline_plan)
        target = layer.PAC_PATH
        self.assertEqual(old["reportSha256"], BASELINE_SHA256)
        self.assertEqual(steve.native.file_hash(helper.HEAD_VISIBLE_LAYER_REPORT), HEAD_REPORT_SHA256)
        self.assertEqual(set(old["payloads"]), set(self.reviewed["payloads"]))
        self.assertEqual(len(self.reviewed["payloads"]), 14)
        self.assertEqual({p for p in old["payloads"] if old["payloads"][p] != self.reviewed["payloads"][p]}, {target})
        self.assertEqual(steve.native.sha256(old["payloads"][target]), layer.OLD_PAC_SHA256)
        self.assertEqual(steve.native.sha256(self.reviewed["payloads"][target]), layer.NEW_PAC_SHA256)
        source, payload = old["payloads"][target], self.reviewed["payloads"][target]
        self.assertEqual((len(source), len(payload)), (96721, 96505))
        from check_steve_head_visible_layer import independent_geometry
        a, b = independent_geometry(source, False), independent_geometry(payload, True)
        edits = [(332+4*i,72,36) for i in range(3)]
        edits += [(36,2064,1992),(44,2064,1992),(52,2064,1992)]
        edits += [(93,90529,90529),(89,92593,92521),(85,94657,94513)]
        edits += [(105,92449,92449),(101,94513,94441),(97,96577,96433)]
        import struct
        inverse, allowed = bytearray(payload[:90529]), set()
        for offset, previous, current in edits:
            self.assertEqual(struct.unpack_from('<I',source,offset)[0],previous)
            self.assertEqual(struct.unpack_from('<I',payload,offset)[0],current)
            if previous != current: allowed.update(range(offset,offset+4))
            struct.pack_into('<I',inverse,offset,previous)
        self.assertTrue(all(source[i]==payload[i] for i in range(90529) if i not in allowed))
        for previous,current in zip(a,b):
            self.assertEqual(previous['records'],current['records'])
            self.assertEqual(previous['indices'][:36],current['indices'])
            inverse.extend(payload[current['start']:current['start']+1992])
            inverse.extend(source[previous['start']+1992:previous['start']+2064])
        self.assertEqual(bytes(inverse),source)
        self.assertEqual(layer.restore_pac(payload,source),source)
        for path,digest in ((layer.MATERIAL_PATH,layer.PRESERVED_MATERIAL_SHA256),(layer.DIFFUSE_PATH,layer.DIFFUSE_SHA256)):
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
        self.assertEqual(len(reports), 10)
        reports[str(helper.HEAD_VISIBLE_LAYER_REPORT.relative_to(steve.ROOT))] = HEAD_REPORT_SHA256
        self.assertEqual(self.reviewed["report"]["candidateReports"], reports)
        self.assertEqual(len(reports), 11)
        candidate, payloads, _ = layer.load_candidate(helper.HEAD_VISIBLE_LAYER_REPORT)
        row = copy.deepcopy(candidate["candidateResources"][0])
        row["localFile"] = str((helper.HEAD_VISIBLE_LAYER_REPORT.parent / row["localFile"]).relative_to(steve.ROOT))
        self.assertEqual(new_rows[target], row)
        self.assertEqual(payloads[target], payload)
        original, updated = packer.encoded_entries(old["package"]), packer.encoded_entries(self.reviewed["package"])
        for path,(entry,raw) in updated.items():
            previous,previous_raw = original[path]
            if path != target:
                self.assertEqual((raw,entry.flags,entry.orig_size),(previous_raw,previous.flags,previous.orig_size),path)
        self.assertEqual((updated[target][0].flags,updated[target][0].orig_size),(1,96505))
        self.assertEqual(updated[layer.MATERIAL_PATH][0].flags,50)
        self.assertEqual(updated[layer.DIFFUSE_PATH][0].flags,0)
        self.assertEqual(self.reviewed["probeVariant"],self.expected_variant)
        self.assertIn("headVisibleLayerComposition",self.reviewed["report"])
        self.assertIn("headUvComposition",old["report"])
        self.assertNotIn("headUvComposition",self.reviewed["report"])
        self.assertNotIn("headVisibleLayerComposition",old["report"])
        self.assertFalse(self.reviewed["report"]["headVisibleLayerComposition"]["nativeShaderUvConventionVerified"])
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
                    {"head_visible_layer_path":self.test_root/"unknown-report.json"}]
        for change in changes:
            with self.subTest(change=change),mock.patch.object(helper.assembly,"load_candidate") as opened:
                with self.assertRaisesRegex(ValueError,"Head visible-layer control"):
                    helper.candidates(helper.DEFAULT_ASSEMBLY,helper.DEFAULT_APPEARANCE,
                        **{**self.base_options(),"head_visible_layer_path":helper.HEAD_VISIBLE_LAYER_REPORT,**change})
                opened.assert_not_called()
        with mock.patch.object(layer,"load_candidate") as opened,mock.patch.object(steve.native,"file_hash") as hashed:
            with self.assertRaises(ValueError):
                packer.load_head(self.test_root/"unknown-report.json",{})
            opened.assert_not_called()
            hashed.assert_not_called()

    def test_27_body_exact_report_set_rejects_missing_or_mixed_modes_before_hash(self):
        plan,path,original = self.altered_plan()
        # Dropping visible-layer alone produces the valid predecessor report-name set;
        # inherited test23 rejects the mismatching PAC after its ordinary read.
        names = (*self.control_reports[:-1],"steve-assembly-report.json","steve-appearance-report.json")
        for name in (*names,"steve-app-report.json","steve-head-mesh-control-report.json","unknown-report.json","duplicate-visible-layer"):
            report = copy.deepcopy(original)
            if name in names:
                del report["candidateReports"][next(p for p in report["candidateReports"] if p.endswith(name))]
            else:
                report["candidateReports"]["build/unused/"+(layer.REPORT_NAME if name == "duplicate-visible-layer" else name)] = "0"*64
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(name=name),mock.patch.object(steve.native,"file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        self.assert_original()

    def test_28_body_pins_prior_body_pac_and_pami_and_preserves_generic_duplicate_rejection(self):
        resources,reports,snapshot = self.body_candidates()
        for target in (layer.PAC_PATH,layer.MATERIAL_PATH,layer.DIFFUSE_PATH):
            changed = copy.deepcopy(resources)
            changed[target]["payload"] += b"tampered"
            changed[target]["row"]["sha256"] = steve.native.sha256(changed[target]["payload"])
            with self.subTest(target=target),mock.patch.object(layer,"load_candidate") as opened:
                with self.assertRaisesRegex(ValueError,"fixed prior head PAC, PAMI and DDS"):
                    helper.apply_head_visible_layer(changed,dict(reports),dict(snapshot),helper.HEAD_VISIBLE_LAYER_REPORT)
                opened.assert_not_called()
        for target in (layer.PAC_PATH,layer.MATERIAL_PATH):
            changed=copy.deepcopy(resources)
            changed[target]["row"]["archiveFlags"] = 0
            with mock.patch.object(layer,"load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.apply_head_visible_layer(changed,dict(reports),dict(snapshot),helper.HEAD_VISIBLE_LAYER_REPORT)
                opened.assert_not_called()
        earlier = dict(reports)
        del earlier[next(p for p in earlier if p.endswith("steve-head-basecolor-report.json"))]
        with mock.patch.object(layer,"load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_visible_layer(copy.deepcopy(resources),earlier,dict(snapshot),helper.HEAD_VISIBLE_LAYER_REPORT)
            opened.assert_not_called()
        updated,after_reports,after_snapshot = copy.deepcopy(resources),dict(reports),dict(snapshot)
        helper.apply_head_visible_layer(updated,after_reports,after_snapshot,helper.HEAD_VISIBLE_LAYER_REPORT)
        with mock.patch.object(layer,"load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_visible_layer(updated,after_reports,after_snapshot,helper.HEAD_VISIBLE_LAYER_REPORT)
            opened.assert_not_called()
        with self.assertRaisesRegex(ValueError,"Duplicate overlay resource"):
            helper.overlay.load_resources([helper.DEFAULT_ASSEMBLY,helper.HEAD_VISIBLE_LAYER_REPORT])
        self.assert_original()

    def test_29_body_payload_tamper_rejects_updated_inner_and_outer_hashes(self):
        plan,path,original = self.altered_plan()
        key = next(p for p in original["candidateReports"] if p.endswith(layer.REPORT_NAME))
        copied = self.test_root/"tampered-visible-layer"
        shutil.copytree(helper.HEAD_VISIBLE_LAYER_REPORT.parent,copied)
        report_path = copied/layer.REPORT_NAME
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
            report_path.write_bytes(layer.report_bytes(candidate))
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
        options = {"baseline":self.baseline_plan,"head_report":helper.HEAD_VISIBLE_LAYER_REPORT,"source":self.source,"deps":self.deps}
        cases = [packer.DEFAULT_OUTPUT/"unused-child",packer.DEFAULT_OUTPUT.parent,packer.DEFAULT_BASELINE,
                 packer.DEFAULT_BASELINE/"unused-child",helper.HEAD_VISIBLE_LAYER_REPORT.parent/"unused-child",
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
                del report["headVisibleLayerComposition"]
            elif change == "old-composition":
                report["headUvComposition"] = report.pop("headVisibleLayerComposition")
            elif change == "runtime-claim":
                report["headVisibleLayerComposition"]["nativeShaderUvConventionVerified"] = True
            else:
                report["headVisibleLayerComposition"]["baselineReportSha256" if change == "baseline-pin" else "candidateReportSha256"] = "0"*64
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
                packer.prepare(output=output,head_report=helper.HEAD_VISIBLE_LAYER_REPORT,source=self.source,deps=self.deps)
        self.assertFalse(output.exists())
        self.assert_production_unchanged()

    def test_34_read_snapshot_covers_current_ten_nine_eight_and_candidate_sources(self):
        snapshot=self.reviewed["readSnapshot"]
        self.assertTrue(all(isinstance(path,Path) and path.is_absolute() and isinstance(raw,bytes)
                            for path,raw in snapshot.items()))
        for plan in (self.plan,helper.HEAD_UV_OUTPUT,helper.HEAD_BASECOLOR_OUTPUT,helper.BODY_NATIVE_MATERIAL_OUTPUT):
            path=plan/"reports/overlay-report.json"
            self.assertIn(path,snapshot)
            raw=snapshot[path]; report=json.loads(raw)
            self.assertEqual(raw,path.read_bytes())
            for relative,digest in report["files"].items():
                file=transaction.target(plan,relative)
                self.assertIn(file,snapshot)
                self.assertEqual(steve.native.sha256(snapshot[file]),digest)
                self.assertEqual(snapshot[file],file.read_bytes())
            for relative,digest in report["candidateReports"].items():
                file=steve.build_path(relative)
                self.assertIn(file,snapshot)
                self.assertEqual(steve.native.sha256(snapshot[file]),digest)
        _,_,incoming=layer.load_candidate(helper.HEAD_VISIBLE_LAYER_REPORT)
        for file,raw in incoming.items(): self.assertEqual(snapshot[file],raw)
        _,_,candidate_sources=helper.candidates(helper.DEFAULT_ASSEMBLY,helper.DEFAULT_APPEARANCE,
            **self.base_options(),head_visible_layer_path=helper.HEAD_VISIBLE_LAYER_REPORT)
        for file,raw in candidate_sources.items(): self.assertEqual(snapshot[file],raw)
        key=next(iter(snapshot))
        with self.assertRaisesRegex(ValueError,"changed between reads"):
            steve.merge_read_snapshot(dict(snapshot),{key:b"conflicting bytes"})
        snapshot_copy=dict(snapshot);snapshot_copy.pop(key)
        self.assertIn(key,self.reviewed["readSnapshot"])
        separately_admitted=steve.load_plan(self.plan)["readSnapshot"]
        self.assertIsNot(separately_admitted,snapshot)
        self.assertEqual(separately_admitted,snapshot)
        separately_admitted.pop(key)
        self.assertIn(key,snapshot)
        self.assert_production_unchanged()

    def test_35_final_source_manifest_package_and_metadata_reread_refuses_races(self):
        plan,_,_=self.altered_plan()
        candidate=json.loads(helper.HEAD_VISIBLE_LAYER_REPORT.read_bytes())
        source=helper.HEAD_VISIBLE_LAYER_REPORT.parent/next(iter(candidate["sources"].values()))["localFile"]
        targets=(source,plan/"reports/overlay-report.json",plan/"package/0041/0.paz",plan/"metadata-after/0.pathc")
        real_validate,real_read=packer.validate_composition,Path.read_bytes
        for target in targets:
            armed=False
            def raced(report,package,before,after,payloads):
                nonlocal armed
                result=real_validate(report,package,before,after,payloads)
                self.assertIn(target,result)
                armed=True
                return result
            def changed_read(path):
                raw=real_read(path)
                if armed and path==target:
                    return raw[:-1]+bytes([raw[-1]^1])
                return raw
            with self.subTest(target=target),mock.patch.object(packer,"validate_composition",side_effect=raced), \
                    mock.patch.object(Path,"read_bytes",changed_read):
                with self.assertRaisesRegex(ValueError,"changed before publication"):
                    steve.load_plan(plan)
        self.assert_original()
        self.assert_production_unchanged()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,default=SteveHeadVisibleLayerOverlayChecks.plan)
    parser.add_argument("--rebuild",action="store_true")
    args = parser.parse_args()
    case = SteveHeadVisibleLayerOverlayChecks
    case.plan,case.rebuild = steve.native.output_directory(args.plan),args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
