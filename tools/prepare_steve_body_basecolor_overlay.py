"""Compose one native body-PAMI experiment over the fixed successful head plan.

Only ignored build is written. This offline composer never reads game metadata,
processes, personal saves or installation receipts.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import prepare_steve_head_visible_layer_overlay as shared
import prepare_steve_body_basecolor as bodycolor

installer, helper = shared.installer, shared.helper
native, overlay, orientation, ROOT = shared.native, shared.overlay, shared.orientation, shared.ROOT
DEFAULT_OUTPUT = helper.BODY_BASECOLOR_OUTPUT
DEFAULT_BASELINE = helper.HEAD_VISIBLE_LAYER_OUTPUT
DEFAULT_BODY_REPORT = helper.BODY_BASECOLOR_REPORT
REPORT_NAME = shared.REPORT_NAME
BASELINE_REPORT_SHA256 = "e86048837217e7cd85ac957d12db2b05b3315449234e8639668ebf627665add1"
BASELINE_VARIANT = shared.VARIANT
VARIANT = "steve-kliff-original-head-body-material-empty-armor-head-basecolor-head-uv-visible-layer-body-basecolor-part-table-v2"
BODY_REPORT_SHA256 = "7a01a93b4173f472c954e3baa7bc669b4854ed9816d3cdff1b8e4237a11f2d3f"
DIRECTORY_NAME, RESOURCE_COUNT, SOURCE_INDEX_COUNT = shared.DIRECTORY_NAME, 14, 34
REPORT_LIMIT, FILE_LIMIT = shared.REPORT_LIMIT, shared.FILE_LIMIT
BASE_REPORT_NAMES = shared.COMPOSITION_REPORT_NAMES
COMPOSITION_REPORT_NAMES = BASE_REPORT_NAMES | {bodycolor.REPORT_NAME}
PACKAGE_FILES, METADATA_FILES, PLAN_FILES = shared.PACKAGE_FILES, shared.METADATA_FILES, shared.PLAN_FILES
PROTECTED_RELATIVE_DIRS = (*shared.PROTECTED_RELATIVE_DIRS,
    "build/steve-head-visible-layer-probe-overlay", "build/steve-body-basecolor", "build/steve-body-native-material")
report_bytes, bounded_read, merge_snapshot = shared.report_bytes, shared.bounded_read, shared.merge_snapshot
fixed_cdmw, admitted_report_paths = shared.fixed_cdmw, shared.admitted_report_paths
encoded_entries, metadata_files, write_files = shared.encoded_entries, shared.metadata_files, shared.write_files


def load_baseline(baseline=DEFAULT_BASELINE):
    baseline = native.output_directory(Path(baseline))
    report_path = baseline / REPORT_NAME
    raw = bounded_read(report_path, REPORT_LIMIT)
    if native.sha256(raw) != BASELINE_REPORT_SHA256:
        raise ValueError("Body base-color requires the fixed visible-layer baseline report SHA")
    report = bodycolor.strict_json(raw)
    admitted_report_paths(report.get("candidateReports"), BASE_REPORT_NAMES)
    if (set(report.get("files", {})) != PLAN_FILES or report.get("directoryName") != DIRECTORY_NAME
            or not isinstance(report.get("sourceIndexes"), dict) or len(report["sourceIndexes"]) != SOURCE_INDEX_COUNT
            or report.get("absentOptionalMountedDirectories") != ["0036", "0037", "0038", "0039", "0040"]
            or len(report.get("replacementPaths", ())) != 3):
        raise ValueError("Fixed visible-layer baseline inventory differs")
    reviewed = installer.load_plan(baseline)
    if (reviewed["reportSha256"] != BASELINE_REPORT_SHA256 or reviewed["probeVariant"] != BASELINE_VARIANT
            or len(reviewed["payloads"]) != RESOURCE_COUNT or reviewed["report"] != report):
        raise ValueError("Fixed visible-layer baseline failed standard pure admission")
    snapshot = {}
    installer.merge_read_snapshot(snapshot, reviewed["readSnapshot"])
    merge_snapshot(snapshot, {report_path: raw})
    for relative, digest in report["files"].items():
        path = installer.transaction.target(baseline, relative)
        if path not in snapshot or native.sha256(snapshot[path]) != digest:
            raise ValueError("Fixed visible-layer snapshot omits admitted package or metadata bytes")
    for path, digest in ((bodycolor.MATERIAL_PATH, bodycolor.NATIVE_MATERIAL_SHA256),
                         (bodycolor.PAC_PATH, bodycolor.PRESERVED_PAC_SHA256),
                         (bodycolor.DIFFUSE_PATH, bodycolor.DIFFUSE_SHA256)):
        if native.sha256(reviewed["payloads"].get(path, b"")) != digest:
            raise ValueError("Fixed visible-layer baseline body PAC, PAMI or diffuse pin differs")
    orientation.verify_snapshot(snapshot)
    return reviewed, snapshot


def load_body(report_path, baseline):
    report_path = native.output_directory(Path(report_path))
    if report_path.name != bodycolor.REPORT_NAME:
        raise ValueError("Body base-color composition requires its exact report name")
    candidate, payloads, snapshot = bodycolor.load_candidate(report_path)
    row, = candidate["candidateResources"]
    if (native.sha256(snapshot[report_path]) != BODY_REPORT_SHA256 or set(payloads) != {bodycolor.MATERIAL_PATH}
            or set(row) != {"kind", "virtualPath", "localFile", "sha256", "payloadSize", "sourceVirtualPath",
                            "templatePath", "templateSha256", "templateArchiveFlags", "archiveFlags"}
            or bodycolor.restore_material(payloads[bodycolor.MATERIAL_PATH]) != baseline["payloads"][bodycolor.MATERIAL_PATH]):
        raise ValueError("Body base-color candidate is not the fixed single baseline PAMI replacement")
    row = copy.deepcopy(row)
    row["localFile"] = str(bodycolor.package_path(report_path.parent, row["localFile"]).relative_to(ROOT))
    return row, payloads[bodycolor.MATERIAL_PATH], snapshot


def processed_body(payload):
    from cdmw.services.archive_overlay_install import _processed_payload
    if native.sha256(payload) != bodycolor.NEW_MATERIAL_SHA256 or len(payload) != bodycolor.CANDIDATE_SIZE:
        raise ValueError("New body base-color PAMI differs from its fixed byte contract")
    return _processed_payload(payload, compression_type=2, encrypted=True,
                              basename=Path(bodycolor.MATERIAL_PATH).name)


def build_archive(original, body_payload):
    """Keep thirteen original encoded entries and replace one fixed PAMI."""
    from cdmw.core.archive_overlay import OverlayFile, build_overlay_archive
    from cdmw.core.archive_format import calculate_pa_checksum
    files = []
    for path, (entry, raw) in original.items():
        size, flags = entry.orig_size, entry.flags
        if path == bodycolor.MATERIAL_PATH:
            raw, size, flags = processed_body(body_payload), bodycolor.CANDIDATE_SIZE, 50
        files.append(OverlayFile(path=path, payload=raw, orig_size=size, flags=flags))
    def reference_checksum(data, *, stop_event=None):
        if len(data) > overlay.RESOURCE_LIMIT * FILE_LIMIT:
            raise ValueError("Body base-color composition exceeds the existing rehearsal bound")
        return calculate_pa_checksum(bytes(data))
    with patch("cdmw.core.archive_overlay._payload_checksum", reference_checksum):
        return build_overlay_archive(sorted(files, key=lambda item: item.path))


def expected_report(baseline, body_report, body_row, package, before, after, payloads):
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    from cdmw.core.archive_format import calculate_pa_checksum
    package = native.output_directory(Path(package))
    if package.name != DIRECTORY_NAME or package.parent.name != "package":
        raise ValueError("Body base-color composition package layout differs")
    files = metadata_files(before, after)
    pamt, paz = bounded_read(package / "0.pamt"), bounded_read(package / "0.paz")
    files.update({PACKAGE_FILES[0]: pamt, PACKAGE_FILES[1]: paz})
    if before != baseline["before"] or after["meta/0.pathc"] != baseline["after"]["meta/0.pathc"]:
        raise ValueError("Body base-color composition changed original metadata or existing texture registry")
    expected_after = papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
        calculate_pa_checksum(pamt[12:]), flags=PAPGT_DEFAULT_FLAGS, first=True)
    if after["meta/0.papgt"] != expected_after:
        raise ValueError("Body base-color PAPGT differs from original metadata plus actual new PAMT CRC")
    expected_payloads = dict(baseline["payloads"])
    expected_payloads[bodycolor.MATERIAL_PATH] = bodycolor.load_candidate(body_report)[1][bodycolor.MATERIAL_PATH]
    if (not isinstance(payloads, dict) or set(payloads) != set(expected_payloads)
            or any(not isinstance(data, bytes) for data in payloads.values()) or payloads != expected_payloads):
        raise ValueError("Body base-color composition decoded payloads changed outside the one fixed body PAMI")
    report = copy.deepcopy(baseline["report"])
    del report["headVisibleLayerComposition"]
    report["resources"] = [copy.deepcopy(body_row) if row["virtualPath"] == bodycolor.MATERIAL_PATH else copy.deepcopy(row)
                           for row in report["resources"]]
    report["candidateReports"][str(body_report.relative_to(ROOT))] = native.file_hash(body_report)
    admitted_report_paths(report["candidateReports"], COMPOSITION_REPORT_NAMES)
    report["bodyBasecolorComposition"] = {"schemaVersion": 1, "probeVariant": VARIANT,
        "baselineReportSha256": BASELINE_REPORT_SHA256, "baselineVariant": BASELINE_VARIANT,
        "candidateReportSha256": BODY_REPORT_SHA256, "onlyReplacedVirtualPath": bodycolor.MATERIAL_PATH,
        "previousMaterialSha256": bodycolor.NATIVE_MATERIAL_SHA256,
        "replacementMaterialSha256": bodycolor.NEW_MATERIAL_SHA256,
        "preservedEncodedResourceCount": 13, "changedMainDrawBaseColorPathCount": 6,
        "retainedMaterialByteSize": 50017, "nativeApplied": False,
        "nativeFormatAcceptanceVerified": False, "mcBodySkinVerified": False,
        "rigAndGeometryUnchanged": True, "mcRuntimeActionsVerified": False}
    report["files"] = {relative: native.sha256(raw) for relative, raw in files.items()}
    report["mountAudit"] = overlay.audit_mounts(before["meta/0.papgt"], after["meta/0.papgt"], DIRECTORY_NAME, pamt)
    report["packageAudit"] = overlay.audit_package(package, report["resources"], payloads)
    original, updated = encoded_entries(baseline["package"]), encoded_entries(package)
    if set(original) != set(updated) or set(updated) != set(payloads):
        raise ValueError("Body base-color composition encoded resource set differs")
    for path, (old_entry, old_raw) in original.items():
        entry, raw = updated[path]
        kind = next(row["kind"] for row in report["resources"] if row["virtualPath"] == path)
        if entry.flags != installer.FLAGS[kind]:
            raise ValueError("Body base-color composition storage flags differ")
        if path != bodycolor.MATERIAL_PATH:
            if (raw, entry.flags, entry.orig_size) != (old_raw, old_entry.flags, old_entry.orig_size):
                raise ValueError("Body base-color composition changed another encoded resource")
        elif (old_entry.flags != 50 or entry.flags != 50 or entry.orig_size != bodycolor.CANDIDATE_SIZE
              or raw != processed_body(payloads[path])):
            raise ValueError("Body base-color composition PAMI encoding or flags differ")
    if (updated[bodycolor.PAC_PATH][0].flags != 1 or updated[bodycolor.DIFFUSE_PATH][0].flags != 0
            or sum(entry.path == bodycolor.DIFFUSE_PATH for entry, _ in updated.values()) != 1):
        raise ValueError("Body base-color composition requires the unique unchanged mesh and raw DDS")
    rebuilt = build_archive(original, payloads[bodycolor.MATERIAL_PATH])
    if pamt != rebuilt.pamt_bytes or paz != rebuilt.paz_bytes:
        raise ValueError("Body base-color archive bytes differ from the complete fixed writer reconstruction")
    return report, files


def validate_composition(report, package, before, after, payloads):
    if not isinstance(report, dict):
        raise ValueError("Body base-color composition report must be an object")
    paths = admitted_report_paths(report.get("candidateReports"), COMPOSITION_REPORT_NAMES)
    baseline, snapshot = load_baseline(DEFAULT_BASELINE)
    body_report = paths[bodycolor.REPORT_NAME]
    row, _, incoming = load_body(body_report, baseline)
    merge_snapshot(snapshot, incoming)
    expected, files = expected_report(baseline, body_report, row, package, before, after, payloads)
    if report != expected or report_bytes(report) != report_bytes(expected):
        raise ValueError("Body base-color overlay differs from the complete fixed-baseline reconstruction")
    plan = native.output_directory(Path(package)).parent.parent
    for relative, expected_bytes in files.items():
        path = installer.transaction.target(plan, relative)
        raw = bounded_read(path)
        if raw != expected_bytes:
            raise ValueError("Body base-color composition file changed during admission")
        merge_snapshot(snapshot, {path: raw})
    report_path = installer.transaction.target(plan, REPORT_NAME)
    raw = bounded_read(report_path, REPORT_LIMIT)
    if raw != report_bytes(expected):
        raise ValueError("Body base-color composition manifest bytes differ from canonical reconstruction")
    merge_snapshot(snapshot, {report_path: raw})
    orientation.verify_snapshot(snapshot)
    return snapshot


def prepare(output=DEFAULT_OUTPUT, baseline=DEFAULT_BASELINE, body_report=DEFAULT_BODY_REPORT,
            source=ROOT / "build/cdmw-fixed-source", deps=ROOT / "build/cdmw-deps"):
    output, baseline, body_report, source, deps = (native.output_directory(Path(p)) for p in
        (output, baseline, body_report, source, deps))
    protected = [baseline, DEFAULT_BASELINE, body_report.parent, source, deps,
                 *(ROOT / relative for relative in PROTECTED_RELATIVE_DIRS)]
    if output != native.output_directory(DEFAULT_OUTPUT):
        protected.append(DEFAULT_OUTPUT)
    output = orientation.preflight(output, protected)
    provenance = fixed_cdmw(source, deps)
    reviewed, snapshot = load_baseline(baseline)
    if provenance != reviewed["report"]["cdmw"]:
        raise ValueError("Body base-color CDMW source/dependencies differ from the fixed baseline")
    row, body_payload, incoming = load_body(body_report, reviewed)
    merge_snapshot(snapshot, incoming)
    built = build_archive(encoded_entries(reviewed["package"]), body_payload)
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    before = dict(reviewed["before"])
    after = {"meta/0.pathc": reviewed["after"]["meta/0.pathc"],
        "meta/0.papgt": papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
            built.pamt_checksum, flags=PAPGT_DEFAULT_FLAGS, first=True)}
    payloads = dict(reviewed["payloads"])
    payloads[bodycolor.MATERIAL_PATH] = body_payload
    writes = metadata_files(before, after)
    writes.update({PACKAGE_FILES[0]: built.pamt_bytes, PACKAGE_FILES[1]: built.paz_bytes})
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="body-basecolor-overlay-stage-") as temporary:
        stage = native.output_directory(Path(temporary))
        write_files(stage, writes)
        report, _ = expected_report(reviewed, body_report, row, stage / "package" / DIRECTORY_NAME, before, after, payloads)
        writes[REPORT_NAME] = report_bytes(report)
        write_files(stage, {REPORT_NAME: writes[REPORT_NAME]})
        staged = validate_composition(report, stage / "package" / DIRECTORY_NAME, before, after, payloads)
        orientation.verify_snapshot(staged)
        orientation.verify_snapshot(snapshot)
        native.verify_source(source)
        output = orientation.preflight(output, protected)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        write_files(output, writes)
        published = validate_composition(report, output / "package" / DIRECTORY_NAME, before, after, payloads)
        orientation.verify_snapshot(published)
        orientation.verify_snapshot(staged)
        orientation.verify_snapshot(snapshot)
        native.verify_source(source)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--body-basecolor-report", type=Path, default=DEFAULT_BODY_REPORT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.baseline, args.body_basecolor_report, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "probeVariant": VARIANT,
        "resources": len(report["resources"]), "candidateReports": len(report["candidateReports"]),
        "bodyBasecolorComposition": report["bodyBasecolorComposition"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
