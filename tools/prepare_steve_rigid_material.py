"""Bind fixed twelve rigid layers to the existing Steve DDS trio, offline.

This authors material bindings, not a prefab, collision control or installable
package. Static Standard alpha behavior is unverified; every layer is retained.
Run in a fresh Python process with the existing fixed local CDMW dependencies.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path, PurePosixPath
import struct
import xml.etree.ElementTree as ET

import prepare_steve_rigid_geometry as geom

ROOT = geom.ROOT
DEFAULT_OUTPUT = ROOT / "build/steve-rigid-material-1.21.1"
REPORT_NAME = "steve-rigid-material-report.json"
VARIANT = "official-steve-twelve-rigid-layers-static-standard-material-bindings"
GEOMETRY_OUTPUT = geom.DEFAULT_OUTPUT
GEOMETRY_REPORT_SHA256 = "40407ce6766dcb3efad97e87c0dacb9ffdaa67f8cb128ef0c61adc5d4b97f8f7"
STEVE_MATERIAL_OUTPUT = ROOT / "build/steve-material"
STEVE_MATERIAL_REPORT_NAME = "steve-material-report.json"
STEVE_MATERIAL_REPORT_SHA256 = "8c27cadac28aec1b812ff007cf03d616667929d8fa86e1005370916c3b7f5812"
PRIMITIVE_NAME = "crimsonmc_steve_1_21_1.dds"
OLD_PRIMITIVE_NAME = "cd_testfield_grid_03.dds"
PAM_NAME_RANGES = ((1056, 1312), (1312, 1568))
PAMLOD_NAME_RANGES = ((108, 364), (364, 620))
DDS_PATHS = {
    "_baseColorTexture": "character/texture/crimsonmc_steve_1_21_1.dds",
    "_normalTexture": "character/texture/crimsonmc_steve_1_21_1_n.dds",
    "_materialTexture": "character/texture/crimsonmc_steve_1_21_1_sp.dds",
}
DDS_PINS = {
    DDS_PATHS["_baseColorTexture"]: "653aa5d14644e515da6284fecd65711fae65a187323697a1b571dbbab74a6b1a",
    DDS_PATHS["_normalTexture"]: "3555d0a27af8de753c2368e8878a995469577ff40515d9467e4540ff2feebc33",
    DDS_PATHS["_materialTexture"]: "047babdb8e93774756a770cdd4387e091fe21527dfb4dca9ad2c8e6f6e29f2db",
}
DDS_FORMATS = dict(zip(DDS_PATHS.values(), ("DXT5", "BC5U", "DXT1")))
DDS_LAST4 = dict(zip(DDS_PATHS.values(), (13, 4, 4)))
LIMIT = geom.LIMIT
require, digest = geom.require, geom.digest
input_path, input_bytes, report_bytes = geom.input_path, geom.input_bytes, geom.report_bytes
merge_snapshot = geom.merge_snapshot
strict_json = geom.adapter.player.strict_json


def preflight(output):
    output = geom.adapter.assets.output_directory(Path(output))
    require(output.name.startswith("steve-rigid-material-"), "Material output must use its owned build prefix")
    protected = [ROOT / name for name in ("tools", "runtime", "minecraft", "downloads",
                 "build/steve-1.21.1", "build/steve-player-pose-1.21.1",
                 "build/steve-rigid-render-contract-20261008",
                 "build/steve-rigid-material-contract-20261008")]
    protected += [geom.SOURCE, geom.DEPS, geom.block.DEFAULT_OUTPUT,
                  geom.adapter.DEFAULT_OUTPUT, GEOMETRY_OUTPUT, STEVE_MATERIAL_OUTPUT]
    if output != DEFAULT_OUTPUT:
        protected.append(DEFAULT_OUTPUT)
    for path in protected:
        path = input_path(path)
        require(not (output == path or output.is_relative_to(path) or path.is_relative_to(output)),
                "Material output overlaps a protected source/canonical")
    require(not output.exists(), "Material output already exists; never overwrite")
    return output


def relative_file(name):
    require(type(name) is str and name and "\\" not in name, "Unsafe resource relative filename")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts and ":" not in name,
            "Unsafe resource relative filename")
    return name


def snapshot_file(inputs, path, pin=None):
    path = input_path(path)
    raw = input_bytes(path, LIMIT)
    if pin is not None:
        require(digest(raw) == pin, "Fixed material input differs: " + path.name)
    merge_snapshot(inputs["snapshot"], {path: raw})
    return raw


def load_inputs():
    """Use the existing strict geometry sources once, then bind fixed outputs."""
    inputs = geom.load_inputs()
    source_geometry = snapshot_file(inputs, GEOMETRY_OUTPUT / geom.REPORT_NAME,
                                    GEOMETRY_REPORT_SHA256)
    geometry_report = strict_json(source_geometry)
    require(geometry_report["variant"] == geom.VARIANT and len(geometry_report["parts"]) == 12
            and len(geometry_report["files"]) == 24,
            "Fixed geometry inventory differs")
    require(geometry_report["sources"] == inputs["sources"]
            and geometry_report["cdmw"] == inputs["cdmw"],
            "Fixed geometry provenance differs from current admitted sources")
    geometry_files = {}
    for name, pin in geometry_report["files"].items():
        relative_file(name)
        geometry_files[name] = snapshot_file(inputs, GEOMETRY_OUTPUT / name, pin)
    expected_names = set()
    for row in geometry_report["parts"]:
        joint, mesh = row["joint"], row["sourceMesh"]
        require(joint in geom.adapter.PARTS, "Unexpected fixed geometry joint")
        sources = inputs["adapter"]["geometry"][joint]["meshes"]
        match = [source for source in sources if source["name"] == mesh]
        require(len(match) == 1 and row["outerLayer"] is match[0]["outerLayer"],
                "Fixed geometry layer identity differs")
        require(row["sourceGeometry"]["sha256"] == digest(report_bytes(match[0])),
                "Fixed geometry source row differs")
        for key in ("pam", "pamlod"):
            expected = f"geometry/{joint}/{mesh}.{key}"
            require(row[key] == expected, "Fixed geometry filename differs")
            expected_names.add(expected)
    require(set(geometry_files) == expected_names and len(expected_names) == 24,
            "Fixed geometry files are incomplete")
    material_report_raw = snapshot_file(inputs, STEVE_MATERIAL_OUTPUT / STEVE_MATERIAL_REPORT_NAME,
                                       STEVE_MATERIAL_REPORT_SHA256)
    material_report = strict_json(material_report_raw)
    texture_rows = [row for row in material_report["candidateResources"] if row["kind"] == "texture"]
    require(len(texture_rows) == 3 and {row["virtualPath"] for row in texture_rows} == set(DDS_PINS),
            "Fixed Steve DDS inventory differs")
    from cdmw.core.dds_native import inspect_dds_native
    textures, audits = {}, {}
    for row in texture_rows:
        virtual = row["virtualPath"]
        require(row["localFile"] == "resources/" + virtual and row["sha256"] == DDS_PINS[virtual],
                "Fixed Steve DDS source row differs")
        raw = snapshot_file(inputs, STEVE_MATERIAL_OUTPUT / row["localFile"], DDS_PINS[virtual])
        info = inspect_dds_native(raw)
        require(not info.reason and info.supported_compressed
                and (info.width, info.height, info.mip_count, info.fourcc, info.data_offset)
                == (256, 256, 9, DDS_FORMATS[virtual], 128), "Fixed Steve DDS format differs")
        levels = info.mip_levels
        require(len(levels) == 9 and levels[-1].offset + levels[-1].byte_count == len(raw),
                "Fixed Steve DDS mip extent differs")
        last4 = struct.unpack_from("<I", raw, 124)[0]
        require(last4 == DDS_LAST4[virtual], "Fixed Steve DDS classification differs")
        textures[virtual] = raw
        audits[virtual] = {"sha256": digest(raw), "bytes": len(raw), "fourcc": info.fourcc,
                           "width": info.width, "height": info.height, "mipCount": info.mip_count,
                           "nativeLast4": last4, "sourceBytesPreserved": True,
                           "shaderAlphaBehaviorVerified": False}
    snapshot_file(inputs, Path(__file__))
    inputs.update(geometryReport=geometry_report, geometryFiles=geometry_files,
                  textures=textures, textureAudit=audits)
    geom.verify_inputs(inputs)
    return inputs


def replace_descriptor_names(original, ranges):
    old = OLD_PRIMITIVE_NAME.encode("ascii")
    new = PRIMITIVE_NAME.encode("ascii").ljust(256, b"\0")
    require(len(old) < 256 and len(new) == 256, "Primitive name exceeds its fixed descriptor field")
    candidate = bytearray(original)
    for start, end in ranges:
        require(end - start == 256 and original[start:end].split(b"\0", 1)[0] == old,
                "Fixed geometry descriptor name differs")
        # Original unused string bytes are not necessarily zero. The admitted
        # oak fixed_string route replaces the complete 256B field; its inverse
        # must restore this particular source span, including its opaque tail.
        candidate[start:end] = new
    candidate = bytes(candidate)
    inverse = bytearray(candidate)
    for start, end in ranges:
        inverse[start:end] = original[start:end]
    require(bytes(inverse) == original and len(candidate) == len(original),
            "Geometry descriptor inverse does not restore every source byte")
    return candidate


def make_pami(original, virtual_stem):
    """Change only five attribute values; preserve the complete other XML tree."""
    expected_pin = geom.block.TEMPLATE_HASHES[geom.block.BASE + ".pami"]
    require(digest(original) == expected_pin, "Blue Standard PAMI source differs")
    template = ET.fromstring(original)
    require(template.tag == "StaticMeshInstance" and template.get("Version") == "1",
            "Blue Standard PAMI root differs")
    candidate = copy.deepcopy(template)
    static = candidate.find("StaticMesh")
    material = candidate.find("MaterialData/Material")
    require(static is not None and material is not None
            and material.find("Common").get("MaterialName") == "Standard"
            and len(material.find("Permutations")) == 0, "Blue Standard material shape differs")
    parameters = material.findall("Parameters/MaterialParameterTexture")
    require(len(parameters) == 3 and {node.get("Name") for node in parameters} == set(DDS_PATHS),
            "Blue Standard texture parameters differ")
    static.set("Path", virtual_stem + ".pam")
    material.set("PrimitiveName", PRIMITIVE_NAME)
    for node in parameters:
        node.set("Value", DDS_PATHS[node.get("Name")])
    payload = ET.tostring(candidate, encoding="utf-8", xml_declaration=False)
    require(payload.startswith(b'<StaticMeshInstance Version="1">') and not payload.startswith(b"<?xml"),
            "PAMI must use the reviewed UTF8 serialization without XML declaration")
    inverse = ET.fromstring(payload)
    inverse.find("StaticMesh").set("Path", template.find("StaticMesh").get("Path"))
    inverse_material = inverse.find("MaterialData/Material")
    inverse_material.set("PrimitiveName", template.find("MaterialData/Material").get("PrimitiveName"))
    original_values = {node.get("Name"): node.get("Value") for node in
                       template.findall("MaterialData/Material/Parameters/MaterialParameterTexture")}
    for node in inverse_material.findall("Parameters/MaterialParameterTexture"):
        node.set("Value", original_values[node.get("Name")])
    require(ET.tostring(inverse) == ET.tostring(template),
            "PAMI changed XML outside the five reviewed attribute values")
    return payload


def prepare(output=DEFAULT_OUTPUT):
    output = preflight(output)
    inputs = load_inputs()
    geom.protect_snapshot(output, inputs["snapshot"])
    files, parts = {}, []
    template = inputs["templates"][geom.block.BASE + ".pami"]
    for source in inputs["geometryReport"]["parts"]:
        mesh = source["sourceMesh"]
        stem = "object/00_common/system/crimsonmc_steve_rigid_" + mesh
        names = {key: "resources/" + stem + "." + key for key in ("pam", "pamlod", "pami")}
        files[names["pam"]] = replace_descriptor_names(inputs["geometryFiles"][source["pam"]], PAM_NAME_RANGES)
        files[names["pamlod"]] = replace_descriptor_names(inputs["geometryFiles"][source["pamlod"]], PAMLOD_NAME_RANGES)
        files[names["pami"]] = make_pami(template, stem)
        parts.append({"joint": source["joint"], "sourceMesh": mesh, "outerLayer": source["outerLayer"],
                      **names, "virtualStem": stem})
    for virtual, raw in inputs["textures"].items():
        files["resources/" + virtual] = raw
    require(len(files) == 39 and len(parts) == 12, "Rigid material output inventory differs")
    for name in files:
        relative_file(name)
    sources = {}
    for path, raw in sorted(inputs["snapshot"].items()):
        relative = os.path.relpath(path, ROOT).replace("\\", "/")
        require(not Path(relative).is_absolute() and input_path(ROOT / relative) == path,
                "Material provenance cannot be represented relative to ROOT")
        sources[relative] = {"sha256": digest(raw), "bytes": len(raw)}
    report = {"schemaVersion": 1, "minecraftVersion": "1.21.1", "variant": VARIANT,
              "sources": sources, "files": {name: digest(raw) for name, raw in files.items()},
              "parts": parts, "textureAudit": inputs["textureAudit"],
              "fixedSources": {"geometryReportSha256": GEOMETRY_REPORT_SHA256,
                               "steveMaterialReportSha256": STEVE_MATERIAL_REPORT_SHA256,
                               "bluePamiSha256": digest(template)},
              "geometryEdits": {"primitiveName": PRIMITIVE_NAME, "oldPrimitiveName": OLD_PRIMITIVE_NAME,
                                "pamNameRanges": [list(row) for row in PAM_NAME_RANGES],
                                "pamlodNameRanges": [list(row) for row in PAMLOD_NAME_RANGES],
                                "fieldBytes": 256, "modifiedFields": 48,
                                "inverseRestoresEverySourceByte": True,
                                "allOtherGeometryBytesPreserved": True},
              "material": {"shader": "Standard", "primitiveName": PRIMITIVE_NAME,
                           "textureParameters": DDS_PATHS, "changedAttributeValuesPerPami": 5,
                           "serialization": "UTF8 without BOM or XML declaration; existing oak serializer",
                           "remainingXmlTreePreserved": True, "alphaParametersAdded": False},
              "coordinates": copy.deepcopy(inputs["geometryReport"]["coordinates"]),
              "integration": {"materialBindingsAuthored": True, "alphaBehaviorVerified": False,
                              "nativeMaterialLoaded": False, "collisionless": False,
                              "nativeApplied": False, "installed": False,
                              "installableResourcePackage": False, "groupObjects": False,
                              "ownerFollow": False, "animationSystemComplete": False},
              "limitations": ["Local material bindings only; no prefab, meshinfo, HKX, package or installation manifest.",
                              "All twelve base/outer layers are retained. Standard BC3 alpha discard, blending and outer visibility remain unverified.",
                              "The existing Steve DDS trio is copied verbatim at its existing virtual paths; native last4 classification is not converted or an alpha-control proof.",
                              "Primitive and material names follow the reviewed synchronized oak route; no general engine naming rule is inferred.",
                              "Geometry, indices, bbox, UV and packed donor fields are preserved apart from the four fixed descriptor strings per layer.",
                              "Static Standard differs from SkinnedMeshStandard; no guessed shader parameters or permutations are added.",
                              "Renderer UV/tangent consistency, resource loading, owner binding, collision absence and runtime lifecycle remain unverified."]}
    encoded = report_bytes(report)
    require(len(encoded) <= LIMIT, "Material report exceeds its read bound")
    geom.verify_inputs(inputs)
    output = preflight(output)
    geom.protect_snapshot(output, inputs["snapshot"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    for name, raw in (*files.items(), (REPORT_NAME, encoded)):
        path = output / name
        geom.block.native.check_links(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    geom.verify_inputs(inputs)
    require({path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            == set(files) | {REPORT_NAME}, "Material output inventory differs")
    for name, raw in (*files.items(), (REPORT_NAME, encoded)):
        require(input_bytes(output / name, LIMIT) == raw, "Material output changed during publication")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = prepare(args.output)
    print(json.dumps({"output": str(geom.adapter.assets.output_directory(args.output)),
                      "files": len(report["files"]), "parts": len(report["parts"]),
                      **report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
