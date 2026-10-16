"""Build a fixed fifteen-resource Steve visual A/B archive, entirely offline.

The fourteen encoded entries come from the admitted 69a body-basecolor plan.
Only the literal walk PAA is added, as opaque original or accepted Y5 bytes.
No PAA codec, native helper, game directory, process or receipt is used here.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import prepare_steve_body_basecolor_overlay as shared

installer, helper = shared.installer, shared.helper
native, overlay, orientation, ROOT = shared.native, shared.overlay, shared.orientation, shared.ROOT
DEFAULT_BASE_PLAN = ROOT / "build/steve-body-basecolor-probe-overlay"
DEFAULT_OUTPUT = ROOT / "build/steve-paa-motion-pack-20261013/resource-work"
DEFAULT_SOURCE, DEFAULT_DEPS = ROOT / "build/cdmw-fixed-source", ROOT / "build/cdmw-deps"
DEFAULT_ORIGINAL = ROOT / "build/steve-paa-route-20261012/donor/cd_phm_00_00_nor_move_walk_f_00.paa"
DEFAULT_CANDIDATE = ROOT / "build/steve-paa-y5-20261012/root-audit/candidate-r2/cd_phm_00_00_nor_move_walk_f_00.y5-diagnostic.paa"
REPORT_NAME = shared.REPORT_NAME
MOTION_REPORT_NAME = "steve-motion-probe-report.json"
MOTION_REPORT_FILE = "reports/" + MOTION_REPORT_NAME
BASE_PLAN_REPORT_SHA256 = "69a58b25f314e00a2c44fa1b6d3da86b1b120dbf48d8209fea6bf2c57d914cfb"
BASELINE_REPORT_SHA256 = BASE_PLAN_REPORT_SHA256
BASELINE_VARIANT = shared.VARIANT
VARIANTS = {"A": BASELINE_VARIANT + "-motion-original-a-v1",
            "B": BASELINE_VARIANT + "-motion-y5-b-v1"}
TARGET_PATH = "character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa"
ORIGINAL_SHA256 = "b5b5d5aeb0e9751242dbbe5bcf5d7f9f69e4329d08ee6cb8e2ff7d2796218085"
CANDIDATE_SHA256 = "909dd356f6087862e23a37596f4a229b310d87dc8d11ef04e88c8524e554b675"
PAA_BYTES, PAA_FLAGS = 41592, 2
DIRECTORY_NAME, RESOURCE_COUNT, SOURCE_INDEX_COUNT = "0041", 15, 34
REPORT_LIMIT, FILE_LIMIT = shared.REPORT_LIMIT, shared.FILE_LIMIT
BASE_REPORT_NAMES = shared.COMPOSITION_REPORT_NAMES
COMPOSITION_REPORT_NAMES = BASE_REPORT_NAMES | {MOTION_REPORT_NAME}
PACKAGE_FILES, METADATA_FILES, PLAN_FILES = shared.PACKAGE_FILES, shared.METADATA_FILES, shared.PLAN_FILES
PATHC_AFTER_SHA256 = "55c9442519f50e3860124358bc33d0dc4cc0ee415802ed92c9c253e8b276e703"
SOURCE_INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
SOURCE_ENCODED_SHA256 = "ea067cbb4919981705251c37468625d9695e31a6abc236c61731628c46b17cc9"
report_bytes, bounded_read, merge_snapshot = shared.report_bytes, shared.bounded_read, shared.merge_snapshot
admitted_report_paths, metadata_files, write_files = shared.admitted_report_paths, shared.metadata_files, shared.write_files


def admitted_variant(variant):
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise ValueError("Motion probe requires the explicit fixed A or B variant")
    return variant


def bootstrap_backend(source=DEFAULT_SOURCE, deps=DEFAULT_DEPS):
    """Reuse only the existing fingerprinted archive/LZ4 backend, never a codec."""
    source, deps = native.output_directory(Path(source)), native.output_directory(Path(deps))
    if source != native.output_directory(DEFAULT_SOURCE) or deps != native.output_directory(DEFAULT_DEPS):
        raise ValueError("Motion probe only admits the existing fixed archive source and dependencies")
    return shared.fixed_cdmw(source, deps)


def load_baseline(base_plan=DEFAULT_BASE_PLAN):
    base_plan = native.output_directory(Path(base_plan))
    raw = bounded_read(base_plan / REPORT_NAME, REPORT_LIMIT)
    if native.sha256(raw) != BASE_PLAN_REPORT_SHA256:
        raise ValueError("Motion probe requires the exact fixed 69a fourteen-resource baseline")
    report = shared.bodycolor.strict_json(raw)
    admitted_report_paths(report.get("candidateReports"), BASE_REPORT_NAMES)
    if (set(report.get("files", {})) != PLAN_FILES or report.get("directoryName") != DIRECTORY_NAME
            or len(report.get("resources", ())) != 14
            or len(report.get("sourceIndexes", {})) != SOURCE_INDEX_COUNT
            or report["sourceIndexes"].get("0009\\0.pamt") != SOURCE_INDEX_SHA256
            or report.get("absentOptionalMountedDirectories") != ["0036", "0037", "0038", "0039", "0040"]
            or len(report.get("replacementPaths", ())) != 3
            or report["files"].get("metadata-after/0.pathc") != PATHC_AFTER_SHA256):
        raise ValueError("Fixed motion baseline inventory differs")
    reviewed = installer.load_plan(base_plan)
    if (reviewed["reportSha256"] != BASE_PLAN_REPORT_SHA256 or reviewed["probeVariant"] != BASELINE_VARIANT
            or len(reviewed["payloads"]) != 14 or TARGET_PATH in reviewed["payloads"] or reviewed["report"] != report):
        raise ValueError("Fixed motion baseline failed standard pure admission")
    snapshot = {}
    merge_snapshot(snapshot, reviewed["readSnapshot"])
    merge_snapshot(snapshot, {base_plan / REPORT_NAME: raw})
    orientation.verify_snapshot(snapshot)
    return reviewed, snapshot


def load_paa_inputs(original=DEFAULT_ORIGINAL, candidate=DEFAULT_CANDIDATE):
    original, candidate = native.output_directory(Path(original)), native.output_directory(Path(candidate))
    if (original != native.output_directory(DEFAULT_ORIGINAL)
            or candidate != native.output_directory(DEFAULT_CANDIDATE)):
        raise ValueError("Motion probe only admits the literal fixed donor and accepted Y5 input paths")
    snapshot = {original: bounded_read(original, PAA_BYTES), candidate: bounded_read(candidate, PAA_BYTES)}
    for path, digest in ((original, ORIGINAL_SHA256), (candidate, CANDIDATE_SHA256)):
        raw = snapshot[path]
        if len(raw) != PAA_BYTES or native.sha256(raw) != digest:
            raise ValueError("Motion PAA input differs from its fixed size and SHA256")
    return snapshot[original], snapshot[candidate], snapshot


def motion_report(variant, provenance):
    variant = admitted_variant(variant)
    path = DEFAULT_ORIGINAL if variant == "A" else DEFAULT_CANDIDATE
    digest = ORIGINAL_SHA256 if variant == "A" else CANDIDATE_SHA256
    row = {"kind": "animationClip", "virtualPath": TARGET_PATH,
        "localFile": path.relative_to(ROOT).as_posix(), "sha256": digest, "payloadSize": PAA_BYTES,
        "sourceVirtualPath": TARGET_PATH, "templatePath": TARGET_PATH, "templateSha256": ORIGINAL_SHA256,
        "templateArchiveFlags": PAA_FLAGS, "archiveFlags": PAA_FLAGS}
    return {"schemaVersion": 1, "motionProbeCandidate": True, "variant": variant,
        "probeVariant": VARIANTS[variant], "supportedExeSha256": native.EXE_SHA256,
        "cdmw": copy.deepcopy(provenance), "baselineReportSha256": BASE_PLAN_REPORT_SHA256,
        "candidateResources": [row], "targetReplacement": TARGET_PATH,
        "sourceArchive": {"indexRelative": "0009/0.pamt", "indexSha256": SOURCE_INDEX_SHA256,
            "recordIndex": 78421, "pazRelative": "0009/16.paz", "offset": 377952160,
            "encodedSize": 32444, "encodedSha256": SOURCE_ENCODED_SHA256,
            "decodedSize": PAA_BYTES, "decodedSha256": ORIGINAL_SHA256, "archiveFlags": PAA_FLAGS},
        "storagePolicy": "Opaque PAA; fixed archive LZ4 block, store_size=False, unencrypted",
        "integration": {"actualGameReadByThisTool": False, "installed": False,
            "nativeFormatAcceptanceVerified": False, "currentClipSelectionVerified": False,
            "nativeQuaternionConventionVerified": False, "mcWalkingApplied": False}}


def load_motion(report_path, variant, provenance):
    report_path = native.output_directory(Path(report_path))
    if report_path.name != MOTION_REPORT_NAME or report_path.parent.name != "reports":
        raise ValueError("Motion candidate report must have its exact owned plan report path")
    raw = bounded_read(report_path, REPORT_LIMIT)
    expected = motion_report(variant, provenance)
    if raw != report_bytes(expected):
        raise ValueError("Motion candidate report differs from the complete fixed A/B reconstruction")
    original, candidate, snapshot = load_paa_inputs()
    merge_snapshot(snapshot, {report_path: raw})
    return expected["candidateResources"][0], original if variant == "A" else candidate, snapshot


def processed_paa(payload):
    from cdmw.services.archive_overlay_install import _processed_payload
    if len(payload) != PAA_BYTES or native.sha256(payload) not in (ORIGINAL_SHA256, CANDIDATE_SHA256):
        raise ValueError("Motion archive writer only admits one of the two fixed opaque PAA byte strings")
    return _processed_payload(payload, compression_type=2, encrypted=False, basename=Path(TARGET_PATH).name)


def encoded_entries(package, count=RESOURCE_COUNT):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data
    package = native.output_directory(Path(package))
    pamt, paz = package / "0.pamt", package / "0.paz"
    rows = parse_archive_pamt(pamt)
    if len(rows) != count or len({entry.path for entry in rows}) != count:
        raise ValueError("Motion archive must have the exact unique entry count")
    result = {}
    for entry in rows:
        if (native.output_directory(entry.pamt_path) != pamt or native.output_directory(entry.paz_file) != paz
                or entry.paz_index != 0 or entry.offset % 16 or not 0 < entry.comp_size <= FILE_LIMIT
                or not 0 < entry.orig_size <= FILE_LIMIT):
            raise ValueError("Motion archive entry path, size or storage boundary differs")
        raw = read_archive_entry_raw_data(entry)
        if len(raw) != entry.comp_size:
            raise ValueError("Motion archive encoded entry is truncated")
        result[entry.path] = (entry, raw)
    return result


def build_archive(original, paa_payload):
    from cdmw.core.archive_overlay import OverlayFile, build_overlay_archive
    from cdmw.core.archive_format import calculate_pa_checksum
    if len(original) != 14 or TARGET_PATH in original:
        raise ValueError("Motion archive needs precisely the fourteen original encoded entries")
    files = [OverlayFile(path=path, payload=raw, orig_size=entry.orig_size, flags=entry.flags)
             for path, (entry, raw) in original.items()]
    files.append(OverlayFile(path=TARGET_PATH, payload=processed_paa(paa_payload), orig_size=PAA_BYTES, flags=PAA_FLAGS))
    def reference_checksum(data, *, stop_event=None):
        if len(data) > overlay.RESOURCE_LIMIT * FILE_LIMIT:
            raise ValueError("Motion composition exceeds the existing rehearsal size bound")
        return calculate_pa_checksum(bytes(data))
    with patch("cdmw.core.archive_overlay._payload_checksum", reference_checksum):
        return build_overlay_archive(sorted(files, key=lambda item: item.path))


def expected_report(baseline, variant, motion_path, row, package, before, after, payloads):
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    from cdmw.core.archive_format import calculate_pa_checksum
    variant = admitted_variant(variant)
    package, motion_path = native.output_directory(Path(package)), native.output_directory(Path(motion_path))
    plan = package.parent.parent
    if (package != plan / "package" / DIRECTORY_NAME or motion_path != plan / MOTION_REPORT_FILE):
        raise ValueError("Motion composition package/report layout differs")
    files = metadata_files(before, after)
    pamt, paz = bounded_read(package / "0.pamt"), bounded_read(package / "0.paz")
    files.update({PACKAGE_FILES[0]: pamt, PACKAGE_FILES[1]: paz})
    if (before != baseline["before"] or after["meta/0.pathc"] != baseline["after"]["meta/0.pathc"]
            or native.sha256(after["meta/0.pathc"]) != PATHC_AFTER_SHA256):
        raise ValueError("Motion composition changed original metadata or the existing texture registry")
    expected_papgt = papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
        calculate_pa_checksum(pamt[12:]), flags=PAPGT_DEFAULT_FLAGS, first=True)
    if after["meta/0.papgt"] != expected_papgt:
        raise ValueError("Motion PAPGT differs from original metadata plus the actual new PAMT checksum")
    selected = bounded_read(installer.build_path(row["localFile"]), PAA_BYTES)
    expected_payloads = dict(baseline["payloads"])
    expected_payloads[TARGET_PATH] = selected
    if (not isinstance(payloads, dict) or set(payloads) != set(expected_payloads)
            or any(not isinstance(raw, bytes) for raw in payloads.values()) or payloads != expected_payloads):
        raise ValueError("Motion decoded payloads differ from the fourteen fixed resources plus one selected PAA")
    report = copy.deepcopy(baseline["report"])
    report["resources"].append(copy.deepcopy(row))
    motion_raw = report_bytes(motion_report(variant, report["cdmw"]))
    report["candidateReports"][motion_path.relative_to(ROOT).as_posix()] = native.sha256(motion_raw)
    admitted_report_paths(report["candidateReports"], COMPOSITION_REPORT_NAMES)
    report["replacementPaths"] = sorted([*baseline["report"]["replacementPaths"], TARGET_PATH])
    report["replacementScope"] = baseline["report"]["replacementScope"] + "; also shadows exactly one shared walk PAA for a reversible visual diagnostic"
    report["motionProbeComposition"] = {"schemaVersion": 1, "probeVariant": VARIANTS[variant], "variant": variant,
        "baselineReportSha256": BASE_PLAN_REPORT_SHA256, "baselineVariant": BASELINE_VARIANT,
        "candidateReportSha256": native.sha256(motion_raw), "onlyAddedReplacementVirtualPath": TARGET_PATH,
        "originalPaaSha256": ORIGINAL_SHA256, "replacementPaaSha256": row["sha256"],
        "opaquePaaBytes": PAA_BYTES, "archiveFlags": PAA_FLAGS, "preservedEncodedResourceCount": 14,
        "sourceIndexSha256": SOURCE_INDEX_SHA256, "pathcAfterSha256": PATHC_AFTER_SHA256,
        "nativeFormatAcceptanceVerified": False, "currentClipSelectionVerified": False,
        "nativeQuaternionConventionVerified": False, "mcWalkingApplied": False}
    report["files"] = {relative: native.sha256(raw) for relative, raw in files.items()}
    report["mountAudit"] = overlay.audit_mounts(before["meta/0.papgt"], after["meta/0.papgt"], DIRECTORY_NAME, pamt)
    report["packageAudit"] = overlay.audit_package(package, report["resources"], payloads)
    original, updated = encoded_entries(baseline["package"], 14), encoded_entries(package)
    if set(updated) != set(original) | {TARGET_PATH}:
        raise ValueError("Motion composition encoded resource set differs")
    for path, (old_entry, old_raw) in original.items():
        entry, raw = updated[path]
        if (raw, entry.flags, entry.orig_size) != (old_raw, old_entry.flags, old_entry.orig_size):
            raise ValueError("Motion composition changed one of the fourteen original encoded resources")
    entry, raw = updated[TARGET_PATH]
    if entry.flags != PAA_FLAGS or entry.orig_size != PAA_BYTES or raw != processed_paa(selected):
        raise ValueError("Motion PAA archive flags, original size or fixed LZ4 encoding differ")
    rebuilt = build_archive(original, selected)
    if pamt != rebuilt.pamt_bytes or paz != rebuilt.paz_bytes:
        raise ValueError("Motion package differs from the complete fixed writer reconstruction")
    return report, files


def validate_composition(report, package, before, after, payloads):
    """Admit all thirteen reports, fixed upstream sources and six package files."""
    if not isinstance(report, dict):
        raise ValueError("Motion composition report must be an object")
    composition = report.get("motionProbeComposition")
    if not isinstance(composition, dict):
        raise ValueError("Motion composition contract is missing")
    variant = admitted_variant(composition.get("variant"))
    paths = admitted_report_paths(report.get("candidateReports"), COMPOSITION_REPORT_NAMES)
    baseline, snapshot = load_baseline()
    row, _, incoming = load_motion(paths[MOTION_REPORT_NAME], variant, baseline["report"]["cdmw"])
    merge_snapshot(snapshot, incoming)
    expected, files = expected_report(baseline, variant, paths[MOTION_REPORT_NAME], row, package, before, after, payloads)
    if report != expected or report_bytes(report) != report_bytes(expected):
        raise ValueError("Motion plan differs from the complete fixed baseline and A/B reconstruction")
    plan = native.output_directory(Path(package)).parent.parent
    for relative, expected_bytes in files.items():
        path = installer.transaction.target(plan, relative)
        raw = bounded_read(path)
        if raw != expected_bytes:
            raise ValueError("Motion package or metadata changed during admission")
        merge_snapshot(snapshot, {path: raw})
    report_path = installer.transaction.target(plan, REPORT_NAME)
    raw = bounded_read(report_path, REPORT_LIMIT)
    if raw != report_bytes(expected):
        raise ValueError("Motion manifest differs from its canonical reconstruction")
    merge_snapshot(snapshot, {report_path: raw})
    orientation.verify_snapshot(snapshot)
    return snapshot


def verify_snapshot(prepared):
    snapshot = prepared.get("readSnapshot")
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("Motion prepared plan is missing its complete read snapshot")
    checked = {}
    merge_snapshot(checked, snapshot)
    orientation.verify_snapshot(checked)
    package = native.output_directory(Path(prepared["package"]))
    package_bytes = prepared.get("packageBytes")
    expected = {name: checked.get(package / name) for name in ("0.pamt", "0.paz")}
    if package_bytes != expected or any(not isinstance(raw, bytes) for raw in expected.values()):
        raise ValueError("Motion publication bytes differ from the same admitted package snapshot")


def load_plan(plan):
    """Return the shared transaction shape, with immutable admitted package bytes."""
    provenance = bootstrap_backend()
    plan = native.output_directory(Path(plan))
    raw = bounded_read(plan / REPORT_NAME, REPORT_LIMIT)
    report = shared.bodycolor.strict_json(raw)
    composition = report.get("motionProbeComposition", {})
    variant = admitted_variant(composition.get("variant"))
    if (report.get("cdmw") != provenance or set(report.get("files", {})) != PLAN_FILES
            or report.get("directoryName") != DIRECTORY_NAME):
        raise ValueError("Motion plan provenance or package file inventory differs")
    row, selected, incoming = load_motion(plan / MOTION_REPORT_FILE, variant, provenance)
    baseline, snapshot = load_baseline()
    merge_snapshot(snapshot, incoming)
    merge_snapshot(snapshot, {plan / REPORT_NAME: raw})
    files = {}
    for relative, digest in report["files"].items():
        path = installer.transaction.target(plan, relative)
        data = bounded_read(path)
        if native.sha256(data) != digest:
            raise ValueError("Motion package file checksum changed")
        files[relative] = data
        merge_snapshot(snapshot, {path: data})
    before = {"meta/" + name: files["metadata-before/" + name] for name in ("0.papgt", "0.pathc")}
    after = {"meta/" + name: files["metadata-after/" + name] for name in ("0.papgt", "0.pathc")}
    payloads = dict(baseline["payloads"])
    payloads[TARGET_PATH] = selected
    package = plan / "package" / DIRECTORY_NAME
    expected, _ = expected_report(baseline, variant, plan / MOTION_REPORT_FILE, row, package, before, after, payloads)
    if report != expected or raw != report_bytes(expected):
        raise ValueError("Motion plan is not the canonical fixed fifteen-resource reconstruction")
    prepared = {"plan": plan, "report": report, "reportSha256": native.sha256(raw), "name": DIRECTORY_NAME,
        "probeVariant": VARIANTS[variant], "candidateReport": str(plan / MOTION_REPORT_FILE),
        "candidateReportSha256": native.sha256(snapshot[plan / MOTION_REPORT_FILE]), "package": package,
        "payloads": payloads, "before": before, "after": after, "readSnapshot": snapshot,
        "packageBytes": {"0.pamt": files[PACKAGE_FILES[0]], "0.paz": files[PACKAGE_FILES[1]]}}
    verify_snapshot(prepared)
    native.verify_source(DEFAULT_SOURCE)
    return prepared


def prepare(output, variant, *, base_plan=DEFAULT_BASE_PLAN, original=DEFAULT_ORIGINAL,
            candidate=DEFAULT_CANDIDATE, source=DEFAULT_SOURCE, deps=DEFAULT_DEPS):
    variant = admitted_variant(variant)
    output, base_plan = native.output_directory(Path(output)), native.output_directory(Path(base_plan))
    protected = [base_plan, DEFAULT_BASE_PLAN, DEFAULT_ORIGINAL.parent, DEFAULT_CANDIDATE.parent,
        DEFAULT_SOURCE, DEFAULT_DEPS, *(ROOT / relative for relative in shared.PROTECTED_RELATIVE_DIRS)]
    output = orientation.preflight(output, protected)
    provenance = bootstrap_backend(source, deps)
    baseline, snapshot = load_baseline(base_plan)
    if provenance != baseline["report"]["cdmw"]:
        raise ValueError("Motion archive backend differs from the fixed baseline")
    original_bytes, candidate_bytes, incoming = load_paa_inputs(original, candidate)
    merge_snapshot(snapshot, incoming)
    selected = original_bytes if variant == "A" else candidate_bytes
    built = build_archive(encoded_entries(baseline["package"], 14), selected)
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    before = dict(baseline["before"])
    after = {"meta/0.pathc": baseline["after"]["meta/0.pathc"],
        "meta/0.papgt": papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
            built.pamt_checksum, flags=PAPGT_DEFAULT_FLAGS, first=True)}
    payloads = dict(baseline["payloads"])
    payloads[TARGET_PATH] = selected
    candidate_report = motion_report(variant, provenance)
    row, = candidate_report["candidateResources"]
    writes = metadata_files(before, after)
    writes.update({PACKAGE_FILES[0]: built.pamt_bytes, PACKAGE_FILES[1]: built.paz_bytes,
        MOTION_REPORT_FILE: report_bytes(candidate_report)})
    orientation.verify_snapshot(snapshot)
    native.verify_source(DEFAULT_SOURCE)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="steve-motion-overlay-stage-") as temporary:
        stage = native.output_directory(Path(temporary))
        write_files(stage, writes)
        # Manifest provenance names the eventual owned report, not the temporary stage.
        stage_report, _ = expected_report(baseline, variant, stage / MOTION_REPORT_FILE, row,
            stage / "package" / DIRECTORY_NAME, before, after, payloads)
        stage_report["candidateReports"].pop((stage / MOTION_REPORT_FILE).relative_to(ROOT).as_posix())
        stage_report["candidateReports"][(output / MOTION_REPORT_FILE).relative_to(ROOT).as_posix()] = native.sha256(writes[MOTION_REPORT_FILE])
        writes[REPORT_NAME] = report_bytes(stage_report)
        orientation.verify_snapshot(snapshot)
        native.verify_source(DEFAULT_SOURCE)
        output = orientation.preflight(output, protected)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        write_files(output, writes)
        published = load_plan(output)
        verify_snapshot(published)
        orientation.verify_snapshot(snapshot)
        native.verify_source(DEFAULT_SOURCE)
    return published["report"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=tuple(VARIANTS), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASE_PLAN)
    parser.add_argument("--cdmw-source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--deps", type=Path, default=DEFAULT_DEPS)
    args = parser.parse_args()
    output = args.output or DEFAULT_OUTPUT / ("plan-" + args.variant.lower())
    report = prepare(output, args.variant, base_plan=args.baseline, source=args.cdmw_source, deps=args.deps)
    print(json.dumps({"output": str(output), "resources": len(report["resources"]),
        "candidateReports": len(report["candidateReports"]), "motionProbeComposition": report["motionProbeComposition"],
        "packageAudit": report["packageAudit"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
