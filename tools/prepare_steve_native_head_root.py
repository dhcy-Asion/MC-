"""Build a fixed native-head three-LOD Steve candidate bound to B_face_com.

This is an offline asset experiment. The common parent is selected from the
actual PAB hierarchy; native animation, shader and appearance remain unverified.
The pure loader reconstructs both payloads from hash-pinned copied inputs.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import analyze_steve_rig as rig
import prepare_native_steve as native
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT/"build/steve-native-head-root"
REPORT_NAME = "steve-native-head-root-report.json"
VARIANT = "steve-native-head-common-root-v1"
PAC_PATH = "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac"
MATERIAL_PATH = "character/modelproperty/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac_xml"
NATIVE_PAC_PATH = "character/model/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac"
PABC_PATH = "character/binary/skeletonvariation/1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"
MATERIAL_TEMPLATE_PATH = "character/modelproperty/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac_xml"
MATERIAL_TEMPLATE_SHA256 = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
NATIVE_PAC_SHA256 = "779cc8247bd72e49c8a86c7cec2535682371d2adff07380e8fe9e9288cab539d"
PAB_SHA256 = "9c8a966142902caa3cf140767db83575cf5d762193b6fe6bbe83f849f79748af"
PABC_SHA256 = "2f761a89f87e38551a4e20b22f9b3d4b589067a2863844dde0879d37a7aec0e5"
SOURCE_PAC_SHA256 = "e75f7a7989137756c4744a16c001bce8f91a6f0b6caabb84214f5d42b710d9b9"
SOURCE_MATERIAL_SHA256 = "01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
DRAW_NAMES = ("CD_PHM_00_Head_0001_Macduff_Eyecover", "CD_PHM_00_Head_0001_Macduff")
LOD_TO_SECTION = {0: 4, 1: 3, 2: 2}
ROOT_BONE = 122
PALETTE_OFFSET = 346
METADATA_END = 90529
SOURCE_SPECS = {
    "nativePac": ("template/"+NATIVE_PAC_PATH, NATIVE_PAC_SHA256),
    "pab": ("template/"+native.SKELETON, PAB_SHA256),
    "headPabc": ("template/"+PABC_PATH, PABC_SHA256),
    "stevePac": ("provenance/"+PAC_PATH, SOURCE_PAC_SHA256),
    "steveMaterial": ("provenance/"+MATERIAL_PATH, SOURCE_MATERIAL_SHA256),
}
DEFAULT_INPUTS = {
    "pab": ROOT/"build/steve-assembly/template"/native.SKELETON,
    "headPabc": ROOT/"build/steve-assembly/template"/PABC_PATH,
    "stevePac": ROOT/"build/steve-assembly/resources"/PAC_PATH,
    "steveMaterial": ROOT/"build/steve-assembly/resources"/MATERIAL_PATH,
}
INTEGRATION = {key: False for key in ("installed", "appearanceApplied", "headAlignmentVerified",
    "animationVerified", "equipmentVerified", "restorationVerified", "nativeBindingVerified", "steveFixed")}
ALLOWED_METADATA_RANGES = ((85, 109), (218, 230), (297, 321), (326, 344), (346, 350))
ALLOWED_HEADER_RANGES = ((36, 40), (44, 48), (52, 56))


def fixed(raw, digest, name):
    if not isinstance(raw, bytes) or native.sha256(raw) != digest:
        raise ValueError("Native head root fixed input differs: "+name)
    return raw


def sections(data):
    if data[:4] != b"PAR " or len(data) < 80:
        raise ValueError("PAC header differs")
    result, offset = {}, 80
    for index in range(8):
        pointer, size = struct.unpack_from("<2I", data, 16+index*8)
        if pointer:
            raise ValueError("Only fixed zero header-offset lanes are supported")
        if size:
            result[index] = {"index": index, "offset": offset, "size": size}
            offset += size
    if offset != len(data):
        raise ValueError("PAC sections do not consume the entire payload")
    return result


def neutral_contract(pab, pabc, donor):
    fixed(pab, PAB_SHA256, "PAB")
    fixed(pabc, PABC_SHA256, "Head PABC")
    bones, _ = rig.parse_pab_records(pab)
    rows, duplicate = rig.parse_pabc_records(pabc, bones)
    hashes = struct.unpack_from("<192I", donor, PALETTE_OFFSET)
    lookup = {b["hash"]: b["index"] for b in bones}
    palette = [lookup[value] for value in hashes]
    if (struct.unpack_from("<H", donor, 344)[0] != 192 or len(set(palette)) != 192
            or palette[0] != 194 or ROOT_BONE in palette or 93 in palette
            or {bones[index]["parent"] for index in palette} != {ROOT_BONE}
            or bones[ROOT_BONE]["name"] != "B_face_com" or bones[ROOT_BONE]["parent"] != 93
            or bones[93]["name"] != "Bip01 Head" or duplicate or len(rows) != 207):
        raise ValueError("Native face palette/common-parent contract differs")
    covered = {row["boneIndex"] for row in rows}
    if not set(palette) <= covered or ROOT_BONE not in covered or 93 in covered:
        raise ValueError("Head PABC coverage differs")
    row = next(row for row in rows if row["boneIndex"] == ROOT_BONE)
    target, _ = rig.neutral_bind(bones[ROOT_BONE]["bind"], row["blocks"][0])
    skin = rig.multiply(bones[ROOT_BONE]["inverse"], target)
    if not .99 < rig.determinant3(skin) < 1.01 or rig.error(rig.multiply(skin, rig.inverse(skin))) > 1e-10:
        raise ValueError("Common-parent neutral skin is not an invertible affine transform")
    chain, cursor = [], ROOT_BONE
    while cursor >= 0:
        chain.append(cursor)
        cursor = bones[cursor]["parent"]
    if chain != [122, 93, 60, 40, 24, 16, 13, 0]:
        raise ValueError("Common-parent ancestry differs")
    return bones, palette, target, skin, chain


def source_geometry(source):
    fixed(source, SOURCE_PAC_SHA256, "Steve head PAC")
    ss = sections(source)
    if set(ss) != {0, 1, 2, 3, 4} or any(ss[i]["size"] != 2064 for i in range(1, 5)):
        raise ValueError("Steve head source section layout differs")
    stream = source[69410:71474]
    if any(source[ss[i]["offset"]:ss[i]["offset"]+2064] != stream for i in range(1, 5)):
        raise ValueError("Steve source LOD records are not identical")
    lo, extent = struct.unpack_from("<3f", source, 176), struct.unpack_from("<3f", source, 188)
    records = [stream[i*40:(i+1)*40] for i in range(48)]
    indices = struct.unpack_from("<72H", stream, 1920)
    if any(index >= 48 for index in indices) or len(set(indices)) != 48:
        raise ValueError("Steve source local topology differs")
    points = [tuple(lo[c]+q*extent[c]/32767 for c, q in enumerate(struct.unpack_from("<3H", record)))
              for record in records]
    if any(struct.unpack_from("<2I", record, 20) != (8, 0) or record[28:34] != b"\xff\0\0\0\0\0"
           or record[39]&63 != 63 for record in records):
        raise ValueError("Steve source is not rigid ordinary Head93 PAC40 skin")
    return records, indices, points


def _quantize(value, low, extent):
    # Exact fixed CDMW _quantize_pac_u16 encoding.
    if abs(extent) < 1e-10:
        return 0
    return min(32767, max(0, round(max(0., min(1., (value-low)/extent))*32767.)))


def _pack_normal(normal, old):
    # Exact fixed CDMW normal XY/sign lanes; preserve tangent Y/handedness.
    enc = lambda v: max(0, min(1023, round((max(-1., min(1., v))+1.)*511.5)))
    sign = 0x40000000 if normal[2] < 0 else 0 if normal[2] > 0 else old&0x40000000
    return (old&0x800003FF)|(enc(normal[0])<<10)|(enc(normal[1])<<20)|sign


def _direction(vector, matrix):
    return orientation.unit(tuple(math.fsum(vector[k]*matrix[k*4+c] for k in range(3)) for c in range(3)))


def _normal(vector, matrix):
    return orientation.unit(tuple(math.fsum(vector[k]*matrix[c*4+k] for k in range(3)) for c in range(3)))


def compensated_records(records, points, skin):
    inverse = rig.inverse(skin)
    bind = [rig.transform(point, inverse) for point in points]
    lo = [min(point[c] for point in bind) for c in range(3)]
    extent = [max(point[c] for point in bind)-lo[c] for c in range(3)]
    encoded = struct.pack("<6f", *lo, *extent)
    lo, extent = struct.unpack_from("<3f", encoded), struct.unpack_from("<3f", encoded, 12)
    result, max_error, min_normal, min_v = [], 0., 1., 1.
    for record, point, target in zip(records, bind, points):
        candidate = bytearray(record)
        struct.pack_into("<3H", candidate, 0, *(_quantize(point[c], lo[c], extent[c]) for c in range(3)))
        n, v, sign = orientation.decode_record_frame(record, 0)
        n_bind, v_bind = _normal(n, skin), _direction(v, inverse)
        struct.pack_into("<I", candidate, 16, _pack_normal(n_bind, struct.unpack_from("<I", record, 16)[0]))
        n_encoded = orientation.decode_record_frame(candidate, 0)[0]
        v_bind = orientation.plane(v_bind, n_encoded)
        lane = max(0, min(32767, round((v_bind[0]+1)*16383.5)))*(-1 if v_bind[2] < 0 else 1)
        word = struct.unpack_from("<I", candidate, 16)[0]&~0x800003FF
        word |= max(0, min(1023, round((v_bind[1]+1)*511.5)))
        if sign > 0:
            word |= 0x80000000
        struct.pack_into("<h", candidate, 6, lane)
        struct.pack_into("<I", candidate, 16, word)
        struct.pack_into("<2I", candidate, 20, 0, 0)
        decoded = tuple(lo[c]+q*extent[c]/32767 for c, q in enumerate(struct.unpack_from("<3H", candidate)))
        max_error = max(max_error, rig.distance(rig.transform(decoded, skin), target))
        nn, vv, actual_sign = orientation.decode_record_frame(candidate, 0)
        min_normal = min(min_normal, orientation.dot(_normal(nn, inverse), orientation.unit(n)))
        min_v = min(min_v, orientation.dot(_direction(vv, skin), orientation.unit(v)))
        if actual_sign != sign or candidate[8:16] != record[8:16] or candidate[28:40] != record[28:40]:
            raise ValueError("Candidate changed UV, handedness or unedited record lanes")
        result.append(bytes(candidate))
    if max_error > .0001 or min(min_normal, min_v) < .995:
        raise ValueError("Quantized neutral geometry/frame replay exceeds tolerance")
    return result, encoded, {"maximumNeutralTargetErrorMetres": max_error,
        "minimumNeutralNormalDot": min_normal, "minimumNeutralPackedVDot": min_v}


def make_material(source):
    fixed(source, SOURCE_MATERIAL_SHA256, "Steve head material")
    root = ET.fromstring("<Root>"+source.decode("utf-8-sig")+"</Root>")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 6:
        raise ValueError("Steve material variant count differs")
    paths = {row.attrib["_path"] for row in root.iter("ResourceReferencePath_ITexture")}
    for variant in variants:
        vectors = [v for v in variant.iter("Vector") if v.get("Name") == "_subMeshResources"]
        if len(vectors) != 1:
            raise ValueError("Material wrapper vector is ambiguous")
        vector = vectors[0]
        wrappers = list(vector)
        if (len(wrappers) != 3 or [w.get("_subMeshName") for w in wrappers] !=
                ["cd_phm_00_head_0001_01", "cd_phm_00_nude_0001_hand", "cd_phm_00_nude_0001"]
                or any(w.find("Material").get("_materialName") != "SkinnedMeshStandard" for w in wrappers)):
            raise ValueError("Fixed Steve material draw/shader contract differs")
        head = wrappers[0]
        for wrapper in wrappers:
            vector.remove(wrapper)
        for name, original in zip(DRAW_NAMES, wrappers[:2]):
            wrapper = copy.deepcopy(head)
            wrapper.set("_subMeshName", name.lower())
            wrapper.set("ItemID", original.attrib["ItemID"])
            vector.append(wrapper)
    if {row.attrib["_path"] for row in root.iter("ResourceReferencePath_ITexture")} != paths:
        raise ValueError("Material texture paths changed")
    candidate = ("\n".join(ET.tostring(child, encoding="unicode") for child in root)+"\n").encode()
    return candidate, {"variants": 6, "wrappersPerVariant": 2, "shader": "SkinnedMeshStandard",
        "drawNames": list(DRAW_NAMES), "texturePaths": sorted(paths), "allTextureReferencesPreserved": True,
        "eyecoverWrapperRetainedWithZeroGeometry": True, "sourceHeadWrapperUsedForBothDraws": True}


def make_candidate(native_pac, old_pac, pab, pabc, old_material):
    """Pure fixed-input builder; no CDMW import, filesystem or game access."""
    fixed(native_pac, NATIVE_PAC_SHA256, "native head PAC")
    ss = sections(native_pac)
    if (ss != {0: {"index": 0, "offset": 80, "size": 90449},
               2: {"index": 2, "offset": 90529, "size": 6736},
               3: {"index": 3, "offset": 97265, "size": 16228},
               4: {"index": 4, "offset": 113493, "size": 145920}}
            or struct.unpack_from("<I", native_pac, 80)[0] != 2 or native_pac[84] != 3):
        raise ValueError("Native PAC section/flags/LOD contract differs")
    bones, palette, target, skin, chain = neutral_contract(pab, pabc, native_pac)
    records, indices, points = source_geometry(old_pac)
    records, bbox, replay = compensated_records(records, points, skin)
    geometry = b"".join(records)+struct.pack("<72H", *indices)
    result = bytearray(native_pac[:METADATA_END])
    result[297:321] = bbox
    result[218:230] = bytes(12)
    struct.pack_into("<3H3I", result, 326, 48, 48, 48, 72, 72, 72)
    struct.pack_into("<I", result, PALETTE_OFFSET, bones[ROOT_BONE]["hash"])
    for sid in (2, 3, 4):
        struct.pack_into("<I", result, 20+sid*8, len(geometry))
        lod, offset = 4-sid, METADATA_END+(sid-2)*len(geometry)
        struct.pack_into("<I", result, 85+lod*4, offset)
        struct.pack_into("<I", result, 97+lod*4, offset+48*40)
    allowed = {i for start, end in (*ALLOWED_HEADER_RANGES, *ALLOWED_METADATA_RANGES) for i in range(start, end)}
    changes = [i for i, (a, b) in enumerate(zip(native_pac, result)) if a != b]
    if any(i not in allowed for i in changes) or result[350:METADATA_END] != native_pac[350:METADATA_END]:
        raise ValueError("Unknown native metadata or retained palette bytes changed")
    pac = bytes(result)+geometry*3
    if set(sections(pac)) != {0, 2, 3, 4} or len(pac) != 96721:
        raise ValueError("Candidate PAC section sizes differ")
    material, material_audit = make_material(old_material)
    return pac, material, {"palette": {"count": 192, "hashOffset": PALETTE_OFFSET, "changedSlot": 0,
        "beforePabIndex": palette[0], "beforeName": bones[palette[0]]["name"],
        "beforeHash": bones[palette[0]]["hash"], "afterPabIndex": ROOT_BONE,
        "afterName": bones[ROOT_BONE]["name"], "afterHash": bones[ROOT_BONE]["hash"],
        "other191EntriesByteIdentical": True, "headPabcCovered": True, "ancestorChain": chain},
        "neutral": {**replay, "pabBindMatrix": list(bones[ROOT_BONE]["bind"]),
            "pabInverseBindMatrix": list(bones[ROOT_BONE]["inverse"]), "headPabcNeutralMatrix": list(target),
            "skinMatrix": list(skin), "equation": "p_bind = p_target * inverse(PAB_inverseBind[122] * HeadPABC_neutral[122])",
            "target": "Quantized original Steve head positions in model space; no guessed translation or scale",
            "baseCharacterScaleCompensated": False},
        "lods": [{"lod": lod, "sectionIndex": sid, "vertices": 48, "triangles": 24,
                  "sectionBytes": 2064, "rigidPaletteSlot": 0, "eyecoverVertices": 0, "eyecoverIndices": 0}
                 for lod, sid in LOD_TO_SECTION.items()],
        "uvAndTopologyPreserved": True, "ordinaryRigidByteWeight": 255, "nativeFlags": 2,
        "unknownMetadataByteIdentical": True, "allowedHeaderRanges": [list(r) for r in ALLOWED_HEADER_RANGES],
        "allowedMetadataRanges": [list(r) for r in ALLOWED_METADATA_RANGES], "changedHeaderAndMetadataOffsets": changes,
        "material": material_audit, "crossCheck": {"cdmwCommit": native.CDMW_COMMIT,
            "pythonSourceTreeSha256": native.CDMW_SOURCE_SHA256, "nativeNoEditRebuildByteIdentical": True,
            "independentThreeLodParseAndNeutralReplay": True}}


def make_report(sources):
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Head root source collection differs")
    for key, (_, digest) in SOURCE_SPECS.items():
        fixed(sources[key], digest, key)
    pac, material, audit = make_candidate(sources["nativePac"], sources["stevePac"], sources["pab"],
                                         sources["headPabc"], sources["steveMaterial"])
    rows = [{"kind": "skinnedMesh", "virtualPath": PAC_PATH, "localFile": "resources/"+PAC_PATH,
             "sha256": native.sha256(pac), "templatePath": NATIVE_PAC_PATH, "templateSha256": NATIVE_PAC_SHA256,
             "templateArchiveFlags": 1, "archiveFlags": 1},
            {"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH, "localFile": "resources/"+MATERIAL_PATH,
             "sha256": native.sha256(material), "templatePath": MATERIAL_TEMPLATE_PATH,
             "templateSha256": MATERIAL_TEMPLATE_SHA256, "templateArchiveFlags": 50, "archiveFlags": 50}]
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": INDEX_SHA256, "candidateResources": rows,
        "sources": {key: {"localFile": rel, "sha256": digest} for key, (rel, digest) in SOURCE_SPECS.items()},
        "files": {**{rel: digest for rel, digest in SOURCE_SPECS.values()},
                  **{row["localFile"]: row["sha256"] for row in rows}},
        "audit": audit, "integration": dict(INTEGRATION), "limitations": [
            "Static native-head-format candidate, not an in-game visual, animation or equipment validation.",
            "Exactly one palette hash replaces a removed face-child slot with its proven common parent B_face_com122; neither palette preservation nor direct Head93 binding is claimed.",
            "All three native geometry sections are replaced by Steve's rigid 48-vertex/24-triangle head; native eyecover geometry is empty with strict material wrapper coverage.",
            "Unknown native metadata is retained without assigning morph, physics, shader or model-hash semantics. Keeping it does not prove native topology-dependent compatibility.",
            "Neutral compensation follows fixed CDMW's single HeadPABC convention; native variation merging, facial animation, character scale and shader skinning remain unverified.",
            "Only the existing private head PAC and its material sidecar are candidate resources. Body, prefab, HeadPrefabData, PAPPT, hair, armor, saves and game files are outside this generator."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit=2*1024*1024):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Native head root file is absent or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Native head root file changed beyond its size limit")
    return raw


def read_native_pac(game):
    """Read one hash-pinned original 0009 entry; never consult a process."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game/"bin64/CrimsonDesert.exe", game/"0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    entry = native.select_unique_entries(parse_archive_pamt(index), (NATIVE_PAC_PATH,))[NATIVE_PAC_PATH]
    if entry.flags != 1:
        raise ValueError("Native head PAC archive flags differ")
    paz = Path(entry.paz_file)
    native.check_links(paz)
    if not paz.resolve().is_relative_to((game/"0009").resolve()):
        raise ValueError("Native head entry escapes the original archive")
    raw = fixed(_decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0],
                NATIVE_PAC_SHA256, "original native head PAC")
    gate()
    return raw


def load_candidate(report_path):
    """Pure admission -> (report, {virtualPath: bytes}, snapshot), no CDMW."""
    path = native.output_directory(report_path)
    raw_report = bounded_read(path)
    report = strict_json(raw_report)
    snapshot, sources = {path: raw_report}, {}
    for key, (relative, digest) in SOURCE_SPECS.items():
        source = native.output_directory(path.parent/relative)
        sources[key] = fixed(bounded_read(source), digest, key)
        snapshot[source] = sources[key]
    expected = make_report(sources)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("Native head root report does not match the exact fixed-source reconstruction")
    pac, material, _ = make_candidate(sources["nativePac"], sources["stevePac"], sources["pab"],
                                      sources["headPabc"], sources["steveMaterial"])
    payloads = {PAC_PATH: pac, MATERIAL_PATH: material}
    for virtual, expected_payload in payloads.items():
        file = native.output_directory(path.parent/"resources"/virtual)
        actual = bounded_read(file)
        if actual != expected_payload:
            raise ValueError("Native head root payload differs from fixed-source reconstruction")
        snapshot[file] = actual
    orientation.verify_snapshot(snapshot)
    return report, payloads, snapshot


def verify_cdmw(sources, pac):
    from cdmw.modding.mesh_parser import (parse_pac, _parse_par_sections, _find_pac_descriptors,
        _parse_pac_geometry_section, resolve_pac_bone_palette)
    from cdmw.modding.mesh_pac_builder import build_pac, _quantize_pac_u16, _pack_pac_normal
    from prepare_steve_assembly import head_matrices
    donor = sources["nativePac"]
    if build_pac(parse_pac(donor, NATIVE_PAC_PATH), donor) != donor:
        raise ValueError("Fixed CDMW native no-edit round trip differs")
    skeleton, _, matrices, covered = head_matrices(sources["pab"], sources["headPabc"])
    bones, _, _, skin, _ = neutral_contract(sources["pab"], sources["headPabc"], donor)
    if ROOT_BONE not in covered or rig.error(skin, matrices[ROOT_BONE]) > 1e-12:
        raise ValueError("Independent common-parent neutral matrix differs from CDMW")
    before = resolve_pac_bone_palette(donor, skeleton)
    after = resolve_pac_bone_palette(pac, skeleton)
    if after != (ROOT_BONE, *before[1:]):
        raise ValueError("Fixed CDMW resolved palette differs")
    source = parse_pac(sources["stevePac"], PAC_PATH).submeshes
    if len(source) != 1 or len(source[0].vertices) != 48 or len(source[0].faces) != 24:
        raise ValueError("CDMW source geometry differs")
    original = source[0]
    ss = {s["index"]: s for s in _parse_par_sections(pac)}
    descriptors = _find_pac_descriptors(pac, 80, 90449, 3)
    if len(descriptors) != 1 or descriptors[0].name != DRAW_NAMES[1]:
        raise ValueError("Candidate retained another active draw")
    for lod, sid in LOD_TO_SECTION.items():
        parsed = _parse_pac_geometry_section(pac, PAC_PATH, descriptors, ss[sid], lod)
        if len(parsed.submeshes) != 1 or parsed.total_vertices != 48 or parsed.total_faces != 24:
            raise ValueError("CDMW candidate three-LOD geometry differs")
        part = parsed.submeshes[0]
        if part.faces != original.faces or part.uvs != original.uvs:
            raise ValueError("CDMW candidate UV/topology differs")
        if any(slots != (0,) or weights != (1.,) for slots, weights in zip(part.bone_indices, part.bone_weights)):
            raise ValueError("CDMW candidate skin is not rigid common-parent slot0")
        if max(rig.distance(rig.transform(a, skin), b) for a, b in zip(part.vertices, original.vertices)) > .0001:
            raise ValueError("CDMW quantized neutral replay differs")
    records, _, points = source_geometry(sources["stevePac"])
    inverse = rig.inverse(skin)
    lo, extent = struct.unpack_from("<3f", pac, 297), struct.unpack_from("<3f", pac, 309)
    for record, point in zip(records, points):
        point = rig.transform(point, inverse)
        if any(_quantize(point[c], lo[c], extent[c]) != _quantize_pac_u16(point[c], lo[c], extent[c]) for c in range(3)):
            raise ValueError("Pure quantizer differs from fixed CDMW")
        n = _normal(orientation.decode_record_frame(record, 0)[0], skin)
        word = struct.unpack_from("<I", record, 16)[0]
        if _pack_normal(n, word) != _pack_pac_normal(n, word):
            raise ValueError("Pure normal encoder differs from fixed CDMW")


def prepare(output=DEFAULT_OUTPUT, source=ROOT/"build/cdmw-fixed-source", deps=ROOT/"build/cdmw-deps", game=None):
    protected = [source, deps, *(path.parent for path in DEFAULT_INPUTS.values())]
    output = orientation.preflight(output, protected)
    if game is None:
        installation = ROOT/"runtime/installation.json"
        config = bounded_read(installation).decode("utf-8-sig").encode("utf-8")
        game = Path(strict_json(config)["gameRoot"])
    else:
        game = Path(game)
    native.check_links(game)
    protected.append(game)
    output = orientation.preflight(output, protected)
    snapshot, sources = {}, {}
    for key, path in DEFAULT_INPUTS.items():
        path = native.output_directory(path)
        sources[key] = fixed(bounded_read(path), SOURCE_SPECS[key][1], key)
        snapshot[path] = sources[key]
    native.load_cdmw(source, deps)
    sources["nativePac"] = read_native_pac(game)
    pac, material, _ = make_candidate(sources["nativePac"], sources["stevePac"], sources["pab"],
                                      sources["headPabc"], sources["steveMaterial"])
    verify_cdmw(sources, pac)
    report = make_report(sources)
    native.verify_source(source)
    orientation.verify_snapshot(snapshot)
    if read_native_pac(game) != sources["nativePac"]:
        raise ValueError("Original native head PAC changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    writes = {relative: sources[key] for key, (relative, _) in SOURCE_SPECS.items()}
    writes.update({"resources/"+PAC_PATH: pac, "resources/"+MATERIAL_PATH: material, REPORT_NAME: report_bytes(report)})
    for relative, data in writes.items():
        file = output/relative
        native.check_links(file)
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("xb") as stream:
            stream.write(data)
    load_candidate(output/REPORT_NAME)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT/"build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT/"build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.cdmw_source, args.deps, args.game_root)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
                      "neutral": report["audit"]["neutral"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
