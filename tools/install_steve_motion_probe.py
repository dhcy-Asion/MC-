"""Install or restore one strictly reviewed Steve animation visual probe.

The A/B plans preserve the fourteen-resource body plan and add one fixed PAA.
They share the existing active receipt, lock, backups and restoration machinery.
Game writes require an explicit action and a closed, supported game. Removing
this probe preserves later saves; visual effects do not establish MC actions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

import install_asset_probe as transaction
import prepare_steve_motion_probe as motion

native, ROOT = transaction.native, transaction.ROOT
KIND = "steve-motion-visual"
OWNER = "CrimsonMC temporary Steve motion visual probe v1"
BASE_PLAN_REPORT_SHA256 = "69a58b25f314e00a2c44fa1b6d3da86b1b120dbf48d8209fea6bf2c57d914cfb"
TARGET_PATH = "character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa"
ORIGINAL_SHA256 = "b5b5d5aeb0e9751242dbbe5bcf5d7f9f69e4329d08ee6cb8e2ff7d2796218085"
CANDIDATE_SHA256 = "909dd356f6087862e23a37596f4a229b310d87dc8d11ef04e88c8524e554b675"
MOTION_REPORT_NAME = "steve-motion-probe-report.json"
BASELINE_VARIANT = "steve-kliff-original-head-body-material-empty-armor-head-basecolor-head-uv-visible-layer-body-basecolor-part-table-v2"
VARIANTS = {"A": BASELINE_VARIANT + "-motion-original-a-v1",
            "B": BASELINE_VARIANT + "-motion-y5-b-v1"}
BASE_REPORT_NAMES = frozenset({
    "steve-assembly-report.json", "steve-appearance-report.json",
    "steve-head-descriptor-report.json", "steve-part-table-report.json",
    "steve-native-head-root-report.json", "steve-head-native-material-report.json",
    "steve-clothing-control-report.json", "steve-body-native-material-report.json",
    "steve-head-basecolor-report.json", "steve-head-uv-control-report.json",
    "steve-head-visible-layer-report.json", "steve-body-basecolor-report.json",
})
REPORT_LIMIT = 2 * 1024 * 1024


def strict_json(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate motion plan JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError("Non-finite motion plan JSON number")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def load_plan(plan):
    """Admit build-only bytes, with no game, receipt or process access.

    The composer independently reconstructs the complete manifest and package,
    including the unchanged fourteen encoded entries. This wrapper adds the
    transaction envelope checks and rereads the admitted per-call snapshot.
    """
    plan = native.output_directory(Path(plan))
    report_path = transaction.target(plan, "reports/overlay-report.json")
    if not report_path.is_file() or not 0 < report_path.stat().st_size <= REPORT_LIMIT:
        raise ValueError("Motion plan report is missing or oversized")
    raw = report_path.read_bytes()
    if not 0 < len(raw) <= REPORT_LIMIT:
        raise ValueError("Motion plan report exceeded its bound")
    report = strict_json(raw)
    if not isinstance(report, dict):
        raise ValueError("Motion plan report must be an object")
    if (not isinstance(report.get("cdmw"), dict) or report.get("schemaVersion") != 1
            or report.get("supportedExeSha256") != native.EXE_SHA256
            or report.get("cdmw", {}).get("commit") != native.CDMW_COMMIT
            or motion.BASE_PLAN_REPORT_SHA256 != BASE_PLAN_REPORT_SHA256
            or motion.TARGET_PATH != TARGET_PATH or motion.ORIGINAL_SHA256 != ORIGINAL_SHA256
            or motion.CANDIDATE_SHA256 != CANDIDATE_SHA256
            or motion.MOTION_REPORT_NAME != MOTION_REPORT_NAME or motion.VARIANTS != VARIANTS
            or transaction.probe_owner(KIND) != OWNER):
        raise ValueError("Motion probe version or fixed baseline differs")
    name = report.get("directoryName")
    if name != "0041":
        raise ValueError("Motion probe requires the fixed reviewed slot")
    candidates = report.get("candidateReports")
    if not isinstance(candidates, dict) or len(candidates) != 13:
        raise ValueError("Motion probe requires exactly thirteen candidate reports")
    names = []
    for path, digest in candidates.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError("Invalid motion candidate report identity")
        names.append(PurePosixPath(path.replace("\\", "/")).name)
    if (len(set(names)) != 13
            or set(names) != BASE_REPORT_NAMES | {motion.MOTION_REPORT_NAME}):
        raise ValueError("Motion candidate report names differ from the fixed set")
    rows = report.get("resources")
    if not isinstance(rows, list) or len(rows) != 15 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Motion probe requires exactly fifteen resources")
    paths = [row.get("virtualPath") for row in rows]
    if any(not isinstance(path, str) for path in paths) or len(set(paths)) != 15:
        raise ValueError("Motion resource paths are invalid or duplicated")
    clips = [row for row in rows if row.get("kind") == "animationClip"]
    if (len(clips) != 1 or clips[0].get("virtualPath") != motion.TARGET_PATH
            or clips[0].get("templatePath") != motion.TARGET_PATH
            or clips[0].get("templateSha256") != motion.ORIGINAL_SHA256
            or clips[0].get("archiveFlags") != 2
            or clips[0].get("templateArchiveFlags") != 2
            or clips[0].get("payloadSize") != 41592):
        raise ValueError("Motion clip identity, storage flags or size differs")
    wanted = {f"package/{name}/0.pamt", f"package/{name}/0.paz",
              "metadata-before/0.papgt", "metadata-before/0.pathc",
              "metadata-after/0.papgt", "metadata-after/0.pathc"}
    if not isinstance(report.get("files"), dict) or set(report["files"]) != wanted:
        raise ValueError("Motion plan must contain the exact six package/metadata files")
    if not isinstance(report.get("sourceIndexes"), dict) or len(report["sourceIndexes"]) != 34:
        raise ValueError("Motion source index inventory differs")
    replacements = report.get("replacementPaths")
    if (not isinstance(replacements, list) or len(replacements) != 4
            or any(not isinstance(path, str) for path in replacements)
            or len(set(replacements)) != 4 or motion.TARGET_PATH not in replacements):
        raise ValueError("Motion replacement path inventory differs")
    composition = report.get("motionProbeComposition")
    if (not isinstance(composition, dict) or composition.get("schemaVersion") != 1
            or composition.get("baselineReportSha256") != BASE_PLAN_REPORT_SHA256
            or composition.get("onlyAddedReplacementVirtualPath") != motion.TARGET_PATH
            or composition.get("originalPaaSha256") != motion.ORIGINAL_SHA256
            or composition.get("opaquePaaBytes") != 41592
            or composition.get("archiveFlags") != 2
            or composition.get("preservedEncodedResourceCount") != 14):
        raise ValueError("Motion composition differs from the fixed fifteen-resource contract")

    prepared = motion.load_plan(plan)
    if (not isinstance(prepared, dict) or prepared.get("plan") != plan or prepared.get("report") != report
            or prepared.get("reportSha256") != native.sha256(raw)
            or prepared.get("name") != name
            or prepared.get("package") != plan / "package" / name):
        raise ValueError("Motion composer admission disagrees with the transaction envelope")
    variants = VARIANTS
    variant = prepared.get("probeVariant")
    selected = next((key for key, value in variants.items() if value == variant), None)
    if selected is None:
        raise ValueError("Unknown motion probe variant")
    expected_sha = ORIGINAL_SHA256 if selected == "A" else CANDIDATE_SHA256
    if (composition.get("variant") != selected or composition.get("probeVariant") != variant
            or composition.get("replacementPaaSha256") != expected_sha):
        raise ValueError("Motion composition variant or A/B digest differs")
    payloads = prepared.get("payloads")
    if not isinstance(payloads, dict) or set(payloads) != set(paths):
        raise ValueError("Motion admitted payload inventory differs")
    payload = payloads.get(motion.TARGET_PATH)
    if (not isinstance(payload, bytes) or len(payload) != 41592
            or native.sha256(payload) != expected_sha or clips[0].get("sha256") != expected_sha):
        raise ValueError("Motion A/B payload differs from its only permitted digest")
    before, after = prepared.get("before"), prepared.get("after")
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or set(before) != set(transaction.METADATA) or set(after) != set(transaction.METADATA)):
        raise ValueError("Motion admitted metadata inventory differs")
    snapshot = prepared.get("readSnapshot")
    if not isinstance(snapshot, dict) or snapshot.get(report_path) != raw:
        raise ValueError("Motion admission omitted the report snapshot")
    package_bytes = {}
    for basename in ("0.pamt", "0.paz"):
        path = prepared["package"] / basename
        data = snapshot.get(path)
        if (not isinstance(data, bytes) or not data
                or native.sha256(data) != report["files"][f"package/{name}/{basename}"]):
            raise ValueError("Motion admission omitted its exact encoded package snapshot")
        package_bytes[basename] = data
    prepared = {**prepared, "packageBytes": package_bytes}
    verify_snapshot(prepared)
    return prepared


def verify_snapshot(prepared):
    """Reject input drift, including drift during save backups, before writes."""
    snapshot = prepared.get("readSnapshot")
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("Motion admission requires a nonempty per-call snapshot")
    for path, expected in snapshot.items():
        if (not isinstance(path, Path) or not path.is_absolute()
                or native.output_directory(path) != path or not isinstance(expected, bytes)
                or path.read_bytes() != expected):
            raise ValueError("Motion admitted source changed during its final readback")


def verify_state_scope(game, state_root=ROOT):
    state_root = Path(state_root)
    if state_root.resolve() != ROOT.resolve():
        # Isolated checks may use another receipt root only with an explicitly
        # build-owned game copy. A real game never bypasses the project receipt.
        if game is None:
            raise ValueError("Isolated motion restoration requires an explicit build game copy")
        native.output_directory(Path(game))
        native.output_directory(state_root)


def install(plan, game, **kwargs):
    verify_state_scope(game, kwargs.get("state_root", ROOT))
    return transaction.install(plan, game, probe_kind=KIND, **kwargs)


def restore(game=None, **kwargs):
    verify_state_scope(game, kwargs.get("state_root", ROOT))
    return transaction.restore(game, probe_kind=KIND, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true")
    action.add_argument("--restore", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    if args.install and (args.plan is None or args.game_root is None):
        parser.error("--install requires explicit --plan and --game-root")
    native.load_cdmw(args.cdmw_source, args.deps)
    result = install(args.plan, args.game_root) if args.install else restore(args.game_root)
    print(json.dumps({key: result[key] for key in ("status", "directoryName", "backupRoot")}, indent=2))


if __name__ == "__main__":
    main()
