"""Verify all legal vanilla state/model selections against original Java classes.

Only reads pinned assets and uses fresh ignored build directories. --rebuild also
reruns the original Java oracle; no Minecraft world or game service is started.
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import build_block_state_models as states


class StateModelChecks(unittest.TestCase):
    output = states.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report = states.strict_json((cls.output / "block-state-models-report.json").read_bytes())
        cls.selection = states.strict_json((cls.output / "block-state-models.json").read_bytes())
        cls.dependencies = states.strict_json((cls.output / "model-dependencies.json").read_bytes())["models"]
        cls.oracle = states.strict_json((cls.output / "selection-oracle.json").read_bytes())
        cls.cases = states.strict_json((cls.output / "contract-cases.json").read_bytes())
        cls.blocks = {b["id"]: b for b in cls.selection["blocks"]}
        cls.registry = states.strict_json((states.REGISTRY_DIR / "block-registry.json").read_bytes())
        cls.client, cls.jars = states.assets.dependencies(states.assets.read_config(), None, False)

    def test_01_complete_registry_ids_properties_and_defaults(self):
        self.assertEqual(len(self.blocks), 1060)
        ids = []
        for source in self.registry["blocks"]:
            block = self.blocks[source["id"]]
            for key in ("registryId", "defaultStateId", "properties", "blockstateResource", "blockstateResourceSha256"):
                self.assertEqual(block[key], source[key])
            expected = {s["id"]: s for s in source["states"]}
            self.assertEqual(len(block["states"]), len(expected))
            for state in block["states"]:
                raw = expected[state["id"]]
                self.assertEqual(state["properties"], raw.get("properties", {}))
                self.assertEqual(state.get("default", False), raw.get("default", False))
                ids.append(state["id"])
        self.assertEqual(sorted(ids), list(range(26684)))
        self.assertEqual(self.selection["registeredBlockCount"], 1060)
        self.assertEqual(self.selection["legalStateCount"], 26684)
        self.assertNotIn("minecraft:item_frame", self.blocks)
        self.assertNotIn("minecraft:glow_item_frame", self.blocks)

    def test_02_all_states_groups_and_choices_match_original_java(self):
        states.verify_oracle(copy.deepcopy(self.selection["blocks"]), self.oracle, self.cases["results"])
        self.assertEqual(self.report["oracle"]["allStatesCompared"], 26684)
        self.assertEqual(self.report["oracle"]["mismatchedStates"], 0)
        self.assertEqual(self.report["oracle"]["parsedChoicesCompared"], 6762)
        self.assertEqual(self.report["oracle"]["contractCasesCompared"], 21)
        self.assertFalse(self.report["oracle"]["worldStarted"])

    def test_03_every_group_preserves_official_source_choices(self):
        group_count = choice_count = multipart_count = 0
        with zipfile.ZipFile(self.client) as archive:
            for block in self.blocks.values():
                raw = json.loads(archive.read(block["blockstateResource"]))
                if "variants" in raw:
                    groups = [(key, None, value) for key, value in raw["variants"].items()]
                    self.assertEqual(block["selectorKind"], "variants")
                else:
                    multipart_count += 1
                    groups = [(None, part.get("when"), part["apply"]) for part in raw["multipart"]]
                    self.assertEqual(block["selectorKind"], "multipart")
                self.assertEqual(len(block["groups"]), len(groups))
                for index, ((selector, condition, value), group) in enumerate(zip(groups, block["groups"])):
                    self.assertEqual(group["group"], index)
                    self.assertEqual(group.get("selector"), selector)
                    self.assertEqual(group.get("when"), condition)
                    if "multipart" in raw:
                        self.assertEqual(group["whenPresent"], "when" in raw["multipart"][index])
                    original = value if isinstance(value, list) else [value]
                    expected = [{"choice": n, "model": v["model"] if ":" in v["model"] else "minecraft:" + v["model"],
                                 "x": v.get("x", 0), "y": v.get("y", 0), "uvlock": v.get("uvlock", False),
                                 "weight": v.get("weight", 1)} for n, v in enumerate(original)]
                    self.assertEqual(group["choices"], expected)
                    group_count += 1
                    choice_count += len(original)
        self.assertEqual((group_count, choice_count, multipart_count), (6529, 6762, 70))
        self.assertEqual((self.selection["groupCount"], self.selection["modelChoiceCount"]), (6529, 6762))

    def test_04_fence_composes_matching_parts_and_log_axes_remain_distinct(self):
        fence = self.blocks["minecraft:oak_fence"]
        for state in fence["states"]:
            expected = [0] + [i for i, side in enumerate(("north", "east", "south", "west"), 1)
                              if state["properties"][side] == "true"]
            self.assertEqual(state["groups"], expected)
        log = self.blocks["minecraft:oak_log"]
        expected = {"x": (90, 90), "y": (0, 0), "z": (90, 0)}
        self.assertEqual(len(log["states"]), 3)
        for state in log["states"]:
            self.assertEqual(len(state["groups"]), 1)
            choices = log["groups"][state["groups"][0]]["choices"]
            self.assertEqual(len(choices), 1)
            self.assertEqual((choices[0]["x"], choices[0]["y"]), expected[state["properties"]["axis"]])

    def test_05_weighted_alternatives_are_not_randomly_collapsed(self):
        multiple = [g for b in self.blocks.values() for g in b["groups"] if len(g["choices"]) > 1]
        nonuniform = [g for b in self.blocks.values() for g in b["groups"] if any(c["weight"] != 1 for c in g["choices"])]
        self.assertEqual(len(multiple), 75)
        self.assertEqual(len(nonuniform), 6)
        self.assertTrue(any(len({c["weight"] for c in g["choices"]}) > 1 for g in nonuniform))
        for b in self.blocks.values():
            for state in b["states"]:
                self.assertNotIn("model", state)
                self.assertNotIn("selectedChoice", state)
                self.assertEqual(state["groups"], sorted(set(state["groups"])))
                self.assertTrue(all(0 <= i < len(b["groups"]) for i in state["groups"]))

    def test_06_special_renderers_and_legitimate_empty_multipart_are_preserved(self):
        counts = collections.Counter(s["renderShape"] for b in self.blocks.values() for s in b["states"])
        self.assertEqual(counts, {"MODEL": 24334, "INVISIBLE": 1934, "ENTITYBLOCK_ANIMATED": 416})
        self.assertEqual(self.selection["renderShapeStateCounts"], dict(counts))
        for name in ("air", "water", "lava", "barrier", "moving_piston"):
            self.assertEqual({s["renderShape"] for s in self.blocks["minecraft:" + name]["states"]}, {"INVISIBLE"})
        self.assertEqual({s["renderShape"] for s in self.blocks["minecraft:chest"]["states"]}, {"ENTITYBLOCK_ANIMATED"})
        self.assertEqual(self.dependencies["minecraft:block/chest"]["geometryKind"], "empty")
        wall = self.blocks["minecraft:cobblestone_wall"]
        empty = [s for s in wall["states"] if s["properties"]["up"] == "false"
                 and all(s["properties"][side] == "none" for side in ("north", "east", "south", "west"))]
        self.assertEqual(len(empty), 2)  # Dry and waterlogged legal states have no wall parts.
        self.assertTrue(all(s["groups"] == [] and s["renderShape"] == "MODEL" for s in empty))
        self.assertTrue(all(v is False for v in self.selection["integration"].values()))
        self.assertEqual(self.selection["integration"], self.report["integration"])

    def test_07_dependency_files_textures_animation_and_geometry_are_truthful(self):
        selected = {c["model"] for b in self.blocks.values() for g in b["groups"] for c in g["choices"]}
        self.assertEqual(selected, set(self.dependencies))
        self.assertEqual(len(selected), 1921)
        self.assertEqual(self.selection["uniqueModelCount"], 1921)
        with zipfile.ZipFile(self.client) as archive:
            resources = states.models.Resources(archive)
            for model, dep in self.dependencies.items():
                expected = resources.dependencies(model)
                self.assertEqual({k: dep[k] for k in expected}, expected)
                self.assertEqual(dep["missing"], [])
                self.assertFalse(dep["nativeIntegrated"])
                self.assertEqual(dep["geometryKind"], "builtin" if dep["builtins"] else "empty" if not dep["elementCount"] else "json_elements")
                for path, digest in dep["modelFiles"].items():
                    self.assertEqual(states.assets.digest(archive.read(path)), digest)
                for path, metadata in dep["textures"].items():
                    self.assertEqual(states.assets.digest(archive.read(path)), metadata["sha256"])
                    if "mcmetaSha256" in metadata:
                        raw = archive.read(path + ".mcmeta")
                        self.assertEqual(states.assets.digest(raw), metadata["mcmetaSha256"])
                        self.assertEqual(json.loads(raw).get("animation"), metadata["animation"])
        self.assertEqual(collections.Counter(d["geometryKind"] for d in self.dependencies.values()), {"json_elements": 1849, "empty": 72})

    def test_08_all_pins_outputs_and_original_class_hashes_match(self):
        for filename, digest in self.report["files"].items():
            self.assertEqual(states.assets.digest((self.output / filename).read_bytes()), digest)
        pins = self.report["sourcePins"]
        self.assertEqual(states.assets.digest(self.client.read_bytes()), pins["clientSha256"])
        for name, path in (("registryReportSha256", states.REGISTRY_DIR / "block-registry.json"),
                           ("resourceCoverageSha256", states.COVERAGE), ("configSha256", states.assets.CONFIG)):
            self.assertEqual(states.assets.digest(path.read_bytes()), pins[name])
        mapping = states.MAPPINGS.read_bytes()
        self.assertEqual(states.assets.digest(mapping), pins["officialMappings"]["sha256"])
        self.assertEqual(states.assets.digest(mapping, "sha1"), pins["officialMappings"]["sha1"])
        self.assertEqual(len(mapping), pins["officialMappings"]["size"])
        self.assertEqual(states.assets.digest(states.JAVA_READER.encode()), pins["javaReaderSourceSha256"])
        with zipfile.ZipFile(self.client) as archive:
            self.assertEqual({n: states.assets.digest(archive.read(n)) for n in states.ENGINE_CLASSES}, pins["selectionClasses"])
        for name, digest in pins["sourceReports"].items():
            self.assertEqual(states.assets.digest((states.REGISTRY_DIR / "reports" / name).read_bytes()), digest)
        for jar in self.jars:
            self.assertEqual(states.assets.digest(jar.read_bytes()), pins["libraries"][jar.name])

    def test_09_original_predicate_edge_cases_are_not_guessed(self):
        oak = next(b for b in self.registry["blocks"] if b["id"] == "minecraft:oak_log")
        result = states.case_results(self.cases["cases"], oak)
        self.assertEqual(result, self.cases["results"])
        self.assertEqual(result, self.oracle["cases"])
        by_name = {r["name"]: r for r in result}
        self.assertEqual(by_name["variant_last_duplicate"]["states"], [131])
        self.assertEqual(by_name["part_negated_union"]["states"], [132])
        self.assertEqual(by_name["part_nested"]["states"], [130])
        self.assertTrue(by_name["part_empty_pipe_single_invalid"]["error"])
        self.assertEqual(by_name["part_omit_empty_multi"]["states"], [130, 131])
        self.assertEqual(by_name["empty_and_true"]["states"], [130, 131, 132])
        self.assertEqual(by_name["empty_or_false"]["states"], [])

    def test_10_oracle_disagreements_are_rejected(self):
        changes = (
            lambda o: o.update(registeredBlockCount=1059),
            lambda o: o["blocks"].pop(),
            lambda o: o["blocks"][0].update(registryId=-1),
            lambda o: o["blocks"][0]["choices"][0][0].update(weight=8),
            lambda o: o["blocks"][0]["states"][0].update(groups=[]),
            lambda o: o["blocks"][0]["states"][0].update(properties={"absent": "true"}),
            lambda o: o["blocks"][0]["states"][0].update(renderShape="CUBE"),
            lambda o: o["cases"].pop(),
        )
        for change in changes:
            with self.subTest(change=changes.index(change)):
                oracle = copy.deepcopy(self.oracle)
                change(oracle)
                with self.assertRaises(ValueError):
                    states.verify_oracle(copy.deepcopy(self.selection["blocks"]), oracle, self.cases["results"])

    def test_11_ambiguous_json_illegal_states_and_overlapping_variants_rejected(self):
        for raw in (b'[]', b'{"x":0,"x":1}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError):
                states.strict_json(raw)
        oak = copy.deepcopy(self.blocks["minecraft:oak_log"])
        for variants in ({"axis=x": {"model": "block/oak_log"}},
                         {"": {"model": "block/oak_log"}, "axis=x": {"model": "block/oak_log"}}):
            with self.assertRaisesRegex(ValueError, "overlap or leave"):
                states.select_block(oak, {"variants": variants})
        oak["states"][0]["properties"]["axis"] = "invalid"
        with self.assertRaisesRegex(ValueError, "not legal"):
            states.select_block(oak, {"variants": {"": {"model": "block/oak_log"}}})
        for choice in ({"model": "../bad"}, {"model": "block/stone", "weight": 0},
                       {"model": "block/stone", "uvlock": 1}, {"model": "block/stone", "x": 45},
                       {"model": "block/stone", "weight": True}, []):
            with self.assertRaises(ValueError):
                states.model_choices(choice)

    def test_12_output_existing_public_and_input_tree_conflicts_stop_early(self):
        with mock.patch.object(states.assets, "dependencies") as dependencies:
            for path in (states.ROOT / "artifacts/state-models", states.DEFAULT_OUTPUT,
                         states.REGISTRY_DIR / "new-output", states.COVERAGE.parent / "new-output"):
                with self.subTest(path=str(path)), self.assertRaises(ValueError):
                    states.build(path)
            dependencies.assert_not_called()
        with tempfile.TemporaryDirectory(dir=states.ROOT / "build", prefix="state-model-output-check-") as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            retained = source / "data.json"
            retained.write_bytes(b"source retained")
            for path in (root, source, source / "child"):
                with self.assertRaises(ValueError):
                    states.preflight(path, (retained,))
            self.assertEqual(retained.read_bytes(), b"source retained")
            self.assertFalse((source / "child").exists())

    def test_13_source_hash_and_change_detection_preserve_inputs(self):
        with tempfile.TemporaryDirectory(dir=states.ROOT / "build", prefix="state-model-input-check-") as temporary:
            source = Path(temporary) / "source"
            source.write_bytes(b"known input")
            snapshots = {}
            states.fixed_read(source, states.assets.digest(b"known input"), snapshots)
            states.verify_snapshots(snapshots)
            source.write_bytes(b"changed input")
            with self.assertRaisesRegex(ValueError, "changed during export"):
                states.verify_snapshots(snapshots)
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                states.fixed_read(source, states.assets.digest(b"known input"), {})
            self.assertEqual(source.read_bytes(), b"changed input")

    def test_14_real_java_rebuild_is_byte_identical_with_relative_inputs(self):
        if not self.rebuild:
            self.skipTest("Pass --rebuild for a fresh original Java oracle")
        java, _ = states.assets.java_tools(None)
        with tempfile.TemporaryDirectory(dir=states.ROOT / "build", prefix="state-model-rebuild-check-") as temporary:
            output = Path(temporary) / "fresh"
            command = [sys.executable, "-B", str(states.ROOT / "tools/build_block_state_models.py"),
                       "--output", str(output), "--client", os.path.relpath(self.client, states.ROOT),
                       "--java-home", os.path.relpath(java.parent.parent, states.ROOT)]
            result = subprocess.run(command, cwd=states.ROOT, capture_output=True, text=True, timeout=240,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = set(self.report["files"]) | {"block-state-models-report.json"}
            self.assertEqual({p.name for p in output.iterdir()}, names)
            for name in names:
                self.assertEqual((output / name).read_bytes(), (self.output / name).read_bytes(), name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=StateModelChecks.output)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    StateModelChecks.output = states.assets.output_directory(args.output)
    StateModelChecks.rebuild = args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StateModelChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
