"""Isolated positive/negative contract checks for the unused pure selector.

All evidence identities below are synthetic fixtures, not production approvals.
No game, assets, reports, installed packages or HTTP services are read/written.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import native_block_models as models


class NativeModelChecks(unittest.TestCase):
    def setUp(self):
        self.identity = models.AssetIdentity("a"*64, "b"*64)
        self.admissions = tuple(models.ModelAdmission(self.identity, models.state_key("minecraft:oak_log", {"axis": axis}),
            models.OAK_PREFABS[axis], "c"*64, "d"*64) for axis in "xyz")
        self.profile = models.NativeProfile(self.identity, self.admissions)
        self.session = models.SessionVerification(self.identity, "synthetic-session-a", "e"*64,
                                                   frozenset(models.OAK_PREFABS.values()))

    def select(self, block="minecraft:oak_log", properties=None, **changes):
        args = {"mode": "native", "profile": self.profile, "session": self.session,
                "current_session_token": "synthetic-session-a", **changes}
        return models.select_model(block, {"axis": "y"} if properties is None else properties, **args)

    def test_01_explicit_blue_supports_all_six_without_native_claims(self):
        for block in sorted(models.BASELINE_BLOCKS):
            for properties in ({"axis": a} for a in "xyz") if block.endswith("oak_log") else ({},):
                choice = models.select_model(block, properties)
                self.assertEqual(choice.mode, "blue")
                self.assertEqual(choice.prefab, models.BLUE_PREFAB)
                self.assertIsNone(choice.identity)
                self.assertEqual(choice.state, models.state_key(block, properties))
        # Having a profile in memory never enables native mode implicitly.
        choice = self.select(mode="blue")
        self.assertEqual(choice.prefab, models.BLUE_PREFAB)
        self.assertIsNone(choice.identity)

    def test_02_exact_three_axes_map_to_three_real_prefab_paths(self):
        choices = [self.select(properties={"axis": axis}) for axis in "xyz"]
        self.assertEqual([c.prefab for c in choices], [
            "/object/00_common/system/crimsonmc_oak_log_x.prefab",
            "/object/00_common/system/crimsonmc_oak_log_y.prefab",
            "/object/00_common/system/crimsonmc_oak_log_z.prefab"])
        self.assertTrue(all(c.mode == "native" and c.identity == self.identity for c in choices))

    def test_03_y_only_admission_does_not_enable_x_or_z(self):
        profile = models.NativeProfile(self.identity, (self.admissions[1],))
        self.assertEqual(self.select(profile=profile).prefab, models.OAK_PREFABS["y"])
        for axis in "xz":
            with self.subTest(axis=axis), self.assertRaisesRegex(models.ModelSelectionError, "exact block state"):
                self.select(properties={"axis": axis}, profile=profile)

    def test_04_native_requests_for_other_five_are_not_fake_textures(self):
        for block in models.BASELINE_BLOCKS - {"minecraft:oak_log"}:
            with self.subTest(block=block), self.assertRaisesRegex(models.ModelSelectionError, "No native asset"):
                self.select(block, {})
            with self.assertRaisesRegex(models.ModelSelectionError, "No native asset"):
                models.ModelAdmission(self.identity, models.state_key(block, {}), models.OAK_PREFABS["y"], "c"*64, "d"*64)

    def test_05_complete_properties_required_even_in_blue_mode(self):
        for props in ({}, {"axis":"q"}, {"axis":"Y"}, {"axis":True}, {"axis":"y","waterlogged":"false"}, None, [], "axis=y"):
            with self.subTest(properties=props), self.assertRaises(models.ModelSelectionError):
                models.select_model("minecraft:oak_log", props)
        for props in ({"axis":"y"}, {"unknown":"value"}, {False:"value"}):
            with self.assertRaises(models.ModelSelectionError):
                models.select_model("minecraft:dirt", props)
        for block in ("minecraft:air", "minecraft:oak_stairs", "oak_log", None, True):
            with self.assertRaises(models.ModelSelectionError):
                models.select_model(block, {})

    def test_06_candidate_and_package_identities_cannot_cross(self):
        for identity in (replace(self.identity, candidate_report_sha256="f"*64),
                         replace(self.identity, package_report_sha256="f"*64)):
            with self.assertRaisesRegex(models.ModelSelectionError, "Candidate/package"):
                self.select(session=replace(self.session, identity=identity))
            with self.assertRaisesRegex(models.ModelSelectionError, "different candidate/package"):
                models.NativeProfile(identity, self.admissions)

    def test_07_process_restart_requires_fresh_session_verification(self):
        with self.assertRaisesRegex(models.ModelSelectionError, "process-session changed"):
            self.select(current_session_token="synthetic-session-b")
        for token in (None, "", "contains space", 123, True, "x"*129):
            with self.assertRaises(models.ModelSelectionError):
                self.select(current_session_token=token)
        new_session = replace(self.session, session_token="synthetic-session-b")
        self.assertEqual(self.select(session=new_session, current_session_token="synthetic-session-b").mode, "native")

    def test_08_resource_read_scope_does_not_expand_from_one_axis(self):
        session = replace(self.session, resource_verified_prefabs=frozenset({models.OAK_PREFABS["y"]}))
        self.assertEqual(self.select(session=session).mode, "native")
        for axis in "xz":
            with self.assertRaisesRegex(models.ModelSelectionError, "resources were not verified"):
                self.select(properties={"axis":axis}, session=session)

    def test_09_missing_inputs_and_raw_report_booleans_are_rejected(self):
        for changes in ({"profile":None}, {"session":None}, {"profile":{"verified":True}},
                        {"session":{"success":True,"allReadAndMatched":True}}, {"mode":True}, {"mode":"auto"}):
            with self.subTest(changes=changes), self.assertRaises(models.ModelSelectionError):
                self.select(**changes)
        with self.assertRaises(models.ModelSelectionError):
            models.NativeProfile({"candidateReportSha256":"a"*64}, self.admissions)
        with self.assertRaises(models.ModelSelectionError):
            models.SessionVerification({"installed":True}, "session", "e"*64, frozenset(models.OAK_PREFABS.values()))

    def test_10_supported_exe_and_version_are_both_mandatory(self):
        for kwargs in ({"exe_sha256":"f"*64}, {"game_version":"1.0.0.9999"}, {"exe_sha256":None}):
            with self.assertRaisesRegex(models.ModelSelectionError, "supported game"):
                models.AssetIdentity("a"*64,"b"*64,**kwargs)
        for digest in ("", "A"*64, "a"*63, "a"*65, "g"*64, True, {}):
            with self.assertRaises(models.ModelSelectionError):
                models.AssetIdentity(digest, "b"*64)
            with self.assertRaises(models.ModelSelectionError):
                models.AssetIdentity("a"*64, digest)

    def test_11_admission_requires_both_evidence_hashes_and_exact_prefab(self):
        admission = self.admissions[1]
        for changes in ({"visual_evidence_sha256":""}, {"collision_evidence_sha256":True},
                        {"prefab":models.OAK_PREFABS["x"]}, {"prefab":models.BLUE_PREFAB},
                        {"prefab":"/character/arbitrary.prefab"}, {"prefab":"../oak_y.prefab"}):
            with self.assertRaises(models.ModelSelectionError):
                replace(admission, **changes)

    def test_12_profile_rejects_duplicate_or_mutable_admissions(self):
        for admissions in ((), list(self.admissions), (self.admissions[1],)*2, ({"verified":True},)):
            with self.assertRaises(models.ModelSelectionError):
                models.NativeProfile(self.identity, admissions)
        for state in (("minecraft:oak_log", (("axis","y"),("axis","y"))),
                      ("minecraft:oak_log", {"axis":"y"}), ["minecraft:oak_log",(("axis","y"),)]):
            with self.assertRaises(models.ModelSelectionError):
                replace(self.admissions[1], state=state)

    def test_13_session_rejects_unknown_mutable_or_empty_resource_scope(self):
        for prefabs in (frozenset(), set(models.OAK_PREFABS.values()), frozenset({models.BLUE_PREFAB}),
                        frozenset({"/object/foreign.prefab"})):
            with self.assertRaises(models.ModelSelectionError):
                replace(self.session, resource_verified_prefabs=prefabs)
        with self.assertRaises(models.ModelSelectionError):
            replace(self.session, resource_evidence_sha256=False)

    def test_14_choices_copy_state_and_profile_records_are_immutable(self):
        properties = {"axis":"y"}
        choice = self.select(properties=properties)
        properties["axis"] = "x"
        self.assertEqual(choice.state[1], (("axis","y"),))
        for obj,field,value in ((choice,"prefab","other"), (self.profile,"admissions",()),
                                (self.identity,"candidate_report_sha256","f"*64), (self.session,"session_token","other")):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj,field,value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
