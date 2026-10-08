"""Build an offline three-path Steve base-color control for the native head PAMI.

Read only the existing admitted head-material and assembly packages. Preserve
every original PAMI byte except the three main-draw baseColor paths; keep the
current head PAC and existing MC DDS as fixed provenance, not new resources.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import prepare_steve_assembly as assembly
import prepare_steve_head_native_material as head_material

native, orientation, strict_json = head_material.native, head_material.orientation, head_material.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-head-basecolor-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-head-basecolor"
VARIANT = "steve-head-basecolor-only-v1"
MATERIAL_PATH = head_material.MATERIAL_PATH
PAC_PATH = head_material.head_root.PAC_PATH
NATIVE_MATERIAL_PATH = head_material.NATIVE_MATERIAL_PATH
NATIVE_MATERIAL_SHA256 = "440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5"
OLD_MATERIAL_SHA256 = NATIVE_MATERIAL_SHA256
NEW_MATERIAL_SHA256 = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
CANDIDATE_SHA256 = NEW_MATERIAL_SHA256
NATIVE_MATERIAL_SIZE, CANDIDATE_SIZE = 16149, 16134
PRESERVED_PAC_SHA256 = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
HEAD_MATERIAL_REPORT_SHA256 = "1ca1972751b346ce8afd9da684ab3d419ef60a92e557a53be1b111145cdb7c7a"
DIFFUSE_PATH = "character/texture/crimsonmc_steve_1_21_1.dds"
DIFFUSE_SHA256 = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
DIFFUSE_SIZE = 87536
ARCHIVE_FLAGS = 50
INDEX_SHA256 = head_material.INDEX_SHA256
DEFAULT_HEAD_MATERIAL_REPORT = head_material.DEFAULT_OUTPUT / head_material.REPORT_NAME
DEFAULT_ASSEMBLY_REPORT = assembly.DEFAULT_OUTPUT / assembly.REPORT_NAME
SOURCE_SPECS = {
    "nativeMaterial": ("template/" + NATIVE_MATERIAL_PATH, NATIVE_MATERIAL_SHA256),
    "preservedPac": ("provenance/preserved/" + PAC_PATH, PRESERVED_PAC_SHA256),
    "diffuseTexture": ("provenance/dependencies/" + DIFFUSE_PATH, DIFFUSE_SHA256),
    "nativeMaterialReport": ("provenance/" + head_material.REPORT_NAME, HEAD_MATERIAL_REPORT_SHA256),
}
SOURCE_LIMITS = {"nativeMaterial": 16149, "preservedPac": 96721,
                 "diffuseTexture": 87536, "nativeMaterialReport": 131072}
SOURCE_SPANS = ((1406, 1455), (6516, 6565), (11631, 11680))
OLD_PATHS = ("character/texture/cd_phm_00_head_0001_macduff.dds",
             "character/texture/cd_phm_00_head_0008_macduff.dds",
             "character/texture/cd_phm_00_head_0001_macduff.dds")
CANDIDATE_SPANS = ((1406, 1450), (6511, 6555), (11621, 11665))
INTEGRATION = {key: False for key in (
    "installed", "appearanceApplied", "headAlignmentVerified", "animationVerified",
    "equipmentVerified", "restorationVerified", "nativeShaderSemanticsProven",
    "mcDiffuseNativeRenderingVerified", "mcHeadSkinVerified", "steveFixed")}


def fixed(raw, digest, label):
    if not isinstance(raw, bytes) or native.sha256(raw) != digest:
        raise ValueError("Head base-color fixed input differs: " + label)
    return raw


def dds_audit(raw):
    """Validate the actual complete legacy BC3 mip byte ranges, without CDMW."""
    if len(raw) < 128 or raw[:4] != b"DDS " or struct.unpack_from("<I", raw, 4)[0] != 124:
        raise ValueError("Head diffuse has an invalid legacy DDS header")
    flags, height, width, pitch, depth, count = struct.unpack_from("<6I", raw, 8)
    pf_size, pf_flags = struct.unpack_from("<2I", raw, 76)
    caps = struct.unpack_from("<I", raw, 108)[0]
    if ((flags & 0xA1007) != 0xA1007 or (width, height, depth, count) != (256, 256, 1, 9)
            or (pf_size, pf_flags) != (32, 4) or raw[84:88] != b"DXT5"
            or (caps & 0x401008) != 0x401008):
        raise ValueError("Head diffuse requires the fixed 256x256 nine-mip legacy DXT5 contract")
    rows, cursor = [], 128
    for level in range(count):
        w, h = max(1, width >> level), max(1, height >> level)
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
        end = cursor + size
        if end > len(raw):
            raise ValueError("Head diffuse has an incomplete mip payload")
        rows.append({"level": level, "width": w, "height": h, "offset": cursor,
                     "byteCount": size, "endOffset": end})
        cursor = end
    if pitch != rows[0]["byteCount"] or cursor != len(raw) or len(raw) != DIFFUSE_SIZE:
        raise ValueError("Head diffuse mip sizes or trailing bytes differ")
    return {"width": width, "height": height, "depth": depth, "mips": count,
            "fourcc": "DXT5", "headerBytes": 128, "payloadBytes": cursor - 128,
            "allMipByteRangesComplete": True, "mipByteRanges": rows}


def material_contract(source, payload):
    """Only three main-draw texture path attributes may differ semantically."""
    before = ET.fromstring("<Root>" + source.decode("utf-8-sig") + "</Root>")
    after = ET.fromstring("<Root>" + payload.decode("utf-8-sig") + "</Root>")
    variants = after.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 3:
        raise ValueError("Head base-color candidate lost the native three variants")
    for index, variant in enumerate(variants):
        wrappers = variant.findall(".//SkinnedMeshMaterialWrapper")
        if len(wrappers) != 2 or tuple(w.get("_subMeshName") for w in wrappers) != head_material.DRAW_NAMES:
            raise ValueError("Head base-color native draw mapping differs")
        params = wrappers[1].findall(".//MaterialParameterTexture[@_name='_baseColorTexture']")
        if len(params) != 1 or params[0].attrib != {
                "StringItemID": "_baseColorTexture", "ItemID": "7", "_name": "_baseColorTexture", "Index": "0"}:
            raise ValueError("Head base-color parameter metadata differs")
        refs = params[0].findall("ResourceReferencePath_ITexture")
        if len(refs) != 1 or refs[0].attrib != {"Name": "_value", "_path": DIFFUSE_PATH}:
            raise ValueError("Head base-color diffuse path differs")
        refs[0].set("_path", OLD_PATHS[index])
    if ET.tostring(before) != ET.tostring(after):
        raise ValueError("Head base-color changed another XML field, shader, parameter, item or flag")


def restore_material(payload):
    fixed(payload, NEW_MATERIAL_SHA256, "three-path candidate")
    if len(payload) != CANDIDATE_SIZE:
        raise ValueError("Head base-color candidate size differs")
    result = payload
    for (start, end), old in reversed(tuple(zip(CANDIDATE_SPANS, OLD_PATHS))):
        if result[start:end] != DIFFUSE_PATH.encode("ascii"):
            raise ValueError("Head base-color inverse path span differs")
        result = result[:start] + old.encode("ascii") + result[end:]
    fixed(result, NATIVE_MATERIAL_SHA256, "inverse original PAMI")
    return result


def build_material(source):
    fixed(source, NATIVE_MATERIAL_SHA256, "native head PAMI")
    head_material.material_audit(source)
    for (start, end), old in zip(SOURCE_SPANS, OLD_PATHS):
        if (source[start:end] != old.encode("ascii") or source[start-7:start] != b'_path="'
                or source[end:end+1] != b'"'):
            raise ValueError("Head base-color source span or exact path boundary differs")
    result = source
    for start, end in reversed(SOURCE_SPANS):
        result = result[:start] + DIFFUSE_PATH.encode("ascii") + result[end:]
    fixed(result, NEW_MATERIAL_SHA256, "three-path candidate")
    if len(result) != CANDIDATE_SIZE or restore_material(result) != source:
        raise ValueError("Head base-color exact inverse or output length differs")
    old_cursor, new_cursor = 0, 0
    for (start, end), (new_start, new_end) in zip(SOURCE_SPANS, CANDIDATE_SPANS):
        if source[old_cursor:start] != result[new_cursor:new_start]:
            raise ValueError("Head base-color changed bytes outside the three path spans")
        old_cursor, new_cursor = end, new_end
    if source[old_cursor:] != result[new_cursor:]:
        raise ValueError("Head base-color changed trailing original bytes")
    material_contract(source, result)
    return result


def make_report(sources):
    """Reconstruct the entire canonical report and candidate from four fixed sources."""
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Head base-color source collection differs")
    for key, (_, digest) in SOURCE_SPECS.items():
        fixed(sources[key], digest, key)
    previous = strict_json(sources["nativeMaterialReport"])
    rows = previous.get("candidateResources")
    if (not isinstance(rows, list) or len(rows) != 1 or rows[0]["virtualPath"] != MATERIAL_PATH
            or rows[0]["sha256"] != NATIVE_MATERIAL_SHA256
            or previous["replacementContract"]["preservedPacVirtualPath"] != PAC_PATH
            or previous["replacementContract"]["preservedPacSha256"] != PRESERVED_PAC_SHA256):
        raise ValueError("Fixed native-head report does not bind the original PAMI/current PAC")
    payload = build_material(sources["nativeMaterial"])
    diffuse = dds_audit(sources["diffuseTexture"])
    row = {"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH,
        "localFile": "resources/" + MATERIAL_PATH, "sha256": NEW_MATERIAL_SHA256,
        "payloadSize": CANDIDATE_SIZE, "sourceVirtualPath": NATIVE_MATERIAL_PATH,
        "templatePath": NATIVE_MATERIAL_PATH, "templateSha256": NATIVE_MATERIAL_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    edits = [{"variantIndex": index, "parameter": "_baseColorTexture", "itemId": "7",
        "parameterIndex": "0", "sourceSpan": list(old), "candidateSpan": list(new),
        "oldPath": OLD_PATHS[index], "newPath": DIFFUSE_PATH}
        for index, (old, new) in enumerate(zip(SOURCE_SPANS, CANDIDATE_SPANS))]
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": relative, "sha256": digest, "payloadSize": len(sources[key])}
                    for key, (relative, digest) in SOURCE_SPECS.items()},
        "files": {**{relative: digest for relative, digest in SOURCE_SPECS.values()}, row["localFile"]: NEW_MATERIAL_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": MATERIAL_PATH,
            "previousMaterialSha256": NATIVE_MATERIAL_SHA256, "replacementMaterialSha256": NEW_MATERIAL_SHA256,
            "preservedPacVirtualPath": PAC_PATH, "preservedPacSha256": PRESERVED_PAC_SHA256,
            "allOtherResourcesMustBeByteIdentical": True, "wholePackageVerifiedByThisTool": False},
        "diffuseDependency": {"virtualPath": DIFFUSE_PATH, "sha256": DIFFUSE_SHA256,
            "payloadSize": DIFFUSE_SIZE, "expectedArchiveFlags": 0,
            "mustAlreadyExistExactlyOnceInPackage": True, "addedAsCandidateResource": False,
            "packageRegistrationVerifiedByThisTool": False, "dds": diffuse,
            "encodingProvenance": {"minecraftVersion": "1.21.1", "geometryStyle": "classic-wide",
                "officialPngSha256": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0",
                "sourcePngDimensions": [64, 64], "nearestExpansion": 4,
                "encoding": "Existing reviewed nine-mip BC3/DXT5 DDS", "encodingIsLossless": False,
                "pngReencodedOrDecodedByThisTool": False}},
        "audit": {"sourceBytes": len(sources["nativeMaterial"]), "candidateBytes": len(payload),
            "byteLengthDelta": -15, "changedPathCount": 3, "edits": edits,
            "outsideThreePathBytesPreserved": True, "exactInverseToOriginalBytes": True,
            "bomPreserved": True, "crlfPreserved": True, "variantCount": 3, "drawsPerVariant": 2,
            "shadersParametersItemsFlagsAndOtherTextureReferencesPreserved": True,
            "nativeSourceContract": head_material.material_audit(sources["nativeMaterial"])},
        "integration": dict(INTEGRATION), "limitations": [
            "Offline single-head-PAMI candidate only; no installation, native rendering, maintained attachment, Minecraft head-skin or complete Steve acceptance.",
            "Exactly three main-draw _baseColorTexture path values change. Native eye shader, wrinkle/aging/damage/normal parameters, item IDs, flags, all other references, BOM and CRLF remain unchanged.",
            "The preserved current head PAC is not edited. All other resources and metadata must remain byte-identical in a separately admitted full package.",
            "The pinned MC diffuse DDS is provenance and an existing package dependency, not a second candidate. A later package must contain it exactly once with archiveFlags=0 and the existing registration.",
            "The DDS has verified complete byte ranges for nine DXT5 mips. Its fixed bytes come from the existing reviewed Minecraft 1.21.1 official classic Steve skin encoding; BC3 encoding is not lossless, and this tool does not re-encode the PNG.",
            "Remaining native material dependencies, alpha/lighting, dynamic masks, head/body appearance and animation semantics remain unverified; this experiment does not establish a unique root cause.",
            "No game file, archive, process, native function, CDMW module, network, service, inventory or save is accessed or changed. Inputs are admitted existing ignored build packages."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Head base-color input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Head base-color input changed beyond its size bound")
    return raw


def package_path(base, relative):
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Head base-color input escapes its package")
    return path


def load_candidate(report_path):
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
        raise ValueError("Head base-color report differs from the complete fixed reconstruction")
    output = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(output, CANDIDATE_SIZE)
    if payload != build_material(sources["nativeMaterial"]):
        raise ValueError("Head base-color payload differs from the three fixed path splices")
    snapshot[output] = payload
    orientation.verify_snapshot(snapshot)
    return report, {MATERIAL_PATH: payload}, snapshot


def read_inputs(head_material_report, assembly_report):
    _, heads, snapshot = head_material.load_candidate(head_material_report)
    _, files, assembly_snapshot = assembly.load_candidate(assembly_report)
    snapshot.update(assembly_snapshot)
    pac = head_material.package_path(head_material_report.parent, head_material.SOURCE_SPECS["preservedPac"][0])
    sources = {"nativeMaterial": heads[MATERIAL_PATH], "preservedPac": snapshot[pac],
               "diffuseTexture": files["resources/" + DIFFUSE_PATH],
               "nativeMaterialReport": snapshot[head_material_report]}
    return sources, snapshot


def prepare(output=DEFAULT_OUTPUT, head_material_report=DEFAULT_HEAD_MATERIAL_REPORT,
            assembly_report=DEFAULT_ASSEMBLY_REPORT):
    head_material_report = native.output_directory(head_material_report)
    assembly_report = native.output_directory(assembly_report)
    protected = [head_material_report.parent, assembly_report.parent,
                 ROOT / "build/steve-body-native-material", ROOT / "build/steve-clothing-control",
                 ROOT / "build/steve-body-native-material-probe-overlay",
                 ROOT / "build/steve-clothing-control-probe-overlay",
                 ROOT / "build/steve-head-native-material-probe-overlay"]
    output = orientation.preflight(output, protected)
    sources, snapshot = read_inputs(head_material_report, assembly_report)
    report = make_report(sources)
    payload = build_material(sources["nativeMaterial"])
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
    load_candidate(output / REPORT_NAME)
    orientation.verify_snapshot(snapshot)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--head-material-report", type=Path, default=DEFAULT_HEAD_MATERIAL_REPORT)
    parser.add_argument("--assembly-report", type=Path, default=DEFAULT_ASSEMBLY_REPORT)
    args = parser.parse_args()
    report = prepare(args.output, args.head_material_report, args.assembly_report)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "changedPathCount": 3, "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
