"""Install/restore fixed Steve probes with head, registration and single-app controls.

This uses the existing transaction, backup, lock and recovery implementation.
The default oak-log installer cannot install or restore this separate probe kind.
The game must be closed. Later game saves are preserved when removing the probe.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import install_asset_probe as transaction
import prepare_steve_probe_overlay as steve

native, overlay, ROOT = transaction.native, transaction.overlay, transaction.ROOT
KIND = "steve-mesh-parameters"
FLAGS = {"texture": 0, "skinnedMesh": 1, "skinnedMaterial": 50,
         "prefab": 0, "prefabDescriptor": 48, "appearanceMeshParams": 50,
         "partPrefabTable": 50, "appearanceDefinition": 48}


def build_path(value):
    # Overlay reports store host filesystem paths, unlike archive virtual paths.
    # Normalize Windows separators before applying the same traversal/root gates.
    if not isinstance(value, str):
        raise ValueError("Steve local path must be a string")
    return native.output_directory(ROOT / transaction.relative(value.replace("\\", "/")))


def load_plan(plan):
    plan = native.output_directory(plan)
    raw = transaction.target(plan, "reports/overlay-report.json").read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Steve probe report is too large")
    report = json.loads(raw)
    if (report.get("schemaVersion") != 1 or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("cdmw", {}).get("commit") != native.CDMW_COMMIT):
        raise ValueError("Steve probe version differs")
    name = report.get("directoryName")
    if not isinstance(name, str) or not name.isascii() or not name.isdigit() or len(name) != 4 or not 36 <= int(name) <= 9999:
        raise ValueError("Unsafe Steve overlay directory")
    candidate_reports = report.get("candidateReports")
    if not isinstance(candidate_reports, dict) or len(candidate_reports) not in (2, 3, 4, 5):
        raise ValueError("Steve probe requires the exact reviewed candidate report set")
    required = {"steve-assembly-report.json", "steve-appearance-report.json"}
    with_head = required | {"steve-head-descriptor-report.json"}
    with_table = with_head | {"steve-part-table-report.json"}
    with_native_head = with_table | {"steve-head-mesh-control-report.json"}
    with_head_root = with_table | {"steve-native-head-root-report.json"}
    allowed = with_native_head | with_head_root | {"steve-app-report.json"}
    by_name = {}
    for path, digest in candidate_reports.items():
        file = build_path(path)
        if file.name not in allowed or file.name in by_name:
            raise ValueError("Unrecognized or ambiguous Steve candidate report name")
        by_name[file.name] = file
    if set(by_name) not in (required, with_head, with_table, with_table | {"steve-app-report.json"},
                           with_native_head, with_head_root):
        raise ValueError("Unrecognized Steve candidate report names")
    for path, digest in candidate_reports.items():
        if native.file_hash(build_path(path)) != digest:
            raise ValueError("Steve candidate report changed or is ambiguous")
    models = by_name["steve-assembly-report.json"]
    appearance = by_name["steve-appearance-report.json"]
    head_descriptor = by_name.get("steve-head-descriptor-report.json")
    part_table = by_name.get("steve-part-table-report.json")
    app = by_name.get("steve-app-report.json")
    head_mesh_control = by_name.get("steve-head-mesh-control-report.json")
    head_root = by_name.get("steve-native-head-root-report.json")
    expected, inputs, snapshot = steve.candidates(models, appearance, head_descriptor, app, part_table, head_mesh_control, head_root)
    if report.get("replacementPaths") != steve.replacement_paths(expected):
        raise ValueError("Steve probe exact replacement targets differ")
    if inputs != candidate_reports:
        raise ValueError("Steve candidate provenance changed")
    rows = report.get("resources")
    if not isinstance(rows, list) or len(rows) != len(expected) or {r.get("virtualPath") for r in rows} != set(expected):
        raise ValueError("Steve probe must contain exactly the reviewed resource set")
    payloads = {}
    for row in rows:
        item = expected[row["virtualPath"]]
        source = item["row"]
        if any(row.get(k) != source[k] for k in ("virtualPath", "kind", "sha256", "templatePath", "templateSha256")):
            raise ValueError("Steve resource identity differs from its verified candidate")
        local = build_path(row["localFile"])
        if local != item["localPath"].resolve() or local.read_bytes() != item["payload"]:
            raise ValueError("Steve resource path or payload changed")
        if row.get("archiveFlags") != FLAGS[source["kind"]]:
            raise ValueError("Steve storage flags differ from the reviewed templates")
        payloads[row["virtualPath"]] = item["payload"]
    if part_table:
        steve.audit_part_components(payloads)
    wanted = {f"package/{name}/0.pamt", f"package/{name}/0.paz",
              "metadata-before/0.papgt", "metadata-before/0.pathc", "metadata-after/0.papgt", "metadata-after/0.pathc"}
    if set(report.get("files", {})) != wanted:
        raise ValueError("Steve package file inventory differs")
    for path, digest in report["files"].items():
        if native.file_hash(transaction.target(plan, path)) != digest:
            raise ValueError("Steve package file checksum changed")
    package = plan / "package" / name
    overlay.audit_package(package, rows, payloads)
    from cdmw.core.archive_format import parse_archive_pamt
    if any(entry.flags != FLAGS[expected[entry.path]["row"]["kind"]] for entry in parse_archive_pamt(package / "0.pamt")):
        raise ValueError("Steve archive flags differ from the exact plan")
    before = {p: (plan / "metadata-before" / Path(p).name).read_bytes() for p in transaction.METADATA}
    after = {p: (plan / "metadata-after" / Path(p).name).read_bytes() for p in transaction.METADATA}
    overlay.audit_mounts(before["meta/0.papgt"], after["meta/0.papgt"], name, (package / "0.pamt").read_bytes())
    textures = {path: data for path, data in payloads.items() if expected[path]["row"]["kind"] == "texture"}
    overlay.audit_registry(before["meta/0.pathc"], after["meta/0.pathc"], textures)
    steve.orientation.verify_snapshot(snapshot)
    variant = "steve-kliff-head-descriptor-v1" if head_descriptor else "steve-kliff-meshparams-v1"
    if part_table:
        variant = "steve-kliff-part-table-v2"
    if head_mesh_control:
        variant = "steve-kliff-native-head-part-table-v2"
    if head_root:
        variant = "steve-kliff-native-head-root-part-table-v2"
    if app:
        path, = [path for path, item in expected.items() if item["row"]["kind"] == "appearanceDefinition"]
        number = Path(path).name.removeprefix("cd_phm_macduff_").removesuffix(".app_xml")
        variant = f"steve-kliff-app-{number}-part-table-v2"
    return {"plan": plan, "report": report, "reportSha256": native.sha256(raw), "name": name,
            "probeVariant": variant,
            "candidateReport": str(models),
            "candidateReportSha256": native.file_hash(models), "package": package,
            "payloads": payloads, "before": before, "after": after}


def install(plan, game, **kwargs):
    return transaction.install(plan, game, probe_kind=KIND, **kwargs)


def restore(game=None, **kwargs):
    return transaction.restore(game, probe_kind=KIND, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true")
    action.add_argument("--restore", action="store_true")
    parser.add_argument("--plan", type=Path, default=steve.DEFAULT_OUTPUT)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    native.load_cdmw(args.cdmw_source, args.deps)
    game = args.game_root
    if args.install and game is None:
        game = Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
    result = install(args.plan, game) if args.install else restore(game)
    print(json.dumps({key: result[key] for key in ("status", "directoryName", "backupRoot")}, indent=2))


if __name__ == "__main__":
    main()
