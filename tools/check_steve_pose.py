"""Check the real, limited offline MC pose oracle; never access native gameplay."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import build_steve_pose as pose


class StevePoseChecks(unittest.TestCase):
    package = pose.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=pose.ROOT / "build", prefix="steve-pose-check-")
        cls.root = pose.assets.output_directory(Path(cls.temporary.name))
        cls.addClassCleanup(cls.temporary.cleanup)
        if cls.rebuild:
            cls.package = cls.root / "official-baseline"
            pose.build(cls.package)
        cls.report, cls.poses, cls.snapshot = pose.load(cls.package)

    def copied_package(self):
        target = self.root / self._testMethodName
        shutil.copytree(self.package, target)
        return target

    def test_01_authoritative_client_classes_and_external_classpath_are_fixed(self):
        sources = self.report["sources"]
        self.assertEqual(sources["client"]["sha256"], pose.CLIENT_SHA256)
        self.assertEqual(sources["algorithmClassSha256"], pose.CLASS_PINS)
        self.assertTrue(sources["allMinecraftClassesPinnedByClientSha256"])
        self.assertGreater(len(sources["externalClasspath"]), 0)
        for library in sources["externalClasspath"]:
            raw = self.snapshot[Path(library["path"])]
            self.assertEqual(pose.digest(raw, "sha1"), library["sha1"])
            self.assertEqual(pose.digest(raw), library["sha256"])
        pose.verify_snapshot(self.snapshot)

    def test_02_real_methods_and_non_player_fixture_are_explicit(self):
        self.assertEqual(self.poses["fixtureType"], "ArmorStandEntity")
        self.assertIs(self.poses["fixtureIsPlayer"], False)
        self.assertIs(self.poses["worldNull"], True)
        self.assertIs(self.poses["entityTicked"], False)
        self.assertEqual(self.poses["fixtureState"], pose.FIXTURE_STATE)
        self.assertEqual(self.poses["animateModelCalls"], 123)
        self.assertEqual(self.poses["setAnglesCalls"], 123)
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertEqual(self.report["files"]["poses.json"], pose.POSE_SHA256)
        self.assertEqual(self.report["files"][pose.CLASS_FILE], pose.HELPER_CLASS_SHA256)

    def test_03_fresh_official_execution_is_byte_deterministic(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a second independent JVM execution")
        rebuilt = self.root / "independent-rebuild"
        pose.build(rebuilt)
        for relative in ("poses.json", pose.CLASS_FILE, pose.REPORT_NAME):
            self.assertEqual((rebuilt / relative).read_bytes(), (self.package / relative).read_bytes(), relative)

    def test_04_complete_cycle_order_inputs_and_phase_symmetry(self):
        pose.validate_poses(self.poses)
        walk = self.poses["profiles"]["walk"]
        self.assertEqual([frame["tick"] for frame in walk], list(range(41)))
        self.assertEqual(walk[0]["inputs"]["phaseRadians"], 0)
        self.assertAlmostEqual(walk[-1]["inputs"]["phaseRadians"], 2 * pose.math.pi, places=6)
        right = [frame["parts"]["right_leg"]["rawModelPart"]["pitch"] for frame in walk]
        left = [frame["parts"]["left_leg"]["rawModelPart"]["pitch"] for frame in walk]
        self.assertGreater(max(right), .8)
        self.assertLess(min(right), -.8)
        for a, b in zip(right, left):
            self.assertAlmostEqual(a, -b, delta=2e-4)
        self.assertAlmostEqual(right[0], right[-1], places=6)
        self.assertAlmostEqual(left[0], left[-1], places=6)
        # Official age-driven idle bob remains explicit and is not fabricated
        # into a 40-tick closed loop with the locomotion phase.
        self.assertNotEqual(walk[0]["parts"]["right_arm"], walk[-1]["parts"]["right_arm"])

    def test_05_look_changes_only_head_and_trs_matches_raw_fields(self):
        standing, look = (self.poses["profiles"][name] for name in ("standing", "look"))
        for base, turned in zip(standing, look):
            for name in pose.PARTS:
                if name != "head":
                    self.assertEqual(base["parts"][name], turned["parts"][name])
            head = turned["parts"]["head"]["rawModelPart"]
            self.assertAlmostEqual(head["yaw"], pose.math.radians(30), places=6)
            self.assertAlmostEqual(head["pitch"], pose.math.radians(15), places=6)
            for item in turned["parts"].values():
                raw = item["rawModelPart"]
                expected = pose.converted_quaternion(raw["pitch"], raw["yaw"], raw["roll"])
                for actual, value in zip(item["rotationQuaternionXYZW"], expected):
                    self.assertAlmostEqual(actual, value, delta=4e-7)

    def test_06_state_inputs_float_bits_and_trs_tampering_are_rejected(self):
        changes = ("fixture", "input", "missing-endpoint", "float-bits", "translation", "quaternion", "complete-claim")
        for change in changes:
            value = copy.deepcopy(self.poses)
            frame = value["profiles"]["walk"][20]
            if change == "fixture":
                frame["fixtureStateAfter"]["usingItem"] = True
            elif change == "input":
                frame["inputs"]["limbDistance"] = .8
            elif change == "missing-endpoint":
                value["profiles"]["walk"].pop()
            elif change == "float-bits":
                frame["parts"]["left_leg"]["rawFloatBits"][3] ^= 1
            elif change == "translation":
                frame["parts"]["head"]["translationMetres"][0] += .1
            elif change == "quaternion":
                frame["parts"]["head"]["rotationQuaternionXYZW"] = [1., 0., 0., 0.]
            else:
                value["animationSystemComplete"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                pose.validate_poses(value)

    def test_07_updated_file_hashes_cannot_admit_different_oracle_or_helper(self):
        package = self.copied_package()
        report_path = package / pose.REPORT_NAME
        original = json.loads(report_path.read_bytes())
        for relative in ("poses.json", pose.CLASS_FILE):
            path = package / relative
            raw = path.read_bytes()
            changed = raw + b" " if relative == "poses.json" else raw[:-1] + bytes([raw[-1] ^ 1])
            path.write_bytes(changed)
            report = copy.deepcopy(original)
            report["files"][relative] = pose.digest(changed)
            report_path.write_bytes(pose.report_bytes(report))
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                pose.load(package)
            path.write_bytes(raw)
        report_path.write_bytes(pose.report_bytes(original))
        pose.load(package)

    def test_08_source_or_manifest_relabelling_is_rejected(self):
        package = self.copied_package()
        path = package / pose.REPORT_NAME
        original = json.loads(path.read_bytes())
        for change in ("class-pin", "library-pin", "source-pin", "unknown", "complete"):
            report = copy.deepcopy(original)
            if change == "class-pin":
                report["sources"]["algorithmClassSha256"]["fvx.class"] = "0" * 64
            elif change == "library-pin":
                report["sources"]["externalClasspath"][0]["sha256"] = "0" * 64
            elif change == "source-pin":
                report["sources"]["helperSource"]["sha256"] = "0" * 64
            elif change == "unknown":
                report["unreviewedState"] = True
            else:
                report["integration"]["animationSystemComplete"] = True
            path.write_bytes(pose.report_bytes(report))
            with self.subTest(change=change), self.assertRaises(ValueError):
                pose.load(package)

    def test_09_bad_client_or_output_is_refused_before_java(self):
        fake = self.root / "not-official-client.jar"
        fake.write_bytes(b"Not the pinned MC client")
        with mock.patch.object(pose.subprocess, "run") as executed:
            with self.assertRaises(ValueError):
                pose.build(self.root / "bad-client-output", client=fake)
            executed.assert_not_called()
        self.assertFalse((self.root / "bad-client-output").exists())
        for output in (self.package, pose.DEFAULT_OUTPUT / "unused-child", pose.assets.DEFAULT_OUTPUT / "unused-child", pose.ROOT / "build"):
            with self.subTest(output=output), mock.patch.object(pose, "sources") as opened:
                with self.assertRaises(ValueError):
                    pose.build(output)
                opened.assert_not_called()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=pose.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    StevePoseChecks.package, StevePoseChecks.rebuild = args.package, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StevePoseChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
