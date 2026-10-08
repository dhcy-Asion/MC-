"""Compose the fixed fourteen-resource head base-color probe from local packages.

Only ignored build inputs are read. The existing body probe stays installed until
the normal installer separately permits a replacement. This tool neither reads
the game installation nor writes a game, receipt, save, process or service.
"""
from __future__ import annotations

import argparse
import copy
from importlib.metadata import version
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

import install_steve_probe as installer
import prepare_steve_head_basecolor as headbase
import prepare_steve_probe_overlay as helper

native, overlay, orientation, ROOT = helper.native, helper.overlay, helper.orientation, helper.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-head-basecolor-probe-overlay"
DEFAULT_BASELINE = helper.BODY_NATIVE_MATERIAL_OUTPUT
DEFAULT_HEAD_REPORT = headbase.DEFAULT_OUTPUT / headbase.REPORT_NAME
REPORT_NAME = "reports/overlay-report.json"
BASELINE_REPORT_SHA256 = "fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341"
BASELINE_VARIANT = "steve-kliff-original-head-body-material-empty-armor-part-table-v2"
VARIANT = "steve-kliff-original-head-body-material-empty-armor-head-basecolor-part-table-v2"
DIRECTORY_NAME = "0041"
RESOURCE_COUNT = 14
SOURCE_INDEX_COUNT = 34
REPORT_LIMIT = 2 * 1024 * 1024
FILE_LIMIT = overlay.FILE_LIMIT
BASE_REPORT_NAMES = frozenset((
    "steve-assembly-report.json", "steve-appearance-report.json",
    "steve-head-descriptor-report.json", "steve-part-table-report.json",
    "steve-native-head-root-report.json", "steve-head-native-material-report.json",
    "steve-clothing-control-report.json", "steve-body-native-material-report.json",
))
COMPOSITION_REPORT_NAMES = BASE_REPORT_NAMES | {headbase.REPORT_NAME}
PACKAGE_FILES = (f"package/{DIRECTORY_NAME}/0.pamt", f"package/{DIRECTORY_NAME}/0.paz")
METADATA_FILES = ("metadata-before/0.papgt", "metadata-before/0.pathc",
                  "metadata-after/0.papgt", "metadata-after/0.pathc")
PLAN_FILES = frozenset((*PACKAGE_FILES, *METADATA_FILES))
PROTECTED_RELATIVE_DIRS = (
    "build/steve-assembly", "build/steve-appearance", "build/steve-head-descriptor",
    "build/steve-part-table-v2", "build/steve-native-head-root",
    "build/steve-head-native-material", "build/steve-clothing-control",
    "build/steve-body-native-material", "build/steve-head-basecolor",
    "build/steve-probe-overlay", "build/steve-head-descriptor-probe-overlay",
    "build/steve-part-table-v2-probe-overlay", "build/steve-native-head-probe-overlay",
    "build/steve-native-head-root-probe-overlay", "build/steve-head-native-material-probe-overlay",
    "build/steve-clothing-control-probe-overlay", "build/steve-body-native-material-probe-overlay",
)


def report_bytes(report):
    # Preserve the established asset-overlay manifest encoding, including its
    # lack of a final newline. Comparing this also distinguishes bool from int.
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def bounded_read(path, limit=FILE_LIMIT):
    path = native.output_directory(Path(path))
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Local head base-color overlay input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Local head base-color overlay input exceeded its read bound")
    return raw


def merge_snapshot(destination, incoming):
    for path, raw in incoming.items():
        safe = native.output_directory(Path(path))
        if not isinstance(path, Path) or not path.is_absolute() or safe != path:
            raise ValueError("Composition snapshot needs safe absolute Path keys")
        if not isinstance(raw, bytes) or (safe in destination and destination[safe] != raw):
            raise ValueError("Composition source changed between its admitted reads")
        destination[safe] = raw


def fixed_cdmw(source, deps):
    """Admit the existing pinned build-only source, without any download route."""
    source = native.output_directory(Path(source))
    if deps is not None:
        deps = native.output_directory(Path(deps))
    loaded = [(name, module) for name, module in tuple(sys.modules.items())
              if name == "cdmw" or name.startswith("cdmw.")]
    if not loaded:
        return native.load_cdmw(source, deps)
    for _, module in loaded:
        file = getattr(module, "__file__", None)
        if file is None or not native.output_directory(Path(file)).is_relative_to(source):
            raise ValueError("Previously imported CDMW differs from the fixed local source")
    provenance = native.verify_source(source)
    expected = {"lz4": "4.4.5", "cryptography": "50.0.2"}
    if any(version(name) != pinned for name, pinned in expected.items()):
        raise ValueError("Local archive dependency version differs from its fixed pin")
    provenance["archiveDependencies"] = expected
    return provenance


def admitted_report_paths(reports, names):
    if not isinstance(reports, dict) or len(reports) != len(names):
        raise ValueError("Composition needs the exact reviewed report set")
    by_name = {}
    for relative, digest in reports.items():
        path = installer.build_path(relative)
        if (path.name not in names or path.name in by_name
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Composition has unknown, duplicate or malformed candidate provenance")
        by_name[path.name] = path
    if set(by_name) != set(names):
        raise ValueError("Composition candidate report dependencies are incomplete")
    return by_name


def load_baseline(baseline=DEFAULT_BASELINE):
    """Admit one fixed existing body plan and all its six files and upstream bytes."""
    baseline = native.output_directory(Path(baseline))
    report_path = baseline / REPORT_NAME
    raw = bounded_read(report_path, REPORT_LIMIT)
    if native.sha256(raw) != BASELINE_REPORT_SHA256:
        raise ValueError("Head base-color requires the fixed body baseline report SHA")
    report = headbase.strict_json(raw)
    paths = admitted_report_paths(report.get("candidateReports"), BASE_REPORT_NAMES)
    if (set(report.get("files", {})) != PLAN_FILES
            or report.get("directoryName") != DIRECTORY_NAME
            or not isinstance(report.get("sourceIndexes"), dict)
            or len(report["sourceIndexes"]) != SOURCE_INDEX_COUNT
            or report.get("absentOptionalMountedDirectories") != ["0036", "0037", "0038", "0039", "0040"]
            or len(report.get("replacementPaths", ())) != 3):
        raise ValueError("Fixed body baseline inventory differs")
    snapshot = {report_path: raw}
    for relative, digest in report["files"].items():
        path = installer.transaction.target(baseline, relative)
        data = bounded_read(path)
        if native.sha256(data) != digest:
            raise ValueError("Fixed body baseline package or metadata changed")
        snapshot[path] = data
    # This recursive call reaches only the original eight-report body branch.
    # The baseline hash and name set above forbid a nine-report recursion.
    reviewed = installer.load_plan(baseline)
    if (reviewed["reportSha256"] != BASELINE_REPORT_SHA256
            or reviewed["probeVariant"] != BASELINE_VARIANT
            or len(reviewed["payloads"]) != RESOURCE_COUNT
            or reviewed["report"] != report):
        raise ValueError("Fixed body baseline failed its standard pure admission")
    _, inputs, upstream = helper.candidates(
        paths["steve-assembly-report.json"], paths["steve-appearance-report.json"],
        head_descriptor_path=paths["steve-head-descriptor-report.json"],
        part_table_path=paths["steve-part-table-report.json"],
        head_root_path=paths["steve-native-head-root-report.json"],
        head_native_material_path=paths["steve-head-native-material-report.json"],
        clothing_path=paths["steve-clothing-control-report.json"],
        body_native_material_path=paths["steve-body-native-material-report.json"])
    if inputs != report["candidateReports"]:
        raise ValueError("Fixed body baseline candidate inputs changed")
    merge_snapshot(snapshot, upstream)
    pins = ((headbase.MATERIAL_PATH, headbase.OLD_MATERIAL_SHA256),
            (headbase.PAC_PATH, headbase.PRESERVED_PAC_SHA256),
            (headbase.DIFFUSE_PATH, headbase.DIFFUSE_SHA256))
    if any(native.sha256(reviewed["payloads"].get(path, b"")) != digest for path, digest in pins):
        raise ValueError("Fixed body baseline head, PAC or diffuse pin differs")
    orientation.verify_snapshot(snapshot)
    return reviewed, snapshot


def load_head(report_path, baseline):
    report_path = native.output_directory(Path(report_path))
    if report_path.name != headbase.REPORT_NAME:
        raise ValueError("Head base-color composition requires its exact report name")
    candidate, payloads, snapshot = headbase.load_candidate(report_path)
    row, = candidate["candidateResources"]
    if (set(payloads) != {headbase.MATERIAL_PATH}
            or set(row) != {"kind", "virtualPath", "localFile", "sha256", "payloadSize",
                            "sourceVirtualPath", "templatePath", "templateSha256",
                            "templateArchiveFlags", "archiveFlags"}
            or headbase.restore_material(payloads[headbase.MATERIAL_PATH]) != baseline["payloads"][headbase.MATERIAL_PATH]):
        raise ValueError("Head base-color candidate is not the fixed single baseline replacement")
    row = copy.deepcopy(row)
    local = headbase.package_path(report_path.parent, row["localFile"])
    row["localFile"] = str(local.relative_to(ROOT))
    return row, payloads[headbase.MATERIAL_PATH], snapshot


def encoded_entries(package):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data
    package = native.output_directory(Path(package))
    pamt, paz = package / "0.pamt", package / "0.paz"
    rows = parse_archive_pamt(pamt)
    if len(rows) != RESOURCE_COUNT or len({entry.path for entry in rows}) != RESOURCE_COUNT:
        raise ValueError("Local composition archive must contain exactly fourteen unique entries")
    result = {}
    for entry in rows:
        if (native.output_directory(entry.pamt_path) != pamt
                or native.output_directory(entry.paz_file) != paz or entry.paz_index != 0
                or entry.offset % 16 or entry.comp_size <= 0 or entry.orig_size <= 0
                or entry.orig_size > FILE_LIMIT or entry.comp_size > FILE_LIMIT):
            raise ValueError("Local composition entry path, size or storage boundary differs")
        raw = read_archive_entry_raw_data(entry)
        if len(raw) != entry.comp_size:
            raise ValueError("Local composition encoded payload is truncated")
        result[entry.path] = (entry, raw)
    return result


def processed_head(payload):
    from cdmw.services.archive_overlay_install import _processed_payload
    if native.sha256(payload) != headbase.NEW_MATERIAL_SHA256 or len(payload) != headbase.CANDIDATE_SIZE:
        raise ValueError("New head base-color PAMI differs from its fixed byte contract")
    return _processed_payload(payload, compression_type=2, encrypted=True,
                              basename=Path(headbase.MATERIAL_PATH).name)


def build_archive(original, head_payload):
    """The fixed writer over thirteen original encoded slices plus one new PAMI."""
    from cdmw.core.archive_overlay import OverlayFile, build_overlay_archive
    from cdmw.core.archive_format import calculate_pa_checksum
    files = []
    for path, (entry, raw) in original.items():
        if path == headbase.MATERIAL_PATH:
            raw, size, flags = processed_head(head_payload), len(head_payload), 50
        else:
            size, flags = entry.orig_size, entry.flags
        files.append(OverlayFile(path=path, payload=raw, orig_size=size, flags=flags))

    def reference_checksum(data, *, stop_event=None):
        if len(data) > overlay.RESOURCE_LIMIT * FILE_LIMIT:
            raise ValueError("Local composition exceeds the existing rehearsal bound")
        return calculate_pa_checksum(bytes(data))

    with patch("cdmw.core.archive_overlay._payload_checksum", reference_checksum):
        return build_overlay_archive(sorted(files, key=lambda item: item.path))


def metadata_files(before, after):
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or set(before) != set(installer.transaction.METADATA)
            or set(after) != set(installer.transaction.METADATA)
            or any(not isinstance(data, bytes) for data in (*before.values(), *after.values()))):
        raise ValueError("Composition metadata must be the exact two byte-valued files")
    return {"metadata-before/0.papgt": before["meta/0.papgt"],
            "metadata-before/0.pathc": before["meta/0.pathc"],
            "metadata-after/0.papgt": after["meta/0.papgt"],
            "metadata-after/0.pathc": after["meta/0.pathc"]}


def expected_report(baseline, head_report, head_row, package, before, after, payloads):
    """Reconstruct the complete overlay manifest after auditing real package bytes."""
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    from cdmw.core.archive_format import calculate_pa_checksum
    package = native.output_directory(Path(package))
    if package.name != DIRECTORY_NAME or package.parent.name != "package":
        raise ValueError("Composition package must use the fixed reviewed directory layout")
    files = metadata_files(before, after)
    pamt, paz = bounded_read(package / "0.pamt"), bounded_read(package / "0.paz")
    files.update({PACKAGE_FILES[0]: pamt, PACKAGE_FILES[1]: paz})
    if before != baseline["before"] or after["meta/0.pathc"] != baseline["after"]["meta/0.pathc"]:
        raise ValueError("Composition changed original metadata or the existing texture registry")
    expected_after = papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
                                         calculate_pa_checksum(pamt[12:]),
                                         flags=PAPGT_DEFAULT_FLAGS, first=True)
    if after["meta/0.papgt"] != expected_after:
        raise ValueError("Composition PAPGT differs from original metadata plus the new actual PAMT checksum")
    expected_payloads = dict(baseline["payloads"])
    expected_payloads[headbase.MATERIAL_PATH] = headbase.load_candidate(head_report)[1][headbase.MATERIAL_PATH]
    if (not isinstance(payloads, dict) or set(payloads) != set(expected_payloads)
            or any(not isinstance(data, bytes) for data in payloads.values())
            or payloads != expected_payloads):
        raise ValueError("Composition decoded payloads changed outside the one fixed head PAMI")
    report = copy.deepcopy(baseline["report"])
    report["resources"] = [copy.deepcopy(head_row) if row["virtualPath"] == headbase.MATERIAL_PATH
                           else copy.deepcopy(row) for row in report["resources"]]
    report["candidateReports"][str(head_report.relative_to(ROOT))] = native.file_hash(head_report)
    admitted_report_paths(report["candidateReports"], COMPOSITION_REPORT_NAMES)
    report["files"] = {relative: native.sha256(data) for relative, data in files.items()}
    report["mountAudit"] = overlay.audit_mounts(before["meta/0.papgt"], after["meta/0.papgt"], DIRECTORY_NAME, pamt)
    report["packageAudit"] = overlay.audit_package(package, report["resources"], payloads)
    # The before/after PATHC bytes and all three DDS bytes are fixed to the
    # already fully audited baseline. No texture registration is added here.
    original, updated = encoded_entries(baseline["package"]), encoded_entries(package)
    if set(updated) != set(original) or set(updated) != set(payloads):
        raise ValueError("Composition encoded resource set differs from the baseline")
    for path, (old_entry, old_raw) in original.items():
        entry, raw = updated[path]
        if entry.flags != installer.FLAGS[next(row["kind"] for row in report["resources"] if row["virtualPath"] == path)]:
            raise ValueError("Composition storage flags differ from the reviewed kind")
        if path != headbase.MATERIAL_PATH:
            if raw != old_raw or entry.flags != old_entry.flags or entry.orig_size != old_entry.orig_size:
                raise ValueError("Composition changed one of the other thirteen encoded resources")
        elif (old_entry.flags != 50 or entry.flags != 50
              or entry.orig_size != headbase.CANDIDATE_SIZE or raw != processed_head(payloads[path])):
            raise ValueError("Composition head PAMI encoding or flags differ")
    diffuse = [entry for entry, _ in updated.values() if entry.path == headbase.DIFFUSE_PATH]
    if len(diffuse) != 1 or diffuse[0].flags != 0:
        raise ValueError("Composition needs exactly one existing raw complete diffuse DDS")
    rebuilt = build_archive(original, payloads[headbase.MATERIAL_PATH])
    if pamt != rebuilt.pamt_bytes or paz != rebuilt.paz_bytes:
        raise ValueError("Composition archive bytes differ from the complete fixed writer reconstruction")
    return report, files


def validate_composition(report, package, before, after, payloads):
    """Pure fixed-baseline admission after standard Steve decode/audits.

    Returns a read-back snapshot with absolute Path keys. The baseline recursive
    admission is restricted to the pinned eight-report body branch, never nine.
    """
    if not isinstance(report, dict):
        raise ValueError("Head base-color composition report must be an object")
    paths = admitted_report_paths(report.get("candidateReports"), COMPOSITION_REPORT_NAMES)
    baseline, snapshot = load_baseline(DEFAULT_BASELINE)
    head_report = paths[headbase.REPORT_NAME]
    head_row, _, head_snapshot = load_head(head_report, baseline)
    merge_snapshot(snapshot, head_snapshot)
    expected, files = expected_report(baseline, head_report, head_row, package, before, after, payloads)
    if report != expected or report_bytes(report) != report_bytes(expected):
        raise ValueError("Head base-color overlay differs from the complete fixed-baseline reconstruction")
    plan = native.output_directory(Path(package)).parent.parent
    for relative, expected_bytes in files.items():
        path = installer.transaction.target(plan, relative)
        raw = bounded_read(path)
        if raw != expected_bytes:
            raise ValueError("Composition metadata or package changed during admission")
        merge_snapshot(snapshot, {path: raw})
    report_path = installer.transaction.target(plan, REPORT_NAME)
    raw = bounded_read(report_path, REPORT_LIMIT)
    if raw != report_bytes(expected):
        raise ValueError("Composition manifest bytes are not the canonical fixed reconstruction")
    merge_snapshot(snapshot, {report_path: raw})
    orientation.verify_snapshot(snapshot)
    return snapshot


def write_files(output, files):
    output = native.output_directory(Path(output))
    for relative, raw in files.items():
        path = installer.transaction.target(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(path)
        with path.open("xb") as stream:
            stream.write(raw)


def prepare(output=DEFAULT_OUTPUT, baseline=DEFAULT_BASELINE, head_report=DEFAULT_HEAD_REPORT,
            source=ROOT / "build/cdmw-fixed-source", deps=ROOT / "build/cdmw-deps"):
    output = native.output_directory(Path(output))
    baseline = native.output_directory(Path(baseline))
    head_report = native.output_directory(Path(head_report))
    source, deps = native.output_directory(Path(source)), native.output_directory(Path(deps))
    protected = [baseline, DEFAULT_BASELINE, head_report.parent, source, deps,
                 *(ROOT / relative for relative in PROTECTED_RELATIVE_DIRS)]
    if output != native.output_directory(DEFAULT_OUTPUT):
        protected.append(DEFAULT_OUTPUT)
    output = orientation.preflight(output, protected)
    provenance = fixed_cdmw(source, deps)
    reviewed, snapshot = load_baseline(baseline)
    if provenance != reviewed["report"]["cdmw"]:
        raise ValueError("Composition CDMW source or dependencies differ from the fixed baseline")
    head_row, head_payload, head_snapshot = load_head(head_report, reviewed)
    merge_snapshot(snapshot, head_snapshot)
    from cdmw.core.papgt_format import PAPGT_DEFAULT_FLAGS, papgt_with_directory
    original = encoded_entries(reviewed["package"])
    built = build_archive(original, head_payload)
    before = dict(reviewed["before"])
    after = {"meta/0.pathc": reviewed["after"]["meta/0.pathc"],
             "meta/0.papgt": papgt_with_directory(before["meta/0.papgt"], DIRECTORY_NAME,
                                                   built.pamt_checksum, flags=PAPGT_DEFAULT_FLAGS, first=True)}
    payloads = dict(reviewed["payloads"])
    payloads[headbase.MATERIAL_PATH] = head_payload
    writes = metadata_files(before, after)
    writes.update({PACKAGE_FILES[0]: built.pamt_bytes, PACKAGE_FILES[1]: built.paz_bytes})
    orientation.verify_snapshot(snapshot)
    native.verify_source(source)
    with tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="head-basecolor-overlay-stage-") as temporary:
        stage = native.output_directory(Path(temporary))
        write_files(stage, writes)
        report, _ = expected_report(reviewed, head_report, head_row,
                                    stage / "package" / DIRECTORY_NAME, before, after, payloads)
        writes[REPORT_NAME] = report_bytes(report)
        write_files(stage, {REPORT_NAME: writes[REPORT_NAME]})
        staged_snapshot = validate_composition(report, stage / "package" / DIRECTORY_NAME, before, after, payloads)
        orientation.verify_snapshot(staged_snapshot)
        orientation.verify_snapshot(snapshot)
        native.verify_source(source)
        output = orientation.preflight(output, protected)
        output.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(output)
        output.mkdir()  # Never adopt an existing or raced output directory.
        write_files(output, writes)
        published = validate_composition(report, output / "package" / DIRECTORY_NAME, before, after, payloads)
        orientation.verify_snapshot(published)
        orientation.verify_snapshot(staged_snapshot)
        orientation.verify_snapshot(snapshot)
        native.verify_source(source)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--head-basecolor-report", type=Path, default=DEFAULT_HEAD_REPORT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.baseline, args.head_basecolor_report, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "probeVariant": VARIANT,
                      "resources": len(report["resources"]), "candidateReports": len(report["candidateReports"]),
                      "packageAudit": report["packageAudit"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
