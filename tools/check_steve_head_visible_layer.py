"""Independent offline checks for the pinned MC transparent-hat index control."""
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

import prepare_steve_head_visible_layer as candidate

ROOT, native = candidate.ROOT, candidate.native
OLD_SHA = "c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55"
NEW_SHA = "7c222d1cb2d475d7e487c8cad87967afc63d27a1fa14b99d35c62a24f762d9ca"
PAMI_SHA = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
DDS_SHA = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
PRIOR_SHA = "56790fa5efb6a2b38ed5938f217d4ddc25b11d5b87c18a6640721fd15ae3a3af"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def independent_geometry(raw, short):
    """Read all scalar boundaries, records and indices without generator helpers."""
    stride, count = 40, 36 if short else 72
    size = 1992 if short else 2064
    require(len(raw) == (96505 if short else 96721) and raw[:4] == b"PAR ", "PAC size/magic")
    table = list(struct.iter_unpack("<II", raw[16:80]))
    require(all(x == 0 for x, _ in table), "Nonzero PAR pointers")
    require([s for _, s in table] == [90449, 0, size, size, size, 0, 0, 0], "PAR sections")
    require(raw[218:230] == bytes(12), "EyeCover has geometry")
    require(struct.unpack_from("<HHHIII", raw, 326) == (48, 48, 48, count, count, count), "Draw counts")
    require(struct.unpack_from("<H", raw, 344)[0] == 192, "Palette size")
    sections, cursor = [], 80
    for sid, (_, n) in enumerate(table):
        if not n:
            continue
        begin, cursor = cursor, cursor + n
        if sid == 0:
            require(begin == 80 and cursor == 90529, "Metadata coverage")
            continue
        lod = 4 - sid
        require(struct.unpack_from("<I", raw, 85 + 4 * lod)[0] == begin, "Vertex mirror")
        require(struct.unpack_from("<I", raw, 97 + 4 * lod)[0] == begin + 48 * stride, "Index mirror")
        records = [raw[begin + i * stride:begin + (i + 1) * stride] for i in range(48)]
        indices = list(struct.unpack_from("<" + "H" * count, raw, begin + 48 * stride))
        require(begin + 48 * stride + len(indices) * 2 == cursor, "Unaccounted geometry gap/tail")
        require(indices[:36] == [q * 4 + i for q in range(6) for i in (0, 1, 2, 0, 2, 3)], "Lost base faces")
        if not short:
            require(indices[36:] == [q * 4 + i for q in range(6, 12) for i in (0, 1, 2, 0, 2, 3)], "Hat source faces")
        require(all(len(set(indices[i:i + 3])) == 3 for i in range(0, count, 3)), "Degenerate face")
        require(max(indices) == (23 if short else 47) and min(indices) == 0, "Index ownership")
        sections.append({"lod": lod, "section": sid, "start": begin, "records": records, "indices": indices})
    require(cursor == len(raw), "Trailing bytes")
    return sections


def independent_bc3(raw, x, y):
    """Separate BC3 bit-index expansion; never calls the candidate pixel helper."""
    require(raw[:4] == b"DDS " and raw[84:88] == b"DXT5", "BC3 DDS format")
    block_id = (y // 4) * 64 + x // 4
    b = raw[128 + 16 * block_id:128 + 16 * (block_id + 1)]
    require(len(b) == 16, "BC3 block bounds")
    alpha_word, color_word = int.from_bytes(b[2:8], "little"), int.from_bytes(b[12:16], "little")
    alpha_ids, color_ids = [], []
    for _ in range(16):
        alpha_ids.append(alpha_word % 8); alpha_word //= 8
        color_ids.append(color_word % 4); color_word //= 4
    first, second = b[0], b[1]
    denom = 7 if first > second else 5
    alphas = [first, second] + [(first * (denom - k) + second * k) // denom for k in range(1, denom)]
    if denom == 5:
        alphas += [0, 255]
    colors = []
    for word in struct.unpack("<2H", b[8:12]):
        colors.append(tuple(word // divisor % (maximum + 1) * 255 // maximum
                            for divisor, maximum in ((2048, 31), (32, 63), (1, 31))))
    colors += [tuple((a * l + c * r) // 3 for a, c in zip(colors[0], colors[1]))
               for l, r in ((2, 1), (1, 2))]
    i = (y % 4) * 4 + x % 4
    return (*colors[color_ids[i]], alphas[alpha_ids[i]])


def accessor(document, raw, index, components, component_type):
    a = document["accessors"][index]; b = document["bufferViews"][a["bufferView"]]
    require(a["componentType"] == component_type and b.get("buffer", 0) == 0 and "byteStride" not in b, "Accessor ABI")
    require(a["type"] == ("SCALAR" if components == 1 else "VEC" + str(components)), "Accessor shape")
    fmt = "<" + ("f" if component_type == 5126 else "H") * components
    start = b.get("byteOffset", 0) + a.get("byteOffset", 0); end = start + a["count"] * struct.calcsize(fmt)
    require(end <= len(raw) and end <= b.get("byteOffset", 0) + b["byteLength"], "Accessor bounds")
    return list(struct.iter_unpack(fmt, raw[start:end]))


class VisibleLayerChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report, cls.payloads, cls.snapshot = candidate.load_candidate(cls.output / candidate.REPORT_NAME)
        cls.sources = {k: (cls.output / rel).read_bytes() for k, (rel, _) in candidate.SOURCE_SPECS.items()}
        cls.source, cls.payload = cls.sources["headPac"], cls.payloads[candidate.PAC_PATH]
        cls.old, cls.new = independent_geometry(cls.source, False), independent_geometry(cls.payload, True)
        cls.official = {name: (ROOT / "build/steve-1.21.1" / name).read_bytes() for name in candidate.MC_SOURCE_PINS}
        for name, digest in candidate.MC_SOURCE_PINS.items():
            require(hashlib.sha256(cls.official[name]).hexdigest() == digest, "MC source: " + name)

    def test_01_four_pins_single_pac_standard_flags_and_false_integration(self):
        self.assertEqual({k: hashlib.sha256(v).hexdigest() for k, v in self.sources.items()}, {
            "headPac": OLD_SHA, "preservedMaterial": PAMI_SHA, "diffuseTexture": DDS_SHA, "headUvReport": PRIOR_SHA})
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), NEW_SHA)
        self.assertEqual(self.report["candidateResources"], [{"kind": "skinnedMesh", "virtualPath": candidate.PAC_PATH,
            "localFile": "resources/" + candidate.PAC_PATH, "sha256": NEW_SHA, "payloadSize": 96505,
            "sourceVirtualPath": candidate.PAC_PATH, "templatePath": candidate.PAC_PATH,
            "templateSha256": OLD_SHA, "templateArchiveFlags": 1, "archiveFlags": 1}])
        self.assertEqual(set(self.payloads), {candidate.PAC_PATH})
        self.assertTrue(all(value is False for value in self.report["integration"].values()))
        self.assertEqual(self.report["preservedDependencies"]["material"]["expectedArchiveFlags"], 50)
        self.assertEqual(self.report["preservedDependencies"]["diffuse"]["expectedArchiveFlags"], 0)
        self.assertEqual(self.report["audit"]["textureEvidence"]["minecraftMapping"]["directGltfTriangleIndexRemapClaimed"], False)

    def test_02_exact_all_sections_48_records_36_base_indices_and_no_gaps(self):
        self.assertEqual([s["start"] for s in self.new], [90529, 92521, 94513])
        self.assertEqual(len(self.source) - len(self.payload), 216)
        for a, b in zip(self.old, self.new):
            self.assertEqual(a["records"], b["records"])
            self.assertEqual(a["indices"][:36], b["indices"])
            self.assertEqual({i for i in b["indices"]}, set(range(24)))
            self.assertEqual(len(b["records"]), 48)
        self.assertEqual(self.source[297:321], self.payload[297:321])
        self.assertEqual(self.source[344:90529], self.payload[344:90529])

    def test_03_independent_all_12_metadata_fields_and_byte_exact_inverse(self):
        edits = [(332 + 4 * i, 72, 36) for i in range(3)]
        edits += [(36, 2064, 1992), (44, 2064, 1992), (52, 2064, 1992)]
        edits += [(93, 90529, 90529), (89, 92593, 92521), (85, 94657, 94513)]
        edits += [(105, 92449, 92449), (101, 94513, 94441), (97, 96577, 96433)]
        allowed = {n for at, old, new in edits if old != new for n in range(at, at + 4)}
        for at, old, new in edits:
            self.assertEqual(struct.unpack_from("<I", self.source, at)[0], old)
            self.assertEqual(struct.unpack_from("<I", self.payload, at)[0], new)
        for n in range(90529):
            if n not in allowed:
                self.assertEqual(self.source[n], self.payload[n], n)
        inverse = bytearray(self.payload[:90529])
        for at, old, new in edits:
            struct.pack_into("<I", inverse, at, old)
        for a, b in zip(self.old, self.new):
            inverse.extend(self.payload[b["start"]:b["start"] + 1992])
            inverse.extend(self.source[a["start"] + 1992:a["start"] + 2064])
        self.assertEqual(bytes(inverse), self.source)
        self.assertEqual(candidate.restore_pac(self.payload, self.source), self.source)
        self.assertEqual(len(self.report["audit"]["difference"]["metadataFields"]), 12)

    def test_04_real_mc_head_hat_accessors_uv_quads_and_indices(self):
        j, binary = json.loads(self.official["steve.gltf"]), self.official["steve.bin"]
        for name, mesh_index, first in (("head", 0, 0), ("hat", 6, 24)):
            m = j["meshes"][mesh_index]; self.assertEqual(m["name"], name)
            p = m["primitives"][0]
            uvs = accessor(j, binary, p["attributes"]["TEXCOORD_0"], 2, 5126)
            points = accessor(j, binary, p["attributes"]["POSITION"], 3, 5126)
            self.assertEqual(len(points), 24)
            indices = [x[0] for x in accessor(j, binary, p["indices"], 1, 5123)]
            self.assertEqual(indices, [4 * q + i for q in range(6) for i in (0, 1, 2, 0, 2, 3)])
            expected_uvs = [uvs[4 * q + i] for q in range(6) for i in (0, 3, 2, 1)]
            for lod in self.old:
                found = [struct.unpack_from("<ee", r, 8) for r in lod["records"][first:first + 24]]
                self.assertEqual(found, expected_uvs)
                self.assertEqual(lod["indices"][first // 24 * 36:first // 24 * 36 + 36], [i + first for i in indices])
            for q in range(6):
                face = points[4 * q:4 * q + 4]
                self.assertEqual(sum(min(p[k] for p in face) == max(p[k] for p in face) for k in range(3)), 1)

    def test_05_independent_real_bc3_six_hat_and_six_base_alpha_and_all_mips(self):
        d = self.sources["diffuseTexture"]
        self.assertEqual(struct.unpack_from("<5I", d, 12), (256, 256, 65536, 1, 9))
        end = 128
        for level in range(9):
            side = max(1, 256 >> level); end += max(1, (side + 3) // 4) ** 2 * 16
        self.assertEqual(end, len(d))
        for q, row in enumerate(self.report["audit"]["textureEvidence"]["quads"]):
            coords = [struct.unpack_from("<ee", r, 8) for r in self.old[0]["records"][4 * q:4 * q + 4]]
            rect = (int(256 * min(x[0] for x in coords)), int(256 * min(x[1] for x in coords)),
                    int(256 * max(x[0] for x in coords)), int(256 * max(x[1] for x in coords)))
            pixels = [independent_bc3(d, x, y) for y in range(rect[1], rect[3]) for x in range(rect[0], rect[2])]
            self.assertEqual(len(pixels), 1024)
            self.assertEqual(Counter(x[3] for x in pixels), {255 if q < 6 else 0: 1024})
            if q >= 6:
                self.assertEqual(set(pixels), {(0, 0, 0, 0)})
            self.assertEqual(list(rect), row["ddsEvidence"]["pixelRectHalfOpen"])
            self.assertEqual(hashlib.sha256(bytes(c for p in pixels for c in p)).hexdigest(), row["ddsEvidence"]["rgbaSha256"])
        self.assertEqual(independent_bc3(d, 37, 49), (255, 255, 255, 255))
        self.assertEqual(independent_bc3(d, 41, 49), (82, 60, 139, 255))
        self.assertEqual(independent_bc3(d, 45, 53), (106, 64, 49, 255))

    def test_06_pure_load_six_absolute_snapshots_without_game_cdmw_network_upstream(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
                "import prepare_steve_head_visible_layer as c;"
                "def_fail=lambda *a,**k:(_ for _ in ()).throw(AssertionError('forbidden'));"
                "c.native.load_cdmw=def_fail;c.native.download_source=def_fail;c.uv.load_candidate=def_fail;"
                "r,p,s=c.load_candidate(Path(sys.argv[1]));assert len(s)==6;"
                "assert all(isinstance(k,Path) and k.is_absolute() for k in s);"
                "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules);c.orientation.verify_snapshot(s)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.output / candidate.REPORT_NAME)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.snapshot), 6)

    def test_07_non_index_metadata_vertex_tail_and_source_hash_relabelling_refuse(self):
        with tempfile.TemporaryDirectory(prefix="visible-negative-", dir=ROOT / "build") as tmp:
            fixture = Path(tmp) / "copy"; shutil.copytree(self.output, fixture)
            original_report = (fixture / candidate.REPORT_NAME).read_bytes()
            payload_path = fixture / ("resources/" + candidate.PAC_PATH)
            for offset in (0, 52, 85, 218, 297, 326, 344, 90400, 90529, 90537, 90539, 90541, 90557, 90565, 92449, 96504):
                raw = bytearray(self.payload); raw[offset] ^= 1; payload_path.write_bytes(raw)
                # Keep the admitted report intact first: this reaches payload comparison.
                (fixture / candidate.REPORT_NAME).write_bytes(original_report)
                with self.subTest(payload_offset=offset), self.assertRaisesRegex(ValueError, "payload differs"):
                    candidate.load_candidate(fixture / candidate.REPORT_NAME)
                report = copy.deepcopy(self.report)
                digest = hashlib.sha256(raw).hexdigest(); report["candidateResources"][0]["sha256"] = digest
                report["files"]["resources/" + candidate.PAC_PATH] = digest
                (fixture / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    candidate.load_candidate(fixture / candidate.REPORT_NAME)
            payload_path.write_bytes(self.payload)
            for key, (rel, _) in candidate.SOURCE_SPECS.items():
                path = fixture / rel; raw = bytearray(self.sources[key]); raw[-1] ^= 1; path.write_bytes(raw)
                report = copy.deepcopy(self.report); digest = hashlib.sha256(raw).hexdigest()
                report["sources"][key]["sha256"] = digest; report["files"][rel] = digest
                (fixture / candidate.REPORT_NAME).write_bytes(candidate.report_bytes(report))
                with self.subTest(source=key), self.assertRaises(ValueError):
                    candidate.load_candidate(fixture / candidate.REPORT_NAME)
                path.write_bytes(self.sources[key])
            (fixture / candidate.REPORT_NAME).write_bytes(original_report)
            candidate.load_candidate(fixture / candidate.REPORT_NAME)

    def test_08_full_report_types_unknown_duplicate_path_and_false_claims_refuse(self):
        changes = [lambda r: r.update(unknown=True), lambda r: r.update(schemaVersion=True),
            lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
            lambda r: r["candidateResources"][0].update(archiveFlags=True),
            lambda r: r["candidateResources"][0].update(templatePath="../escape"),
            lambda r: r["candidateResources"][0].update(localFile="../escape"),
            lambda r: r["sources"]["headPac"].update(localFile="../escape"),
            lambda r: r["audit"]["difference"].update(removedIndexBytes=0),
            lambda r: r["audit"]["textureEvidence"].update(hatAlphaCounts={"255":6144}),
            lambda r: r["audit"]["candidateStructure"].update(activeMainDraws=2),
            lambda r: r["preservedDependencies"]["diffuse"].update(addedAsCandidateResource=True),
            lambda r: r["integration"].update(mcHeadSkinVerified=True)]
        with mock.patch.object(candidate.orientation, "verify_snapshot", return_value=None):
            for change in changes:
                report = copy.deepcopy(self.report); change(report)
                with mock.patch.object(candidate, "bounded_read", side_effect=lambda p, limit=0: candidate.report_bytes(report) if p.name == candidate.REPORT_NAME else self.snapshot[p]):
                    with self.assertRaises(ValueError): candidate.load_candidate(self.output / candidate.REPORT_NAME)
            raw = b'{"schemaVersion":1,"schemaVersion":1}'
            with mock.patch.object(candidate, "bounded_read", return_value=raw), self.assertRaises(ValueError):
                candidate.load_candidate(self.output / candidate.REPORT_NAME)
        with self.assertRaises(ValueError): candidate.make_report({**self.sources,"unknown":b"x"})
        with self.assertRaises(ValueError): candidate.make_report({**self.sources,"headPac":bytearray(self.source)})
        with self.assertRaises(ValueError): candidate.package_path(self.output, "../escape")

    def test_09_existing_protected_sources_overlays_and_canonical_child_early_refuse(self):
        paths = [self.output, candidate.DEFAULT_OUTPUT / "never-create",
                 ROOT / "build/steve-head-uv-control/never-create",
                 ROOT / "build/steve-head-uv-probe-overlay/never-create",
                 ROOT / "build/steve-head-basecolor-probe-overlay/never-create",
                 ROOT / "build/steve-body-native-material-probe-overlay/never-create",
                 ROOT / "build/steve-clothing-control-probe-overlay/never-create",
                 ROOT / "build/cdmw-fixed-source/never-create", ROOT / "build"]
        with mock.patch.object(candidate, "read_inputs", side_effect=AssertionError("inputs must not be read")):
            for path in paths:
                with self.subTest(path=path), self.assertRaises(ValueError): candidate.prepare(path)
        for path in paths[1:-1]: self.assertFalse(path.exists())

    def test_10_snapshot_race_before_publication_and_after_readback_refuse(self):
        with tempfile.TemporaryDirectory(prefix="visible-race-", dir=ROOT / "build") as tmp:
            directory = Path(tmp); source = directory / "source.pac"; source.write_bytes(self.source)
            snapshot = {source: self.source}; real = candidate.make_report
            def changed(s):
                report = real(s); source.write_bytes(self.source[:-1] + bytes([self.source[-1] ^ 1])); return report
            with mock.patch.object(candidate, "read_inputs", return_value=(self.sources, snapshot)), mock.patch.object(candidate, "make_report", side_effect=changed), mock.patch.object(candidate, "verify_official_mapping", return_value={}), mock.patch.object(candidate, "verify_cdmw", return_value=None):
                with self.assertRaises(ValueError): candidate.prepare(directory / "early")
            self.assertFalse((directory / "early").exists())
            source.write_bytes(self.source); load = candidate.load_candidate
            def changed_after(path):
                result = load(path); source.write_bytes(self.source[:-1] + bytes([self.source[-1] ^ 1])); return result
            with mock.patch.object(candidate, "read_inputs", return_value=(self.sources, snapshot)), mock.patch.object(candidate, "load_candidate", side_effect=changed_after), mock.patch.object(candidate, "verify_official_mapping", return_value={}), mock.patch.object(candidate, "verify_cdmw", return_value=None):
                with self.assertRaises(ValueError): candidate.prepare(directory / "late")

    def test_11_independent_real_cdmw_all_lods_original_draw_bounds_and_channels(self):
        code = """
import sys
from pathlib import Path
sys.path.insert(0,'tools')
import prepare_steve_head_visible_layer as c
c.native.load_cdmw(c.ROOT/'build/cdmw-fixed-source',c.ROOT/'build/cdmw-deps')
from cdmw.modding.mesh_parser import _parse_par_sections,_find_pac_descriptors,_parse_pac_geometry_section
source=Path(sys.argv[1]).read_bytes(); payload=Path(sys.argv[2]).read_bytes()
parsed=[]
for raw,indices,faces in ((source,72,24),(payload,36,12)):
 ds=_find_pac_descriptors(raw,80,90449,3)
 assert len(ds)==1 and ds[0].name=='CD_PHM_00_Head_0001_Macduff' and ds[0].descriptor_offset==286
 assert ds[0].vertex_counts==[48,48,48,0] and ds[0].index_counts==[indices,indices,indices,0]
 secs={s['index']:s for s in _parse_par_sections(raw)};lods=[]
 assert set(secs)=={0,2,3,4}
 for sid in (2,3,4):
  m=_parse_pac_geometry_section(raw,c.PAC_PATH,ds,secs[sid],4-sid)
  assert len(m.submeshes)==1 and m.total_vertices==48 and m.total_faces==faces
  p=m.submeshes[0];assert p.source_index_count==indices and p.source_vertex_stride==40
  assert max(max(f) for f in p.faces)==(47 if faces==24 else 23)
  for point in p.vertices:
   assert all(ds[0].bbox_min[k]-1e-6 <= point[k] <= ds[0].bbox_min[k]+ds[0].bbox_extent[k]+1e-6 for k in range(3))
  lods.append(p)
 parsed.append(lods)
for a,b in zip(*parsed):
 assert b.faces==a.faces[:12]
 for key in ('vertices','uvs','normals','bone_indices','bone_weights','source_bone_palette','source_bbox_min','source_bbox_extent','name','material'):
  assert getattr(a,key)==getattr(b,key),key
"""
        result = subprocess.run([sys.executable,"-B","-c",code,
            str(self.output / candidate.SOURCE_SPECS["headPac"][0]),
            str(self.output / ("resources/" + candidate.PAC_PATH))], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_12_real_owned_rebuild_identical_inputs_and_strict_loader(self):
        if not self.rebuild: self.skipTest("Use --rebuild for an independent owned rebuild")
        snapshot = {**self.snapshot, **{ROOT/"build/steve-1.21.1"/n:b for n,b in self.official.items()}}
        with tempfile.TemporaryDirectory(prefix="visible-rebuild-", dir=ROOT / "build") as tmp:
            output = Path(tmp) / "new"
            result = subprocess.run([sys.executable,"-B",str(ROOT/"tools/prepare_steve_head_visible_layer.py"),"--output",str(output)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report, payloads, snap = candidate.load_candidate(output/candidate.REPORT_NAME)
            self.assertEqual(report,self.report); self.assertEqual(payloads,self.payloads)
            self.assertEqual(len(snap),6)
            for rel in [*self.report["files"],candidate.REPORT_NAME]:
                self.assertEqual((output/rel).read_bytes(),(self.output/rel).read_bytes())
        candidate.orientation.verify_snapshot(snapshot)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args();VisibleLayerChecks.output=args.output;VisibleLayerChecks.rebuild=args.rebuild
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(VisibleLayerChecks))
    if result.wasSuccessful():
        print(json.dumps({"candidateResources":VisibleLayerChecks.report["candidateResources"],
            "sourceSnapshotFiles":len(VisibleLayerChecks.snapshot),"integration":VisibleLayerChecks.report["integration"]},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=="__main__":
    main()
