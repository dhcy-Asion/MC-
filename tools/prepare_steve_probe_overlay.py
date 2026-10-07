"""Rehearse the exact Steve assembly plus two Kliff mesh-reference changes.

Only ignored build is written. Original archives remain untouched. The single
existing virtual path is explicitly validated by prepare_steve_appearance; the
general asset-overlay CLI continues to reject non-crimsonmc candidate names.
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


def candidates(assembly_path, appearance_path, head_descriptor_path=None):
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
    orientation.verify_snapshot(snapshot)
    return resources, reports, snapshot


def prepare(game, assembly_path, appearance_path, output, source, deps, *, head_descriptor_path=None):
    assembly_path, appearance_path = native.output_directory(assembly_path), native.output_directory(appearance_path)
    protected = [assembly_path.parent, appearance_path.parent, source, deps, game]
    private_reports = [assembly_path]
    if head_descriptor_path is not None:
        head_descriptor_path = native.output_directory(head_descriptor_path)
        protected.append(head_descriptor_path.parent)
        private_reports.append(head_descriptor_path)
    output = orientation.preflight(output, protected)
    expected, _, snapshot = candidates(assembly_path, appearance_path, head_descriptor_path)
    result = overlay.prepare(game, private_reports, output, source, deps, replacement_report=appearance_path)
    orientation.verify_snapshot(snapshot)
    if result["replacementPaths"] != [appearance.TARGET_PATH] or len(result["resources"]) != len(expected):
        raise ValueError("Prepared Steve package differs from its reviewed resource set")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--appearance-report", type=Path, default=DEFAULT_APPEARANCE)
    parser.add_argument("--head-descriptor-report", type=Path,
                        help="Add only the fixed private head descriptor as a separate twelve-resource control")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    output = args.output or (HEAD_DESCRIPTOR_OUTPUT if args.head_descriptor_report else DEFAULT_OUTPUT)
    result = prepare(game, args.assembly_report, args.appearance_report, output, args.cdmw_source, args.deps,
                     head_descriptor_path=args.head_descriptor_report)
    print(json.dumps({key: result[key] for key in ("directoryName", "replacementPaths", "packageAudit", "integration")}, indent=2))


if __name__ == "__main__":
    main()
