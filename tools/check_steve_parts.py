"""Verify real head/body partitions, material dependencies and rebuild isolation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import prepare_steve_parts as parts

native, segmented, orientation = parts.native, parts.segmented, parts.orientation


class PartsChecks(unittest.TestCase):
    output = parts.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        native.load_cdmw(native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
        cls.output = native.output_directory(cls.output)
        cls.raw = (cls.output / parts.REPORT_NAME).read_bytes()
        cls.report = json.loads(cls.raw)
        cls.source, cls.files, cls.snapshot = parts.load_inputs(parts.SOURCE_REPORT)
        cls.donor = cls.files["template/" + native.BODY]
        cls.combined = cls.files["resources/" + parts.material.PAC_PATH]
        cls.pacs = {name: (cls.output / "resources" / path).read_bytes() for name, path in parts.PAC_PATHS.items()}

    def test_01_source_and_exact_resource_closure(self):
        expected = set(parts.PAC_PATHS.values()) | set(parts.MATERIAL_PATHS.values()) | set(parts.material.TEXTURE_PATHS.values())
        self.assertEqual({row["virtualPath"] for row in self.report["candidateResources"]}, expected)
        self.assertEqual(set(self.report["files"]), {"resources/" + path for path in expected})
        for row in self.report["candidateResources"]:
            self.assertEqual(row["localFile"], "resources/" + row["virtualPath"])
            payload = (self.output / row["localFile"]).read_bytes()
            self.assertEqual(native.sha256(payload), row["sha256"])
            self.assertEqual(row["sha256"], self.report["files"][row["localFile"]])
        self.assertEqual(self.report["sourceSegmentedReportSha256"], parts.SOURCE_SHA256)
        self.assertEqual(self.report["rigInputs"], orientation.fixed_rig_inputs())
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertTrue(any("00_0001" in item and "01_0002" in item for item in self.report["limitations"]))

    def test_02_all_lods_exact_surface_skin_and_packed_frame_union(self):
        self.assertEqual(parts.verify_partition(self.combined, self.pacs, self.donor), self.report["union"])
        self.assertEqual([row["lod"] for row in self.report["union"]], [0, 1, 2, 3])
        for name, counts in (("head", (48, 24)), ("body", (1008, 504))):
            for _, mesh in segmented.parse_lods(self.pacs[name], self.donor):
                self.assertEqual((mesh.total_vertices, mesh.total_faces), counts)
                self.assertEqual(len(mesh.submeshes), 1)
        expected_head = {"head", "hat"}
        head = self.report["parts"]["head"]["parts"]
        body = self.report["parts"]["body"]["parts"]
        self.assertEqual({row["part"] for row in head}, expected_head)
        self.assertEqual({row["part"] for row in body}, {row["part"] for row in self.source["parts"]} - expected_head)
        for name, rows in (("head", head), ("body", body)):
            self.assertTrue(all(row["nativeDrawSlot"] == (0 if name == "head" else 2) for row in rows))
            self.assertEqual(rows, [r for r in self.source["parts"] if (r["logicalPart"] == "head") == (name == "head")])

    def test_03_palette_and_no_edit_rebuild(self):
        from cdmw.modding.skeleton_parser import parse_pab
        from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
        from cdmw.modding.mesh_pac_builder import build_pac
        skeleton = parse_pab(self.files["template/" + native.SKELETON], native.SKELETON)
        palette = resolve_pac_bone_palette(self.combined, skeleton)
        self.assertEqual((len(skeleton.bones), len(palette)), (447, 189))
        for payload in self.pacs.values():
            self.assertEqual(resolve_pac_bone_palette(payload, skeleton), palette)
            self.assertEqual(build_pac(parse_pac(payload, native.BODY), payload), payload)

    def test_04_each_material_covers_native_draws_and_exact_textures(self):
        from cdmw.core.pac_xml_standard_material import find_material_wrappers
        for name, pac_path in parts.PAC_PATHS.items():
            expected = pac_path.replace("/model/", "/modelproperty/", 1) + "_xml"
            self.assertEqual(parts.MATERIAL_PATHS[name], expected)
            data = (self.output / "resources" / expected).read_bytes()
            self.assertEqual(data, self.files["resources/" + parts.material.MATERIAL_PATH])
            wrappers = find_material_wrappers(data.decode("utf-8-sig"))
            self.assertEqual(len(wrappers), 18)
            self.assertEqual({w.submesh_name for w in wrappers}, set(parts.material.DRAW_NAMES))
            for w in wrappers:
                self.assertEqual(w.shader, "SkinnedMeshStandard")
                self.assertEqual(w.textures, {"_baseColorTexture": parts.material.TEXTURE_PATHS["base"],
                                             "_normalTexture": parts.material.TEXTURE_PATHS["normal"],
                                             "_materialTexture": parts.material.TEXTURE_PATHS["material"]})
        for path in parts.material.TEXTURE_PATHS.values():
            self.assertEqual((self.output / "resources" / path).read_bytes(), self.files["resources/" + path])

    def test_05_missing_swapped_and_corrupt_partitions_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly"):
            parts.verify_partition(self.combined, {"head": self.pacs["head"]}, self.donor)
        with self.assertRaisesRegex(ValueError, "changed"):
            parts.verify_partition(self.combined, {"head": self.pacs["body"], "body": self.pacs["head"]}, self.donor)
        corrupt = bytearray(self.pacs["head"])
        offset = segmented.parse_lods(corrupt, self.donor)[0][1].submeshes[0].source_vertex_offsets[0]
        # Unknown/reserved byte changes must also fail even when decoded geometry agrees.
        corrupt[offset + 38] ^= 1
        with self.assertRaisesRegex(ValueError, "packed"):
            parts.verify_partition(self.combined, {**self.pacs, "head": bytes(corrupt)}, self.donor)

    def test_06_wrong_source_and_output_collision_rejected(self):
        with tempfile.TemporaryDirectory(prefix="steve-parts-negative-", dir=native.ROOT / "build") as tmp:
            path = Path(tmp)
            bad = path / "bad.json"
            bad.write_bytes(parts.SOURCE_REPORT.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                parts.load_inputs(bad)
            with self.assertRaisesRegex(ValueError, "already exists"):
                parts.prepare(parts.SOURCE_REPORT, path, native.ROOT / "build/cdmw-fixed-source", native.ROOT / "build/cdmw-deps")
            self.assertEqual(bad.read_bytes(), parts.SOURCE_REPORT.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            orientation.preflight(native.ROOT / "artifacts/steve-parts", [])

    def test_07_real_rebuild_is_identical_and_sources_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a fresh reconstruction")
        with tempfile.TemporaryDirectory(prefix="steve-parts-rebuild-", dir=native.ROOT / "build") as tmp:
            output = Path(tmp) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(native.ROOT / "tools/prepare_steve_parts.py"), "--output", str(output)],
                                    cwd=native.ROOT, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / parts.REPORT_NAME).read_bytes(), self.raw)
            for relative in self.report["files"]:
                self.assertEqual((output / relative).read_bytes(), (self.output / relative).read_bytes())
        orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=parts.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    PartsChecks.output, PartsChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PartsChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
