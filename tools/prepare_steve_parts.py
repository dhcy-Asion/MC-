"""Split the fixed segmented Steve into independent head/body PAC candidates.

Offline only. Preserve native draw names/palette, all four LODs and every skin
record. A model-specific material sidecar accompanies each PAC; no old combined
prefab or old descriptor is advertised as a compatible assembly.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import prepare_steve_segmented as segmented

native, rig, orientation, material = segmented.native, segmented.rig, segmented.orientation, segmented.material
ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-parts"
REPORT_NAME = "steve-parts-report.json"
SOURCE_REPORT = ROOT / "build/steve-segmented/steve-segmented-report.json"
SOURCE_SHA256 = "e7a879dfb26e38b64fe0d65322b89e98b792018ae1bd7762ad47c7367b4ae0fd"
SOURCE_PAC_SHA256 = "dd1143464bedc9b8aab9a5a39a3eaa9381753690497d2eda35cd8bb3edcfaf1a"
PAC_PATHS = {
    "head": "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac",
    "body": "character/model/1_pc/1_phm/nude/crimsonmc_steve_body_1_21_1.pac",
}
MATERIAL_PATHS = {key: path.replace("/model/", "/modelproperty/", 1) + "_xml" for key, path in PAC_PATHS.items()}


def load_inputs(report_path):
    report_path = native.output_directory(report_path)
    snapshot = {}
    report = segmented.prefab.strict_json(rig.read_fixed(report_path, SOURCE_SHA256, snapshot))
    if (report.get("variant") != "steve-native-limb-segments"
            or report.get("rigInputs") != orientation.fixed_rig_inputs()
            or len(report.get("candidateResources", [])) != 7
            or not report.get("integration") or any(v is not False for v in report["integration"].values())):
        raise ValueError("Source is not the fixed offline segmented candidate")
    files = {}
    for relative, digest in report["files"].items():
        path = native.output_directory(report_path.parent / relative)
        if not path.is_relative_to(report_path.parent):
            raise ValueError("Source path escapes its directory")
        files[relative] = rig.read_fixed(path, digest, snapshot)
    for relative, digest in report["rigInputs"].items():
        rig.read_fixed(native.output_directory(ROOT / relative), digest, snapshot)
    if native.sha256(files["resources/" + material.PAC_PATH]) != SOURCE_PAC_SHA256:
        raise ValueError("Source PAC fingerprint mismatch")
    return report, files, snapshot


def verify_partition(source_pac, parts, donor):
    """Independently decode each LOD and compare full vertex records to source."""
    if set(parts) != {"head", "body"}:
        raise ValueError("Partition must contain exactly head and body")
    source_lods = segmented.parse_lods(source_pac, donor)
    parsed = {name: segmented.parse_lods(data, donor) for name, data in parts.items()}
    rows = []
    for index, (lod, mesh) in enumerate(source_lods):
        if len(mesh.submeshes) != 2:
            raise ValueError("Combined source draw partition differs")
        counts = [0, 0]
        for name, source_index in (("head", 0), ("body", 1)):
            found_lod, candidate = parsed[name][index]
            if found_lod != lod or len(candidate.submeshes) != 1:
                raise ValueError("Partition revived an empty draw or lost a LOD")
            expected, actual = mesh.submeshes[source_index], candidate.submeshes[0]
            for channel in ("name", "vertices", "normals", "uvs", "faces", "bone_indices", "bone_weights"):
                if getattr(expected, channel) != getattr(actual, channel):
                    raise ValueError(f"Partition changed {name} {channel} at LOD {lod}")
            if expected.source_vertex_stride != 40 or actual.source_vertex_stride != 40:
                raise ValueError("Partition requires fixed 40-byte native vertex records")
            for old, new in zip(expected.source_vertex_offsets, actual.source_vertex_offsets):
                if source_pac[old:old + 40] != parts[name][new:new + 40]:
                    raise ValueError("Partition changed a packed position, skin or direction record")
            counts[0] += candidate.total_vertices
            counts[1] += candidate.total_faces
        if counts != [1056, 528] or counts != [mesh.total_vertices, mesh.total_faces]:
            raise ValueError("Head/body union lost or duplicated geometry")
        rows.append({"lod": lod, "vertices": counts[0], "triangles": counts[1], "packedRecordsIdentical": True})
    return rows


def prepare(source_report_path, output, source, deps):
    protected = [source_report_path.parent, source, deps, ROOT / "build/native-steve", ROOT / "build/steve-1.21.1"]
    output = orientation.preflight(output, protected)
    source_report, source_files, snapshot = load_inputs(source_report_path)
    provenance = native.load_cdmw(source, deps)
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.mesh_pac_builder import build_pac
    from cdmw.core.pac_xml_standard_material import find_material_wrappers
    donor = source_files["template/" + native.BODY]
    pab = source_files["template/" + native.SKELETON]
    pabc = source_files["template/" + native.VARIATION]
    _, skeleton, palette, plan, _ = segmented.bind_plan(pab, donor, pabc)
    authored = segmented.author_parts(native.steve_geometry(ROOT / "build/steve-1.21.1"), plan, native.rig_candidates(skeleton, palette))
    combined, _, _ = segmented.make_pac(donor, authored)
    if native.sha256(combined) != SOURCE_PAC_SHA256:
        raise ValueError("Reconstructed combined source differs")
    files, resources, pacs, groups = {}, [], {}, {}
    source_rows = {row["virtualPath"]: row for row in source_report["candidateResources"]}

    def resource(path, payload, source_path):
        row = copy.deepcopy(source_rows[source_path])
        row.update(virtualPath=path, localFile="resources/" + path, sha256=native.sha256(payload))
        resources.append(row)
        files[row["localFile"]] = payload

    for path in material.TEXTURE_PATHS.values():
        resource(path, source_files["resources/" + path], path)
    sidecar = source_files["resources/" + material.MATERIAL_PATH]
    wrappers = find_material_wrappers(sidecar.decode("utf-8-sig"))
    if len(wrappers) != 18 or set(w.submesh_name for w in wrappers) != set(material.DRAW_NAMES):
        raise ValueError("Material no longer covers the preserved draw descriptors")
    for name in PAC_PATHS:
        selected = [part for part in authored if (part["parent"] == "head") == (name == "head")]
        pac, ranges, audit = segmented.make_pac(donor, selected)
        mesh = parse_pac(pac, native.BODY)
        if resolve_pac_bone_palette(pac, skeleton) != palette or build_pac(mesh, pac) != pac:
            raise ValueError("Part lost its native palette or byte-identical no-edit rebuild")
        pacs[name] = pac
        groups[name] = {"pacPath": PAC_PATHS[name], "materialPath": MATERIAL_PATHS[name], "parts": ranges,
                        "vertices": mesh.total_vertices, "triangles": mesh.total_faces, "roundtrip": audit}
        resource(PAC_PATHS[name], pac, material.PAC_PATH)
        resource(MATERIAL_PATHS[name], sidecar, material.MATERIAL_PATH)
    union = verify_partition(combined, pacs, donor)
    report = {"schemaVersion": 1, "variant": "steve-separate-head-body", "supportedExeSha256": native.EXE_SHA256,
              "sourceSegmentedReportSha256": SOURCE_SHA256, "sourcePacSha256": SOURCE_PAC_SHA256,
              "cdmw": provenance, "rigInputs": source_report["rigInputs"], "candidateResources": resources,
              "parts": groups, "union": union, "nativePaletteUnchanged": True,
              "materialPolicy": "Byte-identical reviewed sidecar at each model-specific path; preserve all 3 native draw names and 6 variants; empty descriptors stay empty",
              "materialPathSource": "cdmw/core/appearance_composite.py:appearance_model_sidecar_path",
              "files": {path: native.sha256(data) for path, data in files.items()},
              "integration": {key: False for key in source_report["integration"]},
              "limitations": ["Offline partition only; no game installation, actor selection or loaded material/render acceptance.",
                              "Uses unchanged old 00_0001 neutral bind; current 01_0002 descriptor needs a separately verified rig candidate.",
                              "Separate PACs do not themselves hide original hair, beard, underwear or equipment.",
                              "Current descriptor, assembly, part-shrink, head attachment and live animation/equipment remain unverified."]}
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, payload in {**files, REPORT_NAME: (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.source_report, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "resources": len(report["candidateResources"]),
                      "parts": {name: {k: row[k] for k in ("vertices", "triangles")} for name, row in report["parts"].items()},
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
