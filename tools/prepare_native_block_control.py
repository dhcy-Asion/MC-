"""Build one of two fixed offline blue asset controls, changing one asset.

The new oak_y prefab key contains the original blue prefab bytes and therefore
still references the original blue PAMI. This tests a new prefab key separately
from oak geometry/material assembly. The material alias instead keeps the oak
prefab and puts original blue PAMI bytes at its new PAMI key. No game is called.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path, PurePosixPath

import prepare_native_block as block
import prepare_native_steve as native

ROOT = native.ROOT
REPORT_NAME = "native-block-report.json"
DEFAULT_VARIANT = "static-oak-log"
VARIANT = "blue-template-alias"
TEMPLATE = block.BIN_BASE + ".prefab"
TARGET = "object/bin__/00_common/system/crimsonmc_oak_log_y.prefab"
TEMPLATE_SHA256 = block.TEMPLATE_HASHES[TEMPLATE]
PURPOSE = ("Read/spawn control for the new oak_y prefab key using the complete original blue prefab "
           "and its original PAMI reference; this is not an oak appearance or collision acceptance.")
MATERIAL_VARIANT = "blue-material-alias"
VARIANTS = {
    VARIANT: {"target": TARGET, "template": TEMPLATE, "sha256": TEMPLATE_SHA256, "length": 1845,
              "resource": "oak_y_prefab", "output": "native-block-blue-alias", "purpose": PURPOSE},
    MATERIAL_VARIANT: {"target": "object/00_common/system/crimsonmc_oak_log_y.pami",
                       "template": block.BASE + ".pami", "sha256": block.TEMPLATE_HASHES[block.BASE + ".pami"],
                       "length": 727, "resource": "oak_y_pami", "output": "native-block-blue-material-alias",
                       "purpose": "Read/spawn control retaining the normal oak_y prefab and replacing only its new PAMI key "
                                  "with the complete original blue PAMI referencing original PAM/DDS; this is not an oak "
                                  "appearance or collision acceptance."},
}
SOURCE_FIELDS = ("schemaVersion", "supportedExeSha256", "cdmw", "archiveIndex", "archiveIndexSha256",
                 "integration", "candidateResources", "files")


class ControlError(ValueError):
    pass


def _probe():
    # Deliberately lazy: resource.load_assets may call validate_control for the
    # control report. Only its separately proved ordinary source is loaded here.
    import probe_native_resources
    return probe_native_resources


def _report_path(path: Path) -> Path:
    lexical = Path(os.path.abspath(path))
    if (not lexical.is_relative_to(ROOT / "build") or lexical == ROOT / "build"
            or lexical.name != REPORT_NAME):
        raise ControlError("Control/source report must be native-block-report.json in ignored build")
    native.check_links(lexical)
    return lexical


def _read(path: Path, maximum=2 * 1024 * 1024) -> bytes:
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ControlError("Control input file is missing, empty or too large: " + str(path))
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if not 0 < len(data) <= maximum:
        raise ControlError("Control input file changed size")
    return data


def _ordinary_source(path: Path, expected_sha256: str | None = None) -> tuple[dict, bytes]:
    path = _report_path(path)
    raw = _read(path)
    if expected_sha256 is not None and native.sha256(raw) != expected_sha256:
        raise ControlError("Ordinary source report SHA256 changed")
    report = _probe().strict_json(raw)
    if "control" in report or report.get("probeVariant", DEFAULT_VARIANT) != DEFAULT_VARIANT:
        raise ControlError("Control source must be an ordinary static-oak-log report, never another control")
    # This checks the actual fixed templates, all 21 source candidate files,
    # all paths, hashes, source pins and integration flags. It makes no HTTP call.
    verified = _probe().load_assets(path)
    if verified["reportSha256"] != native.sha256(raw):
        raise ControlError("Ordinary source changed during verification")
    for spec in VARIANTS.values():
        if verified["resources"][spec["resource"]]["sha256"] == spec["sha256"]:
            raise ControlError("Ordinary source contains a disguised blue asset control")
    return report, raw


def _expected_report(source_path: Path, source: dict, source_raw: bytes, variant: str = VARIANT) -> dict:
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise ControlError("Unknown fixed blue control variant")
    spec = VARIANTS[variant]
    result = {key: copy.deepcopy(source[key]) for key in SOURCE_FIELDS}
    changed = [row for row in result["candidateResources"] if row["virtualPath"] == spec["target"]]
    if len(changed) != 1:
        raise ControlError("Ordinary source lacks its unique fixed control target")
    changed[0]["sha256"] = spec["sha256"]
    result["files"][changed[0]["localFile"]] = spec["sha256"]
    result["probeVariant"] = variant
    result["control"] = {"sourceReport": source_path.relative_to(ROOT).as_posix(),
                         "sourceReportSha256": native.sha256(source_raw), "changedResource": spec["target"],
                         "unchangedCandidateCount": 20, "templateSha256": spec["sha256"],
                         "purpose": spec["purpose"]}
    return result


def _source_reference(value: object) -> Path:
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ControlError("Control sourceReport must be a canonical relative ROOT/build path")
    parts = value.split("/")
    if len(parts) < 3 or parts[0] != "build" or any(part in ("", ".", "..") for part in parts):
        raise ControlError("Control sourceReport must be a canonical relative ROOT/build path")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or parsed.as_posix() != value:
        raise ControlError("Control sourceReport is not canonical")
    path = _report_path(ROOT.joinpath(*parts))
    if path.relative_to(ROOT).as_posix() != value:
        raise ControlError("Control sourceReport casing/path differs")
    return path


def _separate_directories(source: Path, output: Path) -> None:
    if (output == source or output.is_relative_to(source) or source.is_relative_to(output)):
        raise ControlError("Control output must be independent of the entire source asset directory")


def validate_control(report_path: Path, report: dict) -> dict:
    """Validate a saved control and its ordinary source; return control metadata.

    Caller should invoke this whenever probeVariant is in VARIANTS OR a
    control field exists. Missing/other variants are rejected, not normalized.
    This function never calls load_assets on the control (no recursive import).
    """
    report_path = _report_path(report_path)
    saved = _probe().strict_json(_read(report_path))
    if saved != report:
        raise ControlError("Supplied control report differs from its saved report")
    if (not isinstance(report, dict) or not isinstance(report.get("probeVariant"), str)
            or report["probeVariant"] not in VARIANTS or not isinstance(report.get("control"), dict)):
        raise ControlError("Expected an explicit supported blue asset control report")
    variant = report["probeVariant"]
    spec = VARIANTS[variant]
    control = report["control"]
    expected_keys = {"sourceReport", "sourceReportSha256", "changedResource", "unchangedCandidateCount", "templateSha256", "purpose"}
    if set(control) != expected_keys:
        raise ControlError("Control provenance fields differ")
    source_path = _source_reference(control["sourceReport"])
    _separate_directories(source_path.parent, report_path.parent)
    source, raw = _ordinary_source(source_path, control["sourceReportSha256"])
    expected = _expected_report(source_path, source, raw, variant)
    if report != expected:
        raise ControlError("Control report must describe exactly one fixed blue asset change without extra claims")
    changed_candidates = []
    for row in source["candidateResources"]:
        relative = row["localFile"]
        candidate = _read(report_path.parent / relative, 1024 * 1024)
        original = _read(source_path.parent / relative, 1024 * 1024)
        if native.sha256(original) != row["sha256"]:
            raise ControlError("Ordinary source candidate changed after verification")
        if candidate != original:
            changed_candidates.append(row["virtualPath"])
    if changed_candidates != [spec["target"]]:
        raise ControlError("Control candidate byte diff must be exactly the fixed oak_y target")
    for relative, digest in report["files"].items():
        current = _read(report_path.parent / relative, 1024 * 1024)
        if native.sha256(current) != digest:
            raise ControlError("Control template/candidate SHA256 differs: " + relative)
        if relative.startswith("template/") and current != _read(source_path.parent / relative, 1024 * 1024):
            raise ControlError("Control modified an original template")
    alias = _read(report_path.parent / ("candidate/" + spec["target"]))
    template = _read(source_path.parent / ("template/" + spec["template"]))
    if alias != template or len(alias) != spec["length"] or native.sha256(alias) != spec["sha256"]:
        raise ControlError("Control asset must be the complete pinned blue template for its variant")
    if native.sha256(_read(source_path)) != control["sourceReportSha256"]:
        raise ControlError("Ordinary source report changed during control verification")
    return copy.deepcopy(control)


def build_control(source_report: Path, output: Path, variant: str = VARIANT) -> dict:
    """Build an independent control directory, refusing every existing output."""
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise ControlError("Unknown fixed blue control variant")
    spec = VARIANTS[variant]
    source_report = _report_path(source_report)
    source, raw = _ordinary_source(source_report)
    output = native.output_directory(output)
    _separate_directories(source_report.parent, output)
    if output.exists():
        raise ControlError("Control output already exists; previous/foreign products are never overwritten")
    expected = _expected_report(source_report, source, raw, variant)
    payloads = {}
    for relative, digest in source["files"].items():
        data = _read(source_report.parent / relative, 1024 * 1024)
        if native.sha256(data) != digest:
            raise ControlError("Ordinary source file changed before control copy")
        payloads[relative] = data
    payloads["candidate/" + spec["target"]] = payloads["template/" + spec["template"]]
    if len(payloads["candidate/" + spec["target"]]) != spec["length"]:
        raise ControlError("Pinned blue asset length differs for its variant")
    output.parent.mkdir(parents=True, exist_ok=True)
    native.check_links(output)
    output.mkdir()  # Exclusive directory creation, including any raced collision.
    for relative, data in payloads.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(path)
        with path.open("xb") as stream:
            stream.write(data)
    _ordinary_source(source_report, native.sha256(raw))
    saved = output / REPORT_NAME
    native.check_links(saved)
    with saved.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(expected, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    validate_control(saved, expected)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "build/native-block" / REPORT_NAME)
    parser.add_argument("--variant", choices=tuple(VARIANTS), default=VARIANT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = args.output or ROOT / "build" / VARIANTS[args.variant]["output"]
        result = build_control(args.source, output, args.variant)
        print(json.dumps({"probeVariant": result["probeVariant"], "output": str(output),
                          "changedResource": result["control"]["changedResource"], "unchangedCandidateCount": 20, "nativeRenderable": False}))
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        print("Offline control stopped: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
