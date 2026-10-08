"""Core checks for actual official crouch/MAIN/OFF model-input samples.

Only owned build fixtures and independent offline JVMs are used. No World,
Player, renderer, entity tick, native process, installation or background task.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import build_steve_action_pose as action


class SteveActionPoseChecks(unittest.TestCase):
    package = action.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=action.ROOT / "build", prefix="steve-action-pose-check-")
        cls.root = action.assets.output_directory(Path(cls.temporary.name))
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.legacy_before = {relative: action.input_bytes(action.ROOT / relative) for relative in action.LEGACY_PINS}
        if cls.rebuild:
            cls.package = cls.root / "first-independent-jvm"
            action.build(cls.package)
        cls.report, cls.poses, cls.snapshot = action.load(cls.package)
        cls.original_standing = json.loads(cls.legacy_before["build/steve-pose-1.21.1/poses.json"])["profiles"]["standing"][0]["parts"]
        cls.addClassCleanup(cls.assert_legacy_preserved)

    @classmethod
    def assert_legacy_preserved(cls):
        for relative, raw in cls.legacy_before.items():
            if action.input_bytes(action.ROOT / relative) != raw or action.digest(raw) != action.LEGACY_PINS[relative]:
                raise AssertionError("Original tools/canonical changed: " + relative)

    def copied(self):
        destination = self.root / self._testMethodName
        shutil.copytree(self.package, destination)
        return destination

    def test_01_actual_client_classpath_mapping_and_old_oracle_are_pinned(self):
        sources = self.report["sources"]
        self.assertEqual(sources["client"]["sha256"], action.CLIENT_SHA256)
        self.assertEqual(sources["algorithmClassSha256"], action.CLASS_PINS)
        self.assertEqual(len(action.CLASS_PINS), 29)
        self.assertEqual(sources["officialMappings"]["sha1"], action.MAPPINGS_SHA1)
        self.assertIs(sources["matchesPreservedOracleDependencySha256"], True)
        self.assertEqual(len(sources["externalClasspath"]), 46)
        for item in sources["externalClasspath"]:
            raw = self.snapshot[Path(item["path"])]
            self.assertEqual(action.digest(raw, "sha1"), item["sha1"])
            self.assertEqual(action.digest(raw), item["sha256"])
        for relative, pin in action.LEGACY_PINS.items():
            self.assertEqual(action.digest(self.snapshot[(action.ROOT / relative).resolve()]), pin)
            self.assertEqual(sources["legacyPreserved"][relative]["sha256"], pin)
        action.verify_snapshot(self.snapshot)

    def test_02_model_and_real_fixture_states_and_world_failure_are_separate(self):
        action.validate_poses(self.poses)
        self.assertEqual(self.poses["setAnglesCalls"], 43)
        self.assertEqual(self.poses["animateModelCalls"], 43)
        self.assertEqual(self.poses["swingHandCalls"], 43)
        self.assertEqual(self.poses["preferredArmGetterCalls"], 86)
        self.assertEqual(self.poses["preconditions"], action.PRECONDITIONS)
        self.assertFalse(self.poses["preconditions"]["setCrouchPoseAccepted"])
        self.assertEqual(self.poses["preconditions"]["setCrouchPoseOfficialStack"][0], "bsr.i_:3064")
        for frames in self.poses["profiles"].values():
            for frame in frames:
                entity = frame["fixtureStateBefore"]
                self.assertEqual(entity, frame["fixtureStateAfter"])
                self.assertEqual(entity["pose"], "STANDING")
                self.assertIs(entity["isInSneakingPose"], False)
                self.assertIs(entity["isSneaking"], False)
                self.assertEqual(entity["mainArm"], "RIGHT")
                self.assertEqual(entity["activeHand"], "MAIN_HAND")
                self.assertEqual(entity["entitySwingTicks"], -1)
                self.assertEqual(entity["entityHandSwingProgress"], 0)
                self.assertEqual(frame["modelStateBefore"], frame["modelStateAfter"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertIs(self.poses["progressIsTickCycle"], False)
        self.assertIs(self.poses["leftMainHandPlayerCovered"], False)

    def test_03_second_actual_jvm_is_byte_identical(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a second independent official JVM")
        target = self.root / "second-independent-jvm"
        action.build(target)
        for relative in ("poses.json", action.CLASS_FILE, action.REPORT_NAME):
            self.assertEqual((target / relative).read_bytes(), (self.package / relative).read_bytes(), relative)
        self.assert_legacy_preserved()

    def test_04_crouch_is_the_official_model_branch_against_existing_standing(self):
        frame, = self.poses["profiles"]["model_crouch"]
        self.assertIs(frame["modelStateBefore"]["sneaking"], True)
        self.assertIs(frame["fixtureStateBefore"]["isInSneakingPose"], False)
        expected_y = {"head": 4.2, "body": 3.2, "right_arm": 5.2, "left_arm": 5.2, "right_leg": 12.2, "left_leg": 12.2}
        for name, y in expected_y.items():
            self.assertAlmostEqual(frame["parts"][name]["rawModelPart"]["pivotY"], y, places=6)
            self.assertNotEqual(frame["parts"][name], self.original_standing[name])
        self.assertEqual(frame["parts"]["body"]["rawModelPart"]["pitch"], 0.5)
        for arm in ("right_arm", "left_arm"):
            self.assertAlmostEqual(frame["parts"][arm]["rawModelPart"]["pitch"], 0.4, places=7)
        for leg in ("right_leg", "left_leg"):
            self.assertEqual(frame["parts"][leg]["rawModelPart"]["pivotZ"], 4)
        action.validate_parts(frame["parts"])

    def test_05_main_off_sweep_selects_right_left_with_official_asymmetry_preserved(self):
        main, off = (self.poses["profiles"][name] for name in action.PROFILES[1:])
        for frames, hand, arm in ((main, "MAIN_HAND", "RIGHT"), (off, "OFF_HAND", "LEFT")):
            self.assertEqual(len(frames), 21)
            self.assertEqual([frame["sampleIndex"] for frame in frames], list(range(21)))
            self.assertEqual(frames[0]["parts"], self.original_standing)
            for index, frame in enumerate(frames):
                self.assertEqual(action.f32(frame["inputs"]["handSwingProgress"]), action.f32(index / 20))
                self.assertEqual(frame["fixtureStateBefore"]["preferredHand"], hand)
                self.assertEqual(frame["fixtureStateBefore"]["activeHand"], "MAIN_HAND")
                self.assertEqual(frame["officialPreferredArmBefore"], arm)
                self.assertEqual(frame["officialPreferredArmAfter"], arm)
            self.assertEqual(frames[-1]["inputs"]["handSwingProgress"], 1)
        self.assertLess(min(frame["parts"]["right_arm"]["rawModelPart"]["pitch"] for frame in main), -1)
        self.assertLess(min(frame["parts"]["left_arm"]["rawModelPart"]["pitch"] for frame in off), -1)
        for right, left in zip(main, off):
            a, b = right["parts"], left["parts"]
            for name in ("head", "right_leg", "left_leg"):
                self.assertEqual(a[name], b[name])
                self.assertEqual(a[name], self.original_standing[name])
            yaw_a, yaw_b = (parts["body"]["rawModelPart"]["yaw"] for parts in (a, b))
            self.assertAlmostEqual(yaw_a, -yaw_b, delta=1e-7)
            self.assertAlmostEqual(a["right_arm"]["rawModelPart"]["yaw"], 3*yaw_a, delta=1e-7)
            self.assertAlmostEqual(b["left_arm"]["rawModelPart"]["yaw"], 3*yaw_b, delta=1e-7)
            # Official animateArms always adds body yaw to LEFT-arm pitch.
            # Preserve that real asymmetry instead of fabricating perfect mirrors.
            self.assertAlmostEqual(a["left_arm"]["rawModelPart"]["pitch"], yaw_a, delta=1e-7)
            self.assertEqual(b["right_arm"]["rawModelPart"]["pitch"], 0)
            self.assertAlmostEqual(b["left_arm"]["rawModelPart"]["pitch"]-a["right_arm"]["rawModelPart"]["pitch"], yaw_b, delta=2e-7)

    def test_06_state_hand_order_and_trs_tampering_refuse(self):
        for change in ("entity-pose", "main-arm", "active-hand", "preferred-hand", "model-crouch", "progress", "order", "bits", "translation", "quaternion", "tick-claim"):
            value = copy.deepcopy(self.poses)
            frame = value["profiles"]["right_off_hand_swing"][10]
            if change == "entity-pose": frame["fixtureStateAfter"]["isInSneakingPose"] = True
            elif change == "main-arm": frame["fixtureStateBefore"]["mainArm"] = "LEFT"
            elif change == "active-hand": frame["fixtureStateBefore"]["activeHand"] = "OFF_HAND"
            elif change == "preferred-hand": frame["fixtureStateBefore"]["preferredHand"] = "MAIN_HAND"
            elif change == "model-crouch": value["profiles"]["model_crouch"][0]["modelStateAfter"]["sneaking"] = False
            elif change == "progress": frame["inputs"]["handSwingProgress"] = 0.6
            elif change == "order": value["profiles"]["right_main_hand_swing"].reverse()
            elif change == "bits": frame["parts"]["left_arm"]["rawFloatBits"][3] ^= 1
            elif change == "translation": frame["parts"]["body"]["translationMetres"][1] += 0.1
            elif change == "quaternion": frame["parts"]["left_arm"]["rotationQuaternionXYZW"] = [1.0, 0.0, 0.0, 0.0]
            else: value["progressIsTickCycle"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                action.validate_poses(value)

    def test_07_new_oracle_and_helper_refuse_updated_report_hashes(self):
        package = self.copied()
        report_path = package / action.REPORT_NAME
        original = json.loads(report_path.read_bytes())
        for relative in ("poses.json", action.CLASS_FILE):
            path = package / relative
            raw = path.read_bytes()
            changed = raw + b" " if relative == "poses.json" else raw[:-1] + bytes([raw[-1] ^ 1])
            path.write_bytes(changed)
            altered = copy.deepcopy(original)
            altered["files"][relative] = action.digest(changed)
            report_path.write_bytes(action.report_bytes(altered))
            with self.subTest(relative=relative), self.assertRaises(ValueError): action.load(package)
            path.write_bytes(raw)
        report_path.write_bytes(action.report_bytes(original))
        action.load(package)

    def test_08_source_field_evidence_and_complete_claims_refuse_relabelling(self):
        package = self.copied()
        path = package / action.REPORT_NAME
        original = json.loads(path.read_bytes())
        for change in ("class", "classpath", "legacy", "mapping", "renderer", "complete", "unknown"):
            report = copy.deepcopy(original)
            if change == "class": report["sources"]["algorithmClassSha256"]["fvx.class"] = "0"*64
            elif change == "classpath": report["sources"]["externalClasspath"][0]["sha256"] = "0"*64
            elif change == "legacy": report["sources"]["legacyPreserved"]["tools/StevePoseDump.java"]["sha256"] = "0"*64
            elif change == "mapping": report["sources"]["officialMappings"]["sha1"] = "0"*40
            elif change == "renderer": report["fieldEvidence"]["model.sneaking"]["rendererExecuted"] = True
            elif change == "complete": report["integration"]["animationSystemComplete"] = True
            else: report["unreviewedProfile"] = True
            path.write_bytes(action.report_bytes(report))
            with self.subTest(change=change), self.assertRaises(ValueError): action.load(package)
        self.assert_legacy_preserved()

    def test_09_protected_outputs_and_wrong_client_refuse_before_jvm(self):
        for output in (self.package, action.DEFAULT_OUTPUT / "unused-child", action.old.DEFAULT_OUTPUT,
                       action.old.DEFAULT_OUTPUT / "unused-child", action.assets.DEFAULT_OUTPUT / "unused-child", action.ROOT / "build"):
            with self.subTest(output=output), mock.patch.object(action, "sources") as opened:
                with self.assertRaises(ValueError): action.build(output)
                opened.assert_not_called()
        fake = self.root / "wrong-client.jar"
        fake.write_bytes(b"Not the fixed official client")
        output = self.root / "bad-client-output"
        with mock.patch.object(action.subprocess, "run") as invoked:
            with self.assertRaises(ValueError): action.build(output, client=fake)
            invoked.assert_not_called()
        self.assertFalse(output.exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=SteveActionPoseChecks.package)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    SteveActionPoseChecks.package, SteveActionPoseChecks.rebuild = args.package, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SteveActionPoseChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
