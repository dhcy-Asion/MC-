"""Independent offline checks for six main-body baseColor edits; no game reads."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_body_basecolor as candidate
from check_steve_body_native_material import independent_xml_audit

native, ROOT = candidate.native, candidate.ROOT
NATIVE_SHA = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
NEW_SHA = "93bebbb4ed90a43d706230def1670b488dbf723fc7dfcebce910e76f8b069b2b"
PAC_SHA = "8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537"
DDS_SHA = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
PRIOR_SHA = "485e0b529cf096b3c2568bdbfdf8a66aedeffae626f2fe031d65aff1741ce55c"
TARGET = b"character/texture/crimsonmc_steve_1_21_1.dds"
OLD = b"character/texture/cd_phm_00_nude_00_0001.dds"
SPANS = ((7067,7111), (15595,15639), (24448,24492), (30046,30090), (38579,38623), (47610,47654))


def independent_contract(source, payload):
    """Compare every tree tag/attribute/text/tail after six independently selected edits."""
    original = ET.fromstring("<Root>" + source.decode("utf-8-sig") + "</Root>")
    changed = ET.fromstring("<Root>" + payload.decode("utf-8-sig") + "</Root>")
    variants = original.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 6:
        raise ValueError("Original body variant count differs")
    for index, variant in enumerate(variants):
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        if tuple(w.get("_subMeshName") for w in wrappers) != (
                "cd_phm_00_head_0001_01", "cd_phm_00_nude_0001_hand", "cd_phm_00_nude_0001"):
            raise ValueError("Original body draw mapping differs")
        targets = wrappers[2].findall(".//MaterialParameterTexture[@_name='_baseColorTexture']/ResourceReferencePath_ITexture")
        if len(targets) != 1 or targets[0].attrib != {"Name": "_value", "_path": OLD.decode()}:
            raise ValueError("Original main-body baseColor differs")
        targets[0].set("_path", TARGET.decode())
    def values(element):
        return (element.tag, tuple(sorted(element.attrib.items())), element.text, element.tail,
                tuple(values(child) for child in element))
    if values(original) != values(changed):
        raise ValueError("Unapproved XML value changed")
    return independent_xml_audit(payload)


def independent_spans(source):
    """Locate only the proven wrapper identity, not all occurrences of an old path."""
    result = []
    for block in re.finditer(rb'<SkinnedMeshMaterialWrapper\b[^>]*>.*?</SkinnedMeshMaterialWrapper>', source, re.DOTALL):
        if b'_subMeshName="cd_phm_00_nude_0001"' not in block.group():
            continue
        matches = list(re.finditer(rb'<MaterialParameterTexture\b[^>]*_name="_baseColorTexture"[^>]*>\s*'
                                  rb'<ResourceReferencePath_ITexture[^>]*_path="([^"]+)"', block.group()))
        if len(matches) != 1 or matches[0].group(1) != OLD:
            raise ValueError("Ambiguous main-body byte target")
        result.append(tuple(block.start() + offset for offset in matches[0].span(1)))
    if len(result) != 6:
        raise ValueError("Main body target count differs")
    return tuple(result)


class BodyBaseColorChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = candidate.load_report(cls.report_path)
        cls.sources = {key: (cls.output / row[0]).read_bytes() for key, row in candidate.SOURCE_SPECS.items()}
        cls.original, cls.payload = cls.sources["nativeMaterial"], cls.payloads[candidate.MATERIAL_PATH]

    def test_01_pins_exact_single_pami_inventory_and_false_application_claims(self):
        self.assertEqual({k: hashlib.sha256(v).hexdigest() for k,v in self.sources.items()}, {
            "nativeMaterial": NATIVE_SHA, "preservedPac": PAC_SHA, "diffuseTexture": DDS_SHA,
            "nativeMaterialReport": PRIOR_SHA})
        self.assertEqual([len(self.original), len(self.payload), len(self.sources["preservedPac"]),
                          len(self.sources["diffuseTexture"])], [50017,50017,236594,87536])
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NEW_SHA)
        self.assertEqual(set(self.payloads), {candidate.MATERIAL_PATH})
        self.assertEqual(self.report["candidateResources"], [{"kind": "skinnedMaterial",
            "virtualPath": candidate.MATERIAL_PATH, "localFile": "resources/" + candidate.MATERIAL_PATH,
            "sha256": NEW_SHA, "payloadSize": 50017, "sourceVirtualPath": candidate.NATIVE_MATERIAL_PATH,
            "templatePath": candidate.NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_SHA,
            "templateArchiveFlags": 50, "archiveFlags": 50}])
        self.assertEqual(len(self.report["files"]), 5)
        self.assertEqual(len(self.snapshot), 6)
        self.assertTrue(all(type(value) is bool and value is False for value in self.report["integration"].values()))
        self.assertFalse(self.report["replacementContract"]["standaloneInstallable"])
        self.assertFalse(self.report["diffuseDependency"]["addedAsCandidateResource"])

    def test_02_independent_identity_bound_byte_splices_inverse_and_outside_bytes(self):
        self.assertEqual(independent_spans(self.original), SPANS)
        expected, restored = self.original, self.payload
        for start,end in reversed(SPANS):
            self.assertEqual(expected[start:end], OLD)
            expected = expected[:start] + TARGET + expected[end:]
            self.assertEqual(restored[start:end], TARGET)
            restored = restored[:start] + OLD + restored[end:]
        self.assertEqual(expected, self.payload)
        self.assertEqual(restored, self.original)
        cursor = 0
        for start,end in SPANS:
            self.assertEqual(self.original[cursor:start], self.payload[cursor:start])
            cursor = end
        self.assertEqual(self.original[cursor:], self.payload[cursor:])
        self.assertEqual(self.payload[:3], b"\xef\xbb\xbf")
        self.assertEqual(self.original.count(b"\r\n"), self.payload.count(b"\r\n"))
        self.assertEqual(self.payload.count(TARGET), 6)
        self.assertEqual(self.payload.count(OLD), 0)
        self.assertEqual(candidate.restore_material(self.payload), self.original)

    def test_03_independent_every_xml_value_and_excluded_head_hand_draws(self):
        counts, textures = independent_contract(self.original, self.payload)
        self.assertEqual(counts, [[10,12,9],[9,11,9],[10,12,10],[4,4,9],[9,12,10],[10,12,10]])
        original_tree = ET.fromstring("<Root>"+self.original.decode("utf-8-sig")+"</Root>")
        changed_tree = ET.fromstring("<Root>"+self.payload.decode("utf-8-sig")+"</Root>")
        for original, changed in zip(original_tree.findall(".//ModelProperty"),changed_tree.findall(".//ModelProperty")):
            for index in (0,1):
                self.assertEqual(ET.tostring(original.findall(".//SkinnedMeshMaterialWrapper")[index]),
                                 ET.tostring(changed.findall(".//SkinnedMeshMaterialWrapper")[index]))
        mutants = [(b'_materialName="SkinnedMeshSkin"', b'_materialName="SkinnedMeshStandard"'),
            (b'ItemID="8"', b'ItemID="7"'), (b'_jiggleWindWeight="0"', b'_jiggleWindWeight="1"'),
            (b'Index="5" Version="Reflection"', b'Index="6" Version="Reflection"'),
            (b'character/texture/cd_phm_00_nude_00_0001_hand.dds', TARGET),
            (b'character/texture/cd_phm_00_head_00_0001_01.dds', TARGET),
            (b'character/texture/cd_phm_00_nude_00_0001_n.dds', TARGET)]
        for old,new in mutants:
            changed = self.payload.replace(old,new,1)
            self.assertNotEqual(changed,self.payload)
            with self.subTest(old=old), self.assertRaises(ValueError):
                independent_contract(self.original,changed)
        expected_textures = set(candidate.TEXTURE_PATHS) | {TARGET.decode(), "texture/nonetexture0xffffffff.dds"}
        self.assertEqual(textures,expected_textures)

    def test_04_raw_pac_empty_descriptors_and_only_populated_body_draw_all_lods(self):
        raw = self.sources["preservedPac"]
        self.assertEqual(raw[:4],b"PAR ")
        self.assertEqual(struct.unpack_from("<5Q",raw,20),(63138,43344,43344,43344,43344))
        for offset in (165,279):
            self.assertEqual(raw[offset+35:offset+40],bytes([4,0,1,2,3]))
            self.assertEqual(struct.unpack_from("<4H",raw,offset+40),(0,)*4)
            self.assertEqual(struct.unpack_from("<4I",raw,offset+48),(0,)*4)
        self.assertEqual(raw[344:363],b"CD_PHM_00_Nude_0001")
        self.assertEqual(struct.unpack_from("<4H",raw,423),(1008,)*4)
        self.assertEqual(struct.unpack_from("<4I",raw,431),(1512,)*4)
        starts = (193250,149906,106562,63218)
        splits = (233570,190226,146882,103538)
        ends = (236594,193250,149906,106562)
        self.assertEqual(struct.unpack_from("<4I",raw,85),starts)
        self.assertEqual(struct.unpack_from("<4I",raw,101),splits)
        for start,split,end in zip(starts,splits,ends):
            self.assertEqual((split-start,end-split),(40320,3024))
            indices = struct.unpack_from("<1512H",raw,split)
            self.assertEqual((min(indices),max(indices)),(0,1007))
            self.assertTrue(all(len(set(indices[i:i+3]))==3 for i in range(0,len(indices),3)))
        self.assertEqual(len({raw[start:end] for start,end in zip(starts,ends)}),1)
        proof = self.report["audit"]["mainDrawEvidence"]
        self.assertEqual(proof["onlyPopulatedDrawName"],"cd_phm_00_nude_0001")
        self.assertEqual(proof["onlyPopulatedDrawIndex"],2)
        self.assertFalse(proof["engineDrawSelectionVerified"])
        with self.assertRaises(ValueError):
            candidate.body_draw_audit(raw[:-1])

    def test_05_actual_dds_nine_complete_ranges_and_exact_remaining_dependencies(self):
        raw = self.sources["diffuseTexture"]
        self.assertEqual(struct.unpack_from("<5I",raw,12),(256,256,65536,1,9))
        self.assertEqual(struct.unpack_from("<2I",raw,76),(32,4))
        self.assertEqual(raw[84:88],b"DXT5")
        offsets = ((128,65664),(65664,82048),(82048,86144),(86144,87168),
                   (87168,87424),(87424,87488),(87488,87504),(87504,87520),(87520,87536))
        ranges = self.report["diffuseDependency"]["dds"]["mipByteRanges"]
        self.assertEqual([(r["offset"],r["endOffset"]) for r in ranges],list(offsets))
        self.assertEqual(sum(len(raw[a:b]) for a,b in offsets),87408)
        dependency = self.report["dependencyContract"]
        self.assertEqual(dependency["requiredOriginalDependencyEntries"],22)
        self.assertEqual(len(dependency["textureEntries"]),21)
        self.assertEqual({r["virtualPath"] for r in dependency["textureEntries"]},set(candidate.TEXTURE_PATHS))
        self.assertTrue(all(r["archiveFlags"]==1 for r in dependency["textureEntries"]))
        self.assertEqual(dependency["wrinkleEntry"]["archiveFlags"],50)
        self.assertNotIn(OLD.decode(),set(candidate.TEXTURE_PATHS))
        self.assertEqual(self.report["diffuseDependency"]["expectedArchiveFlags"],0)
        self.assertFalse(dependency["dependencyPayloadsDecoded"])
        self.assertFalse(dependency["noneTextureSentinel"]["runtimeResolutionVerified"])
        for changed in (raw[:-1],raw+b"x",raw[:84]+b"DX10"+raw[88:]):
            with self.assertRaises(ValueError):
                candidate.head_basecolor.dds_audit(changed)

    def test_06_new_process_pure_loader_only_six_paths_and_no_cdmw(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "import prepare_steve_body_basecolor as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('not pure'));"
            "c.native.load_cdmw=forbidden;c.native.download_source=forbidden;"
            "c.body_material.read_native_material=forbidden;c.body_material.load_candidate=forbidden;"
            "c.assembly.load_candidate=forbidden;c.assembly.read_context=forbidden;"
            "r,p,s=c.load_report(Path(sys.argv[1]));assert len(p)==1 and len(s)==6;"
            "assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);"
            "c.orientation.verify_snapshot(s)")
        result = subprocess.run([sys.executable,"-B","-c",code,str(self.report_path)],
                                cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_07_all_fixed_source_payload_tamper_even_relabelled_hashes_rejected(self):
        with tempfile.TemporaryDirectory(prefix="body-basecolor-tamper-",dir=ROOT/"build") as temporary:
            output = Path(temporary)/"copy"
            shutil.copytree(self.output,output)
            for relative in self.report["files"]:
                path = output/relative
                raw = path.read_bytes()
                changed = raw[:-1]+bytes([raw[-1]^1])
                path.write_bytes(changed)
                with self.subTest(relative=relative),self.assertRaises(ValueError):
                    candidate.load_report(output/candidate.REPORT_NAME)
                report = copy.deepcopy(self.report)
                digest = hashlib.sha256(changed).hexdigest()
                report["files"][relative] = digest
                for row in report["sources"].values():
                    if row["localFile"]==relative:
                        row["sha256"] = digest
                if relative.startswith("resources/"):
                    report["candidateResources"][0]["sha256"] = digest
                (output/candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.assertRaises(ValueError):
                    candidate.load_report(output/candidate.REPORT_NAME)
                path.write_bytes(raw)
                (output/candidate.REPORT_NAME).write_bytes(self.report_raw)
        for wrong in ({**self.sources,"unknown":b"extra"},
                      {**self.sources,"diffuseTexture":bytearray(self.sources["diffuseTexture"])},
                      {**self.sources,"nativeMaterial":self.payload}):
            with self.assertRaises(ValueError):
                candidate.make_report(wrong)

    def test_08_manifest_metadata_claim_types_noncanonical_and_actual_extra_file_rejected(self):
        edits = [lambda r:r.update(unknown=True),lambda r:r.update(variant="other"),
            lambda r:r["candidateResources"][0].update(archiveFlags=0),
            lambda r:r["candidateResources"][0].update(payloadSize=50016),
            lambda r:r["candidateResources"][0].update(localFile="../outside"),
            lambda r:r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r:r["integration"].update(installed=True),lambda r:r["integration"].update(installed=0),
            lambda r:r["replacementContract"].update(standaloneInstallable=True),
            lambda r:r["diffuseDependency"].update(addedAsCandidateResource=True),
            lambda r:r["dependencyContract"].update(requiredOriginalDependencyEntries=23),
            lambda r:r["audit"]["edits"][0].update(drawIndex=1),
            lambda r:r["audit"]["mainDrawEvidence"].update(engineDrawSelectionVerified=True),
            lambda r:r["sources"]["preservedPac"].update(localFile="../outside")]
        with tempfile.TemporaryDirectory(prefix="body-basecolor-manifest-",dir=ROOT/"build") as temporary:
            output = Path(temporary)/"copy"
            shutil.copytree(self.output,output)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (output/candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.assertRaises(ValueError):
                    candidate.load_report(output/candidate.REPORT_NAME)
            for raw in (b'{"schemaVersion":1,"schemaVersion":1}',json.dumps(self.report).encode(),b'{"schemaVersion":NaN}'):
                (output/candidate.REPORT_NAME).write_bytes(raw)
                with self.assertRaises(ValueError):
                    candidate.load_report(output/candidate.REPORT_NAME)
            (output/candidate.REPORT_NAME).write_bytes(self.report_raw)
            (output/"foreign.bin").write_bytes(b"foreign")
            with self.assertRaisesRegex(ValueError,"file inventory"):
                candidate.load_report(output/candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.load_report(ROOT/"docs"/candidate.REPORT_NAME)

    def test_09_early_overwrite_and_all_source_overlap_refusal_preserves_sentinel(self):
        with tempfile.TemporaryDirectory(prefix="body-basecolor-output-",dir=ROOT/"build") as temporary:
            output = Path(temporary)
            sentinel = output/"keep"
            sentinel.write_bytes(b"keep")
            with mock.patch.object(candidate,"read_inputs",side_effect=AssertionError("input read")):
                with self.assertRaisesRegex(ValueError,"already exists"):
                    candidate.prepare(output=output)
                for directory in candidate.protected_directories(candidate.DEFAULT_BODY_MATERIAL_REPORT,
                                                                 candidate.DEFAULT_ASSEMBLY_REPORT):
                    with self.subTest(directory=directory),self.assertRaisesRegex(ValueError,"overlaps"):
                        candidate.prepare(output=directory/"fresh")
            self.assertEqual(sentinel.read_bytes(),b"keep")
        with self.assertRaises(ValueError):
            candidate.prepare(output=ROOT/"outside")

    def test_10_wrong_admitted_source_and_source_race_refuse_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="body-basecolor-race-",dir=ROOT/"build") as temporary:
            directory = Path(temporary)
            wrong = directory/"wrong"
            with self.assertRaises(ValueError):
                candidate.prepare(output=wrong,body_material_report=candidate.head_basecolor.DEFAULT_HEAD_MATERIAL_REPORT)
            self.assertFalse(wrong.exists())
            dependency = directory/"source.dds"
            dependency.write_bytes(self.sources["diffuseTexture"])
            output = directory/"fresh"
            snapshot = {dependency:self.sources["diffuseTexture"]}
            real = candidate.make_report
            def make(sources):
                report = real(sources)
                raw = self.sources["diffuseTexture"]
                dependency.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                return report
            with mock.patch.object(candidate,"read_inputs",return_value=(self.sources,snapshot)), \
                 mock.patch.object(candidate,"make_report",side_effect=make):
                with self.assertRaisesRegex(ValueError,"changed before publication"):
                    candidate.prepare(output=output)
            self.assertFalse(output.exists())

    def test_11_stale_snapshot_and_size_bounds_rejected(self):
        with tempfile.TemporaryDirectory(prefix="body-basecolor-stale-",dir=ROOT/"build") as temporary:
            output = Path(temporary)/"copy"
            shutil.copytree(self.output,output)
            _,_,snapshot = candidate.load_report(output/candidate.REPORT_NAME)
            path = output/("resources/"+candidate.MATERIAL_PATH)
            path.write_bytes(self.payload[:-1]+bytes([self.payload[-1]^1]))
            with self.assertRaises(ValueError):
                candidate.orientation.verify_snapshot(snapshot)
            (output/candidate.REPORT_NAME).write_bytes(b" "*131073)
            with self.assertRaises(ValueError):
                candidate.load_report(output/candidate.REPORT_NAME)

    def test_12_new_process_real_rebuild_canonical_bytes_and_source_custody(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for an isolated pure package generation")
        _,input_snapshot = candidate.read_inputs(candidate.DEFAULT_BODY_MATERIAL_REPORT,candidate.DEFAULT_ASSEMBLY_REPORT)
        with tempfile.TemporaryDirectory(prefix="body-basecolor-rebuild-",dir=ROOT/"build") as temporary:
            output = Path(temporary)/"fresh"
            code = ("import sys;sys.path.insert(0,'tools');import prepare_steve_body_basecolor as c;"
                "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('game/CDMW/network forbidden'));"
                "c.native.load_cdmw=forbidden;c.native.download_source=forbidden;"
                "c.body_material.read_native_material=forbidden;c.assembly.read_context=forbidden;"
                "c.main();assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
            result = subprocess.run([sys.executable,"-B","-c",code,"--output",str(output)],
                                    cwd=ROOT,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            report,payloads,snapshot = candidate.load_report(output/candidate.REPORT_NAME)
            self.assertEqual((report,payloads),(self.report,self.payloads))
            self.assertEqual((output/candidate.REPORT_NAME).read_bytes(),self.report_raw)
            self.assertEqual({path.relative_to(output).as_posix():raw for path,raw in snapshot.items()},
                             {path.relative_to(self.output).as_posix():raw for path,raw in self.snapshot.items()})
        candidate.orientation.verify_snapshot(input_snapshot)
        candidate.orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild",action="store_true")
    args = parser.parse_args()
    BodyBaseColorChecks.output,BodyBaseColorChecks.rebuild = args.output,args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BodyBaseColorChecks))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
