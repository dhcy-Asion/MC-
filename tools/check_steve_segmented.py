"""Check the separate limb candidate against real local assets, without a game."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import prepare_steve_segmented as segmented
from check_steve_orientation import read_native_frame

native, rig, orientation = segmented.native, segmented.rig, segmented.orientation


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def distance(a, b):
    return math.sqrt(dot(sub(a, b), sub(a, b)))


def raw_skin(data, offset):
    words = [int.from_bytes(data[offset + n:offset + n + 4], "little") for n in (20, 24)]
    slots = [(word >> (10 * index)) & 1023 for word in words for index in range(3)]
    weights = data[offset + 28:offset + 34]
    if data[offset + 39] & 63 != 63 or sum(weights) != 255:
        raise ValueError("Not a normalized ordinary native skin record")
    return {slot: weight / 255 for slot, weight in zip(slots, weights) if weight}


class SegmentedChecks(unittest.TestCase):
    output = segmented.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        native.load_cdmw(native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
        cls.output = native.output_directory(cls.output)
        cls.report_raw = (cls.output / segmented.REPORT_NAME).read_bytes()
        cls.report = json.loads(cls.report_raw)
        cls.source_report_path = native.ROOT / "build/steve-orientation/steve-orientation-report.json"
        cls.source_report, cls.source_files, cls.snapshot = segmented.load_inputs(cls.source_report_path)
        cls.donor = cls.source_files["template/" + native.BODY]
        cls.pab = cls.source_files["template/" + native.SKELETON]
        cls.pabc = cls.snapshot[native.ROOT / ("build/native-steve/template/" + native.VARIATION)]
        cls.candidate = (cls.output / ("resources/" + segmented.material.PAC_PATH)).read_bytes()
        cls.source_pac = cls.source_files["resources/" + segmented.material.PAC_PATH]
        cls.bones, cls.skeleton, cls.palette, cls.plan, cls.neutral = segmented.bind_plan(cls.pab, cls.donor, cls.pabc)
        cls.levels = segmented.parse_lods(cls.candidate, cls.donor)
        cls.parts = {p["name"]: p for p in native.steve_geometry(native.ROOT / "build/steve-1.21.1")}

    def test_01_fixed_inputs_and_seven_resource_provenance(self):
        self.assertEqual(native.file_hash(self.source_report_path), segmented.ORIENTATION_REPORT_SHA256)
        self.assertEqual(self.report["sourceOrientationReportSha256"], segmented.ORIENTATION_REPORT_SHA256)
        self.assertEqual(self.report["rigInputs"], orientation.fixed_rig_inputs())
        changed = []
        self.assertEqual(len(self.report["candidateResources"]), 7)
        for relative, sha in self.report["files"].items():
            data = (self.output / relative).read_bytes()
            self.assertEqual(native.sha256(data), sha)
            if data != self.source_files[relative]:
                changed.append(relative)
        self.assertEqual(changed, ["resources/" + segmented.material.PAC_PATH])
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        self.assertFalse(self.report["segmentedAudit"]["motion"]["liveAnimationVerified"])
        self.assertEqual(self.report["supportedExeSha256"], native.EXE_SHA256)
        self.assertTrue(any("head separation" in text and "unresolved" in text for text in self.report["limitations"]))

    def test_02_native_palette_descriptors_and_no_edit_roundtrip(self):
        from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
        from cdmw.modding.mesh_pac_builder import build_pac
        self.assertEqual(len(self.bones), 447)
        self.assertEqual(len(self.palette), 189)
        self.assertEqual(resolve_pac_bone_palette(self.candidate, self.skeleton), self.palette)
        self.assertEqual(build_pac(parse_pac(self.candidate, native.BODY), self.candidate), self.candidate)
        self.assertEqual([lod for lod, _ in self.levels], [0, 1, 2, 3])
        for _, mesh in self.levels:
            self.assertEqual((mesh.total_vertices, mesh.total_faces, len(mesh.submeshes)), (1056, 528, 2))
        for row in self.report["parts"]:
            limb = row["logicalPart"] in self.plan
            self.assertEqual((row["vertexCount"], row["faceCount"]), (120, 60) if limb else (24, 12))
        self.assertEqual(len(self.report["parts"]), 12)
        self.assertEqual(len({p["logicalPart"] for p in self.report["parts"]}), 6)

    def test_03_independent_surface_uv_area_and_winding_all_lods(self):
        # Compare every new triangle/vertex with the original unsegmented face,
        # using an independent affine UV solve, not the author's clipping output.
        for _, mesh in self.levels:
            for row in self.report["parts"]:
                actual = mesh.submeshes[0 if row["nativeDrawSlot"] == 0 else 1]
                source = self.parts[row["part"]]
                quads = []
                for first in range(0, 24, 4):
                    points = [(x, y, -z) for x, y, z in source["vertices"][first:first + 4]]
                    uvs = [(u, 1 - v) for u, v in source["uvs"][first:first + 4]]
                    x, y, z = source["normals"][first]
                    quads.append((points, uvs, (x, y, -z)))
                totals = [0.] * 6
                base, end = row["firstVertex"], row["firstVertex"] + row["vertexCount"]
                for i in range(base, end):
                    point, normal = actual.vertices[i], actual.normals[i]
                    which = [k for k, (_, _, n) in enumerate(quads) if dot(n, normal) > .999]
                    self.assertEqual(len(which), 1)
                    points, uvs, n = quads[which[0]]
                    e1, e2 = sub(points[1], points[0]), sub(points[3], points[0])
                    rel = sub(point, points[0])
                    s, t = dot(rel, e1) / dot(e1, e1), dot(rel, e2) / dot(e2, e2)
                    self.assertLess(abs(dot(rel, n)), .0001)
                    self.assertGreaterEqual(min(s, t), -.0002)
                    self.assertLessEqual(max(s, t), 1.0002)
                    expected_uv = [uvs[0][k] + s * (uvs[1][k] - uvs[0][k]) + t * (uvs[3][k] - uvs[0][k]) for k in range(2)]
                    self.assertLess(max(abs(a - b) for a, b in zip(expected_uv, actual.uvs[i])), .0006)
                for face in actual.faces[row["firstFace"]:row["firstFace"] + row["faceCount"]]:
                    self.assertTrue(all(base <= i < end for i in face))
                    a, b, c = [actual.vertices[i] for i in face]
                    area = orientation.cross(sub(b, a), sub(c, a))
                    which = next(k for k, (_, _, n) in enumerate(quads) if dot(n, actual.normals[face[0]]) > .999)
                    self.assertGreater(dot(area, quads[which][2]), 0)
                    totals[which] += math.sqrt(dot(area, area)) / 2
                for area, (points, _, _) in zip(totals, quads):
                    expected = distance(points[0], points[1]) * distance(points[0], points[3])
                    self.assertLess(abs(area - expected), .0001)

    def test_04_independent_packed_weight_and_distal_endpoint_contract(self):
        used = set()
        for _, mesh in self.levels:
            for row in self.report["parts"]:
                part = mesh.submeshes[0 if row["nativeDrawSlot"] == 0 else 1]
                plan = self.plan.get(row["logicalPart"])
                for i in range(row["firstVertex"], row["firstVertex"] + row["vertexCount"]):
                    weights = raw_skin(self.candidate, part.source_vertex_offsets[i])
                    self.assertEqual(weights, dict(zip(part.bone_indices[i], part.bone_weights[i])))
                    self.assertIn(len(weights), (1, 2))
                    used.update(weights)
                    if len(weights) == 2:
                        self.assertEqual(sorted(weights.values()), [127 / 255, 128 / 255])
                    if plan:
                        slots = [b["paletteSlot"] for b in plan["bones"]]
                        y = part.vertices[i][1]
                        if y < plan["jointY"][1] - segmented.HALF_BAND - .0001:
                            self.assertEqual(weights, {slots[2]: 1.})
                        elif plan["jointY"][1] + segmented.HALF_BAND + .0001 < y < plan["jointY"][0] - segmented.HALF_BAND - .0001:
                            self.assertEqual(weights, {slots[1]: 1.})
                        elif y > plan["jointY"][0] + segmented.HALF_BAND + .0001:
                            self.assertEqual(weights, {slots[0]: 1.})
        self.assertEqual(used, {8, 136, 51, 92, 82, 56, 100, 78, 176, 161, 160, 138, 140, 144})

    def test_05_same_surface_points_have_identical_skin_and_no_cut_cracks(self):
        for _, mesh in self.levels:
            for row in self.report["parts"]:
                part = mesh.submeshes[0 if row["nativeDrawSlot"] == 0 else 1]
                seen = {}
                for i in range(row["firstVertex"], row["firstVertex"] + row["vertexCount"]):
                    point = part.vertices[i]
                    skin = raw_skin(self.candidate, part.source_vertex_offsets[i])
                    if point in seen:
                        self.assertEqual(seen[point], skin)
                    seen[point] = skin
                self.assertEqual(len({point[1] for point in seen}), 8 if row["logicalPart"] in self.plan else 2)

    def test_06_pab_rest_and_pabc_neutral_against_independent_cdmw_path(self):
        from cdmw.modding.skeleton_variation_parser import parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices, _deform_positions
        variation = parse_pabc_skeleton_variation(self.pabc, native.VARIATION, skeleton=self.skeleton)
        targets = [bone.bind_matrix for bone in self.skeleton.bones]
        for row in variation.records:
            targets[row.bone_index] = _neutral_variation_bind_matrix(targets[row.bone_index], row.matrix_blocks[0])
        matrices = _skin_matrices(self.skeleton.bones, targets)
        self.assertLess(max(rig.error(a, b) for a, b in zip(matrices, self.neutral)), 1e-12)
        rest = _skin_matrices(self.skeleton.bones, [b.bind_matrix for b in self.skeleton.bones])
        for _, mesh in self.levels:
            for part in mesh.submeshes:
                neutral = _deform_positions(part, self.palette, matrices)
                static = _deform_positions(part, self.palette, rest)
                self.assertLess(max(distance(p, q) for p, q in zip(part.vertices, static)), 1e-6)
                self.assertLess(max(distance(p, q) for p, q in zip(part.vertices, neutral)), .00001)

    def test_07_forearm_calf_and_endpoint_pose_response_with_real_inverse_binds(self):
        from cdmw.modding.skeleton_variation_parser import _skin_matrices, _deform_positions
        byname = {b["name"]: b for b in self.bones}
        mesh = self.levels[0][1]
        for logical, plan in self.plan.items():
            row = next(p for p in self.report["parts"] if p["part"] == logical)
            actual = mesh.submeshes[1]
            first, last = row["firstVertex"], row["firstVertex"] + row["vertexCount"]
            for driver in plan["jointDrivers"]:
                b = byname[driver]
                descendants = {i for i in range(447) if b["index"] in segmented.ancestry(self.bones, i)}
                # Build actual posed global matrices, then let fixed CDMW apply
                # inverse binds. End-only rows must match an analytic rigid turn.
                for axis in range(3):
                    delta = rig.rotation_about(b["bind"][12:15], axis, 30)
                    targets = [rig.multiply(x.bind_matrix, delta) if i in descendants else x.bind_matrix for i, x in enumerate(self.skeleton.bones)]
                    moved = _deform_positions(actual, self.palette, _skin_matrices(self.skeleton.bones, targets))
                    distal = proximal = changed = 0
                    for i in range(first, last):
                        skin = raw_skin(self.candidate, actual.source_vertex_offsets[i])
                        if skin == {plan["bones"][2]["paletteSlot"]: 1.}:
                            self.assertLess(distance(moved[i], rig.transform(actual.vertices[i], delta)), 1e-6)
                            distal += 1
                        if skin == {plan["bones"][0]["paletteSlot"]: 1.}:
                            self.assertLess(distance(moved[i], actual.vertices[i]), 1e-6)
                            proximal += 1
                        changed += distance(moved[i], actual.vertices[i]) > 1e-6
                    self.assertGreater(min(distal, proximal, changed), 0)
        self.assertEqual(len(self.report["segmentedAudit"]["motion"]["syntheticRotations"]), 24)

    def test_08_named_weapon_anchor_is_inside_hand_only_classic_region(self):
        lookup = {b["name"]: b for b in self.bones}
        for side, prefix in (("L", "left"), ("R", "right")):
            source, plan = self.parts[prefix + "_arm"], self.plan[prefix + "_arm"]
            anchor, hand = lookup["Bip_Weapon_" + side], lookup["Bip01 " + side + " Hand"]
            point = anchor["bind"][12:15]
            reflected = [(x, y, -z) for x, y, z in source["vertices"]]
            for i in range(3):
                self.assertLessEqual(min(v[i] for v in reflected), point[i])
                self.assertGreaterEqual(max(v[i] for v in reflected), point[i])
            self.assertEqual(anchor["parent"], hand["index"])
            self.assertLess(point[1], plan["jointY"][1] - segmented.HALF_BAND)
            local = rig.transform(point, hand["inverse"])
            self.assertLess(distance(point, rig.transform(local, hand["bind"])), 1e-6)
        self.assertTrue(all(not r["actualEquipmentSocketVerified"] for r in self.report["segmentedAudit"]["motion"]["namedWeaponAnchors"]))

    def test_09_independent_frames_have_correct_normal_and_uv_derivatives(self):
        for _, mesh in self.levels:
            for part in mesh.submeshes:
                for face in part.faces:
                    p0, p1, p2 = [part.vertices[i] for i in face]
                    uv0, uv1, uv2 = [part.uvs[i] for i in face]
                    e1, e2 = sub(p1, p0), sub(p2, p0)
                    a, b = sub(uv1, uv0), sub(uv2, uv0)
                    det = a[0] * b[1] - a[1] * b[0]
                    self.assertNotEqual(det, 0)
                    u = tuple((e1[k] * b[1] - e2[k] * a[1]) / det for k in range(3))
                    v = tuple((e2[k] * a[0] - e1[k] * b[0]) / det for k in range(3))
                    for i in face:
                        n, packed_v, sign = read_native_frame(self.candidate, part.source_vertex_offsets[i])
                        self.assertLess(abs(dot(n, packed_v)), .004)
                        self.assertGreater(dot(orientation.unit(packed_v), orientation.plane(v, n)), .9999)
                        recovered_u = tuple(x * sign for x in orientation.cross(n, packed_v))
                        self.assertGreater(dot(orientation.unit(recovered_u), orientation.plane(u, n)), .9999)

    def test_10_bad_sources_bone_slots_and_geometry_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="steve-segmented-negative-", dir=native.ROOT / "build") as temporary:
            path = Path(temporary) / "bad.json"
            path.write_bytes(self.source_report_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                segmented.load_inputs(path)
        bad = copy.deepcopy(segmented.SEGMENTS)
        bad["left_arm"] = (("Bip01 L UpArmTwist", 133, 56), *bad["left_arm"][1:])
        with mock.patch.object(segmented, "SEGMENTS", bad):
            with self.assertRaisesRegex(ValueError, "palette"):
                segmented.bind_plan(self.pab, self.donor, self.pabc)
        bad_part = copy.deepcopy(self.parts["left_arm"])
        bad_part["faces"][0] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, "six original"):
            segmented.author_parts([bad_part], self.plan, {})
        bad_plan = copy.deepcopy(self.plan)
        bad_plan["left_arm"]["cutsY"][0] = -10
        with self.assertRaisesRegex(ValueError, "outside"):
            segmented.author_parts([self.parts["left_arm"]], bad_plan, {})

    def test_11_output_collision_scope_and_changed_snapshot_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="steve-segmented-output-", dir=native.ROOT / "build") as temporary:
            path = Path(temporary)
            sentinel = path / "sentinel.txt"
            sentinel.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "already exists"):
                segmented.prepare(self.source_report_path, path, native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                orientation.preflight(path / "nested", [path])
            with self.assertRaisesRegex(ValueError, "changed"):
                orientation.verify_snapshot({sentinel: b"previous"})
        with self.assertRaises(ValueError):
            orientation.preflight(native.ROOT / "artifacts/steve-segmented", [])

    def test_12_real_fresh_rebuild_matches_all_bytes_and_preserves_sources(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for an independent real reconstruction")
        with tempfile.TemporaryDirectory(prefix="steve-segmented-rebuild-", dir=native.ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT / "tools/prepare_steve_segmented.py"), "--output", str(output)],
                                    cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / segmented.REPORT_NAME).read_bytes(), self.report_raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
        orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=segmented.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    SegmentedChecks.output, SegmentedChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
