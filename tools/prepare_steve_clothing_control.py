"""Build one reversible empty-Armor control for the fixed Macduff 00000 app.

Only the twelve default Armor/Prefab lines are removed. Original body, head,
hair, customization, scale, BOM and every surviving CRLF byte remain unchanged.
This is a rendering experiment, not dynamic equipment removal or prohibition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_steve_app as app

native, orientation, strict_json = app.native, app.orientation, app.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-clothing-control-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-clothing-control"
VARIANT = "steve-clothing-empty-default-armor-only-v1"
SOURCE_VARIANT = "macduff-00000"
TARGET_PATH = app.VARIANTS[SOURCE_VARIANT]["path"]
TARGET_SHA256 = app.VARIANTS[SOURCE_VARIANT]["sha256"]
TARGET_SIZE = app.VARIANTS[SOURCE_VARIANT]["size"]
INDEX_SHA256 = app.INDEX_SHA256
ARCHIVE_FLAGS = 48
CANDIDATE_SHA256 = "2b172fc5e2287b9cb7afde9c1e03a0842f99d1ed15cd3518ee269f9a42cb17d2"
ARMOR_NAMES = (
    "cd_phm_00_ub_inner_0054", "cd_phm_00_hand_inner_0054", "cd_phm_00_foot_inner_0054",
    "cd_phm_00_cloak_flight_0001", "cd_t0256_hyperspaceplug_0001",
    "cd_phm_00_parthide_00_0000_w", "cd_phm_00_bag_0000_z", "cd_phm_00_bag_belt_0000",
    "cd_phm_00_ub_00_0054", "cd_phm_00_cloak_00_0054_s", "cd_phm_00_hand_0054",
    "cd_phm_00_foot_0054",
)
INTEGRATION = {key: False for key in (
    "installed", "runtimeAppearanceFileSelected", "emptyArmorEngineLoadVerified",
    "defaultClothingSuppressed", "dynamicEquipmentSuppressed", "equipmentProhibited",
    "appearanceApplied", "steveVisible", "actorLocal", "restorationVerified")}


def armor_block(source):
    tree = app.validate_source(SOURCE_VARIANT, source)
    armor = tree.find("Armor")
    expected = [{"Name": name, **({"Preview": "true"} if index >= 8 else {})}
                for index, name in enumerate(ARMOR_NAMES)]
    if (armor is None or armor.attrib or len(armor) != 12
            or any(node.tag != "Prefab" or len(node) for node in armor)
            or [node.attrib for node in armor] != expected):
        raise ValueError("Clothing control requires the exact twelve original Armor Prefabs")
    begin, end = b"\t<Armor>\r\n", b"\t</Armor>"
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError("Clothing control Armor byte boundaries are not unique")
    start = source.index(begin) + len(begin)
    stop = source.index(end, start)
    removed = source[start:stop]
    if (start != 499 or stop != 1093 or len(removed.splitlines(keepends=True)) != 12
            or any(not line.startswith(b"\t\t<Prefab ") or not line.endswith(b"/>\r\n")
                   for line in removed.splitlines(keepends=True))):
        raise ValueError("Clothing control removal is not the exact original Armor line block")
    return tree, start, stop, removed


def build_app(source):
    tree, start, stop, removed = armor_block(source)
    candidate = source[:start] + source[stop:]
    decoded = ET.fromstring(candidate)
    armor = decoded.find("Armor")
    if armor is None or armor.attrib or len(armor) != 0:
        raise ValueError("Clothing control must retain one empty Armor element")
    if any(ET.tostring(a) != ET.tostring(b) for a, b in zip(tree, decoded) if a.tag != "Armor"):
        raise ValueError("Clothing control changed an element outside Armor")
    if (len(candidate) != 523 or native.sha256(candidate) != CANDIDATE_SHA256
            or candidate[:start] + removed + candidate[start:] != source):
        raise ValueError("Clothing control fixed payload or byte-identical inverse differs")
    return candidate


def make_report(source):
    tree, start, stop, removed = armor_block(source)
    candidate = build_app(source)
    row = {"virtualPath": TARGET_PATH, "localFile": "replacements/" + TARGET_PATH,
           "sha256": CANDIDATE_SHA256, "kind": "appearanceDefinition", "templatePath": TARGET_PATH,
           "templateSha256": TARGET_SHA256, "templateArchiveFlags": ARCHIVE_FLAGS,
           "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "appearanceVariant": SOURCE_VARIANT,
        "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": INDEX_SHA256,
        "candidateResources": [], "targetReplacements": [row], "sourceHashes": {TARGET_PATH: TARGET_SHA256},
        "files": {"template/" + TARGET_PATH: TARGET_SHA256, row["localFile"]: CANDIDATE_SHA256},
        "audit": {"changedSection": "Armor", "removedPrefabCount": 12,
            "removedRegularPrefabCount": 8, "removedPreviewPrefabCount": 4,
            "removedPrefabAttributes": [dict(node.attrib) for node in tree.find("Armor")],
            "removedByteRange": [start, stop], "removedBytes": len(removed),
            "removedBlockSha256": native.sha256(removed), "sourceBytes": len(source),
            "candidateBytes": len(candidate), "emptyArmorElementRetained": True,
            "outsideArmorBytesPreserved": True, "inverseByteIdentical": True,
            "utf8BomPreserved": True, "remainingCrlfBytesPreserved": True,
            "customizationPreserved": dict(app.CUSTOMIZATION), "characterScalePreserved": "1.02571",
            "headScalePreserved": "0.92", "bodyHeadNamesPreserved": [old for _, old, _ in app.REPLACEMENTS],
            "originalHairAndBeardPreserved": list(app.HAIR)},
        "referenceScope": {"onlyReplacementPath": TARGET_PATH, "controlledActorOnly": False,
            "runtimeAppearanceFileSelected": False, "staticDefaultArmorOnly": True,
            "dynamicEquipmentStateDecoded": False,
            "scope": "One shared Macduff 00000 initial appearance resource. Every consumer may observe its empty default Armor section; dynamic equipped parts may still be applied independently."},
        "integration": dict(INTEGRATION), "limitations": [
            "Offline reversible rendering experiment. Empty Armor engine loading and clothing visibility require a separate in-game trial.",
            "Only the twelve static default Armor Prefabs (eight regular, four Preview) are removed. Existing equipment identities and dynamic equipped part selection are not decoded or changed.",
            "Original Nude, Head, Hair, Customization and scales remain byte-identical. This control does not claim complete original/Steve model deduplication or hair suppression.",
            "The separately reviewed Steve thirteen-resource plan is not built or verified by this tool; all thirteen payloads must remain unchanged when adding this single app replacement.",
            "This is a shared appearance override, not an actor-local or persistent Steve implementation. It does not prohibit original equipment or delete any inventory/save equipment.",
            "No process, native function, installation, service, inventory or save is accessed or changed. Original game archive reads are gated and read-only; derived resources stay in ignored build."]}


def report_bytes(report):
    return app.report_bytes(report)


def package_path(base, relative):
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Clothing control input escapes its package")
    return path


def load_candidate(report_path):
    """Pure admission -> (report, {fixed app virtualPath: bytes}, Path-key snapshot)."""
    path = native.output_directory(report_path)
    raw_report = app.bounded_read(path)
    report = strict_json(raw_report)
    source_path = package_path(path.parent, "template/" + TARGET_PATH)
    source = app.bounded_read(source_path, TARGET_SIZE)
    expected = make_report(source)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("Clothing control report differs from the exact fixed-source contract")
    local = package_path(path.parent, expected["targetReplacements"][0]["localFile"])
    payload = app.bounded_read(local, 523)
    if payload != build_app(source):
        raise ValueError("Clothing control payload differs from the exact Armor byte deletion")
    snapshot = {path: raw_report, source_path: source, local: payload}
    orientation.verify_snapshot(snapshot)
    return report, {TARGET_PATH: payload}, snapshot


def read_source(game):
    return app.read_source(game, SOURCE_VARIANT)


def prepare(output=DEFAULT_OUTPUT, source=ROOT / "build/cdmw-fixed-source",
            deps=ROOT / "build/cdmw-deps", game=None):
    protected = [source, deps, ROOT / "build/steve-assembly", ROOT / "build/steve-appearance",
                 ROOT / "build/steve-head-descriptor", ROOT / "build/steve-part-table-v2",
                 ROOT / "build/steve-head-native-material", ROOT / "build/steve-head-native-material-probe-overlay",
                 *(app.default_output(variant) for variant in app.VARIANTS)]
    if game is not None:
        protected.append(game)
    output = orientation.preflight(output, protected)
    if game is None:
        installation = ROOT / "runtime/installation.json"
        native.check_links(installation)
        game = Path(json.loads(installation.read_text(encoding="utf-8-sig"))["gameRoot"])
        protected.append(game)
    output = orientation.preflight(output, protected)
    native.load_cdmw(source, deps)
    original = read_source(game)
    report, candidate = make_report(original), build_app(original)
    native.verify_source(source)
    if read_source(game) != original:
        raise ValueError("Original clothing app changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    writes = {"template/" + TARGET_PATH: original, "replacements/" + TARGET_PATH: candidate,
              REPORT_NAME: report_bytes(report)}
    for relative, data in writes.items():
        path = package_path(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    load_candidate(output / REPORT_NAME)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.cdmw_source, args.deps, args.game_root)
    print(json.dumps({"output": str(args.output), "targetReplacements": report["targetReplacements"],
                      "removedPrefabCount": report["audit"]["removedPrefabCount"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
