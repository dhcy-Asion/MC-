"""Rehearse fixed Steve probes with separate head and default-clothing controls.

Only ignored build is written. Original archives remain untouched. Existing
paths are validated by the fixed meshparam, part-table and single-app loaders;
the general asset-overlay CLI rejects non-crimsonmc candidate names.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import prepare_asset_overlay as overlay
import prepare_steve_appearance as appearance
import prepare_steve_assembly as assembly
import prepare_steve_orientation as orientation

native = overlay.native
ROOT = native.ROOT
DEFAULT_ASSEMBLY = ROOT / "build/steve-assembly/steve-assembly-report.json"
DEFAULT_APPEARANCE = ROOT / "build/steve-appearance/steve-appearance-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-probe-overlay"
HEAD_DESCRIPTOR_REPORT = ROOT / "build/steve-head-descriptor/steve-head-descriptor-report.json"
HEAD_DESCRIPTOR_OUTPUT = ROOT / "build/steve-head-descriptor-probe-overlay"
PART_TABLE_REPORT = ROOT / "build/steve-part-table-v2/steve-part-table-report.json"
PART_TABLE_OUTPUT = ROOT / "build/steve-part-table-v2-probe-overlay"
HEAD_MESH_CONTROL_REPORT = ROOT / "build/steve-head-mesh-control/steve-head-mesh-control-report.json"
NATIVE_HEAD_OUTPUT = ROOT / "build/steve-native-head-probe-overlay"
NATIVE_HEAD_PREFAB = "character/bin__/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefab"
ASSEMBLY_HEAD_SHA256 = "36aef15ab3d1b085846a8b7837ab8108d79073e7379899f85ea69fe5ca2d6df0"
HEAD_ROOT_REPORT = ROOT / "build/steve-native-head-root/steve-native-head-root-report.json"
NATIVE_HEAD_ROOT_OUTPUT = ROOT / "build/steve-native-head-root-probe-overlay"
HEAD_NATIVE_MATERIAL_REPORT = ROOT / "build/steve-head-native-material/steve-head-native-material-report.json"
HEAD_NATIVE_MATERIAL_OUTPUT = ROOT / "build/steve-head-native-material-probe-overlay"
CLOTHING_REPORT = ROOT / "build/steve-clothing-control/steve-clothing-control-report.json"
CLOTHING_OUTPUT = ROOT / "build/steve-clothing-control-probe-overlay"
HEAD_ROOT_RESOURCES = {
    "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac":
        ("e75f7a7989137756c4744a16c001bce8f91a6f0b6caabb84214f5d42b710d9b9", "skinnedMesh", 1),
    "character/modelproperty/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac_xml":
        ("01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538", "skinnedMaterial", 50),
}


def app_output(report_path):
    import prepare_steve_app as app
    report, _, _ = app.load_candidate(report_path)
    return ROOT / ("build/steve-app-" + report["appearanceVariant"] + "-part-table-v2-probe-overlay")


def audit_part_components(payloads):
    """Compare registration slots with the actual decoded private prefab bytes.

    Call only after loading the fixed CDMW implementation. A valid table and a
    valid prefab can still disagree, so neither file's own audit is sufficient.
    """
    import prepare_steve_part_table as parts
    import prepare_steve_parts_prefab as private
    records = parts.parse_table(payloads[parts.TABLE_PATH])["records"]
    result = {}
    for kind, spec in private.PARTS.items():
        if spec["target"] not in payloads:
            raise ValueError("Steve registration has no matching private prefab")
        row = parts.unique_row(records, Path(spec["target"]).stem)
        decoded, _ = private.strict_layout(payloads[spec["target"]])
        actual = [obj.name for obj in decoded.objects]
        if [slot["name"] for slot in row["parts"]] != actual:
            raise ValueError("Steve registration components differ from private prefab: " + kind)
        result[kind] = actual
    return result


def replacement_paths(resources):
    return sorted(path for path, item in resources.items()
                  if item["row"]["kind"] in ("appearanceMeshParams", "appearanceDefinition", "partPrefabTable"))


def candidates(assembly_path, appearance_path, head_descriptor_path=None, app_path=None, part_table_path=None,
               head_mesh_control_path=None, head_root_path=None, head_native_material_path=None,
               clothing_path=None):
    if clothing_path is not None:
        if head_native_material_path is None or head_root_path is None or head_descriptor_path is None or part_table_path is None:
            raise ValueError("Clothing control requires the complete original-head-material v2 controls")
        if app_path is not None or head_mesh_control_path is not None:
            raise ValueError("Clothing control excludes app and head-mesh controls")
    if head_native_material_path is not None:
        if head_root_path is None or head_descriptor_path is None or part_table_path is None:
            raise ValueError("Native-head material control requires head-root, descriptor and v2 part table")
        if app_path is not None or head_mesh_control_path is not None:
            raise ValueError("Native-head material control excludes app and head-mesh controls")
    if head_root_path is not None:
        if app_path is not None or head_mesh_control_path is not None:
            raise ValueError("Native-head-root control cannot be combined with app or head-mesh controls")
        if head_descriptor_path is None or part_table_path is None:
            raise ValueError("Native-head-root control requires the private head descriptor and v2 part table")
    if head_mesh_control_path is not None:
        if app_path is not None:
            raise ValueError("Native-head mesh control cannot be combined with an initial app control")
        if head_descriptor_path is None or part_table_path is None:
            raise ValueError("Native-head mesh control requires the private head descriptor and v2 part table")
    if (app_path is not None or part_table_path is not None) and head_descriptor_path is None:
        raise ValueError("Steve registration/initial app control requires the fixed private head descriptor")
    if app_path is not None and part_table_path is None:
        raise ValueError("Initial app control requires private part registration")
    assembly_path, appearance_path = native.output_directory(assembly_path), native.output_directory(appearance_path)
    model, files, model_snapshot = assembly.load_candidate(assembly_path)
    selection, replaced, selection_snapshot = appearance.load_candidate(appearance_path)
    if len(model["candidateResources"]) != 10 or len(selection["targetReplacements"]) != 1:
        raise ValueError("Steve probe requires the exact ten-resource assembly and one mesh-parameter replacement")
    resources = {}
    for row in model["candidateResources"]:
        path = row["virtualPath"]
        resources[path] = {"row": row, "localPath": assembly_path.parent / row["localFile"], "payload": files[row["localFile"]]}
    for row in selection["targetReplacements"]:
        path = row["virtualPath"]
        if path in resources or path != appearance.TARGET_PATH:
            raise ValueError("Unexpected replacement path or resource collision")
        resources[path] = {"row": row, "localPath": appearance_path.parent / row["localFile"], "payload": replaced[path]}
    if len(resources) != 11:
        raise ValueError("Steve probe resource identities are not unique")
    reports = {str(p.relative_to(ROOT)): native.file_hash(p) for p in (assembly_path, appearance_path)}
    snapshot = {**model_snapshot, **selection_snapshot}
    if head_descriptor_path is not None:
        import prepare_steve_head_descriptor as head
        head_descriptor_path = native.output_directory(head_descriptor_path)
        descriptor, head_files, head_snapshot = head.load_candidate(head_descriptor_path)
        rows = descriptor["candidateResources"]
        if len(rows) != 1:
            raise ValueError("Head-descriptor control must add exactly one resource")
        row = rows[0]
        path = row["virtualPath"]
        if (path != "character/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefabdata_xml"
                or path in resources or row["kind"] != "prefabDescriptor"):
            raise ValueError("Unexpected head-descriptor control resource")
        resources[path] = {"row": row, "localPath": head_descriptor_path.parent / row["localFile"],
                           "payload": head_files[row["localFile"]]}
        reports[str(head_descriptor_path.relative_to(ROOT))] = native.file_hash(head_descriptor_path)
        snapshot.update(head_snapshot)
    if part_table_path is not None:
        import prepare_steve_part_table as parts
        part_table_path = native.output_directory(part_table_path)
        candidate, table_payloads, table_snapshot = parts.load_candidate(part_table_path)
        rows = candidate["targetReplacements"]
        if len(rows) != 1:
            raise ValueError("Steve registration must replace exactly one reviewed part table")
        row = rows[0]
        path = row["virtualPath"]
        if path != "character/bin__/partprefabtable.pappt" or path in resources or row["kind"] != "partPrefabTable":
            raise ValueError("Unexpected Steve part table control resource")
        resources[path] = {"row": row, "localPath": part_table_path.parent / row["localFile"],
                           "payload": table_payloads[path]}
        reports[str(part_table_path.relative_to(ROOT))] = native.file_hash(part_table_path)
        snapshot.update(table_snapshot)
    if head_mesh_control_path is not None:
        import prepare_steve_head_mesh_control as head_mesh
        original = resources.get(NATIVE_HEAD_PREFAB)
        if (original is None or original["row"].get("sha256") != ASSEMBLY_HEAD_SHA256
                or native.sha256(original["payload"]) != ASSEMBLY_HEAD_SHA256):
            raise ValueError("Native-head control requires the fixed original assembly head prefab")
        head_mesh_control_path = native.output_directory(head_mesh_control_path)
        candidate, control_payloads, control_snapshot = head_mesh.load_candidate(head_mesh_control_path)
        rows = candidate["candidateResources"]
        if len(rows) != 1 or set(control_payloads) != {NATIVE_HEAD_PREFAB}:
            raise ValueError("Native-head control must override exactly the fixed private head prefab")
        row = rows[0]
        if (row.get("kind") != "prefab" or row.get("archiveFlags") != 0
                or any(row.get(key) != original["row"][key]
                       for key in ("virtualPath", "kind", "templatePath", "templateSha256"))
                or row.get("sha256") != native.sha256(control_payloads[NATIVE_HEAD_PREFAB])
                or row["sha256"] == ASSEMBLY_HEAD_SHA256):
            raise ValueError("Native-head control resource identity differs from the reviewed assembly donor")
        resources[NATIVE_HEAD_PREFAB] = {"row": row, "localPath": head_mesh_control_path.parent / row["localFile"],
                                         "payload": control_payloads[NATIVE_HEAD_PREFAB]}
        reports[str(head_mesh_control_path.relative_to(ROOT))] = native.file_hash(head_mesh_control_path)
        snapshot.update(control_snapshot)
    if head_root_path is not None:
        import prepare_steve_native_head_root as head_root
        for path, (digest, kind, flags) in HEAD_ROOT_RESOURCES.items():
            original = resources.get(path)
            if (original is None or original["row"].get("kind") != kind
                    or original["row"].get("sha256") != digest or native.sha256(original["payload"]) != digest):
                raise ValueError("Native-head-root control requires the fixed original assembly head resources")
        head_root_path = native.output_directory(head_root_path)
        candidate, root_payloads, root_snapshot = head_root.load_candidate(head_root_path)
        rows = candidate["candidateResources"]
        if (len(rows) != 2 or {row.get("virtualPath") for row in rows} != set(HEAD_ROOT_RESOURCES)
                or set(root_payloads) != set(HEAD_ROOT_RESOURCES)):
            raise ValueError("Native-head-root control must override exactly the private head PAC and material")
        for row in rows:
            path = row["virtualPath"]
            old_digest, kind, flags = HEAD_ROOT_RESOURCES[path]
            if (row.get("kind") != kind or row.get("archiveFlags") != flags
                    or row.get("sha256") != native.sha256(root_payloads[path]) or row["sha256"] == old_digest):
                raise ValueError("Native-head-root resource identity differs from its reviewed candidate")
            # The pure loader admits the new native head donor/template. The
            # old assembly's body-template provenance must not be substituted.
            resources[path] = {"row": row, "localPath": head_root_path.parent / row["localFile"],
                               "payload": root_payloads[path]}
        reports[str(head_root_path.relative_to(ROOT))] = native.file_hash(head_root_path)
        snapshot.update(root_snapshot)
    if head_native_material_path is not None:
        import prepare_steve_head_native_material as material
        import prepare_steve_native_head_root as head_root
        path = material.MATERIAL_PATH
        original = resources.get(path)
        preserved = resources.get(head_root.PAC_PATH)
        if (original is None or original["row"].get("kind") != "skinnedMaterial"
                or original["row"].get("archiveFlags") != 50
                or original["row"].get("sha256") != material.OLD_MATERIAL_SHA256
                or native.sha256(original["payload"]) != material.OLD_MATERIAL_SHA256
                or preserved is None or preserved["row"].get("kind") != "skinnedMesh"
                or preserved["row"].get("sha256") != material.PRESERVED_PAC_SHA256
                or native.sha256(preserved["payload"]) != material.PRESERVED_PAC_SHA256):
            raise ValueError("Native-head material control requires the fixed failed head-root PAC and material")
        head_native_material_path = native.output_directory(head_native_material_path)
        candidate, material_payloads, material_snapshot = material.load_candidate(head_native_material_path)
        rows = candidate["candidateResources"]
        if len(rows) != 1 or set(material_payloads) != {path}:
            raise ValueError("Native-head material control must override exactly the private head PAMI")
        row = rows[0]
        if (row.get("virtualPath") != path or row.get("kind") != "skinnedMaterial"
                or row.get("archiveFlags") != 50 or row.get("payloadSize") != 16149
                or row.get("templatePath") != material.NATIVE_MATERIAL_PATH
                or row.get("sourceVirtualPath") != material.NATIVE_MATERIAL_PATH
                or row.get("templateSha256") != material.NATIVE_MATERIAL_SHA256
                or row.get("sha256") != material.NATIVE_MATERIAL_SHA256
                or native.sha256(material_payloads[path]) != material.NATIVE_MATERIAL_SHA256):
            raise ValueError("Native-head material resource differs from its fixed original head source")
        # This second replacement is specific to the admitted failed PAMI.
        # General duplicate resources remain rejected by the overlay loader.
        resources[path] = {"row": row, "localPath": head_native_material_path.parent / row["localFile"],
                           "payload": material_payloads[path]}
        reports[str(head_native_material_path.relative_to(ROOT))] = native.file_hash(head_native_material_path)
        snapshot.update(material_snapshot)
    if clothing_path is not None:
        import prepare_steve_clothing_control as clothing
        if len(resources) != 13 or len(reports) != 6:
            raise ValueError("Clothing control requires exactly the reviewed thirteen-resource baseline")
        clothing_path = native.output_directory(clothing_path)
        candidate, clothing_payloads, clothing_snapshot = clothing.load_candidate(clothing_path)
        rows = candidate["targetReplacements"]
        if len(rows) != 1 or set(clothing_payloads) != {clothing.TARGET_PATH}:
            raise ValueError("Clothing control must replace exactly the fixed Macduff 00000 app")
        row = rows[0]
        path = clothing.TARGET_PATH
        if (path in resources or row.get("virtualPath") != path or row.get("templatePath") != path
                or row.get("kind") != "appearanceDefinition" or row.get("archiveFlags") != 48
                or row.get("templateArchiveFlags") != 48 or row.get("templateSha256") != clothing.TARGET_SHA256
                or native.sha256(clothing_payloads[path]) != row.get("sha256")):
            raise ValueError("Clothing control differs from its fixed appearance source")
        resources[path] = {"row": row, "localPath": clothing_path.parent / row["localFile"],
                           "payload": clothing_payloads[path]}
        reports[str(clothing_path.relative_to(ROOT))] = native.file_hash(clothing_path)
        snapshot.update(clothing_snapshot)
    if app_path is not None:
        import prepare_steve_app as app
        app_path = native.output_directory(app_path)
        candidate, app_payloads, app_snapshot = app.load_candidate(app_path)
        rows = candidate["targetReplacements"]
        if len(rows) != 1:
            raise ValueError("Initial app control must replace exactly one reviewed appearance")
        row = rows[0]
        path = row["virtualPath"]
        if path not in appearance.APPEARANCES or path in resources or row["kind"] != "appearanceDefinition":
            raise ValueError("Unexpected initial appearance control resource")
        resources[path] = {"row": row, "localPath": app_path.parent / row["localFile"],
                           "payload": app_payloads[path]}
        reports[str(app_path.relative_to(ROOT))] = native.file_hash(app_path)
        snapshot.update(app_snapshot)
    orientation.verify_snapshot(snapshot)
    return resources, reports, snapshot


def prepare(game, assembly_path, appearance_path, output, source, deps, *, head_descriptor_path=None,
            app_path=None, part_table_path=None, head_mesh_control_path=None, head_root_path=None,
            head_native_material_path=None, clothing_path=None):
    assembly_path, appearance_path = native.output_directory(assembly_path), native.output_directory(appearance_path)
    protected = [assembly_path.parent, appearance_path.parent, source, deps, game]
    private_reports = [assembly_path]
    if head_descriptor_path is not None:
        head_descriptor_path = native.output_directory(head_descriptor_path)
        protected.append(head_descriptor_path.parent)
        private_reports.append(head_descriptor_path)
    if app_path is not None:
        app_path = native.output_directory(app_path)
        protected.append(app_path.parent)
    if part_table_path is not None:
        part_table_path = native.output_directory(part_table_path)
        protected.append(part_table_path.parent)
    if head_mesh_control_path is not None:
        head_mesh_control_path = native.output_directory(head_mesh_control_path)
        protected.append(head_mesh_control_path.parent)
    if head_root_path is not None:
        head_root_path = native.output_directory(head_root_path)
        protected.append(head_root_path.parent)
    if head_native_material_path is not None:
        head_native_material_path = native.output_directory(head_native_material_path)
        protected.append(head_native_material_path.parent)
    if clothing_path is not None:
        clothing_path = native.output_directory(clothing_path)
        protected.append(clothing_path.parent)
    output = orientation.preflight(output, protected)
    expected, _, snapshot = candidates(assembly_path, appearance_path, head_descriptor_path, app_path, part_table_path,
                                       head_mesh_control_path, head_root_path, head_native_material_path, clothing_path)
    result = overlay.prepare(game, private_reports, output, source, deps, replacement_report=appearance_path,
                             initial_appearance_report=app_path, part_table_report=part_table_path,
                             head_mesh_control_report=head_mesh_control_path, head_root_report=head_root_path,
                             head_native_material_report=head_native_material_path, clothing_report=clothing_path)
    orientation.verify_snapshot(snapshot)
    if result["replacementPaths"] != replacement_paths(expected) or len(result["resources"]) != len(expected):
        raise ValueError("Prepared Steve package differs from its reviewed resource set")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--appearance-report", type=Path, default=DEFAULT_APPEARANCE)
    parser.add_argument("--head-descriptor-report", type=Path,
                        help="Add only the fixed private head descriptor as a separate twelve-resource control")
    parser.add_argument("--app-report", type=Path,
                        help="Add one fixed initial appearance; requires --head-descriptor-report and --part-table-report")
    parser.add_argument("--part-table-report", type=Path,
                        help="Register the two private body/head stems; requires --head-descriptor-report")
    parser.add_argument("--head-mesh-control-report", type=Path,
                        help="Use the native head mesh in the fixed private prefab; requires the thirteen-resource v2 controls and excludes --app-report")
    parser.add_argument("--head-root-report", type=Path,
                        help="Replace only the private head PAC/material with the native head-root candidate; requires descriptor and v2 table, excludes app/head-mesh controls")
    parser.add_argument("--head-native-material-report", type=Path,
                        help="Replace only the failed head-root PAMI with fixed original head material; requires --head-root-report and its descriptor/table controls")
    parser.add_argument("--clothing-report", type=Path,
                        help="Clear only the fixed initial app Armor prefabs; requires the complete original-head-material controls")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    if args.clothing_report and not args.head_native_material_report:
        parser.error("--clothing-report requires --head-native-material-report and all of its controls")
    if args.head_native_material_report:
        if not args.head_root_report or not args.head_descriptor_report or not args.part_table_report:
            parser.error("--head-native-material-report requires --head-root-report, --head-descriptor-report and --part-table-report")
        if args.app_report or args.head_mesh_control_report:
            parser.error("--head-native-material-report excludes --app-report and --head-mesh-control-report")
    if (args.app_report or args.part_table_report) and not args.head_descriptor_report:
        parser.error("Registration/initial app control requires --head-descriptor-report")
    if args.app_report and not args.part_table_report:
        parser.error("--app-report requires --part-table-report")
    if args.head_root_report:
        if args.app_report or args.head_mesh_control_report:
            parser.error("--head-root-report cannot be combined with --app-report or --head-mesh-control-report")
        if not args.head_descriptor_report or not args.part_table_report:
            parser.error("--head-root-report requires --head-descriptor-report and --part-table-report")
    if args.head_mesh_control_report:
        if args.app_report:
            parser.error("--head-mesh-control-report cannot be combined with --app-report")
        if not args.head_descriptor_report or not args.part_table_report:
            parser.error("--head-mesh-control-report requires --head-descriptor-report and --part-table-report")
    game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    output = args.output or (CLOTHING_OUTPUT if args.clothing_report else
                            HEAD_NATIVE_MATERIAL_OUTPUT if args.head_native_material_report else
                            NATIVE_HEAD_ROOT_OUTPUT if args.head_root_report else
                            NATIVE_HEAD_OUTPUT if args.head_mesh_control_report else
                            app_output(args.app_report) if args.app_report else
                            PART_TABLE_OUTPUT if args.part_table_report else
                            HEAD_DESCRIPTOR_OUTPUT if args.head_descriptor_report else DEFAULT_OUTPUT)
    result = prepare(game, args.assembly_report, args.appearance_report, output, args.cdmw_source, args.deps,
                     head_descriptor_path=args.head_descriptor_report, app_path=args.app_report,
                     part_table_path=args.part_table_report, head_mesh_control_path=args.head_mesh_control_report,
                     head_root_path=args.head_root_report, head_native_material_path=args.head_native_material_report,
                     clothing_path=args.clothing_report)
    print(json.dumps({key: result[key] for key in ("directoryName", "replacementPaths", "packageAudit", "integration")}, indent=2))


if __name__ == "__main__":
    main()
