"""Audit fixed A/B packages and transactions in synthetic build-only game copies.

Real package bytes are decoded; EXE/source-index identities use explicit tiny
fixture sentinels. No production installation, receipt, saves or MC are read.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch

import check_asset_probe as old_checks
import install_steve_motion_probe as motion
import install_asset_probe as probe
import prepare_native_steve as native


class MotionChecks(old_checks.ProbeChecks):
    plan_loader = staticmethod(motion.load_plan)

    @classmethod
    def setUpClass(cls):
        # The batch already builds both plans in this process. Re-admit its
        # fixed loaded modules rather than calling the fresh-process loader.
        motion.motion.bootstrap_backend(cls.source, cls.deps)
        cls.reviewed = cls.plan_loader(cls.plan)
        cls.temporary = tempfile.TemporaryDirectory(dir=native.ROOT / "build", prefix="motion-check-")
        cls.root = Path(cls.temporary.name)
        cls.base = cls.root / "baseline"
        cls.base.mkdir()
        cls.fake_exe = b"Motion fixture executable; never launched."
        cls.sentinels = {}
        for relative, digest in cls.reviewed["report"]["sourceIndexes"].items():
            target = cls.base / relative.replace("\\", "/")
            target.parent.mkdir(parents=True, exist_ok=True)
            data = ("Immutable synthetic index " + relative).encode()
            target.write_bytes(data)
            cls.sentinels[target.relative_to(cls.base).as_posix()] = (data, digest)
        for relative, data in cls.reviewed["before"].items():
            target = cls.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (cls.base / "bin64").mkdir()
        (cls.base / "bin64/CrimsonDesert.exe").write_bytes(cls.fake_exe)
        cls.real_hash = native.file_hash

        def fixture_hash(path):
            path = Path(path).absolute()
            if path.is_relative_to(cls.root) and path.is_file():
                if path.name == "CrimsonDesert.exe" and path.read_bytes() == cls.fake_exe:
                    return native.EXE_SHA256
                for relative, (data, digest) in cls.sentinels.items():
                    if path.as_posix().endswith("/" + relative) and path.read_bytes() == data:
                        return digest
            return cls.real_hash(path)

        cls.hash_patch = patch.object(native, "file_hash", fixture_hash)
        cls.hash_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.hash_patch.stop()
        cls.temporary.cleanup()

    def install(self, **kwargs):
        return motion.install(self.plan, self.game, state_root=self.state,
                              save_roots=[self.save], running=kwargs.pop("running", lambda: False), **kwargs)

    def restore(self, **kwargs):
        return motion.restore(self.game, state_root=self.state,
                              running=kwargs.pop("running", lambda: False), **kwargs)

    def test_16_plan_provenance_matches_resource_set(self):
        plan = self.copy_plan()
        report_path = plan / "reports/overlay-report.json"
        original = json.loads(report_path.read_bytes())
        motion.load_plan(plan)  # Positive relocation control before negative cases.
        mutations = []
        for field, value in (("candidateReports", {}), ("directoryName", "0042"),
                             ("probeVariant", "unknown"), ("sourceIndexes", {})):
            changed = json.loads(json.dumps(original))
            changed[field] = value
            mutations.append(changed)
        changed = json.loads(json.dumps(original))
        changed["resources"][0]["archiveFlags"] ^= 1
        mutations.append(changed)
        for changed in mutations:
            report_path.write_bytes(probe.json_bytes(changed))
            with self.assertRaises(ValueError):
                motion.load_plan(plan)
        self.assert_original()

    def copy_plan(self):
        plan = self.test_root / "plan"
        shutil.copytree(self.plan, plan)
        report_path = plan / "reports/overlay-report.json"
        report = json.loads(report_path.read_bytes())
        key = next(key for key in report["candidateReports"] if key.endswith("/" + motion.motion.MOTION_REPORT_NAME))
        digest = report["candidateReports"].pop(key)
        report["candidateReports"][(plan / motion.motion.MOTION_REPORT_FILE).relative_to(native.ROOT).as_posix()] = digest
        report_path.write_bytes(motion.motion.report_bytes(report))
        return plan

    def test_17_active_receipt_rejects_second_kind_and_plan(self):
        receipt = self.install()
        with self.assertRaisesRegex(ValueError, "active probe receipt"):
            self.install()
        with self.assertRaises(ValueError):
            probe.restore(self.game, state_root=self.state, running=lambda: False)
        self.assertEqual(json.loads((self.state / probe.RECEIPT).read_bytes())["id"], receipt["id"])
        self.restore()
        self.assert_original()

    def test_18_foreign_metadata_during_install_recovery_is_preserved(self):
        def fail(phase):
            if phase == "published:meta/0.pathc":
                (self.game / "meta/0.pathc").write_bytes(b"Foreign concurrent edit")
                raise RuntimeError("injected external edit")
        with self.assertRaisesRegex(RuntimeError, "recovery stopped"):
            self.install(_fault=fail)
        self.assertEqual((self.game / "meta/0.pathc").read_bytes(), b"Foreign concurrent edit")
        self.assertTrue((self.state / probe.RECEIPT).exists())

    def test_19_later_save_survives_restore_and_next_install(self):
        self.install()
        later = b"Newest progress after normal exit"
        (self.save / "slot0.save").write_bytes(later)
        (self.save / "slot1.save").write_bytes(b"New slot")
        self.restore()
        second = self.install()
        self.assertEqual((Path(second["backupRoot"]) / "saves/0/slot0.save").read_bytes(), later)
        self.restore()
        self.assertEqual((self.save / "slot0.save").read_bytes(), later)
        self.assertEqual((self.save / "slot1.save").read_bytes(), b"New slot")
        self.assert_original()

    def test_20_source_drift_during_backup_rejected_before_game_publication(self):
        plan = self.copy_plan()
        motion.load_plan(plan)
        package = plan / "package/0041/0.paz"
        original = probe.backup_saves
        def drift(roots, backup):
            result = original(roots, backup)
            package.write_bytes(package.read_bytes() + b"changed after admission")
            return result
        with patch.object(probe, "backup_saves", drift):
            with self.assertRaisesRegex(ValueError, "source changed"):
                motion.install(plan, self.game, state_root=self.state, save_roots=[self.save], running=lambda: False)
        self.assert_original()

    def test_21_custom_state_cannot_hide_production_receipt(self):
        outside_build = native.ROOT / "fake-outside-build-never-created"
        with patch.object(probe, "require_closed", side_effect=AssertionError("must reject before game read")):
            with self.assertRaises(ValueError):
                probe.install(self.plan, outside_build, state_root=self.state,
                              probe_kind=motion.KIND, running=lambda: False)
            with self.assertRaises(ValueError):
                probe.restore(outside_build, state_root=self.state, probe_kind=motion.KIND, running=lambda: False)
        self.assertFalse(outside_build.exists())

    def test_22_foreign_edit_during_restore_recovery_is_preserved(self):
        self.install()
        def fail(phase):
            if phase == "restored:meta/0.papgt":
                (self.game / "meta/0.papgt").write_bytes(b"Foreign restore edit")
                raise RuntimeError("injected restore foreign edit")
        with self.assertRaisesRegex(RuntimeError, "recovery stopped"):
            self.restore(_fault=fail)
        self.assertEqual((self.game / "meta/0.papgt").read_bytes(), b"Foreign restore edit")
        self.assertTrue((self.state / probe.RECEIPT).exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    MotionChecks.plan = args.plan
    output = native.output_directory(args.report)
    if output.exists():
        raise ValueError("Check report already exists")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MotionChecks))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schemaVersion": 1, "testsRun": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "successful": result.wasSuccessful(),
        "fixture": "synthetic EXE/source-index sentinel identities; real package bytes",
        "productionGameAccessed": False, "gameLaunched": False, "MCWalkingApplied": False}, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
