"""Independent offline checks for the fixed primary-V-only head PAC control."""
from __future__ import annotations

import argparse
from collections import Counter
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

import prepare_steve_head_uv_control as candidate

native, ROOT = candidate.native, candidate.ROOT
SOURCE_SHA = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
NEW_SHA = "c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55"
PAMI_SHA = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
DDS_SHA = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
PRIOR_SHA = "56d0ee077c290395c6efcc013c1c48524fe0db1af5c3bea6137d01a944c9f466"
OFFICIAL = {"steve.gltf": "bc9cd38b3ebcab9702def27a425208bbfb2f6a1093012976d95f0c4d165e81b8",
            "steve.bin": "d03b7e6354652c7872b14b89d9d56861a23d2e910b52349f0e1da4c3101942a0",
            "steve.png": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def independent_sections(raw):
    """Read every table entry, descriptor mirror, record and triangle independently."""
    require(len(raw) == 96721 and raw[:4] == b"PAR ", "Bad head PAC length/magic")
    table = list(struct.iter_unpack("<II", raw[16:80]))
    require(len(table) == 8 and all(pointer == 0 for pointer, _ in table), "Unsupported PAR table")
    require([size for _, size in table] == [90449, 0, 2064, 2064, 2064, 0, 0, 0], "Wrong PAR sizes")
    require(struct.unpack_from("<I", raw, 80)[0] == 2 and raw[84] == 3, "Wrong native flags/LOD count")
    require(raw[218:230] == bytes(12), "EyeCover geometry must stay empty")
    require(struct.unpack_from("<HHHIII", raw, 326) == (48, 48, 48, 72, 72, 72), "Wrong active draw counts")
    require(struct.unpack_from("<H", raw, 344)[0] == 192, "Wrong palette count")
    sections, cursor = [], 80
    for section, (_, size) in enumerate(table):
        if not size:
            continue
        start, cursor = cursor, cursor + size
        if section == 0:
            require(start == 80 and cursor == 90529, "Wrong metadata boundary")
            continue
        lod = 4 - section
        require(struct.unpack_from("<I", raw, 85 + 4 * lod)[0] == start, "Wrong mirrored vertex offset")
        require(struct.unpack_from("<I", raw, 97 + 4 * lod)[0] == start + 1920, "Wrong mirrored index offset")
        vertices = [raw[start + 40 * i:start + 40 * (i + 1)] for i in range(48)]
        faces = list(struct.iter_unpack("<3H", raw[start + 1920:cursor]))
        require(len(faces) == 24 and all(max(f) < 48 and len(set(f)) == 3 for f in faces), "Bad head triangles")
        require({i for f in faces[:12] for i in f} == set(range(24)), "Lost base-head surface")
        require({i for f in faces[12:] for i in f} == set(range(24, 48)), "Lost outer-hat surface")
        for record in vertices:
            require(record[12:16] == bytes.fromhex("0000003c"), "Guide sentinel changed")
            require(record[20:28] == bytes(8) and tuple(record[28:36]) == (255, 0, 0, 0, 0, 0, 0, 0), "Rigid skin bytes changed")
            require(record[39] & 0x3f == 0x3f, "Guide gate changed")
        sections.append({"lod": lod, "section": section, "start": start,
            "records": vertices, "uvs": [struct.unpack_from("<ee", r, 8) for r in vertices], "faces": faces})
    require(cursor == len(raw), "Unaccounted trailing PAC bytes")
    return sections


def independent_accessor(document, binary, index, components):
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    require(accessor["componentType"] == 5126 and accessor["type"] == "VEC" + str(components), "Wrong official accessor format")
    require(view.get("buffer", 0) == 0 and "byteStride" not in view, "Unexpected official accessor stride")
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    end = start + accessor["count"] * components * 4
    require(end <= len(binary) and end <= view.get("byteOffset", 0) + view["byteLength"], "Official accessor escapes its view")
    return list(struct.iter_unpack("<" + "f" * components, binary[start:end]))


def independent_dds_pixel(raw, x, y):
    """Separate BC3 block reader: expand index bits before selecting channels."""
    require(raw[:4] == b"DDS " and raw[84:88] == b"DXT5", "Not the reviewed BC3 DDS")
    require(0 <= x < 256 and 0 <= y < 256, "Pixel escapes mip zero")
    block = raw[128 + 16 * (64 * (y >> 2) + (x >> 2)):128 + 16 * (64 * (y >> 2) + (x >> 2) + 1)]
    require(len(block) == 16, "Incomplete BC3 block")
    alpha_codes, alpha_word = [], int.from_bytes(block[2:8], "little")
    color_codes, color_word = [], int.from_bytes(block[12:16], "little")
    for _ in range(16):
        alpha_codes.append(alpha_word % 8)
        alpha_word //= 8
        color_codes.append(color_word % 4)
        color_word //= 4
    endpoints = [int.from_bytes(block[8:10], "little"), int.from_bytes(block[10:12], "little")]
    rgb = [tuple(word // divisor % (maximum + 1) * 255 // maximum for divisor, maximum in ((2048, 31), (32, 63), (1, 31))) for word in endpoints]
    rgb += [tuple((rgb[0][axis] * left + rgb[1][axis] * right) // 3 for axis in range(3)) for left, right in ((2, 1), (1, 2))]
    first, second = block[:2]
    alpha = [first, second]
    denominator = 7 if first > second else 5
    alpha.extend((first * (denominator - k) + second * k) // denominator for k in range(1, denominator))
    if first <= second:
        alpha.extend((0, 255))
    index = (y & 3) * 4 + (x & 3)
    return (*rgb[color_codes[index]], alpha[alpha_codes[index]])


class HeadUvChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.payloads, cls.snapshot = candidate.load_candidate(cls.report_path)
        cls.sources = {key: (cls.output / relative).read_bytes() for key, (relative, _) in candidate.SOURCE_SPECS.items()}
        cls.source, cls.payload = cls.sources["headPac"], cls.payloads[candidate.PAC_PATH]
        cls.old_lods, cls.new_lods = independent_sections(cls.source), independent_sections(cls.payload)
        cls.official = {}
        for name, digest in OFFICIAL.items():
            path = ROOT / "build/steve-1.21.1" / name
            native.check_links(path)
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == digest, "Official MC source changed: " + name)
            cls.official[path] = raw

    def test_01_fixed_four_sources_single_mesh_false_integration_and_dependency_flags(self):
        self.assertEqual({k: hashlib.sha256(v).hexdigest() for k, v in self.sources.items()}, {
            "headPac": SOURCE_SHA, "preservedMaterial": PAMI_SHA, "diffuseTexture": DDS_SHA, "headBaseColorReport": PRIOR_SHA})
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NEW_SHA)
        self.assertEqual(len(self.source), len(self.payload))
        self.assertEqual(self.report["candidateResources"], [{"kind": "skinnedMesh", "virtualPath": candidate.PAC_PATH,
            "localFile": "resources/" + candidate.PAC_PATH, "sha256": NEW_SHA, "payloadSize": 96721,
            "sourceVirtualPath": candidate.PAC_PATH, "templatePath": candidate.PAC_PATH,
            "templateSha256": SOURCE_SHA, "templateArchiveFlags": 1, "archiveFlags": 1}])
        self.assertEqual(set(self.payloads), {candidate.PAC_PATH})
        self.assertTrue(all(type(v) is bool and v is False for v in self.report["integration"].values()))
        self.assertEqual(self.report["preservedDependencies"]["material"]["expectedArchiveFlags"], 50)
        self.assertEqual(self.report["preservedDependencies"]["diffuse"]["expectedArchiveFlags"], 0)
        self.assertFalse(self.report["preservedDependencies"]["packageRegistrationVerifiedByThisTool"])

    def test_02_independent_complete_par_metadata_palette_draw_topology_skin_and_hat(self):
        self.assertEqual(self.source[:90529], self.payload[:90529])
        self.assertEqual(len(self.old_lods), 3)
        for old, new in zip(self.old_lods, self.new_lods):
            self.assertEqual(old["faces"], new["faces"])
            self.assertEqual(old["start"], new["start"])
            self.assertEqual(new["faces"][12:], old["faces"][12:])
            for a, b in zip(old["records"], new["records"]):
                self.assertEqual(a[:10], b[:10])
                self.assertEqual(a[12:], b[12:])
        self.assertEqual([row["start"] for row in self.new_lods], [90529, 92593, 94657])
        self.assertEqual(len({self.payload[row["start"]:row["start"] + 2064] for row in self.new_lods}), 1)

    def test_03_official_gltf_uv_and_face_quad_match_without_using_generator_transform(self):
        document = json.loads(self.official[ROOT / "build/steve-1.21.1/steve.gltf"])
        binary = self.official[ROOT / "build/steve-1.21.1/steve.bin"]
        head_parts = [next(m for m in document["meshes"] if m["name"] == name) for name in ("head", "hat")]
        wanted = []
        for mesh in head_parts:
            attrs = mesh["primitives"][0]["attributes"]
            uv = independent_accessor(document, binary, attrs["TEXCOORD_0"], 2)
            normals = independent_accessor(document, binary, attrs["NORMAL"], 3)
            self.assertEqual(len(uv), 24)
            self.assertEqual(normals[12:16], [(0., 0., 1.)] * 4)
            for quad in range(6):
                wanted.extend(uv[quad * 4 + i] for i in (0, 3, 2, 1))
        for lod in self.new_lods:
            self.assertEqual(lod["uvs"], wanted)
            self.assertEqual(lod["uvs"][12:16], [(0.25,0.125),(0.25,0.25),(0.125,0.25),(0.125,0.125)])
        for lod in self.old_lods:
            self.assertEqual(lod["uvs"][12:16], [(0.25,0.875),(0.25,0.75),(0.125,0.75),(0.125,0.875)])
        self.assertFalse(self.report["integration"]["nativeShaderUvConventionVerified"])

    def test_04_exact_allowed_half_words_all_non_v_bytes_and_independent_inverse(self):
        # Literal half-word pairs are independent of the generator's arithmetic.
        pairs = {bytes.fromhex("003a"): bytes.fromhex("0034"),
                 bytes.fromhex("003b"): bytes.fromhex("0030"),
                 bytes.fromhex("003c"): bytes.fromhex("0000")}
        allowed, actual, inverse = set(), set(), bytearray(self.payload)
        fields = self.report["audit"]["difference"]["fields"]
        self.assertEqual(len(fields), 144)
        for old, new in zip(self.old_lods, self.new_lods):
            for vertex, (a, b) in enumerate(zip(old["records"], new["records"])):
                offset = new["start"] + vertex * 40 + 10
                allowed.update((offset, offset + 1))
                self.assertEqual(pairs[a[10:12]], b[10:12])
                inverse[offset:offset + 2] = {v:k for k,v in pairs.items()}[b[10:12]]
        for index, (a, b) in enumerate(zip(self.source, self.payload)):
            if a != b:
                actual.add(index)
        self.assertEqual(len(allowed), 288)
        self.assertEqual(len(actual), 144)
        self.assertTrue(actual <= allowed)
        self.assertEqual(bytes(inverse), self.source)
        self.assertEqual(candidate.restore_pac(self.payload), self.source)
        self.assertEqual(self.report["audit"]["difference"]["actualChangedByteOffsets"], sorted(actual))
        outside = bytes(v for i,v in enumerate(self.source) if i not in allowed)
        self.assertEqual(outside, bytes(v for i,v in enumerate(self.payload) if i not in allowed))
        self.assertEqual(hashlib.sha256(outside).hexdigest(), self.report["audit"]["difference"]["outsideVFieldSha256"])

    def test_05_independent_actual_bc3_face_pixels_two_uv_domains_and_transparent_hat(self):
        raw = self.sources["diffuseTexture"]
        self.assertEqual(struct.unpack_from("<5I", raw, 12), (256,256,65536,1,9))
        self.assertEqual(len(raw), 87536)
        rects = ((32,192,64,224),(32,32,64,64),(160,32,192,64))
        data = []
        for x0,y0,x1,y1 in rects:
            pixels = [independent_dds_pixel(raw,x,y) for y in range(y0,y1) for x in range(x0,x1)]
            data.append(pixels)
        self.assertEqual(set(data[0]), {(0,0,0,0)})
        self.assertEqual(Counter(p[3] for p in data[1]), {255:1024})
        self.assertEqual(len(set(data[1])), 19)
        self.assertEqual(set(data[2]), {(0,0,0,0)})
        self.assertEqual(hashlib.sha256(bytes(v for p in data[1] for v in p)).hexdigest(),
                         "68a28b5e92166134024563519728c3777d3a7a603b5353c484ffe18b4e9746ed")
        self.assertEqual(independent_dds_pixel(raw,37,49), (255,255,255,255))
        self.assertEqual(independent_dds_pixel(raw,41,49), (82,60,139,255))
        self.assertEqual(independent_dds_pixel(raw,53,49), (82,60,139,255))
        self.assertEqual(independent_dds_pixel(raw,57,49), (255,255,255,255))
        self.assertEqual(independent_dds_pixel(raw,45,53), (106,64,49,255))
        self.assertNotEqual(independent_dds_pixel(raw,45,57), independent_dds_pixel(raw,45,53))
        evidence = self.report["audit"]["faceSampling"]
        self.assertEqual(evidence["sourceIfVSelectsStoredTopOriginDdsRows"]["alphaCounts"], {"0":1024})
        self.assertEqual(evidence["candidateIfVSelectsStoredTopOriginDdsRows"]["alphaCounts"], {"255":1024})
        self.assertEqual(evidence["candidateIfShaderInvertsV"], evidence["sourceIfVSelectsStoredTopOriginDdsRows"])
        self.assertFalse(evidence["shaderSamplingFilteringWrapLodAndTextureSelectionVerified"])

    def test_06_pure_loader_six_absolute_snapshots_without_game_cdmw_or_upstream_loader(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
            "import prepare_steve_head_uv_control as c;"
            "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('not pure'));"
            "c.headbase.load_candidate=forbidden;c.native.load_cdmw=forbidden;c.native.download_source=forbidden;"
            "c.headbase.head_material.read_native_material=forbidden;"
            "r,p,s=c.load_candidate(Path(sys.argv[1]));assert len(p)==1 and len(s)==6;"
            "assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
            "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);c.orientation.verify_snapshot(s)")
        result = subprocess.run([sys.executable,"-B","-c",code,str(self.report_path)],
            cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_07_payload_non_v_fields_each_source_and_relabelled_hash_tamper_refuse(self):
        with tempfile.TemporaryDirectory(prefix="head-uv-tamper-",dir=ROOT/"build") as temp:
            output = Path(temp)/"copy"
            shutil.copytree(self.output,output)
            for relative in self.report["files"]:
                path = output/relative
                raw = path.read_bytes()
                positions = (0,84,326,346,90529+8,90529+12,90529+20,90529+28,90529+36,90529+39,90529+1920,94657+10) if relative.startswith("resources/") else (len(raw)-1,)
                for position in positions:
                    changed = raw[:position]+bytes([raw[position]^1])+raw[position+1:]
                    path.write_bytes(changed)
                    with self.subTest(relative=relative,position=position), self.assertRaises(ValueError):
                        candidate.load_candidate(output/candidate.REPORT_NAME)
                    report = copy.deepcopy(self.report)
                    report["files"][relative] = hashlib.sha256(changed).hexdigest()
                    for row in report["sources"].values():
                        if row["localFile"] == relative:
                            row["sha256"] = report["files"][relative]
                    if relative.startswith("resources/"):
                        report["candidateResources"][0]["sha256"] = report["files"][relative]
                    (output/candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                    with self.assertRaises(ValueError):
                        candidate.load_candidate(output/candidate.REPORT_NAME)
                    path.write_bytes(raw)
                    (output/candidate.REPORT_NAME).write_bytes(self.report_raw)
            candidate.load_candidate(output/candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.make_report({**self.sources,"unknown":b"x"})
        with self.assertRaises(ValueError):
            candidate.make_report({**self.sources,"headPac":bytearray(self.source)})

    def test_08_manifest_unknown_duplicate_types_paths_fields_flags_and_runtime_claims_refuse(self):
        edits = [lambda r:r.update(unknown=True),lambda r:r.update(schemaVersion=True),lambda r:r.update(variant="other"),
            lambda r:r["candidateResources"][0].update(archiveFlags=True),
            lambda r:r["candidateResources"][0].update(templateArchiveFlags=0),
            lambda r:r["candidateResources"][0].update(localFile="../outside"),
            lambda r:r["candidateResources"][0].update(templatePath="../outside"),
            lambda r:r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r:r["sources"]["headPac"].update(localFile="../outside"),
            lambda r:r["files"].update({"../outside":"0"*64}),
            lambda r:r["integration"].update(installed=True),lambda r:r["integration"].update(installed=0),
            lambda r:r["integration"].update(nativeShaderUvConventionVerified=True),
            lambda r:r["replacementContract"].update(preservedMaterialSha256="0"*64),
            lambda r:r["audit"]["difference"]["fields"][0].update(byteSpan=[90529+8,90529+10]),
            lambda r:r["audit"]["difference"].update(actualChangedBytes=145),
            lambda r:r["audit"]["faceSampling"]["candidateIfVSelectsStoredTopOriginDdsRows"].update(alphaCounts={"0":1024}),
            lambda r:r["audit"]["structure"].update(additionalUvChannelsDecoded=True),
            lambda r:r["preservedDependencies"]["material"].update(addedAsCandidateResource=True)]
        with tempfile.TemporaryDirectory(prefix="head-uv-manifest-",dir=ROOT/"build") as temp:
            output = Path(temp)/"copy"
            shutil.copytree(self.output,output)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                (output/candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(edit=repr(edit)), self.assertRaises(ValueError):
                    candidate.load_candidate(output/candidate.REPORT_NAME)
            for raw in (b'{"schemaVersion":1,"schemaVersion":1}',json.dumps(self.report).encode(),b'{"schemaVersion":NaN}'):
                (output/candidate.REPORT_NAME).write_bytes(raw)
                with self.assertRaises(ValueError):
                    candidate.load_candidate(output/candidate.REPORT_NAME)
        with self.assertRaises(ValueError):
            candidate.package_path(self.output,"../outside")
        with self.assertRaises(ValueError):
            candidate.load_candidate(ROOT/"docs"/candidate.REPORT_NAME)

    def test_09_existing_overlap_canonical_children_and_stale_snapshot_protection(self):
        with tempfile.TemporaryDirectory(prefix="head-uv-output-",dir=ROOT/"build") as temp:
            directory=Path(temp)
            sentinel=directory/"keep"
            sentinel.write_bytes(b"keep")
            with mock.patch.object(candidate,"read_inputs",side_effect=AssertionError("input read")):
                with self.assertRaisesRegex(ValueError,"already exists"):
                    candidate.prepare(output=directory)
                for protected in (*candidate.PROTECTED_DIRS,candidate.DEFAULT_OUTPUT):
                    with self.subTest(protected=protected),self.assertRaisesRegex(ValueError,"overlaps"):
                        candidate.prepare(output=protected/"unpublished-uv-control-test")
            self.assertEqual(sentinel.read_bytes(),b"keep")
            fixture=directory/"fixture"
            shutil.copytree(self.output,fixture)
            _,_,snapshot=candidate.load_candidate(fixture/candidate.REPORT_NAME)
            pac=fixture/("resources/"+candidate.PAC_PATH)
            pac.write_bytes(self.payload[:-1]+bytes([self.payload[-1]^1]))
            with self.assertRaises(ValueError):
                candidate.orientation.verify_snapshot(snapshot)
            (fixture/candidate.REPORT_NAME).write_bytes(b" "*131073)
            with self.assertRaises(ValueError):
                candidate.load_candidate(fixture/candidate.REPORT_NAME)

    def test_10_source_race_detected_before_publication_and_after_complete_writes(self):
        with tempfile.TemporaryDirectory(prefix="head-uv-race-",dir=ROOT/"build") as temp:
            directory=Path(temp)
            source=directory/"source.pac"
            source.write_bytes(self.source)
            snapshot={source:self.source}
            output=directory/"early"
            real=candidate.make_report
            def make(sources):
                report=real(sources)
                source.write_bytes(self.source[:-1]+bytes([self.source[-1]^1]))
                return report
            with mock.patch.object(candidate,"read_inputs",return_value=(self.sources,snapshot)),mock.patch.object(candidate,"make_report",side_effect=make):
                with self.assertRaisesRegex(ValueError,"changed before publication"):
                    candidate.prepare(output=output)
            self.assertFalse(output.exists())
            source.write_bytes(self.source)
            real_load=candidate.load_candidate
            def load(path):
                result=real_load(path)
                source.write_bytes(self.source[:-1]+bytes([self.source[-1]^1]))
                return result
            with mock.patch.object(candidate,"read_inputs",return_value=(self.sources,snapshot)),mock.patch.object(candidate,"load_candidate",side_effect=load):
                with self.assertRaisesRegex(ValueError,"changed before publication"):
                    candidate.prepare(output=directory/"late")

    def test_11_real_owned_rebuild_identical_without_game_cdmw_network_and_inputs_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for a real isolated offline generation")
        _,inputs=candidate.read_inputs(candidate.DEFAULT_HEAD_BASECOLOR_REPORT)
        with tempfile.TemporaryDirectory(prefix="head-uv-rebuild-",dir=ROOT/"build") as temp:
            output=Path(temp)/"fresh"
            code=("import sys;sys.path.insert(0,'tools');import prepare_steve_head_uv_control as c;"
                "forbidden=lambda *a,**k: (_ for _ in ()).throw(AssertionError('game/CDMW/network forbidden'));"
                "c.native.load_cdmw=forbidden;c.native.download_source=forbidden;"
                "c.headbase.head_material.read_native_material=forbidden;c.headbase.assembly.read_context=forbidden;"
                "c.main();assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
            result=subprocess.run([sys.executable,"-B","-c",code,"--output",str(output)],
                cwd=ROOT,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            report,payloads,snapshot=candidate.load_candidate(output/candidate.REPORT_NAME)
            self.assertEqual((report,payloads),(self.report,self.payloads))
            self.assertEqual((output/candidate.REPORT_NAME).read_bytes(),self.report_raw)
            self.assertEqual(len(snapshot),6)
            self.assertEqual({p.relative_to(output).as_posix():raw for p,raw in snapshot.items()},
                             {p.relative_to(self.output).as_posix():raw for p,raw in self.snapshot.items()})
        candidate.orientation.verify_snapshot(inputs)
        candidate.orientation.verify_snapshot(self.snapshot)
        candidate.orientation.verify_snapshot(self.official)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args()
    HeadUvChecks.output,HeadUvChecks.rebuild=args.output,args.rebuild
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeadUvChecks))
    if result.wasSuccessful():
        _,inputs=candidate.read_inputs(candidate.DEFAULT_HEAD_BASECOLOR_REPORT)
        candidate.orientation.verify_snapshot(HeadUvChecks.official)
        print(json.dumps({"candidateResources":HeadUvChecks.report["candidateResources"],
            "fixedSourceCount":4,"candidateSnapshotCount":len(HeadUvChecks.snapshot),
            "upstreamInputSnapshotCount":len(inputs),"officialMcIndependentSnapshotCount":len(HeadUvChecks.official),
            "changedHalfFields":144,"nativeShaderUvConventionVerified":False,"mcHeadSkinVerified":False},indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__=="__main__":
    main()
