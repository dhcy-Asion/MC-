"""Build a pure offline primary-V-only control for the fixed Steve head PAC.

The existing admitted head base-color package supplies all four fixed inputs.
Only 144 half-float V fields change; this does not prove the native shader's UV
convention, texture selection, alpha behavior, head skin or animation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import prepare_steve_head_basecolor as headbase

native, orientation, strict_json = headbase.native, headbase.orientation, headbase.strict_json
ROOT = native.ROOT
REPORT_NAME = "steve-head-uv-control-report.json"
DEFAULT_OUTPUT = ROOT / "build/steve-head-uv-control"
DEFAULT_HEAD_BASECOLOR_REPORT = headbase.DEFAULT_OUTPUT / headbase.REPORT_NAME
VARIANT = "steve-head-primary-v-flip-only-v1"
PAC_PATH = headbase.PAC_PATH
MATERIAL_PATH = headbase.MATERIAL_PATH
DIFFUSE_PATH = headbase.DIFFUSE_PATH
OLD_PAC_SHA256 = "182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660"
NEW_PAC_SHA256 = "c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55"
CANDIDATE_SHA256 = NEW_PAC_SHA256
PRESERVED_MATERIAL_SHA256 = "cc86b387583430d7e2d8ef136db965dd39d3e5754501626b7c82fa606b2abf3f"
DIFFUSE_SHA256 = "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a"
HEAD_BASECOLOR_REPORT_SHA256 = "56d0ee077c290395c6efcc013c1c48524fe0db1af5c3bea6137d01a944c9f466"
PAC_SIZE, MATERIAL_SIZE, DIFFUSE_SIZE, PRIOR_REPORT_SIZE = 96721, 16134, 87536, 36429
ARCHIVE_FLAGS = 1
SOURCE_SPECS = {
    "headPac": ("template/" + PAC_PATH, OLD_PAC_SHA256),
    "preservedMaterial": ("provenance/preserved/" + MATERIAL_PATH, PRESERVED_MATERIAL_SHA256),
    "diffuseTexture": ("provenance/dependencies/" + DIFFUSE_PATH, DIFFUSE_SHA256),
    "headBaseColorReport": ("provenance/" + headbase.REPORT_NAME, HEAD_BASECOLOR_REPORT_SHA256),
}
SOURCE_LIMITS = {"headPac": PAC_SIZE, "preservedMaterial": MATERIAL_SIZE,
                 "diffuseTexture": DIFFUSE_SIZE, "headBaseColorReport": PRIOR_REPORT_SIZE}
LOD_LAYOUT = ((2, 2, 90529), (1, 3, 92593), (0, 4, 94657))
PROTECTED_DIRS = tuple(ROOT / "build" / name for name in (
    "steve-1.21.1", "native-steve", "steve-material", "steve-prefab",
    "steve-segmented", "steve-parts", "steve-parts-prefab", "steve-orientation",
    "steve-current-rig", "steve-assembly", "steve-appearance", "steve-head-descriptor",
    "steve-part-table", "steve-native-head-root", "steve-head-mesh-control",
    "steve-head-native-material", "steve-head-basecolor", "steve-clothing-control",
    "steve-body-native-material", "steve-probe-overlay", "steve-head-descriptor-probe-overlay",
    "steve-part-table-v2-probe-overlay", "steve-native-head-probe-overlay",
    "steve-native-head-root-probe-overlay", "steve-head-native-material-probe-overlay",
    "steve-clothing-control-probe-overlay", "steve-body-native-material-probe-overlay",
    "steve-head-basecolor-probe-overlay", "cdmw-fixed-source", "cdmw-deps"))
INTEGRATION = {key: False for key in (
    "installed", "appearanceApplied", "headAlignmentVerified", "animationVerified",
    "equipmentVerified", "restorationVerified", "nativeShaderUvConventionVerified",
    "nativePrimaryUvSelectionVerified", "nativeAlphaBehaviorVerified",
    "mcDiffuseNativeRenderingVerified", "mcHeadSkinVerified", "steveFixed")}


def fixed(raw, digest, label):
    if not isinstance(raw, bytes) or native.sha256(raw) != digest:
        raise ValueError("Head UV fixed input differs: " + label)
    return raw


def pac_structure(raw):
    """Bounded scalar parse of the fixed PAR table and active draw records."""
    if len(raw) != PAC_SIZE or raw[:4] != b"PAR ":
        raise ValueError("Head UV requires the complete fixed PAR payload")
    cursor, sections = 80, []
    for sid in range(8):
        pointer, size = struct.unpack_from("<2I", raw, 16 + sid * 8)
        if pointer:
            raise ValueError("Head UV PAR table contains a nonzero offset lane")
        if size:
            sections.append({"section": sid, "offset": cursor, "size": size})
            cursor += size
    if sections != [{"section": 0, "offset": 80, "size": 90449}] + [
            {"section": sid, "offset": start, "size": 2064} for _, sid, start in LOD_LAYOUT] or cursor != len(raw):
        raise ValueError("Head UV PAR sections or complete byte coverage differ")
    if (struct.unpack_from("<I", raw, 80)[0] != 2 or raw[84] != 3
            or raw[218:230] != bytes(12)
            or struct.unpack_from("<3H3I", raw, 326) != (48, 48, 48, 72, 72, 72)
            or struct.unpack_from("<H", raw, 344)[0] != 192):
        raise ValueError("Head UV fixed LOD/draw/palette contract differs")
    lods = []
    for lod, sid, start in LOD_LAYOUT:
        if (struct.unpack_from("<I", raw, 85 + lod * 4)[0] != start
                or struct.unpack_from("<I", raw, 97 + lod * 4)[0] != start + 1920):
            raise ValueError("Head UV mirrored LOD vertex/index boundaries differ")
        indices = struct.unpack_from("<72H", raw, start + 1920)
        if max(indices) >= 48 or len(set(indices[:36])) != 24 or set(indices[:36]) != set(range(24)) or set(indices[36:]) != set(range(24, 48)):
            raise ValueError("Head UV base-head/outer-hat index coverage differs")
        for vertex in range(48):
            record = raw[start + vertex * 40:start + (vertex + 1) * 40]
            if (record[12:16] != b"\x00\x00\x00\x3c" or record[20:28] != bytes(8)
                    or record[28:36] != b"\xff" + bytes(7) or record[39] & 63 != 63):
                raise ValueError("Head UV fixed guide gate or rigid byte weights differ")
        lods.append({"lod": lod, "section": sid, "vertexOffset": start,
            "vertices": 48, "vertexStride": 40, "indexOffset": start + 1920,
            "indices": 72, "triangles": 24, "baseHeadVertices": 24, "outerHatVertices": 24})
    return {"sections": sections, "lods": lods, "metadataEndOffset": 90529,
        "eyeCoverGeometryEmpty": True, "mainDrawCount": 1, "paletteEntries": 192,
        "primaryUByteOffset": 8, "primaryVByteOffset": 10, "primaryUvEncoding": "little-endian float16",
        "guideLaneBytes12To16": "0000003c", "guideInfluencesDisabled": True,
        "primaryUvEngineSelectionVerified": False, "additionalUvChannelsDecoded": False}


def transform_pac(raw):
    """Flip only the primary V half fields; accepted inputs are hash-pinned."""
    fixed(raw, OLD_PAC_SHA256, "current head PAC")
    pac_structure(raw)
    result = bytearray(raw)
    for _, _, start in LOD_LAYOUT:
        for vertex in range(48):
            offset = start + vertex * 40 + 10
            value = struct.unpack_from("<e", raw, offset)[0]
            if value not in (0.75, 0.875, 1.0):
                raise ValueError("Head UV source V is outside the fixed dyadic values")
            struct.pack_into("<e", result, offset, 1.0 - value)
    payload = bytes(result)
    fixed(payload, NEW_PAC_SHA256, "primary V control")
    return payload


def restore_pac(payload):
    fixed(payload, NEW_PAC_SHA256, "primary V control inverse")
    pac_structure(payload)
    result = bytearray(payload)
    for _, _, start in LOD_LAYOUT:
        for vertex in range(48):
            offset = start + vertex * 40 + 10
            struct.pack_into("<e", result, offset, 1.0 - struct.unpack_from("<e", payload, offset)[0])
    return fixed(bytes(result), OLD_PAC_SHA256, "exact inverse source PAC")


def field_difference(source, payload):
    changes, allowed = [], set()
    for lod, sid, start in LOD_LAYOUT:
        for vertex in range(48):
            offset = start + vertex * 40 + 10
            allowed.update((offset, offset + 1))
            old, new = source[offset:offset + 2], payload[offset:offset + 2]
            changes.append({"lod": lod, "section": sid, "vertex": vertex,
                "byteSpan": [offset, offset + 2], "oldHex": old.hex(), "newHex": new.hex(),
                "oldV": struct.unpack("<e", old)[0], "newV": struct.unpack("<e", new)[0]})
    changed = [i for i, (a, b) in enumerate(zip(source, payload)) if a != b]
    if len(source) != len(payload) or len(changes) != 144 or len(changed) != 144 or not set(changed) <= allowed or restore_pac(payload) != source:
        raise ValueError("Head UV non-V field change or exact inverse failed")
    outside = bytes(value for i, value in enumerate(source) if i not in allowed)
    if outside != bytes(value for i, value in enumerate(payload) if i not in allowed):
        raise ValueError("Head UV changed an unapproved byte")
    return {"operation": "primary V = 1 - source primary V", "changedHalfFields": 144,
        "allowedFieldBytes": 288, "actualChangedBytes": len(changed),
        "actualChangedByteOffsets": changed, "fields": changes,
        "allOutsideVFieldBytesPreserved": True, "outsideVFieldBytes": len(outside),
        "outsideVFieldSha256": native.sha256(outside), "exactInverseToOriginalBytes": True,
        "metadataPaletteLodDrawsGeometryWeightsUAndGuideBytesPreserved": True,
        "packedNormalAndTangentBytesPreserved": True, "outerHatGeometryPreserved": True,
        "nativeShaderUvConventionVerified": False}


def dxt5_pixel(raw, x, y):
    """Read mip-zero BC3 evidence with integer RGB565 scaling/interpolation."""
    if not (0 <= x < 256 and 0 <= y < 256):
        raise ValueError("Head UV DDS pixel is outside mip zero")
    offset = 128 + ((y // 4) * 64 + x // 4) * 16
    a, b = raw[offset:offset + 2]
    alphas = [a, b] + ([(a * (7 - k) + b * k) // 7 for k in range(1, 7)] if a > b
                      else [(a * (5 - k) + b * k) // 5 for k in range(1, 5)] + [0, 255])
    c0, c1, choices = struct.unpack_from("<2HI", raw, offset + 8)
    def rgb(word):
        return ((word >> 11 & 31) * 255 // 31, (word >> 5 & 63) * 255 // 63, (word & 31) * 255 // 31)
    first, second = rgb(c0), rgb(c1)
    colors = [first, second, tuple((2 * a + b) // 3 for a, b in zip(first, second)),
              tuple((a + 2 * b) // 3 for a, b in zip(first, second))]
    slot = (y % 4) * 4 + x % 4
    alpha_index = (int.from_bytes(raw[offset + 2:offset + 8], "little") >> (3 * slot)) & 7
    return (*colors[(choices >> (2 * slot)) & 3], alphas[alpha_index])


def footprint(raw, rect):
    x0, y0, x1, y1 = rect
    pixels = [dxt5_pixel(raw, x, y) for y in range(y0, y1) for x in range(x0, x1)]
    return {"mip": 0, "pixelRectHalfOpen": list(rect), "texels": len(pixels),
        "alphaCounts": {str(k): v for k, v in sorted(Counter(p[3] for p in pixels).items())},
        "uniqueRgbaValues": len(set(pixels)),
        "rgbaSha256": native.sha256(bytes(value for pixel in pixels for value in pixel)),
        "decodePolicy": "RGB565 channel * 255 // channelMax; BC3 integer interpolation floor"}


def face_sampling(source, payload, diffuse):
    """Compare fixed face UV rectangles against real DDS bytes, without shader claims."""
    headbase.dds_audit(diffuse)
    def bounds(raw, first):
        coords = [struct.unpack_from("<2e", raw, 90529 + i * 40 + 8) for i in range(first, first + 4)]
        return [min(u for u, v in coords), min(v for u, v in coords), max(u for u, v in coords), max(v for u, v in coords)]
    old, new, hat = bounds(source, 12), bounds(payload, 12), bounds(payload, 36)
    if (old, new, hat) != ([0.125, 0.75, 0.25, 0.875], [0.125, 0.125, 0.25, 0.25], [0.625, 0.125, 0.75, 0.25]):
        raise ValueError("Head UV fixed face/hat rectangles differ")
    return {"classification": "offline DDS row-order footprint evidence only",
        "baseFaceVertexIndices": [12, 13, 14, 15], "outerHatFaceVertexIndices": [36, 37, 38, 39],
        "sourcePrimaryUvRect": old, "candidatePrimaryUvRect": new,
        "sourceIfVSelectsStoredTopOriginDdsRows": footprint(diffuse, (32, 192, 64, 224)),
        "candidateIfVSelectsStoredTopOriginDdsRows": footprint(diffuse, (32, 32, 64, 64)),
        "candidateIfShaderInvertsV": footprint(diffuse, (32, 192, 64, 224)),
        "candidateOuterHatIfVSelectsStoredTopOriginDdsRows": footprint(diffuse, (160, 32, 192, 64)),
        "candidateFaceRepresentativePixels": [
            {"ddsPixel": [x, y], "rgba": list(dxt5_pixel(diffuse, x, y))}
            for x, y in ((37, 49), (41, 49), (53, 49), (57, 49), (45, 53), (49, 53), (45, 57), (49, 57))],
        "shaderSamplingFilteringWrapLodAndTextureSelectionVerified": False,
        "nativeShaderUvConventionVerified": False, "nativeAlphaBehaviorVerified": False}


def make_report(sources):
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("Head UV source collection differs")
    for key, (_, digest) in SOURCE_SPECS.items():
        fixed(sources[key], digest, key)
        if len(sources[key]) != SOURCE_LIMITS[key]:
            raise ValueError("Head UV fixed source size differs")
    prior = strict_json(sources["headBaseColorReport"])
    if (prior["variant"] != headbase.VARIANT or prior["supportedExeSha256"] != native.EXE_SHA256
            or prior["candidateResources"] != [{"kind": "skinnedMaterial", "virtualPath": MATERIAL_PATH,
                "localFile": "resources/" + MATERIAL_PATH, "sha256": PRESERVED_MATERIAL_SHA256,
                "payloadSize": MATERIAL_SIZE, "sourceVirtualPath": headbase.NATIVE_MATERIAL_PATH,
                "templatePath": headbase.NATIVE_MATERIAL_PATH, "templateSha256": headbase.NATIVE_MATERIAL_SHA256,
                "templateArchiveFlags": 50, "archiveFlags": 50}]
            or prior["replacementContract"]["preservedPacSha256"] != OLD_PAC_SHA256
            or prior["diffuseDependency"]["sha256"] != DIFFUSE_SHA256):
        raise ValueError("Head UV fixed base-color report does not bind all preserved resources")
    material = ET.fromstring("<Root>" + sources["preservedMaterial"].decode("utf-8-sig") + "</Root>")
    variants = material.findall("./ModelPropertyList/ModelProperty")
    if len(variants) != 3 or any(len(v.findall(".//SkinnedMeshMaterialWrapper")) != 2 for v in variants):
        raise ValueError("Head UV preserved material lost its three-by-two contract")
    payload = transform_pac(sources["headPac"])
    row = {"kind": "skinnedMesh", "virtualPath": PAC_PATH, "localFile": "resources/" + PAC_PATH,
        "sha256": NEW_PAC_SHA256, "payloadSize": PAC_SIZE, "sourceVirtualPath": PAC_PATH,
        "templatePath": PAC_PATH, "templateSha256": OLD_PAC_SHA256,
        "templateArchiveFlags": ARCHIVE_FLAGS, "archiveFlags": ARCHIVE_FLAGS}
    return {"schemaVersion": 1, "variant": VARIANT, "supportedExeSha256": native.EXE_SHA256,
        "archiveIndexSha256": headbase.INDEX_SHA256, "candidateResources": [row],
        "sources": {key: {"localFile": relative, "sha256": digest, "payloadSize": len(sources[key])}
                    for key, (relative, digest) in SOURCE_SPECS.items()},
        "files": {**{relative: digest for relative, digest in SOURCE_SPECS.values()}, row["localFile"]: NEW_PAC_SHA256},
        "replacementContract": {"onlyReplacedVirtualPath": PAC_PATH, "previousPacSha256": OLD_PAC_SHA256,
            "replacementPacSha256": NEW_PAC_SHA256, "preservedMaterialVirtualPath": MATERIAL_PATH,
            "preservedMaterialSha256": PRESERVED_MATERIAL_SHA256, "allOtherResourcesMustBeByteIdentical": True,
            "wholePackageVerifiedByThisTool": False},
        "preservedDependencies": {"material": {"virtualPath": MATERIAL_PATH, "sha256": PRESERVED_MATERIAL_SHA256,
                "payloadSize": MATERIAL_SIZE, "expectedArchiveFlags": 50, "addedAsCandidateResource": False},
            "diffuse": {"virtualPath": DIFFUSE_PATH, "sha256": DIFFUSE_SHA256, "payloadSize": DIFFUSE_SIZE,
                "expectedArchiveFlags": 0, "addedAsCandidateResource": False, "dds": headbase.dds_audit(sources["diffuseTexture"])},
            "packageRegistrationVerifiedByThisTool": False},
        "audit": {"sourceBytes": PAC_SIZE, "candidateBytes": len(payload), "byteLengthDelta": 0,
            "structure": pac_structure(payload), "difference": field_difference(sources["headPac"], payload),
            "faceSampling": face_sampling(sources["headPac"], payload, sources["diffuseTexture"]),
            "preservedMaterialBytes": MATERIAL_SIZE, "preservedMaterialBomHex": sources["preservedMaterial"][:3].hex(),
            "preservedMaterialCrlfCount": sources["preservedMaterial"].count(b"\r\n"),
            "shaderParametersItemsAllOtherTexturePathsAndMaterialBytesPreserved": True},
        "integration": dict(INTEGRATION), "limitations": [
            "Offline single-private-head-PAC V-direction control; no package composition, installation, native call, process, service, save or inventory change.",
            "Only 144 primary V half fields change. Primary U, guide sentinel/gate, all geometry including the outer hat, byte weights, palette, sections, draw metadata, packed normals/tangents and all other PAC bytes are preserved with an exact inverse.",
            "Current three-variant/two-draw head PAMI and fixed MC DDS remain original bytes and dependency sources only. Shader, other color/normal/mask branches, alpha, selected variant and filtering remain unverified.",
            "DDS footprints use stored top-origin row coordinates; the shader may invert V or select another interpolant. UV retention and CDMW import/export conventions do not prove native shader sampling.",
            "Packed normal/tangent bytes deliberately remain unchanged; agreement with the flipped UV derivative or native normal-map behavior is not verified.",
            "The fixed classic Steve DDS contains facial color features and a transparent hat area. This is compressed existing skin provenance, not a lossless encoding or native face-rendering guarantee.",
            "This tool proves only its one-resource candidate. The other thirteen full-plan resources, metadata and runtime selection require separate strict integration; no unique root cause or completed Steve appearance is asserted."]}


def report_bytes(report):
    return (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")


def bounded_read(path, limit=131072):
    native.check_links(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Head UV input is missing or oversized")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("Head UV input changed beyond its size bound")
    return raw


def package_path(base, relative):
    path = native.output_directory(base / relative)
    if not path.is_relative_to(base):
        raise ValueError("Head UV input escapes its package")
    return path


def load_candidate(report_path):
    """Pure fixed reconstruction -> (report, {one PAC: bytes}, absolute Path snapshot)."""
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
        raise ValueError("Head UV report differs from the complete fixed reconstruction")
    output = package_path(path.parent, expected["candidateResources"][0]["localFile"])
    payload = bounded_read(output, PAC_SIZE)
    if payload != transform_pac(sources["headPac"]):
        raise ValueError("Head UV payload differs from the 144 fixed primary V fields")
    snapshot[output] = payload
    orientation.verify_snapshot(snapshot)
    return report, {PAC_PATH: payload}, snapshot


def read_inputs(head_report):
    _, payloads, snapshot = headbase.load_candidate(head_report)
    def copied_source(name):
        return snapshot[headbase.package_path(head_report.parent, headbase.SOURCE_SPECS[name][0])]
    sources = {"headPac": copied_source("preservedPac"), "preservedMaterial": payloads[MATERIAL_PATH],
        "diffuseTexture": copied_source("diffuseTexture"), "headBaseColorReport": snapshot[head_report]}
    return sources, snapshot


def prepare(output=DEFAULT_OUTPUT, head_report=DEFAULT_HEAD_BASECOLOR_REPORT):
    output, head_report = native.output_directory(output), native.output_directory(head_report)
    protected = [head_report.parent, *PROTECTED_DIRS]
    if output != native.output_directory(DEFAULT_OUTPUT):
        protected.append(DEFAULT_OUTPUT)
    output = orientation.preflight(output, protected)
    sources, snapshot = read_inputs(head_report)
    report, payload = make_report(sources), transform_pac(sources["headPac"])
    orientation.verify_snapshot(snapshot)
    output = orientation.preflight(output, protected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    writes = {relative: sources[key] for key, (relative, _) in SOURCE_SPECS.items()}
    writes["resources/" + PAC_PATH], writes[REPORT_NAME] = payload, report_bytes(report)
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
    parser.add_argument("--head-basecolor-report", type=Path, default=DEFAULT_HEAD_BASECOLOR_REPORT)
    args = parser.parse_args()
    report = prepare(args.output, args.head_basecolor_report)
    print(json.dumps({"output": str(args.output), "candidateResources": report["candidateResources"],
        "changedHalfFields": report["audit"]["difference"]["changedHalfFields"],
        "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
