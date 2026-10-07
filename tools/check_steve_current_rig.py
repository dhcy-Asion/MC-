"""Verify the current-rig candidate using real offline bytes and independent skinning."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_current_rig as current
from check_steve_segmented import raw_skin
from check_steve_orientation import read_native_frame

native, rig, segmented = current.native, current.rig, current.segmented


def unit(v):
    length = math.sqrt(sum(x * x for x in v))
    return tuple(x / length for x in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class CurrentRigChecks(unittest.TestCase):
    output = current.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        native.load_cdmw(native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
        cls.output = native.output_directory(cls.output)
        cls.report_raw = (cls.output / current.REPORT_NAME).read_bytes()
        cls.report = json.loads(cls.report_raw)
        cls.source_path = native.ROOT / "build/steve-segmented/steve-segmented-report.json"
        cls.source_report, cls.files, cls.snapshot = current.load_source(cls.source_path)
        cls.source = cls.files["resources/" + current.material.PAC_PATH]
        cls.candidate = (cls.output / ("resources/" + current.PAC_PATH)).read_bytes()
        cls.donor = cls.files["template/" + native.BODY]
        cls.pab = (cls.output / "template" / native.SKELETON).read_bytes()
        cls.pabc = (cls.output / "template" / current.CURRENT_VARIATION).read_bytes()
        cls.skeleton, cls.matrices, cls.covered = current.neutral_matrices(cls.pab, cls.pabc)
        from cdmw.modding.mesh_parser import resolve_pac_bone_palette
        cls.palette = resolve_pac_bone_palette(cls.source, cls.skeleton)
        cls.before = segmented.parse_lods(cls.source, cls.donor)
        cls.after = segmented.parse_lods(cls.candidate, cls.donor)

    def test_01_fixed_sources_private_paths_and_truthful_status(self):
        self.assertEqual(native.file_hash(self.source_path), current.SOURCE_REPORT_SHA256)
        self.assertEqual(native.sha256(self.source), current.SOURCE_PAC_SHA256)
        self.assertEqual(self.report["currentRigInputs"], current.TEMPLATE_HASHES)
        self.assertEqual(self.report["sourceSegmentedReportSha256"], current.SOURCE_REPORT_SHA256)
        for relative, sha in self.report["files"].items():
            self.assertEqual(native.file_hash(self.output / relative), sha)
        for path, sha in current.TEMPLATE_HASHES.items():
            self.assertEqual(native.file_hash(self.output / "template" / path), sha)
        expected = set(current.material.TEXTURE_PATHS.values()) | {current.PAC_PATH, current.MATERIAL_PATH, current.PREFAB_PATH, current.DESCRIPTOR_PATH}
        self.assertEqual({r["virtualPath"] for r in self.report["candidateResources"]}, expected)
        for row in self.report["candidateResources"]:
            self.assertEqual(row["localFile"], "resources/" + row["virtualPath"])
            self.assertEqual(native.file_hash(self.output / row["localFile"]), row["sha256"])
        self.assertNotEqual(current.PAC_PATH, current.material.PAC_PATH)
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        self.assertFalse(self.report["externalReferences"][0]["payloadResolved"])
        self.assertFalse(self.report["scaleInterpretation"]["engineApplicationOrderVerified"])

    def test_02_current_descriptor_scale_ragdoll_and_dependencies_byte_identical(self):
        original = (self.output / "template" / current.CURRENT_DESCRIPTOR).read_bytes()
        candidate = (self.output / "resources" / current.DESCRIPTOR_PATH).read_bytes()
        self.assertEqual(original, candidate)
        root = ET.fromstring(candidate.decode("utf-8-sig"))
        self.assertEqual(len(root), 5)
        self.assertEqual({r.tag: r.attrib for r in root}, current.FIELDS)
        self.assertEqual(root.find("RagdollName").attrib["FileName"], "1_pc/1_phm/macduff.hkt")
        self.assertEqual(root.find("SkeletonVariationName").attrib["FileName"], "1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc")
        self.assertNotEqual(candidate, self.files["resources/" + current.prefab.DESCRIPTOR_PATH])
        self.assertEqual((self.output / "resources" / current.MATERIAL_PATH).read_bytes(), self.files["resources/" + current.material.MATERIAL_PATH])
        for path in current.material.TEXTURE_PATHS.values():
            self.assertEqual((self.output / "resources" / path).read_bytes(), self.files["resources/" + path])

    def test_03_current_prefab_only_one_equal_length_mesh_reference_changes(self):
        from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
        original = (self.output / "template" / current.CURRENT_PREFAB).read_bytes()
        candidate = (self.output / "resources" / current.PREFAB_PATH).read_bytes()
        parsed = current.prefab.audit_prefab(original, native.BODY)
        changed = current.prefab.audit_prefab(candidate, current.PAC_PATH)
        span = parsed.objects[0].resources[0]
        offset = span.offset + 4
        self.assertEqual(len(candidate), len(original))
        self.assertEqual(candidate, original[:offset] + current.PAC_PATH.encode() + original[offset + span.length:])
        self.assertEqual(rewrite_prefab_paths(candidate, {current.PAC_PATH: native.BODY}).data, original)
        self.assertEqual(changed.objects[1].name, "CD_Underwear")
        self.assertEqual([v.text for v in changed.objects[1].resources], [current.prefab.UNDERWEAR])

    def test_04_current_420_records_coverage_and_independent_neutral_interpretation(self):
        from cdmw.modding.skeleton_variation_parser import parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices
        bones, _ = rig.parse_pab_records(self.pab)
        old, _ = rig.parse_pabc_records(self.files["template/" + native.VARIATION], bones)
        new, duplicate = rig.parse_pabc_records(self.pabc, bones)
        self.assertEqual((len(old), len(new), duplicate), (423, 420, False))
        missing = {bones[i]["name"] for i in {r["boneIndex"] for r in old} - self.covered}
        self.assertEqual(missing, {"B_Camera_FPS_00", "B_IK_L_Weapon", "B_IK_R_Weapon"})
        variation = parse_pabc_skeleton_variation(self.pabc, current.CURRENT_VARIATION, skeleton=self.skeleton)
        targets = [b.bind_matrix for b in self.skeleton.bones]
        for row in variation.records:
            targets[row.bone_index] = _neutral_variation_bind_matrix(targets[row.bone_index], row.matrix_blocks[0])
        self.assertLess(max(rig.error(a, b) for a, b in zip(_skin_matrices(self.skeleton.bones, targets), self.matrices)), 1e-12)
        used = {self.palette[s] for _, mesh in self.after for p in mesh.submeshes for slots in p.bone_indices for s in slots}
        self.assertEqual(len(used), 14)
        self.assertTrue(used.issubset(self.covered))

    def test_05_exact_skin_uv_topology_and_only_reviewed_byte_lanes_change(self):
        from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
        from cdmw.modding.mesh_pac_builder import build_pac
        allowed = set()
        descriptors, _ = native.validate_runtime_descriptors(self.donor, self.source, parse_pac(self.donor, native.BODY))
        for descriptor in descriptors:
            if any(descriptor.vertex_counts):
                allowed.update(range(descriptor.descriptor_offset + 11, descriptor.descriptor_offset + 35))
        for (lod, old), (new_lod, new) in zip(self.before, self.after):
            self.assertEqual(lod, new_lod)
            self.assertEqual((new.total_vertices, new.total_faces), (1056, 528))
            for a, b in zip(old.submeshes, new.submeshes):
                self.assertEqual((a.faces, a.uvs, a.bone_indices, a.bone_weights, a.source_vertex_offsets),
                                 (b.faces, b.uvs, b.bone_indices, b.bone_weights, b.source_vertex_offsets))
                for offset in b.source_vertex_offsets:
                    allowed.update(range(offset, offset + 8))
                    allowed.update(range(offset + 16, offset + 20))
                    self.assertEqual(self.source[offset + 8:offset + 16], self.candidate[offset + 8:offset + 16])
                    self.assertEqual(self.source[offset + 20:offset + 40], self.candidate[offset + 20:offset + 40])
                    self.assertEqual(raw_skin(self.source, offset), raw_skin(self.candidate, offset))
        self.assertEqual(len(self.source), len(self.candidate))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.source, self.candidate))))
        self.assertEqual(resolve_pac_bone_palette(self.candidate, self.skeleton), self.palette)
        self.assertEqual(build_pac(parse_pac(self.candidate, native.BODY), self.candidate), self.candidate)

    def test_06_actual_quantized_positions_and_bytes_replay_current_neutral(self):
        from cdmw.modding.skeleton_variation_parser import _deform_positions
        maximum = 0.
        baseline = 0.
        for (_, before), (_, after) in zip(self.before, self.after):
            for a, b in zip(before.submeshes, after.submeshes):
                actual = _deform_positions(b, self.palette, self.matrices)
                uncorrected = _deform_positions(a, self.palette, self.matrices)
                maximum = max(maximum, max(rig.distance(p, q) for p, q in zip(a.vertices, actual)))
                baseline = max(baseline, max(rig.distance(p, q) for p, q in zip(a.vertices, uncorrected)))
        self.assertGreater(baseline, .088)
        self.assertLess(maximum, .00003)
        self.assertAlmostEqual(maximum, self.report["compensationAudit"]["afterNeutralMaximumTargetErrorMetres"], places=12)
        # The head/body target touching planes are retained after neutral replay;
        # this says nothing about dynamic separation or native engine acceptance.
        after = self.after[0][1]
        poses = [_deform_positions(p, self.palette, self.matrices) for p in after.submeshes]
        bounds = {}
        for name in ("head", "body"):
            row = next(r for r in self.report["parts"] if r["part"] == name)
            values = poses[0 if row["nativeDrawSlot"] == 0 else 1][row["firstVertex"]:row["firstVertex"] + row["vertexCount"]]
            bounds[name] = min(p[1] for p in values), max(p[1] for p in values)
        self.assertLess(abs(bounds["head"][0] - bounds["body"][1]), .0001)

    def test_07_original_scale_is_retained_not_baked_or_cancelled(self):
        from cdmw.modding.skeleton_variation_parser import _deform_positions
        scale = float(current.FIELDS["BaseCharacterScale"]["Value"])
        self.assertEqual(scale, 1.02571)
        self.assertFalse(self.report["compensationAudit"]["baseCharacterScaleCompensated"])
        points = [p for part in self.after[0][1].submeshes for p in _deform_positions(part, self.palette, self.matrices)]
        source = [p for part in self.before[0][1].submeshes for p in part.vertices]
        raw_height = max(p[1] for p in source) - min(p[1] for p in source)
        predicted = scale * (max(p[1] for p in points) - min(p[1] for p in points))
        self.assertLess(abs(predicted - raw_height * scale), .0001)
        self.assertGreater(predicted - raw_height, .049)

    def test_08_independent_affine_normal_and_source_v_frame_roundtrip(self):
        minimum_n, minimum_v = 1., 1.
        for _, mesh in self.after:
            for part in mesh.submeshes:
                for offset in part.source_vertex_offsets:
                    skin = raw_skin(self.candidate, offset)
                    matrix = tuple(sum(weight * self.matrices[self.palette[slot]][i] for slot, weight in skin.items()) for i in range(16))
                    inverse = rig.inverse(matrix)
                    n, v, sign = read_native_frame(self.candidate, offset)
                    target_n, target_v, target_sign = read_native_frame(self.source, offset)
                    posed_n = unit(tuple(sum(n[k] * inverse[c * 4 + k] for k in range(3)) for c in range(3)))
                    posed_v = unit(tuple(sum(v[k] * matrix[k * 4 + c] for k in range(3)) for c in range(3)))
                    minimum_n = min(minimum_n, dot(posed_n, unit(target_n)))
                    minimum_v = min(minimum_v, dot(posed_v, unit(target_v)))
                    self.assertEqual(sign, target_sign)
        self.assertGreater(minimum_n, .9995)
        self.assertGreater(minimum_v, .9997)
        self.assertIn("native shader", self.report["compensationAudit"]["normalConvention"])

    def test_09_current_neutral_plus_synthetic_hand_and_foot_pose(self):
        from cdmw.modding.skeleton_variation_parser import _deform_positions
        bones, _ = rig.parse_pab_records(self.pab)
        for name in ("Bip01 L Hand", "Bip01 R Hand", "Bip01 L Foot", "Bip01 R Foot"):
            bone = next(b for b in bones if b["name"] == name)
            descendants = {i for i in range(447) if bone["index"] in segmented.ancestry(bones, i)}
            for axis in range(3):
                delta = rig.rotation_about(bone["bind"][12:15], axis, 30)
                posed = [rig.multiply(m, delta) if i in descendants else m for i, m in enumerate(self.matrices)]
                checked = 0
                for a, b in zip(self.before[0][1].submeshes, self.after[0][1].submeshes):
                    positions = _deform_positions(b, self.palette, posed)
                    for point, moved, slots in zip(a.vertices, positions, b.bone_indices):
                        if len(slots) == 1 and self.palette[slots[0]] == bone["index"]:
                            self.assertLess(rig.distance(rig.transform(point, delta), moved), .0001)
                            checked += 1
                self.assertGreater(checked, 0)

    def test_10_bad_contracts_and_output_conflicts_stop_before_publication(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            current.descriptor_contract((self.output / "resources" / current.DESCRIPTOR_PATH).read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            current.neutral_matrices(self.pab, self.files["template/" + native.VARIATION])
        for slots, weights in (((0,), (.5,)), ((0, 0), (.5, .5)), ((999,), (1.,)), ((0,), (float("nan"),))):
            with self.assertRaises(ValueError):
                current.compensate_point((0., 0., 0.), slots, weights, self.palette, self.matrices)
        with self.assertRaisesRegex(ValueError, "singular"):
            current.compensate_point((0., 0., 0.), (0,), (1.,), (0,), [(0.,) * 16])
        with tempfile.TemporaryDirectory(prefix="steve-current-rig-refuse-", dir=native.ROOT / "build") as temporary:
            output = Path(temporary)
            sentinel = output / "keep.txt"
            sentinel.write_bytes(b"preserve")
            with mock.patch.object(current, "read_templates") as read:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    current.prepare(native.ROOT / "build/game-not-used", self.source_path, output, native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
                read.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                current.orientation.preflight(output / "nested", [output])
        with self.assertRaises(ValueError):
            current.orientation.preflight(native.ROOT / "artifacts/steve-current-rig", [])

    def test_11_real_fixed_archive_rebuild_and_unchanged_source_assets(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for actual fixed-index extraction and reconstruction")
        with tempfile.TemporaryDirectory(prefix="steve-current-rig-rebuild-", dir=native.ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT / "tools/prepare_steve_current_rig.py"), "--output", str(output)],
                                    cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / current.REPORT_NAME).read_bytes(), self.report_raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
        current.orientation.verify_snapshot(self.snapshot)

    def test_12_nonsymmetric_shear_translation_and_127_128_blend_math(self):
        a = (1.2, .3, -.2, 0., .1, .8, .05, 0., 0., .1, 1.05, 0., .23, -.07, .11, 1.)
        b = (.9, -.2, .1, 0., .2, 1.1, .1, 0., -.1, .1, 1.2, 0., -.12, .05, .04, 1.)
        weights = (127 / 255, 128 / 255)
        target = (.27, 1.31, -.14)
        pre, blend = current.compensate_point(target, (0, 1), weights, (0, 1), (a, b))
        expected_matrix = tuple((127 * x + 128 * y) / 255 for x, y in zip(a, b))
        self.assertLess(max(abs(x - y) for x, y in zip(blend, expected_matrix)), 1e-15)
        # Scalar row-vector replay includes translation and off-diagonal terms;
        # diagonal-only examples would not detect a transposed convention.
        replay = tuple(sum(pre[k] * expected_matrix[k * 4 + c] for k in range(3)) + expected_matrix[12 + c] for c in range(3))
        self.assertLess(rig.distance(replay, target), 1e-12)
        inverse = rig.inverse(expected_matrix)
        normal = current.covector_normal((0., 0., 1.), expected_matrix)
        v = current.direction((1., 0., 0.), inverse)
        u = current.direction((0., 1., 0.), inverse)
        self.assertLess(abs(dot(normal, v)), 1e-12)
        self.assertLess(abs(dot(normal, u)), 1e-12)
        self.assertGreater(dot(normal, unit(current.orientation.cross(v, u))), 1 - 1e-12)
        posed_v = unit(tuple(sum(v[k] * expected_matrix[k * 4 + c] for k in range(3)) for c in range(3)))
        self.assertGreater(dot(posed_v, (1., 0., 0.)), 1 - 1e-12)
        inverted = (-1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)
        with self.assertRaisesRegex(ValueError, "inverted"):
            current.compensate_point(target, (0,), (1.,), (0,), (inverted,))

    def test_13_missing_pabc_coverage_and_unlicensed_byte_edits_refused(self):
        with mock.patch.object(current, "neutral_matrices", return_value=(self.skeleton, self.matrices, self.covered - {93})):
            with self.assertRaisesRegex(ValueError, "absent"):
                current.compensate_pac(self.source, self.donor, self.pab, self.pabc)
        original = segmented.pack_frame
        def corrupt_skin(data, offset, v, sign):
            original(data, offset, v, sign)
            data[offset + 28] ^= 1
        with mock.patch.object(segmented, "pack_frame", side_effect=corrupt_skin):
            with self.assertRaisesRegex(ValueError, "unreviewed PAC byte lane"):
                current.compensate_pac(self.source, self.donor, self.pab, self.pabc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=current.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    CurrentRigChecks.output, CurrentRigChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CurrentRigChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
