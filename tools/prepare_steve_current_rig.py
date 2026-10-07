"""Prepare an offline, explicit Macduff-01_0002 neutral compensation candidate.

Read only the fixed native index. Retain its descriptor scale/skeleton/variation/
ragdoll/constraint fields verbatim. Pre-deform the mesh for the documented CDMW
neutral interpretation, without asserting native shader or animation acceptance.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import prepare_steve_segmented as segmented

native, rig, orientation = segmented.native, segmented.rig, segmented.orientation
prefab, material = segmented.prefab, segmented.material
ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-current-rig"
REPORT_NAME = "steve-current-rig-report.json"
SOURCE_REPORT_SHA256 = "e7a879dfb26e38b64fe0d65322b89e98b792018ae1bd7762ad47c7367b4ae0fd"
SOURCE_PAC_SHA256 = "dd1143464bedc9b8aab9a5a39a3eaa9381753690497d2eda35cd8bb3edcfaf1a"
CURRENT_DESCRIPTOR = "character/prefab/1_pc/01_phm/nude/cd_phm_00_nude_01_0002_macduff.prefabdata_xml"
CURRENT_PREFAB = "character/bin__/prefab/1_pc/01_phm/nude/cd_phm_00_nude_01_0002_macduff.prefab"
CURRENT_VARIATION = "character/binary/skeletonvariation/1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc"
TEMPLATE_HASHES = {
    CURRENT_DESCRIPTOR: "e4f831a4b7680dd0dbc7e0547b04347711ceff0d8427ccd5e0f58e611684e1f5",
    CURRENT_PREFAB: "0184309bae4ded9d51e07269ddebea8ed6f6b08701c59a077f9d866d6002e757",
    CURRENT_VARIATION: "4aa84904dc4d24d7700d5a4ec00c10631973157a1ff54877fd9f22cc61c39ef3",
    native.SKELETON: native.TEMPLATE_HASHES[native.SKELETON],
    native.CONSTRAINT: "e09f83b94d61512105d736c0cf210d29698e032677accbd6015bfb6eabfb79ad",
}
FIELDS = {
    "BaseCharacterScale": {"Value": "1.02571"},
    "SkeletonName": {"FileName": "1_pc/1_phm/phm_01.pab"},
    "SkeletonVariationName": {"FileName": "1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc"},
    "RagdollName": {"FileName": "1_pc/1_phm/macduff.hkt"},
    "AnimationConstraintName": {"FileName": "1_pc/1_phm/phm_01.papr"},
}
PRIVATE_NAME = "crimsonmc_steve_rig_01"
PAC_PATH = material.PAC_PATH.replace("crimsonmc_steve_1_21_1", PRIVATE_NAME)
MATERIAL_PATH = material.MATERIAL_PATH.replace("crimsonmc_steve_1_21_1", PRIVATE_NAME)
PREFAB_PATH = prefab.PREFAB_PATH.replace("crimsonmc_steve_1_21_1", PRIVATE_NAME)
DESCRIPTOR_PATH = prefab.DESCRIPTOR_PATH.replace("crimsonmc_steve_1_21_1", PRIVATE_NAME)
LOGICAL_PREFAB = prefab.LOGICAL_PREFAB.replace("crimsonmc_steve_1_21_1", PRIVATE_NAME)


def descriptor_contract(raw):
    if native.sha256(raw) != TEMPLATE_HASHES[CURRENT_DESCRIPTOR]:
        raise ValueError("Current descriptor fingerprint differs")
    root = ET.fromstring(raw.decode("utf-8-sig"))
    if root.tag != "NudePrefabData" or root.attrib or len(root) != 5 or {r.tag: r.attrib for r in root} != FIELDS:
        raise ValueError("Current descriptor fields differ")
    return copy.deepcopy(FIELDS)


def read_templates(game):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    for path in (game, exe, index):
        native.check_links(path)
    if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != prefab.INDEX_SHA256:
        raise ValueError("Unsupported EXE or original 0009 index")
    selected = native.select_unique_entries(parse_archive_pamt(index), tuple(TEMPLATE_HASHES))
    payloads, flags = {}, {}
    for path, entry in selected.items():
        native.check_links(Path(entry.paz_file))
        raw = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if not raw or len(raw) > rig.FILE_LIMIT or native.sha256(raw) != TEMPLATE_HASHES[path]:
            raise ValueError("Current rig template fingerprint differs: " + path)
        payloads[path], flags[path] = raw, entry.flags
    descriptor_contract(payloads[CURRENT_DESCRIPTOR])
    if native.file_hash(index) != prefab.INDEX_SHA256 or native.file_hash(exe) != native.EXE_SHA256:
        raise ValueError("Native source identity changed during extraction")
    return payloads, flags


def load_source(path):
    path = native.output_directory(path)
    snapshot = {}
    report = prefab.strict_json(rig.read_fixed(path, SOURCE_REPORT_SHA256, snapshot))
    if report.get("variant") != "steve-native-limb-segments" or any(v is not False for v in report["integration"].values()):
        raise ValueError("Source is not the fixed offline segmented candidate")
    files = {}
    for relative, sha in report["files"].items():
        file = native.output_directory(path.parent / relative)
        if not file.is_relative_to(path.parent):
            raise ValueError("Source file escapes its directory")
        files[relative] = rig.read_fixed(file, sha, snapshot)
    if native.sha256(files["resources/" + material.PAC_PATH]) != SOURCE_PAC_SHA256:
        raise ValueError("Segmented PAC fingerprint differs")
    return report, files, snapshot


def neutral_matrices(pab, pabc):
    """Pure model-space contract for later body/head split candidates as well."""
    from cdmw.modding.skeleton_parser import parse_pab
    from cdmw.modding.skeleton_variation_parser import parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices
    if native.sha256(pab) != TEMPLATE_HASHES[native.SKELETON] or native.sha256(pabc) != TEMPLATE_HASHES[CURRENT_VARIATION]:
        raise ValueError("Current PAB/PABC fingerprints differ")
    bones, _ = rig.parse_pab_records(pab)
    rows, duplicate = rig.parse_pabc_records(pabc, bones)
    if len(rows) != 420 or duplicate:
        raise ValueError("Current PABC record layout differs")
    targets = [b["bind"] for b in bones]
    for row in rows:
        targets[row["boneIndex"]] = rig.neutral_bind(bones[row["boneIndex"]]["bind"], row["blocks"][0])[0]
    matrices = [rig.multiply(b["inverse"], targets[i]) for i, b in enumerate(bones)]
    skeleton = parse_pab(pab, native.SKELETON)
    parsed = parse_pabc_skeleton_variation(pabc, CURRENT_VARIATION, skeleton=skeleton)
    other = [b.bind_matrix for b in skeleton.bones]
    for row in parsed.records:
        other[row.bone_index] = _neutral_variation_bind_matrix(other[row.bone_index], row.matrix_blocks[0])
    if max(rig.error(a, b) for a, b in zip(matrices, _skin_matrices(skeleton.bones, other))) > 1e-12:
        raise ValueError("Independent current neutral matrices differ from fixed CDMW")
    return skeleton, matrices, {row["boneIndex"] for row in rows}


def blend_matrix(slots, weights, palette, matrices):
    if (not slots or len(slots) != len(weights) or len(set(slots)) != len(slots)
            or any(type(s) is not int or not 0 <= s < len(palette) for s in slots)
            or any(not math.isfinite(w) or w <= 0 for w in weights) or abs(sum(weights) - 1) > 1e-8):
        raise ValueError("Skin row is not an exact normalized palette mapping")
    matrix = tuple(math.fsum(w * matrices[palette[s]][i] for s, w in zip(slots, weights)) for i in range(16))
    if not .5 < rig.determinant3(matrix) < 2:
        raise ValueError("Neutral blend is singular, inverted or outside reviewed bounds")
    return matrix


def compensate_point(point, slots, weights, palette, matrices):
    matrix = blend_matrix(slots, weights, palette, matrices)
    return rig.transform(point, rig.inverse(matrix)), matrix


def covector_normal(normal, matrix):
    # p_bind = p_target * A^-1. A row normal covector therefore uses A^T.
    # This is an explicit affine mathematical convention, not a native shader ABI.
    return orientation.unit(tuple(math.fsum(normal[k] * matrix[c * 4 + k] for k in range(3)) for c in range(3)))


def direction(vector, matrix):
    return orientation.unit(tuple(math.fsum(vector[k] * matrix[k * 4 + c] for k in range(3)) for c in range(3)))


def compensate_pac(source, donor, pab, pabc):
    """Preserve topology, UV and skin bytes; edit only bounds/position/normal/frame."""
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.mesh_pac_builder import _quantize_pac_u16, _pack_pac_normal, build_pac
    skeleton, matrices, covered = neutral_matrices(pab, pabc)
    palette = resolve_pac_bone_palette(source, skeleton)
    if palette != resolve_pac_bone_palette(donor, skeleton):
        raise ValueError("Candidate palette differs from native donor")
    source_levels = segmented.parse_lods(source, donor)
    descriptors, _ = native.validate_runtime_descriptors(donor, source, parse_pac(donor, native.BODY))
    active_descriptors = [d for d in descriptors if any(d.vertex_counts)]
    authored, allowed, result = {}, set(), bytearray(source)
    old_maximum = 0.
    for lod, mesh in source_levels:
        for index, part in enumerate(mesh.submeshes):
            positions, normals, frames = [], [], []
            for point, normal, slots, weights, offset in zip(part.vertices, part.normals, part.bone_indices, part.bone_weights, part.source_vertex_offsets):
                if any(palette[s] not in covered for s in slots):
                    raise ValueError("Candidate weighted bone is absent from current PABC")
                pre, matrix = compensate_point(point, slots, weights, palette, matrices)
                old_maximum = max(old_maximum, rig.distance(point, rig.transform(point, matrix)))
                positions.append(pre)
                normals.append(covector_normal(normal, matrix))
                _, source_v, sign = orientation.decode_record_frame(source, offset)
                frames.append((direction(source_v, rig.inverse(matrix)), sign))
            authored[(lod, index)] = positions, normals, frames
    for index, descriptor in enumerate(active_descriptors):
        positions = [p for (lod, i), (points, _, _) in authored.items() if i == index for p in points]
        lo = tuple(min(p[i] for p in positions) for i in range(3))
        extent = tuple(max(p[i] for p in positions) - lo[i] for i in range(3))
        offset = descriptor.descriptor_offset + 11
        struct.pack_into("<6f", result, offset, *lo, *extent)
        lo, extent = struct.unpack_from("<3f", result, offset), struct.unpack_from("<3f", result, offset + 12)
        allowed.update(range(offset, offset + 24))
        for lod, mesh in source_levels:
            part = mesh.submeshes[index]
            points, normals, _ = authored[(lod, index)]
            for point, normal, offset in zip(points, normals, part.source_vertex_offsets):
                struct.pack_into("<3H", result, offset, *(_quantize_pac_u16(point[i], lo[i], extent[i]) for i in range(3)))
                word = _pack_pac_normal(normal, struct.unpack_from("<I", result, offset + 16)[0])
                struct.pack_into("<I", result, offset + 16, word)
                allowed.update(range(offset, offset + 8))
                allowed.update(range(offset + 16, offset + 20))
    for lod, mesh in segmented.parse_lods(bytes(result), donor):
        for index, part in enumerate(mesh.submeshes):
            for offset, normal, (v, sign) in zip(part.source_vertex_offsets, part.normals, authored[(lod, index)][2]):
                # Transport the final neutral surface's frame, not the derivative
                # of its pre-distorted bind surface (which includes dA/dposition).
                segmented.pack_frame(result, offset, orientation.plane(v, normal), sign)
    payload = bytes(result)
    if len(payload) != len(source) or any(a != b and i not in allowed for i, (a, b) in enumerate(zip(source, payload))):
        raise ValueError("Compensation changed an unreviewed PAC byte lane")
    maximum, per_lod, minimum_normal, minimum_v = 0., [], 1., 1.
    for (lod, before), (new_lod, after) in zip(source_levels, segmented.parse_lods(payload, donor)):
        if lod != new_lod:
            raise ValueError("LOD order changed")
        moved = rig.independently_deform(after, palette, matrices)
        local_max = 0.
        for a, b, points in zip(before.submeshes, after.submeshes, moved):
            if (a.faces != b.faces or a.uvs != b.uvs or a.bone_indices != b.bone_indices or a.bone_weights != b.bone_weights
                    or a.source_vertex_offsets != b.source_vertex_offsets or a.name != b.name):
                raise ValueError("Compensation changed topology, UV, weights or identity")
            local_max = max(local_max, max(rig.distance(p, q) for p, q in zip(a.vertices, points)))
            for offset, slots, weights in zip(b.source_vertex_offsets, b.bone_indices, b.bone_weights):
                matrix = blend_matrix(slots, weights, palette, matrices)
                expected_n, expected_v, expected_sign = orientation.decode_record_frame(source, offset)
                normal, v, sign = orientation.decode_record_frame(payload, offset)
                minimum_normal = min(minimum_normal, orientation.dot(covector_normal(normal, rig.inverse(matrix)), orientation.unit(expected_n)))
                minimum_v = min(minimum_v, orientation.dot(direction(v, matrix), orientation.unit(expected_v)))
                if sign != expected_sign:
                    raise ValueError("Frame transport changed handedness under a positive determinant")
        maximum = max(maximum, local_max)
        per_lod.append({"lod": lod, "vertices": after.total_vertices, "triangles": after.total_faces,
                        "currentNeutralTargetErrorMetres": local_max})
    if maximum > .0001 or min(minimum_normal, minimum_v) < .995 or build_pac(parse_pac(payload, native.BODY), payload) != payload:
        raise ValueError("Current neutral roundtrip or no-edit PAC rebuild failed")
    return payload, {"beforeNeutralMaximumDisplacementMetres": old_maximum,
                     "afterNeutralMaximumTargetErrorMetres": maximum, "perLod": per_lod,
                     "topologyUVSkinBytesPreserved": True, "onlyBoundsPositionNormalFrameChanged": True,
                     "minimumNeutralCovectorNormalDot": minimum_normal, "minimumNeutralTransportedVDot": minimum_v,
                     "positionEquation": "p_bind = p_target * inverse(sum(w * inverseBind * currentNeutralBind))",
                     "normalConvention": "Affine covector n_bind = normalize(n_target * transpose(A)); V_bind = normalize(V_target * inverse(A)), projected against encoded n_bind. These transport the final neutral frame, not the pre-distorted bind-surface gradient; native shader skin-normal path remains unverified",
                     "baseCharacterScaleCompensated": False}


def current_prefab(raw):
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    if native.sha256(raw) != TEMPLATE_HASHES[CURRENT_PREFAB] or len(PAC_PATH) != len(native.BODY):
        raise ValueError("Current prefab or equal-length private path differs")
    original = prefab.audit_prefab(raw, native.BODY)
    span = original.objects[0].resources[0]
    start, end = span.offset + 4, span.offset + 4 + span.length
    result = rewrite_prefab_paths(raw, {native.BODY: PAC_PATH})
    if result.data != raw[:start] + PAC_PATH.encode() + raw[end:] or result.byte_delta or len(result.edits) != 1:
        raise ValueError("Current prefab changed outside its one mesh reference")
    prefab.audit_prefab(result.data, PAC_PATH)
    if rewrite_prefab_paths(result.data, {PAC_PATH: native.BODY}).data != raw:
        raise ValueError("Current prefab inverse rewrite differs")
    return result.data


def prepare(game, source_report_path, output, source, deps):
    source_dirs = [source_report_path.parent, source, deps, game]
    output = orientation.preflight(output, source_dirs)
    report, files, snapshot = load_source(source_report_path)
    provenance = native.load_cdmw(source, deps)
    templates, flags = read_templates(game)
    candidate, audit = compensate_pac(files["resources/" + material.PAC_PATH], files["template/" + native.BODY],
                                      templates[native.SKELETON], templates[CURRENT_VARIATION])
    replacements = {
        material.PAC_PATH: (PAC_PATH, candidate, native.BODY),
        material.MATERIAL_PATH: (MATERIAL_PATH, files["resources/" + material.MATERIAL_PATH], native.MATERIAL),
        prefab.PREFAB_PATH: (PREFAB_PATH, current_prefab(templates[CURRENT_PREFAB]), CURRENT_PREFAB),
        prefab.DESCRIPTOR_PATH: (DESCRIPTOR_PATH, templates[CURRENT_DESCRIPTOR], CURRENT_DESCRIPTOR),
    }
    rows = copy.deepcopy(report["candidateResources"])
    for row in rows:
        if row["virtualPath"] in replacements:
            old = row["virtualPath"]
            path, data, template = replacements[old]
            del files[row["localFile"]]
            row.update({"virtualPath": path, "localFile": "resources/" + path, "sha256": native.sha256(data), "templatePath": template})
            if template in templates:
                row.update({"templateSha256": native.sha256(templates[template]), "templateArchiveFlags": flags[template]})
            files[row["localFile"]] = data
    files.update({"template/" + path: data for path, data in templates.items()})
    scale = float(FIELDS["BaseCharacterScale"]["Value"])
    result = {"schemaVersion": 1, "currentRigCandidate": True, "variant": "steve-current-macduff-neutral-precompensation",
              "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": prefab.INDEX_SHA256, "cdmw": provenance,
              "sourceSegmentedReportSha256": SOURCE_REPORT_SHA256, "sourcePacSha256": SOURCE_PAC_SHA256,
              "candidateResources": rows, "logicalPrefabPath": LOGICAL_PREFAB, "parts": report["parts"],
              "currentDescriptor": {"sourcePath": CURRENT_DESCRIPTOR, "sha256": TEMPLATE_HASHES[CURRENT_DESCRIPTOR],
                                    "byteIdentical": True, "fields": descriptor_contract(templates[CURRENT_DESCRIPTOR])},
              "currentRigInputs": TEMPLATE_HASHES, "compensationAudit": audit,
              "scaleInterpretation": {"preservedDescriptorScale": scale, "appliedToMeshVertices": False,
                                      "predictedAfterExternalUniformScaleErrorMetres": audit["afterNeutralMaximumTargetErrorMetres"] * scale,
                                      "engineApplicationOrderVerified": False},
              "externalReferences": [{"field": "RagdollName", "FileName": FIELDS["RagdollName"]["FileName"],
                                       "referenceBytePreserved": True, "payloadResolved": False, "runtimeResolutionVerified": False}],
              "files": {path: native.sha256(data) for path, data in files.items()},
              "integration": {key: False for key in report["integration"]},
              "limitations": ["Explicit independent build-only candidate; no game calls, installation, actor selection or asset replacement.",
                              "Neutral compensation uses the fixed CDMW PABC interpretation; the native runtime skinning path remains unverified.",
                              "BaseCharacterScale 1.02571 is copied verbatim and is not cancelled or baked into positions; external-scale predictions do not prove native application order.",
                              "The affine normal/orthonormal UV-frame convention is a candidate; native shader normals and animation responses are unverified.",
                              "Current neutral pose compensates the measured torso shrink only; dynamic head separation, shoulder/hip pivot mismatch and equipment partshrink remain unresolved.",
                              "This prefab retains CD_Underwear and the combined head/body Steve mesh; private body/head composition is a separate candidate.",
                              "Original macduff.hkt reference is retained; ragdoll payload location and runtime resolution are unverified.",
                              "All native and MC payloads remain local licensed ignored build assets; no redistribution authorization is implied."]}
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    current, current_flags = read_templates(game)
    if current != templates or current_flags != flags:
        raise ValueError("Current rig archive snapshot changed before publication")
    output = orientation.preflight(output, source_dirs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, data in {**files, REPORT_NAME: (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    orientation.verify_snapshot(snapshot)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--source-report", type=Path, default=ROOT / "build/steve-segmented/steve-segmented-report.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    report = prepare(game, args.source_report, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "compensation": report["compensationAudit"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
