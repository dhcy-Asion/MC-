"""Independent offline checks for the explicit B_face_com Steve head experiment.

No game/process access or installation. A passing result certifies only fixed
binary construction and neutral replay, not native rendering or animation.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import prepare_steve_native_head_root as candidate
import prepare_native_steve as native
import prepare_steve_assembly as assembly
import analyze_steve_rig as rig
from check_steve_orientation import read_native_frame

ROOT = native.ROOT
NATIVE_HEAD_PATH = "character/model/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac"
NATIVE_HEAD_SHA = "779cc8247bd72e49c8a86c7cec2535682371d2adff07380e8fe9e9288cab539d"
STEVE_HEAD_PATH = "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac"
STEVE_HEAD_SHA = "e75f7a7989137756c4744a16c001bce8f91a6f0b6caabb84214f5d42b710d9b9"
STEVE_MATERIAL_SHA = "01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538"
HEAD_PABC = "character/binary/skeletonvariation/1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"
HEAD_PABC_SHA = "2f761a89f87e38551a4e20b22f9b3d4b589067a2863844dde0879d37a7aec0e5"
MAIN_DRAW = "CD_PHM_00_Head_0001_Macduff"
EYE_DRAW = "CD_PHM_00_Head_0001_Macduff_Eyecover"
LOD_SECTIONS = {0: 4, 1: 3, 2: 2}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unit(vector):
    length = math.sqrt(sum(x*x for x in vector))
    require(length > 1e-12, "Degenerate direction")
    return tuple(x / length for x in vector)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def xml_shape(element):
    """Compare semantic XML without serialization whitespace/order artifacts."""
    return element.tag, dict(element.attrib), (element.text or "").strip(), tuple(xml_shape(c) for c in element)


def independent_root_neutral(pab, pabc):
    bones, _ = rig.parse_pab_records(pab)
    rows, duplicate = rig.parse_pabc_records(pabc, bones)
    require(len(rows) == 207 and not duplicate, "Head PABC record contract changed")
    root = bones[122]
    require((root["name"], root["parent"]) == ("B_face_com", 93), "Wrong face root hierarchy")
    matches = [r for r in rows if r["boneIndex"] == 122]
    require(len(matches) == 1, "Head PABC does not uniquely cover B_face_com")
    # Independently apply the documented paired-row reconciliation before
    # inverseBind * neutralBind. No generator compensation helper is called.
    target = tuple(matches[0]["blocks"][0])
    for axes in ((0, 1), (0, 2), (1, 2)):
        aligned = tuple(-v if i//4 in axes and i%4 < 3 else v for i, v in enumerate(target))
        if max(abs(a-b) for a, b in zip(aligned, root["bind"])) <= 1e-4:
            target = aligned
            break
    matrix = tuple(math.fsum(root["inverse"][r*4+k]*target[k*4+c] for k in range(4))
                   for r in range(4) for c in range(4))
    return bones, rows, matrix


def resolved_large_palette_tables(payload, bones):
    """Locate every >=192-entry metadata table resolvable to unique PAB hashes.

    This explicitly checks the count/hash location, rather than trusting the
    CDMW resolver's longest-match scan or the candidate's claimed slot list.
    """
    known = {b["hash"] for b in bones}
    result = []
    for offset in range(80, 90529-2):
        count = struct.unpack_from("<H", payload, offset)[0]
        if not 192 <= count <= 447 or offset+2+count*4 > 90529:
            continue
        if struct.unpack_from("<I", payload, offset+2)[0] not in known:
            continue
        values = struct.unpack_from("<"+"I"*count, payload, offset+2)
        if len(set(values)) == count and all(value in known for value in values):
            result.append((offset, count))
    return result


def independent_pac_audit(payload, donor, source, pab, pabc):
    """Fail closed on binary structure, raw skin, geometry, UV, and neutral frame."""
    from cdmw.modding.mesh_parser import parse_pac, _parse_par_sections, _find_pac_descriptors, _parse_pac_geometry_section, resolve_pac_bone_palette
    from cdmw.modding.skeleton_parser import parse_pab
    require(native.sha256(donor) == NATIVE_HEAD_SHA, "Native head donor fingerprint changed")
    require(native.sha256(source) == STEVE_HEAD_SHA, "Steve target fingerprint changed")
    require(native.sha256(pab) == native.TEMPLATE_HASHES[native.SKELETON], "PAB fingerprint changed")
    require(native.sha256(pabc) == HEAD_PABC_SHA, "Head PABC fingerprint changed")
    sections = {s["index"]: s for s in _parse_par_sections(payload)}
    require(set(sections) == {0, 2, 3, 4}, "Head must use exactly sections 0,2,3,4")
    require(sections[0] == {"index": 0, "offset": 80, "size": 90449}, "Native metadata size moved")
    require(len(payload) == 80 + 90449 + 3*(48*40 + 72*2), "Candidate has old or trailing geometry")
    header_allowed = {i for sid in (2, 3, 4) for i in range(20+sid*8, 24+sid*8)}
    require(all(a == b or i in header_allowed for i, (a, b) in enumerate(zip(payload[:80], donor[:80]))), "Unexplained header mutation")
    allowed = set(range(85, 109)) | set(range(218, 230)) | set(range(297, 321)) | set(range(326, 344)) | set(range(346, 350))
    require(all(a == b or i in allowed for i, (a, b) in enumerate(zip(payload[:90529], donor[:90529])) if i >= 80), "Unexplained metadata mutation")
    require(struct.unpack_from("<I", payload, 80)[0] == 2 and payload[84] == 3, "Native flags or LOD count changed")
    require(payload[218:230] == bytes(12), "Eyecover geometry remains")
    require(struct.unpack_from("<3H3I", payload, 326) == (48, 48, 48, 72, 72, 72), "Main draw counts differ")
    lo, extent = struct.unpack_from("<3f", payload, 297), struct.unpack_from("<3f", payload, 309)
    require(all(math.isfinite(v) for v in (*lo, *extent)) and all(v > 0 for v in extent), "Invalid six-float bbox")
    bones, rows, matrix = independent_root_neutral(pab, pabc)
    inverse = rig.inverse(matrix)
    hashes = struct.unpack_from("<192I", payload, 346)
    original_hashes = struct.unpack_from("<192I", donor, 346)
    require(resolved_large_palette_tables(donor, bones) == [(344, 192)], "Native palette table is ambiguous")
    require(resolved_large_palette_tables(payload, bones) == [(344, 192)], "Candidate palette table is ambiguous")
    require(struct.unpack_from("<H", payload, 344)[0] == 192 and len(set(hashes)) == 192, "Palette length or uniqueness changed")
    require(hashes[0] == bones[122]["hash"] and hashes[1:] == original_hashes[1:], "Only slot0 may be rebound to B_face_com")
    require(bones[122]["hash"] not in original_hashes and bones[93]["hash"] not in hashes, "Unexpected original or Head93 binding")
    skeleton = parse_pab(pab, native.SKELETON)
    palette = resolve_pac_bone_palette(payload, skeleton)
    require(len(palette) == 192 and palette[0] == 122, "Candidate palette does not resolve to root122")
    target = parse_pac(source, STEVE_HEAD_PATH).submeshes[0]
    require(len(target.vertices) == 48 and len(target.faces) == 24, "Unexpected target head topology")
    precompensated = [tuple(math.fsum((*point, 1.)[k]*inverse[k*4+c] for k in range(4))
                           for c in range(3)) for point in target.vertices]
    expected_lo = tuple(min(point[a] for point in precompensated) for a in range(3))
    expected_extent = tuple(max(point[a] for point in precompensated)-expected_lo[a] for a in range(3))
    require(payload[297:321] == struct.pack("<6f", *expected_lo, *expected_extent), "Bbox is not the compensated target's six float32 values")
    descriptors = _find_pac_descriptors(payload, 80, 90449, 3)
    require(len(descriptors) == 1 and descriptors[0].name == MAIN_DRAW, "Old active draw remains")
    maximum, normal_min, frame_min = 0.0, 1.0, 1.0
    payloads, lod_rows = [], []
    for lod, sid in LOD_SECTIONS.items():
        section = sections[sid]
        require(section["offset"] == 90529 + (sid-2)*2064 and section["size"] == 2064, "Wrong section placement or old section4")
        require(struct.unpack_from("<I", payload, 85+lod*4)[0] == section["offset"], "Wrong mirrored LOD start")
        require(struct.unpack_from("<I", payload, 97+lod*4)[0] == section["offset"]+1920, "Wrong vertex/index split")
        mesh = _parse_pac_geometry_section(payload, STEVE_HEAD_PATH, descriptors, section, lod)
        require(len(mesh.submeshes) == 1 and (mesh.total_vertices, mesh.total_faces) == (48, 24), "Incomplete head LOD")
        part = mesh.submeshes[0]
        require(part.faces == target.faces and part.uvs == target.uvs, "Head surface or UV topology changed")
        raw_indices = struct.unpack_from("<72H", payload, section["offset"]+1920)
        require(tuple(i for f in target.faces for i in f) == raw_indices and max(raw_indices) < 48, "Raw triangle indices changed")
        posed = []
        for i, (point, offset, source_offset) in enumerate(zip(part.vertices, part.source_vertex_offsets, target.source_vertex_offsets)):
            record = payload[offset:offset+40]
            slots = tuple((word >> (k*10)) & 1023 for word in struct.unpack_from("<2I", record, 20) for k in range(3))
            weights = tuple(record[28:34])
            require(record[20:28] == bytes(8) and slots == (0,)*6 and weights == (255, 0, 0, 0, 0, 0), "Raw weights must bind solely to slot0")
            require(sum(weights) == 255 and all(w > 0 for w in weights if w), "Unnormalized raw byte weights")
            require(record[34:36] == b"\0\0" and record[39] & 63 == 63, "Unexpected guide/extra weights")
            require(record[8:16] == source[source_offset+8:source_offset+16], "UV or fixed extra lanes changed")
            require(record[36:40] == source[source_offset+36:source_offset+40], "Opaque vertex shader lanes changed")
            q = struct.unpack_from("<3H", record)
            require(all(v <= 32767 for v in q), "Position exceeds native UNORM15 range")
            decoded = tuple(lo[a]+q[a]/32767*extent[a] for a in range(3))
            require(rig.distance(point, decoded) < 1e-12, "Independent quantized decode disagrees")
            moved = tuple(math.fsum((*decoded, 1.)[k]*matrix[k*4+c] for k in range(4)) for c in range(3))
            posed.append(moved)
            maximum = max(maximum, rig.distance(moved, target.vertices[i]))
            n, v, sign = read_native_frame(payload, offset)
            tn, tv, tsign = read_native_frame(source, source_offset)
            posed_n = unit(tuple(math.fsum(n[k]*inverse[c*4+k] for k in range(3)) for c in range(3)))
            posed_v = unit(tuple(math.fsum(v[k]*matrix[k*4+c] for k in range(3)) for c in range(3)))
            normal_min, frame_min = min(normal_min, dot(posed_n, unit(tn))), min(frame_min, dot(posed_v, unit(tv)))
            require(sign == tsign, "Frame handedness changed")
        for face in part.faces:
            a, b, c = (posed[i] for i in face)
            ab, ac = tuple(y-x for x, y in zip(a, b)), tuple(y-x for x, y in zip(a, c))
            cross = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0])
            require(dot(cross, target.normals[face[0]]) > 0, "Target head surface is degenerate or inverted")
        payloads.append(payload[section["offset"]:section["offset"]+section["size"]])
        lod_rows.append({"lod": lod, "section": sid, "vertices": 48, "triangles": 24})
    require(len(set(payloads)) == 1, "LOD geometry/skin/frame differs")
    require(maximum < 0.0001, "Neutral quantized target error exceeds 0.1mm")
    require(min(normal_min, frame_min) > .995, "Neutral direction/frame replay differs")
    return {"maximumNeutralErrorMetres": maximum, "minimumNormalDot": normal_min, "minimumVDot": frame_min, "lods": lod_rows}


class NativeHeadRootChecks(unittest.TestCase):
    output = None
    rebuild = False

    @classmethod
    def setUpClass(cls):
        cls.output = native.output_directory(cls.output or candidate.DEFAULT_OUTPUT)
        cls.report_path = cls.output / candidate.REPORT_NAME
        cls.report_raw = cls.report_path.read_bytes()
        cls.report, cls.files, cls.snapshot = candidate.load_candidate(cls.report_path)
        native.load_cdmw(ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps")
        resources = cls.report["candidateResources"]
        cls.pac_row = next(r for r in resources if r["virtualPath"].endswith(".pac"))
        cls.material_row = next(r for r in resources if r["virtualPath"].endswith(".pac_xml"))
        cls.pac = cls.files.get(cls.pac_row["localFile"], cls.files.get(cls.pac_row["virtualPath"]))
        cls.material = cls.files.get(cls.material_row["localFile"], cls.files.get(cls.material_row["virtualPath"]))
        # Source payloads are selected by their fixed fingerprints, not report labels.
        def source(digest):
            matches = [(cls.output / relative).read_bytes() for relative, found in cls.report["files"].items() if found == digest]
            if len(matches) != 1:
                raise ValueError("Candidate must contain exactly one copy of each fixed source")
            data = matches[0]
            if native.sha256(data) != digest:
                raise ValueError("Independent fixed source fingerprint mismatch")
            return data
        cls.donor = source(NATIVE_HEAD_SHA)
        cls.target = source(STEVE_HEAD_SHA)
        cls.pab = source(native.TEMPLATE_HASHES[native.SKELETON])
        cls.pabc = source(HEAD_PABC_SHA)
        cls.source_material = source(STEVE_MATERIAL_SHA)
        cls.audit = independent_pac_audit(cls.pac, cls.donor, cls.target, cls.pab, cls.pabc)

    def test_01_pure_loader_fixed_resources_and_false_integration(self):
        code = ("import sys;from pathlib import Path;sys.path.insert(0,'tools');"
                "import prepare_steve_native_head_root as c;"
                "r,f,s=c.load_candidate(Path(sys.argv[1]));"
                "assert not any(k=='cdmw' or k.startswith('cdmw.') for k in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.report_path)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.report["candidateResources"]), 2)
        self.assertEqual(tuple(self.pac_row[key] for key in ("kind", "templateArchiveFlags", "archiveFlags")), ("skinnedMesh", 1, 1))
        self.assertEqual(tuple(self.material_row[key] for key in ("kind", "templateArchiveFlags", "archiveFlags")), ("skinnedMaterial", 50, 50))
        self.assertTrue(self.report["integration"])
        self.assertTrue(all(v is False for v in self.report["integration"].values()))
        for relative, digest in self.report["files"].items():
            self.assertEqual(native.file_hash(self.output / relative), digest)
        for row in self.report["candidateResources"]:
            self.assertEqual(row["localFile"], "resources/"+row["virtualPath"])
            self.assertEqual(native.file_hash(self.output / row["localFile"]), row["sha256"])

    def test_02_three_complete_lods_raw_skin_surface_and_neutral_frame(self):
        self.assertEqual([r["section"] for r in self.audit["lods"]], [4, 3, 2])
        self.assertLess(self.audit["maximumNeutralErrorMetres"], .0001)
        self.assertGreater(self.audit["minimumNormalDot"], .995)
        self.assertGreater(self.audit["minimumVDot"], .995)

    def test_03_root_policy_is_exact_real_parent_and_has_pabc_coverage(self):
        from cdmw.modding.skeleton_parser import parse_pab
        from cdmw.modding.skeleton_variation_parser import parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices
        bones, rows, matrix = independent_root_neutral(self.pab, self.pabc)
        skeleton = parse_pab(self.pab, native.SKELETON)
        parsed = parse_pabc_skeleton_variation(self.pabc, HEAD_PABC, skeleton=skeleton)
        poses = [b.bind_matrix for b in skeleton.bones]
        for row in parsed.records:
            poses[row.bone_index] = _neutral_variation_bind_matrix(poses[row.bone_index], row.matrix_blocks[0])
        self.assertLess(rig.error(matrix, _skin_matrices(skeleton.bones, poses)[122]), 1e-12)
        self.assertEqual((bones[122]["name"], bones[122]["parent"]), ("B_face_com", 93))
        self.assertIn(122, {r["boneIndex"] for r in rows})
        self.assertNotIn(93, {r["boneIndex"] for r in rows})
        donor_hashes = struct.unpack_from("<192I", self.donor, 346)
        by_hash = {b["hash"]: b for b in bones}
        self.assertTrue(all(by_hash[h]["parent"] == 122 for h in donor_hashes))

    def test_04_material_main_draw_preserves_the_old_steve_shader_and_texture_contract(self):
        self.assertEqual(native.sha256(self.source_material), STEVE_MATERIAL_SHA)
        old = ET.fromstring("<Root>"+self.source_material.decode("utf-8-sig")+"</Root>")
        new = ET.fromstring("<Root>"+self.material.decode("utf-8-sig")+"</Root>")
        ov, nv = old.findall("./ModelPropertyList/ModelProperty"), new.findall("./ModelPropertyList/ModelProperty")
        self.assertEqual(len(nv), 6)
        self.assertEqual([x.attrib for x in nv], [x.attrib for x in ov])
        for a, b in zip(ov, nv):
            old_wrapper = next(w for w in a.findall(".//SkinnedMeshMaterialWrapper") if w.get("_subMeshName").lower() == "cd_phm_00_head_0001_01")
            wrappers = b.findall(".//SkinnedMeshMaterialWrapper")
            matches = [w for w in wrappers if w.get("_subMeshName").lower() == MAIN_DRAW.lower()]
            self.assertEqual(len(matches), 1)
            main = matches[0]
            self.assertEqual(xml_shape(main.find("Material")), xml_shape(old_wrapper.find("Material")))
            self.assertEqual(main.get("_jiggleWindWeight"), old_wrapper.get("_jiggleWindWeight"))
            self.assertTrue({w.get("_subMeshName").lower() for w in wrappers} <= {MAIN_DRAW.lower(), EYE_DRAW.lower()})
            textures = {p.get("_name"): p.find("ResourceReferencePath_ITexture").get("_path") for p in main.findall(".//MaterialParameterTexture")}
            self.assertEqual(set(textures.values()), set(assembly.material.TEXTURE_PATHS.values()))

    def test_05_independent_audit_rejects_wrong_palette_metadata_skin_and_geometry(self):
        samples = {"flags": 80, "unknown tail": 90528, "second palette hash": 350,
                   "eye count": 218, "main count": 326, "lod offset": 85,
                   "weight": 90529+28, "skin slot": 90529+20, "position": 90529+1,
                   "UV": 90529+8, "vertex shader lane": 90529+36, "triangle": 90529+1920}
        for label, offset in samples.items():
            data = bytearray(self.pac)
            data[offset] ^= 0x40 if label == "position" else 1
            with self.subTest(label=label), self.assertRaises((ValueError, IndexError, struct.error)):
                independent_pac_audit(bytes(data), self.donor, self.target, self.pab, self.pabc)

    def test_06_pure_admission_rejects_tampered_payload_and_fixed_source(self):
        with tempfile.TemporaryDirectory(prefix="head-root-tamper-", dir=ROOT / "build") as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(self.output, target)
            relatives = [self.pac_row["localFile"], self.material_row["localFile"]]
            relatives.extend(relative for relative, digest in self.report["files"].items() if digest in {NATIVE_HEAD_SHA, HEAD_PABC_SHA})
            for relative in relatives:
                path = target / relative
                raw = path.read_bytes()
                path.write_bytes(raw[:-1] + bytes([raw[-1]^1]))
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    candidate.load_candidate(target / candidate.REPORT_NAME)
                path.write_bytes(raw)
            candidate.load_candidate(target / candidate.REPORT_NAME)

    def test_07_report_extensions_path_escape_and_false_flag_types_are_rejected(self):
        edits = [lambda r: r.update(unreviewedField=True),
                 lambda r: r.update(variant="unreviewed-root-policy"),
                 lambda r: r["integration"].update(installed=True),
                 lambda r: r["integration"].update(installed=0),
                 lambda r: r["candidateResources"].append(copy.deepcopy(r["candidateResources"][0])),
                 lambda r: r["candidateResources"][0].update(localFile="../escape.pac"),
                 lambda r: r["files"].update({"../escape": "0"*64})]
        with tempfile.TemporaryDirectory(prefix="head-root-manifest-", dir=ROOT / "build") as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(self.output, target)
            for edit in edits:
                report = copy.deepcopy(self.report)
                edit(report)
                raw = (json.dumps(report)+"\n").encode()
                (target / candidate.REPORT_NAME).write_bytes(raw)
                # Exercise the semantic contract even if the outer report pin
                # is updated. A hash check alone must not allow new claims.
                with mock.patch.object(candidate, "REPORT_SHA256", native.sha256(raw), create=True):
                    with self.assertRaises(ValueError):
                        candidate.load_candidate(target / candidate.REPORT_NAME)

    def test_08_existing_output_is_protected(self):
        with tempfile.TemporaryDirectory(prefix="head-root-output-", dir=ROOT / "build") as temporary:
            output = Path(temporary)
            sentinel = output / "keep.txt"
            sentinel.write_bytes(b"keep")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/prepare_steve_native_head_root.py"), "--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_bytes(), b"keep")
            self.assertEqual({p.name for p in output.iterdir()}, {"keep.txt"})

    def test_09_fixed_rebuild_is_deterministic_and_sources_are_unchanged(self):
        if not self.rebuild:
            self.skipTest("Use --rebuild for deterministic isolated generation")
        with tempfile.TemporaryDirectory(prefix="head-root-rebuild-", dir=ROOT / "build") as temporary:
            output = Path(temporary) / "fresh"
            result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/prepare_steve_native_head_root.py"), "--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            report, files, _ = candidate.load_candidate(output / candidate.REPORT_NAME)
            self.assertEqual((output / candidate.REPORT_NAME).read_bytes(), self.report_raw)
            self.assertEqual(report, self.report)
            self.assertEqual(files, self.files)
        assembly.orientation.verify_snapshot(self.snapshot)
        native.verify_source(ROOT / "build/cdmw-fixed-source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=candidate.DEFAULT_OUTPUT)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    NativeHeadRootChecks.output, NativeHeadRootChecks.rebuild = args.output, args.rebuild
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeHeadRootChecks))
    if result.wasSuccessful():
        print(json.dumps({"offlineAudit": NativeHeadRootChecks.audit, "nativeRenderingVerified": False}, indent=2))
    raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
