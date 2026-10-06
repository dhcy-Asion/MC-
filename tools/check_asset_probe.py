"""Exercise probe installation/restoration only in temporary fake game copies.

Uses the actual reviewed asset package and native archive indexes; the production
installation, personal saves and project runtime receipts are never written.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import install_asset_probe as probe
import prepare_native_steve as native


class ProbeChecks(unittest.TestCase):
    plan = native.ROOT / "build/native-asset-overlay"
    source = native.ROOT / "build/cdmw-fixed-source"
    deps = native.ROOT / "build/cdmw-deps"

    @classmethod
    def setUpClass(cls):
        native.load_cdmw(cls.source, cls.deps)
        cls.reviewed = probe.load_plan(cls.plan)
        cls.temporary = tempfile.TemporaryDirectory(dir=native.ROOT / "build", prefix="probe-check-")
        cls.root = Path(cls.temporary.name)
        cls.base = cls.root / "baseline"
        cls.base.mkdir()
        cls.real_game = Path(json.loads((native.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
        cls.observed = {path: native.file_hash(cls.real_game / path)
                        for path in cls.reviewed["report"]["sourceIndexes"]}
        for relative, digest in cls.observed.items():
            target = cls.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cls.real_game / relative, target)
            if native.file_hash(target) != digest:
                raise ValueError("Fixture index differs from its original snapshot")
        for path, data in cls.reviewed["before"].items():
            target = cls.base / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for path in ("meta/0.papk", "meta/0.paver"):
            source = cls.real_game / path
            if source.exists():
                shutil.copyfile(source, cls.base / path)
        (cls.base / "bin64").mkdir()
        cls.fake_exe = b"Probe fixture executable; never launched."
        (cls.base / "bin64/CrimsonDesert.exe").write_bytes(cls.fake_exe)
        cls.real_hash = native.file_hash
        def fixture_hash(path):
            path = Path(path)
            if (path.name == "CrimsonDesert.exe" and path.resolve().is_relative_to(cls.root)
                    and path.read_bytes() == cls.fake_exe):
                return native.EXE_SHA256
            return cls.real_hash(path)
        # A fake executable is permitted only in owned test directories. The
        # production hash constant and installer code remain unchanged.
        cls.hash_patch = patch.object(native, "file_hash", fixture_hash)
        cls.hash_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.hash_patch.stop()
        for path, digest in cls.observed.items():
            if native.file_hash(cls.real_game / path) != digest:
                raise AssertionError("Production index changed during isolated tests")
        for path, data in cls.reviewed["before"].items():
            if (cls.real_game / path).read_bytes() != data:
                raise AssertionError("Production metadata changed during isolated tests")
        cls.temporary.cleanup()

    def setUp(self):
        self.test_root = self.root / self._testMethodName
        self.game = self.test_root / "game"
        self.state = self.test_root / "state"
        self.save = self.test_root / "saves"
        self.save.mkdir(parents=True)
        (self.save / "slot0.save").write_bytes(b"Preserve this original save snapshot.")
        for source in self.base.rglob("*"):
            target = self.game / source.relative_to(self.base)
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.suffix == ".pamt":
                    # Index files are immutable in the installer. Hard-link
                    # fixture indexes only; metadata and saves use own copies.
                    os.link(source, target)
                else:
                    shutil.copyfile(source, target)
        self.original = {path: (self.game / path).read_bytes() for path in probe.METADATA}

    def install(self, **kwargs):
        return probe.install(self.plan, self.game, state_root=self.state,
                             save_roots=[self.save], running=kwargs.pop("running", lambda: False), **kwargs)

    def restore(self, **kwargs):
        return probe.restore(self.game, state_root=self.state,
                             running=kwargs.pop("running", lambda: False), **kwargs)

    def assert_original(self):
        for path, data in self.original.items():
            self.assertEqual((self.game / path).read_bytes(), data)
        self.assertFalse((self.game / self.reviewed["name"]).exists())
        self.assertFalse((self.state / probe.RECEIPT).exists())
        self.assertEqual(probe.unchanged_game_files(self.game), probe.unchanged_game_files(self.base))

    def test_01_real_package_install_decode_and_restore_preserves_later_saves(self):
        result = self.install()
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["probeVariant"], self.reviewed["probeVariant"])
        self.assertEqual(result["candidateReport"], self.reviewed["candidateReport"])
        self.assertEqual(result["candidateReportSha256"], native.file_hash(Path(result["candidateReport"])))
        probe.verify_owned_directory(self.game, result)
        backup = Path(result["backupRoot"])
        self.assertEqual((backup / "saves/0/slot0.save").read_bytes(), (self.save / "slot0.save").read_bytes())
        (self.save / "slot0.save").write_bytes(b"Later gameplay progress must survive removal.")
        self.restore()
        self.assert_original()
        self.assertEqual((self.save / "slot0.save").read_bytes(), b"Later gameplay progress must survive removal.")

    def test_02_install_faults_after_package_and_each_metadata_publish_roll_back(self):
        for phase in ("package:0.pamt", "package:0.paz", "package_verified",
                      "published:meta/0.pathc", "published:meta/0.papgt"):
            def fail(actual):
                if actual == phase:
                    raise RuntimeError("Injected install failure")
            with self.assertRaisesRegex(RuntimeError, "Injected install failure"):
                self.install(_fault=fail)
            self.assert_original()

    def test_03_existing_foreign_directory_is_preserved(self):
        directory = self.game / self.reviewed["name"]
        directory.mkdir(); (directory / "foreign.txt").write_bytes(b"Not our mod")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.install()
        self.assertEqual((directory / "foreign.txt").read_bytes(), b"Not our mod")

    def test_04_game_process_and_wrong_exe_refused_before_backup(self):
        with self.assertRaisesRegex(ValueError, "Close Crimson Desert"):
            self.install(running=lambda: True)
        (self.game / "bin64/CrimsonDesert.exe").write_bytes(b"Unknown build")
        with self.assertRaisesRegex(ValueError, "EXE SHA"):
            self.install()
        self.assertFalse(self.state.exists())

    def test_05_before_metadata_and_source_index_changes_refused(self):
        (self.game / "meta/0.pathc").write_bytes(b"Other mod")
        with self.assertRaisesRegex(ValueError, "metadata changed"):
            self.install()
        (self.game / "meta/0.pathc").write_bytes(self.original["meta/0.pathc"])
        index = next(iter(self.reviewed["report"]["sourceIndexes"]))
        # Replace instead of editing an immutable fixture hard link.
        probe.atomic_write(self.game / index, b"Changed archive", "test")
        with self.assertRaisesRegex(ValueError, "source index changed"):
            self.install()

    def test_06_restore_rejects_metadata_or_payload_edits_without_overwriting(self):
        result = self.install()
        path = self.game / "meta/0.pathc"
        before = path.read_bytes(); path.write_bytes(b"Other mod changed this")
        with self.assertRaisesRegex(ValueError, "edited by another"):
            self.restore()
        self.assertEqual(path.read_bytes(), b"Other mod changed this")
        path.write_bytes(before)
        payload = self.game / self.reviewed["name"] / "0.paz"
        data = payload.read_bytes(); payload.write_bytes(data + b"Other mod")
        with self.assertRaisesRegex(ValueError, "edited externally"):
            self.restore()
        payload.write_bytes(data)
        self.restore(); self.assert_original()

    def test_07_restore_faults_roll_back_to_installed_state_and_can_retry(self):
        self.install()
        for phase in ("restored:meta/0.papgt", "restored:meta/0.pathc", "removed:0.paz"):
            def fail(actual):
                if actual == phase:
                    raise RuntimeError("Injected restore failure")
            with self.assertRaisesRegex(RuntimeError, "Injected restore failure"):
                self.restore(_fault=fail)
            result = json.loads((self.state / probe.RECEIPT).read_bytes())
            self.assertEqual(result["status"], "installed")
            probe.verify_owned_directory(self.game, result)
            for path, data in self.reviewed["after"].items():
                self.assertEqual((self.game / path).read_bytes(), data)
        self.restore(); self.assert_original()

    def test_08_game_start_during_install_preserves_recovery_without_writes(self):
        live = [False]
        def start(phase):
            if phase == "published:meta/0.pathc":
                live[0] = True
        with self.assertRaisesRegex(RuntimeError, "recovery stopped"):
            self.install(running=lambda: live[0], _fault=start)
        self.assertEqual((self.game / "meta/0.pathc").read_bytes(), self.reviewed["after"]["meta/0.pathc"])
        self.assertEqual((self.game / "meta/0.papgt").read_bytes(), self.original["meta/0.papgt"])
        self.assertEqual(json.loads((self.state / probe.RECEIPT).read_bytes())["status"], "installing")
        self.restore(); self.assert_original()

    def test_09_namespace_changes_during_save_backup_never_remove_foreign_directory(self):
        original = probe.backup_saves
        def concurrent(roots, backup):
            value = original(roots, backup)
            (self.game / self.reviewed["name"]).mkdir()
            return value
        with patch.object(probe, "backup_saves", concurrent):
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                self.install()
        self.assertTrue((self.game / self.reviewed["name"]).is_dir())

    def test_10_save_read_failures_do_not_silently_skip_backups(self):
        def denied(*args, **kwargs):
            kwargs["onerror"](PermissionError("Unreadable save subdirectory"))
            return iter(())
        with patch.object(probe.os, "walk", denied):
            with self.assertRaisesRegex(PermissionError, "Unreadable"):
                probe.tree_files(self.save)

    def test_11_receipt_history_rename_failure_does_not_block_retry(self):
        self.install()
        original = Path.rename
        def fail_active(path, destination):
            if path == self.state / probe.RECEIPT:
                raise OSError("Injected receipt archive failure")
            return original(path, destination)
        with patch.object(Path, "rename", fail_active):
            with self.assertRaisesRegex(OSError, "Injected receipt"):
                self.restore()
        self.assertEqual(json.loads((self.state / probe.RECEIPT).read_bytes())["status"], "installed")
        self.restore(); self.assert_original()

    def test_12_completed_receipt_after_hard_stop_finishes_archival(self):
        result = self.install()
        self.restore()
        history = self.state / "runtime/asset-probe-history" / (result["id"] + ".json")
        # Emulate a hard stop after terminal active state was written but before rename.
        history.rename(self.state / probe.RECEIPT)
        self.restore(); self.assert_original()

    def test_13_save_links_are_rejected(self):
        alias = self.save / "unsafe"
        try:
            alias.symlink_to(self.base, target_is_directory=True)
        except OSError:
            import subprocess
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"New-Item -ItemType Junction -Path {quote(alias)} -Target {quote(self.base)} | Out-Null"],
                           check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                self.install()
            self.assertEqual((self.game / "meta/0.papgt").read_bytes(), self.original["meta/0.papgt"])
        finally:
            alias.unlink() if alias.is_symlink() else alias.rmdir()

    def test_14_interruption_after_receipt_rename_keeps_completed_removal(self):
        self.install()
        original = Path.rename
        def commit_then_interrupt(path, destination):
            result = original(path, destination)
            if path == self.state / probe.RECEIPT:
                raise KeyboardInterrupt("Interrupted after a committed receipt rename")
            return result
        with patch.object(Path, "rename", commit_then_interrupt):
            self.restore()
        self.assert_original()

    def test_15_operation_lock_rejects_concurrency_and_releases(self):
        with probe.state_lock(self.state):
            with self.assertRaisesRegex(ValueError, "Another asset probe operation"):
                with probe.state_lock(self.state):
                    self.fail("Concurrent probe lock was acquired")
        with probe.state_lock(self.state):
            pass
        self.assert_original()

    def test_16_plan_must_name_exactly_one_report_and_match_its_resources(self):
        plan = self.test_root / "plan"
        shutil.copytree(self.plan, plan)
        report_path = plan / "reports/overlay-report.json"
        original = json.loads(report_path.read_bytes())
        changed = dict(original)
        changed["candidateReports"] = {}
        report_path.write_bytes(probe.json_bytes(changed))
        with self.assertRaisesRegex(ValueError, "one exact candidate"):
            probe.load_plan(plan)
        changed = json.loads(json.dumps(original))
        # Even a same-content file at an unrelated location cannot be relabelled
        # as the report's input. This fails before any game publication.
        resource = changed["resources"][0]
        relocated = self.test_root / "relocated-resource"
        shutil.copyfile(native.ROOT / resource["localFile"], relocated)
        resource["localFile"] = str(relocated.relative_to(native.ROOT))
        report_path.write_bytes(probe.json_bytes(changed))
        with self.assertRaisesRegex(ValueError, "verified candidate report"):
            probe.load_plan(plan)
        self.assert_original()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ProbeChecks.plan)
    parser.add_argument("--cdmw-source", type=Path, default=ProbeChecks.source)
    parser.add_argument("--deps", type=Path, default=ProbeChecks.deps)
    args = parser.parse_args()
    ProbeChecks.plan, ProbeChecks.source, ProbeChecks.deps = args.plan, args.cdmw_source, args.deps
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProbeChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
