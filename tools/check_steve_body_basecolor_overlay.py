"""Check the twelve-report body-basecolor package in owned fake game fixtures.

Only the generic transaction suite is inherited. Body-specific provenance,
payload, encoded-entry, writer and output gates are checked independently.
No process, HTTP service, production save or game asset is changed.
"""
from __future__ import annotations

import argparse
import copy
import inspect
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import unittest
from unittest import mock

from check_asset_probe import ProbeChecks
from check_steve_probe import SteveProbeChecks
from check_steve_head_basecolor_overlay import production_snapshot
import install_asset_probe as transaction
import install_steve_probe as steve
import prepare_steve_body_basecolor as body
import prepare_steve_body_basecolor_overlay as packer

helper = steve.steve
BASELINE_SHA256 = "e86048837217e7cd85ac957d12db2b05b3315449234e8639668ebf627665add1"
TARGET_PATH = "character/modelproperty/1_pc/1_phm/nude/crimsonmc_steve_body_1_21_1.pac_xml"
TARGET_SHA256 = "93bebbb4ed90a43d706230def1670b488dbf723fc7dfcebce910e76f8b069b2b"
TARGET_SIZE = 50017
COMPOSITION_KEY = "bodyBasecolorComposition"


class SteveBodyBasecolorOverlayChecks(SteveProbeChecks):
    """Generic install/restore faults plus independent body composition checks."""
    plan = helper.BODY_BASECOLOR_OUTPUT
    baseline_plan = helper.HEAD_VISIBLE_LAYER_OUTPUT
    resource_count = 14
    rebuild = False

    @classmethod
    def setUpClass(cls):
        baseline_manifest = cls.baseline_plan / "reports/overlay-report.json"
        if steve.native.file_hash(baseline_manifest) != BASELINE_SHA256:
            raise ValueError("Body-basecolor checks require the fixed eleven-report baseline SHA")
        baseline_report = json.loads(baseline_manifest.read_bytes())
        indexes = baseline_report["sourceIndexes"]
        cls.production_source_paths = tuple(sorted(indexes))
        if len(indexes) != 34 or any(re.fullmatch(r"[0-9]{4}/0\.pamt", p.replace("\\", "/")) is None for p in indexes):
            raise ValueError("Body-basecolor fixture requires 34 original PAMT paths")
        installation = json.loads((steve.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))
        cls.production_game = Path(installation["gameRoot"])
        cls.production_receipt = steve.ROOT / transaction.RECEIPT
        cls.production_hasher = steve.native.file_hash
        cls.initial_production = production_snapshot(cls.production_game, cls.production_source_paths,
            cls.production_receipt, cls.production_hasher)
        cls.fixture_finished = False
        cls.production_snapshot_verified = False
        cls.fixture_removed = False
        cls.addClassCleanup(cls.finish_fixture)
        # The shared fixture uses actual immutable index copies and a fake EXE;
        # never use a head-mode class's setup or its target-specific tests.
        ProbeChecks.setUpClass.__func__(cls)
        if cls.real_game.resolve() != cls.production_game.resolve() or cls.observed != cls.initial_production["indexes"]:
            raise AssertionError("Production identity or original indexes changed during fixture setup")
        cls.expected_replacements = tuple(baseline_report["replacementPaths"])
        cls.baseline = steve.load_plan(cls.baseline_plan)
        cls.assert_production_unchanged()

    @classmethod
    def assert_production_unchanged(cls):
        actual = production_snapshot(cls.production_game, cls.production_source_paths,
            cls.production_receipt, cls.production_hasher)
        if actual != cls.initial_production:
            raise AssertionError("Production metadata, receipt, installed package or original indexes changed")

    @classmethod
    def finish_fixture(cls):
        if cls.fixture_finished:
            return
        cls.fixture_finished = True
        try:
            patched = cls.__dict__.get("hash_patch")
            if patched is not None:
                patched.stop()
            cls.assert_production_unchanged()
            cls.production_snapshot_verified = True
        finally:
            temporary = cls.__dict__.get("temporary")
            if temporary is not None:
                owned, build = Path(temporary.name).resolve(), (steve.ROOT / "build").resolve()
                if (not owned.is_relative_to(build) or owned == build or not owned.name.startswith("probe-check-")
                        or owned == cls.production_game.resolve()):
                    raise AssertionError("Refusing cleanup outside the explicitly owned fixture directory")
                steve.native.check_links(owned)
                temporary.cleanup()
                cls.fixture_removed = not owned.exists()

    @classmethod
    def tearDownClass(cls):
        cls.finish_fixture()

    def base_options(self, **changes):
        return {"head_descriptor_path": helper.HEAD_DESCRIPTOR_REPORT,
                "part_table_path": helper.PART_TABLE_REPORT, "head_root_path": helper.HEAD_ROOT_REPORT,
                "head_native_material_path": helper.HEAD_NATIVE_MATERIAL_REPORT,
                "clothing_path": helper.CLOTHING_REPORT, "body_native_material_path": helper.BODY_NATIVE_MATERIAL_REPORT,
                "head_basecolor_path": helper.HEAD_BASECOLOR_REPORT, "head_uv_path": helper.HEAD_UV_REPORT,
                "head_visible_layer_path": helper.HEAD_VISIBLE_LAYER_REPORT, **changes}

    def test_16_plan_provenance_matches_resource_set(self):
        plan, manifest, original = self.altered_plan()
        for change in ("reports", "target", "flags", "kind", "payload-path", "report-traversal", "payload-traversal", "template"):
            report = copy.deepcopy(original)
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
                path, digest = report["candidateReports"].popitem()
                report["candidateReports"]["build\\..\\" + path] = digest
            elif change == "payload-traversal":
                report["resources"][0]["localFile"] = "build\\..\\" + report["resources"][0]["localFile"]
            else:
                report["resources"][0]["templatePath"] = "character/another.dds"
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        manifest.write_bytes(packer.report_bytes(original))
        self.assertEqual(len(steve.load_plan(plan)["payloads"]), 14)
        self.assert_original()

    def test_21_real_fresh_overlay_rebuild_is_identical_and_never_installs(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a fresh fixed-local body-basecolor composition")
        self.assertNotIn("game", inspect.signature(packer.prepare).parameters)
        self.assertNotIn("game_root", inspect.signature(packer.prepare).parameters)
        output = self.test_root / "rebuilt-body-basecolor-overlay"
        real_open, production = Path.open, self.production_game.resolve()
        def offline_open(path, *args, **kwargs):
            if path.resolve().is_relative_to(production):
                raise AssertionError("Offline body composition opened the production game")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", offline_open):
            packer.prepare(output=output, baseline=self.baseline_plan, body_report=helper.BODY_BASECOLOR_REPORT,
                source=self.source, deps=self.deps)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes(), relative)
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_original()
        self.assert_production_unchanged()

    def test_22_only_body_pami_changes_and_all_thirteen_encoded_resources_are_preserved(self):
        old = self.baseline
        self.assertEqual(old["reportSha256"], BASELINE_SHA256)
        self.assertEqual(packer.BASELINE_REPORT_SHA256, BASELINE_SHA256)
        self.assertEqual(body.MATERIAL_PATH, TARGET_PATH)
        self.assertEqual(body.NEW_MATERIAL_SHA256, TARGET_SHA256)
        self.assertEqual(set(old["payloads"]), set(self.reviewed["payloads"]))
        self.assertEqual(len(self.reviewed["payloads"]), 14)
        changed = {path for path in old["payloads"] if old["payloads"][path] != self.reviewed["payloads"][path]}
        self.assertEqual(changed, {TARGET_PATH})
        self.assertEqual(steve.native.sha256(old["payloads"][TARGET_PATH]), body.NATIVE_MATERIAL_SHA256)
        self.assertEqual(steve.native.sha256(self.reviewed["payloads"][TARGET_PATH]), TARGET_SHA256)
        self.assertEqual((len(old["payloads"][TARGET_PATH]), len(self.reviewed["payloads"][TARGET_PATH])), (TARGET_SIZE, TARGET_SIZE))
        self.assertEqual(body.restore_material(self.reviewed["payloads"][TARGET_PATH]), old["payloads"][TARGET_PATH])
        original, updated = packer.encoded_entries(old["package"]), packer.encoded_entries(self.reviewed["package"])
        self.assertEqual(set(original), set(updated))
        preserved = 0
        for path, (entry, raw) in updated.items():
            previous, previous_raw = original[path]
            if path != TARGET_PATH:
                self.assertEqual((raw, entry.flags, entry.orig_size), (previous_raw, previous.flags, previous.orig_size), path)
                preserved += 1
        self.assertEqual(preserved, 13)
        self.assertEqual((updated[TARGET_PATH][0].flags, updated[TARGET_PATH][0].orig_size), (50, TARGET_SIZE))
        self.assertEqual(self.reviewed["before"], old["before"])
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        for key in ("sourceIndexes", "replacementPaths", "absentOptionalMountedDirectories"):
            self.assertEqual(self.reviewed["report"][key], old["report"][key])
        old_rows = {row["virtualPath"]: row for row in old["report"]["resources"]}
        new_rows = {row["virtualPath"]: row for row in self.reviewed["report"]["resources"]}
        self.assertEqual({p:r for p,r in old_rows.items() if p != TARGET_PATH}, {p:r for p,r in new_rows.items() if p != TARGET_PATH})
        candidate, payloads, _ = body.load_candidate(helper.BODY_BASECOLOR_REPORT)
        row = copy.deepcopy(candidate["candidateResources"][0])
        row["localFile"] = str((helper.BODY_BASECOLOR_REPORT.parent / row["localFile"]).relative_to(steve.ROOT))
        self.assertEqual(new_rows[TARGET_PATH], row)
        self.assertEqual(payloads[TARGET_PATH], self.reviewed["payloads"][TARGET_PATH])
        reports = dict(old["report"]["candidateReports"])
        self.assertEqual(len(reports), 11)
        reports[str(helper.BODY_BASECOLOR_REPORT.relative_to(steve.ROOT))] = steve.native.file_hash(helper.BODY_BASECOLOR_REPORT)
        self.assertEqual(self.reviewed["report"]["candidateReports"], reports)
        self.assertEqual(len(reports), 12)
        self.assertEqual(self.reviewed["probeVariant"], packer.VARIANT)
        self.assertEqual(self.reviewed["report"][COMPOSITION_KEY]["preservedEncodedResourceCount"], 13)
        self.assertNotIn("headVisibleLayerComposition", self.reviewed["report"])

    def test_23_original_metadata_and_actual_new_crc_mount_are_exact(self):
        from cdmw.core.archive_format import calculate_pa_checksum
        from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
        pamt = (self.reviewed["package"] / "0.pamt").read_bytes()
        after = papgt_with_directory(self.baseline["before"]["meta/0.papgt"], self.reviewed["name"],
            calculate_pa_checksum(pamt[12:]), flags=PAPGT_DEFAULT_FLAGS, first=True)
        self.assertEqual(self.reviewed["after"]["meta/0.papgt"], after)
        self.assertEqual(self.reviewed["before"], self.baseline["before"])
        for relative, raw in self.reviewed["before"].items():
            self.assertEqual((self.plan / "metadata-before" / Path(relative).name).read_bytes(), raw)
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], self.baseline["after"]["meta/0.pathc"])

    def test_24_dependency_options_and_mixed_modes_fail_before_assembly_io(self):
        changes = [{key:None} for key in self.base_options()]
        changes += [{"app_path": self.test_root / "unused-app.json"}, {"head_mesh_control_path": helper.HEAD_MESH_CONTROL_REPORT}]
        for change in changes:
            with self.subTest(change=change), mock.patch.object(helper.assembly, "load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE,
                        **{**self.base_options(), "body_basecolor_path":helper.BODY_BASECOLOR_REPORT, **change})
                opened.assert_not_called()
        with mock.patch.object(body, "load_candidate") as opened, mock.patch.object(steve.native, "file_hash") as hashed:
            with self.assertRaises(ValueError):
                packer.load_body(self.test_root / "unknown-report.json", {})
            opened.assert_not_called()
            hashed.assert_not_called()

    def test_25_strict_twelve_report_set_rejects_missing_mixed_or_duplicate_names(self):
        plan, manifest, original = self.altered_plan()
        names = set(packer.COMPOSITION_REPORT_NAMES)
        self.assertEqual(len(names), 12)
        self.assertEqual({Path(path).name for path in original["candidateReports"]}, names)
        for name in sorted(names - {body.REPORT_NAME}):
            report = copy.deepcopy(original)
            del report["candidateReports"][next(path for path in report["candidateReports"] if Path(path).name == name)]
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(missing=name), mock.patch.object(steve.native, "file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        for name in ("steve-app-report.json", "steve-head-mesh-control-report.json", "unknown-report.json", body.REPORT_NAME):
            report = copy.deepcopy(original)
            report["candidateReports"]["build/unused/" + name] = "0" * 64
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(extra=name), mock.patch.object(steve.native, "file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        # Removing only the final report leaves a legitimate predecessor name
        # set. Its fixed old body payload must still reject these new bytes.
        report = copy.deepcopy(original)
        del report["candidateReports"][next(path for path in report["candidateReports"] if Path(path).name == body.REPORT_NAME)]
        manifest.write_bytes(packer.report_bytes(report))
        with self.assertRaises(ValueError):
            steve.load_plan(plan)
        self.assert_original()

    def test_26_candidate_and_source_tamper_cannot_relabel_inner_and_outer_hashes(self):
        plan, manifest, original = self.altered_plan()
        key = next(path for path in original["candidateReports"] if Path(path).name == body.REPORT_NAME)
        copied = self.test_root / "tampered-body-candidate"
        shutil.copytree(helper.BODY_BASECOLOR_REPORT.parent, copied)
        candidate_path = copied / body.REPORT_NAME
        candidate_raw = candidate_path.read_bytes()
        candidate_original = json.loads(candidate_raw)
        for relative in candidate_original["files"]:
            file = copied / relative
            original_raw = file.read_bytes()
            mutated = original_raw[:-1] + bytes([original_raw[-1] ^ 1])
            file.write_bytes(mutated)
            candidate = copy.deepcopy(candidate_original)
            digest = steve.native.sha256(mutated)
            candidate["files"][relative] = digest
            for source in candidate["sources"].values():
                if source["localFile"] == relative:
                    source["sha256"] = digest
            for row in candidate["candidateResources"]:
                if row["localFile"] == relative:
                    row["sha256"] = digest
            candidate_path.write_bytes(body.report_bytes(candidate))
            report = copy.deepcopy(original)
            del report["candidateReports"][key]
            report["candidateReports"][str(candidate_path.relative_to(steve.ROOT))] = steve.native.file_hash(candidate_path)
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                steve.load_plan(plan)
            file.write_bytes(original_raw)
            candidate_path.write_bytes(candidate_raw)
        self.assert_original()

    def test_27_complete_writer_rejects_padding_after_all_checksums_are_recomputed(self):
        from cdmw.core.archive_entry_addition import parse_pamt_document
        from cdmw.core.archive_format import calculate_pa_checksum
        from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
        plan, manifest, original = self.altered_plan()
        package = plan / "package" / original["directoryName"]
        pamt_path, paz_path = package / "0.pamt", package / "0.paz"
        paz = paz_path.read_bytes() + bytes(16)
        document = parse_pamt_document(pamt_path.read_bytes())
        document.set_paz_record(0, checksum=calculate_pa_checksum(paz), size=len(paz))
        pamt = document.serialize()
        pamt_path.write_bytes(pamt)
        paz_path.write_bytes(paz)
        before_papgt = (plan / "metadata-before/0.papgt").read_bytes()
        after_papgt = papgt_with_directory(before_papgt, original["directoryName"],
            calculate_pa_checksum(pamt[12:]), flags=PAPGT_DEFAULT_FLAGS, first=True)
        (plan / "metadata-after/0.papgt").write_bytes(after_papgt)
        report = copy.deepcopy(original)
        for relative in (f"package/{original['directoryName']}/0.pamt", f"package/{original['directoryName']}/0.paz", "metadata-after/0.papgt"):
            report["files"][relative] = steve.native.file_hash(plan / relative)
        report["packageAudit"] = helper.overlay.audit_package(package, report["resources"], self.reviewed["payloads"])
        report["mountAudit"] = helper.overlay.audit_mounts(before_papgt, after_papgt, original["directoryName"], pamt)
        self.assertTrue(report["packageAudit"]["payloadBoundariesAndChecksumsValid"])
        self.assertTrue(report["packageAudit"]["allPayloadsDecodeByteIdentically"])
        manifest.write_bytes(packer.report_bytes(report))
        with self.assertRaisesRegex(ValueError, "complete fixed writer reconstruction"):
            steve.load_plan(plan)
        self.assert_original()

    def test_28_composition_claims_unknown_fields_and_canonical_source_metadata_reject(self):
        plan, manifest, original = self.altered_plan()
        changes = ("missing-composition", "baseline-pin", "candidate-pin", "nativeApplied", "nativeFormatAcceptanceVerified",
                   "mcBodySkinVerified", "mcRuntimeActionsVerified", "old-composition", "index-digest", "package-audit", "unknown-field")
        for change in changes:
            report = copy.deepcopy(original)
            if change == "missing-composition":
                del report[COMPOSITION_KEY]
            elif change in ("baseline-pin", "candidate-pin"):
                report[COMPOSITION_KEY]["baselineReportSha256" if change == "baseline-pin" else "candidateReportSha256"] = "0" * 64
            elif change in ("nativeApplied", "nativeFormatAcceptanceVerified", "mcBodySkinVerified", "mcRuntimeActionsVerified"):
                self.assertIs(original[COMPOSITION_KEY][change], False)
                report[COMPOSITION_KEY][change] = True
            elif change == "old-composition":
                report["headVisibleLayerComposition"] = self.baseline["report"]["headVisibleLayerComposition"]
            elif change == "index-digest":
                path = next(iter(report["sourceIndexes"]))
                digest = report["sourceIndexes"][path]
                report["sourceIndexes"][path] = ("1" if digest[0] == "0" else "0") + digest[1:]
            elif change == "package-audit":
                report["packageAudit"]["allPayloadsDecodeByteIdentically"] = False
            else:
                report["unreviewedBodyCompositionField"] = True
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "complete fixed-baseline reconstruction"):
                steve.load_plan(plan)
        self.assert_original()

    def test_29_output_overlap_and_existing_output_fail_before_loading_or_mkdir(self):
        options = {"baseline": self.baseline_plan, "body_report": helper.BODY_BASECOLOR_REPORT,
                   "source": self.source, "deps": self.deps}
        cases = [{"output": packer.DEFAULT_OUTPUT / "unused-child"}, {"output": packer.DEFAULT_OUTPUT.parent},
                 {"output": self.baseline_plan}, {"output": self.baseline_plan / "unused-child"},
                 {"output": helper.BODY_BASECOLOR_REPORT.parent / "unused-child"},
                 {"output": self.source / "unused-child"}, {"output": self.deps / "unused-child"},
                 {"output": self.test_root / "source-inputs", "source": self.test_root / "source-inputs/cdmw"},
                 {"output": self.test_root / "baseline-inputs", "baseline": self.test_root / "baseline-inputs/plan"}]
        existing = self.test_root / "existing-output"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_bytes(b"Unrelated retained output")
        cases.append({"output": existing})
        for change in cases:
            with self.subTest(change=change), mock.patch.object(packer, "fixed_cdmw") as loaded_source, \
                    mock.patch.object(packer, "load_baseline") as loaded_plan, mock.patch.object(Path, "mkdir") as made:
                with self.assertRaises(ValueError):
                    packer.prepare(**{**options, **change})
                loaded_source.assert_not_called()
                loaded_plan.assert_not_called()
                made.assert_not_called()
        self.assertEqual(marker.read_bytes(), b"Unrelated retained output")
        self.assert_original()

    def test_30_snapshot_conflicts_refuse_and_read_snapshot_contains_every_composition_source(self):
        snapshot = self.reviewed["readSnapshot"]
        self.assertTrue(all(isinstance(path, Path) and path.is_absolute() and isinstance(raw, bytes) for path,raw in snapshot.items()))
        for plan in (self.plan, self.baseline_plan, helper.HEAD_UV_OUTPUT, helper.HEAD_BASECOLOR_OUTPUT, helper.BODY_NATIVE_MATERIAL_OUTPUT):
            manifest = plan / "reports/overlay-report.json"
            self.assertEqual(snapshot[manifest], manifest.read_bytes())
            report = json.loads(snapshot[manifest])
            for relative, digest in report["files"].items():
                path = transaction.target(plan, relative)
                self.assertEqual(steve.native.sha256(snapshot[path]), digest)
            for relative, digest in report["candidateReports"].items():
                self.assertEqual(steve.native.sha256(snapshot[steve.build_path(relative)]), digest)
        _, _, candidate_sources = body.load_candidate(helper.BODY_BASECOLOR_REPORT)
        for path, raw in candidate_sources.items():
            self.assertEqual(snapshot[path], raw)
        key = next(iter(snapshot))
        with self.assertRaisesRegex(ValueError, "changed between reads"):
            steve.merge_read_snapshot(dict(snapshot), {key:b"conflicting bytes"})
        separately_admitted = steve.load_plan(self.plan)["readSnapshot"]
        self.assertIsNot(separately_admitted, snapshot)
        self.assertEqual(separately_admitted, snapshot)
        separately_admitted.pop(key)
        self.assertIn(key, snapshot)

    def test_31_source_race_stops_publication_and_creates_no_output(self):
        baseline, snapshot = packer.load_baseline(self.baseline_plan)
        fixture = self.test_root / "watched-source.bin"
        fixture.write_bytes(b"admitted source")
        raced = {**snapshot, fixture.resolve():b"admitted source"}
        real_load = packer.load_body
        def changed_source(*args, **kwargs):
            result = real_load(*args, **kwargs)
            fixture.write_bytes(b"changed after source admission")
            return result
        output = self.test_root / "source-race-output"
        with mock.patch.object(packer, "load_baseline", return_value=(baseline, raced)), \
                mock.patch.object(packer, "load_body", side_effect=changed_source):
            with self.assertRaisesRegex(ValueError, "changed before publication"):
                packer.prepare(output=output, baseline=self.baseline_plan, body_report=helper.BODY_BASECOLOR_REPORT,
                    source=self.source, deps=self.deps)
        self.assertFalse(output.exists())
        self.assert_original()

    def test_32_final_manifest_package_and_source_reread_rejects_races(self):
        plan, _, _ = self.altered_plan()
        candidate = json.loads(helper.BODY_BASECOLOR_REPORT.read_bytes())
        source = helper.BODY_BASECOLOR_REPORT.parent / next(iter(candidate["sources"].values()))["localFile"]
        targets = (source, plan / "reports/overlay-report.json", plan / "package/0041/0.paz", plan / "metadata-after/0.pathc")
        real_validate, real_read = packer.validate_composition, Path.read_bytes
        for target in targets:
            armed = False
            def complete_then_race(report, package, before, after, payloads):
                nonlocal armed
                result = real_validate(report, package, before, after, payloads)
                self.assertIn(target, result)
                armed = True
                return result
            def changed_read(path):
                raw = real_read(path)
                return raw[:-1] + bytes([raw[-1] ^ 1]) if armed and path == target else raw
            with self.subTest(target=target), mock.patch.object(packer, "validate_composition", side_effect=complete_then_race), \
                    mock.patch.object(Path, "read_bytes", changed_read):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    steve.load_plan(plan)
        self.assert_original()

    def test_33_fresh_process_rebuild_is_deterministic_without_game_or_network(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a fresh-process deterministic composition")
        output = self.test_root / "fresh-process-body-overlay"
        # This independent process guards file opens and sockets, rather than
        # asserting that a mocked authoring method merely returned success.
        program = "\n".join((
            "from pathlib import Path", "import socket, sys", "from unittest import mock",
            f"sys.path.insert(0, {str(steve.ROOT / 'tools')!r})", "import prepare_steve_body_basecolor_overlay as packer",
            f"production=Path({str(self.production_game.resolve())!r})", "original_open=Path.open",
            "def guarded_open(path,*args,**kwargs):",
            "    if path.resolve().is_relative_to(production): raise AssertionError('Production game opened')",
            "    return original_open(path,*args,**kwargs)",
            "with mock.patch.object(Path,'open',guarded_open), mock.patch.object(socket,'socket',side_effect=AssertionError('Network forbidden')):",
            f"    packer.prepare(output=Path({str(output)!r}),baseline=Path({str(self.baseline_plan)!r}),body_report=Path({str(helper.BODY_BASECOLOR_REPORT)!r}),source=Path({str(self.source)!r}),deps=Path({str(self.deps)!r}))",
        ))
        result = subprocess.run([sys.executable, "-B", "-c", program], cwd=steve.ROOT,
            capture_output=True, text=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes(), relative)
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_original()
        self.assert_production_unchanged()

    def test_34_prior_resource_pins_and_duplicate_application_reject_before_candidate_io(self):
        resources, reports, snapshot = helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE,
            **self.base_options())
        for target in (body.MATERIAL_PATH, body.PAC_PATH, body.DIFFUSE_PATH):
            changed = copy.deepcopy(resources)
            changed[target]["payload"] += b"tampered"
            changed[target]["row"]["sha256"] = steve.native.sha256(changed[target]["payload"])
            with self.subTest(payload=target), mock.patch.object(body, "load_candidate") as opened:
                with self.assertRaisesRegex(ValueError, "fixed prior body PAMI, PAC and DDS"):
                    helper.apply_body_basecolor(changed, dict(reports), dict(snapshot), helper.BODY_BASECOLOR_REPORT)
                opened.assert_not_called()
        for target, field, value in ((body.MATERIAL_PATH,"archiveFlags",0),
                                     (body.PAC_PATH,"templateArchiveFlags",0),
                                     (body.PAC_PATH,"archiveFlags",0),
                                     (body.DIFFUSE_PATH,"kind","skinnedMaterial")):
            changed = copy.deepcopy(resources)
            changed[target]["row"][field] = value
            with self.subTest(target=target,field=field), mock.patch.object(body, "load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.apply_body_basecolor(changed, dict(reports), dict(snapshot), helper.BODY_BASECOLOR_REPORT)
                opened.assert_not_called()
        earlier = dict(reports)
        del earlier[next(path for path in earlier if Path(path).name == "steve-head-visible-layer-report.json")]
        with mock.patch.object(body, "load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_body_basecolor(copy.deepcopy(resources), earlier, dict(snapshot), helper.BODY_BASECOLOR_REPORT)
            opened.assert_not_called()
        updated, after_reports, after_snapshot = copy.deepcopy(resources), dict(reports), dict(snapshot)
        helper.apply_body_basecolor(updated, after_reports, after_snapshot, helper.BODY_BASECOLOR_REPORT)
        with mock.patch.object(body, "load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_body_basecolor(updated, after_reports, after_snapshot, helper.BODY_BASECOLOR_REPORT)
            opened.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Duplicate overlay resource"):
            helper.overlay.load_resources([helper.DEFAULT_ASSEMBLY, helper.BODY_BASECOLOR_REPORT])
        self.assert_original()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=SteveBodyBasecolorOverlayChecks.plan)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--output", type=Path, help="Fresh direct-child build evidence directory; never overwrite")
    args = parser.parse_args()
    case = SteveBodyBasecolorOverlayChecks
    case.plan, case.rebuild = steve.native.output_directory(args.plan), args.rebuild
    output = None
    if args.output is not None:
        output = steve.native.output_directory(args.output)
        build = (steve.ROOT / "build").resolve()
        if (output.parent != build or not output.name.startswith(("steve-body-basecolor-overlay-check-", "steve-body-basecolor-overlay-evidence-"))
                or output.exists()):
            raise ValueError("Evidence needs a new owned direct-child build directory")
    tool_names = ("check_steve_body_basecolor_overlay.py", "prepare_steve_body_basecolor_overlay.py",
                  "prepare_steve_body_basecolor.py", "check_steve_body_basecolor.py",
                  "install_steve_probe.py", "prepare_steve_probe_overlay.py")
    initial_sources = {name:steve.native.file_hash(steve.ROOT / "tools" / name) for name in tool_names}
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    duration = time.monotonic() - started
    if output is not None:
        if output.exists():
            raise ValueError("Evidence directory appeared while checks were running")
        final_sources = {name:steve.native.file_hash(steve.ROOT / "tools" / name) for name in tool_names}
        evidence = {"testsRun":result.testsRun, "passed":result.wasSuccessful(), "success":result.wasSuccessful(),
            "exitCode":0 if result.wasSuccessful() else 1, "duration":duration,
            "errors":[{"test":str(test), "error":error} for test,error in result.errors],
            "failures":[{"test":str(test), "error":error} for test,error in result.failures],
            "skipped":[{"test":str(test), "reason":reason} for test,reason in result.skipped],
            "plan":str(case.plan), "planSha256":steve.native.file_hash(case.plan / "reports/overlay-report.json"),
            "baseline":str(case.baseline_plan), "baselineSha256":steve.native.file_hash(case.baseline_plan / "reports/overlay-report.json"),
            "baselineExpectedSha256":BASELINE_SHA256, "command":sys.argv,
            "initialSourceSha256":initial_sources, "sourceSha256":final_sources, "toolsUnchanged":initial_sources == final_sources,
            "fixtureRemoved":getattr(case,"fixture_removed",False),
            "productionSnapshotVerified":getattr(case,"production_snapshot_verified",False),
            "nativeApplied":False, "installedToProduction":False, "animationSystemComplete":False}
        output.mkdir()
        (output / "offline-check-result.json").write_bytes((json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print(json.dumps({"report":str(output / "offline-check-result.json"), "testsRun":result.testsRun,
                          "passed":result.wasSuccessful()}, ensure_ascii=False))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
