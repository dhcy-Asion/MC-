"""Verify the real offline orientation candidate and independently read its frames."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import prepare_steve_orientation as orientation


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def normalized(v):
    length = math.sqrt(dot(v, v))
    if length < 1e-12:
        raise ValueError("Independent frame is degenerate")
    return tuple(x / length for x in v)


def projected(v, n):
    n = normalized(n)
    return normalized(tuple(x - dot(v, n) * y for x, y in zip(v, n)))


def read_native_frame(raw, offset):
    # Read from raw little-endian bytes without using the candidate codec.
    signed_lane = int.from_bytes(raw[offset + 6:offset + 8], "little", signed=True)
    packed = int.from_bytes(raw[offset + 16:offset + 20], "little")
    nx, ny = 2 * ((packed >> 10) & 1023) / 1023 - 1, 2 * ((packed >> 20) & 1023) / 1023 - 1
    nz = math.sqrt(max(0, 1 - nx * nx - ny * ny)) * (-1 if packed & (1 << 30) else 1)
    vx, vy = 2 * abs(signed_lane) / 32767 - 1, 2 * (packed & 1023) / 1023 - 1
    vz = math.sqrt(max(0, 1 - vx * vx - vy * vy)) * (-1 if signed_lane < 0 else 1)
    return (nx, ny, nz), (vx, vy, vz), (1 if packed & (1 << 31) else -1)


class OrientationChecks(unittest.TestCase):
    output = orientation.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        native, prefab = orientation.native, orientation.prefab
        native.load_cdmw(native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
        cls.output = native.output_directory(cls.output)
        cls.report_raw = (cls.output / orientation.REPORT_NAME).read_bytes()
        cls.report = prefab.strict_json(cls.report_raw)
        cls.source_dir = native.ROOT / "build/steve-prefab"
        cls.source_report = prefab.strict_json((cls.source_dir / prefab.REPORT_NAME).read_bytes())
        cls.source = (cls.source_dir / ("resources/" + orientation.material.PAC_PATH)).read_bytes()
        cls.candidate = (cls.output / ("resources/" + orientation.material.PAC_PATH)).read_bytes()
        cls.donor = (cls.source_dir / ("template/" + native.BODY)).read_bytes()
        cls.pab = (cls.source_dir / ("template/" + native.SKELETON)).read_bytes()
        cls.source_lods, cls.descriptors = orientation.parse_lods(cls.source, cls.donor)
        cls.target_lods, cls.target_descriptors = orientation.parse_lods(cls.candidate, cls.donor)

    def test_01_fixed_source_reports_inputs_and_truthful_candidate_hash(self):
        native, prefab = orientation.native, orientation.prefab
        self.assertEqual(native.file_hash(self.source_dir / prefab.REPORT_NAME), orientation.PREFAB_REPORT_SHA256)
        self.assertEqual(native.file_hash(native.ROOT / "build/steve-rig-analysis/steve-rig-analysis.json"), orientation.RIG_REPORT_SHA256)
        self.assertEqual(self.report["rigInputs"], orientation.fixed_rig_inputs())
        for relative, digest in self.report["rigInputs"].items():
            self.assertEqual(native.file_hash(native.ROOT / relative), digest)
        self.assertTrue(self.report["orientationCandidate"])
        self.assertEqual(native.sha256(self.candidate), self.report["orientationAudit"]["candidatePacSha256"])
        self.assertNotEqual(native.sha256(self.candidate), native.sha256(self.source))
        self.assertEqual(self.report["orientationAudit"]["sourcePacSha256"], native.sha256(self.source))
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        self.assertNotIn("prefabAudit", self.report)  # No inherited audit describes the edited PAC.

    def test_02_only_pac_changes_other_six_resources_and_all_templates_identical(self):
        changed = []
        self.assertEqual(len(self.report["candidateResources"]), 7)
        for row in self.report["candidateResources"]:
            source = next(r for r in self.source_report["candidateResources"] if r["virtualPath"] == row["virtualPath"])
            self.assertEqual({k: v for k, v in row.items() if k != "sha256"}, {k: v for k, v in source.items() if k != "sha256"})
            data = (self.output / row["localFile"]).read_bytes()
            self.assertEqual(orientation.native.sha256(data), row["sha256"])
            if data != (self.source_dir / row["localFile"]).read_bytes():
                changed.append(row["virtualPath"])
        self.assertEqual(changed, [orientation.material.PAC_PATH])
        self.assertEqual(self.report["unchangedCandidateCount"], 6)
        for relative, digest in self.report["files"].items():
            self.assertEqual(orientation.native.file_hash(self.output / relative), digest)
            if relative.startswith("template/"):
                self.assertEqual((self.output / relative).read_bytes(), (self.source_dir / relative).read_bytes())

    def test_03_no_edit_baseline_descriptors_palette_and_four_lods(self):
        from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
        from cdmw.modding.mesh_pac_builder import build_pac
        from cdmw.modding.skeleton_parser import parse_pab
        self.assertEqual(build_pac(parse_pac(self.source, orientation.native.BODY), self.source), self.source)
        self.assertEqual(build_pac(parse_pac(self.candidate, orientation.native.BODY), self.candidate), self.candidate)
        self.assertEqual(self.descriptors, self.target_descriptors)
        skeleton = parse_pab(self.pab, orientation.native.SKELETON)
        self.assertEqual(resolve_pac_bone_palette(self.source, skeleton), resolve_pac_bone_palette(self.candidate, skeleton))
        self.assertEqual([lod for lod, _ in self.target_lods], [0, 1, 2, 3])
        for _, mesh in self.target_lods:
            self.assertEqual((mesh.total_vertices, mesh.total_faces), (288, 144))

    def test_04_independent_positions_normals_and_once_only_winding(self):
        for (lod, before), (new_lod, after) in zip(self.source_lods, self.target_lods):
            self.assertEqual(lod, new_lod)
            for a, b in zip(before.submeshes, after.submeshes):
                self.assertEqual(b.faces, [(x, z, y) for x, y, z in a.faces])
                for old, new, on, nn, offset in zip(a.vertices, b.vertices, a.normals, b.normals, a.source_vertex_offsets):
                    self.assertEqual(old[:2], new[:2])
                    self.assertAlmostEqual(old[2], -new[2], places=14)
                    self.assertEqual(on[:2], nn[:2])
                    self.assertAlmostEqual(on[2], -nn[2], places=14)
                    old_q = int.from_bytes(self.source[offset + 4:offset + 6], "little")
                    new_q = int.from_bytes(self.candidate[offset + 4:offset + 6], "little")
                    self.assertEqual(old_q + new_q, 32767)
                for face in b.faces:
                    pa, pb, pc = [b.vertices[i] for i in face]
                    area = cross(tuple(y - x for x, y in zip(pa, pb)), tuple(y - x for x, y in zip(pa, pc)))
                    self.assertGreater(dot(area, b.normals[face[0]]), 0)

    def test_05_independent_per_triangle_uv_frame_and_empirical_handedness(self):
        count = 0
        for _, mesh in self.target_lods:
            for part in mesh.submeshes:
                for face in part.faces:
                    a, b, c = face
                    p0, p1, p2 = [part.vertices[i] for i in face]
                    uv0, uv1, uv2 = [part.uvs[i] for i in face]
                    e1, e2 = [p1[i] - p0[i] for i in range(3)], [p2[i] - p0[i] for i in range(3)]
                    u1, v1 = uv1[0] - uv0[0], uv1[1] - uv0[1]
                    u2, v2 = uv2[0] - uv0[0], uv2[1] - uv0[1]
                    determinant = u1 * v2 - u2 * v1
                    self.assertNotEqual(determinant, 0)
                    uv_u = [(e1[i] * v2 - e2[i] * v1) / determinant for i in range(3)]
                    uv_v = [(e2[i] * u1 - e1[i] * u2) / determinant for i in range(3)]
                    for index in face:
                        normal, packed_v, sign = read_native_frame(self.candidate, part.source_vertex_offsets[index])
                        self.assertLess(abs(dot(normalized(normal), normalized(packed_v))), .004)
                        self.assertGreater(dot(normalized(packed_v), projected(uv_v, normal)), .99999)
                        recovered_u = tuple(x * sign for x in cross(normalized(normal), normalized(packed_v)))
                        self.assertGreater(dot(normalized(recovered_u), projected(uv_u, normal)), .99999)
                        count += 1
        self.assertEqual(count, 4 * 144 * 3)
        audit = self.report["orientationAudit"]
        self.assertEqual(audit["candidateRecordsWithCompleteFrames"], 1152)
        self.assertEqual(audit["candidateTrianglesReversedOnce"], 576)

    def test_06_all_twelve_layers_uv_and_left_right_semantics(self):
        from cdmw.modding.skeleton_parser import parse_pab
        from cdmw.modding.mesh_parser import resolve_pac_bone_palette
        skeleton = parse_pab(self.pab, orientation.native.SKELETON)
        palette = resolve_pac_bone_palette(self.candidate, skeleton)
        mapping = orientation.native.rig_candidates(skeleton, palette)
        authored = orientation.native.steve_geometry(orientation.ROOT / "build/steve-1.21.1")
        before, after = self.source_lods[0][1], self.target_lods[0][1]
        cursors, seen = [0, 0], []
        for part in authored:
            slot = 0 if part["parent"] == "head" else 1
            start, end = cursors[slot], cursors[slot] + len(part["vertices"])
            cursors[slot] = end
            actual, old = after.submeshes[slot], before.submeshes[slot]
            for source, reflected in zip(part["vertices"], actual.vertices[start:end]):
                self.assertLess(max(abs(x - y) for x, y in zip((source[0], source[1], -source[2]), reflected)), .0001)
            self.assertEqual(actual.uvs[start:end], old.uvs[start:end])
            self.assertTrue(all(row == (mapping[part["parent"]]["paletteSlot"],) for row in actual.bone_indices[start:end]))
            self.assertTrue(all(row == (1.,) for row in actual.bone_weights[start:end]))
            if part["parent"].startswith("left_"):
                self.assertGreater(sum(v[0] for v in actual.vertices[start:end]), 0)
            if part["parent"].startswith("right_"):
                self.assertLess(sum(v[0] for v in actual.vertices[start:end]), 0)
            seen.append(part["name"])
        self.assertEqual(len(seen), 12)
        self.assertEqual(cursors, [48, 240])
        self.assertEqual({p["part"] for p in self.report["parts"]}, set(seen))

    def test_07_all_opaque_bytes_unchanged_outside_proven_lanes(self):
        allowed = set()
        for _, mesh in self.source_lods:
            for part in mesh.submeshes:
                for offset in part.source_vertex_offsets:
                    allowed.update(range(offset + 4, offset + 8))
                    allowed.update(range(offset + 16, offset + 20))
                    self.assertEqual(self.source[offset:offset + 4], self.candidate[offset:offset + 4])
                    self.assertEqual(self.source[offset + 8:offset + 16], self.candidate[offset + 8:offset + 16])
                    self.assertEqual(self.source[offset + 20:offset + 40], self.candidate[offset + 20:offset + 40])
                allowed.update(range(part.source_index_offset, part.source_index_offset + len(part.faces) * 6))
        self.assertEqual(len(self.source), len(self.candidate))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.source, self.candidate))))

    def test_08_fixed_donor_empirical_contract_and_contradiction_stops(self):
        from cdmw.modding.mesh_parser import parse_pac
        contract = self.report["orientationAudit"]["packedFrameContract"]
        self.assertEqual(contract["classification"], "source-backed empirical")
        self.assertFalse(contract["shaderAbiProven"])
        self.assertFalse(contract["liveVerified"])
        self.assertEqual(contract["uniqueStrongRecords"], 11476)
        self.assertEqual((contract["positiveHandednessRecords"], contract["negativeHandednessRecords"]), (5, 11471))
        self.assertEqual(contract["contradictions"], 0)
        for relative, digest in contract["fixedSourceEvidence"].items():
            self.assertEqual(orientation.native.file_hash(orientation.ROOT / "build/cdmw-fixed-source" / relative), digest)
        original_decode = orientation.decode_record_frame
        conflict_offset = contract["positiveRecordOffsets"][0]
        def contradicted(data, offset):
            n, v, sign = original_decode(data, offset)
            return n, v, -sign if offset == conflict_offset else sign
        with mock.patch.object(orientation, "decode_record_frame", side_effect=contradicted):
            with self.assertRaisesRegex(ValueError, "contradictory"):
                orientation.donor_contract(self.donor, parse_pac(self.donor, orientation.native.BODY))

    def test_09_incomplete_conflicting_frames_and_corrupted_source_rejected(self):
        with self.assertRaises(ValueError):
            orientation.triangle_uv_frame([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 0)] * 3)
        with self.assertRaisesRegex(ValueError, "unreferenced"):
            orientation.vertex_frames([(0, 0, 0)], [(0, 1, 0)], [(0, 0)], [])
        corrupted = bytearray(self.source)
        corrupted[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "fixed SHA"):
            orientation.reflect_pac(bytes(corrupted), self.donor, self.pab)

    def test_10_preserved_prefab_and_skeleton_dependency_contract(self):
        prefab, native = orientation.prefab, orientation.native
        prefab.audit_prefab((self.output / ("resources/" + prefab.PREFAB_PATH)).read_bytes(), orientation.material.PAC_PATH)
        prefab.audit_descriptor((self.output / ("resources/" + prefab.DESCRIPTOR_PATH)).read_bytes())
        for path, digest in prefab.DEPENDENCIES.items():
            self.assertEqual(native.file_hash(self.output / "template" / path), digest)
        self.assertEqual(self.report["logicalPrefabPath"], prefab.LOGICAL_PREFAB)
        from cdmw.core.pac_xml_standard_material import find_material_wrappers
        wrappers = find_material_wrappers((self.output / ("resources/" + orientation.material.MATERIAL_PATH)).read_text(encoding="utf-8-sig"))
        source_wrappers = find_material_wrappers((self.source_dir / ("resources/" + orientation.material.MATERIAL_PATH)).read_text(encoding="utf-8-sig"))
        self.assertEqual([(w.submesh_name, w.textures) for w in wrappers], [(w.submesh_name, w.textures) for w in source_wrappers])
        self.assertEqual(len(wrappers), 18)

    def test_11_output_collision_overlap_and_fixed_input_refusals(self):
        with tempfile.TemporaryDirectory(prefix="steve-orientation-refuse-", dir=orientation.ROOT / "build") as temporary:
            directory = orientation.native.output_directory(Path(temporary))
            keep = directory / "owned.txt"
            keep.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "already exists"):
                orientation.preflight(directory, [])
            self.assertEqual(keep.read_bytes(), b"preserve")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                orientation.preflight(directory / "nested", [directory])
            bad_report = directory / orientation.prefab.REPORT_NAME
            bad_report.write_bytes((self.source_dir / orientation.prefab.REPORT_NAME).read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                orientation.load_inputs(bad_report, orientation.ROOT / "build/steve-rig-analysis/steve-rig-analysis.json")
            source = directory / "snapshot.bin"
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                orientation.verify_snapshot({source: b"original"})
        with self.assertRaises(ValueError):
            orientation.preflight(orientation.ROOT / "artifacts/steve-orientation", [])
        with self.assertRaises(ValueError):
            orientation.preflight(orientation.ROOT / "build", [])

    def test_12_real_junction_inputs_and_outputs_refused(self):
        with tempfile.TemporaryDirectory(prefix="steve-orientation-link-", dir=orientation.ROOT / "build") as temporary:
            directory = orientation.native.output_directory(Path(temporary))
            link = directory / "source-link"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.source_dir)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            try:
                with self.assertRaisesRegex(ValueError, "junction"):
                    orientation.preflight(link / "output", [])
                with self.assertRaisesRegex(ValueError, "junction"):
                    orientation.load_inputs(link / orientation.prefab.REPORT_NAME, orientation.ROOT / "build/steve-rig-analysis/steve-rig-analysis.json")
            finally:
                link.rmdir()

    def test_13_real_rebuild_byte_identical_and_inputs_untouched(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for an independent real reconstruction")
        with tempfile.TemporaryDirectory(prefix="steve-orientation-rebuild-", dir=orientation.ROOT / "build") as temporary:
            output = orientation.native.output_directory(Path(temporary)) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(orientation.ROOT / "tools/prepare_steve_orientation.py"),
                                     "--output", str(output)], cwd=orientation.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / orientation.REPORT_NAME).read_bytes(), self.report_raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
            self.assertEqual(orientation.native.sha256((self.source_dir / ("resources/" + orientation.material.PAC_PATH)).read_bytes()), orientation.rig.CANDIDATE_SHA256)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=orientation.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    OrientationChecks.output, OrientationChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OrientationChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
