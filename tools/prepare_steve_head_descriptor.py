"""Copy the fixed native HeadPrefabData to Steve's private head basename.

One new resource, byte-for-byte: a bounded missing-companion control, not proof
that the engine requires it or that it explains the unchanged first appearance.
The previous assembly and meshparam candidates are not modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

import prepare_native_steve as native
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-head-descriptor"
REPORT_NAME = "steve-head-descriptor-report.json"
VARIANT = "steve-private-head-native-descriptor-control"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
SOURCE_PATH = "character/prefab/1_pc/01_phm/head/head/cd_phm_00_head_00_0001_macduff.prefabdata_xml"
TARGET_PATH = "character/prefab/1_pc/01_phm/head/head/crimsonmc_steve_head_1_21_1.prefabdata_xml"
SOURCE_PREFAB = SOURCE_PATH.replace("/prefab/", "/bin__/prefab/", 1).replace(".prefabdata_xml", ".prefab")
TARGET_PREFAB = TARGET_PATH.replace("/prefab/", "/bin__/prefab/", 1).replace(".prefabdata_xml", ".prefab")
SOURCE_SHA256 = "d69be68d7e5592b40c601f98899465a69694eeff7213809b0063217a9faee56b"
SOURCE_SIZE = 466
FLAGS = 48
FIELDS = [
    ("SkeletonVariationName", {"FileName": "1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"}),
    ("FacialAnimationIntensityMask", {"FileName": "bonemask_macduff.xml"}),
    ("FacialAnimationMask", {"FileName": "faceblendmask_base.xml"}),
    ("MorphTargetSet", {"FileName": "1_pc/1_phm/phm_kliff.pamt"}),
    ("SkeletonMorphMask", {"FileName": "morphmask_base.xml"}),
    ("EmotionAnimationSet", {"Name": "CD_Macduff_Emotion"}),
    ("FacialBlendShapeSet", {"SkeletonPath": "1_pc/1_phm/phm_01.pab"}),
]
REFERENCE_PATHS = {
    "SkeletonVariationName": "character/binary/skeletonvariation/1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc",
    "FacialAnimationIntensityMask": "character/descriptors/bonemask/bonemask_macduff.xml",
    "FacialAnimationMask": "character/descriptors/bonemask/faceblendmask_base.xml",
    "MorphTargetSet": "character/model/1_pc/1_phm/phm_kliff.pamt",
    "SkeletonMorphMask": "character/descriptors/bonemask/morphmask_base.xml",
    "FacialBlendShapeSet": "character/model/1_pc/1_phm/phm_01.pab",
}
INTEGRATION = {key: False for key in ("installed", "descriptorLoadVerified", "appearanceApplied",
    "headVisible", "animationVerified", "equipmentVerified", "restorationVerified")}


def descriptor_fields(raw):
    root = ET.fromstring(raw.decode("utf-8-sig"))
    rows = [(node.tag, dict(node.attrib)) for node in root]
    if root.tag != "HeadPrefabData" or root.attrib or rows != FIELDS or any(len(node) for node in root):
        raise ValueError("Head descriptor fields differ from the seven original fields")
    return rows


def validate_source(raw):
    if len(raw) != SOURCE_SIZE or native.sha256(raw) != SOURCE_SHA256:
        raise ValueError("Head descriptor source fingerprint differs")
    descriptor_fields(raw)
    return raw


def read_source(game):
    """Extract exactly the fixed descriptor and verify native index relationships."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    wanted = (SOURCE_PATH, SOURCE_PREFAB, *REFERENCE_PATHS.values())
    entries = native.select_unique_entries(parse_archive_pamt(index), wanted)
    entry = entries[SOURCE_PATH]
    if entry.flags != FLAGS:
        raise ValueError("Head descriptor native storage flags differ")
    native.check_links(Path(entry.paz_file))
    raw = validate_source(_decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0])
    gate()
    return raw


def make_report(raw):
    validate_source(raw)
    source_base = PurePosixPath(SOURCE_PREFAB).stem
    target_base = PurePosixPath(TARGET_PREFAB).stem
    if (SOURCE_PATH != SOURCE_PREFAB.replace("/bin__/", "/", 1).replace(".prefab", ".prefabdata_xml")
            or TARGET_PATH != TARGET_PREFAB.replace("/bin__/", "/", 1).replace(".prefab", ".prefabdata_xml")):
        raise ValueError("Head descriptor is not the exact prefab companion path")
    row = {"kind": "prefabDescriptor", "virtualPath": TARGET_PATH, "localFile": "resources/"+TARGET_PATH,
           "sha256": SOURCE_SHA256, "templatePath": SOURCE_PATH, "templateSha256": SOURCE_SHA256,
           "templateArchiveFlags": FLAGS, "archiveFlags": FLAGS}
    external = []
    for field, attrs in FIELDS:
        reference = {"field": field, "attributes": dict(attrs), "payloadIncluded": False,
                     "runtimeResolutionVerified": False}
        if field in REFERENCE_PATHS:
            reference.update(nativePath=REFERENCE_PATHS[field], originalIndexContainsPath=True, payloadHashVerified=False)
        else:
            reference.update(nativePath=None, interpretation="Named animation set; no same-name file path inferred")
        external.append(reference)
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
            "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
            "files": {"template/"+SOURCE_PATH: SOURCE_SHA256, row["localFile"]: SOURCE_SHA256},
            "audit": {"sourceSize": SOURCE_SIZE, "byteIdenticalCopy": True,
                      "sourceAndTargetBasenames": [source_base, target_base],
                      "sourcePrefab": SOURCE_PREFAB, "targetPrefab": TARGET_PREFAB,
                      "rootTag": "HeadPrefabData", "fields": [[tag, attrs] for tag, attrs in FIELDS],
                      "externalReferences": external, "nativeNecessityOrFallbackBehaviorProven": False},
            "mappingEvidence": {"cdmwCommit": native.CDMW_COMMIT, "pythonSourceTreeSha256": native.CDMW_SOURCE_SHA256,
                "source": "cdmw/core/archive_relationships.py:_candidate_basenames_for_xml_reference",
                "rule": "Name references enumerate both basename.prefab and basename.prefabdata_xml; app relationship expansion follows prefab_data references",
                "nativeEvidence": "Fixed 0009 contains the original Head0001 prefab and same-basename descriptor with seven HeadPrefabData fields",
                "nativeResolverABIOrMandatoryRequirementVerified": False},
            "integration": dict(INTEGRATION),
            "limitations": [
                "One missing-companion control only; original descriptor bytes, encoding, line endings and all seven references are preserved.",
                "Observed same-basename native files and CDMW relationship expansion do not prove this descriptor is mandatory or explains the unchanged appearance.",
                "This tool does not change the ten-resource assembly, appearance meshparam, app XML, prefab, PAC, material, texture, scale, skeleton fields or user saves.",
                "The six indexed file references and named EmotionAnimationSet remain external. Their runtime loading, morph/facial behavior and Steve fit are unverified.",
                "The prior user observation was an unchanged original character, not evidence that Steve was transparent. Actual private-prefab application and display remain separate checks.",
                "Offline licensed resources remain in ignored build. No installation, process access or native calls are performed."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Head descriptor input is absent or exceeds its size limit")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Head descriptor input changed beyond its size limit")
    return raw


def load_candidate(report_path):
    """Pure admission -> (report, payloads by relative path, snapshot), no CDMW."""
    path = native.output_directory(report_path)
    raw_report = bounded_read(path, 131072)
    report = strict_json(raw_report)
    source_path = native.output_directory(path.parent / ("template/"+SOURCE_PATH))
    source = validate_source(bounded_read(source_path, SOURCE_SIZE))
    expected = make_report(source)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("Head descriptor report/path/flags contract differs")
    target = native.output_directory(path.parent / ("resources/"+TARGET_PATH))
    payload = bounded_read(target, SOURCE_SIZE)
    if payload != source:
        raise ValueError("Head descriptor candidate is not the original source bytes")
    snapshot = {path: raw_report, source_path: source, target: payload}
    orientation.verify_snapshot(snapshot)
    return report, {"template/"+SOURCE_PATH: source, "resources/"+TARGET_PATH: payload}, snapshot


def prepare(game, output, source, deps):
    protected = [game, source, deps, ROOT/"build/steve-assembly", ROOT/"build/steve-appearance",
                 ROOT/"build/steve-parts", ROOT/"build/steve-parts-prefab", ROOT/"build/steve-current-rig"]
    output = orientation.preflight(output, protected)
    native.load_cdmw(source, deps)
    raw = read_source(game)
    report = make_report(raw)
    native.verify_source(source)
    if read_source(game) != raw:
        raise ValueError("Head descriptor archive source changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for relative, data in {"template/"+SOURCE_PATH: raw, "resources/"+TARGET_PATH: raw, REPORT_NAME: report_bytes(report)}.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    load_candidate(output / REPORT_NAME)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT/"build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT/"build/cdmw-deps")
    args = parser.parse_args()
    installation = ROOT/"runtime/installation.json"
    native.check_links(installation)
    game = args.game_root or Path(json.loads(installation.read_text(encoding="utf-8-sig"))["gameRoot"])
    report = prepare(game, args.output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
