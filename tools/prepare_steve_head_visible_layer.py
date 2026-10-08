"""Offline control removing only the pinned MC Steve alpha-zero hat triangles.

All 48 vertex records remain original bytes. This is not a generic outer-layer
hiding rule and does not establish the native skin shader's alpha behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import prepare_steve_head_uv_control as uv

native, orientation, strict_json = uv.native, uv.orientation, uv.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-head-visible-layer-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-head-visible-layer"
DEFAULT_HEAD_UV_REPORT = uv.DEFAULT_OUTPUT / uv.REPORT_NAME
VARIANT = "steve-head-fixed-transparent-hat-triangles-removed-v1"
PAC_PATH, MATERIAL_PATH, DIFFUSE_PATH = uv.PAC_PATH, uv.MATERIAL_PATH, uv.DIFFUSE_PATH
OLD_PAC_SHA256 = "c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55"
NEW_PAC_SHA256 = "7c222d1cb2d475d7e487c8cad87967afc63d27a1fa14b99d35c62a24f762d9ca"
CANDIDATE_SHA256 = NEW_PAC_SHA256
PRESERVED_MATERIAL_SHA256 = uv.PRESERVED_MATERIAL_SHA256
DIFFUSE_SHA256 = uv.DIFFUSE_SHA256
HEAD_UV_REPORT_SHA256 = "56790fa5efb6a2b38ed5938f217d4ddc25b11d5b87c18a6640721fd15ae3a3af"
PAC_SIZE, CANDIDATE_SIZE = 96721, 96505
MATERIAL_SIZE, DIFFUSE_SIZE, PRIOR_REPORT_SIZE = 16134, 87536, 55260
ARCHIVE_FLAGS = 1
ACTIVE_DRAW_NAME = "CD_PHM_00_Head_0001_Macduff"
METADATA_END, VERTEX_BYTES, OLD_SECTION_BYTES, NEW_SECTION_BYTES = 90529, 1920, 2064, 1992
SOURCE_SPECS = {
    "headPac": ("template/" + PAC_PATH, OLD_PAC_SHA256),
    "preservedMaterial": ("provenance/preserved/" + MATERIAL_PATH, PRESERVED_MATERIAL_SHA256),
    "diffuseTexture": ("provenance/dependencies/" + DIFFUSE_PATH, DIFFUSE_SHA256),
    "headUvReport": ("provenance/" + uv.REPORT_NAME, HEAD_UV_REPORT_SHA256),
}
SOURCE_LIMITS = {"headPac": PAC_SIZE, "preservedMaterial": MATERIAL_SIZE,
                 "diffuseTexture": DIFFUSE_SIZE, "headUvReport": PRIOR_REPORT_SIZE}
LOD_LAYOUT = ((2, 2, 90529, 90529), (1, 3, 92593, 92521), (0, 4, 94657, 94513))
FIELD_EDITS = tuple(
    [(332 + 4 * i, 72, 36, "mainIndexCountLOD" + str(i)) for i in range(3)]
    + [(20 + 8 * sid, OLD_SECTION_BYTES, NEW_SECTION_BYTES, "PARSectionSize" + str(sid))
       for _, sid, _, _ in LOD_LAYOUT]
    + [(85 + 4 * lod, old, new, "vertexOffsetLOD" + str(lod))
       for lod, _, old, new in LOD_LAYOUT]
    + [(97 + 4 * lod, old + VERTEX_BYTES, new + VERTEX_BYTES, "indexOffsetLOD" + str(lod))
       for lod, _, old, new in LOD_LAYOUT]
)
MC_SOURCE_PINS = {
    "steve.gltf": "bc9cd38b3ebcab9702def27a425208bbfb2f6a1093012976d95f0c4d165e81b8",
    "steve.bin": "d03b7e6354652c7872b14b89d9d56861a23d2e910b52349f0e1da4c3101942a0",
    "steve.png": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0",
}
FACE_RECTS = ((32, 0, 64, 32), (64, 0, 96, 32), (0, 32, 32, 64),
              (32, 32, 64, 64), (64, 32, 96, 64), (96, 32, 128, 64),
              (160, 0, 192, 32), (192, 0, 224, 32), (128, 32, 160, 64),
              (160, 32, 192, 64), (192, 32, 224, 64), (224, 32, 256, 64))
PROTECTED_DIRS = (*uv.PROTECTED_DIRS, uv.DEFAULT_OUTPUT,
                  ROOT / "build/steve-head-uv-probe-overlay",
                  ROOT / "build/steve-head-render-audit-20261008")
INTEGRATION = {key: False for key in (
    "installed", "packageComposed", "appearanceApplied", "headAlignmentVerified",
    "animationVerified", "equipmentVerified", "restorationVerified",
    "nativeFormatAcceptanceVerified", "nativeAlphaBehaviorVerified",
    "nativeShaderUvConventionVerified", "nativePrimaryUvSelectionVerified",
    "rendererSelectionVerified", "mcDiffuseNativeRenderingVerified",
    "mcHeadSkinVerified", "steveFixed")}
bounded_read, package_path, report_bytes = uv.bounded_read, uv.package_path, uv.report_bytes


def fixed(raw, digest, label):
    if not isinstance(raw, bytes) or native.sha256(raw) != digest:
        raise ValueError("Visible-layer fixed input differs: " + label)
    return raw


def structure(raw, candidate=False):
    """Exact table/count/record/index parse; no gap or heuristic layout accepted."""
    wanted_size = CANDIDATE_SIZE if candidate else PAC_SIZE
    width = NEW_SECTION_BYTES if candidate else OLD_SECTION_BYTES
    index_count = 36 if candidate else 72
    if len(raw) != wanted_size or raw[:4] != b"PAR ":
        raise ValueError("Visible-layer PAR length/magic differs")
    entries = list(struct.iter_unpack("<II", raw[16:80]))
    if (len(entries) != 8 or any(pointer for pointer, _ in entries)
            or [size for _, size in entries] != [90449, 0, width, width, width, 0, 0, 0]
            or struct.unpack_from("<I", raw, 80)[0] != 2 or raw[84] != 3
            or raw[218:230] != bytes(12)
            or struct.unpack_from("<3H3I", raw, 326) != (48, 48, 48, *([index_count] * 3))
            or struct.unpack_from("<H", raw, 344)[0] != 192):
        raise ValueError("Visible-layer fixed section/draw/palette contract differs")
    lods = []
    for lod, sid, old, new in LOD_LAYOUT:
        start = new if candidate else old
        if (struct.unpack_from("<I", raw, 85 + 4 * lod)[0] != start
                or struct.unpack_from("<I", raw, 97 + 4 * lod)[0] != start + VERTEX_BYTES):
            raise ValueError("Visible-layer mirrored geometry boundary differs")
        records = raw[start:start + VERTEX_BYTES]
        indices = list(struct.unpack_from("<" + "H" * index_count, raw, start + VERTEX_BYTES))
        faces = [indices[i:i + 3] for i in range(0, index_count, 3)]
        if (len(records) != VERTEX_BYTES or any(len(set(f)) != 3 or min(f) < 0 or max(f) >= 48 for f in faces)
                or set(indices[:36]) != set(range(24))
                or (not candidate and set(indices[36:]) != set(range(24, 48)))):
            raise ValueError("Visible-layer fixed base/hat index ownership differs")
        for vertex in range(48):
            record = records[40 * vertex:40 * (vertex + 1)]
            if (record[12:16] != bytes.fromhex("0000003c") or record[20:28] != bytes(8)
                    or record[28:36] != b"\xff" + bytes(7) or record[39] & 63 != 63):
                raise ValueError("Visible-layer original guide/rigid byte skin differs")
        lods.append({"lod": lod, "section": sid, "vertexOffset": start,
            "indexOffset": start + VERTEX_BYTES, "sectionBytes": width,
            "vertices": 48, "indices": index_count, "baseTriangles": 12,
            "hatTriangles": 0 if candidate else 12, "unreferencedHatVertices": 24 if candidate else 0,
            "vertexRecordSha256": native.sha256(records)})
    if METADATA_END + 3 * width != len(raw):
        raise ValueError("Visible-layer PAR trailing bytes or section gap")
    return {"eyeCoverGeometryEmpty": True, "activeMainDraws": 1, "activeDrawName": ACTIVE_DRAW_NAME,
        "metadataEndOffset": METADATA_END, "vertexStride": 40, "paletteEntries": 192,
        "lods": lods, "allSectionsCompletelyAccountedFor": True}


def transform_pac(source):
    fixed(source, OLD_PAC_SHA256, "UV-control PAC")
    structure(source)
    result = bytearray(source[:METADATA_END])
    for offset, old, new, _ in FIELD_EDITS:
        if struct.unpack_from("<I", result, offset)[0] != old:
            raise ValueError("Visible-layer source metadata field differs")
        struct.pack_into("<I", result, offset, new)
    for _, _, old, _ in LOD_LAYOUT:
        result.extend(source[old:old + NEW_SECTION_BYTES])
    payload = fixed(bytes(result), NEW_PAC_SHA256, "base-only PAC")
    structure(payload, True)
    return payload


def restore_pac(payload, source):
    """Inverse uses only the pinned source's removed index tails, never a guess."""
    fixed(payload, NEW_PAC_SHA256, "base-only PAC inverse")
    fixed(source, OLD_PAC_SHA256, "inverse index-tail source")
    structure(payload, True)
    result = bytearray(payload[:METADATA_END])
    for offset, old, new, _ in FIELD_EDITS:
        if struct.unpack_from("<I", result, offset)[0] != new:
            raise ValueError("Visible-layer inverse metadata field differs")
        struct.pack_into("<I", result, offset, old)
    for _, _, old, new in LOD_LAYOUT:
        result.extend(payload[new:new + NEW_SECTION_BYTES])
        result.extend(source[old + NEW_SECTION_BYTES:old + OLD_SECTION_BYTES])
    return fixed(bytes(result), OLD_PAC_SHA256, "exact inverse PAC")


def difference(source, payload):
    metadata_changes = [i for i in range(METADATA_END) if source[i] != payload[i]]
    allowed = {i for at, old, new, _ in FIELD_EDITS if old != new for i in range(at, at + 4)}
    if not set(metadata_changes) <= allowed or restore_pac(payload, source) != source:
        raise ValueError("Visible-layer unreviewed metadata edit or inverse failure")
    keep_old, keep_new = bytearray(), bytearray()
    for i in range(METADATA_END):
        if i not in allowed:
            keep_old.append(source[i]); keep_new.append(payload[i])
    removed = []
    for lod, sid, old, new in LOD_LAYOUT:
        before, after = source[old:old + NEW_SECTION_BYTES], payload[new:new + NEW_SECTION_BYTES]
        if before != after:
            raise ValueError("Visible-layer changed vertex or retained base-index bytes")
        keep_old.extend(before); keep_new.extend(after)
        tail = source[old + NEW_SECTION_BYTES:old + OLD_SECTION_BYTES]
        removed.append({"lod": lod, "section": sid, "sourceByteSpan": [old + NEW_SECTION_BYTES, old + OLD_SECTION_BYTES],
            "bytes": 72, "sha256": native.sha256(tail), "indices": list(struct.unpack("<36H", tail))})
    if keep_old != keep_new:
        raise ValueError("Visible-layer preserved byte sequence differs")
    return {"operation": "delete only fixed MC alpha-zero hat indices",
        "removedIndexBytes": 216, "removedHatTriangles": 36, "retainedBaseTriangles": 36,
        "metadataFields": [{"byteSpan": [at, at + 4], "sourceValue": old, "candidateValue": new, "name": name}
                           for at, old, new, name in FIELD_EDITS],
        "actualChangedMetadataByteOffsets": metadata_changes, "removedIndexTails": removed,
        "preservedByteSequenceSize": len(keep_old), "preservedByteSequenceSha256": native.sha256(bytes(keep_old)),
        "all48RecordsPerLodAndBaseIndicesByteIdentical": True,
        "allOtherHeaderMetadataPaletteBoundsUvSkinNormalTangentGuideBytesPreserved": True,
        "exactInverseToSourceBytes": True}


def texture_evidence(source, diffuse):
    uv.headbase.dds_audit(diffuse)
    quads = []
    bmin, extent = struct.unpack_from("<3f", source, 297), struct.unpack_from("<3f", source, 309)
    for q, wanted in enumerate(FACE_RECTS):
        coords = [struct.unpack_from("<2e", source, METADATA_END + i * 40 + 8)
                  for i in range(4 * q, 4 * q + 4)]
        rect = [int(256 * min(u for u, v in coords)), int(256 * min(v for u, v in coords)),
                int(256 * max(u for u, v in coords)), int(256 * max(v for u, v in coords))]
        if rect != list(wanted):
            raise ValueError("Visible-layer fixed MC face UV mapping differs")
        evidence = uv.footprint(diffuse, wanted)
        if evidence["alphaCounts"] != {"255" if q < 6 else "0": 1024}:
            raise ValueError("Visible-layer fixed MC base/hat alpha evidence differs")
        points = [tuple(bmin[axis] + component / 65535 * extent[axis]
                        for axis, component in enumerate(struct.unpack_from("<3H", source, METADATA_END + i * 40)))
                  for i in range(4 * q, 4 * q + 4)]
        quads.append({"quad": q, "mcMesh": "head" if q < 6 else "hat",
            "pacVertexIndices": list(range(q * 4, q * 4 + 4)), "primaryUv": [list(row) for row in coords],
            "decodedPacPositionBounds": {"min": [min(p[axis] for p in points) for axis in range(3)],
                "max": [max(p[axis] for p in points) for axis in range(3)]},
            "ddsEvidence": evidence})
    return {"classification": "fixed encoded DDS mip-zero footprint; not native shader sampling",
        "baseTexels": 6144, "baseAlphaCounts": {"255": 6144},
        "hatTexels": 6144, "hatAlphaCounts": {"0": 6144}, "quads": quads,
        "minecraftMapping": {"version": "1.21.1", "style": "classic-wide", "sourcePins": dict(MC_SOURCE_PINS),
            "headMeshIndex": 0, "hatMeshIndex": 6, "headUvAccessor": 3, "hatUvAccessor": 39,
            "headIndexAccessor": 6, "hatIndexAccessor": 42,
            "sourceVertexOrderPerQuad": [0, 3, 2, 1],
            "sourceIndexPatternPerQuad": [0, 1, 2, 0, 2, 3],
            "pacIndexPatternPerQuad": [0, 1, 2, 0, 2, 3],
            "directGltfTriangleIndexRemapClaimed": False,
            "pacBaseVertices": [0, 24], "pacHatVertices": [24, 48]},
        "nativeUvSelectionAlphaFilteringMipAndColorSpaceVerified": False,
        "ddsEncodingIsLossless": False}


def make_report(sources):
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_SPECS):
        raise ValueError("Visible-layer source collection differs")
    for key, (_, digest) in SOURCE_SPECS.items():
        fixed(sources[key], digest, key)
        if len(sources[key]) != SOURCE_LIMITS[key]:
            raise ValueError("Visible-layer fixed source size differs")
    prior = strict_json(sources["headUvReport"])
    if (prior["variant"] != uv.VARIANT or prior["candidateResources"][0]["sha256"] != OLD_PAC_SHA256
            or prior["preservedDependencies"]["material"]["sha256"] != PRESERVED_MATERIAL_SHA256
            or prior["preservedDependencies"]["diffuse"]["sha256"] != DIFFUSE_SHA256):
        raise ValueError("Visible-layer fixed prior report binding differs")
    payload = transform_pac(sources["headPac"])
    row = {"kind": "skinnedMesh", "virtualPath": PAC_PATH, "localFile": "resources/" + PAC_PATH,
        "sha256": NEW_PAC_SHA256, "payloadSize": CANDIDATE_SIZE, "sourceVirtualPath": PAC_PATH,
        "templatePath": PAC_PATH, "templateSha256": OLD_PAC_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": uv.headbase.INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": rel, "sha256": digest, "payloadSize": len(sources[key])}
                    for key, (rel, digest) in SOURCE_SPECS.items()},
        "files": {**{rel: digest for rel, digest in SOURCE_SPECS.values()}, row["localFile"]: NEW_PAC_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": PAC_PATH, "previousPacSha256": OLD_PAC_SHA256,
            "replacementPacSha256": NEW_PAC_SHA256, "preservedMaterialSha256": PRESERVED_MATERIAL_SHA256,
            "preservedDiffuseSha256": DIFFUSE_SHA256, "allOtherResourcesMustBeByteIdentical": True,
            "wholePackageVerifiedByThisTool": False},
        "preservedDependencies": {"material": {"virtualPath": MATERIAL_PATH, "sha256": PRESERVED_MATERIAL_SHA256,
                "payloadSize": MATERIAL_SIZE, "expectedArchiveFlags": 50, "addedAsCandidateResource": False},
            "diffuse": {"virtualPath": DIFFUSE_PATH, "sha256": DIFFUSE_SHA256, "payloadSize": DIFFUSE_SIZE,
                "expectedArchiveFlags": 0, "addedAsCandidateResource": False,
                "dds": uv.headbase.dds_audit(sources["diffuseTexture"])},
            "packageRegistrationVerifiedByThisTool": False},
        "audit": {"sourceBytes": PAC_SIZE, "candidateBytes": CANDIDATE_SIZE, "byteLengthDelta": -216,
            "sourceStructure": structure(sources["headPac"]), "candidateStructure": structure(payload, True),
            "difference": difference(sources["headPac"], payload),
            "textureEvidence": texture_evidence(sources["headPac"], sources["diffuseTexture"]),
            "entireMaterialShaderItemsParametersPermutationsAndOtherTextureBranchesPreserved": True,
            "materialBomHex": sources["preservedMaterial"][:3].hex(),
            "materialCrlfCount": sources["preservedMaterial"].count(b"\r\n")},
        "integration": dict(INTEGRATION), "limitations": [
            "Offline one-private-head-PAC diagnostic. Deletes only the fixed classic Steve hat's alpha-zero faces; it is not a generic invisible outer-layer policy.",
            "Each LOD retains every original 48-by-40-byte record and first 36 base indices. The final 36 hat indices are removed; only reviewed counts, section sizes and affected absolute mirrors change. Original bounds remain conservative.",
            "PAMI cc86 and MC DDS 653 remain exact dependency bytes. Native shader, variant, wrinkles/damage/aging branches, UV selection, alpha/depth, filtering and mip choice are unverified.",
            "Alpha evidence is decoded BC3 mip-zero atlas data. It does not prove the native skin shader discards the transparent hat; removal is a discriminating experiment, not a diagnosed cause or display repair.",
            "Fixed official head/hat glTF UV/index mapping and fixed CDMW three-LOD parsing are checked at generation and independently by the checker; pure admission reconstructs the full manifest from four copied pinned sources without CDMW or game reads.",
            "No package composition, installation, native call, process, game archive/metadata, service, save or inventory operation. The other thirteen full-plan resources and any runtime behavior require separate admission and acceptance."]}


def load_candidate(report_path):
    """Four-source complete reconstruction -> report, one PAC, absolute Path snapshot."""
    path = native.output_directory(report_path)
    raw = bounded_read(path)
    report, snapshot, sources = strict_json(raw), {path: raw}, {}
    for key, (relative, digest) in SOURCE_SPECS.items():
        p = package_path(path.parent, relative)
        sources[key] = fixed(bounded_read(p, SOURCE_LIMITS[key]), digest, key)
        snapshot[p] = sources[key]
    expected = make_report(sources)
    if report != expected or raw != report_bytes(expected):
        raise ValueError("Visible-layer report differs from complete fixed reconstruction")
    p = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(p, CANDIDATE_SIZE)
    if payload != transform_pac(sources["headPac"]):
        raise ValueError("Visible-layer payload differs from the fixed hat-index deletion")
    snapshot[p] = payload
    orientation.verify_snapshot(snapshot)
    return report, {PAC_PATH: payload}, snapshot


def read_inputs(head_report):
    _, payloads, snapshot = uv.load_candidate(head_report)
    def copied(name):
        return snapshot[uv.package_path(head_report.parent, uv.SOURCE_SPECS[name][0])]
    return {"headPac": payloads[PAC_PATH], "preservedMaterial": copied("preservedMaterial"),
            "diffuseTexture": copied("diffuseTexture"), "headUvReport": snapshot[head_report]}, snapshot


def verify_official_mapping(source):
    """Fixed MC accessor mapping checked only from existing local offline outputs."""
    from prepare_native_steve import read_accessor
    snapshot = {}
    for name, digest in MC_SOURCE_PINS.items():
        p = native.output_directory(ROOT / "build/steve-1.21.1" / name)
        snapshot[p] = fixed(bounded_read(p, 262144), digest, name)
    document = strict_json(snapshot[ROOT / "build/steve-1.21.1/steve.gltf"])
    binary = snapshot[ROOT / "build/steve-1.21.1/steve.bin"]
    for name, mesh_index, first in (("head", 0, 0), ("hat", 6, 24)):
        mesh = document["meshes"][mesh_index]
        if mesh["name"] != name or len(mesh["primitives"]) != 1:
            raise ValueError("Visible-layer official head/hat mesh differs")
        primitive = mesh["primitives"][0]
        coords = read_accessor(document, binary, primitive["attributes"]["TEXCOORD_0"], "VEC2", 5126)
        indices = [r[0] for r in read_accessor(document, binary, primitive["indices"], "SCALAR", 5123)]
        order = [4 * q + i for q in range(6) for i in (0, 3, 2, 1)]
        canonical_indices = [q * 4 + k for q in range(6) for k in (0, 1, 2, 0, 2, 3)]
        if indices != canonical_indices:
            raise ValueError("Visible-layer official MC quad triangles differ")
        expected_indices = [i + first for i in canonical_indices]
        for _, _, start, _ in LOD_LAYOUT:
            actual = [struct.unpack_from("<2e", source, start + 40 * i + 8) for i in range(first, first + 24)]
            stored = list(struct.unpack_from("<36H", source, start + VERTEX_BYTES + (72 if first else 0)))
            if actual != [tuple(coords[i]) for i in order] or stored != expected_indices:
                raise ValueError("Visible-layer PAC is not the fixed real MC head/hat UV/index mapping")
    orientation.verify_snapshot(snapshot)
    return snapshot


def verify_cdmw(source, payload, cdmw_source, deps):
    native.load_cdmw(cdmw_source, deps)
    from cdmw.modding.mesh_parser import _parse_par_sections, _find_pac_descriptors, _parse_pac_geometry_section
    def parsed(raw):
        sections = {s["index"]: s for s in _parse_par_sections(raw)}
        desc = _find_pac_descriptors(raw, 80, 90449, 3)
        if len(desc) != 1 or desc[0].name != ACTIVE_DRAW_NAME:
            raise ValueError("Visible-layer CDMW active draw identity differs")
        return [_parse_pac_geometry_section(raw, PAC_PATH, desc, sections[sid], lod)
                for lod, sid, _, _ in LOD_LAYOUT]
    for old, new in zip(parsed(source), parsed(payload)):
        if len(old.submeshes) != 1 or len(new.submeshes) != 1:
            raise ValueError("Visible-layer CDMW active draw count differs")
        a, b = old.submeshes[0], new.submeshes[0]
        if (len(a.vertices) != 48 or len(a.faces) != 24 or len(b.vertices) != 48 or len(b.faces) != 12
                or b.faces != a.faces[:12] or b.source_index_count != 36):
            raise ValueError("Visible-layer CDMW base-only topology differs")
        for channel in ("vertices", "uvs", "normals", "bone_indices", "bone_weights", "source_bone_palette"):
            if getattr(a, channel) != getattr(b, channel):
                raise ValueError("Visible-layer CDMW changed retained vertex channel: " + channel)


def prepare(output=DEFAULT_OUTPUT, head_report=DEFAULT_HEAD_UV_REPORT,
            source=ROOT / "build/cdmw-fixed-source", deps=ROOT / "build/cdmw-deps"):
    output, head_report = native.output_directory(output), native.output_directory(head_report)
    source, deps = native.output_directory(source), native.output_directory(deps) if deps is not None else None
    protected = [head_report.parent, source, *PROTECTED_DIRS]
    if deps is not None:
        protected.append(deps)
    if output != native.output_directory(DEFAULT_OUTPUT):
        protected.append(DEFAULT_OUTPUT)
    output = orientation.preflight(output, protected)
    sources, snapshot = read_inputs(head_report)
    report, payload = make_report(sources), transform_pac(sources["headPac"])
    official = verify_official_mapping(sources["headPac"])
    verify_cdmw(sources["headPac"], payload, source, deps)
    orientation.verify_snapshot(snapshot); orientation.verify_snapshot(official)
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True); output.mkdir()
    writes = {relative: sources[key] for key, (relative, _) in SOURCE_SPECS.items()}
    writes["resources/" + PAC_PATH], writes[REPORT_NAME] = payload, report_bytes(report)
    for relative, raw in writes.items():
        p = package_path(output, relative); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("xb") as stream:
            stream.write(raw)
    load_candidate(output / REPORT_NAME)
    orientation.verify_snapshot(snapshot); orientation.verify_snapshot(official)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--head-uv-report", type=Path, default=DEFAULT_HEAD_UV_REPORT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.head_uv_report, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "removedIndexBytes": report["audit"]["difference"]["removedIndexBytes"],
        "hatAlphaCounts": report["audit"]["textureEvidence"]["hatAlphaCounts"],
        "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
