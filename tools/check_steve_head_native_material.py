"""Independent offline checks for the byte-identical single native-head PAMI.

The rebuild mode reads original archives through the gated generator. No test
installs anything, accesses a process, starts a service, or changes user state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_head_native_material as candidate
import prepare_native_steve as native

ROOT = native.ROOT
NATIVE_SHA = "440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5"
OLD_SHA = "442b56d40caf42e31f082123577483d195e107504a6cb85bcba556a3638c8ff9"
PAC_SHA = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
ROOT_REPORT_SHA = "2d850067c97a7d44762eadb68154dbbb992aa2010f3851b63e3b0e8dfd6085a8"
DRAW_NAMES = ("cd_phm_00_head_0001_macduff_eyecover", "cd_phm_00_head_0001_macduff")
BASE_PARAMETERS = ("_baseColorTexture", "_normalTexture", "_maskTexture", "_skinDetailMaskTexture",
    "_wrinkleMaskTexture0", "_wrinkleMaskTexture1", "_wrinkleColorTexture0", "_wrinkleColorTexture1",
    "_wrinkleNormalTexture0", "_wrinkleNormalTexture1")
DAMAGE_PARAMETERS = ("_damageBlendingDiffuseTexture", "_damageBlendingNormalTexture",
    "_damageBlendingMaterialTexture", "_damageBlendingParameter")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def independent_xml_audit(raw):
    """Check actual XML identities, ordered shaders and complete parameter names."""
    root = ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")
    common = root.findall("SkinnedMeshPropertyCommon")
    require(len(common) == 1 and common[0].attrib == {
        "ReflectObjectXMLDataVersion": "9",
        "_wrinkleFileName": "character/descriptors/wrinkle/cd_phm_00_head_00_0001_kliff.pac.wrinkle.xml"},
        "Native wrinkle common metadata differs")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    require(len(variants) == 3, "Native material must have exactly three variants")
    result = []
    for index, variant in enumerate(variants):
        require(variant.attrib == {"Index":str(index), "Version":"Reflection"}, "Variant identity differs")
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        require(len(wrappers) == 2 and tuple(w.get("_subMeshName") for w in wrappers) == DRAW_NAMES,
                "Native material must have exactly the eye/main draw mapping")
        shaders = ("SkinnedMeshEyeCover", "SkinnedMeshSkinWrinkleAging" if index == 2 else "SkinnedMeshSkinWrinkle")
        item_ids = (("180","181"),("36","37"),("14","15"))[index]
        parameter_counts = []
        for draw, wrapper in enumerate(wrappers):
            require(wrapper.attrib == {"ItemID":item_ids[draw], "_subMeshName":DRAW_NAMES[draw], "_jiggleWindWeight":"0"},
                    "Native material wrapper metadata differs")
            material = wrapper.find("Material")
            require(material is not None and material.attrib == {
                "Name":"_resourceMaterial", "_materialName":shaders[draw]}, "Native shader differs")
            vectors = [v for v in material.findall("Vector") if v.get("Name") == "_parameters"]
            require(len(vectors) == 1, "Ambiguous native parameter vector")
            parameters = list(vectors[0])
            names = ("_normalTexture",) if draw == 0 else BASE_PARAMETERS + (
                ("_transientAgingColorTexture", "_transientAgingNormalTexture") if index == 2 else ()) + DAMAGE_PARAMETERS
            require(tuple(p.get("_name") for p in parameters) == names, "Complete native parameters differ")
            require(tuple(p.get("Index") for p in parameters) == tuple(str(i) for i in range(len(names))),
                    "Native parameter ordering differs")
            for number, parameter in enumerate(parameters):
                expected_tag = "MaterialParameterByte4" if draw == 1 and number == len(parameters)-1 else "MaterialParameterTexture"
                require(parameter.tag == expected_tag, "Native parameter type differs")
                if parameter.tag == "MaterialParameterTexture":
                    refs = parameter.findall("ResourceReferencePath_ITexture")
                    require(len(refs) == 1 and refs[0].get("_path"), "Missing native texture reference")
            parameter_counts.append(len(parameters))
        result.append({"index":index, "shaders":list(shaders), "parameterCounts":parameter_counts})
    return result


class NativeHeadMaterialChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = candidate.load_candidate(cls.report_path)
        cls.sources = {key:(cls.output / row[0]).read_bytes() for key,row in candidate.SOURCE_SPECS.items()}
        cls.payload = cls.payloads[candidate.MATERIAL_PATH]

    def test_01_exact_original_bytes_and_fixed_previous_pac_material_provenance(self):
        expected = {"nativeMaterial":NATIVE_SHA, "previousMaterial":OLD_SHA,
                    "preservedPac":PAC_SHA, "headRootReport":ROOT_REPORT_SHA}
        self.assertEqual({k:hashlib.sha256(v).hexdigest() for k,v in self.sources.items()},expected)
        self.assertEqual(self.payload, self.sources["nativeMaterial"])
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NATIVE_SHA)
        self.assertEqual(len(self.payload),16149)
        old = ET.fromstring("<Root>"+self.sources["previousMaterial"].decode("utf-8-sig")+"</Root>")
        old_variants = old.findall("./ModelPropertyList/ModelProperty")
        self.assertEqual(len(old_variants),6)
        for variant in old_variants:
            wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
            self.assertEqual(tuple(w.get("_subMeshName") for w in wrappers),DRAW_NAMES)
            self.assertTrue(all(w.find("Material").get("_materialName") == "SkinnedMeshStandard" for w in wrappers))
        pac = self.sources["preservedPac"]
        self.assertEqual(len(pac),96721)
        self.assertEqual(struct.unpack_from("<I",pac,80)[0],2)
        self.assertEqual(pac[84],3)
        self.assertEqual(struct.unpack_from("<3H3I",pac,326),(48,48,48,72,72,72))

    def test_02_independent_three_variant_shader_parameter_and_dependency_audit(self):
        audit = independent_xml_audit(self.payload)
        self.assertEqual([r["parameterCounts"] for r in audit],[[1,14],[1,14],[1,16]])
        self.assertEqual(self.payload,self.sources["nativeMaterial"])
        self.assertEqual(self.report["audit"]["variantCount"],3)
        self.assertTrue(self.report["audit"]["nativeTexturesAndWrinkleReferencesUnchanged"])

    def test_03_pure_loader_imports_no_cdmw_and_reads_no_game(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "from unittest.mock import patch;import prepare_steve_head_native_material as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('game read'));"
            "c.read_native_material=forbidden;c.native.load_cdmw=forbidden;"
            "r,p,s=c.load_candidate(Path(sys.argv[1]));"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);"
            "assert len(p)==1;assert all(isinstance(k,Path) for k in s)")
        result = subprocess.run([sys.executable,"-B","-c",code,str(self.report_path)],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_04_exact_single_resource_metadata_and_false_claims(self):
        row = self.report["candidateResources"]
        self.assertEqual(row,[{"kind":"skinnedMaterial", "virtualPath":candidate.MATERIAL_PATH,
            "localFile":"resources/"+candidate.MATERIAL_PATH, "sha256":NATIVE_SHA, "payloadSize":16149,
            "sourceVirtualPath":candidate.NATIVE_MATERIAL_PATH, "templatePath":candidate.NATIVE_MATERIAL_PATH,
            "templateSha256":NATIVE_SHA, "templateArchiveFlags":50, "archiveFlags":50}])
        self.assertEqual(set(self.payloads),{candidate.MATERIAL_PATH})
        self.assertTrue(all(type(v) is bool and v is False for v in self.report["integration"].values()))
        contract = self.report["replacementContract"]
        self.assertEqual(contract["previousMaterialSha256"],OLD_SHA)
        self.assertEqual(contract["preservedPacSha256"],PAC_SHA)
        self.assertFalse(contract["wholePackageVerifiedByThisTool"])
        self.assertTrue(contract["otherElevenResourcesMustBeByteIdentical"])
        for relative,expected in self.report["files"].items():
            self.assertEqual(hashlib.sha256((self.output / relative).read_bytes()).hexdigest(),expected)
        candidate.orientation.verify_snapshot(self.snapshot)

    def test_05_payload_and_every_fixed_source_tamper_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="head-material-tamper-",dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output,output)
            relatives = list(self.report["files"])
            for relative in relatives:
                path = output / relative
                original = path.read_bytes()
                path.write_bytes(original[:-1]+bytes([original[-1]^1]))
                with self.subTest(relative=relative),self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
                path.write_bytes(original)
            candidate.load_candidate(output / candidate.REPORT_NAME)

    def test_06_manifest_fields_flags_path_escape_and_duplicate_keys_are_rejected(self):
        edits = [lambda r:r.update(unreviewedField=True),lambda r:r.update(variant="unreviewed"),
            lambda r:r["candidateResources"][0].update(archiveFlags=1),
            lambda r:r["candidateResources"][0].update(kind="skinnedMesh"),
            lambda r:r["candidateResources"][0].update(localFile="../escape"),
            lambda r:r["candidateResources"][0].update(templatePath="../escape"),
            lambda r:r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r:r["sources"]["nativeMaterial"].update(localFile="../escape"),
            lambda r:r["files"].update({"../escape":"0"*64}),
            lambda r:r["integration"].update(installed=True),lambda r:r["integration"].update(installed=0),
            lambda r:r["replacementContract"].update(preservedPacSha256="0"*64)]
        with tempfile.TemporaryDirectory(prefix="head-material-manifest-",dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output,output)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (output / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(edit=repr(edit)),self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
            duplicate = b'{"schemaVersion":1,"schemaVersion":1}'
            (output / candidate.REPORT_NAME).write_bytes(duplicate)
            with self.assertRaises(ValueError):
                candidate.load_candidate(output / candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.load_candidate(ROOT / "docs" / candidate.REPORT_NAME)

    def test_07_independent_xml_audit_rejects_semantically_invalid_variants_and_shaders(self):
        mutants = [self.payload.replace(b'Index="2" Version="Reflection"',b'Index="3" Version="Reflection"',1),
            self.payload.replace(b'SkinnedMeshSkinWrinkle"',b'SkinnedMeshStandard"',1),
            self.payload.replace(b'_subMeshName="cd_phm_00_head_0001_macduff"',b'_subMeshName="wrong_head_draw"',1),
            self.payload.replace(b'_name="_damageBlendingParameter"',b'_name="_unknownParameter"',1),
            self.payload.replace(b'_jiggleWindWeight="0"',b'_jiggleWindWeight="1"',1)]
        for data in mutants:
            self.assertNotEqual(data,self.payload)
            with self.subTest(sha=hashlib.sha256(data).hexdigest()),self.assertRaises(ValueError):
                independent_xml_audit(data)

    def test_08_existing_output_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="head-material-output-",dir=ROOT / "build") as temporary:
            output = Path(temporary)
            sentinel = output / "keep.txt"
            sentinel.write_bytes(b"keep")
            result = subprocess.run([sys.executable,"-B",str(ROOT / "tools/prepare_steve_head_native_material.py"),
                "--output",str(output)],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("already exists",result.stderr)
            self.assertEqual(sentinel.read_bytes(),b"keep")
            self.assertEqual({p.name for p in output.iterdir()},{"keep.txt"})

    def test_09_archive_gate_rejects_wrong_version_flags_escape_and_payload(self):
        native.load_cdmw(ROOT / "build/cdmw-fixed-source",ROOT / "build/cdmw-deps")
        with tempfile.TemporaryDirectory(prefix="head-material-archive-",dir=ROOT / "build") as temporary:
            game = Path(temporary)
            (game / "0009").mkdir()
            (game / "bin64").mkdir()
            index,exe,paz = game / "0009/0.pamt",game / "bin64/CrimsonDesert.exe",game / "0009/0.paz"
            for path in (index,exe,paz):
                path.write_bytes(b"isolated")
            entry = SimpleNamespace(path=candidate.NATIVE_MATERIAL_PATH,flags=50,paz_file=str(paz))
            from cdmw.core import archive_format,archive_extraction
            def good_hash(path):
                return native.EXE_SHA256 if Path(path) == exe else candidate.INDEX_SHA256
            with mock.patch.object(native,"file_hash",side_effect=good_hash), \
                 mock.patch.object(archive_format,"parse_archive_pamt",return_value=[entry]), \
                 mock.patch.object(native,"select_unique_entries",return_value={candidate.NATIVE_MATERIAL_PATH:entry}), \
                 mock.patch.object(archive_extraction,"read_archive_entry_raw_data",return_value=b"encoded") as read, \
                 mock.patch.object(archive_extraction,"_decode_archive_entry_data",return_value=(self.payload,None)) as decode:
                self.assertEqual(candidate.read_native_material(game),self.payload)
                read.reset_mock()
                with mock.patch.object(native,"file_hash",return_value="0"*64),self.assertRaises(ValueError):
                    candidate.read_native_material(game)
                read.assert_not_called()
                for flags in (1,0,48):
                    entry.flags = flags
                    with self.subTest(flags=flags),self.assertRaises(ValueError):
                        candidate.read_native_material(game)
                read.assert_not_called()
                entry.flags = 50
                entry.paz_file = str(game / "foreign.paz")
                with self.assertRaises(ValueError):
                    candidate.read_native_material(game)
                read.assert_not_called()
                entry.paz_file = str(paz)
                decode.return_value = (b"not the original PAMI",None)
                with self.assertRaises(ValueError):
                    candidate.read_native_material(game)

    def test_10_fixed_rebuild_is_deterministic_and_sources_stay_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for deterministic isolated generation")
        with tempfile.TemporaryDirectory(prefix="head-material-rebuild-",dir=ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable,"-B",str(ROOT / "tools/prepare_steve_head_native_material.py"),
                "--output",str(output)],cwd=ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr)
            report,payloads,_ = candidate.load_candidate(output / candidate.REPORT_NAME)
            self.assertEqual((output / candidate.REPORT_NAME).read_bytes(),self.report_raw)
            self.assertEqual(report,self.report)
            self.assertEqual(payloads,self.payloads)
        candidate.orientation.verify_snapshot(self.snapshot)
        native.verify_source(ROOT / "build/cdmw-fixed-source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild",action="store_true")
    args = parser.parse_args()
    NativeHeadMaterialChecks.output,NativeHeadMaterialChecks.rebuild = args.output,args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeHeadMaterialChecks))
    if result.wasSuccessful():
        print(json.dumps({"candidateResources":NativeHeadMaterialChecks.report["candidateResources"],
            "independentXmlAudit":independent_xml_audit(NativeHeadMaterialChecks.payload),
            "nativeRenderingVerified":False},indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
