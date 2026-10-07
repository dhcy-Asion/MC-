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


def candidates(assembly_path, appearance_path):
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
    orientation.verify_snapshot(snapshot)
    return resources, reports, snapshot


def prepare(game, assembly_path, appearance_path, output, source, deps):
    assembly_path, appearance_path = native.output_directory(assembly_path), native.output_directory(appearance_path)
    protected = [assembly_path.parent, appearance_path.parent, source, deps, game]
    output = orientation.preflight(output, protected)
    _, _, snapshot = candidates(assembly_path, appearance_path)
    result = overlay.prepare(game, [assembly_path], output, source, deps, replacement_report=appearance_path)
    orientation.verify_snapshot(snapshot)
    if result["replacementPaths"] != [appearance.TARGET_PATH] or len(result["resources"]) != 11:
        raise ValueError("Prepared Steve package differs from its reviewed resource set")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--appearance-report", type=Path, default=DEFAULT_APPEARANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    result = prepare(game, args.assembly_report, args.appearance_report, args.output, args.cdmw_source, args.deps)
    print(json.dumps({key: result[key] for key in ("directoryName", "replacementPaths", "packageAudit", "integration")}, indent=2))


if __name__ == "__main__":
    main()
