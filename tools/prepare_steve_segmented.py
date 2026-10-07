"""Build an independent offline Steve limb-skin candidate; never install it.

Keep the classic surface/UVs and the verified forward reflection. Add coplanar
surface rings at real native elbow/wrist/knee/ankle bind heights. Head and torso
remain the earlier rigid candidate. Synthetic deformation is not live animation.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct

import prepare_steve_orientation as orientation

native, rig, prefab, material = orientation.native, orientation.rig, orientation.prefab, orientation.material
ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-segmented"
REPORT_NAME = "steve-segmented-report.json"
ORIENTATION_REPORT_SHA256 = "368bc03aa89f6d6eeb6be8d755488d48a8ee88907c3e50fffa711e8bc5949892"
ORIENTATION_PAC_SHA256 = "8f7b32db6063b7cc8ec71278a8ede09a9e375c2dfd80dedef13283ef77cc0539"
HALF_BAND = .9375 / 32  # Total transition width = one official renderer-scaled MC pixel.
SEGMENTS = {
    "left_arm": (("Bip01 L UpArmTwist", 133, 51), ("Bip01 L Forearm_sub", 349, 92), ("Bip01 L Hand", 348, 82)),
    "right_arm": (("Bip01 R UpArmTwist", 138, 56), ("Bip01 R Forearm_sub", 356, 100), ("Bip01 R Hand", 355, 78)),
    "left_leg": (("Bip01 L Thigh", 18, 176), ("Bip01 L Calf_Sub", 54, 161), ("Bip01 L Foot", 53, 160)),
    "right_leg": (("Bip01 R Thigh", 17, 138), ("Bip01 R Calf_Sub", 48, 140), ("Bip01 R Foot", 46, 144)),
}


def load_inputs(report_path):
    report_path = native.output_directory(report_path)
    snapshot = {}
    report = prefab.strict_json(rig.read_fixed(report_path, ORIENTATION_REPORT_SHA256, snapshot))
    if (report.get("variant") != "steve-native-forward-z-reflection"
            or report.get("rigInputs") != orientation.fixed_rig_inputs()
            or len(report.get("candidateResources", [])) != 7
            or not report.get("integration") or any(v is not False for v in report["integration"].values())):
        raise ValueError("Source is not the fixed offline orientation candidate")
    files = {}
    for relative, digest in report["files"].items():
        path = native.output_directory(report_path.parent / relative)
        if not path.is_relative_to(report_path.parent):
            raise ValueError("Source resource escapes its directory")
        files[relative] = rig.read_fixed(path, digest, snapshot)
    for relative, digest in report["rigInputs"].items():
        rig.read_fixed(native.output_directory(ROOT / relative), digest, snapshot)
    if native.sha256(files["resources/" + material.PAC_PATH]) != ORIENTATION_PAC_SHA256:
        raise ValueError("Source PAC differs from the fixed forward candidate")
    return report, files, snapshot


def ancestry(bones, index):
    result = []
    while index >= 0:
        if index in result:
            raise ValueError("Cyclic skeleton")
        result.append(index)
        index = bones[index]["parent"]
    return result


def bind_plan(pab, donor, pabc):
    from cdmw.modding.skeleton_parser import parse_pab
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    bones, _ = rig.parse_pab_records(pab)
    skeleton = parse_pab(pab, native.SKELETON)
    if any(b.name != r["name"] or rig.error(b.bind_matrix, r["bind"]) > 1e-12 for b, r in zip(skeleton.bones, bones)):
        raise ValueError("Independent PAB parse differs from fixed CDMW")
    palette = resolve_pac_bone_palette(donor, skeleton)
    mesh = parse_pac(donor, native.BODY)
    native.validate_rig(skeleton, mesh, palette)
    records, _ = rig.parse_pabc_records(pabc, bones)
    lookup = {b["name"]: b for b in bones}
    neutral = {row["boneIndex"]: rig.neutral_bind(bones[row["boneIndex"]]["bind"], row["blocks"][0])[0] for row in records}
    plan = {}
    for part, selected in SEGMENTS.items():
        side = "L" if part.startswith("left") else "R"
        limb = "arm" if part.endswith("arm") else "leg"
        middle = lookup[f"Bip01 {side} " + ("Forearm" if limb == "arm" else "Calf")]
        end = lookup[selected[2][0]]
        if middle["index"] in palette:
            raise ValueError("This candidate requires the reviewed driver/helper palette layout")
        entries = []
        for name, index, slot in selected:
            b = lookup[name]
            if b["index"] != index or palette[slot] != index or palette.count(index) != 1 or index not in neutral:
                raise ValueError("Segment bone identity, palette slot or neutral coverage differs")
            if not any(slot in row for p in mesh.submeshes for row in p.bone_indices):
                raise ValueError("Segment bone has no actual donor skin influence")
            bind_error = max(rig.error(rig.multiply(b["bind"], b["inverse"])), rig.error(rig.multiply(b["inverse"], b["bind"])))
            if bind_error > 1e-6:
                raise ValueError("Segment inverse bind is not an inverse")
            entries.append({"boneName": name, "pabIndex": index, "paletteSlot": slot,
                            "parent": bones[b["parent"]]["name"], "bindRowMajor": b["bind"],
                            "inverseBindRowMajor": b["inverse"], "bindInverseError": bind_error})
        if (middle["index"] not in ancestry(bones, selected[1][1])
                or middle["index"] not in ancestry(bones, selected[2][1])
                or end["index"] in ancestry(bones, selected[1][1])):
            raise ValueError("Lower helper/endpoint are not the reviewed distinct native branches")
        heights = [middle["bind"][13], end["bind"][13]]
        if heights[0] - heights[1] <= HALF_BAND * 2:
            raise ValueError("Native bend bands overlap")
        plan[part] = {"bones": entries, "jointDrivers": [middle["name"], end["name"]],
                      "jointBindPositions": [middle["bind"][12:15], end["bind"][12:15]],
                      "jointY": heights, "halfBandMetres": HALF_BAND,
                      "cutsY": sorted(y + d for y in heights for d in (-HALF_BAND, 0., HALF_BAND))}
    deltas = [rig.multiply(b["inverse"], neutral.get(b["index"], b["bind"])) for b in bones]
    return bones, skeleton, palette, plan, deltas


def weights_at(y, plan):
    slots = [b["paletteSlot"] for b in plan["bones"]]
    for index, centre in enumerate(plan["jointY"]):
        if y >= centre + HALF_BAND - 1e-10:
            return (slots[index],), (1.,)
        if y > centre - HALF_BAND + 1e-10:
            lower = .5 if abs(y - centre) < 1e-10 else (centre + HALF_BAND - y) / (2 * HALF_BAND)
            return (slots[index], slots[index + 1]), (1 - lower, lower)
    return (slots[-1],), (1.,)


def clip_y(polygon, height, above):
    """Clip one original face, carrying exact affine position/UV interpolation."""
    result = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ina = a[0][1] >= height if above else a[0][1] <= height
        inb = b[0][1] >= height if above else b[0][1] <= height
        if ina:
            result.append(a)
        if ina != inb:
            t = (height - a[0][1]) / (b[0][1] - a[0][1])
            point = tuple(height if i == 1 else a[0][i] + t * (b[0][i] - a[0][i]) for i in range(3))
            uv = tuple(x + t * (y - x) for x, y in zip(a[1], b[1]))
            result.append((point, uv))
    # Cuts are strictly interior to each source vertical face; no degenerate caps.
    return result


def author_parts(parts, plan, mapping):
    result = []
    for source in parts:
        if len(source["vertices"]) != 24 or source["faces"] != [f for k in range(0, 24, 4) for f in ((k, k + 1, k + 2), (k, k + 2, k + 3))]:
            raise ValueError("Only six original classic cuboid faces are supported")
        parent = source["parent"]
        cuts = plan[parent]["cutsY"] if parent in plan else []
        low, high = min(v[1] for v in source["vertices"]), max(v[1] for v in source["vertices"])
        if cuts and not low < cuts[0] < cuts[-1] < high:
            raise ValueError("Native articulation cuts lie outside the classic limb")
        target = {"name": source["name"], "parent": parent, "vertices": [], "normals": [], "uvs": [],
                  "faces": [], "bone_indices": [], "bone_weights": [], "sourceQuad": []}
        for start in range(0, 24, 4):
            # Reflection requires exactly one winding reversal; native UV flips V.
            order = [start, start + 3, start + 2, start + 1]
            polygon = [((source["vertices"][i][0], source["vertices"][i][1], -source["vertices"][i][2]),
                        (source["uvs"][i][0], 1 - source["uvs"][i][1])) for i in order]
            n = source["normals"][start]
            normal = (n[0], n[1], -n[2])
            face_low, face_high = min(p[0][1] for p in polygon), max(p[0][1] for p in polygon)
            inside = [cut for cut in cuts if face_low < cut < face_high]
            bands = list(zip([face_low] + inside, inside + [face_high])) if inside else [(face_low, face_high)]
            for lower, upper in bands:
                clipped = polygon if not inside else clip_y(clip_y(polygon, lower, True), upper, False)
                # Remove adjacent duplicates introduced at an existing source corner.
                unique = []
                for item in clipped:
                    if not unique or item != unique[-1]:
                        unique.append(item)
                if len(unique) > 1 and unique[0] == unique[-1]:
                    unique.pop()
                if len(unique) != 4:
                    raise ValueError("A classic face strip is not a nondegenerate quad")
                base = len(target["vertices"])
                for point, uv in unique:
                    slots, weights = weights_at(point[1], plan[parent]) if parent in plan else ((mapping[parent]["paletteSlot"],), (1.,))
                    for key, value in (("vertices", point), ("normals", normal), ("uvs", uv), ("bone_indices", slots), ("bone_weights", weights), ("sourceQuad", start // 4)):
                        target[key].append(value)
                target["faces"].extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
        result.append(target)
    return result


def parse_lods(payload, donor):
    from cdmw.modding.mesh_parser import parse_pac, _parse_par_sections, _parse_pac_geometry_section
    descriptors, count = native.validate_runtime_descriptors(donor, payload, parse_pac(donor, native.BODY))
    if count != 4 or len(descriptors) != 3:
        raise ValueError("Native descriptor/LOD set changed")
    levels = sorted((count - s["index"], _parse_pac_geometry_section(payload, native.BODY, descriptors, s, count - s["index"]))
                    for s in _parse_par_sections(payload) if 1 <= s["index"] <= count)
    if [lod for lod, _ in levels] != list(range(4)):
        raise ValueError("Native LOD set is incomplete")
    return levels


def pack_frame(data, offset, v, sign):
    # Same independently evidenced V lanes as orientation; the authored normal is
    # already reflected, so preserve bit30 rather than reflecting it a second time.
    lane = max(0, min(32767, round((v[0] + 1) * 16383.5))) * (-1 if v[2] < 0 else 1)
    word = struct.unpack_from("<I", data, offset + 16)[0] & ~0x800003FF
    word |= max(0, min(1023, round((v[1] + 1) * 511.5)))
    if sign > 0:
        word |= 0x80000000
    struct.pack_into("<h", data, offset + 6, lane)
    struct.pack_into("<I", data, offset + 16, word)


def make_pac(donor, parts):
    from cdmw.modding.mesh_parser import parse_pac
    from cdmw.modding.mesh_pac_builder import _build_pac_full_rebuild
    original = parse_pac(donor, native.BODY)
    working = copy.deepcopy(original)
    if len(working.submeshes) != 3:
        raise ValueError("Native donor draw slots differ")
    channels = ("vertices", "normals", "uvs", "faces", "bone_indices", "bone_weights", "source_vertex_map")
    for submesh in working.submeshes:
        for channel in channels:
            setattr(submesh, channel, [])
        submesh.clean_donor_shading_records = True
    ranges = []
    for part in parts:
        slot = 0 if part["parent"] == "head" else 2
        submesh = working.submeshes[slot]
        base = len(submesh.vertices)
        first_face = len(submesh.faces)
        for channel in ("vertices", "normals", "uvs", "bone_indices", "bone_weights"):
            getattr(submesh, channel).extend(part[channel])
        submesh.faces.extend(tuple(base + i for i in face) for face in part["faces"])
        ranges.append({"part": part["name"], "logicalPart": part["parent"], "nativeDrawSlot": slot,
                       "firstVertex": base, "vertexCount": len(part["vertices"]),
                       "firstFace": first_face, "faceCount": len(part["faces"])})
    payload = native.keep_complete_geometry_at_all_lods(_build_pac_full_rebuild(original, working, donor, preserve_runtime_abi=True), donor)
    mutable = bytearray(payload)
    for _, mesh in parse_lods(payload, donor):
        for part in mesh.submeshes:
            frames = orientation.vertex_frames(part.vertices, part.normals, part.uvs, part.faces)
            for offset, frame in zip(part.source_vertex_offsets, frames):
                pack_frame(mutable, offset, *frame)
    payload = bytes(mutable)
    maximum_position, maximum_uv, maximum_weight, minimum_normal = 0., 0., 0., 1.
    for _, mesh in parse_lods(payload, donor):
        expected = [p for p in working.submeshes if p.vertices]
        if len(mesh.submeshes) != len(expected):
            raise ValueError("Candidate revived an empty draw slot")
        for wanted, actual in zip(expected, mesh.submeshes):
            if wanted.name != actual.name or wanted.faces != actual.faces or len(wanted.vertices) != len(actual.vertices):
                raise ValueError("Candidate topology/order changed during PAC encoding")
            for i, (a, b) in enumerate(zip(wanted.vertices, actual.vertices)):
                maximum_position = max(maximum_position, rig.distance(a, b))
                maximum_uv = max(maximum_uv, max(abs(x - y) for x, y in zip(wanted.uvs[i], actual.uvs[i])))
                minimum_normal = min(minimum_normal, orientation.dot(wanted.normals[i], actual.normals[i]))
                w, found = dict(zip(wanted.bone_indices[i], wanted.bone_weights[i])), dict(zip(actual.bone_indices[i], actual.bone_weights[i]))
                if set(w) != set(found) or abs(sum(found.values()) - 1) > 1e-12:
                    raise ValueError("Candidate gained/lost a skin influence")
                maximum_weight = max(maximum_weight, max(abs(w[k] - found[k]) for k in w))
    if maximum_position > .0001 or maximum_uv > .0005 or maximum_weight > 1 / 255 or minimum_normal < .999:
        raise ValueError("PAC position/UV/skin/normal roundtrip exceeds its bounds")
    return payload, ranges, {"maximumPositionErrorMetres": maximum_position, "maximumUVError": maximum_uv,
                             "maximumWeightQuantizationError": maximum_weight, "minimumNormalDot": minimum_normal}


def motion_audit(mesh, source_mesh, bones, palette, neutral, plan):
    rest = [rig.multiply(b["inverse"], b["bind"]) for b in bones]
    def maximum_displacement(matrices):
        moved = rig.independently_deform(mesh, palette, matrices)
        return max(rig.distance(v, p) for sub, points in zip(mesh.submeshes, moved) for v, p in zip(sub.vertices, points))
    rest_error, neutral_error = maximum_displacement(rest), maximum_displacement(neutral)
    if rest_error > 1e-6 or neutral_error > .00001:
        raise ValueError("Rest/neutral matrices deform the classic static surface")
    lookup = {b["name"]: b for b in bones}
    chains = {b["index"]: ancestry(bones, b["index"]) for b in bones}
    samples, anchors = [], []
    for part, row in plan.items():
        for driver in row["jointDrivers"]:
            b = lookup[driver]
            descendants = {i for i, chain in chains.items() if b["index"] in chain}
            old_count = sum(any(palette[s] in descendants for s in slots) for sub in source_mesh.submeshes for slots in sub.bone_indices)
            for axis in range(3):
                delta = rig.rotation_about(b["bind"][12:15], axis, 30)
                matrices = [delta if i in descendants else rig.IDENTITY for i in range(len(bones))]
                positions = rig.independently_deform(mesh, palette, matrices)
                distances = [rig.distance(v, p) for sub, points in zip(mesh.submeshes, positions) for v, p in zip(sub.vertices, points)]
                count = sum(d > 1e-6 for d in distances)
                if not count or old_count:
                    raise ValueError("New distal branch did not add the expected motion response")
                samples.append({"part": part, "driver": driver, "axis": "XYZ"[axis], "syntheticDegrees": 30,
                                "sourceAffectedVertices": old_count, "candidateMovedVertices": count,
                                "maximumDisplacementMetres": max(distances)})
        if part.endswith("arm"):
            side = "L" if part.startswith("left") else "R"
            anchor, hand = lookup["Bip_Weapon_" + side], lookup["Bip01 " + side + " Hand"]
            point = anchor["bind"][12:15]
            slots, weights = weights_at(point[1], row)
            if anchor["parent"] != hand["index"] or slots != (row["bones"][2]["paletteSlot"],) or weights != (1.,):
                raise ValueError("Named weapon bind anchor does not lie in the Hand-only region")
            anchors.append({"boneName": anchor["name"], "handBone": hand["name"], "bindPosition": point,
                            "handLocalPosition": rig.transform(point, hand["inverse"]), "handOnlyRegion": True,
                            "actualEquipmentSocketVerified": False})
    return {"bindRestMaximumDisplacementMetres": rest_error, "pabcNeutralMaximumDisplacementMetres": neutral_error,
            "syntheticRotations": samples, "namedWeaponAnchors": anchors, "liveAnimationVerified": False}


def prepare(source_report_path, output, source, deps):
    source_dirs = [source_report_path.parent, source, deps, ROOT / "build/native-steve", ROOT / "build/steve-1.21.1"]
    output = orientation.preflight(output, source_dirs)
    source_report, files, snapshot = load_inputs(source_report_path)
    provenance = native.load_cdmw(source, deps)
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.mesh_pac_builder import build_pac
    donor, pab = files["template/" + native.BODY], files["template/" + native.SKELETON]
    pabc = snapshot[ROOT / ("build/native-steve/template/" + native.VARIATION)]
    bones, skeleton, palette, plan, neutral = bind_plan(pab, donor, pabc)
    source_pac = files["resources/" + material.PAC_PATH]
    source_mesh = parse_pac(source_pac, native.BODY)
    if build_pac(source_mesh, source_pac) != source_pac or resolve_pac_bone_palette(source_pac, skeleton) != palette:
        raise ValueError("Fixed source does not roundtrip or preserve native palette")
    mapping = native.rig_candidates(skeleton, palette)
    authored = author_parts(native.steve_geometry(ROOT / "build/steve-1.21.1"), plan, mapping)
    candidate, ranges, audit = make_pac(donor, authored)
    mesh = parse_pac(candidate, native.BODY)
    if resolve_pac_bone_palette(candidate, skeleton) != palette or build_pac(mesh, candidate) != candidate:
        raise ValueError("Segment candidate palette or no-edit rebuild differs")
    audit.update({"vertices": mesh.total_vertices, "triangles": mesh.total_faces,
                  "storedDrawDescriptors": 3, "activeDrawDescriptors": 2, "verifiedLods": [0, 1, 2, 3],
                  "nativePaletteUnchanged": True, "sourcePacSha256": native.sha256(source_pac),
                  "candidatePacSha256": native.sha256(candidate),
                  "packedFrameContract": orientation.donor_contract(donor, parse_pac(donor, native.BODY)),
                  "motion": motion_audit(mesh, source_mesh, bones, palette, neutral, plan)})
    files["resources/" + material.PAC_PATH] = candidate
    rows = copy.deepcopy(source_report["candidateResources"])
    for row in rows:
        if row["virtualPath"] == material.PAC_PATH:
            row["sha256"] = native.sha256(candidate)
    report = {"schemaVersion": 1, "segmentedSkinCandidate": True, "variant": "steve-native-limb-segments",
              "supportedExeSha256": native.EXE_SHA256, "cdmw": provenance,
              "sourceOrientationReportSha256": ORIENTATION_REPORT_SHA256, "rigInputs": source_report["rigInputs"],
              "archiveIndexSha256": source_report["archiveIndexSha256"], "candidateResources": rows,
              "logicalPrefabPath": prefab.LOGICAL_PREFAB, "templates": source_report["templates"],
              "coordinates": "Native model metres; official 0.9375 renderer scale, +Y up, +X left, MC Z reflected once; row-vector inverseBind * pose skin matrices",
              "segmentation": plan, "parts": ranges, "segmentedAudit": audit,
              "changedResource": material.PAC_PATH, "unchangedCandidateCount": 6,
              "files": {path: native.sha256(data) for path, data in files.items()},
              "integration": {key: False for key in source_report["integration"]},
              "limitations": ["Offline independent candidate only; no installation, appearance override or native animation acceptance.",
                              "Six logical parts and original static surfaces/UVs remain; limbs gain surface rings and one-MC-pixel two-bone blend bands, not original rigid MC motion.",
                              "Helpers are real weighted donor bones; dynamic twist/skin response still requires captured/native animation validation.",
                              "Head, torso, shoulder and hip pivot mismatch, visible head separation and any part-shrink problem remain unresolved; no proportional refit or pose retarget is implemented.",
                              "Bip_Weapon_L/R are PAB Hand children inside distal bind regions; actual equipment socket selection, attachments and armour fit are unverified.",
                              "Materials, transparency, prefab loading and skinned rendering remain unverified; unchanged source resources are not re-certified by this candidate.",
                              "Licensed source data and all generated native/MC payloads remain in ignored build; no redistribution authorization is claimed."]}
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    output = orientation.preflight(output, source_dirs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, data in {**files, REPORT_NAME: (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, default=ROOT / "build/steve-orientation/steve-orientation-report.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.source_report, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "vertices": report["segmentedAudit"]["vertices"],
                      "triangles": report["segmentedAudit"]["triangles"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
