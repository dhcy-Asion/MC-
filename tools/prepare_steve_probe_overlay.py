"""Rehearse the exact Steve assembly plus two Kliff mesh-reference changes.

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
PART_TABLE_REPORT = ROOT / "build/steve-part-table/steve-part-table-report.json"
PART_TABLE_OUTPUT = ROOT / "build/steve-part-table-probe-overlay"


def app_output(report_path):
    import prepare_steve_app as app
    report, _, _ = app.load_candidate(report_path)
    return ROOT / ("build/steve-app-" + report["appearanceVariant"] + "-probe-overlay")


def replacement_paths(resources):
    return sorted(path for path, item in resources.items()
                  if item["row"]["kind"] in ("appearanceMeshParams", "appearanceDefinition", "partPrefabTable"))


def candidates(assembly_path, appearance_path, head_descriptor_path=None, app_path=None, part_table_path=None):
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
            app_path=None, part_table_path=None):
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
    output = orientation.preflight(output, protected)
    expected, _, snapshot = candidates(assembly_path, appearance_path, head_descriptor_path, app_path, part_table_path)
    result = overlay.prepare(game, private_reports, output, source, deps, replacement_report=appearance_path,
                             initial_appearance_report=app_path, part_table_report=part_table_path)
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    if (args.app_report or args.part_table_report) and not args.head_descriptor_report:
        parser.error("Registration/initial app control requires --head-descriptor-report")
    if args.app_report and not args.part_table_report:
        parser.error("--app-report requires --part-table-report")
    game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    output = args.output or (app_output(args.app_report) if args.app_report else
                            PART_TABLE_OUTPUT if args.part_table_report else
                            HEAD_DESCRIPTOR_OUTPUT if args.head_descriptor_report else DEFAULT_OUTPUT)
    result = prepare(game, args.assembly_report, args.appearance_report, output, args.cdmw_source, args.deps,
                     head_descriptor_path=args.head_descriptor_report, app_path=args.app_report,
                     part_table_path=args.part_table_report)
    print(json.dumps({key: result[key] for key in ("directoryName", "replacementPaths", "packageAudit", "integration")}, indent=2))


if __name__ == "__main__":
    main()
