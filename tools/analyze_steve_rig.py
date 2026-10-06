"""Analyze the fixed Steve/native rig contract without producing game assets.

The matrix implementation and PAB/PABC record reader below are independent of
CDMW. CDMW supplies an additional parsed-mesh/neutral-presentation comparison.
All rotations are synthetic offline examples, never captured game animation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import struct

import prepare_native_steve as native

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-rig-analysis"
REPORT_NAME = "steve-rig-analysis.json"
CANDIDATE_SHA256 = "430fa4685687d41082decec695a388661740954fab426f282719e0ffe962a974"
PABC_SHA256 = "d662f990135f90fb6862246524f7d719cdf0aa97cac4eb7e4891741bd072319d"
PREFAB_PATH = "character/bin__/prefab/1_pc/01_phm/nude/cd_phm_00_nude_00_0001.prefab"
PREFAB_SHA256 = "e3cd0a7937d34098d19078978de2022fe00031352702f5b1eb87fc40c5275ee9"
DESCRIPTOR_SHA256 = "ab6ed2fcef90c363e7461502be2cbe7a233d22bcdc7705611ec593f19351edda"
FILE_LIMIT = 32 * 1024 * 1024
IDENTITY = tuple(float(i // 4 == i % 4) for i in range(16))


def matrix(values):
    result = tuple(float(v) for v in values)
    if len(result) != 16 or not all(math.isfinite(v) for v in result):
        raise ValueError("Matrix must contain sixteen finite values")
    return result


def multiply(a, b):
    a, b = matrix(a), matrix(b)
    return tuple(math.fsum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
                 for r in range(4) for c in range(4))


def inverse(values):
    """Partial-pivot Gauss-Jordan inverse, independent of the CDMW affine path."""
    values = matrix(values)
    rows = [[*values[r * 4:r * 4 + 4], *IDENTITY[r * 4:r * 4 + 4]] for r in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) <= 1e-12:
            raise ValueError("Matrix is singular")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for row in range(4):
            if row != col:
                factor = rows[row][col]
                rows[row] = [v - factor * p for v, p in zip(rows[row], rows[col])]
    return matrix(v for row in rows for v in row[4:])


def translation(point):
    if len(point) != 3 or not all(math.isfinite(v) for v in point):
        raise ValueError("Translation must contain three finite values")
    result = list(IDENTITY)
    result[12:15] = point
    return tuple(result)


def transform(point, values):
    values = matrix(values)
    if len(point) != 3 or not all(math.isfinite(v) for v in point):
        raise ValueError("Position must contain three finite values")
    row = (*point, 1.0)
    moved = tuple(math.fsum(row[k] * values[k * 4 + c] for k in range(4)) for c in range(4))
    if abs(moved[3] - 1.0) > 1e-6:
        raise ValueError("Position transform must be affine")
    return moved[:3]


def error(a, b=IDENTITY):
    if len(a) != len(b):
        raise ValueError("Comparison lengths differ")
    return max(abs(x - y) for x, y in zip(a, b))


def distance(a, b):
    return math.sqrt(math.fsum((x - y) ** 2 for x, y in zip(a, b)))


def axis_rotation(axis, degrees):
    if axis not in range(3) or not math.isfinite(degrees):
        raise ValueError("Rotation requires a model axis and finite angle")
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    result = list(IDENTITY)
    u, v = ((1, 2), (2, 0), (0, 1))[axis]
    result[u * 4 + u] = result[v * 4 + v] = c
    result[u * 4 + v], result[v * 4 + u] = s, -s
    return tuple(result)


def rotation_about(point, axis, degrees):
    return multiply(multiply(translation(tuple(-v for v in point)), axis_rotation(axis, degrees)),
                    translation(point))


def determinant3(a):
    a = matrix(a)
    return (a[0] * (a[5] * a[10] - a[6] * a[9])
            - a[1] * (a[4] * a[10] - a[6] * a[8])
            + a[2] * (a[4] * a[9] - a[5] * a[8]))


def parse_pab_records(data):
    if len(data) < 22 or data[:4] != b"PAR ":
        raise ValueError("PAB header is invalid")
    count = struct.unpack_from("<H", data, 20)[0]
    if count != 447:
        raise ValueError("Only the fixed 447-bone PAB is supported")
    rows, offset = [], 22
    for index in range(count):
        if offset + 305 > len(data):
            raise ValueError("PAB record is truncated")
        name_hash, length = struct.unpack_from("<IB", data, offset)
        end = offset + 305 + length
        if not length or end > len(data):
            raise ValueError("PAB name or record is invalid")
        name = data[offset + 5:offset + 5 + length].decode("ascii")
        parent = struct.unpack_from("<i", data, offset + 5 + length)[0]
        if parent < -1 or parent >= count or parent == index:
            raise ValueError("PAB parent is invalid")
        matrices = [matrix(struct.unpack_from("<16f", data, offset + 9 + length + 64 * k))
                    for k in range(4)]
        rows.append({"index": index, "name": name, "hash": name_hash, "parent": parent,
                     "bind": matrices[0], "inverse": matrices[1],
                     "local": matrices[2], "localInverse": matrices[3]})
        offset = end
    if len({r["name"] for r in rows}) != count or len({r["hash"] for r in rows}) != count:
        raise ValueError("PAB names or hashes are ambiguous")
    for row in rows:
        visited, index = set(), row["index"]
        while index >= 0:
            if index in visited:
                raise ValueError("PAB hierarchy contains a cycle")
            visited.add(index)
            index = rows[index]["parent"]
    return rows, offset


def parse_pabc_records(data, bones):
    if len(data) < 20 or data[:4] != b"PAR ":
        raise ValueError("PABC header is invalid")
    count = struct.unpack_from("<I", data, 16)[0]
    if not 0 < count <= len(bones):
        raise ValueError("PABC count is invalid")
    end = 20 + count * 196
    if end > len(data):
        raise ValueError("PABC table is truncated")
    tail = data[end:]
    duplicate = len(tail) == 8 + count * 196
    if duplicate:
        if struct.unpack_from("<I", tail, 4)[0] != count or tail[8:] != data[20:end]:
            raise ValueError("PABC duplicate table differs")
    elif len(tail) != 4:
        raise ValueError("PABC trailing layout is unreviewed")
    lookup = {r["hash"]: r for r in bones}
    rows = []
    for index in range(count):
        offset = 20 + 196 * index
        name_hash = struct.unpack_from("<I", data, offset)[0]
        blocks = tuple(matrix(struct.unpack_from("<16f", data, offset + 4 + 64 * k)) for k in range(3))
        if name_hash not in lookup:
            raise ValueError("PABC record does not resolve to the fixed PAB")
        rows.append({"index": index, "hash": name_hash,
                     "boneIndex": lookup[name_hash]["index"], "blocks": blocks})
    if len({r["hash"] for r in rows}) != count:
        raise ValueError("PABC repeated bone hash is ambiguous")
    return rows, duplicate


def neutral_bind(bind, target):
    """Reproduce only the pinned CDMW paired-row neutral reconciliation."""
    for axes in ((0, 1), (0, 2), (1, 2)):
        aligned = tuple(-v if i // 4 in axes and i % 4 < 3 else v for i, v in enumerate(target))
        if error(aligned, bind) <= 1e-4:
            return aligned, list(axes)
    return target, []


def independently_deform(mesh, palette, matrices):
    result = []
    for part in mesh.submeshes:
        positions = []
        if not len(part.vertices) == len(part.bone_indices) == len(part.bone_weights):
            raise ValueError("PAC skin rows are incomplete")
        for point, slots, weights in zip(part.vertices, part.bone_indices, part.bone_weights):
            if len(slots) != len(weights) or not slots or any(w <= 0 or not math.isfinite(w) for w in weights):
                raise ValueError("PAC skin weights are invalid")
            if any(not 0 <= s < len(palette) for s in slots):
                raise ValueError("PAC palette slot is invalid")
            total = math.fsum(weights)
            moved = [transform(point, matrices[palette[slot]]) for slot in slots]
            positions.append(tuple(math.fsum(p[c] * w / total for p, w in zip(moved, weights)) for c in range(3)))
        result.append(positions)
    return result


def summarize_deformation(mesh, independent, cdmw_positions):
    source = [v for p in mesh.submeshes for v in p.vertices]
    target = [v for p in independent for v in p]
    observed = [v for p in cdmw_positions for v in p]
    if not len(source) == len(target) == len(observed) or not source:
        raise ValueError("Neutral presentation vertex counts differ")
    displacement = [distance(a, b) for a, b in zip(source, target)]
    return {"vertices": len(source), "maximumDisplacementMetres": max(displacement),
            "meanDisplacementMetres": math.fsum(displacement) / len(displacement),
            "maximumIndependentVsCDMWMetres": max(distance(a, b) for a, b in zip(target, observed))}


def signed_face_areas(parts, reflected=False, reverse=False):
    dots = []
    for part in parts:
        for face in part["faces"]:
            face = (face[0], face[2], face[1]) if reverse else face
            points = [part["vertices"][i] for i in face]
            normals = [part["normals"][i] for i in face]
            if reflected:
                points = [(x, y, -z) for x, y, z in points]
                normals = [(x, y, -z) for x, y, z in normals]
            a, b, c = points
            u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            dots.append(math.fsum(cross[i] * normals[0][i] for i in range(3)))
    return {"triangles": len(dots), "minimumAreaDotNormal": min(dots), "maximumAreaDotNormal": max(dots)}


def rigid_seams(parts, joints, neutral_deltas):
    """Sample the actual touching base-cuboid rectangles, including overhangs.

    These face points need not be indexed vertices (head/body have different
    rectangle widths). Rigid weighting makes the affine result valid over the
    entire face. Synthetic equal model-axis rotations are sensitivity examples.
    """
    base = {p["name"]: p for p in parts if p["name"] in native.RIG_CANDIDATE}
    rig = {j["minecraftPart"]: j for j in joints}
    bounds = {name: ([min(v[c] for v in p["vertices"]) for c in range(3)],
                     [max(v[c] for v in p["vertices"]) for c in range(3)]) for name, p in base.items()}
    rows = []
    for a, b in (("head", "body"), ("body", "right_arm"), ("body", "left_arm"),
                 ("body", "right_leg"), ("body", "left_leg")):
        amin, amax = bounds[a]
        bmin, bmax = bounds[b]
        low, high = [max(x, y) for x, y in zip(amin, bmin)], [min(x, y) for x, y in zip(amax, bmax)]
        axes = [c for c in range(3) if abs(high[c] - low[c]) < 1e-7]
        if len(axes) != 1 or any(high[c] < low[c] - 1e-7 for c in range(3)):
            raise ValueError("Classic base parts no longer have the reviewed contact faces")
        normal_axis = axes[0]
        uv_axes = [c for c in range(3) if c != normal_axis]
        points = []
        for u, v in ((0, 0), (0, 1), (1, 0), (1, 1)):
            point = list(low)
            point[uv_axes[0]] = (low, high)[u][uv_axes[0]]
            point[uv_axes[1]] = (low, high)[v][uv_axes[1]]
            points.append(tuple(point))
        ja, jb = rig[a], rig[b]
        simulations = []
        for axis in range(3):
            na, nb = (rotation_about(j["nativePivotMetres"], axis, 30) for j in (ja, jb))
            ma, mb = (rotation_about(j["minecraftPivotMetres"], axis, 30) for j in (ja, jb))
            # Error in the relative separation vector, rather than calling the
            # normal MC rigid-joint articulation itself a deformation error.
            excess = []
            for p in points:
                npa, npb, mpa, mpb = transform(p, na), transform(p, nb), transform(p, ma), transform(p, mb)
                excess.append(distance(tuple(x - y for x, y in zip(npa, npb)), tuple(x - y for x, y in zip(mpa, mpb))))
            simulations.append({"modelAxis": "XYZ"[axis], "degrees": 30,
                                "nativeVsMinecraftSeparationVectorDifferenceMetres": max(excess)})
        rows.append({"parts": [a, b], "contactNormalAxis": "XYZ"[normal_axis],
                     "contactFaceCornersMetres": points,
                     "pabcNeutralMaximumSeparationMetres": max(distance(transform(p, neutral_deltas[ja["pabIndex"]]), transform(p, neutral_deltas[jb["pabIndex"]])) for p in points),
                     "staticRefitSeparationMetres": distance(ja["staticRefitTranslationMetres"], jb["staticRefitTranslationMetres"]),
                     "syntheticEqualModelAxisRotations": simulations})
    return {"interpretation": "Actual neutral touching face samples under rigid weights; synthetic angles quantify pivot sensitivity, not captured Crimson Desert animation",
            "basePartContactFaces": rows, "allCandidateVerticesRigidSingleBone": True,
            "limitation": "Rigid parts cannot smooth skin across joints; native skin/cloth/equipment behavior needs runtime validation"}


def bind_pivots(document, binary):
    skin = document["skins"][0]
    accessor = document["accessors"][skin["inverseBindMatrices"]]
    view = document["bufferViews"][accessor["bufferView"]]
    if (accessor["type"] != "MAT4" or accessor["componentType"] != 5126
            or accessor.get("sparse") or view.get("byteStride") or view["buffer"] != 0
            or accessor["count"] != 6):
        raise ValueError("Steve inverse bind accessor differs from the fixed export")
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    end = start + 6 * 64
    if start < view.get("byteOffset", 0) or end > view.get("byteOffset", 0) + view["byteLength"] or end > len(binary):
        raise ValueError("Steve inverse bind accessor is out of bounds")
    # glTF is column-vector column-major: the same 16 ordered values are the
    # transpose represented as row-vector row-major, without an axis change.
    inverse_binds = [matrix(struct.unpack_from("<16f", binary, start + 64 * i)) for i in range(6)]
    result = {}
    for part, joint, inv_bind in zip(native.RIG_CANDIDATE, skin["joints"], inverse_binds):
        node = document["nodes"][joint]
        if set(node) != {"name", "translation"} or node["name"] != part + "_joint":
            raise ValueError("Steve joint node has an unreviewed transform")
        raw = tuple(node["translation"])
        result[part] = {"unscaledPivot": raw, "pivot": tuple(v * .9375 for v in raw),
                        "rawInverseBind": inv_bind, "sourceIdentityError": error(multiply(translation(raw), inv_bind))}
    if len(skin["joints"]) != 6 or any(r["sourceIdentityError"] > 1e-7 for r in result.values()):
        raise ValueError("Steve inverse bind does not match its source joint")
    return result


def read_fixed(path, digest, snapshot):
    native.check_links(path)
    path = path.resolve()
    if not path.is_file() or not 0 < path.stat().st_size <= FILE_LIMIT:
        raise ValueError("Input file is missing or outside its size bound")
    data = path.read_bytes()
    if native.sha256(data) != digest:
        raise ValueError(f"Fixed input fingerprint differs: {path.name}")
    snapshot[path] = data
    return data


def protect_output(output, inputs):
    output = native.output_directory(output)
    targets = [output / REPORT_NAME, output / (REPORT_NAME + ".tmp"),
               output / "steve-rig-analysis.md", output / "steve-rig-analysis.md.tmp"]
    for target in targets:
        native.check_links(target)
        if target.exists() and not target.is_file():
            raise ValueError("Report output must be a regular file")
        for source in inputs:
            source = source.resolve()
            if (target.resolve() == source or
                    (target.exists() and source.exists() and os.path.samefile(target, source))):
                raise ValueError("Analysis output aliases an input")
    return output


def analyze(native_dir, asset_dir, prefab_dir, source, deps):
    native_dir, asset_dir, prefab_dir = (native.output_directory(p) for p in (native_dir, asset_dir, prefab_dir))
    snapshot = {}
    pab = read_fixed(native_dir / "template" / native.SKELETON, native.TEMPLATE_HASHES[native.SKELETON], snapshot)
    body = read_fixed(native_dir / "template" / native.BODY, native.TEMPLATE_HASHES[native.BODY], snapshot)
    candidate = read_fixed(native_dir / "steve-rig-candidate.pac", CANDIDATE_SHA256, snapshot)
    pabc = read_fixed(native_dir / "template" / native.VARIATION, PABC_SHA256, snapshot)
    prefab = read_fixed(prefab_dir / "template" / PREFAB_PATH, PREFAB_SHA256, snapshot)
    descriptor = read_fixed(prefab_dir / "template" / native.DESCRIPTOR, DESCRIPTOR_SHA256, snapshot)
    mc = {name: read_fixed(asset_dir / name, digest, snapshot) for name, digest in native.STEVE_HASHES.items()}
    native.load_cdmw(source, deps)
    from cdmw.modding.skeleton_parser import parse_pab
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.skeleton_variation_parser import (
        parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices, _deform_positions,
    )
    import prepare_steve_prefab as prefab_tool
    skeleton = parse_pab(pab, native.SKELETON)
    bones, tail = parse_pab_records(pab)
    for actual, row in zip(skeleton.bones, bones):
        if (actual.index != row["index"] or actual.name != row["name"] or actual.name_hash != row["hash"]
                or actual.parent_index != row["parent"] or actual.bind_matrix != row["bind"]
                or actual.inv_bind_matrix != row["inverse"] or actual.local_bind_matrix != row["local"]
                or actual.inv_local_bind_matrix != row["localInverse"]):
            raise ValueError("Independent PAB records differ from CDMW")
    if skeleton.bone_count != len(bones) or skeleton.tail_offset != tail or skeleton.parser_mode != "fixed":
        raise ValueError("Independent PAB boundaries differ from CDMW")
    variation = parse_pabc_skeleton_variation(pabc, native.VARIATION, skeleton=skeleton)
    records, duplicate = parse_pabc_records(pabc, bones)
    if variation.record_count != len(records) or variation.duplicate_record_table != duplicate:
        raise ValueError("Independent PABC boundaries differ from CDMW")
    for actual, row in zip(variation.records, records):
        if (actual.index != row["index"] or actual.bone_hash != row["hash"]
                or actual.bone_index != row["boneIndex"] or actual.matrix_blocks != row["blocks"]):
            raise ValueError("Independent PABC records differ from CDMW")
    palette = resolve_pac_bone_palette(body, skeleton)
    if resolve_pac_bone_palette(candidate, skeleton) != palette:
        raise ValueError("Steve and donor bone palettes differ")
    original, steve = parse_pac(body, native.BODY), parse_pac(candidate, native.BODY)
    native.validate_rig(skeleton, original, palette)
    native.validate_rig(skeleton, steve, palette)
    if any(len(slots) != 1 or weights != (1.0,) and weights != [1.0]
           for p in steve.submeshes for slots, weights in zip(p.bone_indices, p.bone_weights)):
        raise ValueError("Steve candidate no longer uses one rigid bone per vertex")
    parts = native.steve_geometry(asset_dir)
    document = json.loads(mc["steve.gltf"])
    mc_pivots = bind_pivots(document, mc["steve.bin"])
    targets = [r["bind"] for r in bones]
    pabc_lookup, reconciled = {}, []
    for row in records:
        index = row["boneIndex"]
        targets[index], axes = neutral_bind(bones[index]["bind"], row["blocks"][0])
        pabc_lookup[index] = {"recordIndex": row["index"], "pairedRowsReconciled": axes,
                              "rawBindMaximumDifference": error(row["blocks"][0], bones[index]["bind"]),
                              "neutralBind": targets[index]}
        if axes:
            reconciled.append(index)
    deltas = [multiply(r["inverse"], targets[i]) for i, r in enumerate(bones)]
    cdmw_targets = [b.bind_matrix for b in skeleton.bones]
    for row in variation.records:
        cdmw_targets[row.bone_index] = _neutral_variation_bind_matrix(
            cdmw_targets[row.bone_index], row.matrix_blocks[0])
    cdmw_deltas = _skin_matrices(skeleton.bones, cdmw_targets)
    if max(error(a, b) for a, b in zip(deltas, cdmw_deltas)) > 1e-12:
        raise ValueError("Independent neutral delta matrices differ from CDMW")
    presentations = {}
    for label, mesh in (("nativeDonor", original), ("steveCandidate", steve)):
        independent = independently_deform(mesh, palette, deltas)
        cdmw_positions = [_deform_positions(part, palette, cdmw_deltas) for part in mesh.submeshes]
        presentations[label] = summarize_deformation(mesh, independent, cdmw_positions)
        if presentations[label]["maximumIndependentVsCDMWMetres"] > 1e-7:
            raise ValueError("Independent neutral skinning differs from CDMW")
    lookup = {r["name"]: r for r in bones}
    mapping = native.rig_candidates(skeleton, palette)
    joints = []
    shifted = []
    for name, entry in mapping.items():
        bone = bones[entry["pabIndex"]]
        mc_pivot, native_pivot = mc_pivots[name]["pivot"], bone["bind"][12:15]
        part_positions = [v for p in parts if p["parent"] == name for v in p["vertices"]]
        offset = tuple(n - m for m, n in zip(mc_pivot, native_pivot))
        shifted.extend(tuple(v[i] + offset[i] for i in range(3)) for v in part_positions)
        # Translation-only change of model-axis pivot. Full bind-frame conversion
        # is also retained separately; neither is an implemented runtime hook.
        frame = translation(offset)
        full_frame = multiply(inverse(translation(mc_pivot)), bone["bind"])
        simulations = []
        for axis in range(3):
            donor_delta = rotation_about(native_pivot, axis, 30)
            desired = rotation_about(mc_pivot, axis, 30)
            retargeted = multiply(multiply(frame, donor_delta), inverse(frame))
            simulations.append({"modelAxis": "XYZ"[axis], "degrees": 30,
                                "maximumUnretargetedVertexDifferenceMetres": max(distance(transform(v, donor_delta), transform(v, desired)) for v in part_positions),
                                "retargetMatrixMaximumError": error(retargeted, desired),
                                "retargetVertexMaximumErrorMetres": max(distance(transform(v, retargeted), transform(v, desired)) for v in part_positions)})
        weights = []
        for part in original.submeshes:
            for point, slots, row_weights in zip(part.vertices, part.bone_indices, part.bone_weights):
                weight = math.fsum(w for slot, w in zip(slots, row_weights) if palette[slot] == bone["index"])
                if weight > 0:
                    weights.append((point, weight))
        total = math.fsum(w for _, w in weights)
        joints.append({"minecraftPart": name, **entry,
                       "parentName": bones[bone["parent"]]["name"] if bone["parent"] >= 0 else None,
                       "minecraftPivotMetres": mc_pivot, "nativePivotMetres": native_pivot,
                       "staticRefitTranslationMetres": offset, "pivotDistanceMetres": distance(mc_pivot, native_pivot),
                       "nativeGlobalBindRowMajor": bone["bind"], "nativeGlobalInverseBindRowMajor": bone["inverse"],
                       "independentInverseMaximumError": error(inverse(bone["bind"]), bone["inverse"]),
                       "nativeLocalBindRowMajor": bone["local"], "minecraftModelInverseBindRowMajor": inverse(translation(mc_pivot)),
                       "minecraftSourceInverseIdentityError": mc_pivots[name]["sourceIdentityError"],
                       "pabc": pabc_lookup.get(bone["index"]),
                       "donorWeightedVertexCount": len(weights),
                       "donorWeightedCentroidMetres": tuple(math.fsum(v[c] * w for v, w in weights) / total for c in range(3)),
                       "pivotRetargetFrameRowMajor": frame, "fullBindRetargetFrameRowMajor": full_frame,
                       "fullFrameNeutralIdentityError": error(multiply(full_frame, inverse(full_frame))),
                       "syntheticModelAxisRotations": simulations})
    pdb = prefab_tool.audit_prefab(prefab, native.BODY)
    prefab_tool.audit_descriptor(descriptor)
    if pdb.root_members != ("_components",) or pdb.root_numbers:
        raise ValueError("Native nude prefab contains unexpected root transforms")
    for obj in pdb.objects:
        if [(x.name, x.type_name, struct.unpack("<f", x.raw)[0]) for x in obj.numbers] != [("_shrinkMaskDistance", "float", struct.unpack("<f", b"\xcd\xcc\x4c\x3d")[0])]:
            raise ValueError("Native nude prefab has an unreviewed numeric field")
    native_forward = []
    for label, a, b in (("rightToe", "Bip01 R Toe0", "Bip01 R Toe0Nub"),
                        ("leftToe", "Bip01 L Toe0", "Bip01 L Toe0Nub"),
                        ("leftEyeFromHead", "Bip01 Head", "B_Eyeball_L"),
                        ("rightEyeFromHead", "Bip01 Head", "B_Eyeball_R")):
        start, end = lookup[a]["bind"][12:15], lookup[b]["bind"][12:15]
        native_forward.append({"evidence": label, "fromBone": a, "toBone": b,
                               "fromPositionMetres": start, "toPositionMetres": end,
                               "deltaMetres": tuple(y - x for x, y in zip(start, end))})
    left_right = []
    for left, right, lb, rb in (("left_arm", "right_arm", "Bip01 L UpArmTwist", "Bip01 R UpArmTwist"),
                               ("left_leg", "right_leg", "Bip01 L Thigh", "Bip01 R Thigh")):
        left_right.append({"pair": [left, right], "minecraftX": [mc_pivots[left]["pivot"][0], mc_pivots[right]["pivot"][0]],
                           "nativeX": [lookup[lb]["bind"][12], lookup[rb]["bind"][12]]})
    left_right.append({"pair": ["leftEye", "rightEye"],
                       "nativeX": [lookup["B_Eyeball_L"]["bind"][12], lookup["B_Eyeball_R"]["bind"][12]]})
    if any(r["deltaMetres"][2] >= -.06 for r in native_forward) or any(r["nativeX"][0] <= 0 or r["nativeX"][1] >= 0 for r in left_right):
        raise ValueError("Pinned anatomical coordinate evidence changed")
    reflection = list(IDENTITY)
    reflection[10] = -1.0
    reflected = signed_face_areas(parts, True, True)
    unreflected = signed_face_areas(parts)
    wrong_winding = signed_face_areas(parts, True, False)
    if unreflected["minimumAreaDotNormal"] <= 0 or reflected["minimumAreaDotNormal"] <= 0 or wrong_winding["maximumAreaDotNormal"] >= 0:
        raise ValueError("Reflection/winding evidence is inconsistent")
    same_mc = mc_pivots["head"]["pivot"] == mc_pivots["body"]["pivot"]
    distinct_native = distance(lookup["Bip01 Head"]["bind"][12:15], lookup["Bip01 Spine_Sub"]["bind"][12:15])
    report = {
        "schemaVersion": 1, "supportedExeSha256": native.EXE_SHA256,
        "cdmw": {"commit": native.CDMW_COMMIT, "pythonSourceTreeSha256": native.CDMW_SOURCE_SHA256},
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): native.sha256(data) for path, data in sorted(snapshot.items())},
        "matrixConvention": "Native PAB/PAC: row-vector, row-major; translation indices 12..14; local * parentGlobal = global",
        "units": "Metres in the imported native model and scaled MC model; one MC pixel is 0.9375/16 metres",
        "pab": {"bones": len(bones), "independentRecordReaderMatchesCDMW": True,
                "maximumBindTimesInverseIdentityError": max(error(multiply(r["bind"], r["inverse"])) for r in bones),
                "maximumLocalTimesParentVsGlobalError": max(error(multiply(r["local"], bones[r["parent"]]["bind"] if r["parent"] >= 0 else IDENTITY), r["bind"]) for r in bones),
                "maximumLocalTimesLocalInverseIdentityError": max(error(multiply(r["local"], r["localInverse"])) for r in bones)},
        "pabc": {"records": len(records), "matchedRecords": variation.matched_record_count,
                 "exactDuplicateTable": duplicate, "uncoveredBoneIndices": sorted(set(range(len(bones))) - set(pabc_lookup)),
                 "pairedRowsReconciledBoneIndices": reconciled,
                 "interpretation": "Only block 0 used by pinned CDMW neutral presentation; other blocks remain uninterpreted"},
        "neutralPresentation": presentations, "joints": joints,
        "rigidSeams": rigid_seams(parts, joints, deltas),
        "coordinateContract": {
            "minecraft": document["extras"]["coordinateSystem"], "nativeForwardInference": "Anatomical forward -Z from both eyes and both toe chains",
            "nativeForwardEvidence": native_forward, "leftRightEvidence": left_right,
            "nativePrefabRootMembers": pdb.root_members,
            "nativePrefabNumericMembers": [{"object": o.name, "members": [x.name for x in o.numbers]} for o in pdb.objects],
            "serializedPrefabOrientationCompensation": False,
            "currentConversionOrientationCompensation": False,
            "currentConversion": "prepare_native_steve.steve_geometry/make_candidate directly copy scaled model positions/normals; V-only UV flip; CDMW glTF importer is not invoked",
            "cdmwImporter": "scene_gltf_import applies declared node transforms and jointWorld * inverseBind; no native-anatomical front-axis conversion is supplied by this pipeline",
            "minimalStaticOrientationCandidate": {"positionTransformRowMajor": reflection, "determinant": determinant3(reflection),
                "positions": "z = -z", "normals": "nz = -nz", "faces": "(a,b,c) -> (a,c,b) exactly once",
                "tangents": "Regenerate from reflected geometry and unchanged face UVs; do not reuse old handedness",
                "jointSemanticMapping": "Preserve left/right bone names and X coordinates",
                "generated": False},
            "y180Alternative": {"determinant": determinant3(axis_rotation(1, 180)),
                "preservesLeftRightX": False, "reason": "Maps +Z to -Z but also positive-X left limbs to negative-X native right limbs"},
            "windingExperiment": {"source": unreflected, "zReflectionWithoutWindingFlip": wrong_winding, "zReflectionWithWindingFlip": reflected},
            "remainingUnknown": "Controlled actor parent transforms/defaults and actual renderer culling/tangent acceptance have not been read or verified in game"},
        "pivotConstraint": {"minecraftHeadBodyCoincident": same_mc,
            "nativeHeadBodyDistanceMetres": distinct_native, "oneGlobalAffineCanMatchSixPivots": not (same_mc and distinct_native > 1e-6),
            "proof": "A deterministic affine transform maps one coincident source point to one point, but native head and body require two distinct points"},
        "staticPerPartRefit": {"generated": False,
            "translatedAssembledBoundsMetres": {"min": [min(v[c] for v in shifted) for c in range(3)], "max": [max(v[c] for v in shifted) for c in range(3)]},
            "effect": "Moves each rigid part to the native pivot, changing assembled proportions and feet height; cannot preserve the classic Steve assembly"},
        "runtimeRetargetCandidate": {"implemented": False, "syntheticEvidenceOnly": True,
            "formulaRowVector": "F = inverse(MC_bind) * Native_bind; D_native = inverse(Native_bind) * Native_pose; D_mc = F * D_native * inverse(F); MC_pose = Native_pose * inverse(F)",
            "geometry": "Can retain classic MC vertices and pivots if a verified runtime/controller can supply converted joint poses; requires coherent parent/local reconstruction",
            "warning": "Replacing only native inverse binds with MC inverse binds does not preserve the native neutral pose",
            "nextImplementation": "First make a separate Z-reflected PAC candidate with normals/winding/tangents and native metadata preserved, then validate it before any character override. For motion, obtain verified native pose/controller and equipment socket contracts before introducing per-joint retargeting."},
        "integration": {"adjustedAssetsGenerated": False, "installedInGame": False, "engineNeutralPoseVerified": False,
                        "engineAnimationVerified": False, "controlledCharacterVerified": False, "equipmentVerified": False}}
    return report, snapshot


def markdown(report):
    lines = ["# Steve/native rig evidence", "",
             "Offline evidence only. No PAC/PAB edits or game access were performed.", "",
             "The native anatomical model faces -Z while the official Steve export faces +Z. Both keep left limbs at positive X.",
             "A minimal separate orientation candidate reflects Z, reflects normal Z, reverses each triangle once, and regenerates tangents. Y180 changes left/right X.", "",
             "| MC part | Native bone | MC pivot (m) | Native pivot (m) | Distance (m) |", "| --- | --- | --- | --- | --- |"]
    for j in report["joints"]:
        point = lambda p: ", ".join(f"{v:.6f}" for v in p)
        lines.append(f"| {j['minecraftPart']} | {j['boneName']} | {point(j['minecraftPivotMetres'])} | {point(j['nativePivotMetres'])} | {j['pivotDistanceMetres']:.6f} |")
    lines.extend(["", "MC head/body pivots coincide; native pivots differ by " + f"{report['pivotConstraint']['nativeHeadBodyDistanceMetres']:.6f} m. A single global transform cannot align all joints.",
                  "Per-part static refit changes the assembly and feet height. Preserving the classic mesh needs per-joint animation retargeting through a verified pose/controller interface.", "",
                  "The report contains full native bind/inverse matrices, independently checked neutral skinning, PABC coverage, and synthetic 30-degree pivot retarget results.",
                  "The body prefab serializes no orientation transform. Controlled actor parent transforms and renderer behavior remain unverified.", "",
                  "Next concrete asset step: a separate Z-reflected PAC preserving native descriptors/palette/LODs, with correct winding and regenerated tangents. It must pass offline checks before any installation."])
    return ("\n".join(lines) + "\n").encode("utf-8")


def publish(output, report, snapshot):
    output = protect_output(output, snapshot)
    for path, expected in snapshot.items():
        native.check_links(path)
        if path.stat().st_size != len(expected) or path.read_bytes() != expected:
            raise ValueError("Input changed during analysis")
    output.mkdir(parents=True, exist_ok=True)
    outputs = {REPORT_NAME: (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"),
               "steve-rig-analysis.md": markdown(report)}
    protect_output(output, snapshot)
    for name, data in outputs.items():
        temporary = output / (name + ".tmp")
        temporary.write_bytes(data)
        protect_output(output, snapshot)
        temporary.replace(output / name)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-steve", type=Path, default=ROOT / "build/native-steve")
    parser.add_argument("--steve-asset", type=Path, default=ROOT / "build/steve-1.21.1")
    parser.add_argument("--prefab", type=Path, default=ROOT / "build/steve-prefab")
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protect_output(args.output, [])
    report, snapshot = analyze(args.native_steve, args.steve_asset, args.prefab, args.cdmw_source, args.deps)
    output = publish(args.output, report, snapshot)
    print(json.dumps({"output": str(output), "bones": report["pab"]["bones"], "joints": len(report["joints"]),
                      "pabcRecords": report["pabc"]["records"], "neutralPresentation": report["neutralPresentation"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
