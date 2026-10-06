"""Verify local baseline block assets against the pinned client, without a game/world.

Reads the actual client resource files independently, checks the original-engine
geometry and every glTF buffer, and exercises refusal/output protection paths.
Does not install, render in Crimson Desert, or alter experimental inventory.
"""
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
import zipfile

import build_block_assets as asset


def read_accessor(gltf: dict, binary: bytes, index: int) -> list:
    value = gltf["accessors"][index]
    view = gltf["bufferViews"][value["bufferView"]]
    components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[value["type"]]
    code, size = {5126: ("f", 4), 5123: ("H", 2)}[value["componentType"]]
    offset = view.get("byteOffset", 0) + value.get("byteOffset", 0)
    count = value["count"] * components
    if offset % size or offset + count * size > view.get("byteOffset", 0) + view["byteLength"] or offset + count * size > len(binary):
        raise ValueError("Accessor crosses its buffer view")
    numbers = struct.unpack_from("<" + code * count, binary, offset)
    if not all(math.isfinite(n) for n in numbers):
        raise ValueError("Nonfinite accessor")
    return [list(numbers[i:i + components]) for i in range(0, count, components)]


def source_choices(raw: dict) -> list[dict]:
    # Independent raw resource traversal; no call to exporter choices().
    groups = list(raw.get("variants", {}).items())
    groups += [(f"part:{i}", part["apply"]) for i, part in enumerate(raw.get("multipart", []))]
    return [{"selector": selector, "choice": i, **choice} for selector, choices in groups
            for i, choice in enumerate(choices if isinstance(choices, list) else [choices])]


def model_chain(archive: zipfile.ZipFile, model: str) -> tuple[list[str], dict]:
    chain, documents = [], []
    while model:
        namespace, name = model.split(":", 1) if ":" in model else ("minecraft", model)
        if name.startswith("builtin/"):
            break
        path = f"assets/{namespace}/models/{name}.json"
        if path in chain:
            raise ValueError("Independent model cycle")
        chain.append(path)
        document = json.loads(archive.read(path))
        documents.append(document)
        model = document.get("parent")
    merged = {"textures": {}}
    for document in reversed(documents):
        merged["textures"].update(document.get("textures", {}))
        if "elements" in document:
            merged["elements"] = document["elements"]
    return chain, merged


class BlockAssetChecks(unittest.TestCase):
    asset_root = asset.DEFAULT_OUTPUT

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = asset.steve.read_config()
        cls.client, _ = asset.steve.dependencies(cls.config, None, False)
        asset.steve.verify_client(cls.client, cls.config)
        cls.archive = zipfile.ZipFile(cls.client)
        cls.manifest = json.loads((cls.asset_root / "manifest.json").read_text(encoding="utf-8"))
        cls.coverage = json.loads((cls.asset_root / "coverage.json").read_text(encoding="utf-8"))
        cls.quads = json.loads((cls.asset_root / "quad-input.json").read_text(encoding="utf-8"))
        cls.geometry = json.loads((cls.asset_root / "engine-quads.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.archive.close()

    def close_vector(self, actual: list, expected: list, tolerance: float = 2e-6) -> None:
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, delta=tolerance)

    def test_01_provenance_and_local_files(self) -> None:
        self.assertEqual(self.manifest["clientSha256"], self.config["client"]["sha256"])
        self.assertEqual(self.manifest["sourceConfigSha256"], asset.steve.digest(asset.steve.CONFIG.read_bytes()))
        self.assertEqual(self.manifest["exporterSha256"], asset.steve.digest(Path(asset.__file__).read_bytes()))
        self.assertEqual(self.manifest["readerSha256"], asset.steve.digest(asset.JAVA_READER.encode("utf-8")))
        self.assertEqual(self.manifest["engineClassSha256"], asset.ENGINE_CLASSES)
        for path, expected in asset.ENGINE_CLASSES.items():
            self.assertEqual(asset.steve.digest(self.archive.read(path)), expected)
        for path, expected in self.manifest["files"].items():
            self.assertEqual(asset.steve.digest((self.asset_root / path).read_bytes()), expected, path)
        self.assertFalse(self.manifest["nativeIntegrated"])
        self.assertFalse(self.manifest["registryComplete"])
        self.assertFalse(self.coverage["registryComplete"])
        self.assertFalse(self.coverage["nativeIntegrated"])

    def test_02_all_actual_blockstate_resources_and_model_references(self) -> None:
        source_paths = sorted(path for path in self.archive.namelist() if path.startswith("assets/minecraft/blockstates/") and path.endswith(".json"))
        self.assertEqual([row["file"] for row in self.coverage["entries"]], source_paths)
        self.assertEqual(self.coverage["resourceFileCount"], len(source_paths))
        total = 0
        for row in self.coverage["entries"]:
            raw = json.loads(self.archive.read(row["file"]))
            self.assertEqual(row["sha256"], asset.steve.digest(self.archive.read(row["file"])))
            expected = source_choices(raw)
            self.assertEqual(len(row["choices"]), len(expected))
            total += len(expected)
            for item, original in zip(row["choices"], expected):
                self.assertEqual(item["model"], original["model"] if ":" in original["model"] else "minecraft:" + original["model"])
                for key, default in (("x", 0), ("y", 0), ("weight", 1), ("uvlock", False)):
                    self.assertEqual(item[key], original.get(key, default))
                self.assertEqual(item["selector"], original["selector"])
                self.assertEqual(item["choice"], original["choice"])
                self.assertEqual(item["dependencyStatus"], "resolved")
                chain, merged = model_chain(self.archive, item["model"])
                self.assertEqual(set(item["modelFiles"]), set(chain))
                self.assertEqual(item["elementCount"], len(merged.get("elements", [])))
                for path in chain:
                    self.assertEqual(item["modelFiles"][path], asset.steve.digest(self.archive.read(path)))
                for path, texture in item["textures"].items():
                    self.assertEqual(texture["sha256"], asset.steve.digest(self.archive.read(path)))
                    if "mcmetaSha256" in texture:
                        self.assertEqual(texture["mcmetaSha256"], asset.steve.digest(self.archive.read(path + ".mcmeta")))
        self.assertEqual(total, self.coverage["modelChoiceCount"])
        self.assertEqual(self.coverage["missingChoiceCount"], 0)
        # Resource-only models lack rendered block geometry for these cases.
        by_id = {row["id"]: row for row in self.coverage["entries"]}
        for block in ("air", "water", "chest", "oak_sign", "red_bed"):
            self.assertTrue(all(choice["elementCount"] == 0 for choice in by_id["minecraft:" + block]["choices"]))
        empty_count = sum(c["elementCount"] == 0 for r in self.coverage["entries"] for c in r["choices"])
        self.assertEqual(self.coverage["emptyGeometryChoiceCount"], empty_count)

    def test_03_baseline_choices_and_textures_equal_original_bytes(self) -> None:
        expected = [("minecraft:" + block, choice["selector"], choice["choice"], choice["model"])
                    for block in asset.BASELINE for choice in source_choices(json.loads(self.archive.read(f"assets/minecraft/blockstates/{block}.json")))]
        actual = [(row["id"], row["selector"], row["choice"], row["model"]) for row in self.manifest["assets"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 14)
        textures = [path for path in self.manifest["files"] if path.endswith(".png")]
        self.assertEqual(len(textures), 9)
        for path in textures:
            original = "assets/" + path.removeprefix("textures/").split("/", 1)[0] + "/textures/" + path.removeprefix("textures/").split("/", 1)[1]
            self.assertEqual((self.asset_root / path).read_bytes(), self.archive.read(original))
            asset.png_info((self.asset_root / path).read_bytes(), require_opaque=True)
        self.assertEqual(len(self.quads), 84)
        self.assertEqual([q["quadId"] for q in self.geometry], list(range(84)))

    def test_04_gltf_buffers_equal_original_engine_geometry(self) -> None:
        for row in self.manifest["assets"]:
            gltf = json.loads((self.asset_root / row["file"]).read_text(encoding="utf-8"))
            binary = (self.asset_root / Path(row["file"]).with_suffix(".bin")).read_bytes()
            self.assertEqual(gltf["buffers"][0]["byteLength"], len(binary))
            self.assertFalse(gltf["extras"]["nativeIntegrated"])
            self.assertFalse(gltf["extras"]["randomChoiceApplied"])
            self.assertNotIn("skins", gltf)
            self.assertNotIn("animations", gltf)
            self.assertEqual(gltf["samplers"][0]["magFilter"], 9728)
            primitives = gltf["meshes"][0]["primitives"]
            self.assertEqual(len(primitives), 6)
            for primitive, quad_id in zip(primitives, row["quadIds"]):
                original, request = self.geometry[quad_id], self.quads[quad_id]
                positions = read_accessor(gltf, binary, primitive["attributes"]["POSITION"])
                uvs = read_accessor(gltf, binary, primitive["attributes"]["TEXCOORD_0"])
                normals = read_accessor(gltf, binary, primitive["attributes"]["NORMAL"])
                for p, source in zip(positions, original["positions"]):
                    self.close_vector(p, source)
                    self.assertTrue(all(abs(n) < 2e-6 or abs(n - 1) < 2e-6 for n in p))
                for uv, source in zip(uvs, original["uvs"]):
                    self.close_vector(uv, source)
                self.assertEqual({tuple(round(n, 6) for n in uv) for uv in uvs}, {(0., 0.), (0., 1.), (1., 0.), (1., 1.)})
                center = [sum(p[i] for p in positions) / 4 - 0.5 for i in range(3)]
                for n in normals:
                    self.assertAlmostEqual(sum(n[i] * center[i] for i in range(3)), 0.5, delta=2e-6)
                self.assertEqual(read_accessor(gltf, binary, primitive["indices"]), [[0], [1], [2], [0], [2], [3]])
                material = gltf["materials"][primitive["material"]]
                self.assertEqual(material["name"], request["texture"])
                image = gltf["images"][gltf["textures"][material["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["uri"]
                self.assertTrue((self.asset_root / "meshes" / image).resolve().is_relative_to(self.asset_root.resolve()))
                self.assertEqual((self.asset_root / "meshes" / image).read_bytes(), self.archive.read(asset.entry_path(request["texture"], "textures", "png")))
            for i in range(len(gltf["accessors"])):
                read_accessor(gltf, binary, i)

    def test_05_oak_log_three_axes_and_mirrored_stone_uv(self) -> None:
        for row in self.manifest["assets"]:
            if row["id"] == "minecraft:oak_log":
                axis = {"axis=x": 0, "axis=y": 1, "axis=z": 2}[row["selector"]]
                end_faces = [self.geometry[i]["positions"] for i in row["quadIds"] if self.quads[i]["texture"] == "minecraft:block/oak_log_top"]
                self.assertEqual(len(end_faces), 2)
                plane_values = []
                for points in end_faces:
                    self.assertLess(max(p[axis] for p in points) - min(p[axis] for p in points), 2e-6)
                    plane_values.append(round(points[0][axis]))
                self.assertEqual(sorted(plane_values), [0, 1])
        stone = [row for row in self.manifest["assets"] if row["id"] == "minecraft:stone"]
        for a, b in ((stone[0], stone[1]), (stone[2], stone[3])):
            for ai, bi in zip(a["quadIds"], b["quadIds"]):
                for point, mirrored in zip(self.geometry[ai]["positions"], self.geometry[bi]["positions"]):
                    self.close_vector(point, mirrored)
                for uv, mirrored in zip(self.geometry[ai]["uvs"], self.geometry[bi]["uvs"]):
                    self.close_vector(mirrored, [1 - uv[0], uv[1]])

    def test_06_resource_and_geometry_refusals(self) -> None:
        for bad in ("../outside", "minecraft:block/../outside", "other:", "Minecraft:Stone", "minecraft:/stone"):
            with self.assertRaises(ValueError):
                asset.resource_id(bad)
        for value, mapping in (("#a", {"a": "#b", "b": "#a"}), ("#missing", {})):
            with self.assertRaises(ValueError):
                asset.Resources.texture(value, mapping)
        with self.assertRaises(ValueError):
            asset.Resources.face_texture("unknown", {"all": "block/stone"})
        # heavy_core demonstrates vanilla's optional '#' face key convention.
        self.assertEqual(asset.Resources.face_texture("all", {"all": "block/heavy_core"}), "minecraft:block/heavy_core")
        resources = asset.Resources(self.archive)
        with self.assertRaisesRegex(ValueError, "Missing model"):
            resources.model("minecraft:block/crimsonmc_missing_test")
        original = resources.model("minecraft:block/oak_log_horizontal")
        for alteration, pattern in (("rotation", "Element rotation"), ("tint", "biome tint"), ("missing", "Missing face texture"), ("degenerate", "Degenerate")):
            mutated = copy.deepcopy(original)
            element = mutated["elements"][0]
            if alteration == "rotation":
                element["rotation"] = {"axis": "x", "angle": 22.5}
            elif alteration == "tint":
                element["faces"]["down"]["tintindex"] = 0
            elif alteration == "missing":
                element["faces"]["down"]["texture"] = "#missing"
            else:
                element["to"] = element["from"]
            resources.models["minecraft:block/oak_log_horizontal"] = mutated
            with self.assertRaisesRegex(ValueError, pattern):
                resources.baseline_quads()
        resources.models["minecraft:block/oak_log_horizontal"] = original

    def test_07_png_corruption_and_output_protection(self) -> None:
        png = self.archive.read("assets/minecraft/textures/block/oak_log.png")
        for bad in (png[:-1], b"bad image", png[:40] + bytes([png[40] ^ 1]) + png[41:]):
            with self.assertRaises(ValueError):
                asset.png_info(bad, require_opaque=True)
        with self.assertRaises(ValueError):
            asset.steve.output_directory(asset.steve.ROOT / "docs" / "block-assets")
        with tempfile.TemporaryDirectory(prefix="block-assets-check-", dir=asset.steve.ROOT / "build") as name:
            root = Path(name)
            with self.assertRaises(ValueError):
                asset.checked_target(root, "../other.txt")
            with patch.object(Path, "is_symlink", lambda p: p == root / "textures"):
                with self.assertRaises(ValueError):
                    asset.checked_target(root, "textures/stone.png")
        gltf = json.loads((self.asset_root / self.manifest["assets"][0]["file"]).read_text())
        binary = (self.asset_root / Path(self.manifest["assets"][0]["file"]).with_suffix(".bin")).read_bytes()
        corrupted = copy.deepcopy(gltf)
        corrupted["accessors"][0]["count"] = len(binary) + 1
        with self.assertRaises(ValueError):
            read_accessor(corrupted, binary, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=asset.DEFAULT_OUTPUT)
    args = parser.parse_args()
    BlockAssetChecks.asset_root = asset.steve.output_directory(args.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BlockAssetChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
