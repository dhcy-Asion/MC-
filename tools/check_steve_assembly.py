"""Isolated fixed-data checks for the ten-resource Steve assembly; no game calls."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import prepare_steve_assembly as assembly
from check_steve_orientation import read_native_frame
from check_steve_current_rig import unit, dot
from check_steve_segmented import raw_skin

native, current, parts = assembly.native, assembly.current, assembly.parts
segmented, rig = assembly.segmented, assembly.rig


class AssemblyChecks(unittest.TestCase):
    output = assembly.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report, cls.files, cls.snapshot = assembly.load_candidate(cls.output / assembly.REPORT_NAME)
        cls.report_raw = (cls.output / assembly.REPORT_NAME).read_bytes()
        native.load_cdmw(native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
        cls.reports, cls.inputs, cls.sources_snapshot, _ = assembly.load_sources()
        cls.original = {key: cls.inputs["parts"]["resources/"+p] for key, p in parts.PAC_PATHS.items()}
        cls.pacs = {key: cls.files["resources/"+p] for key, p in parts.PAC_PATHS.items()}
        cls.donor, cls.pab = (cls.files["template/"+p] for p in (native.BODY, native.SKELETON))
        cls.body_pabc, cls.head_pabc = (cls.files["template/"+p] for p in (current.CURRENT_VARIATION, assembly.HEAD_VARIATION))
        cls.skeleton, cls.body_matrices, _ = current.neutral_matrices(cls.pab, cls.body_pabc)
        from cdmw.modding.mesh_parser import resolve_pac_bone_palette
        cls.palette = resolve_pac_bone_palette(cls.donor, cls.skeleton)

    def test_01_admission_is_pure_and_pins_ten_resources_and_all_templates(self):
        # A new interpreter proves successful admission does not even import
        # CDMW, rather than accidentally relying on this suite's loaded cache.
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
                "import prepare_steve_assembly as a;"
                "r,f,s=a.load_candidate(Path(sys.argv[1]));"
                "assert len(r['candidateResources'])==10 and len(f)==30;"
                "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.output / assembly.REPORT_NAME)],
                                cwd=native.ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.report["files"]), set(self.files))
        self.assertEqual(len(assembly.EXPECTED_PATHS), 10)
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        for row in self.report["candidateResources"]:
            self.assertEqual(native.sha256(self.files[row["localFile"]]), row["sha256"])
            self.assertEqual(native.sha256(self.files["template/"+row["templatePath"]]), row["templateSha256"])

    def test_02_four_lod_body_records_exact_combined_and_head_exact_original(self):
        combined = self.inputs["current"]["resources/"+current.PAC_PATH]
        levels = segmented.parse_lods(combined, self.donor)
        self.assertEqual([lod for lod, _ in levels], [0, 1, 2, 3])
        head = segmented.parse_lods(self.pacs["head"], self.donor)
        body = segmented.parse_lods(self.pacs["body"], self.donor)
        self.assertEqual(self.pacs["head"], self.original["head"])
        for (lod, mesh), (head_lod, h), (body_lod, b) in zip(levels, head, body):
            self.assertEqual((head_lod, body_lod), (lod, lod))
            self.assertEqual((h.total_vertices, h.total_faces, b.total_vertices, b.total_faces), (48, 24, 1008, 504))
            self.assertEqual((h.total_vertices+b.total_vertices, h.total_faces+b.total_faces), (1056, 528))
            for candidate, reference, payload, is_body in ((h.submeshes[0], mesh.submeshes[0], self.pacs["head"], False),
                                                          (b.submeshes[0], mesh.submeshes[1], self.pacs["body"], True)):
                for name in ("faces", "uvs", "bone_indices", "bone_weights", "name"):
                    self.assertEqual(getattr(candidate, name), getattr(reference, name))
                for a, c in zip(candidate.source_vertex_offsets, reference.source_vertex_offsets):
                    if is_body:
                        self.assertEqual(payload[a:a+40], combined[c:c+40])
                    else:
                        # The head differs in quantized positions/frame from
                        # combined body-rig compensation, but all UV/skin lanes
                        # and active draw correspondence are retained.
                        self.assertEqual(payload[a+8:a+16], combined[c+8:c+16])
                        self.assertEqual(payload[a+20:a+40], combined[c+20:c+40])

    def test_03_independent_byte_weight_body_neutral_position_and_frame_replay(self):
        maximum, normal_min, frame_min = 0., 1., 1.
        for (_, old), (_, new) in zip(segmented.parse_lods(self.original["body"], self.donor), segmented.parse_lods(self.pacs["body"], self.donor)):
            a, b = old.submeshes[0], new.submeshes[0]
            for target, point, offset, old_offset in zip(a.vertices, b.vertices, b.source_vertex_offsets, a.source_vertex_offsets):
                weights = raw_skin(self.pacs["body"], offset)
                matrix = tuple(sum(w*self.body_matrices[self.palette[s]][i] for s, w in weights.items()) for i in range(16))
                posed = tuple(sum(point[k]*matrix[k*4+c] for k in range(3))+matrix[12+c] for c in range(3))
                maximum = max(maximum, rig.distance(target, posed))
                inverse = rig.inverse(matrix)
                n, v, sign = read_native_frame(self.pacs["body"], offset)
                target_n, target_v, target_sign = read_native_frame(self.original["body"], old_offset)
                posed_n = unit(tuple(sum(n[k]*inverse[c*4+k] for k in range(3)) for c in range(3)))
                posed_v = unit(tuple(sum(v[k]*matrix[k*4+c] for k in range(3)) for c in range(3)))
                normal_min, frame_min = min(normal_min, dot(posed_n, unit(target_n))), min(frame_min, dot(posed_v, unit(target_v)))
                self.assertEqual(sign, target_sign)
        self.assertLess(maximum, .00003)
        self.assertAlmostEqual(maximum, self.report["bodyCompensation"]["afterNeutralMaximumTargetErrorMetres"], places=12)
        self.assertGreater(normal_min, .9995)
        self.assertGreater(frame_min, .9997)

    def test_04_head_pabc_missing_bone_fallback_and_body_merge_hypothesis_are_distinct(self):
        from cdmw.modding.skeleton_variation_parser import _neutral_variation_bind_matrix, _skin_matrices, _deform_positions
        skeleton, variation, independent, covered = assembly.head_matrices(self.pab, self.head_pabc)
        self.assertEqual(len(variation.records), 207)
        self.assertNotIn(93, covered)
        globals_ = [bone.bind_matrix for bone in skeleton.bones]
        for row in variation.records:
            globals_[row.bone_index] = _neutral_variation_bind_matrix(globals_[row.bone_index], row.matrix_blocks[0])
        matrices = _skin_matrices(skeleton.bones, globals_)
        self.assertEqual(len(matrices), 447)
        maximum, inherited = 0., 0.
        for _, mesh in segmented.parse_lods(self.pacs["head"], self.donor):
            part = mesh.submeshes[0]
            for offset in part.source_vertex_offsets:
                self.assertEqual(raw_skin(self.pacs["head"], offset), {8: 1.})
                self.assertEqual(self.palette[8], 93)
            fallback, other = _deform_positions(part, self.palette, matrices), _deform_positions(part, self.palette, self.body_matrices)
            maximum = max(maximum, max(rig.distance(p, q) for p, q in zip(part.vertices, fallback)))
            inherited = max(inherited, max(rig.distance(p, q) for p, q in zip(part.vertices, other)))
        self.assertLess(maximum, 3e-8)
        self.assertGreater(inherited, 7e-5)
        self.assertLess(inherited, 8e-5)
        self.assertAlmostEqual(maximum, self.report["correspondence"]["head"]["pabFallbackMaximumTargetErrorMetres"], places=12)
        self.assertAlmostEqual(inherited, self.report["correspondence"]["head"]["bodyNeutralInheritanceHypothesisMaximumTargetErrorMetres"], places=12)
        self.assertFalse(self.report["correspondence"]["head"]["nativeMergeSemanticsVerified"])
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            assembly.head_matrices(self.pab, self.body_pabc)
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            current.neutral_matrices(self.pab, self.head_pabc)

    def test_05_actual_selection_variations_and_scales_preserved_without_appearance_patch(self):
        context = {p: self.files["template/"+p] for p in assembly.CONTEXT_HASHES}
        result = assembly.selection_contract(context)
        self.assertEqual(result, self.report["selectionContext"])
        self.assertEqual(result["selections"]["body"]["skeletonVariation"], current.CURRENT_VARIATION)
        self.assertEqual(result["selections"]["head"]["skeletonVariation"], assembly.HEAD_VARIATION)
        self.assertEqual((result["bodyCharacterScale"], result["headScale"]), (1.02571, .92))
        self.assertFalse(result["scaleBakedOrCancelled"])
        self.assertFalse(result["engineScaleOrderOrPivotVerified"])
        self.assertNotIn(assembly.MESH_PARAM, assembly.EXPECTED_PATHS)
        self.assertNotIn(assembly.APPEARANCE, assembly.EXPECTED_PATHS)
        self.assertEqual(self.files["resources/"+assembly.private.DESCRIPTOR_PATH], self.files["template/"+current.CURRENT_DESCRIPTOR])
        wrong = dict(context)
        wrong[assembly.MESH_PARAM] = wrong[assembly.MESH_PARAM].replace(b'UseSkeletonVariation="True"', b'UseSkeletonVariation="False"', 1)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            assembly.selection_contract(wrong)

    def test_06_private_single_components_material_and_external_edges(self):
        result = assembly.dependency_audit(self.files)
        self.assertEqual(json.loads(json.dumps(result)), self.report["dependencies"])
        self.assertEqual(set(result["dds"]), set(assembly.material.TEXTURE_PATHS.values()))
        self.assertFalse(result["allExternalDependenciesResolved"])
        for kind, component in (("body", "CD_Nude"), ("head", "CD_Head")):
            row = result["parts"][kind]
            self.assertEqual((row["variants"], row["wrappers"]), (6, 18))
            self.assertEqual(row["prefab"]["component"]["name"], component)
            self.assertEqual(row["prefab"]["component"]["numbers"], [("_shrinkMaskDistance", "float", "cdcc4c3d")])
        self.assertEqual({r["role"] for r in result["externalReferences"]},
                         {"wrinkle", "skeleton", "bodyVariation", "headVariation", "animationConstraint", "ragdoll", "headBoneAnimationScript"})
        self.assertTrue(all(r["runtimeResolutionVerified"] is False for r in result["externalReferences"]))
        missing = dict(self.files)
        del missing["resources/"+next(iter(assembly.material.TEXTURE_PATHS.values()))]
        with self.assertRaises(KeyError):
            assembly.dependency_audit(missing)
        swapped = dict(self.files)
        spec = assembly.private.PARTS
        swapped["resources/"+spec["body"]["target"]] = self.files["resources/"+spec["head"]["target"]]
        with self.assertRaisesRegex(ValueError, "component"):
            assembly.dependency_audit(swapped)

    def test_07_payload_and_source_template_tampering_rejected(self):
        with tempfile.TemporaryDirectory(prefix="steve-assembly-tamper-", dir=native.ROOT / "build") as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(self.output, target)
            for relative in ("resources/"+parts.PAC_PATHS["body"], "template/"+assembly.HEAD_VARIATION, "provenance/current.json"):
                path = target / relative
                raw = path.read_bytes()
                path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    assembly.load_candidate(target / assembly.REPORT_NAME)
                path.write_bytes(raw)
            assembly.load_candidate(target / assembly.REPORT_NAME)

    def test_08_changed_report_is_rejected_even_if_only_success_flag_changed(self):
        with tempfile.TemporaryDirectory(prefix="steve-assembly-report-", dir=native.ROOT / "build") as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(self.output, target)
            raw = json.loads(self.report_raw)
            raw["integration"]["installed"] = True
            (target / assembly.REPORT_NAME).write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                assembly.load_candidate(target / assembly.REPORT_NAME)

    def test_09_strict_manifest_and_boolean_guards_independent_of_report_pin(self):
        edits = [lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
                 lambda r: r["candidateResources"][0].update(virtualPath="../foreign.dds"),
                 lambda r: r["candidateResources"][0].update(localFile="Resources/"+r["candidateResources"][0]["virtualPath"]),
                 lambda r: r["candidateResources"][0].update(templateSha256="0"*64),
                 lambda r: r["integration"].update(installed=0),
                 lambda r: r["files"].update({"../escape": "0"*64})]
        with tempfile.TemporaryDirectory(prefix="steve-assembly-manifest-", dir=native.ROOT / "build") as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(self.output, target)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                raw = json.dumps(report).encode()
                (target / assembly.REPORT_NAME).write_bytes(raw)
                with mock.patch.object(assembly, "REPORT_SHA256", native.sha256(raw)):
                    with self.assertRaises(ValueError):
                        assembly.load_candidate(target / assembly.REPORT_NAME)
        for bad in ("/absolute", "../escape", "a//b", "a/./b", "A/b", "a\\b", "C:/file", "a/../b"):
            with self.assertRaises(ValueError):
                assembly.relative_path(bad)

    def test_10_existing_output_and_overlap_rejected_before_any_input_or_game_read(self):
        with tempfile.TemporaryDirectory(prefix="steve-assembly-refuse-", dir=native.ROOT / "build") as temporary:
            output = Path(temporary)
            sentinel = output / "keep.txt"
            sentinel.write_bytes(b"preserve")
            with mock.patch.object(assembly, "load_sources") as load, mock.patch.object(assembly, "read_context") as read:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    assembly.prepare(native.ROOT / "build/unused-game", output, native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
                load.assert_not_called()
                read.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"preserve")
        with self.assertRaisesRegex(ValueError, "overlaps"):
            assembly.orientation.preflight(assembly.SOURCES["parts"][0].parent / "nested", [assembly.SOURCES["parts"][0].parent])

    def test_11_source_changed_during_real_computation_aborts_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="steve-assembly-race-", dir=native.ROOT / "build") as temporary:
            root = Path(temporary)
            sources = {}
            for key, (path, digest) in assembly.SOURCES.items():
                shutil.copytree(path.parent, root / key)
                sources[key] = (root / key / path.name, digest)
            changed_path = root / "parts/resources" / parts.PAC_PATHS["body"]
            compare = assembly.compare_parts
            def change_after_compare(*args):
                result = compare(*args)
                raw = changed_path.read_bytes()
                changed_path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                return result
            context = {p: self.files["template/"+p] for p in assembly.CONTEXT_HASHES}
            output = root / "candidate"
            with mock.patch.object(assembly, "SOURCES", sources), mock.patch.object(assembly, "read_context", return_value=context), \
                    mock.patch.object(native, "load_cdmw", return_value=self.report["cdmw"]), \
                    mock.patch.object(assembly, "compare_parts", side_effect=change_after_compare):
                with self.assertRaisesRegex(ValueError, "input changed"):
                    assembly.prepare(root / "unused-game", output, native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
            self.assertFalse(output.exists())

    def test_12_real_fixed_archive_rebuild_all_bytes_equal_and_originals_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for actual fixed-index extraction and full independent output")
        with tempfile.TemporaryDirectory(prefix="steve-assembly-rebuild-", dir=native.ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT / "tools/prepare_steve_assembly.py"), "--output", str(output)],
                                    cwd=native.ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / assembly.REPORT_NAME).read_bytes(), self.report_raw)
            report, files, _ = assembly.load_candidate(output / assembly.REPORT_NAME)
            self.assertEqual(report, self.report)
            self.assertEqual(files, self.files)
        assembly.orientation.verify_snapshot(self.snapshot)
        assembly.orientation.verify_snapshot(self.sources_snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=assembly.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    AssemblyChecks.output, AssemblyChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AssemblyChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
