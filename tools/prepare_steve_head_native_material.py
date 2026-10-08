"""Build one byte-identical native-head PAMI control for the failed Steve head.

This is an offline candidate. Native textures are intentional for this material
contract control; the failed head-root PAC and the other eleven resources must
remain unchanged in a separately checked thirteen-resource package.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_native_steve as native
import prepare_steve_native_head_root as head_root
import prepare_steve_orientation as orientation
from prepare_steve_prefab import strict_json

ROOT = native.ROOT
REPORT_NAME = "steve-head-native-material-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-head-native-material"
VARIANT = "steve-head-native-material-only-v1"
MATERIAL_PATH = head_root.MATERIAL_PATH
NATIVE_MATERIAL_PATH = "character/modelproperty/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac_xml"
NATIVE_MATERIAL_SHA256 = "440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5"
NATIVE_MATERIAL_SIZE = 16149
OLD_MATERIAL_SHA256 = "442b56d40caf42e31f082123577483d195e107504a6cb85bcba556a3638c8ff9"
PRESERVED_PAC_SHA256 = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
HEAD_ROOT_REPORT_SHA256 = "2d850067c97a7d44762eadb68154dbbb992aa2010f3851b63e3b0e8dfd6085a8"
INDEX_SHA256 = head_root.INDEX_SHA256
ARCHIVE_FLAGS = 50
DEFAULT_HEAD_ROOT_REPORT = head_root.DEFAULT_OUTPUT / head_root.REPORT_NAME
SOURCE_SPECS = {
    "nativeMaterial": ("template/" + NATIVE_MATERIAL_PATH, NATIVE_MATERIAL_SHA256),
    "previousMaterial": ("provenance/previous/" + MATERIAL_PATH, OLD_MATERIAL_SHA256),
    "preservedPac": ("provenance/preserved/" + head_root.PAC_PATH, PRESERVED_PAC_SHA256),
    "headRootReport": ("provenance/" + head_root.REPORT_NAME, HEAD_ROOT_REPORT_SHA256),
}
INTEGRATION = {key: False for key in (
    "installed", "appearanceApplied", "headAlignmentVerified", "animationVerified",
    "equipmentVerified", "restorationVerified", "nativeShaderSemanticsProven", "steveFixed")}
DRAW_NAMES = tuple(name.lower() for name in head_root.DRAW_NAMES)
MAIN_SHADERS = ("SkinnedMeshSkinWrinkle", "SkinnedMeshSkinWrinkle", "SkinnedMeshSkinWrinkleAging")
MAIN_PARAMETER_COUNTS = (14, 14, 16)


def fixed(raw, expected, name):
    if not isinstance(raw, bytes) or native.sha256(raw) != expected:
        raise ValueError("Native-head material fixed input differs: " + name)
    return raw


def material_audit(raw):
    """Audit the exact original's three variants; never serialize or edit XML."""
    fixed(raw, NATIVE_MATERIAL_SHA256, "original native PAMI")
    if len(raw) != NATIVE_MATERIAL_SIZE:
        raise ValueError("Native-head original PAMI size differs")
    root = ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 3 or len(root.findall(".//SkinnedMeshMaterialWrapper")) != 6:
        raise ValueError("Native-head PAMI must retain three variants with two draws")
    rows = []
    for index, variant in enumerate(variants):
        if variant.attrib != {"Index": str(index), "Version": "Reflection"}:
            raise ValueError("Native-head material variant identity differs")
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        if len(wrappers) != 2 or tuple(w.get("_subMeshName") for w in wrappers) != DRAW_NAMES:
            raise ValueError("Native-head material draw mapping differs")
        draw_rows = []
        for draw, wrapper in enumerate(wrappers):
            material = wrapper.find("Material")
            if material is None:
                raise ValueError("Native-head material wrapper has no shader")
            expected = "SkinnedMeshEyeCover" if draw == 0 else MAIN_SHADERS[index]
            parameters = [p for p in material.iter() if p.tag.startswith("MaterialParameter")]
            count = 1 if draw == 0 else MAIN_PARAMETER_COUNTS[index]
            if material.get("_materialName") != expected or len(parameters) != count:
                raise ValueError("Original native-head shader/parameter contract differs")
            textures = []
            for parameter in parameters:
                if parameter.tag != "MaterialParameterTexture":
                    continue
                references = parameter.findall("ResourceReferencePath_ITexture")
                if len(references) != 1 or not references[0].get("_path"):
                    raise ValueError("Native-head texture reference is ambiguous")
                textures.append({"name": parameter.get("_name"), "path": references[0].get("_path")})
            draw_rows.append({"wrapper": dict(wrapper.attrib), "shader": expected,
                "parameterCount": count, "parameters": [
                    {"tag": p.tag, "attributes": dict(p.attrib)} for p in parameters], "textures": textures})
        rows.append({"variant": dict(variant.attrib), "draws": draw_rows})
    return {"sourceBytes": len(raw), "candidateBytes": len(raw), "originalBytesPreserved": True,
        "variantCount": 3, "drawsPerVariant": 2, "drawNames": list(DRAW_NAMES),
        "mainShaderNames": list(MAIN_SHADERS), "mainParameterCounts": list(MAIN_PARAMETER_COUNTS),
        "eyecoverShader": "SkinnedMeshEyeCover", "eyecoverParameterCount": 1,
        "nativeTexturesAndWrinkleReferencesUnchanged": True, "variants": rows}


def make_report(sources):
    """Reconstruct the complete deterministic manifest from four fixed byte inputs."""
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Native-head material source collection differs")
    for key, (_, expected) in SOURCE_SPECS.items():
        fixed(sources[key], expected, key)
    audit = material_audit(sources["nativeMaterial"])
    previous = strict_json(sources["headRootReport"])
    previous_rows = {r["virtualPath"]: r for r in previous["candidateResources"]}
    if (previous_rows[MATERIAL_PATH]["sha256"] != OLD_MATERIAL_SHA256
            or previous_rows[head_root.PAC_PATH]["sha256"] != PRESERVED_PAC_SHA256):
        raise ValueError("Fixed previous head-root report does not bind the reviewed PAC/PAMI")
    row = {"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH,
        "localFile": "resources/" + MATERIAL_PATH, "sha256": NATIVE_MATERIAL_SHA256,
        "payloadSize": NATIVE_MATERIAL_SIZE, "sourceVirtualPath": NATIVE_MATERIAL_PATH,
        "templatePath": NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_MATERIAL_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": relative, "sha256": expected, "payloadSize": len(sources[key])}
                    for key, (relative, expected) in SOURCE_SPECS.items()},
        "files": {**{relative: expected for relative, expected in SOURCE_SPECS.values()},
                  row["localFile"]: NATIVE_MATERIAL_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": MATERIAL_PATH,
            "previousMaterialSha256": OLD_MATERIAL_SHA256,
            "replacementMaterialSha256": NATIVE_MATERIAL_SHA256,
            "preservedPacVirtualPath": head_root.PAC_PATH, "preservedPacSha256": PRESERVED_PAC_SHA256,
            "otherElevenResourcesMustBeByteIdentical": True, "wholePackageVerifiedByThisTool": False},
        "audit": audit, "integration": dict(INTEGRATION), "limitations": [
            "Offline single-PAMI control; successful construction is not native head-position, visibility, animation or shader validation.",
            "The original native-head material's three variants, two draw names, shaders, complete parameters, wrapper metadata, native textures and wrinkle dependency remain byte-for-byte unchanged.",
            "Native textures are intentional for the position experiment; this candidate does not claim the final Minecraft skin or complete Steve appearance.",
            "Only the private head PAMI is a candidate resource. The fixed failed head-root PAC and the other eleven resources must remain unchanged in a separately audited thirteen-resource package.",
            "The original head PAMI has three variants, not the previous Steve material's six; no variant expansion or shader-name-only rewrite is performed.",
            "This tests a material-resource contract as one variable; an eventual visual difference would not by itself prove one shader field is the root cause.",
            "No process, native function, installation, service, inventory or save is accessed or changed by this generator; original game archive reads are gated and read-only."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")


def bounded_read(path, limit=2*1024*1024):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Native-head material input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Native-head material input changed beyond its size bound")
    return raw


def package_path(base, relative):
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Native-head material input escapes its package")
    return path


def load_candidate(report_path):
    """Pure admission -> (report, {virtualPath: bytes}, {absolute safe Path: bytes})."""
    path = native.output_directory(report_path)
    raw = bounded_read(path)
    report = strict_json(raw)
    sources, snapshot = {}, {path: raw}
    for key, (relative, expected) in SOURCE_SPECS.items():
        source = package_path(path.parent, relative)
        sources[key] = fixed(bounded_read(source), expected, key)
        snapshot[source] = sources[key]
    expected = make_report(sources)
    if report != expected or raw != report_bytes(expected):
        raise ValueError("Native-head material report differs from the exact fixed reconstruction")
    output = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(output, NATIVE_MATERIAL_SIZE)
    if payload != sources["nativeMaterial"]:
        raise ValueError("Native-head material payload differs from original source bytes")
    snapshot[output] = payload
    orientation.verify_snapshot(snapshot)
    return report, {MATERIAL_PATH: payload}, snapshot


def read_native_material(game):
    """Read one hash/size/flags-pinned entry from original 0009; no process access."""
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    exe, index = game / "bin64/CrimsonDesert.exe", game / "0009/0.pamt"
    def gate():
        for path in (game, exe, index):
            native.check_links(path)
        if native.file_hash(exe) != native.EXE_SHA256 or native.file_hash(index) != INDEX_SHA256:
            raise ValueError("Unsupported EXE or original 0009 archive index")
    gate()
    entry = native.select_unique_entries(parse_archive_pamt(index), (NATIVE_MATERIAL_PATH,))[NATIVE_MATERIAL_PATH]
    if entry.flags != ARCHIVE_FLAGS:
        raise ValueError("Original native-head PAMI archive flags differ")
    paz = Path(entry.paz_file)
    native.check_links(paz)
    if not paz.resolve().is_relative_to((game / "0009").resolve()):
        raise ValueError("Native-head material entry escapes original 0009")
    raw = fixed(_decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0],
                NATIVE_MATERIAL_SHA256, "original 0009 native-head PAMI")
    material_audit(raw)
    gate()
    return raw


def prepare(output=DEFAULT_OUTPUT, source=ROOT / "build/cdmw-fixed-source", deps=ROOT / "build/cdmw-deps",
            game=None, head_root_report=DEFAULT_HEAD_ROOT_REPORT):
    head_root_report = native.output_directory(head_root_report)
    protected = [source, deps, head_root_report.parent]
    output = orientation.preflight(output, protected)
    if game is None:
        config = strict_json(bounded_read(ROOT / "runtime/installation.json").decode("utf-8-sig").encode("utf-8"))
        game = Path(config["gameRoot"])
    else:
        game = Path(game)
    native.check_links(game)
    protected.append(game)
    output = orientation.preflight(output, protected)
    _, payloads, snapshot = head_root.load_candidate(head_root_report)
    sources = {"headRootReport": fixed(bounded_read(head_root_report), HEAD_ROOT_REPORT_SHA256, "previous report"),
        "previousMaterial": fixed(payloads[MATERIAL_PATH], OLD_MATERIAL_SHA256, "previous PAMI"),
        "preservedPac": fixed(payloads[head_root.PAC_PATH], PRESERVED_PAC_SHA256, "preserved PAC")}
    native.load_cdmw(source, deps)
    sources["nativeMaterial"] = read_native_material(game)
    report = make_report(sources)
    native.verify_source(source)
    orientation.verify_snapshot(snapshot)
    if read_native_material(game) != sources["nativeMaterial"]:
        raise ValueError("Original native-head PAMI changed before publication")
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
    parser.add_argument("--head-root-report", type=Path, default=DEFAULT_HEAD_ROOT_REPORT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    args = parser.parse_args()
    report = prepare(args.output, args.cdmw_source, args.deps, args.game_root, args.head_root_report)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "variantCount": report["audit"]["variantCount"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
