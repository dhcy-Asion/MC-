"""Check the real vanilla registry export and reject incomplete coverage claims."""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import build_block_registry as registry


class RegistryChecks(unittest.TestCase):
    output = registry.DEFAULT_OUTPUT
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.report = registry.strict_json((cls.output / "block-registry.json").read_bytes())
        cls.blocks = registry.strict_json((cls.output / "reports/blocks.json").read_bytes())
        cls.registries = registry.strict_json((cls.output / "reports/registries.json").read_bytes())
        cls.client, _ = registry.assets.dependencies(registry.assets.read_config(), None, False)

    def test_01_real_registry_counts_ids_defaults_and_resources(self):
        with zipfile.ZipFile(self.client) as archive:
            observed = registry.audit_registry(self.blocks, self.registries, archive)
        for key, value in observed.items():
            self.assertEqual(self.report[key], value)
        self.assertEqual(observed["registeredBlockCount"], 1060)
        self.assertEqual(observed["legalStateCount"], 26684)
        self.assertEqual(observed["resourceFileCount"], 1062)
        self.assertEqual(observed["unregisteredResourceIds"], ["minecraft:glow_item_frame", "minecraft:item_frame"])
        self.assertEqual(observed["missingResourceIds"], [])
        oak = next(row for row in observed["blocks"] if row["id"] == "minecraft:oak_log")
        self.assertEqual(oak["properties"], {"axis": ["x", "y", "z"]})
        self.assertEqual(oak["defaultStateId"], 131)
        self.assertEqual({state["id"] for state in oak["states"]}, {130, 131, 132})

    def test_02_actual_inputs_and_raw_reports_match_provenance(self):
        self.assertEqual(registry.assets.digest(self.client.read_bytes()), self.report["clientSha256"])
        with zipfile.ZipFile(self.client) as archive:
            self.assertEqual(registry.assets.digest(archive.read(registry.MAIN_CLASS)), registry.MAIN_SHA256)
        for name, digest in self.report["sourceReports"].items():
            self.assertEqual(registry.assets.digest((self.output / "reports" / name).read_bytes()), digest)
        self.assertEqual(self.report["sourceReports"]["blocks.json"], registry.BLOCKS_SHA256)
        self.assertTrue(all(value is False for value in self.report["integration"].values()))

    @staticmethod
    def fixture():
        blocks = {"minecraft:air": {"states": [{"id": 0, "default": True}]},
                  "minecraft:test": {"properties": {"axis": ["x", "y"]}, "states": [
                      {"id": 1, "properties": {"axis": "x"}, "default": True},
                      {"id": 2, "properties": {"axis": "y"}}]}}
        registries = {"minecraft:block": {"entries": {key: {"protocol_id": i} for i, key in enumerate(blocks)}}}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for key in blocks:
                archive.writestr("assets/minecraft/blockstates/" + key.split(":")[1] + ".json", "{}")
        return blocks, registries, stream

    def test_03_fixture_demonstrates_complete_product_and_separate_id_spaces(self):
        blocks, registries, stream = self.fixture()
        with zipfile.ZipFile(stream) as archive:
            result = registry.audit_registry(blocks, registries, archive)
        self.assertEqual((result["registeredBlockCount"], result["legalStateCount"]), (2, 3))
        self.assertEqual(result["blocks"][1]["registryId"], 1)

    def test_04_missing_duplicate_illegal_states_and_bad_defaults_are_rejected(self):
        changes = [
            lambda b: b["minecraft:test"]["states"].pop(),
            lambda b: b["minecraft:test"]["states"][1].update(id=1),
            lambda b: b["minecraft:test"]["states"][1].update(id=9),
            lambda b: b["minecraft:test"]["states"][1].update(properties={"axis": "z"}),
            lambda b: b["minecraft:test"]["states"][1].update(properties={"axis": "x"}),
            lambda b: b["minecraft:test"]["states"][1].update(properties={"foreign": "y"}),
            lambda b: b["minecraft:test"]["states"][1].update(default=True),
            lambda b: b["minecraft:test"]["states"][0].update(default=False),
            lambda b: b["minecraft:test"]["states"][0].update(default=1),
            lambda b: b["minecraft:test"]["properties"].update(axis=["x", "x"]),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                blocks, registries, stream = self.fixture()
                change(blocks)
                with zipfile.ZipFile(stream) as archive, self.assertRaises(ValueError):
                    registry.audit_registry(blocks, registries, archive)

    def test_05_registry_mismatch_protocol_collision_and_missing_resource_are_rejected(self):
        blocks, registries, stream = self.fixture()
        missing = copy.deepcopy(registries)
        del missing["minecraft:block"]["entries"]["minecraft:air"]
        collision = copy.deepcopy(registries)
        collision["minecraft:block"]["entries"]["minecraft:test"]["protocol_id"] = 0
        for case in (missing, collision):
            with zipfile.ZipFile(stream) as archive, self.assertRaises(ValueError):
                registry.audit_registry(blocks, case, archive)
        blank = io.BytesIO()
        with zipfile.ZipFile(blank, "w"):
            pass
        with zipfile.ZipFile(blank) as archive, self.assertRaisesRegex(ValueError, "lack client resources"):
            registry.audit_registry(blocks, registries, archive)

    def test_06_json_ambiguity_and_nonfinite_numbers_are_rejected(self):
        for data in (b'{"states":[],"states":[1]}', b'{"id":NaN}', b'[]'):
            with self.assertRaises(ValueError):
                registry.strict_json(data)

    def test_07_bad_output_stops_before_any_published_file(self):
        with self.assertRaises(ValueError):
            registry.preflight(registry.ROOT / "artifacts/blocks", ["report.json"])
        with tempfile.TemporaryDirectory(dir=registry.ROOT / "build", prefix="block-registry-test-") as temp:
            output = Path(temp)
            with self.assertRaises(ValueError):
                registry.publish(output, {"good.json": b"ok", "../outside.json": b"bad"})
            self.assertEqual(list(output.iterdir()), [])
            (output / "block-registry.json.tmp").write_bytes(b"foreign")
            with self.assertRaises(ValueError):
                registry.publish(output, {"reports/blocks.json": b"ok", "block-registry.json": b"new"})
            self.assertFalse((output / "reports").exists())
            self.assertEqual((output / "block-registry.json.tmp").read_bytes(), b"foreign")

    def test_08_fresh_vanilla_generator_produces_identical_registry(self):
        if not self.rebuild:
            self.skipTest("Pass --rebuild to rerun the vanilla data generator")
        relative_client = Path(os.path.relpath(self.client, registry.ROOT))
        java, _ = registry.assets.java_tools(None)
        relative_java_home = Path(os.path.relpath(java.parent.parent, registry.ROOT))
        self.assertFalse(relative_client.is_absolute() or relative_java_home.is_absolute())
        with tempfile.TemporaryDirectory(dir=registry.ROOT / "build", prefix="block-registry-rebuild-") as temp:
            result = subprocess.run([sys.executable, "-B", str(registry.ROOT / "tools/build_block_registry.py"),
                "--output", temp, "--client", str(relative_client), "--java-home", str(relative_java_home)],
                cwd=registry.ROOT, capture_output=True, text=True, timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fresh = registry.strict_json((Path(temp) / "block-registry.json").read_bytes())
            self.assertEqual(fresh, self.report)
            for name in self.report["sourceReports"]:
                self.assertEqual((Path(temp) / "reports" / name).read_bytes(), (self.output / "reports" / name).read_bytes())

    def test_09_canonical_and_hardlinked_final_or_temporary_input_collisions_are_rejected(self):
        for target_name in ("block-registry.json", "block-registry.json.tmp"):
            for hardlinked in (False, True):
                with self.subTest(target=target_name, hardlinked=hardlinked):
                    with tempfile.TemporaryDirectory(dir=registry.ROOT / "build", prefix="block-registry-conflict-") as temp:
                        output = Path(temp)
                        target = output / target_name
                        if hardlinked:
                            source = output / "verified-client.jar"
                            source.write_bytes(b"input retained")
                            target.hardlink_to(source)
                            self.assertNotEqual(source.resolve(), target.resolve())
                            self.assertTrue(target.samefile(source))
                        else:
                            target.write_bytes(b"input retained")
                            source = output / "nonexistent/.." / target_name
                            self.assertEqual(source.resolve(), target.resolve())
                        with self.assertRaisesRegex(ValueError, "conflicts with a generator input"):
                            registry.publish(output, {"reports/blocks.json": b"new", "block-registry.json": b"replace"}, (source,))
                        self.assertFalse((output / "reports").exists())
                        self.assertEqual(target.read_bytes(), b"input retained")
                        if hardlinked:
                            self.assertEqual(source.read_bytes(), b"input retained")

    def test_10_real_client_output_collision_stops_before_generator_and_preserves_input(self):
        before = registry.assets.digest(self.client.read_bytes())
        with tempfile.TemporaryDirectory(dir=registry.ROOT / "build", prefix="block-registry-client-conflict-") as temp:
            output = Path(temp)
            client = output / "block-registry.json"
            client.hardlink_to(self.client)
            with mock.patch.object(registry.subprocess, "run") as generator:
                with self.assertRaisesRegex(ValueError, "conflicts with a generator input"):
                    registry.build(output, client=client)
                generator.assert_not_called()
            self.assertEqual(list(output.iterdir()), [client])
            self.assertEqual(registry.assets.digest(client.read_bytes()), before)
        self.assertEqual(registry.assets.digest(self.client.read_bytes()), before)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RegistryChecks.output)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    RegistryChecks.output = registry.assets.output_directory(args.output)
    RegistryChecks.rebuild = args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistryChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
