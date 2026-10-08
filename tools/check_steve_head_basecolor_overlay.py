"""Isolated head-basecolor transaction checks, preserving the current production state.

The inherited fixture copies original PAMTs into its own fake game and installs
there only. Production may already have the reviewed body control installed.
"""
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

from check_steve_probe import SteveBodyNativeMaterialProbeChecks
import install_asset_probe as transaction
import install_steve_probe as steve
import prepare_steve_head_basecolor as color

helper = steve.steve
BASELINE_SHA256 = "fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341"
HEAD_REPORT_SHA256 = "56d0ee077c290395c6efcc013c1c48524fe0db1af5c3bea6137d01a944c9f466"


def production_snapshot(game, source_paths, receipt_path, hasher):
    """Read only the fixed original indexes, metadata and active receipt files."""
    steve.native.check_links(game)
    # Parent fixture preserves report keys verbatim; transaction.target accepts
    # only POSIX relative paths for access. Keep dictionary identity unchanged.
    indexes = {name: hasher(transaction.target(game, name.replace("\\", "/"))) for name in source_paths}
    metadata = {}
    for name in (*transaction.METADATA, "meta/0.papk", "meta/0.paver"):
        path = transaction.target(game, name)
        metadata[name] = path.read_bytes() if path.exists() else None
    steve.native.check_links(receipt_path)
    raw_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    files, inventory = {}, None
    if raw_receipt is not None:
        receipt = json.loads(raw_receipt)
        name = receipt.get("directoryName")
        if (not isinstance(name, str) or re.fullmatch(r"[0-9]{4}", name) is None
                or not 36 <= int(name) <= 9999
                or Path(receipt.get("gameRoot", "")).resolve() != game.resolve()):
            raise ValueError("Production receipt does not name the current game and a bounded overlay")
        expected = {name + "/0.pamt", name + "/0.paz", name + "/" + transaction.MARKER}
        if set(receipt.get("installedFiles", {})) != expected:
            raise ValueError("Production receipt installed file inventory differs")
        # A bounded directory name is not a folder-qualified resource path.
        directory = game / name
        steve.native.check_links(directory)
        if not directory.resolve().is_relative_to(game.resolve()):
            raise ValueError("Production overlay directory escaped its game root")
        inventory = tuple(sorted(path.name for path in directory.iterdir())) if directory.exists() else None
        for relative in sorted(expected):
            path = transaction.target(game, relative)
            files[relative] = path.read_bytes() if path.exists() else None
    return {"indexes": indexes, "metadata": metadata, "receiptBytes": raw_receipt,
            "installedFiles": files, "ownedDirectoryInventory": inventory}


class SteveHeadBasecolorOverlayChecks(SteveBodyNativeMaterialProbeChecks):
    plan = helper.HEAD_BASECOLOR_OUTPUT
    baseline_plan = helper.BODY_NATIVE_MATERIAL_OUTPUT
    expected_variant = "steve-kliff-original-head-body-material-empty-armor-head-basecolor-part-table-v2"
    control_reports = (*SteveBodyNativeMaterialProbeChecks.control_reports, color.REPORT_NAME)
    rebuild = False

    @classmethod
    def setUpClass(cls):
        # Snapshot actual current metadata and receipt before the parent creates
        # its original-before fake game. An active body receipt is permitted.
        baseline_report = cls.baseline_plan / "reports/overlay-report.json"
        if steve.native.file_hash(baseline_report) != BASELINE_SHA256:
            raise ValueError("Head-basecolor checks require the fixed body baseline report SHA")
        source_indexes = json.loads(baseline_report.read_bytes())["sourceIndexes"]
        cls.production_source_paths = tuple(sorted(source_indexes))
        if (len(cls.production_source_paths) != 34
                or any(re.fullmatch(r"[0-9]{4}/0\.pamt", name.replace("\\", "/")) is None
                       for name in cls.production_source_paths)):
            raise ValueError("Head-basecolor fixture requires exactly 34 original PAMT paths")
        installation = json.loads((steve.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))
        cls.production_game = Path(installation["gameRoot"])
        cls.production_receipt = steve.ROOT / transaction.RECEIPT
        cls.production_hasher = steve.native.file_hash
        cls.initial_production = production_snapshot(cls.production_game, cls.production_source_paths,
                                                    cls.production_receipt, cls.production_hasher)
        cls.fixture_finished = False
        cls.addClassCleanup(cls.finish_fixture)
        # Keep the original real-PAMT copy, original plan-before metadata,
        # fake executable hash gate and unmocked installer audit_sources.
        super().setUpClass()
        if cls.real_game.resolve() != cls.production_game.resolve():
            raise AssertionError("Parent fixture changed its production game identity")
        if cls.observed != cls.initial_production["indexes"]:
            raise AssertionError("Original PAMTs changed during fixture setup")
        cls.assert_production_unchanged()

    @classmethod
    def assert_production_unchanged(cls):
        actual = production_snapshot(cls.production_game, cls.production_source_paths,
                                     cls.production_receipt, cls.production_hasher)
        if actual != cls.initial_production:
            raise AssertionError("Production metadata, receipt, installed files or original indexes changed")

    @classmethod
    def finish_fixture(cls):
        if cls.fixture_finished:
            return
        cls.fixture_finished = True
        try:
            patch = cls.__dict__.get("hash_patch")
            if patch is not None:
                patch.stop()
            cls.assert_production_unchanged()
        finally:
            temporary = cls.__dict__.get("temporary")
            if temporary is not None:
                owned = Path(temporary.name).resolve()
                build = (steve.ROOT / "build").resolve()
                if (not owned.is_relative_to(build) or owned == build
                        or not owned.name.startswith("probe-check-")
                        or owned == cls.production_game.resolve()):
                    raise AssertionError("Refusing cleanup outside this fixture's explicit owned build directory")
                steve.native.check_links(owned)
                temporary.cleanup()

    @classmethod
    def tearDownClass(cls):
        # Parent teardown compares production to plan.before; the actual initial
        # production snapshot is authoritative for this independent subclass.
        cls.finish_fixture()

    def base_options(self, **changes):
        return {"head_descriptor_path": helper.HEAD_DESCRIPTOR_REPORT,
                "part_table_path": helper.PART_TABLE_REPORT, "head_root_path": helper.HEAD_ROOT_REPORT,
                "head_native_material_path": helper.HEAD_NATIVE_MATERIAL_REPORT,
                "clothing_path": helper.CLOTHING_REPORT,
                "body_native_material_path": helper.BODY_NATIVE_MATERIAL_REPORT, **changes}

    def body_candidates(self):
        return helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE, **self.base_options())

    def test_16_plan_provenance_matches_resource_set(self):
        import prepare_steve_head_basecolor_overlay as packer
        plan, path, original = self.altered_plan()
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
                original_path, digest = report["candidateReports"].popitem()
                report["candidateReports"]["build\\..\\" + original_path] = digest
            elif change == "payload-traversal":
                report["resources"][0]["localFile"] = "build\\..\\" + report["resources"][0]["localFile"]
            else:
                report["resources"][0]["templatePath"] = "character/another.dds"
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        path.write_bytes(packer.report_bytes(original))
        self.assertEqual(len(steve.load_plan(plan)["payloads"]), self.resource_count)
        self.assert_original()
        self.assert_production_unchanged()

    def test_21_real_fresh_overlay_rebuild_is_identical_and_never_installs(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild to compose only from the fixed existing body plan")
        import prepare_steve_head_basecolor_overlay as packer
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assertNotIn("game", inspect.signature(packer.prepare).parameters)
        self.assertNotIn("game_root", inspect.signature(packer.prepare).parameters)
        self.assert_production_unchanged()
        output = self.test_root / "rebuilt-head-basecolor-overlay"
        packer.prepare(output=output, baseline=self.baseline_plan, head_report=helper.HEAD_BASECOLOR_REPORT,
                       source=self.source, deps=self.deps)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes(), relative)
        self.assert_production_unchanged()
        self.assertFalse((self.state / transaction.RECEIPT).exists())
        self.assert_original()

    def test_22_control_adds_exactly_one_reviewed_resource(self):
        import prepare_steve_head_basecolor_overlay as packer
        old = steve.load_plan(self.baseline_plan)
        target = color.MATERIAL_PATH
        self.assertEqual(old["reportSha256"], BASELINE_SHA256)
        self.assertEqual(steve.native.file_hash(helper.HEAD_BASECOLOR_REPORT), HEAD_REPORT_SHA256)
        self.assertEqual(set(old["payloads"]), set(self.reviewed["payloads"]))
        self.assertEqual(len(self.reviewed["payloads"]), 14)
        self.assertEqual({path for path in old["payloads"]
                          if old["payloads"][path] != self.reviewed["payloads"][path]}, {target})
        self.assertEqual(steve.native.sha256(old["payloads"][target]), color.NATIVE_MATERIAL_SHA256)
        self.assertEqual(steve.native.sha256(self.reviewed["payloads"][target]), color.NEW_MATERIAL_SHA256)
        self.assertEqual([len(old["payloads"][target]), len(self.reviewed["payloads"][target])], [16149, 16134])
        self.assertEqual(color.restore_material(self.reviewed["payloads"][target]), old["payloads"][target])
        for path, digest in ((color.PAC_PATH, color.PRESERVED_PAC_SHA256), (color.DIFFUSE_PATH, color.DIFFUSE_SHA256)):
            self.assertEqual(self.reviewed["payloads"][path], old["payloads"][path])
            self.assertEqual(steve.native.sha256(self.reviewed["payloads"][path]), digest)
        old_rows = {row["virtualPath"]: row for row in old["report"]["resources"]}
        new_rows = {row["virtualPath"]: row for row in self.reviewed["report"]["resources"]}
        self.assertEqual({path: row for path, row in new_rows.items() if path != target},
                         {path: row for path, row in old_rows.items() if path != target})
        self.assertEqual(self.reviewed["before"], old["before"])
        self.assertEqual(self.reviewed["after"]["meta/0.pathc"], old["after"]["meta/0.pathc"])
        self.assertEqual(self.reviewed["report"]["sourceIndexes"], old["report"]["sourceIndexes"])
        inputs = dict(old["report"]["candidateReports"])
        self.assertEqual(len(inputs), 8)
        inputs[str(helper.HEAD_BASECOLOR_REPORT.relative_to(steve.ROOT))] = HEAD_REPORT_SHA256
        self.assertEqual(self.reviewed["report"]["candidateReports"], inputs)
        self.assertEqual(len(inputs), 9)
        candidate, payloads, _ = color.load_candidate(helper.HEAD_BASECOLOR_REPORT)
        expected_row = copy.deepcopy(candidate["candidateResources"][0])
        expected_row["localFile"] = str((helper.HEAD_BASECOLOR_REPORT.parent / expected_row["localFile"]).relative_to(steve.ROOT))
        self.assertEqual(new_rows[target], expected_row)
        self.assertEqual(self.reviewed["payloads"][target], payloads[target])
        original, updated = packer.encoded_entries(old["package"]), packer.encoded_entries(self.reviewed["package"])
        self.assertEqual(set(original), set(updated))
        for path, (entry, raw) in updated.items():
            before_entry, before_raw = original[path]
            if path != target:
                self.assertEqual((raw, entry.flags, entry.orig_size),
                                 (before_raw, before_entry.flags, before_entry.orig_size), path)
        self.assertEqual(updated[target][0].flags, 50)
        self.assertEqual(updated[color.PAC_PATH][0].flags, 1)
        self.assertEqual(updated[color.DIFFUSE_PATH][0].flags, 0)
        self.assertEqual(sum(entry.path == color.DIFFUSE_PATH for entry, _ in updated.values()), 1)
        self.assertEqual(self.reviewed["probeVariant"], self.expected_variant)
        receipt = self.install()
        self.assertEqual(receipt["probeVariant"], self.expected_variant)
        self.assertEqual(receipt["planSha256"], self.reviewed["reportSha256"])
        self.restore()
        self.assert_original()
        self.assert_production_unchanged()

    def test_23_required_controls_and_replacement_declarations_are_inseparable(self):
        import prepare_steve_head_basecolor_overlay as packer
        plan, path, original = self.altered_plan()
        for change in (*self.control_reports, "resource", "replacement-list", "unknown-report"):
            report = copy.deepcopy(original)
            if change in self.control_reports:
                name = next(key for key in report["candidateReports"] if key.endswith(change))
                del report["candidateReports"][name]
            elif change == "resource":
                report["resources"] = [row for row in report["resources"] if row["virtualPath"] != self.extra_path]
            elif change == "replacement-list":
                report["replacementPaths"].remove(self.extra_path)
            else:
                report["candidateReports"]["build/unknown-report.json"] = "0" * 64
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change), self.assertRaises(ValueError):
                steve.load_plan(plan)
        self.assert_original()
        self.assert_production_unchanged()

    def test_26_body_requires_all_dependencies_and_excludes_other_modes_before_io(self):
        # Override body26 with the independent final head-basecolor admission.
        changes = [{name: None} for name in self.base_options()]
        changes.extend(({"app_path": self.test_root / "unused-app-report.json"},
                        {"head_mesh_control_path": helper.HEAD_MESH_CONTROL_REPORT},
                        {"head_basecolor_path": self.test_root / "unknown-report.json"}))
        for change in changes:
            options = {**self.base_options(), "head_basecolor_path": helper.HEAD_BASECOLOR_REPORT, **change}
            with self.subTest(change=change), mock.patch.object(helper.assembly, "load_candidate") as opened:
                with self.assertRaisesRegex(ValueError, "Head base-color control"):
                    helper.candidates(helper.DEFAULT_ASSEMBLY, helper.DEFAULT_APPEARANCE, **options)
                opened.assert_not_called()
        import prepare_steve_head_basecolor_overlay as packer
        with mock.patch.object(color, "load_candidate") as opened, mock.patch.object(steve.native, "file_hash") as hashed:
            with self.assertRaises(ValueError):
                packer.load_head(self.test_root / "unknown-report.json", {})
            opened.assert_not_called()
            hashed.assert_not_called()
        self.assert_production_unchanged()

    def test_27_body_exact_report_set_rejects_missing_or_mixed_modes_before_hash(self):
        import prepare_steve_head_basecolor_overlay as packer
        plan, path, original = self.altered_plan()
        # Removing head-basecolor alone leaves the valid eight-report baseline.
        # Inherited test23 proves its head bytes cannot accompany these reports.
        base_names = (*self.control_reports[:-1], "steve-assembly-report.json", "steve-appearance-report.json")
        for name in (*base_names, "steve-app-report.json", "steve-head-mesh-control-report.json", "unknown-report.json",
                     "duplicate-head-report"):
            report = copy.deepcopy(original)
            if name in base_names:
                key = next(key for key in report["candidateReports"] if key.endswith(name))
                del report["candidateReports"][key]
            else:
                extra = color.REPORT_NAME if name == "duplicate-head-report" else name
                report["candidateReports"]["build/unused/" + extra] = "0" * 64
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(name=name), mock.patch.object(steve.native, "file_hash") as hashed:
                with self.assertRaises(ValueError):
                    steve.load_plan(plan)
                hashed.assert_not_called()
        self.assert_original()
        self.assert_production_unchanged()

    def test_28_body_pins_prior_body_pac_and_pami_and_preserves_generic_duplicate_rejection(self):
        resources, reports, snapshot = self.body_candidates()
        for target in (color.MATERIAL_PATH, color.PAC_PATH, color.DIFFUSE_PATH):
            changed = copy.deepcopy(resources)
            changed[target]["payload"] += b"changed"
            changed[target]["row"]["sha256"] = steve.native.sha256(changed[target]["payload"])
            with self.subTest(target=target), mock.patch.object(color, "load_candidate") as opened:
                with self.assertRaisesRegex(ValueError, "fixed prior head PAMI, PAC and DDS"):
                    helper.apply_head_basecolor(changed, dict(reports), dict(snapshot), helper.HEAD_BASECOLOR_REPORT)
                opened.assert_not_called()
        for target, flag in ((color.MATERIAL_PATH, 0), (color.PAC_PATH, 50)):
            changed = copy.deepcopy(resources)
            changed[target]["row"]["archiveFlags"] = flag
            with self.subTest(target=target, flag=flag), mock.patch.object(color, "load_candidate") as opened:
                with self.assertRaises(ValueError):
                    helper.apply_head_basecolor(changed, dict(reports), dict(snapshot), helper.HEAD_BASECOLOR_REPORT)
                opened.assert_not_called()
        changed = copy.deepcopy(resources)
        changed[color.DIFFUSE_PATH]["row"]["kind"] = "skinnedMaterial"
        with mock.patch.object(color, "load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_basecolor(changed, dict(reports), dict(snapshot), helper.HEAD_BASECOLOR_REPORT)
            opened.assert_not_called()
        # Applying before the eighth body report, or applying a second time,
        # must fail at the predecessor contract before loading the candidate.
        earlier = dict(reports)
        del earlier[next(key for key in earlier if key.endswith("steve-body-native-material-report.json"))]
        with mock.patch.object(color, "load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_basecolor(copy.deepcopy(resources), earlier, dict(snapshot), helper.HEAD_BASECOLOR_REPORT)
            opened.assert_not_called()
        updated, after_reports, after_snapshot = copy.deepcopy(resources), dict(reports), dict(snapshot)
        helper.apply_head_basecolor(updated, after_reports, after_snapshot, helper.HEAD_BASECOLOR_REPORT)
        with mock.patch.object(color, "load_candidate") as opened:
            with self.assertRaises(ValueError):
                helper.apply_head_basecolor(updated, after_reports, after_snapshot, helper.HEAD_BASECOLOR_REPORT)
            opened.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Duplicate overlay resource"):
            helper.overlay.load_resources([helper.DEFAULT_ASSEMBLY, helper.HEAD_BASECOLOR_REPORT])
        self.assert_original()

    def test_29_body_payload_tamper_rejects_updated_inner_and_outer_hashes(self):
        import prepare_steve_head_basecolor_overlay as packer
        plan, path, original = self.altered_plan()
        old_key = next(key for key in original["candidateReports"] if key.endswith(color.REPORT_NAME))
        copied = self.test_root / "tampered-head-basecolor"
        shutil.copytree(helper.HEAD_BASECOLOR_REPORT.parent, copied)
        copied_report = copied / color.REPORT_NAME
        raw_report = copied_report.read_bytes()
        original_candidate = json.loads(raw_report)
        # All four provenance sources and the sole candidate payload are fixed.
        # Relabelling inner hashes and the plan's outer report digest cannot
        # admit a different PAC, DDS, native PAMI, source report or output PAMI.
        for relative in original_candidate["files"]:
            file = copied / relative
            raw = file.read_bytes()
            changed = raw[:-1] + bytes([raw[-1] ^ 1])
            file.write_bytes(changed)
            candidate = copy.deepcopy(original_candidate)
            digest = steve.native.sha256(changed)
            candidate["files"][relative] = digest
            for source in candidate["sources"].values():
                if source["localFile"] == relative:
                    source["sha256"] = digest
            for row in candidate["candidateResources"]:
                if row["localFile"] == relative:
                    row["sha256"] = digest
            copied_report.write_bytes(color.report_bytes(candidate))
            report = copy.deepcopy(original)
            del report["candidateReports"][old_key]
            report["candidateReports"][str(copied_report.relative_to(steve.ROOT))] = steve.native.file_hash(copied_report)
            path.write_bytes(packer.report_bytes(report))
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                steve.load_plan(plan)
            file.write_bytes(raw)
            copied_report.write_bytes(raw_report)
        path.write_bytes(packer.report_bytes(original))
        self.assert_original()
        self.assert_production_unchanged()

    def test_30_composition_outputs_reject_source_overlap_before_loading_or_mkdir(self):
        import prepare_steve_head_basecolor_overlay as packer
        options = {"baseline": self.baseline_plan, "head_report": helper.HEAD_BASECOLOR_REPORT,
                   "source": self.source, "deps": self.deps}
        cases = (
            ("canonical-child", {"output": packer.DEFAULT_OUTPUT / "unused-child"}),
            ("canonical-ancestor", {"output": packer.DEFAULT_OUTPUT.parent}),
            ("fixed-body-baseline", {"output": packer.DEFAULT_BASELINE}),
            ("fixed-body-child", {"output": packer.DEFAULT_BASELINE / "unused-child"}),
            ("body-ancestor", {"output": self.test_root / "body-inputs",
                               "baseline": self.test_root / "body-inputs/body-plan"}),
            ("head-source-child", {"output": helper.HEAD_BASECOLOR_REPORT.parent / "unused-child"}),
            ("cdmw-source-child", {"output": self.source / "unused-child"}),
            ("cdmw-source-ancestor", {"output": self.test_root / "source-inputs",
                                      "source": self.test_root / "source-inputs/cdmw"}),
            ("dependencies-child", {"output": self.deps / "unused-child"}),
        )
        for label, change in cases:
            with self.subTest(output=label), mock.patch.object(packer, "fixed_cdmw") as compiled, \
                    mock.patch.object(packer, "load_baseline") as loaded, mock.patch.object(Path, "mkdir") as made:
                with self.assertRaises(ValueError):
                    packer.prepare(**{**options, **change})
                compiled.assert_not_called()
                loaded.assert_not_called()
                made.assert_not_called()
        self.assert_original()
        self.assert_production_unchanged()

    def test_31_complete_writer_rejects_aligned_trailing_zero_even_after_checksum_updates(self):
        import prepare_steve_head_basecolor_overlay as packer
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
        for relative in (f"package/{original['directoryName']}/0.pamt",
                         f"package/{original['directoryName']}/0.paz", "metadata-after/0.papgt"):
            report["files"][relative] = steve.native.file_hash(plan / relative)
        # Ordinary checksum, length, alignment, payload and mount audits all
        # accept this self-consistent archive; complete writer bytes must not.
        report["packageAudit"] = helper.overlay.audit_package(package, report["resources"], self.reviewed["payloads"])
        report["mountAudit"] = helper.overlay.audit_mounts(before_papgt, after_papgt, original["directoryName"], pamt)
        self.assertTrue(report["packageAudit"]["payloadBoundariesAndChecksumsValid"])
        manifest.write_bytes(packer.report_bytes(report))
        with self.assertRaisesRegex(ValueError, "complete fixed writer reconstruction"):
            steve.load_plan(plan)
        self.assert_original()
        self.assert_production_unchanged()

    def test_32_snapshot_conflicts_and_canonical_manifest_fields_are_rejected(self):
        import prepare_steve_head_basecolor_overlay as packer
        absolute = (self.test_root / "snapshot/source.bin").resolve()
        snapshot = {}
        packer.merge_snapshot(snapshot, {absolute: b"first admitted bytes"})
        packer.merge_snapshot(snapshot, {absolute: b"first admitted bytes"})
        with self.assertRaisesRegex(ValueError, "changed between its admitted reads"):
            packer.merge_snapshot(snapshot, {absolute: b"raced different bytes"})
        self.assertEqual(snapshot, {absolute: b"first admitted bytes"})

        # Exercise the active-receipt branch with real resource-path validation
        # and synthetic bytes only, including the original backslash key form.
        game = self.test_root / "synthetic-production"
        receipt_path = self.test_root / "synthetic-state/active.json"
        directory = game / "0041"
        installed = {"0041/0.pamt", "0041/0.paz", "0041/" + transaction.MARKER}
        receipt = {"directoryName": "0041", "gameRoot": str(game), "installedFiles": dict.fromkeys(installed, "digest")}
        content = {receipt_path: json.dumps(receipt).encode("utf-8")}
        content.update({game / relative: relative.encode("ascii") for relative in installed})
        content.update({game / relative: relative.encode("ascii")
                        for relative in (*transaction.METADATA, "meta/0.papk", "meta/0.paver")})
        source_keys = ("0000\\0.pamt", "0033/0.pamt")
        source_files = {game / key.replace("\\", "/"): "digest-" + key for key in source_keys}
        with mock.patch.object(steve.native, "check_links") as checked, \
                mock.patch.object(Path, "resolve", lambda path, *args, **kwargs: path), \
                mock.patch.object(Path, "exists", lambda path: path in content or path == directory), \
                mock.patch.object(Path, "read_bytes", lambda path: content[path]), \
                mock.patch.object(Path, "iterdir", lambda path: iter(game / relative for relative in installed)):
            observed = production_snapshot(game, source_keys, receipt_path, lambda path: source_files[path])
            checked.assert_any_call(directory)
        self.assertEqual(observed["indexes"], {key: "digest-" + key for key in source_keys})
        self.assertEqual(observed["receiptBytes"], content[receipt_path])
        self.assertEqual(observed["installedFiles"], {key: content[game / key] for key in installed})
        self.assertEqual(observed["ownedDirectoryInventory"], tuple(sorted(Path(key).name for key in installed)))

        plan, manifest, original = self.altered_plan()
        for change in ("source-index-digest", "package-audit-bool", "unknown-field"):
            report = copy.deepcopy(original)
            if change == "source-index-digest":
                key = next(iter(report["sourceIndexes"]))
                digest = report["sourceIndexes"][key]
                report["sourceIndexes"][key] = ("0" if digest[0] != "0" else "1") + digest[1:]
            elif change == "package-audit-bool":
                report["packageAudit"]["allPayloadsDecodeByteIdentically"] = False
            else:
                report["unreviewedCompositionField"] = True
            manifest.write_bytes(packer.report_bytes(report))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "complete fixed-baseline reconstruction"):
                steve.load_plan(plan)
        self.assert_original()
        self.assert_production_unchanged()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=SteveHeadBasecolorOverlayChecks.plan)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    case = SteveHeadBasecolorOverlayChecks
    case.plan, case.rebuild = args.plan, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
