"""Build a separate, offline Z-reflected Steve PAC with regenerated UV frames.

PAC packed direction conventions are source-backed empirical evidence from the
fixed native donor, not a shader ABI or live-render acceptance. Unknown layouts,
contradictory donor records or incomplete candidate frames stop publication.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct

import analyze_steve_rig as rig
import prepare_native_steve as native
import prepare_steve_material as material
import prepare_steve_prefab as prefab

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-orientation"
REPORT_NAME = "steve-orientation-report.json"
PREFAB_REPORT_SHA256 = "b141da0e8a16d005a0cfeb5b3d2f7adabe6194da6220102bc0455a806fb0af9d"
RIG_REPORT_SHA256 = "ea2225304ba2dc7c74c936cf94594baa78870b791832911f96dd1eab43673865"
PACKED_DIRECTION_SOURCE = "cdmw/services/new_item_template_model.py"
NORMAL_SOURCE = "cdmw/modding/mesh_pac_builder.py"
FRAME_TOLERANCE = .004


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(v):
    if len(v) != 3 or not all(math.isfinite(x) for x in v):
        raise ValueError("Frame vector must have three finite components")
    length = math.sqrt(dot(v, v))
    if length <= 1e-12:
        raise ValueError("Frame vector is degenerate")
    return tuple(x / length for x in v)


def plane(v, n):
    n = unit(n)
    return unit(tuple(x - dot(v, n) * y for x, y in zip(v, n)))


def triangle_uv_frame(points, uvs):
    a, b, c = points
    e1, e2 = tuple(y - x for x, y in zip(a, b)), tuple(y - x for x, y in zip(a, c))
    du1, dv1 = tuple(y - x for x, y in zip(uvs[0], uvs[1]))
    du2, dv2 = tuple(y - x for x, y in zip(uvs[0], uvs[2]))
    det = du1 * dv2 - du2 * dv1
    if not math.isfinite(det) or abs(det) <= 1e-12 or dot(cross(e1, e2), cross(e1, e2)) <= 1e-20:
        raise ValueError("Triangle has a degenerate position or UV frame")
    return (tuple((x * dv2 - y * dv1) / det for x, y in zip(e1, e2)),
            tuple((y * du1 - x * du2) / det for x, y in zip(e1, e2)))


def decode_record_frame(data, offset):
    """Independent scalar read of lanes documented by fixed CDMW sources."""
    if not 0 <= offset <= len(data) - 40:
        raise ValueError("PAC frame record is out of bounds")
    lane, word = struct.unpack_from("<h", data, offset + 6)[0], struct.unpack_from("<I", data, offset + 16)[0]
    nx, ny = ((word >> 10) & 1023) / 511.5 - 1, ((word >> 20) & 1023) / 511.5 - 1
    nz = math.sqrt(max(0, 1 - nx * nx - ny * ny)) * (-1 if word & 0x40000000 else 1)
    vx, vy = abs(lane / 32767.0) * 2 - 1, (word & 1023) / 511.5 - 1
    vz = math.sqrt(max(0, 1 - vx * vx - vy * vy)) * (-1 if lane < 0 else 1)
    # This polarity is inferred below from unique, strongly aligned native
    # donor records for both bit31 values, rather than borrowed from glTF.
    sign = 1.0 if word & 0x80000000 else -1.0
    return (nx, ny, nz), (vx, vy, vz), sign


def donor_contract(data, mesh):
    strong, conflicts, u_aligned, v_aligned = {}, 0, set(), set()
    for part in mesh.submeshes:
        if part.source_vertex_stride != 40:
            raise ValueError("Donor direction evidence requires the exact PAC40 layout")
        for face in part.faces:
            try:
                u, v = triangle_uv_frame([part.vertices[i] for i in face], [part.uvs[i] for i in face])
            except ValueError:
                continue  # Exclude degenerate donor evidence; candidate cannot exclude any.
            for index in face:
                offset = part.source_vertex_offsets[index]
                normal, packed_v, sign = decode_record_frame(data, offset)
                u_dot, v_dot = dot(packed_v, unit(u)), dot(packed_v, unit(v))
                if abs(u_dot) > .95:
                    u_aligned.add(offset)
                if v_dot > .95:
                    v_aligned.add(offset)
                derived_u_dot = dot(cross(normal, packed_v), unit(u))
                if v_dot > .95 and abs(derived_u_dot) > .95 and abs(dot(normal, packed_v)) < .08:
                    observation = (sign, derived_u_dot > 0)
                    if offset in strong and strong[offset] != observation:
                        conflicts += 1
                    strong[offset] = observation
    positive = [offset for offset, (sign, actual) in strong.items() if sign > 0 and actual]
    negative = [offset for offset, (sign, actual) in strong.items() if sign < 0 and not actual]
    contradictions = [offset for offset, (sign, actual) in strong.items() if (sign > 0) != actual]
    if (conflicts or contradictions or len(strong) < 10000 or len(positive) < 5 or len(negative) < 10000
            or u_aligned or len(v_aligned) < 10000):
        raise ValueError("Fixed donor packed-frame convention is incomplete or contradictory")
    return {"classification": "source-backed empirical", "shaderAbiProven": False, "liveVerified": False,
            "donorSha256": native.sha256(data), "uniqueStrongRecords": len(strong),
            "positiveHandednessRecords": len(positive), "negativeHandednessRecords": len(negative),
            "positiveRecordOffsets": sorted(positive), "contradictions": len(contradictions),
            "conflictingTriangleObservations": conflicts, "uniqueUVUAlignedRecords": len(u_aligned),
            "uniqueUVVAlignedRecords": len(v_aligned),
            "packedDirection": "Native UV V derivative, projected against the decoded normal",
            "reconstructedUVU": "U = cross(N, packedV) * (bit31 ? +1 : -1)",
            "encoding": "signed-magnitude X/Z at bytes6..7; Y at normalword bits0..9; normalXY bits10..29 and normalZ sign bit30",
            "strengthThresholds": {"uvVDot": .95, "absoluteUFromCrossDot": .95, "absoluteNormalDot": .08}}


def vertex_frames(vertices, normals, uvs, faces):
    u_sum, v_sum = [[0., 0., 0.] for _ in vertices], [[0., 0., 0.] for _ in vertices]
    corners = [[] for _ in vertices]
    for face in faces:
        u, v = triangle_uv_frame([vertices[i] for i in face], [uvs[i] for i in face])
        for index in face:
            for c in range(3):
                u_sum[index][c] += u[c]
                v_sum[index][c] += v[c]
            corners[index].append((u, v))
    frames = []
    for index, normal in enumerate(normals):
        if not corners[index]:
            raise ValueError("Candidate contains an unreferenced vertex without a UV frame")
        n, v = unit(normal), plane(v_sum[index], normal)
        u = plane(u_sum[index], n)
        sign = 1.0 if dot(cross(n, v), u) > 0 else -1.0
        reconstructed = tuple(x * sign for x in cross(n, v))
        if dot(reconstructed, u) < .999:
            raise ValueError("Candidate U/V frame is not representable by the fixed native lane")
        for cu, cv in corners[index]:
            if dot(v, plane(cv, n)) < .999 or dot(reconstructed, plane(cu, n)) < .999:
                raise ValueError("Candidate vertex has conflicting tangent corners; no splitting is allowed")
        frames.append((v, sign))
    return frames


def encode_frame(data, offset, v, sign):
    if sign not in (-1., 1.) or abs(dot(v, v) - 1) > 1e-6:
        raise ValueError("Authored packed frame is invalid")
    lane = max(0, min(32767, round((v[0] + 1) * 16383.5)))
    if v[2] < 0:
        lane = -lane
    word = struct.unpack_from("<I", data, offset + 16)[0]
    word = ((word ^ 0x40000000) & ~0x800003FF) | max(0, min(1023, round((v[1] + 1) * 511.5)))
    if sign > 0:
        word |= 0x80000000
    struct.pack_into("<h", data, offset + 6, lane)
    struct.pack_into("<I", data, offset + 16, word)


def parse_lods(data, donor_data):
    from cdmw.modding.mesh_parser import parse_pac, _parse_par_sections, _parse_pac_geometry_section
    donor = parse_pac(donor_data, native.BODY)
    descriptors, count = native.validate_runtime_descriptors(donor_data, data, donor)
    if count != 4 or len(descriptors) != 3:
        raise ValueError("Only the verified four-LOD/three-descriptor Steve source is supported")
    levels = []
    for section in _parse_par_sections(data):
        if 1 <= section["index"] <= count:
            lod = count - section["index"]
            mesh = _parse_pac_geometry_section(data, native.BODY, descriptors, section, lod)
            if mesh.total_vertices != 288 or mesh.total_faces != 144 or len(mesh.submeshes) != 2:
                raise ValueError("A source LOD does not contain the complete fixed Steve model")
            levels.append((lod, mesh))
    if sorted(lod for lod, _ in levels) != list(range(4)):
        raise ValueError("PAC stored LOD set is incomplete")
    return sorted(levels), descriptors


def reflect_pac(source_data, donor_data, skeleton_data):
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.mesh_pac_builder import build_pac
    from cdmw.modding.skeleton_parser import parse_pab
    source = parse_pac(source_data, native.BODY)
    if native.sha256(source_data) != rig.CANDIDATE_SHA256 or build_pac(source, source_data) != source_data:
        raise ValueError("Steve source PAC fails its fixed SHA or byte-identical no-edit baseline")
    skeleton = parse_pab(skeleton_data, native.SKELETON)
    palette = resolve_pac_bone_palette(source_data, skeleton)
    if palette != resolve_pac_bone_palette(donor_data, skeleton):
        raise ValueError("Steve palette differs from its real donor")
    contract = donor_contract(donor_data, parse_pac(donor_data, native.BODY))
    levels, descriptors = parse_lods(source_data, donor_data)
    result, allowed, seen_records, seen_faces = bytearray(source_data), set(), set(), set()
    authored_frames = {}
    for lod, mesh in levels:
        for part in mesh.submeshes:
            if (part.source_vertex_stride != 40 or len(part.source_vertex_offsets) != len(part.vertices)
                    or part.source_index_offset < 0 or part.source_bbox_min[2] * 2 + part.source_bbox_extent[2] != 0):
                raise ValueError("Reflection requires unique PAC40 records and an exactly symmetric Z quantization box")
            vertices = [(x, y, -z) for x, y, z in part.vertices]
            normals = [(x, y, -z) for x, y, z in part.normals]
            faces = [(a, c, b) for a, b, c in part.faces]
            frames = vertex_frames(vertices, normals, part.uvs, faces)
            for offset, frame in zip(part.source_vertex_offsets, frames):
                if offset in seen_records:
                    raise ValueError("Candidate contains a shared native record between stored LODs")
                seen_records.add(offset)
                z = struct.unpack_from("<H", source_data, offset + 4)[0]
                if z > 32767:
                    raise ValueError("PAC Z position exceeds the proven 15-bit UNORM range")
                struct.pack_into("<H", result, offset + 4, 32767 - z)
                encode_frame(result, offset, *frame)
                allowed.update(range(offset + 4, offset + 8))
                allowed.update(range(offset + 16, offset + 20))
                authored_frames[offset] = frame
            for index, face in enumerate(faces):
                offset = part.source_index_offset + index * 6
                if offset in seen_faces or not 0 <= offset <= len(source_data) - 6:
                    raise ValueError("Candidate triangle record boundary is ambiguous")
                seen_faces.add(offset)
                struct.pack_into("<3H", result, offset, *face)
                allowed.update(range(offset, offset + 6))
    payload = bytes(result)
    if payload == source_data or any(a != b and i not in allowed for i, (a, b) in enumerate(zip(source_data, payload))):
        raise ValueError("Orientation changed bytes outside the exact proven position/frame/index lanes")
    target_levels, target_descriptors = parse_lods(payload, donor_data)
    if target_descriptors != descriptors or resolve_pac_bone_palette(payload, skeleton) != palette:
        raise ValueError("Orientation changed descriptor or palette bytes")
    audits = []
    for (lod, original), (new_lod, target) in zip(levels, target_levels):
        if lod != new_lod:
            raise ValueError("Orientation changed LOD identity")
        maximum_position, maximum_frame, minimum_area_dot = 0., 0., math.inf
        for before, after in zip(original.submeshes, target.submeshes):
            if (before.name != after.name or before.uvs != after.uvs or before.bone_indices != after.bone_indices
                    or before.bone_weights != after.bone_weights or before.source_vertex_offsets != after.source_vertex_offsets
                    or after.faces != [(a, c, b) for a, b, c in before.faces]):
                raise ValueError("Orientation changed source order, UVs, weights or more than one winding reversal")
            for point, changed, normal, changed_normal, offset in zip(before.vertices, after.vertices, before.normals, after.normals, after.source_vertex_offsets):
                maximum_position = max(maximum_position, rig.distance((point[0], point[1], -point[2]), changed))
                if rig.error((normal[0], normal[1], -normal[2]), changed_normal) > 1e-12:
                    raise ValueError("Normal reflection did not preserve exact decoded normal XY")
                packed_n, packed_v, sign = decode_record_frame(payload, offset)
                wanted_v, wanted_sign = authored_frames[offset]
                maximum_frame = max(maximum_frame, rig.distance(packed_v, wanted_v))
                if sign != wanted_sign or maximum_frame > FRAME_TOLERANCE or rig.error(packed_n, changed_normal) > 1e-12:
                    raise ValueError("Packed frame roundtrip or empirical handedness exceeds the reviewed bound")
                if source_data[offset:offset + 4] != payload[offset:offset + 4] or source_data[offset + 8:offset + 16] != payload[offset + 8:offset + 16] or source_data[offset + 20:offset + 40] != payload[offset + 20:offset + 40]:
                    raise ValueError("Orientation changed XY position, UV, colour or skin/opaque bytes")
            for face in after.faces:
                a, b, c = [after.vertices[i] for i in face]
                area = cross(tuple(y - x for x, y in zip(a, b)), tuple(y - x for x, y in zip(a, c)))
                minimum_area_dot = min(minimum_area_dot, dot(area, after.normals[face[0]]))
        if maximum_position > 1e-12 or minimum_area_dot <= 0:
            raise ValueError(f"Independent reflected position or face-normal orientation failed: "
                             f"LOD{lod} positionError={maximum_position} areaDot={minimum_area_dot}")
        audits.append({"lod": lod, "vertices": target.total_vertices, "triangles": target.total_faces,
                       "maximumPositionReflectionErrorMetres": maximum_position,
                       "maximumPackedVDirectionError": maximum_frame, "minimumFaceAreaDotNormal": minimum_area_dot})
    return payload, {"sourcePacSha256": native.sha256(source_data), "candidatePacSha256": native.sha256(payload),
                     "sourceNoEditCDMWRebuildByteIdentical": True, "storedDrawDescriptors": 3,
                     "activeDrawDescriptors": 2, "descriptorsByteIdentical": True, "paletteByteIdentical": True,
                     "weightsByteIdentical": True, "uvBytesIdentical": True, "opaqueVertexBytesIdentical": True,
                     "candidateRecordsWithCompleteFrames": len(seen_records), "candidateTrianglesReversedOnce": len(seen_faces),
                     "perLod": audits, "packedFrameContract": contract,
                     "positionMethod": "Exact symmetric 15-bit UNORM quantization: qZ -> 32767-qZ, leaving descriptor bounds unchanged",
                     "directionMethod": "Reflect decoded normal Z; recompute each native UV V frame and bit31 U-from-cross polarity",
                     "writer": "Bounded in-place record edits, independently compared against CDMW parse and no-edit writer baseline"}


def fixed_rig_inputs():
    return {"build/native-steve/template/" + native.SKELETON: native.TEMPLATE_HASHES[native.SKELETON],
            "build/native-steve/template/" + native.BODY: native.TEMPLATE_HASHES[native.BODY],
            "build/native-steve/template/" + native.VARIATION: rig.PABC_SHA256,
            "build/native-steve/steve-rig-candidate.pac": rig.CANDIDATE_SHA256,
            "build/steve-prefab/template/" + rig.PREFAB_PATH: rig.PREFAB_SHA256,
            "build/steve-prefab/template/" + native.DESCRIPTOR: rig.DESCRIPTOR_SHA256,
            **{"build/steve-1.21.1/" + k: v for k, v in native.STEVE_HASHES.items()}}


def load_inputs(prefab_report, rig_report):
    prefab_report, rig_report = native.output_directory(prefab_report), native.output_directory(rig_report)
    snapshot = {}
    source_raw = rig.read_fixed(prefab_report, PREFAB_REPORT_SHA256, snapshot)
    rig_raw = rig.read_fixed(rig_report, RIG_REPORT_SHA256, snapshot)
    source_report, rig_report_data = prefab.strict_json(source_raw), prefab.strict_json(rig_raw)
    if rig_report_data.get("inputs") != fixed_rig_inputs() or not all(v is False for v in rig_report_data["integration"].values()):
        raise ValueError("Rig evidence inputs or integration claims differ from the reviewed analysis")
    for relative, digest in fixed_rig_inputs().items():
        rig.read_fixed(native.output_directory(ROOT / relative), digest, snapshot)
    expected_paths = set(prefab.INPUT_RESOURCES) | {prefab.PREFAB_PATH, prefab.DESCRIPTOR_PATH}
    if (len(source_report["candidateResources"]) != 7 or
            {r["virtualPath"] for r in source_report["candidateResources"]} != expected_paths or
            any(v is not False for v in source_report["integration"].values())):
        raise ValueError("Source prefab is not the exact seven-resource offline candidate")
    files = {}
    for relative, digest in source_report["files"].items():
        path = native.output_directory(prefab_report.parent / relative)
        if not path.is_relative_to(prefab_report.parent):
            raise ValueError("Source prefab file escapes its own directory")
        files[relative] = rig.read_fixed(path, digest, snapshot)
    return source_report, rig_report_data, files, snapshot


def preflight(output, source_dirs):
    output = native.output_directory(output)
    for directory in source_dirs:
        native.check_links(directory)
        directory = directory.resolve()
        if output == directory or output.is_relative_to(directory) or directory.is_relative_to(output):
            raise ValueError("Orientation output overlaps an input/source directory")
    if output.exists():
        raise ValueError("Orientation output already exists; previous or foreign assets are never overwritten")
    return output


def verify_snapshot(snapshot):
    for path, data in snapshot.items():
        native.check_links(path)
        if path.stat().st_size != len(data) or path.read_bytes() != data:
            raise ValueError("Orientation input changed before publication")


def prepare(prefab_report, rig_report, output, source, deps):
    source_dirs = [prefab_report.parent, rig_report.parent, source, deps,
                   ROOT / "build/native-steve", ROOT / "build/steve-1.21.1"]
    output = preflight(output, source_dirs)
    source_report, rig_report_data, files, snapshot = load_inputs(prefab_report, rig_report)
    provenance = native.load_cdmw(source, deps)
    pac_local = "resources/" + material.PAC_PATH
    candidate, audit = reflect_pac(files[pac_local], files["template/" + native.BODY], files["template/" + native.SKELETON])
    audit["packedFrameContract"]["fixedSourceEvidence"] = {
        relative: native.file_hash(source / relative)
        for relative in (PACKED_DIRECTION_SOURCE, NORMAL_SOURCE, "cdmw/modding/mesh_parser.py")}
    files[pac_local] = candidate
    rows = copy.deepcopy(source_report["candidateResources"])
    for row in rows:
        if row["virtualPath"] == material.PAC_PATH:
            row["sha256"] = native.sha256(candidate)
    # These audits still describe only unchanged prefab/descriptor bytes. PAC
    # geometry claims are new and never inherited from the earlier source.
    prefab.audit_prefab(files["resources/" + prefab.PREFAB_PATH], material.PAC_PATH)
    prefab.audit_descriptor(files["resources/" + prefab.DESCRIPTOR_PATH])
    report = {"schemaVersion": 1, "orientationCandidate": True, "variant": "steve-native-forward-z-reflection",
              "supportedExeSha256": native.EXE_SHA256, "cdmw": provenance,
              "archiveIndexSha256": source_report["archiveIndexSha256"],
              "sourcePrefabReport": str(prefab_report.resolve().relative_to(ROOT)).replace("\\", "/"),
              "sourcePrefabReportSha256": PREFAB_REPORT_SHA256,
              "rigAnalysisReport": str(rig_report.resolve().relative_to(ROOT)).replace("\\", "/"),
              "rigAnalysisReportSha256": RIG_REPORT_SHA256, "rigInputs": fixed_rig_inputs(),
              "candidateResources": rows, "logicalPrefabPath": prefab.LOGICAL_PREFAB,
              "changedResource": material.PAC_PATH, "unchangedCandidateCount": 6,
              "orientationAudit": audit,
              "parts": [{"part": p["name"], "semanticJoint": p["parent"], "vertices": len(p["vertices"]),
                          "xUnchanged": True, "yUnchanged": True, "zReflected": True, "nativeUvUnchanged": True}
                         for p in native.steve_geometry(ROOT / "build/steve-1.21.1")],
              "templates": copy.deepcopy(source_report["templates"]),
              "files": {path: native.sha256(data) for path, data in files.items()},
              "integration": {key: False for key in source_report["integration"]},
              "limitations": ["Separate build-only orientation candidate; no game access, installation or asset-chain update.",
                              "Packed-frame convention is source-backed empirical, with both bit31 values evidenced by the fixed donor; shader ABI and live rendering remain unverified.",
                              "A Z reflection preserves left/right X semantics but does not repair six native-vs-Minecraft pivot differences.",
                              "Existing PAB/PABC/PAPR, underwear, materials, texture bytes and prefab references are unchanged; animation/control/equipment remain unverified.",
                              "The packed frame is regenerated at every vertex/LOD; no unsupported authored CDMW tangent writeback is claimed.",
                              "Native and MC assets remain licensed local ignored build payloads and must not be redistributed."]}
    verify_snapshot(snapshot)
    native.verify_source(source)
    output = preflight(output, source_dirs)
    all_files = {**files, REPORT_NAME: (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()}
    output.parent.mkdir(parents=True, exist_ok=True)
    native.check_links(output)
    output.mkdir()  # Exclusive creation; never adopt a raced existing directory.
    for relative, data in all_files.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(path)
        with path.open("xb") as stream:
            stream.write(data)
    verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefab-report", type=Path, default=ROOT / "build/steve-prefab/steve-prefab-report.json")
    parser.add_argument("--rig-report", type=Path, default=ROOT / "build/steve-rig-analysis/steve-rig-analysis.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.prefab_report, args.rig_report, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "resources": len(report["candidateResources"]),
                      "orientationCandidate": report["orientationCandidate"], "orientationAudit": report["orientationAudit"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
