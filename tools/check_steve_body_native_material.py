"""Independent offline checks for the single original native-body PAMI control.

Rebuild reads fixed original archives into an isolated output. No test installs,
accesses a game process, calls a native function or changes inventory/save state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_body_native_material as candidate

native, ROOT = candidate.native, candidate.ROOT
NATIVE_SHA = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
OLD_SHA = "01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538"
PAC_SHA = "8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537"
ASSEMBLY_SHA = "2f167887d0abcae102f293d98f34c6421b52d7b5153eb1b9393e2d6da57b8f33"
DRAW_NAMES = ("cd_phm_00_head_0001_01", "cd_phm_00_nude_0001_hand", "cd_phm_00_nude_0001")
BASIC = ("_baseColorTexture", "_normalTexture", "_materialTexture")
DETAIL = ("_skinDetailMaskTexture", "_skinDetailNormalTexture", "_skinDetailMaterialTexture",
          "_skinDetailOpacity", "_skinDetailScale")
DAMAGE = ("_damageBlendingMaterialTexture",)
FLAG = ("_damageBlendingParameter",)
HEAD = BASIC + DETAIL + DAMAGE
HAND = BASIC + ("_heightTexture", "_screenSpaceDisplacementScale") + DETAIL + DAMAGE
EXPECTED_PARAMETERS = (
    (BASIC + DETAIL + ("_faceMaskTexture",) + DAMAGE,
     BASIC + ("_heightTexture", "_screenSpaceDisplacementScale", "_maskTexture") + DETAIL + DAMAGE, HEAD),
    (HEAD, HAND, HEAD), (HEAD + FLAG, HAND + FLAG, HEAD + FLAG),
    (BASIC + FLAG, BASIC + FLAG, BASIC + DETAIL + FLAG),
    (HEAD, HAND + FLAG, HEAD + FLAG), (HEAD + FLAG, HAND + FLAG, HEAD + FLAG),
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def independent_xml_audit(raw):
    """Parse identities and complete ordered parameter names independently."""
    root = ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")
    common = root.findall("SkinnedMeshPropertyCommon")
    require(len(common) == 1 and common[0].attrib == {
        "ReflectObjectXMLDataVersion": "9",
        "_wrinkleFileName": "character/descriptors/wrinkle/cd_phm_00_nude_00_0001.pac.wrinkle.xml"},
        "Original body common metadata differs")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    require(len(variants) == 6, "Body material must have six variants")
    item_bases, textures, counts = (322, 147, 111, 108, 72, 36), set(), []
    for index, variant in enumerate(variants):
        require(variant.attrib == {"Index": str(index), "Version": "Reflection"}, "Variant identity differs")
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        require(len(wrappers) == 3, "Body material must have three draws in each variant")
        row = []
        for draw, wrapper in enumerate(wrappers):
            require(wrapper.attrib == {"ItemID": str(item_bases[index] + draw),
                "_subMeshName": DRAW_NAMES[draw], "_jiggleWindWeight": "0"}, "Wrapper identity differs")
            material = wrapper.find("Material")
            require(material is not None and material.attrib == {
                "Name": "_resourceMaterial", "_materialName": "SkinnedMeshSkin"}, "Native body shader differs")
            vectors = [v for v in material.findall("Vector") if v.get("Name") == "_parameters"]
            require(len(vectors) == 1, "Ambiguous native parameter vector")
            parameters = list(vectors[0])
            require(tuple(p.get("_name") for p in parameters) == EXPECTED_PARAMETERS[index][draw],
                    "Complete native parameter names/order differ")
            require(tuple(p.get("Index") for p in parameters) == tuple(str(i) for i in range(len(parameters))),
                    "Native parameter indexes differ")
            for parameter in parameters:
                name = parameter.get("_name")
                tag = ("MaterialParameterByte4" if name == "_damageBlendingParameter" else
                       "MaterialParameterFloat" if name in ("_screenSpaceDisplacementScale", "_skinDetailOpacity", "_skinDetailScale") else
                       "MaterialParameterTexture")
                require(parameter.tag == tag, "Native parameter type differs")
                if tag == "MaterialParameterTexture":
                    refs = parameter.findall("ResourceReferencePath_ITexture")
                    require(len(refs) == 1 and refs[0].get("_path"), "Missing native texture reference")
                    path = refs[0].get("_path")
                    require(path.startswith("character/texture/") or path == "texture/nonetexture0xffffffff.dds",
                            "Unexpected texture path scope")
                    textures.add(path)
            row.append(len(parameters))
        counts.append(row)
    require(len(textures) == 23 and "texture/nonetexture0xffffffff.dds" in textures,
            "Native body's real texture/sentinel set differs")
    return counts, textures


class NativeBodyMaterialChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = candidate.load_candidate(cls.report_path)
        cls.sources = {key: (cls.output / row[0]).read_bytes() for key, row in candidate.SOURCE_SPECS.items()}
        cls.payload = cls.payloads[candidate.MATERIAL_PATH]

    def test_01_original_bytes_and_four_fixed_previous_body_sources(self):
        expected = {"nativeMaterial": NATIVE_SHA, "previousMaterial": OLD_SHA,
                    "preservedPac": PAC_SHA, "assemblyReport": ASSEMBLY_SHA}
        self.assertEqual({key: hashlib.sha256(raw).hexdigest() for key, raw in self.sources.items()}, expected)
        self.assertEqual(self.payload, self.sources["nativeMaterial"])
        self.assertEqual(len(self.payload), 50017)
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NATIVE_SHA)
        self.assertEqual(len(self.sources["preservedPac"]), 236594)
        old = ET.fromstring("<Root>" + self.sources["previousMaterial"].decode("utf-8-sig") + "</Root>")
        variants = old.findall("./ModelPropertyList/ModelProperty")
        self.assertEqual(len(variants), 6)
        for variant in variants:
            wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
            self.assertEqual(tuple(w.get("_subMeshName") for w in wrappers), DRAW_NAMES)
            self.assertTrue(all(w.find("Material").get("_materialName") == "SkinnedMeshStandard" for w in wrappers))
        previous = json.loads(self.sources["assemblyReport"])
        rows = {row["virtualPath"]: row for row in previous["candidateResources"]}
        self.assertEqual(rows[candidate.MATERIAL_PATH]["sha256"], OLD_SHA)
        self.assertEqual(rows[candidate.PAC_PATH]["sha256"], PAC_SHA)

    def test_02_independent_six_by_three_complete_shader_parameter_and_texture_audit(self):
        counts, textures = independent_xml_audit(self.payload)
        self.assertEqual(counts, [[10,12,9], [9,11,9], [10,12,10], [4,4,9], [9,12,10], [10,12,10]])
        dependency = self.report["dependencyContract"]
        rows = dependency["textureEntries"]
        self.assertEqual(len(rows), 22)
        self.assertEqual({row["virtualPath"] for row in rows}, textures - {"texture/nonetexture0xffffffff.dds"})
        self.assertTrue(all(row["archiveFlags"] == 1 for row in rows))
        self.assertEqual(dependency["requiredDependencyEntries"], 23)
        self.assertEqual(dependency["wrinkleEntry"]["archiveFlags"], 50)
        self.assertFalse(dependency["noneTextureSentinel"]["archiveEntryRequired"])
        self.assertFalse(dependency["noneTextureSentinel"]["runtimeResolutionVerified"])
        self.assertFalse(dependency["dependencyPayloadsDecoded"])
        self.assertEqual(dependency["candidateDependencyOverrides"], [])

    def test_03_pure_loader_has_six_absolute_path_snapshots_and_no_game_or_cdmw_reads(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "import prepare_steve_body_native_material as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('not pure'));"
            "c.read_native_material=forbidden;c.native.load_cdmw=forbidden;c.assembly.load_candidate=forbidden;"
            "r,p,s=c.load_candidate(Path(sys.argv[1]));"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);"
            "assert len(p)==1 and len(s)==6;assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
            "c.orientation.verify_snapshot(s)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.report_path)],
                                cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_04_single_resource_metadata_preserved_pac_empty_armor_and_false_claims(self):
        self.assertEqual(self.report["candidateResources"], [{"kind": "skinnedMaterial",
            "virtualPath": candidate.MATERIAL_PATH, "localFile": "resources/" + candidate.MATERIAL_PATH,
            "sha256": NATIVE_SHA, "payloadSize": 50017, "sourceVirtualPath": candidate.NATIVE_MATERIAL_PATH,
            "templatePath": candidate.NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_SHA,
            "templateArchiveFlags": 50, "archiveFlags": 50}])
        self.assertEqual(set(self.payloads), {candidate.MATERIAL_PATH})
        self.assertTrue(all(type(v) is bool and v is False for v in self.report["integration"].values()))
        contract = self.report["replacementContract"]
        self.assertEqual(contract["previousMaterialSha256"], OLD_SHA)
        self.assertEqual(contract["preservedPacSha256"], PAC_SHA)
        self.assertTrue(contract["otherThirteenResourcesMustBeByteIdentical"])
        self.assertTrue(contract["emptyArmorMustRemainUnchanged"])
        self.assertFalse(contract["wholePackageVerifiedByThisTool"])
        for relative, digest in self.report["files"].items():
            self.assertEqual(hashlib.sha256((self.output / relative).read_bytes()).hexdigest(), digest)
        candidate.orientation.verify_snapshot(self.snapshot)

    def test_05_payload_each_source_and_relabelled_inner_hash_tamper_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="body-material-tamper-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output, output)
            for relative in self.report["files"]:
                path = output / relative
                original = path.read_bytes()
                changed = original[:-1] + bytes([original[-1] ^ 1])
                path.write_bytes(changed)
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
                report = copy.deepcopy(self.report)
                report["files"][relative] = hashlib.sha256(changed).hexdigest()
                for row in report["sources"].values():
                    if row["localFile"] == relative:
                        row["sha256"] = hashlib.sha256(changed).hexdigest()
                (output / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
                path.write_bytes(original)
                (output / candidate.REPORT_NAME).write_bytes(self.report_raw)
            candidate.load_candidate(output / candidate.REPORT_NAME)

    def test_06_manifest_paths_flags_dependency_claims_and_duplicate_keys_fail_closed(self):
        edits = [lambda r: r.update(unreviewed=True), lambda r: r.update(variant="other"),
            lambda r: r["candidateResources"][0].update(archiveFlags=1),
            lambda r: r["candidateResources"][0].update(payloadSize=16149),
            lambda r: r["candidateResources"][0].update(kind="skinnedMesh"),
            lambda r: r["candidateResources"][0].update(localFile="../escape"),
            lambda r: r["candidateResources"][0].update(sourceVirtualPath="../escape"),
            lambda r: r["sources"]["nativeMaterial"].update(localFile="../escape"),
            lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r: r["files"].update({"../escape": "0" * 64}),
            lambda r: r["integration"].update(installed=True), lambda r: r["integration"].update(installed=0),
            lambda r: r["replacementContract"].update(preservedPacSha256="0" * 64),
            lambda r: r["replacementContract"].update(emptyArmorMustRemainUnchanged=False),
            lambda r: r["dependencyContract"]["textureEntries"][0].update(archiveFlags=0),
            lambda r: r["dependencyContract"].update(dependencyPayloadsDecoded=True),
            lambda r: r["dependencyContract"]["noneTextureSentinel"].update(runtimeResolutionVerified=True)]
        with tempfile.TemporaryDirectory(prefix="body-material-manifest-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output, output)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (output / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(edit=repr(edit)), self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
            for raw in (b'{"schemaVersion":1,"schemaVersion":1}', json.dumps(self.report).encode()):
                (output / candidate.REPORT_NAME).write_bytes(raw)
                with self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.load_candidate(ROOT / "docs" / candidate.REPORT_NAME)

    def test_07_independent_xml_audit_rejects_variant_shader_parameter_and_wrapper_changes(self):
        mutants = [self.payload.replace(b'Index="5" Version="Reflection"', b'Index="6" Version="Reflection"', 1),
            self.payload.replace(b'SkinnedMeshSkin"', b'SkinnedMeshStandard"', 1),
            self.payload.replace(b'_subMeshName="cd_phm_00_nude_0001"', b'_subMeshName="wrong_draw"', 1),
            self.payload.replace(b'_name="_heightTexture"', b'_name="_unknownParameter"', 1),
            self.payload.replace(b'_jiggleWindWeight="0"', b'_jiggleWindWeight="1"', 1)]
        for raw in mutants:
            self.assertNotEqual(raw, self.payload)
            with self.subTest(sha=hashlib.sha256(raw).hexdigest()), self.assertRaises(ValueError):
                independent_xml_audit(raw)

    def test_08_output_protection_stale_snapshot_and_size_bound(self):
        with tempfile.TemporaryDirectory(prefix="body-material-output-", dir=ROOT / "build") as temporary:
            directory = Path(temporary)
            sentinel = directory / "keep"
            sentinel.write_bytes(b"keep")
            with mock.patch.object(native, "load_cdmw", side_effect=AssertionError("native read")), \
                 mock.patch.object(candidate.assembly, "load_candidate", side_effect=AssertionError("assembly read")):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    candidate.prepare(output=directory)
                for base in (ROOT / "build/cdmw-fixed-source", candidate.DEFAULT_ASSEMBLY_REPORT.parent,
                             ROOT / "build/steve-clothing-control"):
                    with self.assertRaisesRegex(ValueError, "overlaps"):
                        candidate.prepare(output=base / "new-output")
            self.assertEqual(sentinel.read_bytes(), b"keep")
            fixture = directory / "fixture"
            shutil.copytree(self.output, fixture)
            _, _, snapshot = candidate.load_candidate(fixture / candidate.REPORT_NAME)
            payload = fixture / ("resources/" + candidate.MATERIAL_PATH)
            payload.write_bytes(self.payload[:-1] + bytes([self.payload[-1] ^ 1]))
            with self.assertRaises(ValueError):
                candidate.orientation.verify_snapshot(snapshot)
            (fixture / candidate.REPORT_NAME).write_bytes(b" " * 131073)
            with self.assertRaises(ValueError):
                candidate.load_candidate(fixture / candidate.REPORT_NAME)

    def test_09_original_archive_version_unique_entries_flags_paz_bounds_and_payload_gates(self):
        native.load_cdmw(ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps")
        from cdmw.core import archive_format, archive_extraction
        with tempfile.TemporaryDirectory(prefix="body-material-archive-", dir=ROOT / "build") as temporary:
            game = Path(temporary)
            (game / "0009").mkdir()
            (game / "bin64").mkdir()
            exe, index, paz = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt", game / "0009/0.paz"
            for path in (exe, index, paz):
                path.write_bytes(b"isolated")
            flags = {candidate.NATIVE_MATERIAL_PATH: 50, **candidate.DEPENDENCY_FLAGS}
            entries = [SimpleNamespace(path=path, flags=flag, paz_file=paz) for path, flag in flags.items()]
            def good_hash(path):
                return native.EXE_SHA256 if Path(path) == exe else candidate.INDEX_SHA256
            with mock.patch.object(native, "file_hash", side_effect=good_hash), \
                 mock.patch.object(archive_format, "parse_archive_pamt", return_value=entries) as parse, \
                 mock.patch.object(archive_extraction, "read_archive_entry_raw_data", return_value=b"encoded") as read, \
                 mock.patch.object(archive_extraction, "_decode_archive_entry_data", return_value=(self.payload, None)) as decode:
                self.assertEqual(candidate.read_native_material(game), self.payload)
                read.assert_called_once_with(entries[0])  # No texture payload is extracted.
                read.reset_mock()
                with mock.patch.object(native, "file_hash", return_value="0" * 64), self.assertRaises(ValueError):
                    candidate.read_native_material(game)
                read.assert_not_called()
                for raw in (entries[:-1], entries + [entries[1]]):
                    parse.return_value = raw
                    with self.assertRaises(ValueError):
                        candidate.read_native_material(game)
                parse.return_value = entries
                for entry, changed in ((entries[0], 1), (entries[1], 0), (entries[-1], 1)):
                    old = entry.flags
                    entry.flags = changed
                    with self.assertRaises(ValueError):
                        candidate.read_native_material(game)
                    entry.flags = old
                entries[1].paz_file = game / "foreign.paz"
                with self.assertRaises(ValueError):
                    candidate.read_native_material(game)
                entries[1].paz_file = game / "0009/missing.paz"
                with self.assertRaises(ValueError):
                    candidate.read_native_material(game)
                entries[1].paz_file = paz
                read.assert_not_called()
                decode.return_value = (b"wrong PAMI", None)
                with self.assertRaises(ValueError):
                    candidate.read_native_material(game)
        with tempfile.TemporaryDirectory(prefix="body-material-race-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            with mock.patch.object(native, "load_cdmw"), \
                 mock.patch.object(candidate, "read_native_material", side_effect=[self.payload, b"changed"]):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    candidate.prepare(output=output)
            self.assertFalse(output.exists())

    def test_10_real_original_archive_rebuild_is_identical_and_existing_inputs_stay_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for isolated generation from real original archives")
        from prepare_steve_head_native_material import load_candidate as load_head, DEFAULT_OUTPUT as head_output, REPORT_NAME as head_name
        from prepare_steve_clothing_control import load_candidate as load_clothing, DEFAULT_OUTPUT as clothes_output, REPORT_NAME as clothes_name
        snapshots = [self.snapshot, candidate.assembly.load_candidate(candidate.DEFAULT_ASSEMBLY_REPORT)[2],
                     load_head(head_output / head_name)[2], load_clothing(clothes_output / clothes_name)[2]]
        with tempfile.TemporaryDirectory(prefix="body-material-rebuild-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/prepare_steve_body_native_material.py"),
                "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, payloads, _ = candidate.load_candidate(output / candidate.REPORT_NAME)
            self.assertEqual((output / candidate.REPORT_NAME).read_bytes(), self.report_raw)
            self.assertEqual((report, payloads), (self.report, self.payloads))
        for snapshot in snapshots:
            candidate.orientation.verify_snapshot(snapshot)
        native.verify_source(ROOT / "build/cdmw-fixed-source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    NativeBodyMaterialChecks.output, NativeBodyMaterialChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeBodyMaterialChecks))
    if result.wasSuccessful():
        print(json.dumps({"candidateResources": NativeBodyMaterialChecks.report["candidateResources"],
            "independentParameterCounts": independent_xml_audit(NativeBodyMaterialChecks.payload)[0],
            "nativeRenderingVerified": False, "dynamicMaskVerified": False}, indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
