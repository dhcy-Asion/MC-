"""Build one offline main-body baseColor candidate from admitted fixed packages.

Only six main-body path attributes change. Preserve the current PAC and existing
MC DDS as provenance; this single-PAMI candidate cannot be installed standalone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import prepare_steve_assembly as assembly
import prepare_steve_body_native_material as body_material
import prepare_steve_head_basecolor as head_basecolor

native, orientation, strict_json = body_material.native, body_material.orientation, body_material.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-body-basecolor-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-body-basecolor"
VARIANT = "steve-body-basecolor-only-v1"
MATERIAL_PATH, PAC_PATH = body_material.MATERIAL_PATH, body_material.PAC_PATH
NATIVE_MATERIAL_PATH = body_material.NATIVE_MATERIAL_PATH
NATIVE_MATERIAL_SHA256 = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
OLD_MATERIAL_SHA256 = NATIVE_MATERIAL_SHA256
NEW_MATERIAL_SHA256 = "93bebbb4ed90a43d706230def1670b488dbf723fc7dfcebce910e76f8b069b2b"
CANDIDATE_SHA256 = NEW_MATERIAL_SHA256
NATIVE_MATERIAL_SIZE = CANDIDATE_SIZE = 50017
PRESERVED_PAC_SHA256 = "8f26d6ceb38768be8b933067a53cb3a5cb1170a13b8f287cc4159f865b1e4537"
BODY_MATERIAL_REPORT_SHA256 = "485e0b529cf096b3c2568bdbfdf8a66aedeffae626f2fe031d65aff1741ce55c"
DIFFUSE_PATH = "character/texture/crimsonmc_steve_1_21_1.dds"
DIFFUSE_SHA256 = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
DIFFUSE_SIZE = 87536
ARCHIVE_FLAGS = 50
INDEX_SHA256 = body_material.INDEX_SHA256
DEFAULT_BODY_MATERIAL_REPORT = body_material.DEFAULT_OUTPUT / body_material.REPORT_NAME
DEFAULT_ASSEMBLY_REPORT = assembly.DEFAULT_OUTPUT / assembly.REPORT_NAME
SOURCE_SPECS = {
    "nativeMaterial": ("template/" + NATIVE_MATERIAL_PATH, NATIVE_MATERIAL_SHA256),
    "preservedPac": ("provenance/preserved/" + PAC_PATH, PRESERVED_PAC_SHA256),
    "diffuseTexture": ("provenance/dependencies/" + DIFFUSE_PATH, DIFFUSE_SHA256),
    "nativeMaterialReport": ("provenance/" + body_material.REPORT_NAME, BODY_MATERIAL_REPORT_SHA256),
}
SOURCE_LIMITS = {"nativeMaterial": 50017, "preservedPac": 236594,
                 "diffuseTexture": 87536, "nativeMaterialReport": 131072}
SOURCE_SPANS = ((7067, 7111), (15595, 15639), (24448, 24492),
                (30046, 30090), (38579, 38623), (47610, 47654))
CANDIDATE_SPANS = SOURCE_SPANS
OLD_PATH = "character/texture/cd_phm_00_nude_00_0001.dds"
OLD_PATHS = (OLD_PATH,) * 6
TARGET_DRAW = "cd_phm_00_nude_0001"
TARGET_DRAW_INDEX = 2
PAC_SIZE = 236594
PAC_GEOMETRY_SHA256 = "6cbf5938ee83ebeeb065b10445988c9f06554b480c969fc5339ad81b1bfba5e5"
TEXTURE_PATHS = tuple(path for path in body_material.TEXTURE_PATHS if path != OLD_PATH)
INTEGRATION = {key: False for key in (
    "installed", "appearanceApplied", "leftHandVisibilityVerified", "bodyAlignmentVerified",
    "animationVerified", "equipmentVerified", "partShrinkVerified", "restorationVerified",
    "nativeShaderSemanticsProven", "mcDiffuseNativeRenderingVerified", "mcBodySkinVerified", "steveFixed")}


def fixed(raw, digest, label):
    if not isinstance(raw, bytes) or native.sha256(raw) != digest:
        raise ValueError("Body base-color fixed input differs: " + label)
    return raw


def xml_root(raw):
    return ET.fromstring("<Root>" + raw.decode("utf-8-sig") + "</Root>")


def body_draw_audit(raw):
    """Read bounded raw PAC counts, including descriptors for both empty draws."""
    fixed(raw, PRESERVED_PAC_SHA256, "current compensated body PAC")
    if (len(raw) != PAC_SIZE or raw[:4] != b"PAR "
            or struct.unpack_from("<5Q", raw, 20) != (63138, 43344, 43344, 43344, 43344)):
        raise ValueError("Body base-color preserved PAC size or magic differs")
    starts = (193250, 149906, 106562, 63218)
    splits = (233570, 190226, 146882, 103538)
    ends = (236594, 193250, 149906, 106562)
    if struct.unpack_from("<4I", raw, 85) != starts or struct.unpack_from("<4I", raw, 101) != splits:
        raise ValueError("Body base-color raw PAC LOD table differs")
    names = ((119, 165, b"CD_PHM_00_Head_0001_01", b"CD_PHM_00_Head_0001_01"),
             (229, 279, b"CD_PHM_00_Nude_0001_Hand", b"CD_PHM_00_Nude_0001_hand"),
             (343, 383, b"CD_PHM_00_Nude_0001", b"CD_PHM_00_Nude_0001"))
    draws = []
    for slot, (identity, descriptor, name, material) in enumerate(names):
        encoded = bytes([len(name)]) + name + bytes([len(material)]) + material
        vertices = struct.unpack_from("<4H", raw, descriptor + 40)
        indices = struct.unpack_from("<4I", raw, descriptor + 48)
        expected_vertices, expected_indices = ((1008,) * 4, (1512,) * 4) if slot == 2 else ((0,) * 4, (0,) * 4)
        if (raw[identity:descriptor] != encoded or raw[descriptor+35:descriptor+40] != b"\x04\x00\x01\x02\x03"
                or vertices != expected_vertices or indices != expected_indices):
            raise ValueError("Body base-color raw PAC descriptor identity/counts differ")
        draws.append({"drawIndex": slot, "name": name.decode(), "material": material.decode(),
            "descriptorOffset": descriptor, "verticesPerLod": list(vertices), "indicesPerLod": list(indices)})
    lods = []
    for lod, (start, split, end) in enumerate(zip(starts, splits, ends)):
        if split-start != 1008*40 or end-split != 1512*2 or not 0 <= start < split < end <= len(raw):
            raise ValueError("Body base-color raw PAC geometry section bounds differ")
        indices = struct.unpack_from("<1512H", raw, split)
        if (max(indices) != 1007 or min(indices) != 0
                or any(len(set(indices[i:i+3])) != 3 for i in range(0, 1512, 3))
                or native.sha256(raw[start:end]) != PAC_GEOMETRY_SHA256):
            raise ValueError("Body base-color raw PAC topology/section fingerprint differs")
        lods.append({"lod": lod, "vertexOffset": start, "indexOffset": split, "endOffset": end,
            "vertices": 1008, "triangles": 504, "geometrySectionSha256": PAC_GEOMETRY_SHA256})
    return {"pacSha256": PRESERVED_PAC_SHA256, "pacBytes": PAC_SIZE,
        "metadataSection": {"offset": 80, "byteCount": 63138, "endOffset": 63218},
        "descriptors": draws, "lods": lods, "onlyPopulatedDrawIndex": 2,
        "onlyPopulatedDrawName": TARGET_DRAW, "headAndHandDrawsEmptyAtAllFourLods": True,
        "pacBytesUnchanged": True, "engineDrawSelectionVerified": False}


def material_contract(source, payload):
    """Restore the six allowed tree attributes and compare every XML value."""
    before, after = xml_root(source), xml_root(payload)
    variants = after.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 6 or len(after.findall(".//SkinnedMeshMaterialWrapper")) != 18:
        raise ValueError("Body base-color must retain six variants with three draws")
    for index, variant in enumerate(variants):
        if variant.attrib != {"Index": str(index), "Version": "Reflection"}:
            raise ValueError("Body base-color variant identity differs")
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        if len(wrappers) != 3 or tuple(w.get("_subMeshName") for w in wrappers) != body_material.DRAW_NAMES:
            raise ValueError("Body base-color native draw mapping differs")
        params = wrappers[TARGET_DRAW_INDEX].findall(".//MaterialParameterTexture[@_name='_baseColorTexture']")
        if len(params) != 1 or params[0].attrib != {
                "StringItemID": "_baseColorTexture", "ItemID": "8", "_name": "_baseColorTexture", "Index": "0"}:
            raise ValueError("Body base-color main-draw parameter metadata differs")
        refs = params[0].findall("ResourceReferencePath_ITexture")
        if len(refs) != 1 or refs[0].attrib != {"Name": "_value", "_path": DIFFUSE_PATH}:
            raise ValueError("Body base-color main-draw diffuse path differs")
        refs[0].set("_path", OLD_PATH)
    if ET.tostring(before) != ET.tostring(after):
        raise ValueError("Body base-color changed another XML value, shader, parameter, item, flag or reference")


def restore_material(payload):
    fixed(payload, NEW_MATERIAL_SHA256, "six-path candidate")
    if len(payload) != CANDIDATE_SIZE:
        raise ValueError("Body base-color candidate size differs")
    result = payload
    for start, end in reversed(CANDIDATE_SPANS):
        if result[start:end] != DIFFUSE_PATH.encode("ascii"):
            raise ValueError("Body base-color inverse path span differs")
        result = result[:start] + OLD_PATH.encode("ascii") + result[end:]
    fixed(result, NATIVE_MATERIAL_SHA256, "inverse original PAMI")
    return result


def build_material(source):
    fixed(source, NATIVE_MATERIAL_SHA256, "native body PAMI")
    body_material.material_audit(source)
    for start, end in SOURCE_SPANS:
        if (source[start:end] != OLD_PATH.encode("ascii") or source[start-7:start] != b'_path="'
                or source[end:end+1] != b'"'):
            raise ValueError("Body base-color source span or exact path boundary differs")
    result = source
    for start, end in reversed(SOURCE_SPANS):
        result = result[:start] + DIFFUSE_PATH.encode("ascii") + result[end:]
    fixed(result, NEW_MATERIAL_SHA256, "six-path candidate")
    if len(result) != CANDIDATE_SIZE or restore_material(result) != source:
        raise ValueError("Body base-color exact inverse or output length differs")
    cursor = 0
    for start, end in SOURCE_SPANS:
        if source[cursor:start] != result[cursor:start]:
            raise ValueError("Body base-color changed bytes outside the six path spans")
        cursor = end
    if source[cursor:] != result[cursor:]:
        raise ValueError("Body base-color changed trailing original bytes")
    material_contract(source, result)
    return result


def dependency_contract(payload):
    tree = xml_root(payload)
    references = {ref.get("_path") for ref in tree.findall(".//ResourceReferencePath_ITexture")}
    expected = set(TEXTURE_PATHS) | {DIFFUSE_PATH, body_material.NONE_TEXTURE_PATH}
    if references != expected or len(TEXTURE_PATHS) != 21:
        raise ValueError("Body base-color exact surviving texture dependency set differs")
    return {"originalIndexSha256": INDEX_SHA256,
        "originalEntryAdmissionFromPinnedNativeMaterialReport": True,
        "textureEntries": [{"virtualPath": path, "archiveFlags": 1} for path in TEXTURE_PATHS],
        "wrinkleEntry": {"virtualPath": body_material.WRINKLE_PATH, "archiveFlags": 50},
        "requiredOriginalDependencyEntries": 22,
        "removedOriginalBaseColorDependency": OLD_PATH,
        "candidateDependencyOverrides": [], "dependencyPayloadsDecoded": False,
        "noneTextureSentinel": {"path": body_material.NONE_TEXTURE_PATH, "originalBytesPreserved": True,
                                "archiveEntryRequired": False, "runtimeResolutionVerified": False},
        "mcDiffuseMustAlreadyExistExactlyOnceInPackage": True, "nativeShaderSemanticsProven": False}


def make_report(sources):
    """Reconstruct the whole deterministic manifest from four fixed byte inputs."""
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Body base-color source collection differs")
    for key, (_, digest) in SOURCE_SPECS.items():
        fixed(sources[key], digest, key)
    previous = strict_json(sources["nativeMaterialReport"])
    rows = previous.get("candidateResources")
    if (not isinstance(rows, list) or len(rows) != 1 or rows[0]["virtualPath"] != MATERIAL_PATH
            or rows[0]["sha256"] != NATIVE_MATERIAL_SHA256
            or previous["replacementContract"]["preservedPacVirtualPath"] != PAC_PATH
            or previous["replacementContract"]["preservedPacSha256"] != PRESERVED_PAC_SHA256):
        raise ValueError("Fixed native-body report does not bind the original PAMI/current PAC")
    payload = build_material(sources["nativeMaterial"])
    diffuse = head_basecolor.dds_audit(sources["diffuseTexture"])
    row = {"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH,
        "localFile": "resources/" + MATERIAL_PATH, "sha256": NEW_MATERIAL_SHA256,
        "payloadSize": CANDIDATE_SIZE, "sourceVirtualPath": NATIVE_MATERIAL_PATH,
        "templatePath": NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_MATERIAL_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    edits = [{"variantIndex": index, "drawIndex": TARGET_DRAW_INDEX, "drawName": TARGET_DRAW,
        "parameter": "_baseColorTexture", "itemId": "8", "parameterIndex": "0",
        "sourceSpan": list(span), "candidateSpan": list(span), "oldPath": OLD_PATH, "newPath": DIFFUSE_PATH}
        for index, span in enumerate(SOURCE_SPANS)]
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": relative, "sha256": digest, "payloadSize": len(sources[key])}
                    for key, (relative, digest) in SOURCE_SPECS.items()},
        "files": {**{relative: digest for relative, digest in SOURCE_SPECS.values()}, row["localFile"]: NEW_MATERIAL_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": MATERIAL_PATH,
            "previousMaterialSha256": NATIVE_MATERIAL_SHA256, "replacementMaterialSha256": NEW_MATERIAL_SHA256,
            "preservedPacVirtualPath": PAC_PATH, "preservedPacSha256": PRESERVED_PAC_SHA256,
            "allOtherResourcesMustBeByteIdentical": True, "emptyArmorMustRemainUnchanged": True,
            "wholePackageVerifiedByThisTool": False, "standaloneInstallable": False},
        "diffuseDependency": {"virtualPath": DIFFUSE_PATH, "sha256": DIFFUSE_SHA256,
            "payloadSize": DIFFUSE_SIZE, "expectedArchiveFlags": 0,
            "mustAlreadyExistExactlyOnceInPackage": True, "addedAsCandidateResource": False,
            "packageRegistrationVerifiedByThisTool": False, "dds": diffuse,
            "encodingProvenance": {"minecraftVersion": "1.21.1", "geometryStyle": "classic-wide",
                "officialPngSha256": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0",
                "sourcePngDimensions": [64, 64], "nearestExpansion": 4,
                "encoding": "Existing reviewed nine-mip BC3/DXT5 DDS", "encodingIsLossless": False,
                "pngReencodedOrDecodedByThisTool": False}},
        "dependencyContract": dependency_contract(payload),
        "audit": {"sourceBytes": len(sources["nativeMaterial"]), "candidateBytes": len(payload),
            "byteLengthDelta": 0, "changedPathCount": 6, "edits": edits,
            "outsideSixPathBytesPreserved": True, "exactInverseToOriginalBytes": True,
            "bomPreserved": True, "crlfPreserved": True, "variantCount": 6, "drawsPerVariant": 3,
            "shadersParametersItemsFlagsAndOtherTextureReferencesPreserved": True,
            "headAndHandDrawBaseColorPathsPreserved": True,
            "mainDrawEvidence": body_draw_audit(sources["preservedPac"]),
            "nativeSourceContract": body_material.material_audit(sources["nativeMaterial"])},
        "integration": dict(INTEGRATION), "limitations": [
            "Offline single-body-PAMI candidate only; it is not standalone installable or complete Steve acceptance.",
            "Exactly six cd_phm_00_nude_0001 main-draw _baseColorTexture paths change. Head/hand draws, native SkinnedMeshSkin, all other parameters/references, item IDs, flags, BOM and CRLF remain unchanged.",
            "The fixed current body PAC is provenance and is not edited. Geometry, rig, weights, UV, bounds, shrink metadata, empty Armor and every other resource must stay byte-identical in a separately admitted full package.",
            "The existing MC DDS is provenance and a package dependency, not a second candidate. A later full package must contain it exactly once with archiveFlags=0 and its existing registration.",
            "The DDS has complete nine-mip DXT5 byte ranges and fixed reviewed official Minecraft 1.21.1 classic Steve skin encoding. BC3 encoding is not lossless; this tool does not re-encode the PNG.",
            "Twenty-one surviving native textures and the wrinkle entry retain the pinned native-body report's original index metadata admission. This tool does not read archives or decode dependency payloads. The preserved none-texture sentinel has no required archive entry and unverified runtime resolution.",
            "Offline draw identity is not renderer selection, DDS sampling, lighting, shader semantics, body alignment, animation or equipment acceptance; these remain unverified.",
            "No game file, archive, process, native function, CDMW module, network, service, inventory or save is accessed or changed. Inputs are admitted existing ignored build packages."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Body base-color input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Body base-color input changed beyond its size bound")
    return raw


def package_path(base, relative):
    assembly.relative_path(relative)
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Body base-color input escapes its package")
    return path


def exact_inventory(base, relatives):
    actual = set()
    for path in base.rglob("*"):
        native.check_links(path)
        if path.is_file():
            actual.add(path.relative_to(base).as_posix())
        elif not path.is_dir():
            raise ValueError("Body base-color package has an unsupported filesystem entry")
    if actual != set(relatives):
        raise ValueError("Body base-color package file inventory differs")


def load_report(report_path):
    """Pure admission -> (report, {one private PAMI: bytes}, absolute Path snapshot)."""
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
        raise ValueError("Body base-color report differs from the complete fixed reconstruction")
    output = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(output, CANDIDATE_SIZE)
    if payload != build_material(sources["nativeMaterial"]):
        raise ValueError("Body base-color payload differs from the six fixed path splices")
    snapshot[output] = payload
    exact_inventory(path.parent, {*expected["files"], REPORT_NAME})
    orientation.verify_snapshot(snapshot)
    return report, {MATERIAL_PATH: payload}, snapshot


load_candidate = load_report


def read_inputs(body_material_report, assembly_report):
    _, bodies, snapshot = body_material.load_candidate(body_material_report)
    _, files, assembly_snapshot = assembly.load_candidate(assembly_report)
    snapshot.update(assembly_snapshot)
    pac = body_material.package_path(body_material_report.parent, body_material.SOURCE_SPECS["preservedPac"][0])
    sources = {"nativeMaterial": bodies[MATERIAL_PATH], "preservedPac": snapshot[pac],
               "diffuseTexture": files["resources/" + DIFFUSE_PATH],
               "nativeMaterialReport": snapshot[body_material_report]}
    return sources, snapshot


def protected_directories(body_material_report, assembly_report):
    return [body_material_report.parent, assembly_report.parent,
        *(ROOT / "build" / name for name in (
            "steve-clothing-control", "steve-clothing-control-probe-overlay",
            "steve-body-native-material-probe-overlay", "steve-head-native-material",
            "steve-head-native-material-probe-overlay", "steve-head-basecolor",
            "steve-head-basecolor-probe-overlay", "steve-head-uv", "steve-head-uv-probe-overlay",
            "steve-head-visible-layer", "steve-head-visible-layer-probe-overlay",
            "native-steve", "steve-1.21.1", "cdmw-fixed-source", "cdmw-deps"))]


def prepare(output=DEFAULT_OUTPUT, body_material_report=DEFAULT_BODY_MATERIAL_REPORT,
            assembly_report=DEFAULT_ASSEMBLY_REPORT):
    body_material_report = native.output_directory(body_material_report)
    assembly_report = native.output_directory(assembly_report)
    protected = protected_directories(body_material_report, assembly_report)
    output = orientation.preflight(output, protected)
    sources, snapshot = read_inputs(body_material_report, assembly_report)
    report, payload = make_report(sources), build_material(sources["nativeMaterial"])
    orientation.verify_snapshot(snapshot)
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    writes = {relative: sources[key] for key, (relative, _) in SOURCE_SPECS.items()}
    writes["resources/" + MATERIAL_PATH] = payload
    writes[REPORT_NAME] = report_bytes(report)
    for relative, raw in writes.items():
        path = package_path(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    load_report(output / REPORT_NAME)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--body-material-report", type=Path, default=DEFAULT_BODY_MATERIAL_REPORT)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY_REPORT)
    args = parser.parse_args()
    report = prepare(args.output, args.body_material_report, args.assembly_report)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "changedPathCount": 6, "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
