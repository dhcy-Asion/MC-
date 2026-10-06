"""Verify native oak-log geometry/material/texture candidates without game writes.

The default checks local outputs. --rebuild additionally reads the actual game
archives into a fresh ignored build directory and compares the candidate bytes.
No process attachment, inventory mutation, installation or archive write occurs.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_native_block as block


class NativeBlockChecks(unittest.TestCase):
    output = block.ROOT / "build/native-block"
    source = block.ROOT / "build/cdmw-fixed-source"
    deps = block.ROOT / "build/cdmw-deps"
    asset = block.ROOT / "build/block-assets-1.21.1"
    decoder = Path(shutil.which("python") or "python")
    rebuild = False

    @classmethod
    def setUpClass(cls) -> None:
        block.native.load_cdmw(cls.source, cls.deps)
        cls.report = json.loads((cls.output / "native-block-report.json").read_text(encoding="utf-8"))
        cls.payloads = {path: (cls.output / "template" / path).read_bytes() for path in block.TEMPLATE_HASHES}
        cls.pam, cls.lod, cls.layout, cls.lod_layout = block.validate_template(cls.payloads)
        cls.mc, cls.axes = block.read_mc(cls.asset)
        cls.resources = {row["virtualPath"]: row for row in cls.report["candidateResources"]}

    def candidate(self, axis: str, suffix: str, binary: bool = False) -> bytes:
        path = f"object/{'bin__/' if binary else ''}00_common/system/crimsonmc_oak_log_{axis}{suffix}"
        return (self.output / self.resources[path]["localFile"]).read_bytes()

    def test_01_fixed_native_and_mc_provenance(self) -> None:
        self.assertEqual(self.report["supportedExeSha256"], block.native.EXE_SHA256)
        self.assertEqual(self.report["cdmw"]["commit"], block.native.CDMW_COMMIT)
        self.assertEqual(self.report["mcInputs"], block.MC_HASHES)
        self.assertEqual(self.report["archiveIndex"], "0000/0.pamt")
        for name, digest in self.report["files"].items():
            self.assertEqual(block.native.file_hash(self.output / name), digest)
        for path, digest in block.TEMPLATE_HASHES.items():
            self.assertEqual(block.native.sha256(self.payloads[path]), digest)
        self.assertEqual(len(self.resources), 21)
        for path, row in self.resources.items():
            self.assertTrue(Path(path).name.startswith("crimsonmc_"))
            self.assertEqual(row["templateSha256"], block.TEMPLATE_HASHES[row["templatePath"]])
            self.assertEqual(block.native.file_hash(self.output / row["localFile"]), row["sha256"])

    def test_02_original_static_template_no_edit_rebuild(self) -> None:
        self.assertEqual(self.report["templateNoEditRebuildByteIdentical"], {"pam": True, "pamlod": True, "prefab": True})
        pam, lod, layout, lod_layout = block.validate_template(self.payloads)
        self.assertEqual((pam.total_vertices, pam.total_faces), (24, 12))
        self.assertEqual((lod.total_vertices, lod.total_faces), (13, 6))
        self.assertEqual(layout["entries"][0]["stride"], lod_layout["stride"])

    def test_03_three_axes_original_corner_uv_and_topology_round_trip(self) -> None:
        for axis in "xyz":
            mapped = block.map_mc_corners(self.pam, self.axes[axis])
            block.validate_geometry(self.candidate(axis, ".pam"), self.candidate(axis, ".pamlod"), mapped)
            axis_index = "xyz".index(axis)
            end_normals = {tuple(round(v) for v in row["mcNormal"]) for row in mapped if row["atlasTile"]}
            self.assertEqual(end_normals, {tuple(sign if i == axis_index else 0 for i in range(3)) for sign in (-1, 1)})
            self.assertEqual(sum(row["atlasTile"] for row in mapped), 8)
            self.assertEqual(sum(not row["atlasTile"] for row in mapped), 16)

    def test_04_pam_unreviewed_bytes_and_native_shading_records_preserved(self) -> None:
        original = self.payloads[block.BASE + ".pam"]
        permitted = set()
        for offset in self.pam.submeshes[0].source_vertex_offsets:
            permitted.update(range(offset + 8, offset + 12))
        desc = self.layout["entries"][0]["desc_off"]
        for start in (desc + 0x10, desc + 0x110):
            permitted.update(range(start, start + 256))
        for axis in "xyz":
            candidate = self.candidate(axis, ".pam")
            self.assertEqual(len(candidate), len(original))
            changed = {i for i, (a, b) in enumerate(zip(original, candidate)) if a != b}
            self.assertTrue(changed and changed <= permitted)
            for offset in self.pam.submeshes[0].source_vertex_offsets:
                self.assertEqual(candidate[offset:offset + 8], original[offset:offset + 8])
                self.assertEqual(candidate[offset + 12:offset + 20], original[offset + 12:offset + 20])

    def test_05_complete_lod_and_identical_native_vertex_records(self) -> None:
        from cdmw.modding.mesh_parser import parse_pamlod
        for axis in "xyz":
            main = self.candidate(axis, ".pam")
            far = self.candidate(axis, ".pamlod")
            self.assertEqual(main[1712:2264], far[736:])
            self.assertEqual(struct.unpack_from("<4I", far, 92), (24, 36, 0, 0))
            self.assertEqual(len(parse_pamlod(far).lod_levels), 1)
            before, after = self.payloads[block.BASE + ".pamlod"][:736], far[:736]
            permitted = set(range(92, 108)) | set(range(108, 620))
            self.assertTrue({i for i, (a, b) in enumerate(zip(before, after)) if a != b} <= permitted)

    def test_06_prefab_paths_structure_and_collision_preserved(self) -> None:
        from cdmw.core.prefab_binary import decode_prefab_binary, walk_is_determined
        from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
        original = self.payloads[block.BIN_BASE + ".prefab"]
        for axis in "xyz":
            candidate = self.candidate(axis, ".prefab", binary=True)
            path = f"object/00_common/system/crimsonmc_oak_log_{axis}.pami"
            expected = rewrite_prefab_paths(original, {block.BASE + ".pami": path})
            self.assertEqual(candidate, expected.data)
            self.assertTrue(walk_is_determined(candidate))
            self.assertEqual([row.text for row in decode_prefab_binary(candidate).all_strings()], [path])
            self.assertEqual(self.candidate(axis, ".hkx"), self.payloads[block.BASE + ".hkx"])
            self.assertEqual(self.candidate(axis, ".meshinfo", binary=True), self.payloads[block.BIN_BASE + ".meshinfo"])

    def test_07_native_material_and_mesh_primitive_agree(self) -> None:
        from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
        original = ET.fromstring(self.payloads[block.BASE + ".pami"])
        for axis in "xyz":
            doc = ET.fromstring(self.candidate(axis, ".pami"))
            material = doc.find("MaterialData/Material")
            self.assertEqual(doc.find("StaticMesh").get("Path"), f"object/00_common/system/crimsonmc_oak_log_{axis}.pam")
            name = "crimsonmc_oak_log_atlas.dds"
            self.assertEqual(material.get("PrimitiveName"), name)
            self.assertEqual(parse_pam(self.candidate(axis, ".pam")).submeshes[0].material, name)
            self.assertEqual(parse_pamlod(self.candidate(axis, ".pamlod")).submeshes[0].material, name)
            self.assertEqual(ET.tostring(material.find("Common")), ET.tostring(original.find("MaterialData/Material/Common")))
            self.assertEqual(material.find("Common").get("MaterialName"), "Standard")
            expected = {"_baseColorTexture": block.TEXTURE_TARGET + ".dds", "_normalTexture": block.TEXTURE_TARGET + "_n.dds",
                        "_materialTexture": block.TEXTURE_TARGET + "_sp.dds"}
            self.assertEqual({p.get("Name"): p.get("Value") for p in material.findall("Parameters/MaterialParameterTexture")}, expected)
            self.assertTrue(all(path in self.resources for path in expected.values()))

    def test_08_real_texture_bytes_and_independent_all_mip_decode(self) -> None:
        textures, audit, decoder = block.textures_candidate(self.payloads, self.mc, self.decoder)
        self.assertEqual(audit, self.report["textureCandidates"])
        self.assertEqual(decoder, self.report["independentTextureDecoder"])
        for path, data in textures.items():
            self.assertEqual(data, (self.output / self.resources[path]["localFile"]).read_bytes())
        for row in audit.values():
            self.assertEqual(row["mipCount"], 8)
            self.assertEqual((row["width"], row["height"]), (128, 64))
            self.assertLessEqual(row["independentDecode"][0]["maxRgbError"], 4)
            self.assertEqual(row["independentDecode"][0]["maxAlphaError"], 0)
        self.assertEqual(audit[".dds"]["templateHeaderClassification"], 12)
        self.assertEqual(audit["_n.dds"]["templateHeaderClassification"], 4)
        self.assertEqual(audit["_sp.dds"]["templateHeaderClassification"], 4)

    def test_09_corrupt_native_template_and_geometry_rejected(self) -> None:
        damaged = dict(self.payloads)
        damaged[block.BASE + ".pam"] = damaged[block.BASE + ".pam"][:-1]
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            block.validate_template(damaged)
        mapped = block.map_mc_corners(self.pam, self.axes["y"])
        damaged_pam = bytearray(self.candidate("y", ".pam"))
        struct.pack_into("<e", damaged_pam, 1712 + 8, 0.3)
        with self.assertRaisesRegex(ValueError, "UV round-trip"):
            block.validate_geometry(bytes(damaged_pam), self.candidate("y", ".pamlod"), mapped)
        damaged_faces = copy.deepcopy(self.axes["y"])
        damaged_faces[0]["normals"] = [(0, 0, 0)] * 4
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            block.map_mc_corners(self.pam, damaged_faces)

    def test_10_public_output_link_and_report_escape_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ignored build"):
            block.native.output_directory(block.ROOT / "docs/native-block")
        with tempfile.TemporaryDirectory(prefix="native-block-guard-", dir=block.ROOT / "build") as temp:
            output = Path(temp)
            linked = output / "native-block-report.json"
            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == linked):
                with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                    block.publish(output, {"must-not-write.pam": b"test"}, {})
            self.assertFalse((output / "must-not-write.pam").exists())
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                block.publish(output, {"../escape.pam": b"test"}, {})
            self.assertFalse((output / "native-block-report.json").exists())

    def test_11_all_game_integration_flags_remain_false(self) -> None:
        self.assertTrue(self.report["integration"])
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertEqual({row["selector"] for row in self.report["variants"]}, {"axis=x", "axis=y", "axis=z"})

    def test_12_directory_collision_rejected_before_any_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="native-block-dir-guard-", dir=block.ROOT / "build") as temp:
            output = Path(temp)
            (output / "native-block-report.json").mkdir()
            with self.assertRaisesRegex(ValueError, "collides with a directory"):
                block.publish(output, {"must-not-write.pam": b"test"}, {})
            self.assertFalse((output / "must-not-write.pam").exists())

    def test_13_fresh_read_only_archive_rebuild(self) -> None:
        if not self.rebuild:
            self.skipTest("Pass --rebuild for fresh read-only installed archive extraction")
        with tempfile.TemporaryDirectory(prefix="native-block-rebuild-", dir=block.ROOT / "build") as temp:
            cmd = [sys.executable, "-B", str(block.ROOT / "tools/prepare_native_block.py"), "--output", temp,
                   "--cdmw-source", str(self.source), "--deps", str(self.deps), "--block-asset", str(self.asset),
                   "--decoder-python", str(self.decoder)]
            result = subprocess.run(cmd, cwd=block.ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rebuilt = json.loads((Path(temp) / "native-block-report.json").read_text(encoding="utf-8"))
            self.assertEqual(rebuilt, self.report)
            for name in self.report["files"]:
                self.assertEqual((Path(temp) / name).read_bytes(), (self.output / name).read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=NativeBlockChecks.output)
    parser.add_argument("--cdmw-source", type=Path, default=NativeBlockChecks.source)
    parser.add_argument("--deps", type=Path, default=NativeBlockChecks.deps)
    parser.add_argument("--block-asset", type=Path, default=NativeBlockChecks.asset)
    parser.add_argument("--decoder-python", type=Path, default=NativeBlockChecks.decoder)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    NativeBlockChecks.output = block.native.output_directory(args.output)
    NativeBlockChecks.source, NativeBlockChecks.deps, NativeBlockChecks.asset = args.cdmw_source, args.deps, args.block_asset
    NativeBlockChecks.decoder, NativeBlockChecks.rebuild = args.decoder_python, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeBlockChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
