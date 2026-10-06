"""Check Steve rig evidence, matrix math and safe deterministic reconstruction."""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import analyze_steve_rig as rig


class RigChecks(unittest.TestCase):
    output = rig.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = rig.native.output_directory(cls.output)
        cls.report_bytes = (cls.output / rig.REPORT_NAME).read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.raw_pab = (rig.ROOT / "build/native-steve/template" / rig.native.SKELETON).read_bytes()
        cls.raw_pabc = (rig.ROOT / "build/native-steve/template" / rig.native.VARIATION).read_bytes()
        cls.bones, _ = rig.parse_pab_records(cls.raw_pab)
        cls.records, _ = rig.parse_pabc_records(cls.raw_pabc, cls.bones)
        cls.parts = rig.native.steve_geometry(rig.ROOT / "build/steve-1.21.1")

    def test_01_fixed_inputs_source_and_no_integration_claims(self):
        expected = {
            "build/native-steve/template/" + rig.native.SKELETON: rig.native.TEMPLATE_HASHES[rig.native.SKELETON],
            "build/native-steve/template/" + rig.native.BODY: rig.native.TEMPLATE_HASHES[rig.native.BODY],
            "build/native-steve/template/" + rig.native.VARIATION: rig.PABC_SHA256,
            "build/native-steve/steve-rig-candidate.pac": rig.CANDIDATE_SHA256,
            "build/steve-prefab/template/" + rig.PREFAB_PATH: rig.PREFAB_SHA256,
            "build/steve-prefab/template/" + rig.native.DESCRIPTOR: rig.DESCRIPTOR_SHA256,
            **{"build/steve-1.21.1/" + k: v for k, v in rig.native.STEVE_HASHES.items()},
        }
        self.assertEqual(self.report["inputs"], expected)
        for path, digest in expected.items():
            self.assertEqual(rig.native.file_hash(rig.ROOT / path), digest)
        self.assertEqual(rig.native.verify_source(rig.ROOT / "build/cdmw-fixed-source")["commit"], self.report["cdmw"]["commit"])
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        self.assertFalse(self.report["runtimeRetargetCandidate"]["implemented"])
        self.assertTrue(self.report["runtimeRetargetCandidate"]["syntheticEvidenceOnly"])
        self.assertFalse(self.report["coordinateContract"]["minimalStaticOrientationCandidate"]["generated"])

    def test_02_all_native_matrices_and_six_joint_identities(self):
        self.assertEqual(len(self.bones), 447)
        native_max = max(rig.error(rig.multiply(b["bind"], b["inverse"])) for b in self.bones)
        local_max = max(rig.error(rig.multiply(b["local"], self.bones[b["parent"]]["bind"] if b["parent"] >= 0 else rig.IDENTITY), b["bind"]) for b in self.bones)
        self.assertLess(native_max, 1e-6)
        self.assertLess(local_max, 1e-5)
        self.assertEqual(native_max, self.report["pab"]["maximumBindTimesInverseIdentityError"])
        self.assertEqual(local_max, self.report["pab"]["maximumLocalTimesParentVsGlobalError"])
        self.assertEqual(len(self.report["joints"]), 6)
        for j in self.report["joints"]:
            bone = self.bones[j["pabIndex"]]
            self.assertEqual(bone["name"], j["boneName"])
            self.assertEqual(bone["hash"], j["nameHash"])
            self.assertEqual(list(bone["bind"]), j["nativeGlobalBindRowMajor"])
            self.assertEqual(list(bone["inverse"]), j["nativeGlobalInverseBindRowMajor"])
            self.assertLess(rig.error(rig.inverse(bone["bind"]), bone["inverse"]), 1e-6)
            self.assertGreater(j["donorWeightedVertexCount"], 0)

    def test_03_real_pabc_coverage_and_neutral_deformation(self):
        self.assertEqual(len(self.records), 423)
        observed = {r["boneIndex"] for r in self.records}
        self.assertEqual(self.report["pabc"]["matchedRecords"], 423)
        self.assertEqual(self.report["pabc"]["uncoveredBoneIndices"], sorted(set(range(447)) - observed))
        self.assertEqual(len(self.report["pabc"]["uncoveredBoneIndices"]), 24)
        for j in self.report["joints"]:
            matching = [r for r in self.records if r["boneIndex"] == j["pabIndex"]]
            self.assertEqual(len(matching), 1)
            neutral, axes = rig.neutral_bind(self.bones[j["pabIndex"]]["bind"], matching[0]["blocks"][0])
            self.assertEqual(list(neutral), j["pabc"]["neutralBind"])
            self.assertEqual(axes, j["pabc"]["pairedRowsReconciled"])
        candidate = self.report["neutralPresentation"]["steveCandidate"]
        donor = self.report["neutralPresentation"]["nativeDonor"]
        self.assertEqual(candidate["vertices"], 288)
        self.assertEqual(donor["vertices"], 13162)
        self.assertLess(candidate["maximumDisplacementMetres"], 2e-6)
        self.assertLess(donor["maximumDisplacementMetres"], .0004)
        self.assertLess(candidate["maximumIndependentVsCDMWMetres"], 1e-7)
        self.assertLess(donor["maximumIndependentVsCDMWMetres"], 1e-7)

    def test_04_left_right_forward_and_reflection_winding(self):
        contract = self.report["coordinateContract"]
        for row in contract["leftRightEvidence"]:
            self.assertGreater(row["nativeX"][0], 0)
            self.assertLess(row["nativeX"][1], 0)
            if "minecraftX" in row:
                self.assertGreater(row["minecraftX"][0], 0)
                self.assertLess(row["minecraftX"][1], 0)
        for row in contract["nativeForwardEvidence"]:
            self.assertLess(row["deltaMetres"][2], -.06)
        reflection = contract["minimalStaticOrientationCandidate"]["positionTransformRowMajor"]
        self.assertEqual(rig.transform((1, 2, 3), reflection), (1, 2, -3))
        self.assertEqual(rig.determinant3(reflection), -1)
        self.assertAlmostEqual(rig.transform((1, 2, 3), rig.axis_rotation(1, 180))[0], -1)
        self.assertFalse(contract["y180Alternative"]["preservesLeftRightX"])
        self.assertEqual(rig.signed_face_areas(self.parts), contract["windingExperiment"]["source"])
        self.assertEqual(rig.signed_face_areas(self.parts, True, False), contract["windingExperiment"]["zReflectionWithoutWindingFlip"])
        self.assertEqual(rig.signed_face_areas(self.parts, True, True), contract["windingExperiment"]["zReflectionWithWindingFlip"])
        self.assertGreater(contract["windingExperiment"]["zReflectionWithWindingFlip"]["minimumAreaDotNormal"], 0)
        self.assertLess(contract["windingExperiment"]["zReflectionWithoutWindingFlip"]["maximumAreaDotNormal"], 0)

    def test_05_pivot_constraint_and_static_refit_cost(self):
        by_name = {j["minecraftPart"]: j for j in self.report["joints"]}
        self.assertEqual(by_name["head"]["minecraftPivotMetres"], by_name["body"]["minecraftPivotMetres"])
        self.assertGreater(rig.distance(by_name["head"]["nativePivotMetres"], by_name["body"]["nativePivotMetres"]), .6)
        self.assertFalse(self.report["pivotConstraint"]["oneGlobalAffineCanMatchSixPivots"])
        for j in by_name.values():
            self.assertGreater(j["pivotDistanceMetres"], .23)
            for axis in j["syntheticModelAxisRotations"]:
                self.assertLess(axis["retargetMatrixMaximumError"], 1e-14)
                self.assertLess(axis["retargetVertexMaximumErrorMetres"], 1e-14)
        bounds = self.report["staticPerPartRefit"]["translatedAssembledBoundsMetres"]
        self.assertGreater(bounds["min"][1], .25)
        self.assertGreater(bounds["max"][1], 2.15)

    def test_06_actual_rigid_face_seams_and_synthetic_gap_difference(self):
        seams = self.report["rigidSeams"]
        self.assertTrue(seams["allCandidateVerticesRigidSingleBone"])
        self.assertEqual(len(seams["basePartContactFaces"]), 5)
        for seam in seams["basePartContactFaces"]:
            self.assertEqual(len(seam["contactFaceCornersMetres"]), 4)
            self.assertLess(seam["pabcNeutralMaximumSeparationMetres"], 1e-5)
            self.assertGreater(seam["staticRefitSeparationMetres"], .5)
        head_body = seams["basePartContactFaces"][0]
        self.assertEqual(head_body["parts"], ["head", "body"])
        self.assertGreater(head_body["syntheticEqualModelAxisRotations"][0]["nativeVsMinecraftSeparationVectorDifferenceMetres"], .3)

    def test_07_matrix_inverse_retarget_and_invalid_inputs(self):
        affine = rig.multiply(rig.axis_rotation(1, 23), rig.translation((.3, 1.7, -.2)))
        scaled = list(affine)
        scaled[0:4] = [v * 2 for v in scaled[0:4]]
        scaled[4:8] = [v * .5 for v in scaled[4:8]]
        self.assertLess(rig.error(rig.multiply(scaled, rig.inverse(scaled))), 1e-14)
        for bad in ([0] * 16, [math.nan] * 16, [1] * 15):
            with self.assertRaises(ValueError):
                rig.inverse(bad)
        # Full-frame retarget has zero neutral deformation and respects the
        # explicit pose formula for an arbitrary non-neutral synthetic pose.
        for j in self.report["joints"]:
            mb = rig.translation(j["minecraftPivotMetres"])
            nb = j["nativeGlobalBindRowMajor"]
            frame = rig.multiply(rig.inverse(mb), nb)
            native_pose = rig.multiply(nb, rig.rotation_about(j["nativePivotMetres"], 0, 17))
            native_delta = rig.multiply(rig.inverse(nb), native_pose)
            desired_delta = rig.multiply(rig.multiply(frame, native_delta), rig.inverse(frame))
            mc_pose = rig.multiply(native_pose, rig.inverse(frame))
            self.assertLess(rig.error(rig.multiply(rig.inverse(mb), mc_pose), desired_delta), 1e-13)
            self.assertLess(rig.error(rig.multiply(rig.inverse(mb), rig.multiply(nb, rig.inverse(frame)))), 1e-13)
            # Swapping the inverse bind alone already deforms the neutral mesh.
            self.assertGreater(rig.error(rig.multiply(rig.inverse(mb), nb)), .2)

    def test_08_binary_bounds_hash_and_duplicate_rejections(self):
        with self.assertRaises(ValueError):
            rig.parse_pab_records(self.raw_pab[:400])
        corrupted = bytearray(self.raw_pab)
        length = corrupted[26]
        struct.pack_into("<f", corrupted, 22 + 9 + length, math.nan)
        with self.assertRaises(ValueError):
            rig.parse_pab_records(corrupted)
        with self.assertRaises(ValueError):
            rig.parse_pabc_records(self.raw_pabc[:100], self.bones)
        duplicate = bytearray(self.raw_pabc[:20 + 423 * 196])
        duplicate.extend(struct.pack("<II", 0, 423))
        duplicate.extend(self.raw_pabc[20:20 + 423 * 196])
        duplicate[-1] ^= 1
        with self.assertRaises(ValueError):
            rig.parse_pabc_records(duplicate, self.bones)
        with self.assertRaises(ValueError):
            rig.read_fixed(rig.ROOT / "build/steve-1.21.1/steve.bin", "0" * 64, {})

    def test_09_output_alias_hardlink_tmp_and_changed_input_rejections(self):
        with tempfile.TemporaryDirectory(prefix="steve-rig-check-", dir=rig.ROOT / "build") as temporary:
            root = rig.native.output_directory(Path(temporary))
            source = root / "source.bin"
            source.write_bytes(b"owned input")
            snapshot = {source: source.read_bytes()}
            output = root / "out"
            output.mkdir()
            final = output / rig.REPORT_NAME
            os.link(source, final)
            with self.assertRaises(ValueError):
                rig.protect_output(output, snapshot)
            self.assertEqual(source.read_bytes(), b"owned input")
            final.unlink()
            tmp = output / (rig.REPORT_NAME + ".tmp")
            os.link(source, tmp)
            with self.assertRaises(ValueError):
                rig.publish(output, self.report, snapshot)
            tmp.unlink()
            source.write_bytes(b"changed input")
            with self.assertRaises(ValueError):
                rig.publish(output, self.report, snapshot)
            self.assertFalse(final.exists())
            self.assertFalse(tmp.exists())
        with self.assertRaises(ValueError):
            rig.protect_output(rig.ROOT / "artifacts/steve-rig-analysis", [])
        with self.assertRaises(ValueError):
            rig.protect_output(rig.ROOT / "build", [])

    def test_10_rebuild_real_inputs_deterministic(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for real deterministic reconstruction")
        with tempfile.TemporaryDirectory(prefix="steve-rig-rebuild-", dir=rig.ROOT / "build") as temporary:
            output = rig.native.output_directory(Path(temporary))
            result = subprocess.run([sys.executable, "-B", str(rig.ROOT / "tools/analyze_steve_rig.py"),
                                     "--output", str(output)], cwd=rig.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / rig.REPORT_NAME).read_bytes(), self.report_bytes)
            self.assertEqual((output / "steve-rig-analysis.md").read_bytes(), (self.output / "steve-rig-analysis.md").read_bytes())
            for path, digest in self.report["inputs"].items():
                self.assertEqual(rig.native.file_hash(rig.ROOT / path), digest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=rig.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    RigChecks.output, RigChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RigChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
