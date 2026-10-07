"""Prepare one explicitly selected Macduff app's two private-prefab references.

Only Nude/Prefab Name and Head/Prefab Name change. Every other source byte,
including BOM, CRLF, scales, customization, hair and equipment, is retained.
The selected candidate variant is not evidence of the controlled runtime app.
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
REPORT_NAME = "steve-app-report.json"
REPORT_VARIANT = "steve-direct-app-body-head-reference-probe"
INDEX_SHA256 = "c561ae348ba6dea65b0460686dec089b65291bbbeec439643d42bc5f4ead05b9"
PREFIX = "character/appearance/1_pc/1_phm/cd_phm_macduff/"
VARIANTS = {
    "macduff-00000": {"path": PREFIX+"cd_phm_macduff_00000.app_xml",
                      "sha256": "945e25586db2d50a83b4dd5227ab89a8e5db8c7937abd404470e52ae5b9edffe", "size": 1117, "flags": 48},
    "macduff-00002": {"path": PREFIX+"cd_phm_macduff_00002.app_xml",
                      "sha256": "ec4bde75a0b51269c4c0332832a22e3b7d9d08f0e7181e884914f17ceacd00fe", "size": 665, "flags": 48},
}
REPLACEMENTS = (
    ("Nude", "cd_phm_00_nude_01_0002_macduff", "crimsonmc_steve_body_1_21_1"),
    ("Head", "cd_phm_00_head_00_0001_macduff", "crimsonmc_steve_head_1_21_1"),
)
CUSTOMIZATION = {"CustomizationFile": "cd_pc/cd_phm_macduff_customization", "MeshParamFile": "meshparam_example_kliff.xml",
                 "DecorationParamFile": "decorationparam_player.xml"}
HAIR = ["cd_phm_00_hair_00_0022_player", "cd_phm_00_beard_00_0005_06_player"]
INTEGRATION = {key: False for key in ("installed", "runtimeAppearanceFileSelected", "privatePrefabsLoaded",
    "appearanceApplied", "steveVisible", "actorLocal", "originalHairBeardSuppressed", "animationVerified",
    "equipmentVerified", "restorationVerified")}


def variant_spec(variant):
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise ValueError("Choose exactly macduff-00000 or macduff-00002 explicitly")
    return VARIANTS[variant]


def default_output(variant):
    variant_spec(variant)
    return ROOT/("build/steve-app-"+variant)


def tree_value(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text, node.tail, tuple(tree_value(x) for x in node))


def validate_source(variant, source):
    spec = variant_spec(variant)
    if len(source) != spec["size"] or native.sha256(source) != spec["sha256"]:
        raise ValueError("Selected app source fingerprint differs")
    root = ET.fromstring(source.decode("utf-8-sig"))
    if (root.tag != "Appearance" or root.attrib or [node.tag for node in root] != ["Customization", "Nude", "Head", "Hair", "Armor"]
            or root.find("Customization").attrib != CUSTOMIZATION
            or root.find("Nude/Prefab").attrib != {"Name": REPLACEMENTS[0][1], "CharacterScale": "1.02571"}
            or root.find("Head/Prefab").attrib != {"Name": REPLACEMENTS[1][1], "HeadScale": "0.92"}
            or any(len(root.find(section)) != 1 for section in ("Nude", "Head"))
            or [node.attrib for node in root.findall("Hair/Prefab")] != [{"Name": name} for name in HAIR]):
        raise ValueError("Selected app structural/scale/customization contract differs")
    return root


def build_app(source, variant):
    tree = validate_source(variant, source)
    candidate = source
    for section, old, new in REPLACEMENTS:
        before, after = f'Name="{old}"'.encode(), f'Name="{new}"'.encode()
        if candidate.count(before) != 1 or after in candidate:
            raise ValueError("App replacement is not one unique original Name attribute")
        # The hash-pinned XML proves the unique token belongs to the exact
        # section; replacing its bytes avoids reserializing any unrelated XML.
        candidate = candidate.replace(before, after)
        tree.find(section+"/Prefab").set("Name", new)
    if tree_value(ET.fromstring(candidate.decode("utf-8-sig"))) != tree_value(tree):
        raise ValueError("App rewrite changed unrelated XML semantics")
    restored = candidate
    for _, old, new in REPLACEMENTS:
        restored = restored.replace(f'Name="{new}"'.encode(), f'Name="{old}"'.encode())
    if restored != source:
        raise ValueError("App inverse rewrite is not byte-identical")
    return candidate


def read_source(game, variant):
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    spec = variant_spec(variant)
    exe, index = game/"bin64/CrimsonDesert.exe", game/"0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 index")
    gate()
    entry = native.select_unique_entries(parse_archive_pamt(index), (spec["path"],))[spec["path"]]
    if entry.flags != spec["flags"]:
        raise ValueError("Selected app native storage flags differ")
    native.check_links(Path(entry.paz_file))
    source = _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
    validate_source(variant, source)
    gate()
    return source


def make_report(source, variant):
    spec = variant_spec(variant)
    tree = validate_source(variant, source)
    candidate = build_app(source, variant)
    row = {"virtualPath": spec["path"], "localFile": "replacements/"+spec["path"], "sha256": native.sha256(candidate),
           "kind": "appearanceDefinition", "templatePath": spec["path"], "templateSha256": spec["sha256"],
           "templateArchiveFlags": spec["flags"], "archiveFlags": spec["flags"]}
    return {"schemaVersion": 1, "variant": REPORT_VARIANT, "appearanceVariant": variant,
            "supportedExeSha256": native.EXE_SHA256, "archiveIndexSha256": INDEX_SHA256,
            "candidateResources": [], "targetReplacements": [row], "sourceHashes": {spec["path"]: spec["sha256"]},
            "requiredPrivatePrefabBasenames": [new for _, _, new in REPLACEMENTS],
            "files": {"template/"+spec["path"]: spec["sha256"], row["localFile"]: row["sha256"]},
            "audit": {"changedAttributes": [{"section": section, "element": "Prefab", "attribute": "Name", "before": old, "after": new}
                                              for section, old, new in REPLACEMENTS],
                      "inverseByteIdentical": True, "remainingXmlBytesPreserved": True,
                      "utf8BomPreserved": source.startswith(b"\xef\xbb\xbf"), "crlfPreserved": True,
                      "customizationPreserved": dict(CUSTOMIZATION), "characterScalePreserved": "1.02571",
                      "headScalePreserved": "0.92", "originalHairAndBeardPreserved": list(HAIR),
                      "originalArmorAttributesPreserved": [dict(node.attrib) for node in tree.findall("Armor/Prefab")]},
            "referenceScope": {"explicitOfflineVariant": variant, "onlyReplacementPath": spec["path"],
                "runtimeAppearanceFileSelected": False, "controlledActorOnly": False,
                "scope": "This is one shared app resource replacement. Explicit offline variant selection does not identify the controlled actor's runtime initial Appearance key, and every consumer of this path may observe the replacement."},
            "integration": dict(INTEGRATION),
            "limitations": [
                "Offline candidate only; exactly one of the two known app paths is included per report. No runtime app path is guessed or selected.",
                "Only Nude/Prefab Name and Head/Prefab Name change. BOM, CRLF, scales, customization/meshparam references, hair, equipment and all other source bytes are retained.",
                "The required private prefab, head/body descriptors, meshes, materials and textures are separate reviewed resources, not bundled here.",
                "The original head/body selection in meshparam remains external; this tool does not edit customization choices or trigger refresh/application.",
                "A replaced initial app reference does not establish native private-basename resolution, assembled parts, rendering, animation, equipment fit or restoration.",
                "Hair, beard and armor remain and may obscure the mesh. This shared-resource control is not actor-local persistent Steve mode.",
                "No game files, process, native functions, save, inventory or equipment state are touched. Licensed resources remain in ignored local build."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False)+"\n").encode()


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("App candidate input is absent or exceeds its size limit")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("App candidate changed beyond its size limit")
    return raw


def load_candidate(report_path):
    """Pure admission -> (report, {virtualPath: replacement bytes}, snapshot)."""
    path = native.output_directory(report_path)
    raw_report = bounded_read(path)
    report = strict_json(raw_report)
    variant = report.get("appearanceVariant")
    spec = variant_spec(variant)
    source_path = native.output_directory(path.parent/("template/"+spec["path"]))
    source = bounded_read(source_path, spec["size"])
    validate_source(variant, source)
    expected = make_report(source, variant)
    if report != expected or raw_report != report_bytes(expected):
        raise ValueError("App report differs from the exact selected single-path replacement contract")
    local = native.output_directory(path.parent/expected["targetReplacements"][0]["localFile"])
    payload = bounded_read(local, spec["size"])
    if payload != build_app(source, variant):
        raise ValueError("App payload differs from the exact two-Name rewrite")
    snapshot = {path: raw_report, source_path: source, local: payload}
    orientation.verify_snapshot(snapshot)
    return report, {spec["path"]: payload}, snapshot


def prepare(game, variant, output, source, deps):
    variant_spec(variant)
    protected = [game, source, deps, ROOT/"build/steve-assembly", ROOT/"build/steve-appearance", ROOT/"build/steve-head-descriptor",
                 *(default_output(other) for other in VARIANTS if other != variant)]
    output = orientation.preflight(output, protected)
    native.load_cdmw(source, deps)
    original = read_source(game, variant)
    report = make_report(original, variant)
    candidate = build_app(original, variant)
    native.verify_source(source)
    if read_source(game, variant) != original:
        raise ValueError("Selected native app changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    spec = variant_spec(variant)
    payloads = {"template/"+spec["path"]: original, "replacements/"+spec["path"]: candidate, REPORT_NAME: report_bytes(report)}
    for relative, data in payloads.items():
        path = output/relative
        native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    load_candidate(output/REPORT_NAME)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=tuple(VARIANTS), required=True)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT/"build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT/"build/cdmw-deps")
    args = parser.parse_args()
    installation = ROOT/"runtime/installation.json"
    native.check_links(installation)
    game = args.game_root or Path(json.loads(installation.read_text(encoding="utf-8-sig"))["gameRoot"])
    output = args.output or default_output(args.variant)
    report = prepare(game, args.variant, output, args.cdmw_source, args.deps)
    print(json.dumps({"output": str(output), "appearanceVariant": args.variant, "targetReplacements": report["targetReplacements"],
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
