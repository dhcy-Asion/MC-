"""Build one byte-identical native-body PAMI control for the Steve body.

Native textures are intentional for the left-hand/material diagnostic. The
current compensated body PAC, empty Armor and all other thirteen resources in
the separate fourteen-resource clothing package must remain unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_steve_assembly as assembly

native, orientation = assembly.native, assembly.orientation
strict_json = assembly.current.prefab.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-body-native-material-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-body-native-material"
VARIANT = "steve-body-native-material-only-v1"
MATERIAL_PATH = assembly.parts.MATERIAL_PATHS["body"]
PAC_PATH = assembly.parts.PAC_PATHS["body"]
NATIVE_MATERIAL_PATH = "character/modelproperty/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac_xml"
NATIVE_MATERIAL_SHA256 = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
NATIVE_MATERIAL_SIZE = 50017
OLD_MATERIAL_SHA256 = "01f17ad65bf24e4d8ce59bec0de2c9d3cf570992101a67ac2e0ac94ce52d0538"
PRESERVED_PAC_SHA256 = "8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537"
ASSEMBLY_REPORT_SHA256 = "2f167887d0abcae102f293d98f34c6421b52d7b5153eb1b9393e2d6da57b8f33"
INDEX_SHA256 = assembly.private.INDEX_SHA256
ARCHIVE_FLAGS = 50
DEFAULT_ASSEMBLY_REPORT = assembly.DEFAULT_OUTPUT / assembly.REPORT_NAME
SOURCE_SPECS = {
    "nativeMaterial": ("template/" + NATIVE_MATERIAL_PATH, NATIVE_MATERIAL_SHA256),
    "previousMaterial": ("provenance/previous/" + MATERIAL_PATH, OLD_MATERIAL_SHA256),
    "preservedPac": ("provenance/preserved/" + PAC_PATH, PRESERVED_PAC_SHA256),
    "assemblyReport": ("provenance/" + assembly.REPORT_NAME, ASSEMBLY_REPORT_SHA256),
}
SOURCE_LIMITS = {"nativeMaterial": 50017, "previousMaterial": 23893,
                 "preservedPac": 236594, "assemblyReport": 131072}
DRAW_NAMES = ("cd_phm_00_head_0001_01", "cd_phm_00_nude_0001_hand", "cd_phm_00_nude_0001")
PARAMETER_COUNTS = ((10, 12, 9), (9, 11, 9), (10, 12, 10),
                    (4, 4, 9), (9, 12, 10), (10, 12, 10))
NONE_TEXTURE_PATH = "texture/nonetexture0xffffffff.dds"
WRINKLE_PATH = "character/descriptors/wrinkle/cd_phm_00_nude_00_0001.pac.wrinkle.xml"
TEXTURE_PATHS = (
    "character/texture/cd_phm_00_head_0001_01_caliburn_dm01.dds",
    "character/texture/cd_phm_00_head_0001_01_caliburn_dm_sp.dds",
    "character/texture/cd_phm_00_head_00_0001_01.dds",
    "character/texture/cd_phm_00_head_00_0001_01_m.dds",
    "character/texture/cd_phm_00_head_00_0001_01_n.dds",
    "character/texture/cd_phm_00_head_00_0001_01_sp.dds",
    "character/texture/cd_phm_00_head_01_0001_01_n.dds",
    "character/texture/cd_phm_00_nude_00_0001.dds",
    "character/texture/cd_phm_00_nude_00_0001_hand.dds",
    "character/texture/cd_phm_00_nude_00_0001_hand_disp.dds",
    "character/texture/cd_phm_00_nude_00_0001_hand_m.dds",
    "character/texture/cd_phm_00_nude_00_0001_hand_n.dds",
    "character/texture/cd_phm_00_nude_00_0001_hand_sp.dds",
    "character/texture/cd_phm_00_nude_00_0001_m.dds",
    "character/texture/cd_phm_00_nude_00_0001_n.dds",
    "character/texture/cd_phm_00_nude_00_0001_sp.dds",
    "character/texture/cd_phm_00_nude_01_0001_hand_n.dds",
    "character/texture/cd_phm_00_nude_01_0001_n.dds",
    "character/texture/cd_texturelayer_damaged_head_scar_sp.dds",
    "character/texture/cd_texturelayer_damaged_scar_sp.dds",
    "character/texture/cd_texturelayer_skin_0001_n.dds",
    "character/texture/cd_texturelayer_skin_0001_sp.dds",
)
DEPENDENCY_FLAGS = {**{path: 1 for path in TEXTURE_PATHS}, WRINKLE_PATH: 50}
INTEGRATION = {key: False for key in (
    "installed", "appearanceApplied", "leftHandVisibilityVerified", "bodyAlignmentVerified",
    "animationVerified", "equipmentVerified", "partShrinkVerified", "restorationVerified",
    "nativeShaderSemanticsProven", "steveFixed")}


def fixed(raw, expected, name):
    if not isinstance(raw, bytes) or native.sha256(raw) != expected:
        raise ValueError("Native-body material fixed input differs: " + name)
    return raw


def material_audit(raw):
    """Read the exact native six-by-three contract without serializing its XML."""
    fixed(raw, NATIVE_MATERIAL_SHA256, "original native PAMI")
    if len(raw) != NATIVE_MATERIAL_SIZE:
        raise ValueError("Native-body original PAMI size differs")
    root = ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")
    common = root.findall("SkinnedMeshPropertyCommon")
    if len(common) != 1 or common[0].attrib != {
            "ReflectObjectXMLDataVersion": "9", "_wrinkleFileName": WRINKLE_PATH}:
        raise ValueError("Native-body wrinkle common metadata differs")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 6 or len(root.findall(".//SkinnedMeshMaterialWrapper")) != 18:
        raise ValueError("Native-body PAMI must retain six variants with three draws")
    rows, paths = [], set()
    for index, variant in enumerate(variants):
        if variant.attrib != {"Index": str(index), "Version": "Reflection"}:
            raise ValueError("Native-body variant identity differs")
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        if len(wrappers) != 3 or tuple(w.get("_subMeshName") for w in wrappers) != DRAW_NAMES:
            raise ValueError("Native-body material draw mapping differs")
        draw_rows = []
        for draw, wrapper in enumerate(wrappers):
            material = wrapper.find("Material")
            if material is None or material.attrib != {
                    "Name": "_resourceMaterial", "_materialName": "SkinnedMeshSkin"}:
                raise ValueError("Original native-body shader differs")
            parameters = [p for p in material.iter() if p.tag.startswith("MaterialParameter")]
            if len(parameters) != PARAMETER_COUNTS[index][draw]:
                raise ValueError("Original native-body parameter count differs")
            textures = []
            for parameter in parameters:
                if parameter.tag != "MaterialParameterTexture":
                    continue
                references = parameter.findall("ResourceReferencePath_ITexture")
                if len(references) != 1 or not references[0].get("_path"):
                    raise ValueError("Native-body texture reference is ambiguous")
                path = references[0].get("_path")
                paths.add(path)
                textures.append({"name": parameter.get("_name"), "path": path})
            draw_rows.append({"wrapper": dict(wrapper.attrib), "shader": "SkinnedMeshSkin",
                "parameterCount": len(parameters), "parameters": [
                    {"tag": p.tag, "attributes": dict(p.attrib)} for p in parameters], "textures": textures})
        rows.append({"variant": dict(variant.attrib), "draws": draw_rows})
    if paths != set(TEXTURE_PATHS) | {NONE_TEXTURE_PATH}:
        raise ValueError("Native-body bounded texture dependency set differs")
    return {"sourceBytes": len(raw), "candidateBytes": len(raw), "originalBytesPreserved": True,
        "variantCount": 6, "drawsPerVariant": 3, "drawNames": list(DRAW_NAMES),
        "shader": "SkinnedMeshSkin", "parameterCounts": [list(row) for row in PARAMETER_COUNTS],
        "nativeTexturesAndWrinkleReferencesUnchanged": True, "variants": rows}


def make_report(sources):
    """Reconstruct the whole deterministic manifest from four fixed byte inputs."""
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Native-body material source collection differs")
    for key, (_, expected) in SOURCE_SPECS.items():
        fixed(sources[key], expected, key)
    audit = material_audit(sources["nativeMaterial"])
    previous = strict_json(sources["assemblyReport"])
    previous_rows = {row["virtualPath"]: row for row in previous["candidateResources"]}
    if (previous_rows[MATERIAL_PATH]["sha256"] != OLD_MATERIAL_SHA256
            or previous_rows[PAC_PATH]["sha256"] != PRESERVED_PAC_SHA256):
        raise ValueError("Fixed assembly report does not bind the reviewed body PAC/PAMI")
    row = {"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH,
        "localFile": "resources/" + MATERIAL_PATH, "sha256": NATIVE_MATERIAL_SHA256,
        "payloadSize": NATIVE_MATERIAL_SIZE, "sourceVirtualPath": NATIVE_MATERIAL_PATH,
        "templatePath": NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_MATERIAL_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": relative, "sha256": digest, "payloadSize": len(sources[key])}
                    for key, (relative, digest) in SOURCE_SPECS.items()},
        "files": {**{relative: digest for relative, digest in SOURCE_SPECS.values()},
                  row["localFile"]: NATIVE_MATERIAL_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": MATERIAL_PATH,
            "previousMaterialSha256": OLD_MATERIAL_SHA256,
            "replacementMaterialSha256": NATIVE_MATERIAL_SHA256,
            "preservedPacVirtualPath": PAC_PATH, "preservedPacSha256": PRESERVED_PAC_SHA256,
            "otherThirteenResourcesMustBeByteIdentical": True, "emptyArmorMustRemainUnchanged": True,
            "wholePackageVerifiedByThisTool": False},
        "dependencyContract": {"originalIndexSha256": INDEX_SHA256,
            "originalIndexEntryAdmissionRequired": True,
            "textureEntries": [{"virtualPath": path, "archiveFlags": 1} for path in TEXTURE_PATHS],
            "wrinkleEntry": {"virtualPath": WRINKLE_PATH, "archiveFlags": 50},
            "noneTextureSentinel": {"path": NONE_TEXTURE_PATH, "originalBytesPreserved": True,
                                    "archiveEntryRequired": False, "runtimeResolutionVerified": False},
            "requiredDependencyEntries": 23, "dependencyPayloadsDecoded": False,
            "candidateDependencyOverrides": [], "nativeShaderSemanticsProven": False},
        "audit": audit, "integration": dict(INTEGRATION), "limitations": [
            "Offline single-PAMI control; construction is not left-hand visibility, body alignment, animation, part-shrink or shader validation.",
            "The original native-body PAMI retains six variants, three draw names, SkinnedMeshSkin, complete parameters, wrapper metadata, native textures and wrinkle reference byte-for-byte.",
            "Native body textures are intentional for the material/left-hand experiment; this is not the final Minecraft skin or complete Steve appearance.",
            "Only the private body PAMI is a candidate resource. The current compensated PAC, empty Armor and all other thirteen resources must stay byte-identical in a separately audited fourteen-resource clothing package.",
            "Generation checks only twenty-two real texture entries and the wrinkle entry in the fixed original 0009 index, expected flags, PAZ existence and original-directory bounds. It does not extract or decode those dependency payloads or verify engine/shader behavior.",
            "The original texture/nonetexture0xffffffff.dds sentinel has no required archive entry and is preserved unchanged; its runtime fallback behavior is unverified. Dependencies are not claimed fully resolved.",
            "This tests the entire material contract as one variable; a visual difference would not prove a single shader field as the root cause. PAC weights, skeleton, scale, shrink tag and mask distance are not changed.",
            "No process, native function, installation, service, inventory or save is accessed or changed; original game archive reads are gated and read-only."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Native-body material input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Native-body material input changed beyond its size bound")
    return raw


def package_path(base, relative):
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Native-body material input escapes its package")
    return path


def load_candidate(report_path):
    """Pure admission -> (report, {fixed virtualPath: bytes}, absolute Path snapshot)."""
    path = native.output_directory(report_path)
    raw = bounded_read(path)
    report = strict_json(raw)
    sources, snapshot = {}, {path: raw}
    for key, (relative, digest) in SOURCE_SPECS.items():
        source = package_path(path.parent, relative)
        sources[key] = fixed(bounded_read(source, SOURCE_LIMITS[key]), digest, key)
        snapshot[source] = sources[key]
    expected = make_report(sources)
    if report != expected or raw != report_bytes(expected):
        raise ValueError("Native-body material report differs from the exact fixed reconstruction")
    output = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(output, NATIVE_MATERIAL_SIZE)
    if payload != sources["nativeMaterial"]:
        raise ValueError("Native-body material payload differs from original source bytes")
    snapshot[output] = payload
    orientation.verify_snapshot(snapshot)
    return report, {MATERIAL_PATH: payload}, snapshot


def validate_archive_entry(game, entry, flags):
    if entry.flags != flags:
        raise ValueError("Native-body original entry archive flags differ")
    paz = Path(entry.paz_file)
    native.check_links(paz)
    if not paz.resolve().is_relative_to((game / "0009").resolve()):
        raise ValueError("Native-body original entry escapes original 0009")
    if not paz.is_file() or paz.stat().st_size <= 0:
        raise ValueError("Native-body original entry PAZ is missing or empty")


def read_native_material(game):
    """Extract only the PAMI; bound dependency checks to fixed index metadata."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 archive index")
    gate()
    required = (NATIVE_MATERIAL_PATH, *DEPENDENCY_FLAGS)
    entries = native.select_unique_entries(parse_archive_pamt(index), required)
    for path, flags in {NATIVE_MATERIAL_PATH: ARCHIVE_FLAGS, **DEPENDENCY_FLAGS}.items():
        validate_archive_entry(game, entries[path], flags)
    entry = entries[NATIVE_MATERIAL_PATH]
    raw = fixed(_decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0],
                NATIVE_MATERIAL_SHA256, "original 0009 native-body PAMI")
    material_audit(raw)
    gate()
    return raw


def prepare(output=DEFAULT_OUTPUT, source=ROOT / "build/cdmw-fixed-source", deps=ROOT / "build/cdmw-deps",
            game=None, assembly_report=DEFAULT_ASSEMBLY_REPORT):
    assembly_report = native.output_directory(assembly_report)
    protected = [source, deps, assembly_report.parent, ROOT / "build/steve-clothing-control",
                 ROOT / "build/steve-clothing-control-probe-overlay", ROOT / "build/steve-head-native-material"]
    if game is not None:
        protected.append(Path(game))
    output = orientation.preflight(output, protected)
    if game is None:
        config = strict_json(bounded_read(ROOT / "runtime/installation.json", 2*1024*1024).decode("utf-8-sig").encode("utf-8"))
        game = Path(config["gameRoot"])
    else:
        game = Path(game)
    native.check_links(game)
    protected.append(game)
    output = orientation.preflight(output, protected)
    _, files, snapshot = assembly.load_candidate(assembly_report)
    sources = {"assemblyReport": fixed(bounded_read(assembly_report), ASSEMBLY_REPORT_SHA256, "previous report"),
        "previousMaterial": fixed(files["resources/" + MATERIAL_PATH], OLD_MATERIAL_SHA256, "previous PAMI"),
        "preservedPac": fixed(files["resources/" + PAC_PATH], PRESERVED_PAC_SHA256, "preserved PAC")}
    native.load_cdmw(source, deps)
    sources["nativeMaterial"] = read_native_material(game)
    report = make_report(sources)
    native.verify_source(source)
    orientation.verify_snapshot(snapshot)
    if read_native_material(game) != sources["nativeMaterial"]:
        raise ValueError("Original native-body PAMI changed before publication")
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    writes = {relative: sources[key] for key, (relative, _) in SOURCE_SPECS.items()}
    writes["resources/" + MATERIAL_PATH] = sources["nativeMaterial"]
    writes[REPORT_NAME] = report_bytes(report)
    for relative, raw in writes.items():
        path = package_path(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    load_candidate(output / REPORT_NAME)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY_REPORT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.cdmw_source, args.deps, args.game_root, args.assembly_report)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "variantCount": report["audit"]["variantCount"], "dependencyEntryCount": 23,
        "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
