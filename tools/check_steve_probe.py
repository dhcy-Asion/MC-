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

from check_asset_probe import ProbeChecks
import install_asset_probe as transaction
import install_steve_probe as steve


class SteveProbeChecks(ProbeChecks):
    plan = steve.steve.DEFAULT_OUTPUT
    plan_loader = staticmethod(steve.load_plan)
    rebuild = False

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
        # Override the oak-specific admission test: Steve requires two reports.
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
        self.assertEqual(len(steve.load_plan(plan)["payloads"]), 11)

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

    def test_20_exact_package_shadow_and_ten_new_resources(self):
        from cdmw.core.archive_format import parse_archive_pamt
        target = steve.steve.appearance.TARGET_PATH
        entries = parse_archive_pamt(self.reviewed["package"] / "0.pamt")
        self.assertEqual(len(entries), 11)
        self.assertEqual([e.path for e in entries if not Path(e.path).name.startswith("crimsonmc_")], [target])
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
        result = subprocess.run([sys.executable, "-B", str(steve.ROOT / "tools/prepare_steve_probe_overlay.py"), "--output", str(output)],
                                cwd=steve.ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in (*self.reviewed["report"]["files"], "reports/overlay-report.json"):
            self.assertEqual((output / relative).read_bytes(), (self.plan / relative).read_bytes())
        self.assertFalse((steve.ROOT / transaction.RECEIPT).exists())
        self.assert_original()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=SteveProbeChecks.plan)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    SteveProbeChecks.plan, SteveProbeChecks.rebuild = args.plan, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SteveProbeChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
