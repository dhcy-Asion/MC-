"""Checks for the frozen real-Player-state six-joint official model replay.

Default is pure admission. --rebuild evaluates one independent offline JVM.
No server, production game/process/API, renderer or future action is exercised.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import build_steve_player_pose as replay


class StevePlayerPoseChecks(unittest.TestCase):
    package = replay.DEFAULT_OUTPUT
    source = replay.SOURCE_DIRECTORY
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=replay.ROOT / "build", prefix="steve-player-pose-check-")
        cls.root = replay.assets.output_directory(Path(cls.temporary.name))
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.report, cls.poses, cls.snapshot = replay.load(cls.package)
        cls.player = replay.strict_json(cls.snapshot[(cls.source / "player-tick-fixture.json").resolve()])
        cls.runner = replay.strict_json(cls.snapshot[(cls.source / "runner-result.json").resolve()])
        cls.preserved = {relative: cls.snapshot[(replay.ROOT / relative).resolve()] for relative in replay.PRESERVED_PINS}
        cls.addClassCleanup(cls.preserved_unchanged)

    @classmethod
    def preserved_unchanged(cls):
        for relative, raw in cls.preserved.items():
            if replay.input_bytes(replay.ROOT / relative) != raw or replay.digest(raw) != replay.PRESERVED_PINS[relative]:
                raise AssertionError("Existing oracle/tool changed: " + relative)

    def copied(self, suffix=""):
        target = self.root / (self._testMethodName + suffix)
        shutil.copytree(self.package, target)
        return target

    def test_01_real_capture_sources_and_complete_snapshot_are_pinned(self):
        replay.validate_player_report(self.player)
        replay.validate_runner(self.runner)
        self.assertEqual(self.report["sources"]["capture"]["runTicket"], replay.TICKET)
        self.assertEqual(self.report["sources"]["officialClientOracle"]["client"]["sha256"], replay.action.CLIENT_SHA256)
        for name, pin in replay.SOURCE_FILE_PINS.items():
            self.assertEqual(replay.digest(self.snapshot[(self.source / name).resolve()]), pin)
        for relative, pin in replay.PRODUCER_PINS.items():
            self.assertEqual(replay.digest(self.snapshot[(replay.ROOT / relative).resolve()]), pin)
        for name in (replay.REPORT_NAME, "poses.json", replay.CLASS_FILE):
            self.assertEqual(self.snapshot[(self.package / name).resolve()], (self.package / name).read_bytes())
        replay.verify_snapshot(self.snapshot)
        self.assertTrue(all(isinstance(path, Path) and path.is_absolute() for path in self.snapshot))
        self.assertEqual(len(self.player["warmup"]), 11)
        self.assertEqual(self.player["worldTickEntityCalls"], 43)
        self.assertEqual(self.player["playerTickCalls"], 43)

    def test_02_ninety_six_samples_use_actual_after_getters_and_natural_age(self):
        replay.validate_poses(self.poses, self.player)
        self.assertEqual(len(self.poses["samples"]), 96)
        self.assertEqual(self.poses["officialMathHelperCalls"], 384)
        for i, sample in enumerate(self.poses["samples"]):
            state = self.player["frames"][i // 3]["after"]
            point = state["interpolation"][i % 3]
            self.assertEqual(sample["inputs"]["rawFloatBits"]["handSwingProgress"], point["handSwingProgress"]["rawBits"])
            self.assertIs(sample["inputs"]["modelSneaking"], state["isInSneakingPose"])
            self.assertEqual(sample["sourceAge"], state["age"])
            self.assertEqual(sample["sourceAge"], 12 + i // 3)
            self.assertEqual(sample["fixtureStateBefore"]["pose"], "STANDING")
            self.assertFalse(sample["fixtureStateBefore"]["isInSneakingPose"])
            self.assertEqual(sample["fixtureStateBefore"], sample["fixtureStateAfter"])
            self.assertEqual(sample["modelStateBefore"], sample["modelStateAfter"])
            crouch = sample["sourceProfile"].startswith("crouching_")
            self.assertAlmostEqual(sample["parts"]["body"]["rawModelPart"]["pitch"], 0.5 if crouch else 0)
            self.assertAlmostEqual(sample["parts"]["head"]["rawModelPart"]["pivotY"], 4.2 if crouch else 0, places=6)
        self.assertTrue(any(frame["after"]["velocity"]["y"] != 0 for frame in self.player["frames"]))
        self.assertFalse(self.report["integration"]["rendererExecuted"])
        self.assertFalse(self.report["integration"]["nativeApplied"])
        self.assertTrue(self.report["integration"]["officialModelReplayedFromPlayerState"])

    def test_03_one_independent_official_jvm_rebuild_is_byte_identical(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for one independent official JVM")
        target = self.root / "independent-official-jvm"
        replay.build(target, self.source)
        for name in ("poses.json", replay.CLASS_FILE, replay.REPORT_NAME):
            self.assertEqual((target / name).read_bytes(), (self.package / name).read_bytes(), name)

    def test_04_source_entry_phase_ticks_counts_and_runner_failure_refuse(self):
        def mutate_fixture(change):
            value = copy.deepcopy(self.player); change(value)
            with self.assertRaises(ValueError):
                replay.validate_player_report(value)
        changes = [
            lambda p: p.update(result="failure"),
            lambda p: p.update(runTicket="00000000-0000-0000-0000-000000000000"),
            lambda p: p["scope"].update(worldTickEntityCalled=False),
            lambda p: p["scope"].update(twentyHzLifecycleVerified=True),
            lambda p: p.update(worldTickEntityCalls=42),
            lambda p: p["frames"][1].update(serverTick=p["frames"][0]["serverTick"]),
            lambda p: p["frames"][0].update(entryPointOrder="playerTick before world.tickEntity"),
            lambda p: p["frames"][0]["afterWorldTickEntity"].update(age=p["frames"][0]["before"]["age"]),
            lambda p: p["frames"][0].update(after=copy.deepcopy(p["frames"][0]["before"])),
            lambda p: p["frames"][0].update(profile="crouching_main"),
            lambda p: p.update(frames=p["frames"][:-1]),
        ]
        for change in changes:
            with self.subTest(change=change): mutate_fixture(change)
        for name, value in (("failure", "failure"), ("normalConsoleShutdown", False), ("ownedProcessExitCode", 1),
                            ("forcedOwnedPidStop", True), ("production8766Or8765Requested", True), ("nativeApplied", True)):
            runner = copy.deepcopy(self.runner); runner[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError): replay.validate_runner(runner)
        runner = copy.deepcopy(self.runner); runner["inputs"]["sourceSha256"]["unknown/source"] = "0" * 64
        with self.assertRaises(ValueError): replay.validate_runner(runner)
        runner = copy.deepcopy(self.runner); runner["productionDirectoriesUnchanged"]["minecraft/build"] = False
        with self.assertRaises(ValueError): replay.validate_runner(runner)

    def test_05_actual_floatbits_delta_types_and_scope_refuse(self):
        for change in (
            lambda s: s.update(mainArm="LEFT"), lambda s: s.update(preferredHand="OFF_HAND"),
            lambda s: s.update(usingItem=True), lambda s: s.update(riding=True),
            lambda s: s.update(isInSneakingPose=True), lambda s: s.update(fallFlyingTicks=5),
            lambda s: s["interpolation"][0]["handSwingProgress"].update(value=0.5),
            lambda s: s["interpolation"][0]["handSwingProgress"].update(rawBits=True),
            lambda s: s["interpolation"][0]["limbSpeed"].update(value=0.5, rawBits=1056964608),
            lambda s: s.update(interpolation=list(reversed(s["interpolation"]))),
            lambda s: s.update(age=True), lambda s: s.update(unknown=True),
        ):
            state = copy.deepcopy(self.player["frames"][0]["after"]); change(state)
            with self.subTest(change=change), self.assertRaises(ValueError): replay.validate_state(state, "standing_main")
        self.assertEqual(replay.float_record({"value": -0.0, "rawBits": -(1 << 31)}), -0.0)
        with self.assertRaises(ValueError): replay.float_record({"value": 0.0, "rawBits": -(1 << 31)})
        with self.assertRaises(ValueError): replay.strict_json(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError): replay.strict_json(b'{"x":NaN}')

    def test_06_source_rawpins_and_final_snapshot_races_refuse(self):
        original = replay.input_bytes
        for relative in replay.SOURCE_FILE_PINS:
            target = (self.source / relative).resolve()
            def corrupt(path, *args, _target=target, **kwargs):
                raw = original(path, *args, **kwargs)
                return raw + b" " if Path(path).resolve() == _target else raw
            with self.subTest(pin=relative), mock.patch.object(replay, "input_bytes", side_effect=corrupt), mock.patch.object(replay.subprocess, "run") as invoked:
                with self.assertRaises(ValueError): replay.evaluate(self.source)
                invoked.assert_not_called()
        original_verify_read = replay.action.old.input_bytes
        for target in ((self.source / "player-tick-fixture.json").resolve(), (self.source / "runner-result.json").resolve(),
                       replay.JAVA_SOURCE.resolve(), (replay.ROOT / replay.context.NAMED_JAR_RELATIVE).resolve()):
            def changed(path, *args, _target=target, **kwargs):
                raw = original_verify_read(path, *args, **kwargs)
                return raw + b" " if Path(path).resolve() == _target else raw
            with self.subTest(race=target), mock.patch.object(replay.action.old, "input_bytes", side_effect=changed), mock.patch.object(replay.subprocess, "run") as invoked:
                with self.assertRaises(ValueError): replay.evaluate(self.source)
                invoked.assert_not_called()
        with self.assertRaises(ValueError): replay.merge_snapshot({self.source: b"one"}, {self.source: b"two"})

    def test_07_pose_class_and_complete_report_tamper_refuse_even_with_new_hashes(self):
        for kind in ("pose", "class", "report"):
            target = self.copied("-" + kind)
            manifest = replay.strict_json((target / replay.REPORT_NAME).read_bytes())
            if kind == "pose":
                poses = replay.strict_json((target / "poses.json").read_bytes())
                poses["samples"][0]["parts"]["head"]["rawModelPart"]["pitch"] = 0.1
                raw = replay.report_bytes(poses); (target / "poses.json").write_bytes(raw)
                manifest["files"]["poses.json"] = replay.digest(raw)
            elif kind == "class":
                raw = (target / replay.CLASS_FILE).read_bytes() + b"\0"
                (target / replay.CLASS_FILE).write_bytes(raw); manifest["files"][replay.CLASS_FILE] = replay.digest(raw)
            else:
                manifest["integration"]["rendererExecuted"] = True; manifest["unknown"] = True
            (target / replay.REPORT_NAME).write_bytes(replay.report_bytes(manifest))
            with self.subTest(kind=kind), self.assertRaises(ValueError): replay.load(target)
        poses = copy.deepcopy(self.poses)
        poses["samples"][0]["sourceDeltaIndex"] = 1
        with self.assertRaises(ValueError): replay.validate_poses(poses, self.player)

    def test_08_protected_output_early_refusal_and_pure_load_do_not_launch(self):
        for target in (self.package, replay.DEFAULT_OUTPUT / "new-child", replay.SOURCE_DIRECTORY / "new-child",
                       replay.ROOT / "runtime", replay.ROOT / "tools", replay.action.DEFAULT_OUTPUT / "new-child",
                       replay.action.old.DEFAULT_OUTPUT, replay.ROOT / "build", replay.ROOT / "minecraft"):
            with self.subTest(output=target), mock.patch.object(replay, "evaluate") as invoked:
                with self.assertRaises(ValueError): replay.build(target, self.source)
                invoked.assert_not_called()
        with mock.patch.object(replay.subprocess, "run") as invoked:
            with self.assertRaises(ValueError): replay.evaluate(self.root / "arbitrary-fresh-capture")
            invoked.assert_not_called()
            report, poses, snapshot = replay.load(self.package)
            self.assertEqual(report, self.report); self.assertEqual(poses, self.poses)
            replay.verify_snapshot(snapshot); invoked.assert_not_called()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=StevePlayerPoseChecks.package)
    parser.add_argument("--source", type=Path, default=StevePlayerPoseChecks.source, help="Only the frozen successful Player capture")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    StevePlayerPoseChecks.package = replay.assets.output_directory(args.package)
    StevePlayerPoseChecks.source = replay.input_path(args.source)
    replay.require(StevePlayerPoseChecks.source == replay.SOURCE_DIRECTORY.resolve(), "Checker requires the fixed reviewed capture")
    StevePlayerPoseChecks.rebuild = args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StevePlayerPoseChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
