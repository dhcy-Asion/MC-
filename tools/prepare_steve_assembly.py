"""Assemble ten fixed offline Steve resources with separate body/head rig contracts.

Body uses the measured 01_0002 neutral compensation. Head remains byte-identical
to the original split: its sole weighted Head bone is absent from Head0001 PABC.
CDMW's single-variation PAB fallback is an explicit candidate assumption, not a
claim about the engine's cross-component merge, head scale or animation path.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

import prepare_steve_current_rig as current
import prepare_steve_parts as parts
import prepare_steve_parts_prefab as private

native, rig, segmented = current.native, current.rig, current.segmented
orientation, material = current.orientation, current.material
ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-assembly"
REPORT_NAME = "steve-assembly-report.json"
VARIANT = "steve-private-parts-current-body-head-fallback"
BODY_SHA256 = "8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537"
# Fixed after the complete offline audit; admission never trusts self-declared
# report success flags or a caller-edited manifest, and needs no CDMW import.
REPORT_SHA256 = "2f167887d0abcae102f293d98f34c6421b52d7b5153eb1b9393e2d6da57b8f33"
SOURCES = {
    "parts": (parts.DEFAULT_OUTPUT / parts.REPORT_NAME, "b868ca5d9aa19f6cacae3af4afc8a744be98e966fa3cddbe072d67c3bb33db5d"),
    "prefab": (private.DEFAULT_OUTPUT / private.REPORT_NAME, "9aefc59a11e321cb0f46baebc6b8a6ca04caaca98b80da956d8250df43adc3f7"),
    "current": (current.DEFAULT_OUTPUT / current.REPORT_NAME, "da3bd0c0d899c280d26ad1c8d9ca188d9600eeaaf5d2f74a6c4e614a06287585"),
}
HEAD_VARIATION = "character/binary/skeletonvariation/1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"
MESH_PARAM = "character/descriptors/customizationmeta/meshparam_example_kliff.xml"
APPEARANCE = "character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml"
CONTEXT_HASHES = {
    HEAD_VARIATION: "2f761a89f87e38551a4e20b22f9b3d4b589067a2863844dde0879d37a7aec0e5",
    MESH_PARAM: "5c35726023151b024bbd10b03481bd0bb2c6c0ba745fcefe68907d20c07e40b5",
    APPEARANCE: "945e25586db2d50a83b4dd5227ab89a8e5db8c7937abd404470e52ae5b9edffe",
}
EXPECTED_PATHS = frozenset((*parts.PAC_PATHS.values(), *parts.MATERIAL_PATHS.values(),
                          *material.TEXTURE_PATHS.values(), *(s["target"] for s in private.PARTS.values()), private.DESCRIPTOR_PATH))
INTEGRATION = {key: False for key in ("archiveRegistered", "prefabLoadVerified", "nativeRenderable",
    "privateAppearanceConfigured", "controlledAppearanceBound", "animationVerified", "equipmentBound",
    "originalHairBeardSuppressed", "partShrinkVerified", "headBodyMergeVerified", "headScaleVerified",
    "nativeShaderFrameVerified", "restorationVerified", "installed")}


def relative_path(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value != value.lower() or PurePosixPath(value).is_absolute()
            or any(x in ("", ".", "..") for x in value.split("/"))):
        raise ValueError("Manifest path is not an exact lowercase relative resource path")
    return value


def read_inventory(base, manifest, snapshot):
    result = {}
    for relative, digest in manifest.items():
        relative_path(relative)
        path = native.output_directory(base / relative)
        if not path.is_relative_to(base):
            raise ValueError("Manifest path escapes its directory")
        result[relative] = rig.read_fixed(path, digest, snapshot)
    return result


def load_sources():
    reports, inventories, snapshot, raw_reports = {}, {}, {}, {}
    for key, (path, digest) in SOURCES.items():
        path = native.output_directory(path)
        raw = rig.read_fixed(path, digest, snapshot)
        report = current.prefab.strict_json(raw)
        if (report.get("supportedExeSha256") != native.EXE_SHA256 or not report.get("integration")
                or any(value is not False for value in report["integration"].values())):
            raise ValueError("Assembly requires the fixed offline source reports")
        reports[key], raw_reports[key] = report, raw
        inventories[key] = read_inventory(path.parent, report["files"], snapshot)
    return reports, inventories, snapshot, raw_reports


def read_context(game):
    """Direct fixed-index extraction; no ignored research script is an input."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != private.INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    entries = native.select_unique_entries(parse_archive_pamt(index), tuple(CONTEXT_HASHES))
    result = {}
    for path, entry in entries.items():
        native.check_links(Path(entry.paz_file))
        raw = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if not 0 < len(raw) <= rig.FILE_LIMIT or native.sha256(raw) != CONTEXT_HASHES[path]:
            raise ValueError("Head/selection context fingerprint differs: " + path)
        result[path] = raw
    gate()
    return result


def selection_contract(context):
    for path, digest in CONTEXT_HASHES.items():
        if native.sha256(context[path]) != digest:
            raise ValueError("Selection context fingerprint differs")
    meta = ET.fromstring(context[MESH_PARAM].decode("utf-8-sig"))
    rows = {}
    for kind, index, variation, name in (
            ("body", "0", current.CURRENT_VARIATION, "cd_phm_00_nude_01_0002_macduff"),
            ("head", "1", HEAD_VARIATION, "cd_phm_00_head_00_0001_macduff")):
        params = meta.findall(f"./ParamDesc[@Index='{index}']")
        if len(params) != 1 or params[0].get("Default") != "0":
            raise ValueError("Observed body/head default selection differs")
        meshes = params[0].findall("./MeshSet[@Index='0']")
        expected = {"Index": "0", "SkeletonVariation": variation.removeprefix("character/binary/skeletonvariation/"), "UseSkeletonVariation": "True"}
        if len(meshes) != 1 or meshes[0].attrib != expected or [x.attrib for x in meshes[0]] != [{"MeshFileName": name}]:
            raise ValueError("Observed selected MeshSet contract differs")
        rows[kind] = {"parameterIndex": int(index), "defaultMeshSetIndex": 0, "skeletonVariation": variation,
                      "useSkeletonVariation": True, "originalMeshFileName": name}
    app = ET.fromstring(context[APPEARANCE].decode("utf-8-sig"))
    if (app.find("./Nude/Prefab").attrib != {"Name": rows["body"]["originalMeshFileName"], "CharacterScale": "1.02571"}
            or app.find("./Head/Prefab").attrib != {"Name": rows["head"]["originalMeshFileName"], "HeadScale": "0.92"}):
        raise ValueError("Observed appearance scales differ")
    return {"sourceMeshParam": MESH_PARAM, "sourceAppearance": APPEARANCE, "selections": rows,
            "bodyCharacterScale": 1.02571, "headScale": .92, "scaleBakedOrCancelled": False,
            "engineScaleOrderOrPivotVerified": False, "appearanceCandidateIncluded": False}


def head_matrices(pab, pabc):
    from cdmw.modding.skeleton_parser import parse_pab
    from cdmw.modding.skeleton_variation_parser import parse_pabc_skeleton_variation, _neutral_variation_bind_matrix, _skin_matrices
    if native.sha256(pab) != native.TEMPLATE_HASHES[native.SKELETON] or native.sha256(pabc) != CONTEXT_HASHES[HEAD_VARIATION]:
        raise ValueError("Head PAB/PABC fingerprints differ")
    bones, _ = rig.parse_pab_records(pab)
    rows, duplicate = rig.parse_pabc_records(pabc, bones)
    covered = {row["boneIndex"] for row in rows}
    if len(rows) != 207 or duplicate or 93 in covered or bones[93]["name"] != "Bip01 Head":
        raise ValueError("Head variation coverage differs from fixed candidate assumption")
    targets = [bone["bind"] for bone in bones]
    for row in rows:
        i = row["boneIndex"]
        targets[i] = rig.neutral_bind(bones[i]["bind"], row["blocks"][0])[0]
    matrices = [rig.multiply(bone["inverse"], targets[i]) for i, bone in enumerate(bones)]
    skeleton = parse_pab(pab, native.SKELETON)
    parsed = parse_pabc_skeleton_variation(pabc, HEAD_VARIATION, skeleton=skeleton)
    # The fixed apply_skeleton_variation_to_mesh starts from these PAB binds and
    # applies only this PABC. Use its exact numeric helpers without importing its
    # optional GUI/native editor dependencies or inventing a body/head merge.
    globals_ = [bone.bind_matrix for bone in skeleton.bones]
    for row in parsed.records:
        globals_[row.bone_index] = _neutral_variation_bind_matrix(globals_[row.bone_index], row.matrix_blocks[0])
    if max(rig.error(a, b) for a, b in zip(matrices, _skin_matrices(skeleton.bones, globals_))) > 1e-12:
        raise ValueError("Independent head matrices differ from fixed CDMW helpers")
    return skeleton, parsed, matrices, covered


def compare_parts(pacs, original, combined, donor, pab, head_pabc, body_pabc):
    """Body records match combined-current exactly; head uses its own contract."""
    from cdmw.modding.mesh_parser import resolve_pac_bone_palette, parse_pac
    from cdmw.modding.mesh_pac_builder import build_pac
    from cdmw.modding.skeleton_variation_parser import _deform_positions
    skeleton, variation, head_neutral, covered = head_matrices(pab, head_pabc)
    _, body_neutral, _ = current.neutral_matrices(pab, body_pabc)
    palette = resolve_pac_bone_palette(donor, skeleton)
    if len(palette) != 189 or len(skeleton.bones) != 447:
        raise ValueError("Native skeleton/palette dimensions differ")
    combined_lods = segmented.parse_lods(combined, donor)
    rows, fallback_max, inherited_max, combined_delta, normal_min, v_min = [], 0., 0., 0., 1., 1.
    for kind, data in pacs.items():
        if resolve_pac_bone_palette(data, skeleton) != palette or build_pac(parse_pac(data, native.BODY), data) != data:
            raise ValueError("Assembly PAC palette or no-edit rebuild differs")
        before = segmented.parse_lods(original[kind], donor)
        for (lod, mesh), (old_lod, old), (combined_lod, all_mesh) in zip(segmented.parse_lods(data, donor), before, combined_lods):
            if lod != old_lod or lod != combined_lod or len(mesh.submeshes) != 1 or len(all_mesh.submeshes) != 2:
                raise ValueError("Assembly active draw/LOD correspondence differs")
            actual, target, combined_part = mesh.submeshes[0], old.submeshes[0], all_mesh.submeshes[0 if kind == "head" else 1]
            for channel in ("name", "faces", "uvs", "bone_indices", "bone_weights"):
                if getattr(actual, channel) != getattr(target, channel) or getattr(actual, channel) != getattr(combined_part, channel):
                    raise ValueError("Assembly topology/UV/skin correspondence differs")
            if any(part.source_vertex_stride != 40 for part in (actual, target, combined_part)):
                raise ValueError("Assembly vertex stride differs")
            if kind == "body":
                for a, b in zip(actual.source_vertex_offsets, combined_part.source_vertex_offsets):
                    if data[a:a+40] != combined[b:b+40]:
                        raise ValueError("Body packed record differs from combined current candidate")
                for channel in ("vertices", "normals"):
                    if getattr(actual, channel) != getattr(combined_part, channel):
                        raise ValueError("Body descriptor bounds differ from combined current candidate")
            else:
                if data != original[kind] or {palette[s] for slots in actual.bone_indices for s in slots} != {93}:
                    raise ValueError("Head must remain exact original bytes with sole weighted bone 93")
                oracle = _deform_positions(actual, palette, head_neutral)
                fallback = rig.independently_deform(mesh, palette, head_neutral)[0]
                inherited = rig.independently_deform(mesh, palette, body_neutral)[0]
                combined_pose = rig.independently_deform(all_mesh, palette, body_neutral)[0]
                if max(rig.distance(a, b) for a, b in zip(fallback, oracle)) > 1e-12:
                    raise ValueError("Independent head fallback differs from fixed CDMW application")
                fallback_max = max(fallback_max, max(rig.distance(a, b) for a, b in zip(target.vertices, fallback)))
                inherited_max = max(inherited_max, max(rig.distance(a, b) for a, b in zip(target.vertices, inherited)))
                combined_delta = max(combined_delta, max(rig.distance(a, b) for a, b in zip(fallback, combined_pose)))
                for offset in actual.source_vertex_offsets:
                    n, v, sign = orientation.decode_record_frame(data, offset)
                    matrix = head_neutral[93]
                    normal_min = min(normal_min, orientation.dot(current.covector_normal(n, rig.inverse(matrix)), orientation.unit(n)))
                    v_min = min(v_min, orientation.dot(current.direction(v, matrix), orientation.unit(v)))
            expected_counts = (48, 24) if kind == "head" else (1008, 504)
            if (mesh.total_vertices, mesh.total_faces) != expected_counts:
                raise ValueError("Assembly part counts differ")
            rows.append({"part": kind, "lod": lod, "vertices": mesh.total_vertices, "triangles": mesh.total_faces,
                         "topologyUVSkinCorrespondToCombined": True, "fullRecordsEqualCombinedCurrent": kind == "body"})
    if fallback_max > 1e-7 or inherited_max > .0001 or combined_delta > .0001:
        raise ValueError("Head assumption error exceeds reviewed bounds")
    return {"lods": rows, "skeletonBones": 447, "paletteBones": 189,
            "head": {"variationPath": HEAD_VARIATION, "records": len(covered), "weightedBones": [93],
                     "weightedBonesCoveredByHeadVariation": [], "sourceBytesPreserved": True,
                     "candidateAssumption": "Fixed CDMW single-head-PABC application initializes missing bone 93 from PAB bind; no body-to-head merge is asserted",
                     "pabFallbackMaximumTargetErrorMetres": fallback_max,
                     "bodyNeutralInheritanceHypothesisMaximumTargetErrorMetres": inherited_max,
                     "fallbackVersusCombinedCurrentNeutralMaximumDeltaMetres": combined_delta,
                     "minimumFallbackCovectorNormalDot": normal_min, "minimumFallbackTransportedVDot": v_min,
                     "nativeMergeSemanticsVerified": False,
                     "sourceEvidence": ["cdmw/modding/skeleton_variation_parser.py:apply_skeleton_variation_to_mesh",
                                        "cdmw/core/archive_mesh_appearance.py:single per-mesh pabc_entry"]}}


def dependency_audit(files):
    from prepare_asset_overlay import validate_candidate_dds
    result, references = {}, []
    for kind, path in parts.MATERIAL_PATHS.items():
        raw = files["resources/" + path]
        document = ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")
        variants = document.findall("./ModelPropertyList/ModelProperty")
        if len(variants) != 6:
            raise ValueError("Material variants differ")
        for variant in variants:
            wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
            if len(wrappers) != 3 or {w.get("_subMeshName") for w in wrappers} != set(material.DRAW_NAMES):
                raise ValueError("Material draw coverage differs")
            for wrapper in wrappers:
                params = wrapper.findall(".//MaterialParameterTexture")
                actual = {p.get("_name"): p.find("ResourceReferencePath_ITexture").get("_path") for p in params}
                expected = dict(zip(("_baseColorTexture", "_normalTexture", "_materialTexture"), material.TEXTURE_PATHS.values()))
                if len(params) != 3 or actual != expected or wrapper.find("Material").get("_materialName") != "SkinnedMeshStandard":
                    raise ValueError("Material texture or shader chain differs")
                for texture in actual.values():
                    validate_candidate_dds(files["resources/" + texture])
        wrinkle = document.find("SkinnedMeshPropertyCommon").get("_wrinkleFileName")
        if wrinkle != "character/descriptors/wrinkle/cd_phm_00_nude_00_0001.pac.wrinkle.xml":
            raise ValueError("Original external wrinkle reference differs")
        references.append({"from": path, "target": wrinkle, "role": "wrinkle", "payloadIncluded": False, "runtimeResolutionVerified": False})
        result[kind] = {"path": path, "variants": 6, "wrappers": 18, "textureReferencesClosed": True}
    for kind, spec in private.PARTS.items():
        raw = files["resources/" + spec["target"]]
        rebuilt, audit = private.build_part(files["template/" + spec["template"]], kind)
        if rebuilt != raw or spec["targetMesh"] not in EXPECTED_PATHS:
            raise ValueError("Private component regeneration or mesh reference differs")
        result[kind]["prefab"] = {"path": spec["target"], "meshPath": spec["targetMesh"],
                                   "component": audit["component"], "singleComponentRebuiltByteIdentically": True}
    current.descriptor_contract(files["resources/" + private.DESCRIPTOR_PATH])
    for path, role in ((native.SKELETON, "skeleton"), (current.CURRENT_VARIATION, "bodyVariation"),
                       (HEAD_VARIATION, "headVariation"), (native.CONSTRAINT, "animationConstraint")):
        references.append({"target": path, "role": role, "payloadIncluded": False,
                           "sourceTemplateIncluded": True, "runtimeResolutionVerified": False})
    references.extend([
        {"target": "1_pc/1_phm/macduff.hkt", "role": "ragdoll", "payloadIncluded": False, "payloadLocationResolved": False, "runtimeResolutionVerified": False},
        {"target": "breath_effect_basic", "role": "headBoneAnimationScript", "payloadIncluded": False, "runtimeResolutionVerified": False}])
    return {"parts": result, "dds": {p: validate_candidate_dds(files["resources/"+p]) for p in material.TEXTURE_PATHS.values()},
            "externalReferences": references, "allExternalDependenciesResolved": False}


def fixed_manifest(reports):
    rows = copy.deepcopy(reports["parts"]["candidateResources"] + reports["prefab"]["candidateResources"])
    for row in rows:
        if row["virtualPath"] == parts.PAC_PATHS["body"]:
            row["sha256"] = BODY_SHA256
    if len(rows) != 10 or {r["virtualPath"] for r in rows} != EXPECTED_PATHS:
        raise ValueError("Assembly must contain exactly ten reviewed resources")
    return rows


def expected_inventory(reports):
    inventory = {"provenance/" + key + ".json": digest for key, (_, digest) in SOURCES.items()}
    for key in ("current", "prefab"):
        for path, digest in reports[key]["files"].items():
            if path.startswith("template/"):
                if path in inventory and inventory[path] != digest:
                    raise ValueError("Source template disagreement")
                inventory[path] = digest
    inventory.update({"template/"+path: digest for path, digest in CONTEXT_HASHES.items()})
    inventory.update({row["localFile"]: row["sha256"] for row in fixed_manifest(reports)})
    return inventory


def load_candidate(report_path):
    """Pure local admission -> (report, file bytes by relative path, snapshot).

    Does not import/load CDMW, extract the game, mutate files or accept a report
    as evidence of runtime validation. All ten bytestrings and source templates
    are SHA pinned, independently of the report's self-declared file digests.
    """
    path = native.output_directory(report_path)
    snapshot = {}
    report = current.prefab.strict_json(rig.read_fixed(path, REPORT_SHA256, snapshot))
    if (report.get("schemaVersion") != 1 or report.get("variant") != VARIANT
            or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("archiveIndexSha256") != private.INDEX_SHA256
            or report.get("integration") != INTEGRATION
            or any(v is not False for v in report["integration"].values())):
        raise ValueError("Candidate is not the reviewed offline assembly")
    reports = {}
    for key, (_, digest) in SOURCES.items():
        reports[key] = current.prefab.strict_json(rig.read_fixed(path.parent / ("provenance/"+key+".json"), digest, snapshot))
    expected = expected_inventory(reports)
    if report.get("files") != expected or report.get("candidateResources") != fixed_manifest(reports):
        raise ValueError("Candidate inventory/resource contract differs")
    files = read_inventory(path.parent, expected, snapshot)
    for row in report["candidateResources"]:
        if (relative_path(row["virtualPath"]) not in EXPECTED_PATHS or row["localFile"] != "resources/"+row["virtualPath"]
                or native.sha256(files["template/"+row["templatePath"]]) != row["templateSha256"]):
            raise ValueError("Candidate resource template/path contract differs")
    selection_contract({p: files["template/"+p] for p in CONTEXT_HASHES})
    current.descriptor_contract(files["resources/"+private.DESCRIPTOR_PATH])
    orientation.verify_snapshot(snapshot)
    return report, files, snapshot


def prepare(game, output, source, deps):
    protected = [game, source, deps, *(path.parent for path, _ in SOURCES.values()), parts.SOURCE_REPORT.parent]
    output = orientation.preflight(output, protected)
    reports, inputs, snapshot, raw_reports = load_sources()
    provenance = native.load_cdmw(source, deps)
    context = read_context(game)
    source_report, source_files, source_snapshot = parts.load_inputs(parts.SOURCE_REPORT)
    snapshot.update(source_snapshot)
    original = {kind: inputs["parts"]["resources/"+path] for kind, path in parts.PAC_PATHS.items()}
    donor, pab = (inputs["current"]["template/"+p] for p in (native.BODY, native.SKELETON))
    body_pabc = inputs["current"]["template/"+current.CURRENT_VARIATION]
    original_union = parts.verify_partition(source_files["resources/"+material.PAC_PATH], original, donor)
    body, compensation = current.compensate_pac(original["body"], donor, pab, body_pabc)
    if native.sha256(body) != BODY_SHA256:
        raise ValueError("Reconstructed compensated body fingerprint differs")
    pacs = {"head": original["head"], "body": body}
    correspondence = compare_parts(pacs, original, inputs["current"]["resources/"+current.PAC_PATH], donor, pab, context[HEAD_VARIATION], body_pabc)
    files = {"provenance/"+key+".json": raw for key, raw in raw_reports.items()}
    for key in ("current", "prefab"):
        files.update({p: data for p, data in inputs[key].items() if p.startswith("template/")})
    files.update({"template/"+p: data for p, data in context.items()})
    for key in ("parts", "prefab"):
        files.update({p: data for p, data in inputs[key].items() if p.startswith("resources/")})
    files["resources/"+parts.PAC_PATHS["body"]] = body
    inventory = expected_inventory(reports)
    if {p: native.sha256(data) for p, data in files.items()} != inventory:
        raise ValueError("Generated assembly inventory differs")
    report = {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
              "archiveIndexSha256": private.INDEX_SHA256, "cdmw": provenance,
              "sourceReports": {key: digest for key, (_, digest) in SOURCES.items()},
              "candidateResources": fixed_manifest(reports), "logicalPrefabs": reports["prefab"]["logicalPrefabs"],
              "selectionContext": selection_contract(context), "originalPartitionUnion": original_union,
              "correspondence": correspondence, "bodyCompensation": compensation,
              "dependencies": dependency_audit(files), "files": inventory, "integration": dict(INTEGRATION),
              "limitations": [
                  "Offline ten-resource assembly only; no appearance selection, game calls, installation or native acceptance.",
                  "Body records match the combined current candidate; head deliberately retains original split bytes and uses its independent Head0001 variation contract.",
                  "Head PABC omits weighted Head bone 93. Fixed CDMW per-mesh PAB fallback and possible body-neutral inheritance are quantified separately; native merge semantics are unknown.",
                  "Body scale 1.02571 and HeadScale 0.92 remain source evidence, neither baked nor cancelled. Native scale order and pivot require a reversible visual trial.",
                  "Neutral affine normal/frame replay is mathematical; the native shader, live animation, head attachment and equipment sockets remain unverified.",
                  "Nude shrink tag, 0.05 shrink distance, empty skeleton references, original opaque owner tokens and head breath_effect_basic key remain unchanged; native identity and part-shrink behavior are unverified.",
                  "DDS references are closed within this assembly, but wrinkle, skeleton, both PABC, PAPR, ragdoll and head script remain external runtime dependencies.",
                  "Original hair/beard and equipment are not suppressed by these resources. Activation, visual fit, load/unload and restoration are separate acceptance steps.",
                  "Native and MC payloads stay in ignored local build; no redistribution authorization is implied."]}
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    if read_context(game) != context:
        raise ValueError("Native context changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, data in {**files, REPORT_NAME: (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.game_root or private.installed_game(), args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "resources": len(report["candidateResources"]),
                      "bodyErrorMetres": report["bodyCompensation"]["afterNeutralMaximumTargetErrorMetres"],
                      "head": report["correspondence"]["head"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
