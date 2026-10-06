"""Check local overlay exports and reject corrupted payloads/registry/mount edits.

Run after prepare_asset_overlay.py. No game files, saves, inventories or native
functions are changed. --verify-game also reads the installed metadata/indexes.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
import unittest

import prepare_asset_overlay as overlay
import prepare_native_steve as native


class AssetOverlayChecks(unittest.TestCase):
    output = native.ROOT / "build/native-asset-overlay"
    source = native.ROOT / "build/cdmw-fixed-source"
    deps = native.ROOT / "build/cdmw-deps"
    game = None

    @classmethod
    def setUpClass(cls) -> None:
        native.load_cdmw(cls.source, cls.deps)
        cls.report = json.loads((cls.output / "reports/overlay-report.json").read_text(encoding="utf-8"))
        cls.resources = cls.report["resources"]
        cls.payloads = {row["virtualPath"]: (native.ROOT / row["localFile"]).read_bytes() for row in cls.resources}
        cls.papgt_before = (cls.output / "metadata-before/0.papgt").read_bytes()
        cls.papgt_after = (cls.output / "metadata-after/0.papgt").read_bytes()
        cls.pathc_before = (cls.output / "metadata-before/0.pathc").read_bytes()
        cls.pathc_after = (cls.output / "metadata-after/0.pathc").read_bytes()
        cls.package = cls.output / "package" / cls.report["directoryName"]
        cls.pamt = (cls.package / "0.pamt").read_bytes()
        cls.textures = {row["virtualPath"]: cls.payloads[row["virtualPath"]]
                        for row in cls.resources if row["kind"] == "texture"}

    def test_01_actual_candidate_and_package_fingerprints(self) -> None:
        self.assertEqual(self.report["supportedExeSha256"], native.EXE_SHA256)
        self.assertEqual(self.report["cdmw"]["commit"], native.CDMW_COMMIT)
        for relative, wanted in self.report["files"].items():
            self.assertEqual(native.file_hash(self.output / relative), wanted, relative)
        for row in self.resources:
            self.assertEqual(native.sha256(self.payloads[row["virtualPath"]]), row["sha256"])
        for relative, wanted in self.report["candidateReports"].items():
            self.assertEqual(native.file_hash(native.ROOT / relative), wanted)

    def test_02_decode_all_real_candidate_payloads(self) -> None:
        audit = overlay.audit_package(self.package, self.resources, self.payloads)
        self.assertEqual(audit, self.report["packageAudit"])
        self.assertTrue(audit["allPayloadsDecodeByteIdentically"])

    def test_03_mount_order_and_language_flags_preserved(self) -> None:
        audit = overlay.audit_mounts(self.papgt_before, self.papgt_after,
                                     self.report["directoryName"], self.pamt)
        self.assertEqual(audit, self.report["mountAudit"])
        self.assertEqual(audit["afterDirectoryCount"], audit["beforeDirectoryCount"] + 1)

    def test_04_registry_has_exact_new_dds_shapes_and_mips(self) -> None:
        audit = overlay.audit_registry(self.pathc_before, self.pathc_after, self.textures)
        self.assertEqual(audit, self.report["registryAudit"])
        self.assertTrue(audit["originalRowsHeadersCollisionsUnchanged"])

    def test_05_mount_tampering_rejected_even_with_valid_checksum(self) -> None:
        from cdmw.core.papgt_format import parse_papgt, serialize_papgt
        from dataclasses import replace
        rows = list(parse_papgt(self.papgt_after))
        rows[1] = replace(rows[1], flags=rows[1].flags ^ 0x100)
        changed = serialize_papgt(rows, header=self.papgt_after[:12])
        with self.assertRaisesRegex(ValueError, "original records"):
            overlay.audit_mounts(self.papgt_before, changed, self.report["directoryName"], self.pamt)
        with self.assertRaises(ValueError):
            overlay.audit_mounts(self.papgt_before, self.papgt_after, rows[1].name, self.pamt)

    def test_06_registry_tampering_rejected_even_with_valid_shape(self) -> None:
        from cdmw.core.pathc_format import parse_pathc, encode_pathc
        from dataclasses import replace
        table = parse_pathc(self.pathc_after)
        rows = list(table.entries)
        rows[0] = replace(rows[0], block_infos=bytes(16))
        altered = encode_pathc(replace(table, entries=tuple(rows)))
        if altered == self.pathc_after:
            rows[0] = replace(rows[0], block_infos=b"\xff" * 16)
            altered = encode_pathc(replace(table, entries=tuple(rows)))
        with self.assertRaises(ValueError):
            overlay.audit_registry(self.pathc_before, altered, self.textures)
        with self.assertRaises(ValueError):
            overlay.audit_registry(self.pathc_before, self.pathc_after, {})

    def test_07_corrupt_archive_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=native.ROOT / "build", prefix="overlay-check-") as temporary:
            root = Path(temporary)
            self.assertTrue(root.resolve().is_relative_to(native.ROOT / "build"))
            (root / "0.pamt").write_bytes(self.pamt)
            payload = bytearray((self.package / "0.paz").read_bytes())
            payload[0] ^= 0x20
            (root / "0.paz").write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "PAZ checksum"):
                overlay.audit_package(root, self.resources, self.payloads)

    def test_08_candidate_path_duplicate_and_fingerprint_guards(self) -> None:
        reports = [native.ROOT / path for path in self.report["candidateReports"]]
        _rows, payloads, _inputs = overlay.load_resources(reports)
        self.assertEqual(set(payloads), set(self.payloads))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            overlay.load_resources(reports + reports[:1])
        for value in ("../escape.pam", "/absolute/file.pam", "C:/file.pam", "a\\b.pam", "a/./b.pam",
                      "a/nul\x00.pam", "a/new\nline.pam"):
            with self.assertRaises(ValueError):
                overlay.virtual_path(value)
        with self.assertRaises(ValueError):
            native.output_directory(native.ROOT / "downloads/overlay")

    def test_09_existing_symlink_output_rejected_before_first_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=native.ROOT / "build", prefix="overlay-links-") as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            alias = root / "alias"
            try:
                alias.symlink_to(target, target_is_directory=True)
            except OSError:
                # Windows allows a junction without Developer Mode.
                import subprocess
                quote = lambda value: "'" + str(value).replace("'", "''") + "'"
                subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"New-Item -ItemType Junction -Path {quote(alias)} -Target {quote(target)} | Out-Null"],
                               check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                overlay.publish(root, {"first/out.txt": b"first", "alias/out.txt": b"second"})
            self.assertFalse((root / "first").exists())
            alias.unlink() if alias.is_symlink() else alias.rmdir()

    def test_10_integration_status_does_not_claim_game_behavior(self) -> None:
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertTrue(self.report["limitations"])

    def test_11_truncated_extra_and_unknown_dds_payloads_rejected(self) -> None:
        for data in self.textures.values():
            overlay.validate_candidate_dds(data)
            for bad in (data[:128], data[:-1], data + b"\x00", data[:84] + b"DX10" + data[88:]):
                with self.assertRaises(ValueError):
                    overlay.validate_candidate_dds(bad)

    def test_12_report_link_rejected_before_package_publication(self) -> None:
        with tempfile.TemporaryDirectory(dir=native.ROOT / "build", prefix="overlay-report-") as temporary:
            root = Path(temporary)
            (root / "reports/overlay-report.json").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "existing directory"):
                overlay.preflight_outputs(root, ["package/0041/0.paz", "reports/overlay-report.json"])
            self.assertFalse((root / "package").exists())

    def test_13_installed_metadata_and_indexes_remain_unchanged(self) -> None:
        if self.game is None:
            self.skipTest("Pass --verify-game for an additional read-only installed-snapshot check")
        self.assertEqual(native.file_hash(self.game / "bin64/CrimsonDesert.exe"), native.EXE_SHA256)
        self.assertEqual((self.game / "meta/0.papgt").read_bytes(), self.papgt_before)
        self.assertEqual((self.game / "meta/0.pathc").read_bytes(), self.pathc_before)
        self.assertFalse((self.game / self.report["directoryName"]).exists())
        for relative, wanted in self.report["sourceIndexes"].items():
            self.assertEqual(native.file_hash(self.game / relative), wanted)
        for name in self.report["absentOptionalMountedDirectories"]:
            self.assertFalse((self.game / name / "0.pamt").exists())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=AssetOverlayChecks.output)
    parser.add_argument("--cdmw-source", type=Path, default=AssetOverlayChecks.source)
    parser.add_argument("--deps", type=Path, default=AssetOverlayChecks.deps)
    parser.add_argument("--verify-game", action="store_true")
    parser.add_argument("--game-root", type=Path)
    args = parser.parse_args()
    AssetOverlayChecks.output = native.output_directory(args.output)
    AssetOverlayChecks.source, AssetOverlayChecks.deps = args.cdmw_source, args.deps
    if args.verify_game:
        AssetOverlayChecks.game = args.game_root or Path(json.loads(
            (native.ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AssetOverlayChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
