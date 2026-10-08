"""Offline checks for the three-path MC head diffuse candidate; no game/CDMW read."""
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
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_head_basecolor as candidate
from check_steve_head_native_material import independent_xml_audit

native, ROOT = candidate.native, candidate.ROOT
NATIVE_SHA = "440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5"
NEW_SHA = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
PAC_SHA = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
DDS_SHA = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
PRIOR_SHA = "1ca1972751b346ce8afd9da684ab3d419ef60a92e557a53be1b111145cdb7c7a"
TARGET = b"character/texture/crimsonmc_steve_1_21_1.dds"
OLD_PATHS = (b"character/texture/cd_phm_00_head_0001_macduff.dds",
             b"character/texture/cd_phm_00_head_0008_macduff.dds",
             b"character/texture/cd_phm_00_head_0001_macduff.dds")


def independent_contract(source, payload):
    """Compare every XML tag/attribute/text/tail after only three expected edits."""
    original = ET.fromstring("<Root>" + source.decode("utf-8-sig") + "</Root>")
    changed = ET.fromstring("<Root>" + payload.decode("utf-8-sig") + "</Root>")
    variants = original.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 3:
        raise ValueError("Original head variant contract differs")
    for index, variant in enumerate(variants):
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        refs = wrappers[1].findall(".//MaterialParameterTexture[@_name='_baseColorTexture']/ResourceReferencePath_ITexture")
        if len(refs) != 1 or refs[0].attrib != {"Name": "_value", "_path": OLD_PATHS[index].decode()}:
            raise ValueError("Original main-draw base-color differs")
        refs[0].set("_path", TARGET.decode())
    if ET.tostring(original) != ET.tostring(changed):
        raise ValueError("An unapproved shader/parameter/item/flag/reference/XML field changed")
    return independent_xml_audit(payload)


class HeadBaseColorChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = candidate.load_candidate(cls.report_path)
        cls.sources = {key: (cls.output / row[0]).read_bytes() for key, row in candidate.SOURCE_SPECS.items()}
        cls.original, cls.payload = cls.sources["nativeMaterial"], cls.payloads[candidate.MATERIAL_PATH]

    def test_01_four_pinned_sources_exact_single_pami_and_false_runtime_claims(self):
        expected = {"nativeMaterial": NATIVE_SHA, "preservedPac": PAC_SHA,
                    "diffuseTexture": DDS_SHA, "nativeMaterialReport": PRIOR_SHA}
        self.assertEqual({k: hashlib.sha256(v).hexdigest() for k, v in self.sources.items()}, expected)
        self.assertEqual([len(self.original), len(self.payload), len(self.sources["preservedPac"]),
                          len(self.sources["diffuseTexture"])], [16149, 16134, 96721, 87536])
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NEW_SHA)
        self.assertEqual(self.report["candidateResources"], [{"kind": "skinnedMaterial",
            "virtualPath": candidate.MATERIAL_PATH, "localFile": "resources/" + candidate.MATERIAL_PATH,
            "sha256": NEW_SHA, "payloadSize": 16134, "sourceVirtualPath": candidate.NATIVE_MATERIAL_PATH,
            "templatePath": candidate.NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_SHA,
            "templateArchiveFlags": 50, "archiveFlags": 50}])
        self.assertEqual(set(self.payloads), {candidate.MATERIAL_PATH})
        self.assertTrue(all(type(v) is bool and v is False for v in self.report["integration"].values()))
        dependency = self.report["diffuseDependency"]
        self.assertFalse(dependency["addedAsCandidateResource"])
        self.assertFalse(dependency["packageRegistrationVerifiedByThisTool"])
        self.assertEqual(dependency["expectedArchiveFlags"], 0)
        self.assertFalse(dependency["encodingProvenance"]["encodingIsLossless"])

    def test_02_independent_three_byte_splices_inverse_bom_crlf_and_outside_regions(self):
        spans = ((1406,1455), (6516,6565), (11631,11680))
        expected = self.original
        for (start, end), old in reversed(tuple(zip(spans, OLD_PATHS))):
            self.assertEqual(expected[start:end], old)
            expected = expected[:start] + TARGET + expected[end:]
        self.assertEqual(expected, self.payload)
        restored = self.payload
        for (start, end), old in reversed(tuple(zip(((1406,1450), (6511,6555), (11621,11665)), OLD_PATHS))):
            self.assertEqual(restored[start:end], TARGET)
            restored = restored[:start] + old + restored[end:]
        self.assertEqual(restored, self.original)
        self.assertEqual(self.original[:1406], self.payload[:1406])
        self.assertEqual(self.original[1455:6516], self.payload[1450:6511])
        self.assertEqual(self.original[6565:11631], self.payload[6555:11621])
        self.assertEqual(self.original[11680:], self.payload[11665:])
        self.assertEqual(self.payload[:3], b"\xef\xbb\xbf")
        self.assertEqual(self.original.count(b"\r\n"), self.payload.count(b"\r\n"))
        self.assertEqual(self.payload.count(TARGET), 3)
        self.assertEqual(candidate.restore_material(self.payload), self.original)

    def test_03_independent_complete_three_by_two_xml_contract_and_nonpath_mutations(self):
        audit = independent_contract(self.original, self.payload)
        self.assertEqual([row["parameterCounts"] for row in audit], [[1,14], [1,14], [1,16]])
        changes = [(b'SkinnedMeshSkinWrinkle"', b'SkinnedMeshStandard"'),
                   (b'_name="_damageBlendingParameter"', b'_name="_unreviewed"'),
                   (b'ItemID="7"', b'ItemID="8"'),
                   (b'_jiggleWindWeight="0"', b'_jiggleWindWeight="1"'),
                   (b'Index="2" Version="Reflection"', b'Index="3" Version="Reflection"')]
        for old, new in changes:
            raw = self.payload.replace(old, new, 1)
            self.assertNotEqual(raw, self.payload)
            with self.subTest(old=old), self.assertRaises(ValueError):
                independent_contract(self.original, raw)

    def test_04_independent_dds_header_nine_real_mip_spans_and_format_failures(self):
        raw = self.sources["diffuseTexture"]
        self.assertEqual(raw[:4], b"DDS ")
        self.assertEqual(struct.unpack_from("<I", raw, 4)[0], 124)
        self.assertEqual(struct.unpack_from("<5I", raw, 12), (256,256,65536,1,9))
        self.assertEqual(struct.unpack_from("<2I", raw, 76), (32,4))
        self.assertEqual(raw[84:88], b"DXT5")
        offsets = ((128,65664), (65664,82048), (82048,86144), (86144,87168),
                   (87168,87424), (87424,87488), (87488,87504), (87504,87520), (87520,87536))
        rows = self.report["diffuseDependency"]["dds"]["mipByteRanges"]
        self.assertEqual([(row["offset"], row["endOffset"]) for row in rows], list(offsets))
        self.assertEqual([row["byteCount"] for row in rows], [65536,16384,4096,1024,256,64,16,16,16])
        self.assertEqual(sum(len(raw[a:b]) for a,b in offsets), 87408)
        mutants = [raw[:-1], raw + b"x", raw[:84] + b"DX10" + raw[88:]]
        for offset, value in ((4,128), (8,0x1007), (12,128), (16,1024), (20,1), (24,0), (28,8), (76,31), (80,0), (108,0x1000)):
            changed = bytearray(raw)
            struct.pack_into("<I", changed, offset, value)
            mutants.append(bytes(changed))
        for raw in mutants:
            with self.assertRaises(ValueError):
                candidate.dds_audit(raw)

    def test_05_pure_loader_uses_only_six_absolute_paths_and_imports_no_cdmw(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "import prepare_steve_head_basecolor as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('not pure'));"
            "c.native.load_cdmw=forbidden;c.head_material.read_native_material=forbidden;"
            "c.head_material.load_candidate=forbidden;c.assembly.load_candidate=forbidden;"
            "r,p,s=c.load_candidate(Path(sys.argv[1]));assert len(p)==1 and len(s)==6;"
            "assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);"
            "c.orientation.verify_snapshot(s)")
        result = subprocess.run([sys.executable,"-B","-c",code,str(self.report_path)],
                                cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_06_payload_each_fixed_source_and_relabelled_inner_hash_tamper_fail(self):
        with tempfile.TemporaryDirectory(prefix="head-basecolor-tamper-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output, output)
            for relative in self.report["files"]:
                path = output / relative
                raw = path.read_bytes()
                changed = raw[:-1] + bytes([raw[-1] ^ 1])
                path.write_bytes(changed)
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
                report = copy.deepcopy(self.report)
                digest = hashlib.sha256(changed).hexdigest()
                report["files"][relative] = digest
                for row in report["sources"].values():
                    if row["localFile"] == relative:
                        row["sha256"] = digest
                if relative.startswith("resources/"):
                    report["candidateResources"][0]["sha256"] = digest
                (output / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
                path.write_bytes(raw)
                (output / candidate.REPORT_NAME).write_bytes(self.report_raw)
            candidate.load_candidate(output / candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.make_report({**self.sources, "unknown": b"unapproved"})
        with self.assertRaises(ValueError):
            candidate.make_report({**self.sources, "diffuseTexture": bytearray(self.sources["diffuseTexture"])})

    def test_07_unknown_duplicate_typed_manifest_metadata_paths_and_claims_are_rejected(self):
        edits = [lambda r: r.update(unknown=True), lambda r: r.update(variant="other"),
            lambda r: r["candidateResources"][0].update(archiveFlags=0),
            lambda r: r["candidateResources"][0].update(templateArchiveFlags=1),
            lambda r: r["candidateResources"][0].update(localFile="../outside"),
            lambda r: r["candidateResources"][0].update(templatePath="../outside"),
            lambda r: r["candidateResources"][0].update(payloadSize=16149),
            lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r: r["sources"]["diffuseTexture"].update(localFile="../outside"),
            lambda r: r["files"].update({"../outside": "0" * 64}),
            lambda r: r["integration"].update(installed=True), lambda r: r["integration"].update(installed=0),
            lambda r: r["replacementContract"].update(preservedPacSha256="0" * 64),
            lambda r: r["diffuseDependency"].update(addedAsCandidateResource=True),
            lambda r: r["diffuseDependency"].update(expectedArchiveFlags=1),
            lambda r: r["diffuseDependency"]["encodingProvenance"].update(encodingIsLossless=True),
            lambda r: r["audit"]["edits"][0].update(sourceSpan=[0,49]),
            lambda r: r["audit"]["nativeSourceContract"]["variants"][0]["draws"][1].update(shader="Standard")]
        with tempfile.TemporaryDirectory(prefix="head-basecolor-manifest-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "copy"
            shutil.copytree(self.output, output)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (output / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(edit=repr(edit)), self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
            for raw in (b'{"schemaVersion":1,"schemaVersion":1}', json.dumps(self.report).encode(),
                        b'{"schemaVersion":NaN}'):
                (output / candidate.REPORT_NAME).write_bytes(raw)
                with self.assertRaises(ValueError):
                    candidate.load_candidate(output / candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.load_candidate(ROOT / "docs" / candidate.REPORT_NAME)

    def test_08_early_output_overlap_existing_bounds_and_stale_snapshot_protection(self):
        with tempfile.TemporaryDirectory(prefix="head-basecolor-output-", dir=ROOT / "build") as temporary:
            output = Path(temporary)
            sentinel = output / "keep"
            sentinel.write_bytes(b"keep")
            with mock.patch.object(candidate, "read_inputs", side_effect=AssertionError("input read")):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    candidate.prepare(output=output)
                for directory in (candidate.DEFAULT_HEAD_MATERIAL_REPORT.parent,
                                  candidate.DEFAULT_ASSEMBLY_REPORT.parent, ROOT / "build/steve-body-native-material",
                                  ROOT / "build/steve-body-native-material-probe-overlay",
                                  ROOT / "build/steve-clothing-control-probe-overlay",
                                  ROOT / "build/steve-head-native-material-probe-overlay"):
                    with self.assertRaisesRegex(ValueError, "overlaps"):
                        candidate.prepare(output=directory / "fresh")
            self.assertEqual(sentinel.read_bytes(), b"keep")
            fixture = output / "fixture"
            shutil.copytree(self.output, fixture)
            _, _, snapshot = candidate.load_candidate(fixture / candidate.REPORT_NAME)
            payload = fixture / ("resources/" + candidate.MATERIAL_PATH)
            payload.write_bytes(self.payload[:-1] + bytes([self.payload[-1] ^ 1]))
            with self.assertRaises(ValueError):
                candidate.orientation.verify_snapshot(snapshot)
            (fixture / candidate.REPORT_NAME).write_bytes(b" " * 131073)
            with self.assertRaises(ValueError):
                candidate.load_candidate(fixture / candidate.REPORT_NAME)

    def test_09_source_race_refuses_before_output_publication(self):
        with tempfile.TemporaryDirectory(prefix="head-basecolor-race-", dir=ROOT / "build") as temporary:
            directory = Path(temporary)
            dependency = directory / "source.dds"
            dependency.write_bytes(self.sources["diffuseTexture"])
            snapshot = {dependency: self.sources["diffuseTexture"]}
            output = directory / "fresh"
            real = candidate.make_report
            def make(sources):
                report = real(sources)
                raw = self.sources["diffuseTexture"]
                dependency.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                return report
            with mock.patch.object(candidate, "read_inputs", return_value=(self.sources, snapshot)), \
                 mock.patch.object(candidate, "make_report", side_effect=make):
                with self.assertRaisesRegex(ValueError, "changed before publication"):
                    candidate.prepare(output=output)
            self.assertFalse(output.exists())

    def test_10_real_pure_package_rebuild_is_identical_and_all_inputs_stay_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for deterministic isolated pure generation")
        _, input_snapshot = candidate.read_inputs(candidate.DEFAULT_HEAD_MATERIAL_REPORT, candidate.DEFAULT_ASSEMBLY_REPORT)
        with tempfile.TemporaryDirectory(prefix="head-basecolor-rebuild-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            code = ("import sys;sys.path.insert(0,'tools');import prepare_steve_head_basecolor as c;"
                "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('game/CDMW/network forbidden'));"
                "c.native.load_cdmw=forbidden;c.native.download_source=forbidden;"
                "c.head_material.read_native_material=forbidden;c.assembly.read_context=forbidden;"
                "c.main();assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
            result = subprocess.run([sys.executable,"-B","-c",code,"--output",str(output)],
                                    cwd=ROOT,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, payloads, snapshot = candidate.load_candidate(output / candidate.REPORT_NAME)
            self.assertEqual((report, payloads), (self.report, self.payloads))
            self.assertEqual((output / candidate.REPORT_NAME).read_bytes(), self.report_raw)
            self.assertEqual(len(snapshot), 6)
            self.assertEqual({path.relative_to(output).as_posix(): raw for path, raw in snapshot.items()},
                             {path.relative_to(self.output).as_posix(): raw for path, raw in self.snapshot.items()})
        candidate.orientation.verify_snapshot(input_snapshot)
        candidate.orientation.verify_snapshot(self.snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    HeadBaseColorChecks.output, HeadBaseColorChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeadBaseColorChecks))
    if result.wasSuccessful():
        _, inputs = candidate.read_inputs(candidate.DEFAULT_HEAD_MATERIAL_REPORT, candidate.DEFAULT_ASSEMBLY_REPORT)
        print(json.dumps({"candidateResources": HeadBaseColorChecks.report["candidateResources"],
            "fixedSourceCount": 4, "candidateSnapshotCount": len(HeadBaseColorChecks.snapshot),
            "upstreamInputSnapshotCount": len(inputs), "mcHeadSkinVerified": False,
            "nativeRenderingVerified": False}, indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
