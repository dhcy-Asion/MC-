"""Prepare one exact reversible Kliff meshparam replacement, without installing.

Only two default-option prefab basenames change. Shared metadata consumers may
all be affected: this is not an actor-local appearance implementation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_native_steve as native
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-appearance"
REPORT_NAME = "steve-appearance-report.json"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
TARGET_PATH = "character/descriptors/customizationmeta/meshparam_example_kliff.xml"
TARGET_SHA256 = "5c35726023151b024bbd10b03481bd0bb2c6c0ba745fcefe68907d20c07e40b5"
REPLACEMENTS = (
    ("cd_phm_00_nude_01_0002_macduff", "crimsonmc_steve_body_1_21_1"),
    ("cd_phm_00_head_00_0001_macduff", "crimsonmc_steve_head_1_21_1"),
)
APPEARANCES = {
    "character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml": "945e25586db2d50a83b4dd5227ab89a8e5db8c7937abd404470e52ae5b9edffe",
    "character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00002.app_xml": "ec4bde75a0b51269c4c0332832a22e3b7d9d08f0e7181e884914f17ceacd00fe",
}
SOURCE_HASHES = {TARGET_PATH: TARGET_SHA256, **APPEARANCES}
GROUPS = (("Body", 2), ("Head", 2), ("Hair", 7), ("Beard", 7), ("Mustache", 0), ("Whiskers", 0), ("Eyebrows", 0))
BASELINE_SELECTED = ["cd_phm_00_nude_01_0002_macduff", "cd_phm_00_head_00_0001_macduff",
                     "cd_phm_00_hair_00_0022_player", "cd_phm_00_beard_00_0005_06_player"]
VARIATIONS = ["1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc", "1_pc/1_phm/head/head/cd_phm_macduff_head_0001.pabc"]


def tree_value(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text, node.tail, tuple(tree_value(x) for x in node))


def build_meshparam(source):
    if native.sha256(source) != TARGET_SHA256:
        raise ValueError("Fixed Kliff meshparam fingerprint mismatch")
    tree = ET.fromstring(source.decode("utf-8-sig"))
    groups = tree.findall("ParamDesc")
    if tree.tag != "MeshParam" or len(groups) != 7:
        raise ValueError("Meshparam group set differs")
    for index, (group, (key, count)) in enumerate(zip(groups, GROUPS)):
        options = group.findall("MeshSet")
        if (group.attrib != {"Index": str(index), "Default": "0", "UIKey": key}
                or len(options) != count or [x.attrib.get("Index") for x in options] != [str(i) for i in range(count)]):
            raise ValueError("Meshparam default/slot/count differs")
        if count and options[0].find("MeshList").attrib.get("MeshFileName") != BASELINE_SELECTED[index]:
            raise ValueError("Meshparam default prefab differs")
        if index < 2 and (options[0].attrib.get("SkeletonVariation") != VARIATIONS[index]
                          or options[0].attrib.get("UseSkeletonVariation") != "True"):
            raise ValueError("Meshparam explicit body/head variation differs")
    candidate = source
    for index, (old, new) in enumerate(REPLACEMENTS):
        before, after = f'MeshFileName="{old}"'.encode(), f'MeshFileName="{new}"'.encode()
        if candidate.count(before) != 1 or after in candidate:
            raise ValueError("Meshparam replacement is not one exact attribute occurrence")
        candidate = candidate.replace(before, after)
        groups[index].find("MeshSet/MeshList").set("MeshFileName", new)
    if tree_value(ET.fromstring(candidate.decode("utf-8-sig"))) != tree_value(tree):
        raise ValueError("Meshparam rewrite changed unrelated XML semantics")
    restored = candidate
    for old, new in REPLACEMENTS:
        restored = restored.replace(f'MeshFileName="{new}"'.encode(), f'MeshFileName="{old}"'.encode())
    if restored != source:
        raise ValueError("Meshparam inverse rewrite is not byte-identical")
    return candidate


def validate_appearance(raw, path):
    if path not in APPEARANCES or native.sha256(raw) != APPEARANCES[path]:
        raise ValueError("Known appearance consumer fingerprint mismatch")
    root = ET.fromstring(raw.decode("utf-8-sig"))
    custom = root.find("Customization")
    if root.tag != "Appearance" or custom is None or custom.attrib.get("MeshParamFile") != Path(TARGET_PATH).name:
        raise ValueError("Known appearance does not reference the Kliff meshparam")
    if (root.find("Nude/Prefab").attrib != {"Name": BASELINE_SELECTED[0], "CharacterScale": "1.02571"}
            or root.find("Head/Prefab").attrib != {"Name": BASELINE_SELECTED[1], "HeadScale": "0.92"}
            or [x.attrib.get("Name") for x in root.findall("Hair/Prefab")] != BASELINE_SELECTED[2:]):
        raise ValueError("Known appearance body/head/hair contract differs")


def read_sources(game):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    for path in (game, exe, index):
        native.check_links(path)
    def gate():
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    selected = native.select_unique_entries(parse_archive_pamt(index), tuple(SOURCE_HASHES))
    result = {}
    for path, entry in selected.items():
        native.check_links(Path(entry.paz_file))
        data = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
        if not 0 < len(data) <= 131072 or native.sha256(data) != SOURCE_HASHES[path]:
            raise ValueError("Native appearance source fingerprint mismatch: " + path)
        result[path] = data
    build_meshparam(result[TARGET_PATH])
    for path in APPEARANCES:
        validate_appearance(result[path], path)
    gate()
    return result


def make_report(candidate):
    row = {"virtualPath": TARGET_PATH, "localFile": "replacements/"+TARGET_PATH,
           "sha256": native.sha256(candidate), "kind": "appearanceMeshParams",
           "templatePath": TARGET_PATH, "templateSha256": TARGET_SHA256}
    return {"schemaVersion": 1, "variant": "steve-kliff-default-body-head-reference-probe",
            "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": INDEX_SHA256,
            "candidateResources": [], "targetReplacements": [row],
            "requiredPrivatePrefabBasenames": [new for _, new in REPLACEMENTS],
            "sourceHashes": SOURCE_HASHES,
            "files": {**{"template/"+path: digest for path, digest in SOURCE_HASHES.items()}, row["localFile"]: row["sha256"]},
            "audit": {"changedAttributes": 2, "inverseByteIdentical": True,
                      "remainingXmlSemanticsPreserved": True, "groupOptionCounts": [count for _, count in GROUPS],
                      "defaultsPreserved": [0]*7, "skeletonVariationsPreserved": VARIATIONS,
                      "originalHairAndBeardPreserved": BASELINE_SELECTED[2:]},
            "referenceScope": {"verifiedAppearanceConsumers": list(APPEARANCES),
                "scope": "This generator rechecks only the exact meshparam and these two fixed appearance consumers. A shared resource replacement can affect every consumer, including other instances using these appearances; no exhaustive actor or other-index enumeration is claimed.",
                "controlledActorOnly": False, "runtimeAppearanceFileSelected": False,
                "priorResearch": "The separate bounded 0009 scan examined 5667 app_xml and five meshparam files, with one malformed NPC XML. It does not prove an exhaustive runtime consumer set."},
            "integration": {key: False for key in ("installed", "privatePrefabsLoaded", "steveVisible", "actorLocal",
                "originalHairBeardSuppressed", "equipmentVerified", "animationVerified", "restorationVerified")},
            "limitations": [
                "Offline candidate only; the two required private prefab/mesh/material/texture chains are separate inputs to the overlay wrapper.",
                "Only default Body and Head MeshFileName attributes change. App XML, armor, all other options, decoration floors and icon paths remain untouched.",
                "Hair and beard remain visible candidates and may obscure Steve; FF means fallback selection, never hide.",
                "Both Body 01_0002 and Head 0001 skeleton variations remain selected. Their merge/application order and external CharacterScale/HeadScale remain unverified.",
                "This is one shared metadata replacement, not an actor-local implementation or persistent Steve mode.",
                "No process, game function, installation, save, inventory or equipment operation is performed."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Candidate input exceeds its bounded file size")
    data = path.read_bytes()
    if not 0 < len(data) <= limit:
        raise ValueError("Candidate input changed beyond its bounded file size")
    return data


def load_candidate(report_path):
    """Pure fixed replacement gate for the separate installer; no CDMW imports."""
    report_path = native.output_directory(report_path)
    raw = bounded_read(report_path, 2*1024*1024)
    report = strict_json(raw)
    snapshot = {report_path: raw}
    sources = {}
    for path, digest in SOURCE_HASHES.items():
        local = native.output_directory(report_path.parent / ("template/"+path))
        data = bounded_read(local)
        if native.sha256(data) != digest:
            raise ValueError("Candidate template fingerprint mismatch")
        snapshot[local] = data
        sources[path] = data
    candidate = build_meshparam(sources[TARGET_PATH])
    for path in APPEARANCES:
        validate_appearance(sources[path], path)
    expected = make_report(candidate)
    if report != expected or raw != report_bytes(expected):
        raise ValueError("Candidate report differs from the one fixed replacement contract")
    local = native.output_directory(report_path.parent / expected["targetReplacements"][0]["localFile"])
    data = bounded_read(local)
    if data != candidate:
        raise ValueError("Candidate payload differs from the exact two-attribute rewrite")
    snapshot[local] = data
    orientation.verify_snapshot(snapshot)
    return report, {TARGET_PATH: data}, snapshot


def prepare(game, output, source, deps):
    output = orientation.preflight(output, [game, source, deps])
    native.load_cdmw(source, deps)
    originals = read_sources(game)
    candidate = build_meshparam(originals[TARGET_PATH])
    report = make_report(candidate)
    if read_sources(game) != originals:
        raise ValueError("Native appearance sources changed before publication")
    native.verify_source(source)
    output = orientation.preflight(output, [game, source, deps])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    payloads = {**{"template/"+p: raw for p, raw in originals.items()},
                "replacements/"+TARGET_PATH: candidate, REPORT_NAME: report_bytes(report)}
    for relative, data in payloads.items():
        path = output / relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    load_candidate(output / REPORT_NAME)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game-root", type=Path)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    p.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    a = p.parse_args()
    installation = ROOT / "runtime/installation.json"
    native.check_links(installation)
    game = a.game_root or Path(json.loads(installation.read_text(encoding="utf-8-sig"))["gameRoot"])
    r = prepare(game, a.output, a.cdmw_source, a.deps)
    print(json.dumps({"output": str(a.output), "targetReplacements": r["targetReplacements"], "integration": r["integration"]}, indent=2))


if __name__ == "__main__":
    main()
