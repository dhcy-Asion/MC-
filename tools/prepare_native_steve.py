"""Prepare a real Crimson Desert rig and an offline Steve PAC candidate.

Run with Python 3.12, after tools/build_steve_asset.py. CDMW is MIT and pinned
below; --download-source prepares its source in ignored build, without installing
an app. Its archive reader needs lz4==4.4.5 and cryptography==50.0.2; a local
--deps directory is optional. This tool never attaches to a process, modifies
game archives, installs an overlay, or claims the candidate renders in game.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import struct
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CDMW_COMMIT = "787680f97502522e90ec3dd1ea1889ca86452985"
CDMW_URL = f"https://codeload.github.com/Ratty123/CDMW-Full/zip/{CDMW_COMMIT}"
CDMW_ZIP_SHA256 = "4133d83dfbaf34a5e1483ce84d16008cae13382020feca5d6f887531d08d0d9c"
CDMW_SOURCE_SHA256 = "4eae434238c1fae03450774820150f82d0969288ed9506ce19578faa4a480f41"
CDMW_LICENSE_SHA256 = "e5ee37a74e136d5edd8c0991c138a5a40465f4a10a5f5dbc4809f7edda64efd1"
EXE_SHA256 = "57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7"
SKELETON = "character/model/1_pc/1_phm/phm_01.pab"
BODY = "character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac"
DESCRIPTOR = "character/prefab/1_pc/01_phm/nude/cd_phm_00_nude_00_0001.prefabdata_xml"
MATERIAL = "character/modelproperty/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac_xml"
VARIATION = "character/binary/skeletonvariation/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pabc"
CONSTRAINT = "character/model/1_pc/1_phm/phm_01.papr"
TEMPLATE_HASHES = {
    SKELETON: "9c8a966142902caa3cf140767db83575cf5d762193b6fe6bbe83f849f79748af",
    BODY: "27cd7d4f4b688bf7128e4ef4103c08cab07f410b8f94a8f3ad9b2ed07a65ba7c",
}
STEVE_HASHES = {
    "steve.gltf": "bc9cd38b3ebcab9702def27a425208bbfb2f6a1093012976d95f0c4d165e81b8",
    "steve.bin": "d03b7e6354652c7872b14b89d9d56861a23d2e910b52349f0e1da4c3101942a0",
    "steve.png": "d876e0c88f4b3de71040966ed94a614f315b888592b520b993399fd2738418d0",
}
# These names are really present in the verified body palette. Helper/twist bones
# are explicit candidate choices, not a claim of motion or equipment acceptance.
RIG_CANDIDATE = {
    "head": "Bip01 Head", "body": "Bip01 Spine_Sub",
    "right_arm": "Bip01 R UpArmTwist", "left_arm": "Bip01 L UpArmTwist",
    "right_leg": "Bip01 R Thigh", "left_leg": "Bip01 L Thigh",
}
OUTER_PARTS = {"hat": "head", "jacket": "body", "right_sleeve": "right_arm",
               "left_sleeve": "left_arm", "right_pants": "right_leg", "left_pants": "left_leg"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def check_links(path: Path) -> None:
    current = Path(os.path.abspath(path))
    while current != current.parent:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Native asset paths must not contain symlinks or junctions")
        current = current.parent


def output_directory(path: Path) -> Path:
    lexical = Path(os.path.abspath(path))
    build = ROOT / "build"
    if not lexical.is_relative_to(build) or lexical == build:
        raise ValueError("Licensed native/MC assets must stay in an ignored build subdirectory")
    check_links(lexical)
    return lexical.resolve()


def source_fingerprint(source: Path) -> str:
    check_links(source)
    rows = []
    for path in (source / "cdmw").rglob("*.py"):
        check_links(path)
        rows.append((path.relative_to(source).as_posix(), file_hash(path)))
    return sha256(json.dumps(sorted(rows), separators=(",", ":")).encode("utf-8"))


def verify_source(source: Path) -> dict:
    if source_fingerprint(source) != CDMW_SOURCE_SHA256:
        raise ValueError(f"CDMW Python source does not match fixed commit {CDMW_COMMIT}")
    if file_hash(source / "LICENSE") != CDMW_LICENSE_SHA256:
        raise ValueError("CDMW MIT license fingerprint mismatch")
    return {"repository": "https://github.com/Ratty123/CDMW-Full", "commit": CDMW_COMMIT,
            "sourceArchiveUrl": CDMW_URL, "archiveSha256": CDMW_ZIP_SHA256,
            "pythonSourceTreeSha256": CDMW_SOURCE_SHA256, "license": "MIT"}


def download_source(source: Path) -> None:
    """Extract only the hash-pinned Python package and license into ignored build."""
    source = output_directory(source)
    with urllib.request.urlopen(CDMW_URL, timeout=60) as response:
        archive = response.read(32 * 1024 * 1024 + 1)
    if len(archive) > 32 * 1024 * 1024 or sha256(archive) != CDMW_ZIP_SHA256:
        raise ValueError("CDMW fixed source archive failed its checksum/size limit")
    prefix = f"CDMW-Full-{CDMW_COMMIT}/"
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for info in bundle.infolist():
            if not info.filename.startswith(prefix):
                raise ValueError("Unexpected fixed source ZIP root")
            relative = info.filename[len(prefix):]
            parts = PurePosixPath(relative).parts
            if ".." in parts or PurePosixPath(relative).is_absolute() or "\\" in relative:
                raise ValueError("Unsafe fixed source ZIP member")
            if relative != "LICENSE" and not (relative.startswith("cdmw/") and relative.endswith(".py")):
                continue
            target = source / relative
            check_links(target)
            data = bundle.read(info)
            if target.exists() and target.read_bytes() != data:
                raise ValueError("Existing edited CDMW source retained; select a fresh source directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    verify_source(source)


def load_cdmw(source: Path, deps: Path | None) -> dict:
    provenance = verify_source(source)
    if any(name == "cdmw" or name.startswith("cdmw.") for name in sys.modules):
        raise ValueError("CDMW was already imported; use a clean Python process for fixed-source verification")
    sys.dont_write_bytecode = True
    if deps:
        sys.path.insert(0, str(deps.resolve()))
    sys.path.insert(0, str(source.resolve()))
    # These archive dependencies are pinned separately from CDMW's MIT source.
    from importlib.metadata import version
    for name, expected in (("lz4", "4.4.5"), ("cryptography", "50.0.2")):
        if version(name) != expected:
            raise ValueError(f"Native archive preparation requires {name}=={expected}")
    provenance["archiveDependencies"] = {"lz4": "4.4.5", "cryptography": "50.0.2"}
    return provenance


def select_unique_entries(entries: list, paths: tuple[str, ...]) -> dict:
    selected = {}
    for entry in entries:
        if entry.path not in paths:
            continue
        if entry.path in selected:
            raise ValueError(f"Ambiguous native archive path: {entry.path}")
        selected[entry.path] = entry
    missing = set(paths) - set(selected)
    if missing:
        raise ValueError(f"Missing native template dependencies: {sorted(missing)}")
    return selected


def validate_rig(skeleton: object, mesh: object, palette: tuple) -> dict:
    if skeleton.parser_mode != "fixed" or skeleton.parse_warning or skeleton.bone_count != 447:
        raise ValueError("Target PAB was not parsed as the reviewed 447-bone rig")
    if len(palette) != 189 or len(set(palette)) != len(palette):
        raise ValueError("Target body palette does not match the reviewed 189 unique bones")
    weighted = 0
    for part in mesh.submeshes:
        if part.source_vertex_stride != 40 or part.source_skin_weight_layout != "pac_slot_u10x6":
            raise ValueError("Native template has an unsupported skin layout")
        if len(part.vertices) != len(part.bone_indices) or len(part.vertices) != len(part.bone_weights):
            raise ValueError("Native template has incomplete skin rows")
        for indices, weights in zip(part.bone_indices, part.bone_weights):
            if len(indices) != len(weights) or not indices:
                raise ValueError("Native skin row is empty or inconsistent")
            if any(not math.isfinite(w) or w <= 0 for w in weights):
                raise ValueError("Native skin row contains invalid weights")
            if abs(sum(weights) - 1) > 1 / 255 + 1e-6:
                raise ValueError("Native skin row is not normalized")
            if any(not 0 <= index < len(palette) for index in indices):
                raise ValueError("Native weighted index exceeds the exact PAB palette")
            weighted += 1
    return {"skeletonBones": skeleton.bone_count, "paletteBones": len(palette),
            "weightedVertices": weighted, "drawDescriptors": len(mesh.submeshes),
            "vertices": mesh.total_vertices, "triangles": mesh.total_faces}


def rig_candidates(skeleton: object, palette: tuple) -> dict:
    result = {}
    for part, name in RIG_CANDIDATE.items():
        matches = [b for b in skeleton.bones if b.name == name]
        if len(matches) != 1 or palette.count(matches[0].index) != 1:
            raise ValueError(f"Candidate bone is missing or ambiguous in native palette: {name}")
        bone = matches[0]
        result[part] = {"boneName": name, "pabIndex": bone.index,
                        "paletteSlot": palette.index(bone.index), "nameHash": bone.name_hash,
                        "bindPosition": list(bone.bind_matrix[12:15]), "motionVerified": False}
    return result


def read_accessor(document: dict, binary: bytes, index: int, kind: str, component: int) -> list:
    accessor = document["accessors"][index]
    if accessor["type"] != kind or accessor["componentType"] != component or accessor.get("sparse"):
        raise ValueError("Unsupported Steve accessor shape")
    view = document["bufferViews"][accessor["bufferView"]]
    if view["buffer"] != 0 or view.get("byteStride"):
        raise ValueError("Unsupported Steve interleaved/multi-buffer layout")
    counts = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    code = {5126: "f", 5123: "H"}[component]
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    size = struct.calcsize("<" + code * counts[kind])
    end = offset + size * accessor["count"]
    if offset < view.get("byteOffset", 0) or end > view.get("byteOffset", 0) + view["byteLength"] or end > len(binary):
        raise ValueError("Steve accessor points outside its declared buffer")
    rows = list(struct.iter_unpack("<" + code * counts[kind], binary[offset:end]))
    if component == 5126 and any(not math.isfinite(value) for row in rows for value in row):
        raise ValueError("Steve accessor contains a non-finite value")
    return rows


def steve_geometry(asset: Path) -> list[dict]:
    check_links(asset)
    files = {name: (asset / name).read_bytes() for name in STEVE_HASHES}
    if any(sha256(files[name]) != expected for name, expected in STEVE_HASHES.items()):
        raise ValueError("Steve input is not the reviewed official 1.21.1 export; rebuild tools/build_steve_asset.py")
    document = json.loads(files["steve.gltf"])
    binary = files["steve.bin"]
    parts = []
    scale = document["nodes"][0]["scale"]
    if scale != [0.9375] * 3:
        raise ValueError("Unexpected official Steve renderer scale")
    for mesh in document["meshes"]:
        name = mesh["name"]
        parent = OUTER_PARTS.get(name, name)
        if parent not in RIG_CANDIDATE or len(mesh["primitives"]) != 1:
            raise ValueError("Unexpected Steve mesh part")
        primitive = mesh["primitives"][0]
        attributes = primitive["attributes"]
        positions = read_accessor(document, binary, attributes["POSITION"], "VEC3", 5126)
        normals = read_accessor(document, binary, attributes["NORMAL"], "VEC3", 5126)
        uvs = read_accessor(document, binary, attributes["TEXCOORD_0"], "VEC2", 5126)
        joints = read_accessor(document, binary, attributes["JOINTS_0"], "VEC4", 5123)
        weights = read_accessor(document, binary, attributes["WEIGHTS_0"], "VEC4", 5126)
        indices = [row[0] for row in read_accessor(document, binary, primitive["indices"], "SCALAR", 5123)]
        joint = tuple(RIG_CANDIDATE).index(parent)
        if any(row != (joint, 0, 0, 0) for row in joints) or any(row != (1, 0, 0, 0) for row in weights):
            raise ValueError("Official rigid Steve joint rows differ from reviewed geometry")
        if not len(positions) == len(normals) == len(uvs) == len(joints) == len(weights) or len(indices) % 3:
            raise ValueError("Incomplete Steve geometry rows")
        if any(not 0 <= index < len(positions) for index in indices):
            raise ValueError("Steve triangle references an invalid vertex")
        parts.append({"name": name, "parent": parent,
                      "vertices": [tuple(value * scale[axis] for axis, value in enumerate(row)) for row in positions],
                      "normals": normals, "uvs": uvs,
                      "faces": [tuple(indices[i:i + 3]) for i in range(0, len(indices), 3)]})
    if {p["name"] for p in parts} != set(RIG_CANDIDATE) | set(OUTER_PARTS):
        raise ValueError("Steve export is missing classic body/outer parts")
    return parts


def validate_runtime_descriptors(original_data: bytes, payload: bytes, original: object) -> tuple[list, int]:
    from cdmw.modding.mesh_parser import _parse_par_sections, _find_pac_descriptors
    source_sections = _parse_par_sections(original_data)
    target_sections = _parse_par_sections(payload)
    source = next(s for s in source_sections if s["index"] == 0)
    target = next(s for s in target_sections if s["index"] == 0)
    if source["size"] != target["size"]:
        raise ValueError("Candidate PAC changed the runtime metadata section size")
    old = bytearray(original_data[source["offset"]:source["offset"] + source["size"]])
    new = bytearray(payload[target["offset"]:target["offset"] + target["size"]])
    lods = old[4]
    descriptors = _find_pac_descriptors(original_data, source["offset"], source["size"], lods)
    if len(descriptors) != len(original.submeshes):
        raise ValueError("Template runtime descriptor boundary is ambiguous")
    target_descriptors = []
    for descriptor in descriptors:
        offset = descriptor.descriptor_offset - source["offset"]
        count_offset = offset + 40
        counts_size = descriptor.stored_lod_count * 6
        # Only bound floats and the per-LOD vertex/index counts may change.
        # Identity, material, palette, format flags and opaque metadata must survive.
        bounds = slice(offset + 11, offset + 35)
        counts = slice(count_offset, count_offset + counts_size)
        target_descriptor = copy.deepcopy(descriptor)
        target_descriptor.bbox_min = struct.unpack_from("<3f", new, offset + 11)
        target_descriptor.bbox_extent = struct.unpack_from("<3f", new, offset + 23)
        target_descriptor.vertex_counts = list(struct.unpack_from("<" + "H" * descriptor.stored_lod_count,
                                                                   new, count_offset))
        target_descriptor.index_counts = list(struct.unpack_from("<" + "I" * descriptor.stored_lod_count,
                                                                  new, count_offset + descriptor.stored_lod_count * 2))
        target_descriptor.descriptor_offset = target["offset"] + offset
        target_descriptors.append(target_descriptor)
        old[bounds] = new[bounds] = bytes(24)
        old[counts] = new[counts] = bytes(counts_size)
    # Metadata mirrors the rebuilt sections' absolute positions and the boundary
    # between 40-byte vertex records and u16 indices. Check these before masking.
    for lod in range(lods):
        section = next(s for s in target_sections if s["index"] == lods - lod)
        expected_split = section["offset"] + sum(d.vertex_counts[lod] * 40 for d in target_descriptors)
        if struct.unpack_from("<I", new, 5 + lod * 4)[0] != section["offset"]:
            raise ValueError("Candidate PAC contains an incorrect mirrored LOD offset")
        if struct.unpack_from("<I", new, 5 + lods * 4 + lod * 4)[0] != expected_split:
            raise ValueError("Candidate PAC contains an incorrect vertex/index boundary")
    old[5:5 + lods * 8] = new[5:5 + lods * 8] = bytes(lods * 8)
    if old != new:
        raise ValueError("Candidate PAC changed unreviewed runtime descriptor/metadata bytes")
    return target_descriptors, lods


def keep_complete_geometry_at_all_lods(payload: bytes, original_data: bytes) -> bytes:
    """Retain the small Steve mesh at every existing LOD, without triangle sampling.

    CDMW's generic replacement downsamples according to the large donor's LOD
    ratios, leaving only three triangles at distance here. PAR section sizes and
    metadata offsets are already bounded by its writer. Reuse its exact LOD0
    records; only the documented size/offset/count fields are then re-encoded.
    """
    from cdmw.modding.mesh_parser import _parse_par_sections, _find_pac_descriptors
    sections = {s["index"]: s for s in _parse_par_sections(payload)}
    source = _parse_par_sections(original_data)[0]
    metadata = bytearray(payload[sections[0]["offset"]:sections[0]["offset"] + sections[0]["size"]])
    lods = metadata[4]
    descriptors = _find_pac_descriptors(original_data, source["offset"], source["size"], lods)
    vertex_bytes = 0
    for descriptor in descriptors:
        relative = descriptor.descriptor_offset - source["offset"]
        count_offset = relative + 40
        count = descriptor.stored_lod_count
        vertices = struct.unpack_from("<H", metadata, count_offset)[0]
        indices = struct.unpack_from("<I", metadata, count_offset + count * 2)[0]
        vertex_bytes += vertices * 40
        struct.pack_into("<" + "H" * count, metadata, count_offset, *([vertices] * count))
        struct.pack_into("<" + "I" * count, metadata, count_offset + count * 2, *([indices] * count))
    base = sections[lods]
    base_bytes = payload[base["offset"]:base["offset"] + base["size"]]
    stored = {i: payload[s["offset"]:s["offset"] + s["size"]] for i, s in sections.items()}
    for index in range(1, lods + 1):
        stored[index] = base_bytes
    stored[0] = bytes(metadata)
    offsets = {}
    next_offset = 0x50
    for index in sorted(stored):
        offsets[index] = next_offset
        next_offset += len(stored[index])
    for lod in range(lods):
        start = offsets[lods - lod]
        struct.pack_into("<I", metadata, 5 + lod * 4, start)
        struct.pack_into("<I", metadata, 5 + lods * 4 + lod * 4, start + vertex_bytes)
    stored[0] = bytes(metadata)
    header = bytearray(payload[:0x50])
    for index in range(8):
        struct.pack_into("<II", header, 0x10 + index * 8, 0, len(stored.get(index, b"")))
    return bytes(header) + b"".join(stored[index] for index in sorted(stored))


def make_candidate(original: object, data: bytes, parts: list[dict], mapping: dict) -> tuple[bytes, dict]:
    from cdmw.modding.mesh_pac_builder import _build_pac_full_rebuild
    from cdmw.modding.mesh_parser import parse_pac
    working = copy.deepcopy(original)
    if len(working.submeshes) != 3:
        raise ValueError("Unsupported native runtime draw descriptor set")
    for part in working.submeshes:
        for channel in ("vertices", "normals", "uvs", "faces", "bone_indices", "bone_weights", "source_vertex_map"):
            setattr(part, channel, [])
        part.clean_donor_shading_records = True
    offsets = []
    for part in parts:
        target_index = 0 if part["parent"] == "head" else 2
        target = working.submeshes[target_index]
        base = len(target.vertices)
        slot = mapping[part["parent"]]["paletteSlot"]
        target.vertices.extend(part["vertices"])
        target.normals.extend(part["normals"])
        # glTF uses top-origin image UVs; the native PAC convention is bottom-origin.
        target.uvs.extend((u, 1 - v) for u, v in part["uvs"])
        target.faces.extend(tuple(i + base for i in face) for face in part["faces"])
        target.bone_indices.extend([(slot,)] * len(part["vertices"]))
        target.bone_weights.extend([(1.0,)] * len(part["vertices"]))
        offsets.append({"part": part["name"], "nativeDrawSlot": target_index, "firstVertex": base,
                        "vertexCount": len(part["vertices"]), "paletteSlot": slot})
    payload = _build_pac_full_rebuild(original, working, data, preserve_runtime_abi=True)
    payload = keep_complete_geometry_at_all_lods(payload, data)
    descriptors, lods = validate_runtime_descriptors(data, payload, original)
    parsed = parse_pac(payload, original.path)
    # Quantized native geometry and half-float UVs are compared to the authored
    # output. Merely obtaining bytes from the serializer is not acceptance.
    found_by_name = {part.name: part for part in parsed.submeshes}
    for wanted in working.submeshes:
        if not wanted.vertices:
            if wanted.name in found_by_name and found_by_name[wanted.name].vertices:
                raise ValueError("Candidate PAC revived an empty runtime draw slot")
            continue
        found = found_by_name.get(wanted.name)
        if found is None:
            raise ValueError(f"Candidate PAC lost runtime draw slot: {wanted.name}")
        if wanted.faces != found.faces or len(wanted.vertices) != len(found.vertices):
            raise ValueError(f"Candidate PAC changed authored triangle topology: {wanted.name} "
                             f"({len(wanted.vertices)}/{len(found.vertices)} vertices, "
                             f"{len(wanted.faces)}/{len(found.faces)} triangles)")
        if wanted.bone_indices != found.bone_indices or wanted.bone_weights != found.bone_weights:
            raise ValueError("Candidate PAC did not preserve exact rigid native skin rows")
        if any(abs(a - b) > 0.0001 for wa, fa in zip(wanted.vertices, found.vertices) for a, b in zip(wa, fa)):
            raise ValueError("Candidate PAC positions exceed native quantization tolerance")
        if any(abs(a - b) > 0.0005 for wa, fa in zip(wanted.uvs, found.uvs) for a, b in zip(wa, fa)):
            raise ValueError("Candidate PAC UVs exceed half-float tolerance")
    from cdmw.modding.mesh_parser import _parse_par_sections, _parse_pac_geometry_section
    checked_lods = []
    for section in _parse_par_sections(payload):
        if not 1 <= section["index"] <= lods:
            continue
        lod = lods - section["index"]
        decoded = _parse_pac_geometry_section(payload, original.path, descriptors, section, lod)
        if decoded.total_vertices != parsed.total_vertices or decoded.total_faces != parsed.total_faces:
            raise ValueError(f"Candidate PAC LOD {lod} does not contain the complete Steve topology: "
                             f"{decoded.total_vertices}/{parsed.total_vertices} vertices, "
                             f"{decoded.total_faces}/{parsed.total_faces} triangles")
        if [(p.bone_indices, p.bone_weights) for p in decoded.submeshes] != [(p.bone_indices, p.bone_weights) for p in parsed.submeshes]:
            raise ValueError("Candidate PAC LOD contains different native skin rows")
        checked_lods.append(lod)
    if len(checked_lods) != lods:
        raise ValueError("Candidate PAC lost an original runtime LOD section")
    return payload, {"vertices": parsed.total_vertices, "triangles": parsed.total_faces,
                     "partRanges": offsets, "geometryRoundTrip": True, "skinRoundTrip": True,
                     "uvRoundTrip": True, "preservedRuntimeDrawDescriptors": True,
                     "storedDrawDescriptors": len(descriptors), "activeDrawDescriptors": len(parsed.submeshes),
                     "verifiedLods": sorted(checked_lods),
                     "uvConvention": "glTF top-origin V converted to native bottom-origin V"}


def publish_files(output: Path, files: dict[str, bytes], report: dict) -> None:
    output = output_directory(output)
    payloads = dict(files)
    payloads["native-steve-report.json"] = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    # Inspect all final/temporary paths before any result is published, including
    # the report. A symlinked report must not bypass the licensed-output boundary.
    for name in payloads:
        path = output / name
        check_links(path)
        check_links(path.with_suffix(path.suffix + ".tmp"))
    output.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        check_links(target)
        temporary = target.with_suffix(target.suffix + ".tmp")
        check_links(temporary)
        temporary.write_bytes(data)
        temporary.replace(target)


def prepare(game: Path, output: Path, source: Path, deps: Path | None,
            asset: Path, template_only: bool = False) -> dict:
    output = output_directory(output)
    provenance = load_cdmw(source, deps)
    if file_hash(game / "bin64" / "CrimsonDesert.exe") != EXE_SHA256:
        raise ValueError("Unsupported Crimson Desert EXE SHA; native preparation stopped")
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    from cdmw.modding.mesh_parser import parse_pac, resolve_pac_bone_palette
    from cdmw.modding.mesh_importer import rebuild_mesh_with_report
    from cdmw.modding.skeleton_parser import parse_pab
    import xml.etree.ElementTree as ET
    index = game / "0009" / "0.pamt"
    index_hash = file_hash(index)
    entries = parse_archive_pamt(index)
    paths = (SKELETON, BODY, DESCRIPTOR, MATERIAL, VARIATION, CONSTRAINT)
    selected = select_unique_entries(entries, paths)
    # Use the reviewed in-process decoder directly. No accelerator subprocess,
    # native game function, engine loader, archive mutation service, or fallback.
    payloads = {path: _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
                for path, entry in selected.items()}
    for path, expected in TEMPLATE_HASHES.items():
        if sha256(payloads[path]) != expected:
            raise ValueError(f"Native template SHA mismatch: {path}")
    descriptor = ET.fromstring(payloads[DESCRIPTOR].decode("utf-8-sig"))
    if descriptor.find("SkeletonName").attrib["FileName"].casefold() != "1_pc/1_phm/phm_01.pab":
        raise ValueError("Native body descriptor does not name the exact target skeleton")
    skeleton = parse_pab(payloads[SKELETON], SKELETON)
    mesh = parse_pac(payloads[BODY], BODY)
    palette = resolve_pac_bone_palette(payloads[BODY], skeleton)
    audit = validate_rig(skeleton, mesh, palette)
    roundtrip = rebuild_mesh_with_report(mesh, payloads[BODY], original_mesh=mesh)
    if roundtrip.data != payloads[BODY] or not roundtrip.report.byte_identical:
        raise ValueError("Native PAC no-edit rebuild was not byte-identical")
    mapping = rig_candidates(skeleton, palette)
    candidate = None
    candidate_audit = None
    if not template_only:
        candidate, candidate_audit = make_candidate(mesh, payloads[BODY], steve_geometry(asset), mapping)
        candidate_palette = resolve_pac_bone_palette(candidate, skeleton)
        if candidate_palette != palette:
            raise ValueError("Steve candidate changed the native bone palette")
        validate_rig(skeleton, parse_pac(candidate, BODY), candidate_palette)
    if file_hash(index) != index_hash:
        raise ValueError("Native archive index changed during offline preparation")
    # Re-read every consumed entry so concurrent archive replacement cannot
    # combine a skeleton, geometry and descriptor from different snapshots.
    for path, entry in selected.items():
        if _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0] != payloads[path]:
            raise ValueError(f"Native source changed during preparation: {path}")
    files = {f"template/{path}": data for path, data in payloads.items()}
    if candidate:
        files["steve-rig-candidate.pac"] = candidate
    report = {
        "schemaVersion": 1, "supportedExeSha256": EXE_SHA256, "cdmw": provenance,
        "archiveIndexSha256": index_hash, "template": audit,
        "templateNoEditRebuildByteIdentical": True, "rigMappingCandidates": mapping,
        "palette": [{"slot": slot, "pabIndex": index, "boneName": skeleton.bones[index].name}
                    for slot, index in enumerate(palette)],
        "candidate": candidate_audit, "files": {name: sha256(data) for name, data in files.items()},
        "integration": {"nativeMaterialPrepared": False, "animationVerified": False,
                        "equipmentBound": False, "controlledAppearanceBound": False,
                        "nativeRenderable": False, "installed": False},
        "limitations": [
            "Candidate rigid parts use real target-rig palette slots; twist/helper mapping needs animation and fit checks.",
        "Template material, morph, wrinkle, physics and appearance dependencies are unmodified; no Steve skin is bound.",
            "The two-layer MC alpha materials are not authored into native shaders; UV orientation is an offline convention.",
            "No game load, lifecycle, restoring appearance, weapons, armour, socket, or control behavior has been tested.",
            "Local licensed game templates and MC-derived geometry stay in ignored build and must not be redistributed.",
        ],
    }
    publish_files(output, files, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "native-steve")
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build" / "cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build" / "cdmw-deps")
    parser.add_argument("--steve-asset", type=Path, default=ROOT / "build" / "steve-1.21.1")
    parser.add_argument("--download-source", action="store_true")
    parser.add_argument("--template-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.download_source:
            download_source(args.cdmw_source)
        game = args.game_root
        if game is None:
            game = Path(json.loads((ROOT / "runtime" / "installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
        report = prepare(game, args.output, args.cdmw_source, args.deps, args.steve_asset, args.template_only)
    except (OSError, ValueError, ImportError, KeyError) as error:
        raise SystemExit(f"Native asset preparation stopped: {error}") from error
    print(json.dumps({"output": str(output_directory(args.output)), "template": report["template"],
                      "candidate": report["candidate"], "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
