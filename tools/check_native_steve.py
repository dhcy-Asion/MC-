"""Verify real local native templates, PAC skin/LOD round trips and output guards.

Run `py -3.12 -B tools/prepare_native_steve.py`, then this script. Tests consume
only ignored local exports; no process, game function, save or archive is changed.
--rebuild adds a fresh, read-only game-archive preparation and compares every byte.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import prepare_native_steve as native


class NativeSteveChecks(unittest.TestCase):
    output = native.ROOT / "build" / "native-steve"
    source = native.ROOT / "build" / "cdmw-fixed-source"
    deps = native.ROOT / "build" / "cdmw-deps"
    steve = native.ROOT / "build" / "steve-1.21.1"
    rebuild = False

    @classmethod
    def setUpClass(cls) -> None:
        native.load_cdmw(cls.source, cls.deps)
        from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
        from cdmw.modding.skeleton_parser import parse_pab
        cls.report = json.loads((cls.output / "native-steve-report.json").read_text(encoding="utf-8"))
        cls.body_data = (cls.output / "template" / native.BODY).read_bytes()
        cls.rig_data = (cls.output / "template" / native.SKELETON).read_bytes()
        cls.candidate = (cls.output / "steve-rig-candidate.pac").read_bytes()
        cls.body = parse_pac(cls.body_data, native.BODY)
        cls.rig = parse_pab(cls.rig_data, native.SKELETON)
        cls.palette = resolve_pac_bone_palette(cls.body_data, cls.rig)
        cls.mesh = parse_pac(cls.candidate, native.BODY)

    def test_01_fixed_source_and_real_template_provenance(self) -> None:
        self.assertEqual(self.report["cdmw"]["commit"], native.CDMW_COMMIT)
        self.assertEqual(native.source_fingerprint(self.source), native.CDMW_SOURCE_SHA256)
        for path, expected in native.TEMPLATE_HASHES.items():
            self.assertEqual(native.file_hash(self.output / "template" / path), expected)
        for path, expected in self.report["files"].items():
            self.assertEqual(native.file_hash(self.output / path), expected)

    def test_02_real_rig_complete_weighted_palette(self) -> None:
        audit = native.validate_rig(self.rig, self.body, self.palette)
        self.assertEqual(audit["skeletonBones"], 447)
        self.assertEqual(audit["paletteBones"], 189)
        self.assertEqual(audit["weightedVertices"], 13162)
        self.assertEqual(audit["drawDescriptors"], 3)

    def test_03_unmodified_template_rebuild_is_byte_identical(self) -> None:
        from cdmw.modding.mesh_importer import rebuild_mesh_with_report
        result = rebuild_mesh_with_report(self.body, self.body_data, original_mesh=self.body)
        self.assertEqual(result.data, self.body_data)
        self.assertTrue(result.report.byte_identical)

    def test_04_candidate_has_classic_parts_and_rigid_native_weights(self) -> None:
        self.assertEqual((self.mesh.total_vertices, self.mesh.total_faces), (288, 144))
        ranges = self.report["candidate"]["partRanges"]
        self.assertEqual({r["part"] for r in ranges}, set(native.RIG_CANDIDATE) | set(native.OUTER_PARTS))
        self.assertEqual(sum(r["vertexCount"] for r in ranges), 288)
        parts = {0: self.mesh.submeshes[0], 2: self.mesh.submeshes[1]}
        for r in ranges:
            part = parts[r["nativeDrawSlot"]]
            start, count = r["firstVertex"], r["vertexCount"]
            self.assertEqual(part.bone_indices[start:start + count], [(r["paletteSlot"],)] * count)
            self.assertEqual(part.bone_weights[start:start + count], [(1.0,)] * count)

    def test_05_candidate_preserves_palette_and_runtime_metadata(self) -> None:
        from cdmw.modding.mesh_parser import resolve_pac_bone_palette
        self.assertEqual(resolve_pac_bone_palette(self.candidate, self.rig), self.palette)
        descriptors, lods = native.validate_runtime_descriptors(self.body_data, self.candidate, self.body)
        self.assertEqual(len(descriptors), 3)
        self.assertEqual(lods, 4)
        self.assertEqual(descriptors[1].vertex_counts, [0] * 4)
        self.assertEqual(descriptors[1].index_counts, [0] * 4)

    def test_06_all_four_lods_contain_complete_geometry_and_weights(self) -> None:
        from cdmw.modding.mesh_parser import _parse_par_sections, _parse_pac_geometry_section
        descriptors, lods = native.validate_runtime_descriptors(self.body_data, self.candidate, self.body)
        checked = []
        for section in _parse_par_sections(self.candidate):
            if 1 <= section["index"] <= lods:
                mesh = _parse_pac_geometry_section(self.candidate, native.BODY, descriptors, section, lods - section["index"])
                self.assertEqual((mesh.total_vertices, mesh.total_faces), (288, 144))
                self.assertEqual([(p.faces, p.vertices, p.uvs, p.bone_indices, p.bone_weights) for p in mesh.submeshes],
                                 [(p.faces, p.vertices, p.uvs, p.bone_indices, p.bone_weights) for p in self.mesh.submeshes])
                checked.append(lods - section["index"])
        self.assertEqual(sorted(checked), [0, 1, 2, 3])

    def test_07_authored_geometry_uv_and_skin_round_trip(self) -> None:
        mapping = native.rig_candidates(self.rig, self.palette)
        parts = native.steve_geometry(self.steve)
        rebuilt, report = native.make_candidate(self.body, self.body_data, parts, mapping)
        self.assertEqual(rebuilt, self.candidate)
        self.assertTrue(report["geometryRoundTrip"] and report["uvRoundTrip"] and report["skinRoundTrip"])

    def test_08_out_of_palette_weight_is_rejected(self) -> None:
        damaged = copy.deepcopy(self.mesh)
        damaged.submeshes[0].bone_indices[0] = (len(self.palette),)
        with self.assertRaisesRegex(ValueError, "exceeds the exact PAB palette"):
            native.validate_rig(self.rig, damaged, self.palette)

    def test_09_opaque_runtime_metadata_change_is_rejected(self) -> None:
        from cdmw.modding.mesh_parser import _parse_par_sections
        data = bytearray(self.candidate)
        metadata = _parse_par_sections(data)[0]
        data[metadata["offset"] + metadata["size"] - 1] ^= 1
        with self.assertRaisesRegex(ValueError, "unreviewed runtime"):
            native.validate_runtime_descriptors(self.body_data, bytes(data), self.body)

    def test_10_incorrect_lod_boundary_is_rejected(self) -> None:
        data = bytearray(self.candidate)
        data[0x50 + 5] ^= 1
        with self.assertRaisesRegex(ValueError, "mirrored LOD offset"):
            native.validate_runtime_descriptors(self.body_data, bytes(data), self.body)

    def test_11_native_game_integration_is_not_claimed(self) -> None:
        self.assertTrue(self.report["templateNoEditRebuildByteIdentical"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertTrue(all(row["motionVerified"] is False for row in self.report["rigMappingCandidates"].values()))

    def test_12_public_output_and_linked_build_ancestor_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ignored build"):
            native.output_directory(native.ROOT / "docs" / "native-steve")
        linked = native.ROOT / "build"
        with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda p: p == linked):
            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                native.output_directory(linked / "native-steve")

    def test_13_linked_report_is_rejected_before_any_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="native-steve-guard-", dir=native.ROOT / "build") as temp:
            output = Path(temp)
            linked = output / "native-steve-report.json"
            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda p: p == linked):
                with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                    native.publish_files(output, {"must-not-be-written.pac": b"candidate"}, {})
            self.assertFalse((output / "must-not-be-written.pac").exists())
            self.assertFalse(linked.exists())

    def test_14_duplicate_missing_paths_and_modified_source_are_rejected(self) -> None:
        entry = SimpleNamespace(path=native.BODY)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            native.select_unique_entries([entry, entry], (native.BODY,))
        with self.assertRaisesRegex(ValueError, "Missing"):
            native.select_unique_entries([], (native.BODY,))
        with tempfile.TemporaryDirectory(prefix="native-steve-source-", dir=native.ROOT / "build") as temp:
            source = Path(temp)
            (source / "cdmw").mkdir()
            (source / "cdmw" / "__init__.py").write_text("raise RuntimeError('must never execute')", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixed commit"):
                native.load_cdmw(source, self.deps)

    def test_15_fresh_readonly_archive_preparation_is_reproducible(self) -> None:
        if not self.rebuild:
            self.skipTest("Use --rebuild for a fresh read-only native archive run")
        with tempfile.TemporaryDirectory(prefix="native-steve-rebuild-", dir=native.ROOT / "build") as temp:
            result = subprocess.run([sys.executable, "-B", str(native.ROOT / "tools" / "prepare_native_steve.py"),
                                     "--cdmw-source", str(self.source), "--deps", str(self.deps),
                                     "--steve-asset", str(self.steve), "--output", temp],
                                    text=True, capture_output=True, timeout=120, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((Path(temp) / "native-steve-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report, self.report)
            for path in report["files"]:
                self.assertEqual((Path(temp) / path).read_bytes(), (self.output / path).read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=NativeSteveChecks.output)
    parser.add_argument("--cdmw-source", type=Path, default=NativeSteveChecks.source)
    parser.add_argument("--deps", type=Path, default=NativeSteveChecks.deps)
    parser.add_argument("--steve-asset", type=Path, default=NativeSteveChecks.steve)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    for name in ("output", "source", "deps", "steve", "rebuild"):
        setattr(NativeSteveChecks, name, getattr(args, {"source": "cdmw_source", "steve": "steve_asset"}.get(name, name)))
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeSteveChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
