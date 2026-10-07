"""Prepare the real oak-log/static-mesh asset slice without modifying the game.

Python 3.12, hash-pinned CDMW source, version-pinned dependencies and the original-class MC
block export are required. Outputs, including licensed templates, stay in
ignored build. A parseable candidate is not an in-game rendering acceptance.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import xml.etree.ElementTree as ET

import prepare_native_steve as native

ROOT = native.ROOT
BASE = "object/00_common/system/cd_testfield_grid_box_1m"
BIN_BASE = "object/bin__/00_common/system/cd_testfield_grid_box_1m"
TEX = "object/texture/cd_testfield_grid_03"
TEMPLATE_HASHES = {
    BASE + ".pam": "4b22a194c5150f3033e5b5226fb5605ec02a4627d0156c1f2de5f51b7eaf9b36",
    BASE + ".pami": "a8c6dac4dc64a78af8acee4430bd200130a74300ffe4d0a71941399a6745e77e",
    BASE + ".pamlod": "1a695c516ed816e4b842ac13cc837d8c47cb8e9e72160ae43287856f16659b1f",
    BASE + ".hkx": "cc177ef7c1fa4daf55075c50b2f5b384eb92c66c7a771b96367fb601e2f8939c",
    BIN_BASE + ".meshinfo": "504b30976d10c67ad5eaa2c51ba8259e5cf5f1995cdbfb35cc2c73410df13caf",
    BIN_BASE + ".prefab": "e05cf4bab0cfc7c59398ea45cb0b62f955c7c6f5dc9e2c5d17d59fef5658f56c",
    TEX + ".dds": "96bb64e2f3cbaf48819dd2bf0b7fa57425f8241b8db736f5c6469b15e05a967f",
    TEX + "_n.dds": "3555d0a27af8de753c2368e8878a995469577ff40515d9467e4540ff2feebc33",
    TEX + "_sp.dds": "92e1c74bfd10d820af28965df3451ff8283b9cc525568aa781797f366c6df5e0",
}
MC_HASHES = {
    "meshes/oak_log__axis_x__choice_0.gltf": "25b49e6f60a002e27a2ce3cdbc6191df511a637af588f5ffb2106f1be5a59618",
    "meshes/oak_log__axis_y__choice_0.gltf": "adc2138cd443e190dcc5fb7eedb2d10c0cde54844026f28998d41bc6f90be000",
    "meshes/oak_log__axis_z__choice_0.gltf": "055aac9baf2cc70a378b6a6067ddc4259faa1d59689313da2dfcb0c9ee094b16",
    "meshes/oak_log__axis_x__choice_0.bin": "e6d63d356aa995736da8317bb251e6908b04e386780930ec8036840943cf789a",
    "meshes/oak_log__axis_y__choice_0.bin": "99a416d4e96809415446a600bbc6c8bc14212178a325880975641de4b9309e62",
    "meshes/oak_log__axis_z__choice_0.bin": "bc8d28f89a20631d78f3f998dfe0e85750b8bf6e047e6ddc6b0b445fa98df67c",
    "textures/minecraft/block/oak_log.png": "060c93128fb65aa350a84e4b6576e616c47d40211bbe537cfe923a81d072e30c",
    "textures/minecraft/block/oak_log_top.png": "62f38b25ae28b6c4842ee5a83f790394b1ec4d6c6f20dd52044394855346a2a7",
}
TEXTURE_TARGET = "object/texture/crimsonmc_oak_log_atlas"
MATERIAL_SERIALIZATION = "pami-utf8-no-declaration-v1"
DEFAULT_OUTPUT = ROOT / "build/native-block-declaration-fixed"


def read_mc(asset: Path) -> tuple[dict, dict[str, list[dict]]]:
    native.check_links(asset)
    files = {}
    for name, expected in MC_HASHES.items():
        path = asset / name
        native.check_links(path)
        files[name] = path.read_bytes()
        if native.sha256(files[name]) != expected:
            raise ValueError(f"MC oak-log input differs from reviewed 1.21.1 export: {name}")
    axes = {}
    for axis in "xyz":
        stem = f"meshes/oak_log__axis_{axis}__choice_0"
        doc = json.loads(files[stem + ".gltf"])
        binary = files[stem + ".bin"]
        if len(doc["nodes"]) != 1 or doc["nodes"][0] != {"mesh": 0, "name": "minecraft:oak_log"}:
            raise ValueError("Oak log acquired an unreviewed node transform")
        if doc["extras"]["selector"] != f"axis={axis}" or doc["extras"]["nativeIntegrated"]:
            raise ValueError("Oak-log blockstate identity differs")
        if len(doc["buffers"]) != 1 or doc["buffers"][0]["uri"] != PurePosixPath(stem).name + ".bin":
            raise ValueError("Oak-log buffer is not its fixed local binary")
        primitives = doc["meshes"][0]["primitives"]
        if len(primitives) != 6:
            raise ValueError("Expected the six original oak-log quads")
        faces = []
        for primitive in primitives:
            attrs = primitive["attributes"]
            positions = native.read_accessor(doc, binary, attrs["POSITION"], "VEC3", 5126)
            normals = native.read_accessor(doc, binary, attrs["NORMAL"], "VEC3", 5126)
            uvs = native.read_accessor(doc, binary, attrs["TEXCOORD_0"], "VEC2", 5126)
            indices = [row[0] for row in native.read_accessor(doc, binary, primitive["indices"], "SCALAR", 5123)]
            if len(positions) != 4 or len(normals) != 4 or len(uvs) != 4 or len(indices) != 6:
                raise ValueError("Oak-log quad shape differs from original export")
            material = doc["materials"][primitive["material"]]["name"]
            if material not in ("minecraft:block/oak_log", "minecraft:block/oak_log_top"):
                raise ValueError("Unsupported oak-log texture route")
            if any(not 0 <= v <= 1 for row in positions + uvs for v in row):
                raise ValueError("Oak-log geometry/UV exceeds the reviewed unit cuboid")
            faces.append({"positions": positions, "normals": normals, "uvs": uvs,
                          "indices": indices, "material": material,
                          "sourceQuadId": primitive["extras"]["sourceQuadId"]})
        axes[axis] = faces
    return files, axes


def validate_template(payloads: dict) -> tuple[object, object, dict, dict]:
    from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
    from cdmw.modding.mesh_pam_builder import _inspect_pam_layout, build_pam
    from cdmw.modding.mesh_pamlod_builder import _inspect_pamlod_lod0_layout
    from cdmw.modding.mesh_importer import rebuild_mesh_with_report
    from cdmw.core.prefab_binary import decode_prefab_binary, walk_is_determined
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    for path, digest in TEMPLATE_HASHES.items():
        if native.sha256(payloads[path]) != digest:
            raise ValueError(f"Blue-cube native template SHA mismatch: {path}")
    pam = parse_pam(payloads[BASE + ".pam"], BASE + ".pam")
    lod = parse_pamlod(payloads[BASE + ".pamlod"], BASE + ".pamlod")
    layout = _inspect_pam_layout(payloads[BASE + ".pam"])
    lod_layout = _inspect_pamlod_lod0_layout(payloads[BASE + ".pamlod"])
    if (pam.total_vertices, pam.total_faces, len(pam.submeshes)) != (24, 12, 1):
        raise ValueError("Unexpected blue-cube template topology")
    if pam.has_bones or pam.bbox_min != (0, 0, 0) or pam.bbox_max != (1, 1, 1):
        raise ValueError("Blue-cube template is not the static one-metre unit cuboid")
    if layout["kind"] != "local" or layout["geom_off"] != 1712 or layout["entries"][0]["stride"] != 20:
        raise ValueError("Blue-cube PAM record layout is unsupported")
    if (lod_layout["kind"], lod_layout["lod_count"], lod_layout["vertex_base"], lod_layout["stride"],
        lod_layout["old_lod0_end"]) != ("lod0_single", 1, 736, 20, len(payloads[BASE + ".pamlod"])):
        raise ValueError("Blue-cube PAMLOD record layout is unsupported")
    for mesh, path in ((pam, BASE + ".pam"), (lod, BASE + ".pamlod")):
        rebuilt = rebuild_mesh_with_report(mesh, payloads[path], original_mesh=mesh)
        if rebuilt.data != payloads[path] or not rebuilt.report.byte_identical:
            raise ValueError("Static mesh no-edit rebuild was not byte-identical")
    if build_pam(pam, payloads[BASE + ".pam"]) != payloads[BASE + ".pam"]:
        raise ValueError("Direct PAM no-edit writer changed source bytes")
    prefab = payloads[BIN_BASE + ".prefab"]
    if not walk_is_determined(prefab) or not decode_prefab_binary(prefab).walk_complete:
        raise ValueError("Native prefab structural walk is incomplete")
    if [s.text for s in decode_prefab_binary(prefab).all_strings()] != [BASE + ".pami"]:
        raise ValueError("Native prefab acquired unexpected resource dependencies")
    if rewrite_prefab_paths(prefab, {}).data != prefab:
        raise ValueError("Native prefab no-edit structural rewrite changed bytes")
    material = ET.fromstring(payloads[BASE + ".pami"])
    if material.tag != "StaticMeshInstance" or material.find("StaticMesh").get("Path") != BASE + ".pam":
        raise ValueError("Template PAMI does not reference the exact static geometry")
    node = material.find("MaterialData/Material")
    expected = {"_baseColorTexture": TEX + ".dds", "_normalTexture": TEX + "_n.dds",
                "_materialTexture": TEX + "_sp.dds"}
    found = {p.get("Name"): p.get("Value") for p in node.findall("Parameters/MaterialParameterTexture")}
    if node.get("PrimitiveName") != pam.submeshes[0].material or node.find("Common").get("MaterialName") != "Standard" or found != expected:
        raise ValueError("Template Standard material bindings differ")
    return pam, lod, layout, lod_layout


def map_mc_corners(pam: object, faces: list[dict]) -> list[dict]:
    """Match each split native corner by both position and face normal."""
    part = pam.submeshes[0]
    mapped = []
    for pos, normal in zip(part.vertices, part.normals):
        matches = []
        for face in faces:
            for idx, (mc_pos, mc_normal) in enumerate(zip(face["positions"], face["normals"])):
                if max(abs(a - b) for a, b in zip(pos, mc_pos)) <= 1 / 65535 + 1e-7 and max(abs(a - b) for a, b in zip(normal, mc_normal)) < 1e-6:
                    uv = face["uvs"][idx]
                    tile = int(face["material"].endswith("oak_log_top"))
                    matches.append({"mcPosition": mc_pos, "mcNormal": mc_normal, "mcUv": uv,
                                    "atlasTile": tile, "sourceQuadId": face["sourceQuadId"],
                                    "nativeUv": ((uv[0] + tile) / 2, 1 - uv[1])})
        if len(matches) != 1:
            raise ValueError("MC/native cube corner matching is missing or ambiguous")
        mapped.append(matches[0])
    if len(mapped) != 24 or sum(row["atlasTile"] for row in mapped) != 8:
        raise ValueError("Oak-log did not map exactly two end faces and four side faces")
    # Verify triangle winding independently of importer/source face order.
    for face in part.faces:
        p0, p1, p2 = (mapped[i]["mcPosition"] for i in face)
        a, b = [p1[i] - p0[i] for i in range(3)], [p2[i] - p0[i] for i in range(3)]
        cross = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        if sum(cross[i] * mapped[face[0]]["mcNormal"][i] for i in range(3)) < 0.99:
            raise ValueError("Native triangle winding disagrees with original MC face normal")
    return mapped


def fixed_string(payload: bytearray, offset: int, name: str) -> None:
    data = name.encode("ascii")
    if len(data) >= 256 or offset < 0 or offset + 256 > len(payload):
        raise ValueError("Native primitive string exceeds its exact 256-byte descriptor field")
    payload[offset:offset + 256] = data + bytes(256 - len(data))


def geometry_candidate(payloads: dict, pam: object, lod: object, layout: dict,
                       lod_layout: dict, faces: list[dict]) -> tuple[bytes, bytes, list[dict]]:
    from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
    from cdmw.modding.mesh_pamlod_builder import _serialize_pamlod_lod0_full_rebuild
    mapped = map_mc_corners(pam, faces)
    source = payloads[BASE + ".pam"]
    result = bytearray(source)
    part = pam.submeshes[0]
    for offset, row in zip(part.source_vertex_offsets, mapped):
        if offset < layout["geom_off"] or offset + 20 > layout["entries"][0]["idx_off"]:
            raise ValueError("Native vertex lies outside validated local record range")
        struct.pack_into("<ee", result, offset + 8, *row["nativeUv"])
    name = PurePosixPath(TEXTURE_TARGET).name + ".dds"
    desc = layout["entries"][0]["desc_off"]
    fixed_string(result, desc + 0x10, name)
    fixed_string(result, desc + 0x110, name)
    parsed = parse_pam(bytes(result), BASE + ".pam")
    if parsed.submeshes[0].vertices != part.vertices or parsed.submeshes[0].faces != part.faces:
        raise ValueError("UV/primitive update changed original static cube geometry")
    edited = copy.deepcopy(parsed.submeshes[0])
    # The pinned writer updates the exact PAMLOD descriptor counts. It normally
    # picks shading donors from a reduced 13-vertex LOD. Instead retain each of
    # the matching cube's complete 20-byte PAM records, whose static layout is
    # identical; this avoids inventing packed normals/tangents or losing faces.
    lod_bytes = bytearray(_serialize_pamlod_lod0_full_rebuild([edited], lod,
                                                            payloads[BASE + ".pamlod"], BASE + ".pamlod"))
    struct.pack_into("<3f", lod_bytes, 0x10, *pam.bbox_min)
    struct.pack_into("<3f", lod_bytes, 0x1C, *pam.bbox_max)
    fixed_string(lod_bytes, lod_layout["entry"]["tex_start"], name)
    fixed_string(lod_bytes, lod_layout["entry"]["tex_start"] + 0x100, name)
    geom = bytes(result[layout["geom_off"]:layout["old_geom_end"]])
    lod_bytes[lod_layout["vertex_base"]:] = geom
    found = parse_pamlod(bytes(lod_bytes), BASE + ".pamlod")
    validate_geometry(bytes(result), bytes(lod_bytes), mapped)
    if found.bbox_min != pam.bbox_min or found.bbox_max != pam.bbox_max:
        raise ValueError("Native LOD changed the one-metre bounding box")
    return bytes(result), bytes(lod_bytes), mapped


def validate_geometry(pam_data: bytes, lod_data: bytes, mapped: list[dict]) -> None:
    from cdmw.modding.mesh_parser import parse_pam, parse_pamlod
    main, lod = parse_pam(pam_data), parse_pamlod(lod_data)
    for mesh in (main, lod):
        if (len(mesh.submeshes), mesh.total_vertices, mesh.total_faces) != (1, 24, 12):
            raise ValueError("Native candidate lost complete cube topology")
        part = mesh.submeshes[0]
        if (part.faces != main.submeshes[0].faces or len(part.vertices) != len(mapped)
                or len(part.uvs) != len(mapped) or len(part.normals) != len(mapped)):
            raise ValueError("Native candidate LOD changed face indices")
        for pos, uv, normal, row in zip(part.vertices, part.uvs, part.normals, mapped):
            if max(abs(a - b) for a, b in zip(pos, row["mcPosition"])) > 1 / 65535 + 1e-7:
                raise ValueError("Native candidate geometry exceeds its uint16 quantization tolerance")
            if max(abs(a - b) for a, b in zip(uv, row["nativeUv"])) > 0.0005:
                raise ValueError("Native candidate UV round-trip exceeds half-float tolerance")
            if max(abs(a - b) for a, b in zip(normal, row["mcNormal"])) > 1e-6:
                raise ValueError("Native candidate geometric face normals differ from MC")


def make_material(payload: bytes, axis: str) -> bytes:
    if axis not in ("x", "y", "z") or native.sha256(payload) != TEMPLATE_HASHES[BASE + ".pami"]:
        raise ValueError("PAMI requires a known axis and the fixed native template")
    doc = ET.fromstring(payload)
    doc.find("StaticMesh").set("Path", f"object/00_common/system/crimsonmc_oak_log_{axis}.pam")
    material = doc.find("MaterialData/Material")
    material.set("PrimitiveName", PurePosixPath(TEXTURE_TARGET).name + ".dds")
    # RepresentColor is a native preview/representative colour field. Preserve
    # its verified value; do not guess that it controls the shader's tint.
    names = {"_baseColorTexture": ".dds", "_normalTexture": "_n.dds", "_materialTexture": "_sp.dds"}
    for node in material.findall("Parameters/MaterialParameterTexture"):
        node.set("Value", TEXTURE_TARGET + names[node.get("Name")])
    # The real native PAMI begins directly with StaticMeshInstance. The isolated Y
    # control proved that removing only the prior 39-byte declaration enables
    # loading. Keep the exact ElementTree body, UTF-8 encoding and spacing.
    return ET.tostring(doc, encoding="utf-8", xml_declaration=False)


def textures_candidate(payloads: dict, files: dict, decoder_python: Path) -> tuple[dict, dict, dict]:
    from prepare_steve_material import decode_png, encode_dds, nearest_expand, verify_texture, independent_decode
    from cdmw.core.dds_native import inspect_dds_native
    width, height, side = decode_png(files["textures/minecraft/block/oak_log.png"])
    top_w, top_h, top = decode_png(files["textures/minecraft/block/oak_log_top.png"])
    if (width, height, top_w, top_h) != (16, 16, 16, 16):
        raise ValueError("Original oak-log textures are not the fixed 16-pixel square maps")
    decoder, decoded = independent_decode([files["textures/minecraft/block/oak_log.png"],
                                          files["textures/minecraft/block/oak_log_top.png"]], decoder_python)
    if decoded != [(16, 16, side), (16, 16, top)]:
        raise ValueError("Original PNG decoding differs from independent Pillow")
    atlas = [pixel for y in range(16) for pixel in side[y * 16:(y + 1) * 16] + top[y * 16:(y + 1) * 16]]
    # Each original pixel occupies a whole BC1 block at LOD0; only RGB565
    # endpoint quantization remains. Mips and native filtering still need game QA.
    w, h, expanded = nearest_expand(32, 16, atlas, 4)
    pixels = {".dds": expanded, "_n.dds": [(128, 128, 255, 255)] * (w * h),
              "_sp.dds": [(0, 255, 0, 255)] * (w * h)}
    output, audit = {}, {}
    for suffix, rgba in pixels.items():
        donor = payloads[TEX + suffix]
        fourcc = "BC5U" if suffix == "_n.dds" else "DXT1"
        data = encode_dds(w, h, rgba, fourcc=fourcc, template_header=donor[:128])
        info = inspect_dds_native(data)
        if (info.width, info.height, info.fourcc, info.mip_count) != (128, 64, fourcc, 8):
            raise ValueError("DDS candidate native header/mip chain differs")
        if not info.supported_compressed or data[124:128] != donor[124:128]:
            raise ValueError("DDS candidate lost its native compressed format/classification")
        independent, decoded_audit = verify_texture(data, w, h, rgba, fourcc, decoder_python)
        if independent != decoder:
            raise ValueError("Independent texture decoder changed during preparation")
        decoded_audit["sourceAlphaCounts"] = {str(key): value for key, value in decoded_audit["sourceAlphaCounts"].items()}
        output[TEXTURE_TARGET + suffix] = data
        audit[suffix] = {**decoded_audit, "nativeHeaderVerified": True,
                         "templateHeaderClassification": struct.unpack_from("<I", donor, 124)[0],
                         "headerClassificationInherited": True,
                         "sourceRgbaSha256": native.sha256(bytes(v for p in rgba for v in p))}
    return output, audit, decoder


def publish(output: Path, files: dict[str, bytes], report: dict) -> None:
    output = native.output_directory(output)
    payloads = dict(files)
    payloads["native-block-report.json"] = (json.dumps(report, indent=2) + "\n").encode()
    for name in payloads:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Unsafe native candidate output resource name")
        path = output / name
        native.check_links(path)
        temporary = path.with_suffix(path.suffix + ".tmp")
        native.check_links(temporary)
        if (path.exists() and not path.is_file()) or (temporary.exists() and not temporary.is_file()):
            raise ValueError("Native output or temporary file collides with a directory")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        native.check_links(path)
        native.check_links(temporary)
        temporary.write_bytes(data)
        temporary.replace(path)


def prepare(game: Path, output: Path, source: Path, deps: Path | None, asset: Path,
            decoder_python: Path) -> dict:
    output = native.output_directory(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Native candidate output must be new or empty; historical assets are never overwritten")
    native.check_links(game)
    provenance = native.load_cdmw(source, deps)
    if native.file_hash(game / "bin64/CrimsonDesert.exe") != native.EXE_SHA256:
        raise ValueError("Unsupported Crimson Desert EXE SHA; static preparation stopped")
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    from cdmw.core.prefab_binary import decode_prefab_binary, walk_is_determined
    from cdmw.core.prefab_binary_edit import rewrite_prefab_paths
    index = game / "0000/0.pamt"
    index_hash = native.file_hash(index)
    entries = native.select_unique_entries(parse_archive_pamt(index), tuple(TEMPLATE_HASHES))
    payloads = {path: _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
                for path, entry in entries.items()}
    pam, lod, layout, lod_layout = validate_template(payloads)
    mc_files, axes = read_mc(asset)
    textures, texture_audit, decoder = textures_candidate(payloads, mc_files, decoder_python)
    files = {"template/" + path: data for path, data in payloads.items()}
    resources, variants = [], []

    def add(path: str, data: bytes, kind: str, donor: str) -> None:
        local = "candidate/" + path
        files[local] = data
        resources.append({"virtualPath": path, "localFile": local, "sha256": native.sha256(data),
                          "kind": kind, "templatePath": donor, "templateSha256": TEMPLATE_HASHES[donor]})

    for path, data in textures.items():
        suffix = path[len(TEXTURE_TARGET):]
        add(path, data, "texture", TEX + suffix)
    for axis, faces in axes.items():
        base = f"object/00_common/system/crimsonmc_oak_log_{axis}"
        binary = f"object/bin__/00_common/system/crimsonmc_oak_log_{axis}"
        main, far, mapping = geometry_candidate(payloads, pam, lod, layout, lod_layout, faces)
        material = make_material(payloads[BASE + ".pami"], axis)
        rewritten = rewrite_prefab_paths(payloads[BIN_BASE + ".prefab"], {BASE + ".pami": base + ".pami"})
        if not walk_is_determined(rewritten.data) or [s.text for s in decode_prefab_binary(rewritten.data).all_strings()] != [base + ".pami"]:
            raise ValueError("New prefab path does not survive its complete structural walk")
        for path, data, kind, donor in (
            (base + ".pam", main, "staticMesh", BASE + ".pam"),
            (base + ".pamlod", far, "staticMeshLod", BASE + ".pamlod"),
            (base + ".pami", material, "material", BASE + ".pami"),
            (base + ".hkx", payloads[BASE + ".hkx"], "collision", BASE + ".hkx"),
            (binary + ".meshinfo", payloads[BIN_BASE + ".meshinfo"], "meshInfo", BIN_BASE + ".meshinfo"),
            (binary + ".prefab", rewritten.data, "prefab", BIN_BASE + ".prefab"),
        ):
            add(path, data, kind, donor)
        variants.append({"id": "minecraft:oak_log", "selector": "axis=" + axis,
                         "logicalPrefab": "/" + base + ".prefab", "physicalPrefab": binary + ".prefab",
                         "vertices": 24, "triangles": 12, "lodVertices": 24, "lodTriangles": 12,
                         "mcCornerMapping": mapping, "geometryRoundTrip": True, "uvRoundTrip": True,
                         "prefabStructuralWalkComplete": True, "prefabRelocatedPointers": rewritten.relocated_pointers})
    if native.file_hash(index) != index_hash:
        raise ValueError("Native archive index changed during static preparation")
    for path, entry in entries.items():
        if _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0] != payloads[path]:
            raise ValueError(f"Native template source changed during preparation: {path}")
    # All original-class MC files are checked again before publishing too.
    read_mc(asset)
    report = {"schemaVersion": 1, "supportedExeSha256": native.EXE_SHA256, "cdmw": provenance,
              "materialSerialization": MATERIAL_SERIALIZATION,
              "archiveIndex": "0000/0.pamt", "archiveIndexSha256": index_hash,
              "templateNoEditRebuildByteIdentical": {"pam": True, "pamlod": True, "prefab": True},
              "mcInputs": MC_HASHES, "candidateResources": resources, "variants": variants,
              "textureCandidates": texture_audit, "independentTextureDecoder": decoder,
              "files": {p: native.sha256(d) for p, d in files.items()},
              "integration": {"nativeRenderable": False, "installed": False, "collisionVerified": False,
                              "bridgeMapped": False, "minecraftSamplerVerified": False,
                              "nativeLightingVerified": False},
              "limitations": [
                  "Native blue proxy is a static PAM, not a skinned PAC; original unit-cube geometry stays within uint16 quantization tolerance.",
                  "Atlas pixels originate from the two actual 1.21.1 textures; BC1 compression is lossy, filtering/mip atlas seams and shading are unverified.",
                  "PAMI preserves the actual Standard shader. Flat normal/fully rough nonmetal textures are candidates; red-channel material meaning and represent colour are not behavior-verified.",
                  "The native V flip follows CDMW's offline interchange convention; in-game texture orientation remains unverified.",
                  "One original LOD is replaced with complete cube records. Opaque packed shading bytes come from the matching PAM corners, not guessed values.",
                  "Original HKX and binary meshinfo are copied without edits; collision loading, resource lifecycle, engine metadata registration and game load require separate acceptance.",
                  "Local licensed game/MC assets and derivatives must remain in ignored build and must not be redistributed.",
              ]}
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Native candidate output changed during preparation; historical assets are never overwritten")
    publish(output, files, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build/cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build/cdmw-deps")
    parser.add_argument("--block-asset", type=Path, default=ROOT / "build/block-assets-1.21.1")
    parser.add_argument("--decoder-python", type=Path, default=Path(shutil.which("python") or "python"))
    args = parser.parse_args()
    try:
        game = args.game_root or Path(json.loads((ROOT / "runtime/installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
        report = prepare(game, args.output, args.cdmw_source, args.deps, args.block_asset, args.decoder_python)
    except (OSError, ValueError, ImportError, KeyError, TypeError) as error:
        raise SystemExit(f"Native static-block preparation stopped: {error}") from error
    print(json.dumps({"output": str(native.output_directory(args.output)),
                      "variants": [{k: v for k, v in row.items() if k != "mcCornerMapping"} for row in report["variants"]],
                      "resources": len(report["candidateResources"]), "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
