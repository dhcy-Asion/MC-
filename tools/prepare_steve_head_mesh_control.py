"""Retarget the fixed private CD_Head component to the original native head PAC.

This one-resource offline control changes only the mesh reference and its
required binary lengths/pointers. It is a diagnostic, not a Steve repair.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import prepare_native_steve as native
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT/"build/steve-head-mesh-control"
REPORT_NAME = "steve-head-mesh-control-report.json"
VARIANT = "steve-private-head-native-mesh-reference-control-v1"
TARGET_PATH = "character/bin__/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefab"
TEMPLATE_PATH = "character/bin__/prefab/1_pc/01_phm/head/head/cd_phm_00_head_00_0001_macduff.prefab"
TEMPLATE_SHA256 = "b8bde25e8781391f281d09b8e2bfce17bf99c91325a4215eee1e6df469b1c26e"
SOURCE_SHA256 = "36aef15ab3d1b085846a8b7837ab8108d79073e7379899f85ea69fe5ca2d6df0"
CANDIDATE_SHA256 = "c2d0af7e8bd3b90cc394545c852266356a7f48f0753052d536988698fab01601"
SOURCE_SIZE, CANDIDATE_SIZE = 1918, 1921
SOURCE_MESH = "character/model/1_pc/1_phm/head/head/crimsonmc_steve_head_1_21_1.pac"
NATIVE_MESH = "character/model/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac"
DEFAULT_INPUT = ROOT/"build/steve-assembly/resources"/TARGET_PATH
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
FLAGS = 0
PATH_OFFSET = 1779
# Source offsets and values, independently checked against fixed CDMW's
# complete pointer walk. Fields following the path move three bytes in output.
U32_EDITS = (
    (1665, 1918, 1921, "fileSize"),
    (1685, 229, 232, "blobSize"),
    (1775, 68, 71, "meshPathLength"),
    (1847, 76, 79, "meshPointeeLength"),
    (1866, 1870, 1873, "emptySkeletonPointerTarget"),
    (1913, 178, 181, "componentNamePointeeFooter"),
)
PROTECTED_BUILDS = ("steve-assembly", "steve-parts-prefab", "steve-head-descriptor", "steve-appearance",
                    "steve-part-table", "steve-part-table-v2", "steve-app-macduff-00000", "steve-app-macduff-00002")
INTEGRATION = {key: False for key in ("installed", "nativeHeadMeshResolved", "appearanceApplied",
    "headAlignmentVerified", "animationVerified", "equipmentVerified", "restorationVerified", "steveFixed")}


def validate_source(raw):
    if not isinstance(raw, bytes) or len(raw) != SOURCE_SIZE or native.sha256(raw) != SOURCE_SHA256:
        raise ValueError("Private head prefab source fingerprint differs")
    return raw


def _fixed_rewrite(raw, reverse=False):
    size, digest = (CANDIDATE_SIZE, CANDIDATE_SHA256) if reverse else (SOURCE_SIZE, SOURCE_SHA256)
    if not isinstance(raw, bytes) or len(raw) != size or native.sha256(raw) != digest:
        raise ValueError("Head mesh control input fingerprint differs")
    old, new = (NATIVE_MESH, SOURCE_MESH) if reverse else (SOURCE_MESH, NATIVE_MESH)
    old, new = old.encode("ascii"), new.encode("ascii")
    source_end = PATH_OFFSET+len(SOURCE_MESH)
    delta = CANDIDATE_SIZE-SOURCE_SIZE
    if raw[PATH_OFFSET:PATH_OFFSET+len(old)] != old or raw.count(old) != 1:
        raise ValueError("Head mesh reference is not the one fixed path span")
    result = bytearray(raw)
    for offset, before, after, _ in U32_EDITS:
        at = offset+(delta if reverse and offset >= source_end else 0)
        expected, replacement = (after, before) if reverse else (before, after)
        if struct.unpack_from("<I", raw, at)[0] != expected:
            raise ValueError("Head mesh control fixed length/pointer field differs")
        struct.pack_into("<I", result, at, replacement)
    result[PATH_OFFSET:PATH_OFFSET+len(old)] = new
    payload = bytes(result)
    wanted_size, wanted_digest = (SOURCE_SIZE, SOURCE_SHA256) if reverse else (CANDIDATE_SIZE, CANDIDATE_SHA256)
    if len(payload) != wanted_size or native.sha256(payload) != wanted_digest:
        raise ValueError("Head mesh control output fingerprint differs")
    return payload


def build_prefab(raw):
    """Pure exact-byte builder for only the hash-pinned private head prefab."""
    validate_source(raw)
    candidate = _fixed_rewrite(raw)
    if _fixed_rewrite(candidate, reverse=True) != raw:
        raise ValueError("Head mesh reference inverse is not byte-identical")
    return candidate


def restore_private_prefab(candidate):
    return _fixed_rewrite(candidate, reverse=True)


def verify_cdmw(raw, candidate):
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    from prepare_steve_parts_prefab import contract, strict_layout
    validate_source(raw)
    original, old_footers = strict_layout(raw)
    actual, new_footers = strict_layout(candidate)
    if len(original.objects) != 1 or original.objects[0].name != "CD_Head" or len(actual.objects) != 1:
        raise ValueError("Head control must retain only the original CD_Head component")
    before = contract(original.objects[0])
    if (before["resources"] != [SOURCE_MESH]
            or before["values"] != [("_skinnedMeshFile", SOURCE_MESH), ("_shrinkTag", "Nude"),
                                    ("_modelBoneAnimationScriptKey", "breath_effect_basic")]):
        raise ValueError("Private CD_Head mesh/property contract differs")
    expected = dict(before, resources=[NATIVE_MESH],
                    values=[(key, NATIVE_MESH if key == "_skinnedMeshFile" else value) for key, value in before["values"]])
    if contract(actual.objects[0]) != expected:
        raise ValueError("Head control changed a non-path component property")
    result = rewrite_prefab_paths(raw, {SOURCE_MESH: NATIVE_MESH})
    if (candidate != build_prefab(raw) or result.data != candidate or len(result.edits) != 1
            or result.edits[0].offset != PATH_OFFSET-4 or result.byte_delta != 3 or result.relocated_pointers != 3):
        raise ValueError("Head control differs from the fixed CDMW single-reference rewrite")
    if (rewrite_prefab_paths(raw, {}).data != raw or rewrite_prefab_paths(candidate, {}).data != candidate
            or rewrite_prefab_paths(candidate, {NATIVE_MESH: SOURCE_MESH}).data != raw):
        raise ValueError("Head control CDMW no-edit/inverse round trip differs")
    if old_footers != [{"name": "CD_Head", "nameTarget": 1735, "fieldOffset": 1913, "length": 178}] or new_footers != [
            {"name": "CD_Head", "nameTarget": 1735, "fieldOffset": 1916, "length": 181}]:
        raise ValueError("Head control exact component footer differs")


def make_report(raw):
    candidate = build_prefab(raw)
    row = {"kind": "prefab", "virtualPath": TARGET_PATH, "localFile": "resources/"+TARGET_PATH,
           "sha256": native.sha256(candidate), "templatePath": TEMPLATE_PATH, "templateSha256": TEMPLATE_SHA256,
           "templateArchiveFlags": FLAGS, "archiveFlags": FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
            "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
            "sourcePrivatePrefabSha256": SOURCE_SHA256,
            "files": {"template/"+TARGET_PATH: SOURCE_SHA256, row["localFile"]: CANDIDATE_SHA256},
            "audit": {"only_reference_change": True, "component": "CD_Head", "property": "_skinnedMeshFile",
                      "before": SOURCE_MESH, "after": NATIVE_MESH, "sourceSize": SOURCE_SIZE,
                      "candidateSize": CANDIDATE_SIZE, "pathByteDelta": 3, "componentCount": 1,
                      "nonPathComponentSemanticsPreserved": True, "strictNameFootersVerified": True,
                      "emptySkeletonReferencePreserved": True, "inverseByteIdentical": True,
                      "fixedU32Edits": [{"sourceOffset": at, "before": old, "after": new, "role": role}
                                        for at, old, new, role in U32_EDITS],
                      "crossCheck": {"cdmwCommit": native.CDMW_COMMIT, "pythonSourceTreeSha256": native.CDMW_SOURCE_SHA256,
                                     "singleReferenceRewriteByteIdentical": True, "inverseByteIdentical": True}},
            "externalNativeMesh": {"path": NATIVE_MESH, "payloadIncluded": False, "runtimeResolutionVerified": False},
            "integration": dict(INTEGRATION),
            "limitations": [
                "Diagnostic single-reference control, not a visual fix: only the private CD_Head prefab points back to the original native head PAC.",
                "Its component name, owner token, empty skeleton, shrink fields, breath script and all non-path semantics remain unchanged; six required binary length/pointer fields are updated.",
                "The native PAC and its material/texture dependencies remain external. A result can distinguish the private mesh resource chain from shared assembly, not isolate bone weights from every PAC-dependent feature.",
                "No body, descriptor, PAPPT, meshparam, app, hair, armor, scale, PAC or save is edited or bundled by this candidate.",
                "The containing overlay must explicitly replace its existing private head prefab entry; this is not a second prefab or an installed package.",
                "Offline ignored build only. No game/process access, native calls or restoration/animation/equipment claims."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Head mesh control input is absent or exceeds its size limit")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Head mesh control input changed beyond its size limit")
    return raw


def load_candidate(report_path):
    """Pure admission -> (report, {virtualPath: payload}, snapshot), no CDMW."""
    path = native.output_directory(report_path)
    raw_report = bounded_read(path, 131072)
    report = strict_json(raw_report)
    source_path = native.output_directory(path.parent/("template/"+TARGET_PATH))
    raw = validate_source(bounded_read(source_path, SOURCE_SIZE))
    expected = make_report(raw)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("Head mesh control report/path/flags contract differs")
    target = native.output_directory(path.parent/("resources/"+TARGET_PATH))
    candidate = bounded_read(target, CANDIDATE_SIZE)
    if candidate != build_prefab(raw):
        raise ValueError("Head mesh control payload differs from the exact reference rewrite")
    snapshot = {path: raw_report, source_path: raw, target: candidate}
    orientation.verify_snapshot(snapshot)
    return report, {TARGET_PATH: candidate}, snapshot


def prepare(input_prefab, output, source, deps):
    input_prefab = native.output_directory(input_prefab)
    protected = [input_prefab.parent, source, deps, *(ROOT/"build"/name for name in PROTECTED_BUILDS)]
    output = orientation.preflight(output, protected)
    native.load_cdmw(source, deps)
    raw = validate_source(bounded_read(input_prefab, SOURCE_SIZE))
    snapshot = {input_prefab: raw}
    candidate = build_prefab(raw)
    verify_cdmw(raw, candidate)
    report = make_report(raw)
    native.verify_source(source)
    orientation.verify_snapshot(snapshot)
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, data in {"template/"+TARGET_PATH: raw, "resources/"+TARGET_PATH: candidate,
                           REPORT_NAME: report_bytes(report)}.items():
        path = output/relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    load_candidate(output/REPORT_NAME)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-prefab", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT/"build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT/"build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.input_prefab, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
