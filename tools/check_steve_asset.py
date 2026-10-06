"""Check the local, actual-engine Steve export without touching either game/world."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import build_steve_asset as asset


def accessor(gltf: dict, binary: bytes, index: int) -> list:
    value = gltf["accessors"][index]
    view = gltf["bufferViews"][value["bufferView"]]
    components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[value["type"]]
    code, size = {5126: ("f", 4), 5123: ("H", 2)}[value["componentType"]]
    offset = view.get("byteOffset", 0) + value.get("byteOffset", 0)
    length = value["count"] * components * size
    if offset % size or offset + length > view.get("byteOffset", 0) + view["byteLength"] or offset + length > len(binary):
        raise ValueError("Accessor crosses its buffer view")
    flat = struct.unpack_from("<" + code * (value["count"] * components), binary, offset)
    if not all(math.isfinite(number) for number in flat):
        raise ValueError("Nonfinite glTF attribute")
    return [list(flat[start:start + components]) for start in range(0, len(flat), components)]


def cross(a: list, b: list, c: list) -> list:
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]


class SteveChecks(unittest.TestCase):
    asset_root = asset.DEFAULT_OUTPUT

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = asset.read_config()
        cls.manifest = json.loads((cls.asset_root / "manifest.json").read_text(encoding="utf-8"))
        cls.gltf = json.loads((cls.asset_root / "steve.gltf").read_text(encoding="utf-8"))
        cls.binary = (cls.asset_root / "steve.bin").read_bytes()
        cls.geometry = json.loads((cls.asset_root / "minecraft-model.json").read_text(encoding="utf-8"))
        cls.parts = {part["name"]: part for part in cls.geometry["parts"]}

    def mesh(self, name: str) -> dict:
        return next(mesh for mesh in self.gltf["meshes"] if mesh["name"] == name)["primitives"][0]

    def data(self, name: str, attribute: str) -> list:
        return accessor(self.gltf, self.binary, self.mesh(name)["attributes"][attribute])

    def test_01_actual_engine_and_official_skin_hashes(self) -> None:
        self.assertEqual(asset.canonical_digest(self.geometry), self.config["geometryCanonicalSha256"])
        self.assertEqual(asset.digest((self.asset_root / "steve.png").read_bytes()), self.config["skin"]["sha256"])
        for name, expected in self.manifest["files"].items():
            self.assertEqual(asset.digest((self.asset_root / name).read_bytes()), expected)
        self.assertEqual(self.manifest["configurationSha256"], asset.digest(asset.CONFIG.read_bytes()))
        self.assertEqual(self.manifest["exporterSha256"], asset.digest(Path(asset.__file__).read_bytes()))
        self.assertEqual(self.manifest["readerSha256"], asset.digest((asset.ROOT / "tools" / "SteveModelDump.java").read_bytes()))
        self.assertTrue(all(value is False for value in self.manifest["integration"].values()))

    def test_02_independent_classic_dimensions_and_pivots(self) -> None:
        expected_dimensions = {"head": [8, 8, 8], "body": [8, 12, 4],
                               "right_arm": [4, 12, 4], "left_arm": [4, 12, 4],
                               "right_leg": [4, 12, 4], "left_leg": [4, 12, 4]}
        expected_pivots = {"head": [0, 0, 0], "body": [0, 0, 0],
                           "right_arm": [-5, 2, 0], "left_arm": [5, 2, 0],
                           "right_leg": [-1.9, 12, 0], "left_leg": [1.9, 12, 0]}
        for name, dimensions in expected_dimensions.items():
            part = self.parts[name]
            positions = [v[:3] for c in part["cuboids"] for q in c["quads"] for v in q["vertices"]]
            self.assertEqual([max(v[i] for v in positions) - min(v[i] for v in positions) for i in range(3)], dimensions)
            self.assertEqual(part["pivot"], expected_pivots[name])
        self.assertFalse(self.geometry["thinArms"])

    def test_03_independent_skin_atlas_front_faces(self) -> None:
        # Known 64x64 modern classic layout; exact ordered pixel corners also catch
        # accidental mirroring/UV flips, including independent left limbs and overlays.
        rectangles = {"head": (8, 8, 16, 16), "hat": (40, 8, 48, 16),
                      "body": (20, 20, 28, 32), "jacket": (20, 36, 28, 48),
                      "right_arm": (44, 20, 48, 32), "left_arm": (36, 52, 40, 64),
                      "right_sleeve": (44, 36, 48, 48), "left_sleeve": (52, 52, 56, 64),
                      "right_leg": (4, 20, 8, 32), "left_leg": (20, 52, 24, 64),
                      "right_pants": (4, 36, 8, 48), "left_pants": (4, 52, 8, 64)}
        for name, (u0, v0, u1, v1) in rectangles.items():
            front = next(quad for quad in self.parts[name]["cuboids"][0]["quads"] if quad["normal"] == [0, 0, -1])
            self.assertEqual([vertex[3:5] for vertex in front["vertices"]],
                             [[u1 / 64, v0 / 64], [u0 / 64, v0 / 64], [u0 / 64, v1 / 64], [u1 / 64, v1 / 64]])

    def test_04_every_exported_vertex_uv_and_normal_matches_engine(self) -> None:
        for name in (*asset.BASE_PARTS, *asset.OUTER_PARTS):
            part = self.parts[name]
            source = [(vertex, quad["normal"]) for c in part["cuboids"] for quad in c["quads"] for vertex in quad["vertices"]]
            positions, normals, uvs = self.data(name, "POSITION"), self.data(name, "NORMAL"), self.data(name, "TEXCOORD_0")
            self.assertEqual(len(source), 24)
            self.assertEqual(len(positions), len(source))
            for index, (vertex, normal) in enumerate(source):
                expected = [(vertex[0] + part["pivot"][0]) / 16,
                            (24 - vertex[1] - part["pivot"][1]) / 16,
                            -(vertex[2] + part["pivot"][2]) / 16]
                for actual, wanted in zip(positions[index], expected):
                    self.assertAlmostEqual(actual, wanted, places=6)
                self.assertEqual(normals[index], [normal[0], -normal[1], -normal[2]])
                self.assertEqual(uvs[index], vertex[3:5])

    def test_05_outer_dilation_and_shared_joints(self) -> None:
        for outer, base in asset.OUTER_PARTS.items():
            dilation = 0.5 if outer == "hat" else 0.25
            base_positions, outer_positions = self.data(base, "POSITION"), self.data(outer, "POSITION")
            for axis in range(3):
                self.assertAlmostEqual(min(p[axis] for p in base_positions) - min(p[axis] for p in outer_positions), dilation / 16)
                self.assertAlmostEqual(max(p[axis] for p in outer_positions) - max(p[axis] for p in base_positions), dilation / 16)
            self.assertEqual(self.data(base, "JOINTS_0"), self.data(outer, "JOINTS_0"))
            self.assertEqual(self.data(base, "WEIGHTS_0"), self.data(outer, "WEIGHTS_0"))

    def test_06_default_scene_excludes_special_cape_and_ears(self) -> None:
        self.assertEqual({mesh["name"] for mesh in self.gltf["meshes"]}, set(asset.BASE_PARTS) | set(asset.OUTER_PARTS))
        children = self.gltf["nodes"][0]["children"]
        self.assertEqual(len(children), 6)
        self.assertEqual(len(set(children)), len(children))
        self.assertEqual(self.gltf["skins"][0]["joints"], children)
        self.assertEqual(self.gltf["scenes"][0]["nodes"], [0, *range(7, 19)])
        for node in self.gltf["nodes"][7:]:
            self.assertEqual(node["skin"], 0)
        self.assertNotIn("animations", self.gltf)

    def test_07_bind_matrices_preserve_mesh_and_pivots(self) -> None:
        skin = self.gltf["skins"][0]
        matrices = accessor(self.gltf, self.binary, skin["inverseBindMatrices"])
        for name in asset.BASE_PARTS:
            joint = asset.BASE_PARTS.index(name)
            pivot = self.gltf["nodes"][skin["joints"][joint]]["translation"]
            matrix = matrices[joint]
            self.assertEqual(matrix[:12], [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0])
            self.assertEqual(matrix[15], 1)
            for actual, expected in zip(matrix[12:15], [-component for component in pivot]):
                self.assertAlmostEqual(actual, expected, places=6)
            for position in self.data(name, "POSITION"):
                # J_bind * inverseBind * vertex is unchanged in the shared root space.
                for axis in range(3):
                    self.assertAlmostEqual(pivot[axis] + matrix[12 + axis] + position[axis], position[axis], places=6)
            for weights, joints in zip(self.data(name, "WEIGHTS_0"), self.data(name, "JOINTS_0")):
                self.assertEqual(weights, [1, 0, 0, 0])
                self.assertEqual(joints, [joint, 0, 0, 0])

    def test_08_articulation_uses_real_shared_arm_pivot(self) -> None:
        skin = self.gltf["skins"][0]
        pivot = self.gltf["nodes"][skin["joints"][asset.BASE_PARTS.index("right_arm")]]["translation"]
        self.assertEqual(pivot, [-5 / 16, 22 / 16, 0])
        angle = math.pi / 2
        for name in ("right_arm", "right_sleeve"):
            self.assertEqual(self.data(name, "JOINTS_0")[0][0], asset.BASE_PARTS.index("right_arm"))
            for position in self.data(name, "POSITION"):
                local = [position[i] - pivot[i] for i in range(3)]
                rotated = [local[0], math.cos(angle) * local[1] - math.sin(angle) * local[2],
                           math.sin(angle) * local[1] + math.cos(angle) * local[2]]
                output = [pivot[i] + rotated[i] for i in range(3)]
                self.assertAlmostEqual(sum((output[i] - pivot[i]) ** 2 for i in range(3)), sum(x * x for x in local))
        # Rigid MC limb pivots are exported; this does not imply any red-side bone match.
        self.assertFalse(self.manifest["integration"]["gameSkeletonMapped"])

    def test_09_triangle_winding_and_unit_normals(self) -> None:
        for name in (*asset.BASE_PARTS, *asset.OUTER_PARTS):
            positions, normals = self.data(name, "POSITION"), self.data(name, "NORMAL")
            indices = [row[0] for row in accessor(self.gltf, self.binary, self.mesh(name)["indices"])]
            self.assertEqual(len(indices), 36)
            for start in range(0, len(indices), 3):
                a, b, c = indices[start:start + 3]
                normal = normals[a]
                self.assertEqual(sum(n * n for n in normal), 1)
                facing = cross(positions[a], positions[b], positions[c])
                self.assertGreater(sum(facing[i] * normal[i] for i in range(3)), 0)

    def test_10_renderer_scale_and_floor_are_explicit(self) -> None:
        self.assertEqual(self.gltf["nodes"][0]["scale"], [0.9375] * 3)
        base_positions = [position for name in asset.BASE_PARTS for position in self.data(name, "POSITION")]
        self.assertEqual(min(p[1] for p in base_positions), 0)
        self.assertEqual(max(p[1] for p in base_positions), 2)
        self.assertEqual((max(p[1] for p in base_positions) - min(p[1] for p in base_positions)) * 0.9375, 1.875)
        self.assertEqual(self.manifest["model"]["baseHeightRenderedMeters"], 1.875)

    def test_11_buffer_bounds_materials_and_pixel_sampling(self) -> None:
        self.assertEqual(self.gltf["buffers"][0]["byteLength"], len(self.binary))
        for index in range(len(self.gltf["accessors"])):
            accessor(self.gltf, self.binary, index)
        for name in (*asset.BASE_PARTS, *asset.OUTER_PARTS):
            self.assertEqual(self.mesh(name)["material"], int(name in asset.OUTER_PARTS))
            for uv in self.data(name, "TEXCOORD_0"):
                self.assertTrue(all(0 <= value <= 1 for value in uv))
        self.assertEqual(self.gltf["samplers"][0]["magFilter"], 9728)
        self.assertEqual(self.gltf["samplers"][0]["minFilter"], 9728)
        self.assertEqual(self.gltf["materials"][1]["alphaMode"], "MASK")
        self.assertEqual(self.gltf["images"][0]["uri"], "steve.png")
        broken = copy.deepcopy(self.gltf)
        broken["accessors"][0]["count"] += 1
        with self.assertRaisesRegex(ValueError, "buffer view"):
            accessor(broken, self.binary, 0)

    def test_12_deterministic_export_and_fail_closed_guards(self) -> None:
        regenerated, binary = asset.export_gltf(self.geometry, self.config)
        self.assertEqual(regenerated, self.gltf)
        self.assertEqual(binary, self.binary)
        with self.assertRaises(ValueError):
            asset.output_directory(asset.ROOT / "docs" / "steve")
        with tempfile.TemporaryDirectory() as temporary:
            invalid_client = Path(temporary) / "client.jar"
            invalid_client.write_bytes(b"not an official Minecraft binary")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                asset.verify_client(invalid_client, self.config)
            self.assertEqual(invalid_client.read_bytes(), b"not an official Minecraft binary")
        broken = copy.deepcopy(self.geometry)
        broken["parts"][0]["name"] = "unreviewed_part"
        with self.assertRaisesRegex(ValueError, "model parts"):
            asset.export_gltf(broken, self.config)

    def test_13_linked_build_root_cannot_make_public_output_acceptable(self) -> None:
        build_root = asset.ROOT / "build"
        public_output = asset.ROOT / "docs" / "steve"
        actual_resolve = Path.resolve
        actual_symlink = Path.is_symlink
        # Simulate a junction whose target is docs without creating a Windows link.
        def resolve(path, *args, **kwargs):
            return asset.ROOT / "docs" if path == build_root else actual_resolve(path, *args, **kwargs)
        def symlink(path):
            return path == build_root or actual_symlink(path)
        with patch.object(Path, "resolve", resolve), patch.object(Path, "is_symlink", symlink):
            with self.assertRaisesRegex(ValueError, "ignored build"):
                asset.output_directory(public_output)
            with self.assertRaisesRegex(ValueError, "symlinks or junctions"):
                asset.output_directory(build_root / "steve")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=asset.DEFAULT_OUTPUT)
    args = parser.parse_args()
    SteveChecks.asset_root = asset.output_directory(args.asset_root)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SteveChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
