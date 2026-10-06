"""Prepare seven local Steve resources with a grounded nude prefab reference.

Only fixed-source archive reads and build outputs are used. The cloned prefab
does not select Kliff's controlled body or supply an animation controller.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_asset_overlay as overlay
import prepare_native_steve as native
import prepare_steve_material as material

ROOT = native.ROOT
REPORT_NAME = "steve-prefab-report.json"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
PREFAB_TEMPLATE = "character/bin__/prefab/1_pc/01_phm/nude/cd_phm_00_nude_00_0001.prefab"
PREFAB_SHA256 = "e3cd0a7937d34098d19078978de2022fe00031352702f5b1eb87fc40c5275ee9"
DESCRIPTOR_SHA256 = "ab6ed2fcef90c363e7461502be2cbe7a233d22bcdc7705611ec593f19351edda"
PREFAB_PATH = "character/bin__/prefab/1_pc/01_phm/nude/crimsonmc_steve_1_21_1.prefab"
DESCRIPTOR_PATH = "character/prefab/1_pc/01_phm/nude/crimsonmc_steve_1_21_1.prefabdata_xml"
LOGICAL_PREFAB = "/character/prefab/1_pc/01_phm/nude/crimsonmc_steve_1_21_1.prefab"
UNDERWEAR = "character/model/1_pc/1_phm/armor/38_underwear/cd_phm_00_uw_00_0001.pac"
DEPENDENCIES = {
    native.SKELETON: native.TEMPLATE_HASHES[native.SKELETON],
    native.VARIATION: "d662f990135f90fb6862246524f7d719cdf0aa97cac4eb7e4891741bd072319d",
    native.CONSTRAINT: "e09f83b94d61512105d736c0cf210d29698e032677accbd6015bfb6eabfb79ad",
}
DESCRIPTOR_FIELDS = {
    "SkeletonName": "1_pc/1_phm/phm_01.pab",
    "SkeletonVariationName": "1_PC/1_PHM/Nude/CD_PHM_00_Nude_00_0001.pabc",
    "AnimationConstraintName": "1_pc/1_phm/phm_01.papr",
}
# The input is the already reviewed material candidate, not a generic donor.
INPUT_RESOURCES = {
    material.TEXTURE_PATHS["base"]: ("texture", material.TEXTURE_TEMPLATES["base"][0],
        material.TEXTURE_TEMPLATES["base"][1], "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"),
    material.TEXTURE_PATHS["normal"]: ("texture", material.TEXTURE_TEMPLATES["normal"][0],
        material.TEXTURE_TEMPLATES["normal"][1], "3555d0a27af8de753c2368e8878a995469577ff40515d9467e4540ff2feebc33"),
    material.TEXTURE_PATHS["material"]: ("texture", material.TEXTURE_TEMPLATES["material"][0],
        material.TEXTURE_TEMPLATES["material"][1], "047babdb8e93774756a770cdd4387e091fe21527dfb4dca9ad2c8e6f6e29f2db"),
    material.PAC_PATH: ("skinnedMesh", native.BODY, native.TEMPLATE_HASHES[native.BODY], material.CANDIDATE_PAC_SHA256),
    material.MATERIAL_PATH: ("skinnedMaterial", native.MATERIAL, material.MATERIAL_SHA256,
        "01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538"),
}


def strict_json(data: bytes) -> dict:
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError("Candidate report size is outside the reviewed bounds")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Candidate report contains duplicate JSON keys")
            result[key] = value
        return result
    value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
    if not isinstance(value, dict):
        raise ValueError("Candidate report must be an object")
    return value


def load_material(report_path: Path) -> tuple[list[dict], dict[str, bytes], dict[Path, bytes]]:
    report_path = native.output_directory(report_path)
    raw = report_path.read_bytes()
    report = strict_json(raw)
    if (report.get("schemaVersion") != 1 or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("archiveIndexSha256") != INDEX_SHA256
            or report.get("cdmw", {}).get("commit") != native.CDMW_COMMIT
            or report.get("cdmw", {}).get("pythonSourceTreeSha256") != native.CDMW_SOURCE_SHA256):
        raise ValueError("Material report has an unreviewed source or game fingerprint")
    claims = report.get("integration")
    if not isinstance(claims, dict) or not claims or any(value is not False for value in claims.values()):
        raise ValueError("Material report contains unverified integration claims")
    rows = report.get("candidateResources")
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("Material report must contain exactly five reviewed resources")
    resources, payloads, snapshot = [], {}, {report_path: raw}
    inventory = report.get("files")
    if not isinstance(inventory, dict) or len(inventory) > 32:
        raise ValueError("Material report file inventory is invalid")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Material resource must be an object")
        path = overlay.virtual_path(row.get("virtualPath"))
        if path in payloads or path not in INPUT_RESOURCES:
            raise ValueError("Material report has a duplicate or unreviewed resource path")
        kind, template, template_sha, digest = INPUT_RESOURCES[path]
        local = "resources/" + path
        if (row.get("localFile") != local or row.get("kind") != kind
                or row.get("templatePath") != template or row.get("templateSha256") != template_sha
                or row.get("sha256") != digest or inventory.get(local) != digest):
            raise ValueError("Material resource metadata differs from the reviewed candidate")
        source = native.output_directory(report_path.parent / local)
        if source.stat().st_size > overlay.FILE_LIMIT:
            raise ValueError("Material resource exceeds the bounded file size")
        data = source.read_bytes()
        if not data or native.sha256(data) != digest:
            raise ValueError("Material candidate checksum mismatch")
        if kind == "texture":
            overlay.validate_candidate_dds(data)
        payloads[path], snapshot[source] = data, data
        resources.append({"virtualPath": path, "localFile": local, "sha256": digest,
                          "kind": kind, "templatePath": template, "templateSha256": template_sha})
    # Validate every claimed source file too, rather than trusting unused rows.
    for local, digest in inventory.items():
        local = overlay.virtual_path(local)
        path = native.output_directory(report_path.parent / local)
        if not path.is_relative_to(report_path.parent) or path.stat().st_size > overlay.FILE_LIMIT:
            raise ValueError("Material file inventory escapes its bounded report directory")
        data = path.read_bytes()
        if native.sha256(data) != digest:
            raise ValueError("Material report file inventory checksum mismatch")
        snapshot[path] = data
    return resources, payloads, snapshot


def audit_prefab(data: bytes, mesh: str) -> object:
    from cdmw.core.prefab_binary import decode_prefab_binary, walk_is_determined
    document = decode_prefab_binary(data)
    if not document.walk_complete or not walk_is_determined(data) or document.root_type != "SceneObject":
        raise ValueError("Nude prefab structure is not completely determined")
    if len(document.objects) != 2 or [row.name for row in document.objects] != ["CD_Nude", "CD_Underwear"]:
        raise ValueError("Nude prefab components differ from the reviewed template")
    for row, expected, tag in zip(document.objects, (mesh, UNDERWEAR), ("Nude", "Underwear")):
        if (row.component_type != "SkinnedMeshComponent" or
                [(name, value.text) for name, value in row.values] !=
                [("_skinnedMeshFile", expected), ("_shrinkTag", tag)] or
                [value.text for value in row.resources] != [expected]):
            raise ValueError("Nude prefab target reference or underwear dependency changed")
    if [value.text for value in document.all_strings()] != [mesh, "Nude", UNDERWEAR, "Underwear"]:
        raise ValueError("Nude prefab contains an unreviewed reference")
    return document


def build_prefab(data: bytes, target: str = material.PAC_PATH) -> tuple[bytes, dict]:
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    if target != material.PAC_PATH:
        raise ValueError("Only the reviewed new Steve PAC target is supported")
    if native.sha256(data) != PREFAB_SHA256:
        raise ValueError("Nude prefab template fingerprint mismatch")
    original = audit_prefab(data, native.BODY)
    if rewrite_prefab_paths(data, {}).data != data:
        raise ValueError("Nude prefab no-edit rewrite changed source bytes")
    result = rewrite_prefab_paths(data, {native.BODY: target})
    audit_prefab(result.data, target)
    span = original.objects[0].resources[0]
    old, new = native.BODY.encode("ascii"), target.encode("ascii")
    start, stop = span.offset + 4, span.offset + 4 + len(old)
    if span.length != len(old) or len(old) != len(new) or data[start:stop] != old:
        raise ValueError("Nude prefab target span is outside the reviewed equal-length boundary")
    expected = data[:start] + new + data[stop:]
    if len(result.edits) != 1 or result.byte_delta != 0 or result.data != expected:
        raise ValueError("Prefab rewrite modified bytes outside its one target reference")
    if rewrite_prefab_paths(result.data, {target: native.BODY}).data != data:
        raise ValueError("Prefab inverse rewrite did not restore the exact template")
    return result.data, {"walkComplete": True, "walkDetermined": True,
        "noEditRewriteByteIdentical": True, "inverseRewriteByteIdentical": True,
        "onlyTargetReferenceBytesChanged": True, "targetObject": "CD_Nude",
        "targetMember": "_skinnedMeshFile", "targetOffset": start,
        "oldPath": native.BODY, "newPath": target, "pathEdits": len(result.edits),
        "byteDelta": result.byte_delta, "relocatedPointers": result.relocated_pointers,
        "underwearPathPreserved": UNDERWEAR, "controllerSupplied": False}


def audit_descriptor(data: bytes) -> dict:
    if native.sha256(data) != DESCRIPTOR_SHA256:
        raise ValueError("Nude descriptor template fingerprint mismatch")
    root = ET.fromstring(data.decode("utf-8-sig"))
    if root.tag != "NudePrefabData" or len(root) != 3 or root.attrib:
        raise ValueError("Nude descriptor has an unreviewed structure")
    actual = {row.tag: row.attrib.get("FileName") for row in root}
    if actual != DESCRIPTOR_FIELDS or any(set(row.attrib) != {"FileName"} for row in root):
        raise ValueError("Nude descriptor skeleton dependencies changed")
    return {"byteIdenticalCopy": True, "fields": actual, "dependencies": DEPENDENCIES}


def read_templates(game: Path) -> tuple[dict[str, bytes], dict[str, int]]:
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    native.check_links(game)
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    for path in (exe, index):
        native.check_links(path)
    if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
        raise ValueError("Unsupported EXE or source archive index fingerprint")
    hashes = {PREFAB_TEMPLATE: PREFAB_SHA256, native.DESCRIPTOR: DESCRIPTOR_SHA256, **DEPENDENCIES}
    hashes.update({row[1]: row[2] for row in INPUT_RESOURCES.values()})
    selected = native.select_unique_entries(parse_archive_pamt(index), tuple(hashes))
    payloads, flags = {}, {}
    for path, entry in selected.items():
        native.check_links(Path(entry.paz_file))
        data = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if not data or len(data) > overlay.FILE_LIMIT or native.sha256(data) != hashes[path]:
            raise ValueError("Native source template fingerprint mismatch: " + path)
        payloads[path], flags[path] = data, entry.flags
    if native.file_hash(index) != INDEX_SHA256 or native.file_hash(exe) != native.EXE_SHA256:
        raise ValueError("Source archive or executable changed during extraction")
    return payloads, flags


def preflight(output: Path, names: list[str]) -> Path:
    output = native.output_directory(output)
    if len(names) != len({name.casefold() for name in names}):
        raise ValueError("Duplicate candidate output path")
    for name in names:
        overlay.virtual_path("asset/" + name)
        for path in (output / name, (output / name).with_name(Path(name).name + ".tmp")):
            native.check_links(path)
            if path.exists() and (not path.is_file() or path.name.endswith(".tmp")):
                raise ValueError("Candidate output or temporary path is occupied")
    return output


def publish(output: Path, files: dict[str, bytes], report: dict) -> None:
    payloads = {**files, REPORT_NAME: (json.dumps(report, indent=2) + "\n").encode()}
    output = preflight(output, list(payloads))
    for name, data in payloads.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(destination)
        temporary = destination.with_name(destination.name + ".tmp")
        native.check_links(temporary)
        created = False
        try:
            with temporary.open("xb") as stream:
                created = True
                stream.write(data)
                stream.flush()
            temporary.replace(destination)
        finally:
            if created and temporary.exists():
                temporary.unlink()


def prepare(game: Path, output: Path, source: Path, deps: Path, material_report: Path) -> dict:
    output, material_report = native.output_directory(output), native.output_directory(material_report)
    if output.is_relative_to(material_report.parent) or material_report.parent.is_relative_to(output):
        raise ValueError("Prefab output must be separate from its material inputs")
    for directory in (source, deps):
        native.check_links(directory)
        resolved = directory.resolve()
        if output.is_relative_to(resolved) or resolved.is_relative_to(output):
            raise ValueError("Prefab output overlaps its fixed-source dependencies")
    provenance = native.load_cdmw(source, deps)
    resources, inputs, snapshot = load_material(material_report)
    templates, flags = read_templates(game)
    candidate, prefab_audit = build_prefab(templates[PREFAB_TEMPLATE])
    descriptor = templates[native.DESCRIPTOR]
    descriptor_audit = audit_descriptor(descriptor)
    files = {"template/" + path: data for path, data in templates.items()}
    files.update({"resources/" + path: data for path, data in inputs.items()})
    for path, data, kind, template in ((PREFAB_PATH, candidate, "prefab", PREFAB_TEMPLATE),
                                      (DESCRIPTOR_PATH, descriptor, "prefabDescriptor", native.DESCRIPTOR)):
        files["resources/" + path] = data
        resources.append({"virtualPath": path, "localFile": "resources/" + path,
            "sha256": native.sha256(data), "kind": kind, "templatePath": template,
            "templateSha256": native.sha256(templates[template])})
    for row in resources:
        row["templateArchiveFlags"] = flags[row["templatePath"]]
    report = {"schemaVersion": 1, "supportedExeSha256": native.EXE_SHA256,
        "cdmw": provenance, "archiveIndexSha256": INDEX_SHA256,
        "materialReport": str(material_report.relative_to(ROOT)).replace("\\", "/"),
        "materialReportSha256": native.sha256(snapshot[material_report]),
        "candidateResources": resources, "logicalPrefabPath": LOGICAL_PREFAB,
        "prefabAudit": prefab_audit, "descriptorAudit": descriptor_audit,
        "templates": {path: {"sha256": native.sha256(data), "archiveFlags": flags[path]}
                      for path, data in templates.items()},
        "files": {path: native.sha256(data) for path, data in files.items()},
        "integration": {"archiveRegistered": False, "prefabLoadVerified": False,
            "nativeMaterialLoaded": False, "nativeRenderable": False,
            "controllerBound": False, "controlledAppearanceBound": False,
            "animationVerified": False, "equipmentBound": False, "installed": False},
        "limitations": [
            "Only a local offline prefab candidate; no process attachment, game API or game-file writes.",
            "The source prefab contains CD_Nude and preserved CD_Underwear; no animation controller is supplied.",
            "The logical prefab path is a candidate alias for the bin__ resource, not proof of runtime loading.",
            "The existing PAB/PABC/PAPR references are unchanged; fitting, animation, alpha and equipment remain unverified.",
            "No current Kliff appearance/controller selection or controlled-body refresh lifecycle has been established.",
            "Packaging must separately check all mounted archive paths and register the three DDS in PATHC.",
            "All native and Minecraft-derived payloads remain local ignored build assets; no redistribution approval."]}
    preflight(output, [*files, REPORT_NAME])
    if any(path.read_bytes() != data for path, data in snapshot.items()):
        raise ValueError("Material input changed during prefab preparation")
    # Read the actual archives again before publishing, not only the local copies.
    final_templates, final_flags = read_templates(game)
    if final_templates != templates or final_flags != flags:
        raise ValueError("Native templates changed before prefab publication")
    publish(output, files, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/steve-prefab")
    parser.add_argument("--material-report", type=Path, default=ROOT / "build/steve-material/steve-material-report.json")
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    try:
        game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
        report = prepare(game, args.output, args.cdmw_source, args.deps, args.material_report)
    except (OSError, ValueError, ImportError, KeyError, TypeError) as error:
        raise SystemExit(f"Steve prefab preparation stopped: {error}") from error
    print(json.dumps({"output": str(native.output_directory(args.output)),
        "resources": len(report["candidateResources"]), "prefabAudit": report["prefabAudit"],
        "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
